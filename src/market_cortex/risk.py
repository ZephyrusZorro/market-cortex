"""Deterministic, research-only portfolio risk over pinned daily observations."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, NAMESPACE_URL, uuid5

from .alignment import compare
from .database import connect
from .features import FeatureEngine, FeatureRequest
from .market_state import MarketStateEngine, MarketStateRequest
from .opportunity_store import OpportunityStore
from .portfolio_store import PortfolioStore
from .risk_contracts import (OverlayRequest, Portfolio, PortfolioExposure, PositionInput,
                             PositionRisk, RiskRequest, RiskSnapshot, ScenarioDefinition,
                             ScenarioResult, SizingRequest)
from .storage import PostgresCatalog
from .workstation import build_context


VERSION = "portfolio_risk_daily_v1"
CODE_HASH = hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
CENTRAL_CONCENTRATION_THRESHOLD = Decimal("0.35")
CLUSTER_CORRELATION_THRESHOLD = .8
CLUSTER_WEIGHT_THRESHOLD = Decimal("0.50")
Q = Decimal("0.00000001")


def money(value: Decimal) -> Decimal:
    return value.quantize(Q)


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str,
                                     separators=(",", ":")).encode()).hexdigest()


def snapshot_identity(snapshot: RiskSnapshot) -> UUID:
    """Address the complete persisted payload, including correlations and warnings."""
    return uuid5(NAMESPACE_URL, digest(snapshot.model_dump(mode="json", exclude={"snapshot_id"})))


def research_sizing(request: SizingRequest) -> dict:
    budget = request.risk_amount if request.risk_amount is not None else request.capital * request.risk_percent
    distance = request.entry_price - request.invalidation_price
    quantity = budget / distance
    return {"label": "research sizing", "method": "fixed_monetary_risk" if request.risk_amount
        else "fixed_fractional_risk", "risk_budget": money(budget),
        "risk_per_unit": money(distance), "hypothetical_quantity": money(quantity),
        "hypothetical_notional": money(quantity * request.entry_price),
        "capital": request.capital,
        "target_r": money((request.target_price-request.entry_price)/distance)
            if request.target_price is not None else None,
        "reward_to_risk": money((request.target_price-request.entry_price)/distance)
            if request.target_price is not None else None,
        "warning": "Hypothetical research only; no order quantity or execution"}


def calculate_position(position: PositionInput, symbol: str, price: Decimal | None,
                       price_session: str | None, observation_id: UUID | None,
                       features: dict[str, tuple[float | None, str]],
                       freshness: str, coverage: float,
                       thesis_invalidation: Decimal | None = None,
                       data_quality: str = "valid") -> PositionRisk:
    warnings = []
    invalidation = position.invalidation_price or thesis_invalidation
    source = "owner_explicit" if position.invalidation_price is not None else \
             "thesis_condition" if thesis_invalidation is not None else None
    if invalidation is None:
        warnings.append("RISK_UNBOUNDED_OR_UNKNOWN:INVALIDATION_MISSING")
    if freshness != "current":
        warnings.append(f"PRICE_NOT_CURRENT:{freshness}")
    if price is None:
        warnings.append("PRICE_UNAVAILABLE")
    if coverage < .9:
        warnings.append("FEATURE_COVERAGE_BELOW_90_PERCENT")
    if data_quality not in ("valid", "corrected"):
        warnings.append(f"PRICE_QUALITY_UNCERTAIN:{data_quality}")
    value = money(position.quantity * price) if price is not None else None
    cost = money(position.quantity * position.average_cost)
    pnl = money(value - cost) if value is not None else None
    pnl_pct = money((price / position.average_cost) - 1) if price is not None else None
    one_r = money((position.average_cost - invalidation) * position.quantity) if invalidation else None
    distance = money(price - invalidation) if price is not None and invalidation else None
    current_r = money((price-position.average_cost)/(position.average_cost-invalidation)) \
        if price is not None and invalidation is not None and position.average_cost > invalidation else None
    target_r = money((position.target_price-position.average_cost)/(position.average_cost-invalidation)) \
        if position.target_price is not None and invalidation is not None and position.average_cost > invalidation else None
    if invalidation is not None and price is not None and price <= invalidation:
        warnings.append("INVALIDATION_BREACHED_RISK_NOT_ZERO")
    risk = money(distance * position.quantity) if distance is not None and distance > 0 else None
    pct = money(distance / price) if distance is not None and distance > 0 and price else None
    names = {key: features.get(key, (None, ""))[0] for key in
        ("annualized_volatility", "atr", "volatility_percentile", "drawdown",
         "maximum_drawdown", "drawdown_duration", "recovery_state")}
    for key in ("annualized_volatility", "atr", "volatility_percentile"):
        if names[key] is None:
            warnings.append(f"FEATURE_UNAVAILABLE:{key}")
    return PositionRisk(position_id=position.position_id, instrument_id=position.instrument_id,
        symbol=symbol, native_currency=position.native_currency, quantity=position.quantity,
        reference_price=price, price_session=price_session, price_observation_id=observation_id,
        market_value=value, cost_basis=cost, unrealized_pnl=pnl, pnl_percent=pnl_pct,
        annualized_volatility=names["annualized_volatility"], atr14=names["atr"],
        volatility_rank90=names["volatility_percentile"], drawdown=names["drawdown"],
        maximum_drawdown=names["maximum_drawdown"], drawdown_duration=names["drawdown_duration"],
        recovery_state=names["recovery_state"], invalidation_price=invalidation,
        invalidation_source=source, distance_to_invalidation=distance,
        risk_to_invalidation=risk, risk_percent_of_value=pct, one_r=one_r,
        current_r=current_r, target_r=target_r, reward_to_risk=target_r,
        freshness=freshness, data_quality=data_quality, coverage=coverage,
        feature_ids={key: value[1] for key, value in features.items() if value[1]},
        warnings=warnings, thesis_id=position.thesis_id)


def run_scenario(snapshot: RiskSnapshot, scenario: ScenarioDefinition) -> ScenarioResult:
    contributions: dict[str, Decimal | None] = {}
    by_currency: dict[str, Decimal] = {}
    warnings = ["WHAT_IF_NOT_FORECAST"]
    for position in snapshot.positions:
        shock = scenario.shocks.get(position.symbol, Decimal(0))
        if shock == 0:
            contribution = Decimal(0)
        elif position.market_value is None:
            contributions[str(position.position_id)] = None
            warnings.append(f"PRICE_UNAVAILABLE:{position.symbol}")
            continue
        else:
            contribution = money(position.market_value * shock)
        contributions[str(position.position_id)] = contribution
        by_currency[position.native_currency] = money(
            by_currency.get(position.native_currency, Decimal(0)) + contribution)
    complete = all(value is not None for value in contributions.values())
    same_currency = all(item.native_currency == snapshot.base_currency for item in snapshot.positions)
    total = by_currency.get(snapshot.base_currency, Decimal(0)) if complete and same_currency else None
    if not same_currency:
        warnings.append("FX_CONVERSION_UNAVAILABLE")
    return ScenarioResult(snapshot_id=snapshot.snapshot_id, scenario=scenario,
        position_pnl=contributions, currency_pnl=by_currency,
        portfolio_pnl=total, portfolio_change_percent=money(total/snapshot.capital)
            if total is not None else None,
        coverage=sum(value is not None for value in contributions.values())/len(contributions)
            if contributions else 1.0, warnings=list(dict.fromkeys(warnings)))


class RiskService:
    def __init__(self, catalog: PostgresCatalog, environment: str):
        self.catalog = catalog
        self.store = PortfolioStore(catalog.dsn, environment)
        self.features = FeatureEngine(catalog)

    def validate_position(self, position: PositionInput, portfolio: Portfolio) -> None:
        identities, _ = self.catalog.load_identity()
        instrument = next((item for item in identities if item.instrument_id == position.instrument_id), None)
        if instrument is None or instrument.trading_currency != position.native_currency:
            raise ValueError("INSTRUMENT_OR_CURRENCY_MISMATCH")
        if position.source_type == "synthetic_fixture" and portfolio.classification != "SYNTHETIC_TEST_PORTFOLIO":
            raise ValueError("SYNTHETIC_POSITION_REQUIRES_TEST_PORTFOLIO")
        if position.thesis_id:
            thesis = OpportunityStore(self.catalog.dsn).thesis(position.thesis_id)
            if thesis is None or thesis.instrument_id != position.instrument_id:
                raise ValueError("THESIS_INSTRUMENT_MISMATCH")

    def _manifest_ancestors(self, manifest: UUID) -> set[UUID]:
        with connect(self.catalog.dsn) as connection:
            rows = connection.execute("""WITH RECURSIVE chain AS (
                SELECT manifest_id,parent_manifest_id FROM dataset_manifests WHERE manifest_id=%s
                UNION ALL SELECT m.manifest_id,m.parent_manifest_id FROM dataset_manifests m
                JOIN chain ON chain.parent_manifest_id=m.manifest_id)
                SELECT manifest_id FROM chain""", (manifest,)).fetchall()
        return {row[0] for row in rows}

    def _thesis_invalidation(self, position: PositionInput, cutoff: datetime,
                             visible_manifests: set[UUID]) -> Decimal | None:
        if not position.thesis_id:
            return None
        versions = OpportunityStore(self.catalog.dsn).versions(position.thesis_id)
        visible = [item for item in versions if item.updated_at <= cutoff and
                   item.as_of <= cutoff and item.source_manifest_id in visible_manifests]
        if not visible:
            return None
        thesis = visible[-1]
        for condition in thesis.invalidation_conditions:
            if condition.metric == "close" and condition.operator in ("lt", "lte") and \
                    isinstance(condition.threshold, (int, float)) and condition.threshold > 0:
                level = Decimal(str(condition.threshold))
                if level < position.average_cost:
                    return level
        return None

    def snapshot(self, portfolio_id: UUID, request: RiskRequest,
                 *, overlay: PositionInput | None = None) -> RiskSnapshot:
        cutoff = request.as_of or datetime.now(timezone.utc)
        version = request.portfolio_version
        if version is None:
            visible = [item["version"] for item in self.store.versions(portfolio_id)
                       if datetime.fromisoformat(item["recorded_at"]) <= cutoff]
            version = max(visible) if visible else None
        portfolio = self.store.get(portfolio_id, version) if version is not None else None
        if portfolio is None:
            raise LookupError("PORTFOLIO_NOT_VISIBLE_AT_CUTOFF")
        if portfolio.updated_at > cutoff:
            raise ValueError("PORTFOLIO_VERSION_NOT_YET_KNOWN_AT_CUTOFF")
        context = build_context(self.catalog, as_of=cutoff, manifest_id=request.manifest_id)
        manifest = UUID(context["source_manifest_id"])
        if datetime.fromisoformat(context["manifest"]["created_at"]) > cutoff:
            raise ValueError("MANIFEST_NOT_YET_KNOWN_AT_CUTOFF")
        visible_manifests = self._manifest_ancestors(manifest)
        members = {UUID(item["instrument_id"]): item for item in context["members"] if item["instrument_id"]}
        positions = [item for item in portfolio.positions if item.opened_at <= cutoff and
                     (item.closed_at is None or item.closed_at > cutoff)]
        if overlay is not None:
            self.validate_position(overlay, portfolio)
            if overlay.thesis_id and not any(item.updated_at <= cutoff and item.as_of <= cutoff and
                item.source_manifest_id in visible_manifests for item in
                    OpportunityStore(self.catalog.dsn).versions(overlay.thesis_id)):
                raise ValueError("THESIS_NOT_VISIBLE_IN_RISK_CONTEXT")
            if any(item.position_id == overlay.position_id for item in portfolio.positions):
                raise ValueError("OVERLAY_POSITION_ID_ALREADY_EXISTS")
            positions.append(overlay)
        series_by_symbol = {}
        result_positions = []
        warnings = []
        for position in positions:
            member = members.get(position.instrument_id)
            if member is None or not member["last_session"] or not member["first_session"]:
                symbol = "UNMAPPED"
                result_positions.append(calculate_position(position, symbol, None, None, None,
                    {}, "unknown", 0))
                warnings.append(f"PILOT_MAPPING_OR_HISTORY_UNAVAILABLE:{position.position_id}")
                continue
            symbol = member["symbol"]
            end = datetime.fromisoformat(member["last_session"]).date()
            start = max(datetime.fromisoformat(member["first_session"]).date(), end-timedelta(days=180))
            loaded = self.features.load(instrument_id=position.instrument_id,
                start_date=start, end_date=end, as_of=cutoff, manifest_id=manifest,
                provider_id="binance")
            series_by_symbol[symbol] = loaded
            bar = loaded.bars[-1] if loaded.bars else None
            coverage = sum(item is not None for item in loaded.bars)/len(loaded.bars) if loaded.bars else 0
            computed = {}
            for key, params in (("annualized_volatility", {"period":20}), ("atr", {"period":14}),
                                ("volatility_percentile", {"period":20,"rank_window":90}),
                                ("drawdown", {}), ("maximum_drawdown", {}),
                                ("drawdown_duration", {}), ("recovery_state", {})):
                output = self.features.calculate(FeatureRequest(instrument_id=position.instrument_id,
                    feature=key, start_date=start, end_date=end, as_of=cutoff,
                    manifest_id=manifest, provider_id="binance", parameters=params), loaded)
                computed[key] = (output.points[-1].value, output.feature_id)
            result_positions.append(calculate_position(position, symbol,
                Decimal(str(bar.close)) if bar else None,
                str(bar.session_date) if bar else None,
                bar.envelope.observation_id if bar else None,
                computed, loaded.freshness_state, coverage,
                self._thesis_invalidation(position, cutoff, visible_manifests),
                bar.envelope.quality_state if bar else "unavailable"))
        if positions and "BTCUSDT" not in series_by_symbol:
            benchmark = next((item for item in context["members"] if item["symbol"] == "BTCUSDT"), None)
            if benchmark and benchmark["instrument_id"] and benchmark["last_session"] and benchmark["first_session"]:
                end = datetime.fromisoformat(benchmark["last_session"]).date()
                start = max(datetime.fromisoformat(benchmark["first_session"]).date(),
                            end-timedelta(days=180))
                series_by_symbol["BTCUSDT"] = self.features.load(
                    instrument_id=UUID(benchmark["instrument_id"]), start_date=start,
                    end_date=end, as_of=cutoff, manifest_id=manifest, provider_id="binance")
        state_regime = None
        state_freshness = "unknown"
        if context["evaluation_date"] and context["history_start"]:
            state = MarketStateEngine(self.catalog).compute(MarketStateRequest(
                history_start=max(datetime.fromisoformat(context["history_start"]).date(),
                                  datetime.fromisoformat(context["evaluation_date"]).date()-timedelta(days=180)),
                evaluation_date=datetime.fromisoformat(context["evaluation_date"]).date(),
                as_of=cutoff, manifest_id=manifest))
            state_regime = state.regime.category
            state_freshness = next((item.freshness for item in state.dimensions
                                    if item.name == "data_freshness"), "unknown")
        exposure_by_instrument: dict[str, Decimal] = {}
        exposure_by_currency: dict[str, Decimal] = {}
        exposure_by_strategy: dict[str, Decimal] = {}
        exposure_by_provider: dict[str, Decimal] = {}
        for position in result_positions:
            if position.market_value is None:
                continue
            exposure_by_instrument[position.symbol] = money(exposure_by_instrument.get(position.symbol, Decimal(0)) + position.market_value)
            exposure_by_currency[position.native_currency] = money(exposure_by_currency.get(position.native_currency, Decimal(0)) + position.market_value)
            strategy = next((item.thesis_id for item in positions if item.position_id == position.position_id), None)
            name = str(strategy) if strategy else "unlinked"
            exposure_by_strategy[name] = money(exposure_by_strategy.get(name, Decimal(0)) + position.market_value)
            exposure_by_provider["binance"] = money(exposure_by_provider.get("binance", Decimal(0)) + position.market_value)
        all_known = all(item.market_value is not None for item in result_positions)
        common_currency = all(item.native_currency == portfolio.base_currency for item in result_positions)
        gross = sum(exposure_by_currency.values(), Decimal(0)) if all_known and common_currency else None
        if gross is not None:
            gross = money(gross)
        portfolio_pnl = money(sum((item.unrealized_pnl for item in result_positions), Decimal(0))) \
            if all_known and common_currency else None
        weights = {symbol: money(value/gross) for symbol, value in exposure_by_instrument.items()} if gross else {}
        flags = [symbol for symbol, weight in weights.items() if weight >= CENTRAL_CONCENTRATION_THRESHOLD]
        if gross is None and result_positions:
            warnings.append("GROSS_EXPOSURE_UNAVAILABLE_MISSING_PRICE_OR_FX")
        unknown = [item.position_id for item in result_positions if item.risk_to_invalidation is None]
        heat_by_position = {str(item.position_id): item.risk_to_invalidation for item in result_positions}
        heat_amount = money(sum((item.risk_to_invalidation for item in result_positions), Decimal(0))) \
            if not unknown and common_currency else None
        if unknown:
            warnings.append("RISK_UNBOUNDED_OR_UNKNOWN")
        if not common_currency:
            warnings.append("FX_CONVERSION_UNAVAILABLE")
        heat_strategy: dict[str, Decimal | None] = {}
        heat_asset: dict[str, Decimal | None] = {}
        for item in result_positions:
            source = next(p for p in positions if p.position_id == item.position_id)
            key = str(source.thesis_id) if source.thesis_id else "unlinked"
            if item.risk_to_invalidation is None:
                heat_strategy[key] = None
                heat_asset["crypto_spot"] = None
            else:
                if heat_strategy.get(key, Decimal(0)) is not None:
                    heat_strategy[key] = money(heat_strategy.get(key, Decimal(0)) + item.risk_to_invalidation)
                if heat_asset.get("crypto_spot", Decimal(0)) is not None:
                    heat_asset["crypto_spot"] = money(heat_asset.get("crypto_spot", Decimal(0)) + item.risk_to_invalidation)
        correlations = []
        symbols = sorted(series_by_symbol)
        for left_index, left in enumerate(symbols):
            for right in symbols[left_index+1:]:
                result = compare(series_by_symbol[left], series_by_symbol[right], kind="correlation", window=60)
                point = result.points[-1]
                correlations.append({"left":left,"right":right,"correlation":point.value,
                    "sample_count":point.observation_count,"coverage":point.coverage,
                    "result_id":result.result_id,"unknown_reason":point.unknown_reason,
                    "manifest_id":str(manifest),"as_of":cutoff.isoformat()})
        if len(symbols) > 1 and any(row["correlation"] is None for row in correlations):
            warnings.append("CORRELATION_HISTORY_INSUFFICIENT")
        if state_regime in (None, "insufficient_data"):
            warnings.append("MARKET_STATE_UNAVAILABLE")
        if state_freshness != "current":
            warnings.append(f"MARKET_STATE_NOT_CURRENT:{state_freshness}")
        if any(item.freshness != "current" for item in result_positions):
            warnings.append("PRICE_OR_FEATURE_DATA_STALE")
        # A weighted correlation is a sensitivity proxy, not regression beta.
        btc_proxy = None
        if gross is not None and gross > 0 and "BTCUSDT" in series_by_symbol:
            total = exposure_by_instrument.get("BTCUSDT", Decimal(0))
            for symbol, value in exposure_by_instrument.items():
                if symbol == "BTCUSDT":
                    continue
                row = next((item for item in correlations if {item["left"],item["right"]} ==
                            {symbol,"BTCUSDT"}), None)
                if row is None or row["correlation"] is None:
                    total = None
                    break
                total += value * Decimal(str(row["correlation"]))
            if total is not None:
                btc_proxy = money(total/portfolio.capital)
        held_symbols = set(exposure_by_instrument)
        cluster_flags = [f"{row['left']}+{row['right']}" for row in correlations
            if row["left"] in held_symbols and row["right"] in held_symbols and
            row["correlation"] is not None and row["correlation"] >= CLUSTER_CORRELATION_THRESHOLD and
            weights.get(row["left"], Decimal(0)) + weights.get(row["right"], Decimal(0)) >= CLUSTER_WEIGHT_THRESHOLD]
        if cluster_flags:
            warnings.append("CORRELATED_CLUSTER_CONCENTRATION")
        if not common_currency:
            heat_strategy = {key: None for key in heat_strategy}
            heat_asset = {key: None for key in heat_asset}
        exposure = PortfolioExposure(by_instrument=exposure_by_instrument,
            by_asset_class={f"crypto_spot:{currency}": value for currency, value in exposure_by_currency.items()},
            by_currency=exposure_by_currency, by_strategy=exposure_by_strategy,
            by_provider=exposure_by_provider, gross=gross, net=gross,
            currency=portfolio.base_currency if gross is not None else None,
            concentration_weights=weights, concentration_threshold=CENTRAL_CONCENTRATION_THRESHOLD,
            concentration_flags=flags)
        snapshot = RiskSnapshot(snapshot_id=UUID(int=0),
            calculation_code_hash=CODE_HASH, portfolio_id=portfolio_id,
            portfolio_version=portfolio.version, portfolio_classification=portfolio.classification,
            portfolio_updated_at=portfolio.updated_at, source_manifest_id=manifest, as_of=cutoff,
            evaluation_date=context["evaluation_date"], market_regime=state_regime,
            capital=portfolio.capital, base_currency=portfolio.base_currency,
            positions=result_positions, exposure=exposure,
            portfolio_market_value=gross, unrealized_pnl=portfolio_pnl,
            heat_amount=heat_amount, heat_percent=money(heat_amount/portfolio.capital)
                if heat_amount is not None else None,
            heat_by_position=heat_by_position, heat_by_strategy=heat_strategy,
            heat_by_asset_class=heat_asset, unknown_risk_position_ids=unknown,
            correlation_window=60, correlations=correlations,
            correlation_cluster_flags=cluster_flags, btc_sensitivity_proxy=btc_proxy,
            portfolio_drawdown=None,
            coverage=sum(item.market_value is not None for item in result_positions)/len(result_positions)
                if result_positions else 1.0,
            price_freshness="stale" if any(item.freshness != "current" for item in result_positions)
                else "current", feature_freshness="stale" if any(item.freshness != "current"
                for item in result_positions) else "current",
            market_state_freshness=state_freshness,
            warnings=list(dict.fromkeys(warnings + ["PORTFOLIO_EQUITY_SERIES_UNAVAILABLE:DRAWDOWN_UNKNOWN"])))
        from .intelligence import IntelligenceService
        from .intelligence_contracts import ContextRequest
        supplementary = {}
        context_service = IntelligenceService(self.catalog)
        for position in result_positions:
            contextual = context_service.snapshot(ContextRequest(as_of=cutoff, market_manifest_id=manifest,
                instrument_id=position.instrument_id))
            supplementary[str(position.instrument_id)] = {'context_snapshot_id': str(contextual.snapshot_id),
                'context_manifest_id': str(contextual.context_manifest_id) if contextual.context_manifest_id else None,
                'event_risk': contextual.event_risk, 'derivatives': contextual.dimensions['derivatives'].model_dump(mode='json'),
                'warning': 'CONTEXT_WARNINGS_DO_NOT_CHANGE_NUMERICAL_RISK_OR_SIZING'}
        snapshot = snapshot.model_copy(update={'contextual_risk': supplementary})
        snapshot = snapshot.model_copy(update={"snapshot_id":snapshot_identity(snapshot)})
        if request.persist and overlay is None:
            self.store.save_risk(snapshot.model_dump(mode="json"))
        return snapshot

    def overlay(self, portfolio_id: UUID, request: OverlayRequest) -> dict:
        before = self.snapshot(portfolio_id, request.risk.model_copy(update={"persist":False}))
        after = self.snapshot(portfolio_id, RiskRequest(manifest_id=before.source_manifest_id,
            as_of=before.as_of, portfolio_version=before.portfolio_version),
            overlay=request.hypothetical_position)
        scenario_before = run_scenario(before, request.scenario) if request.scenario else None
        scenario_after = run_scenario(after, request.scenario) if request.scenario else None
        def delta(new, old):
            return money(new-old) if new is not None and old is not None else None
        return {"label":"HYPOTHETICAL_RESEARCH_OVERLAY", "before":before.model_dump(mode="json"),
            "after":after.model_dump(mode="json"),
            "delta_gross_exposure":delta(after.exposure.gross,before.exposure.gross),
            "delta_heat":delta(after.heat_amount,before.heat_amount),
            "delta_btc_sensitivity_proxy":delta(after.btc_sensitivity_proxy,before.btc_sensitivity_proxy),
            "before_scenario":scenario_before.model_dump(mode="json") if scenario_before else None,
            "after_scenario":scenario_after.model_dump(mode="json") if scenario_after else None}
