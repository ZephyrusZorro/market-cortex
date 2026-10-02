"""Point-in-time feature, alignment, breadth, state, and API acceptance cases."""

from __future__ import annotations

import hashlib
import math
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import numpy as np
import pytest
from fastapi.testclient import TestClient

from market_cortex.alignment import FxConversion, FxPoint, align, compare
from market_cortex.api import create_app
from market_cortex.breadth import calculate_breadth
from market_cortex.calendar import SessionCalendar
from market_cortex.config import Settings
from market_cortex.contracts import Bar, IdentifierMapping, Instrument, ObservationEnvelope, Venue
from market_cortex.features import FeatureEngine, FeatureRequest
from market_cortex.market_state import (MarketStateDimension, MarketStateEngine,
                                        MarketStateRequest, PILOT_SYMBOLS, classify_regime)
from market_cortex.storage import visible_bars


UTC = timezone.utc
VENUE = Venue(venue_id="BINANCE_SPOT", timezone="UTC", session_kind="24x7")
CALENDAR = SessionCalendar(VENUE, "BINANCE_SPOT:utc_daily", "v1")


def identity(symbol: str):
    instrument = Instrument(instrument_id=uuid4(), asset_class="crypto_spot", instrument_kind="spot_pair",
                            primary_venue_id=VENUE.venue_id, trading_currency="USDT", price_unit="quote_currency",
                            quantity_unit=symbol.removesuffix("USDT"), listing_status="active",
                            valid_from=datetime(2024, 1, 1, tzinfo=UTC))
    mapping = IdentifierMapping(mapping_id=uuid4(), instrument_id=instrument.instrument_id,
                                provider_id="binance", venue_id=VENUE.venue_id,
                                identifier_type="exchange_pair", identifier_value=symbol,
                                valid_from=instrument.valid_from,
                                available_at=datetime(2024, 1, 2, tzinfo=UTC))
    return instrument, mapping


def bar(instrument: Instrument, symbol: str, day: date, close: float, *,
        available_at: datetime | None = None, supersedes: UUID | None = None,
        volume: float | None = 1000, quality: str = "valid") -> Bar:
    start = datetime.combine(day, datetime.min.time(), UTC)
    end = start + timedelta(days=1)
    available = available_at or end + timedelta(hours=1)
    envelope = ObservationEnvelope(observation_id=uuid4(), instrument_id=instrument.instrument_id,
        venue_id=VENUE.venue_id, provider_id="binance", provider_record_id=f"{symbol}:{day}",
        event_at=end, available_at=available, availability_basis="observed_arrival",
        ingested_at=available, timestamp_precision="day", is_final=True,
        quality_state=quality, freshness_policy_id="binance:daily", validation_codes=[],
        source_ref="synthetic:phase2", source_batch_id=uuid4(),
        raw_content_hash=hashlib.sha256(f"{symbol}:{day}:{close}".encode()).hexdigest(),
        raw_retention_state="hash_only", normalizer_version="synthetic_v1",
        license_policy_id="hash_only", unit="quote_currency", currency="USDT",
        adjustment_basis="raw", supersedes_observation_id=supersedes)
    return Bar(envelope=envelope, interval="P1D", start_at=start, end_at=end,
               session_date=day, calendar_id=CALENDAR.calendar_id,
               open=Decimal(str(close)), high=Decimal(str(close * 1.01)),
               low=Decimal(str(close * .99)), close=Decimal(str(close)),
               volume=Decimal(str(volume)) if volume is not None else None,
               aggregation_method="provider_spot_public:session", quote_currency="USDT",
               volume_unit=instrument.quantity_unit)


class MemoryCatalog:
    def __init__(self):
        self.old_manifest, self.new_manifest = uuid4(), uuid4()
        self.instruments: list[Instrument] = []
        self.mappings: list[IdentifierMapping] = []
        self.old_bars: list[Bar] = []
        self.new_bars: list[Bar] = []

    def head(self): return self.new_manifest
    def load_identity(self): return self.instruments, self.mappings
    def load_calendar(self, *args): return CALENDAR

    def bars(self, *, instrument_id, start, end, as_of, manifest_id=None,
             adjustment_basis="raw", provider_id=None):
        pinned = manifest_id or self.head()
        if pinned not in (self.old_manifest, self.new_manifest):
            raise KeyError("manifest")
        records = self.old_bars if pinned == self.old_manifest else self.new_bars
        return pinned, visible_bars(records, instrument_id=instrument_id, start=start, end=end,
                                    as_of=as_of, adjustment_basis=adjustment_basis,
                                    provider_id=provider_id)


def fixture(prices: list[float], *, second: list[float] | None = None,
            missing_index: int | None = None) -> tuple[MemoryCatalog, list[Instrument], date]:
    catalog = MemoryCatalog()
    first = date(2025, 1, 1)
    for symbol, series in (("BTCUSDT", prices), ("ETHUSDT", second)):
        if series is None: continue
        instrument, mapping = identity(symbol)
        catalog.instruments.append(instrument)
        catalog.mappings.append(mapping)
        for index, close in enumerate(series):
            if symbol == "BTCUSDT" and index == missing_index: continue
            item = bar(instrument, symbol, first + timedelta(days=index), close)
            catalog.old_bars.append(item)
            catalog.new_bars.append(item)
    return catalog, catalog.instruments, first


def feature_request(instrument: Instrument, first: date, last: date, *,
                    feature: str = "sma", manifest: UUID | None = None,
                    as_of: datetime = datetime(2025, 2, 1, tzinfo=UTC),
                    parameters: dict | None = None):
    return FeatureRequest(instrument_id=instrument.instrument_id, feature=feature,
                          start_date=first, end_date=last, as_of=as_of,
                          manifest_id=manifest, provider_id="binance",
                          parameters=parameters or {"period": 3})


def test_manifest_asof_correction_and_future_bar_do_not_leak():
    catalog, instruments, first = fixture([10, 20, 30, 40, 50])
    original = catalog.old_bars[2]
    corrected = bar(instruments[0], "BTCUSDT", first + timedelta(days=2), 60,
                    available_at=datetime(2025, 1, 20, tzinfo=UTC),
                    supersedes=original.envelope.observation_id, quality="corrected")
    catalog.new_bars.append(corrected)
    catalog.new_bars.append(bar(instruments[0], "BTCUSDT", first + timedelta(days=5), 999))
    engine = FeatureEngine(catalog)
    last = first + timedelta(days=4)
    old = engine.calculate(feature_request(instruments[0], first, last, manifest=catalog.old_manifest))
    future_manifest_old_cutoff = engine.calculate(feature_request(
        instruments[0], first, last, manifest=catalog.new_manifest,
        as_of=datetime(2025, 1, 10, tzinfo=UTC)))
    future_manifest_new_cutoff = engine.calculate(feature_request(
        instruments[0], first, last, manifest=catalog.new_manifest,
        as_of=datetime(2025, 1, 21, tzinfo=UTC)))
    pinned_old_after_correction = engine.calculate(feature_request(
        instruments[0], first, last, manifest=catalog.old_manifest,
        as_of=datetime(2025, 1, 21, tzinfo=UTC)))
    assert old.points[2].value == 20
    assert future_manifest_old_cutoff.points[2].value == 20
    assert future_manifest_new_cutoff.points[2].value == 30
    assert pinned_old_after_correction.points[2].value == 20
    assert old.points[-1].value == 40
    assert engine.calculate(feature_request(instruments[0], first, last,
                                           manifest=catalog.old_manifest)).feature_id == old.feature_id
    assert old.feature_id != future_manifest_new_cutoff.feature_id
    assert len(old.source_observation_ids) == 5


def test_missing_session_quality_volume_and_warmup_are_exposed():
    catalog, instruments, first = fixture([10, 20, 30, 40, 50], missing_index=1)
    engine = FeatureEngine(catalog)
    result = engine.calculate(feature_request(instruments[0], first, first + timedelta(days=4),
                                              manifest=catalog.old_manifest))
    assert result.expected_sessions == 5 and result.observed_sessions == 4
    assert result.missing_sessions == [first + timedelta(days=1)]
    assert result.points[1].value is None and result.points[1].reason == "NO_VISIBLE_VALID_BAR"
    assert result.points[3].value is None and result.points[3].reason == "INSUFFICIENT_HISTORY_OR_GAP"
    assert result.points[4].value == 40
    missing_volume = catalog.old_bars[0].model_copy(update={"volume": None})
    catalog.old_bars[0] = missing_volume
    catalog.new_bars[0] = missing_volume
    relative = engine.calculate(feature_request(instruments[0], first, first + timedelta(days=4),
                                                feature="relative_volume", manifest=catalog.old_manifest,
                                                parameters={"period": 2}))
    assert relative.points[0].reason == "INPUT_UNAVAILABLE"


def test_prelisting_sessions_are_ineligible_and_never_used_for_warmup():
    catalog, instruments, first = fixture([10, 20, 30, 40, 50])
    later = instruments[0].model_copy(update={"valid_from": datetime(2025, 1, 3, tzinfo=UTC)})
    catalog.instruments[0] = later
    result = FeatureEngine(catalog).calculate(feature_request(
        later, first, first + timedelta(days=4), manifest=catalog.old_manifest))
    assert result.expected_sessions == 5 and result.eligible_sessions == 3
    assert result.ineligible_sessions == [first, first + timedelta(days=1)]
    assert result.missing_sessions == []
    assert [point.reason for point in result.points[:2]] == ["INSTRUMENT_NOT_VALID"] * 2
    assert result.points[-1].value == 40


def test_alignment_relative_strength_correlation_and_currency_guard():
    target = [100, 110, 100, 120, 110, 132, 121]
    reference = [50, 55, 50, 60, 55, 66, 60.5]
    catalog, instruments, first = fixture(target, second=reference)
    engine = FeatureEngine(catalog)
    cutoff = datetime(2025, 2, 1, tzinfo=UTC)
    loaded = [engine.load(instrument_id=item.instrument_id, start_date=first,
                          end_date=first + timedelta(days=6), as_of=cutoff,
                          manifest_id=catalog.old_manifest, provider_id="binance") for item in instruments]
    relative = compare(*loaded, kind="relative_strength", window=2)
    correlation = compare(*loaded, kind="correlation", window=3)
    assert relative.points[-1].value == pytest.approx(0)
    assert correlation.points[-1].value == pytest.approx(1)
    assert correlation.points[-1].observation_count == 3
    assert correlation.points[-1].coverage == 1
    assert -1 <= correlation.points[-1].value <= 1
    assert correlation.points[-1].stability is not None
    assert all(point.target_observation_id and point.reference_observation_id
               for point in correlation.points[-3:])
    other_instrument = loaded[1].instrument.model_copy(update={"trading_currency": "USD"})
    with pytest.raises(ValueError, match="FX_CONVERSION_REQUIRED"):
        compare(loaded[0], replace(loaded[1], instrument=other_instrument), kind="correlation", window=3)
    different_calendar = SessionCalendar(Venue(venue_id="XNYS", timezone="America/New_York", session_kind="regular"),
                                         "nyse", "v1")
    with pytest.raises(ValueError, match="CALENDAR_ALIGNMENT_REQUIRED"):
        compare(loaded[0], replace(loaded[1], calendar=different_calendar), kind="correlation", window=3)


def test_explicit_utc_cutoff_alignment_rejects_future_and_stale_reference():
    catalog, instruments, first = fixture([100, 110, 120], second=[50, 55, 60])
    engine = FeatureEngine(catalog)
    as_of = datetime(2025, 1, 10, tzinfo=UTC)
    target, reference = [engine.load(instrument_id=item.instrument_id, start_date=first,
        end_date=first + timedelta(days=2), as_of=as_of, manifest_id=catalog.old_manifest,
        provider_id="binance") for item in instruments]
    nyse = SessionCalendar(Venue(venue_id="XNYS", timezone="America/New_York", session_kind="regular"),
                           "nyse", "v1")
    adjusted = []
    for item in reference.bars:
        earlier_end = item.start_at + timedelta(hours=21)
        env = item.envelope.model_copy(update={"available_at": earlier_end + timedelta(minutes=30)})
        adjusted.append(item.model_copy(update={"end_at": earlier_end, "envelope": env}))
    reference = replace(reference, calendar=nyse, bars=tuple(adjusted))
    paired = align(target, reference, policy="completed_at_utc_cutoff",
                   cutoff_lag=timedelta(hours=2), max_reference_age=timedelta(hours=6))
    assert paired.reference_ids[0] == adjusted[0].envelope.observation_id
    too_late = adjusted[0].envelope.model_copy(update={"available_at": target.bars[0].end_at + timedelta(hours=3)})
    delayed = replace(reference, bars=(adjusted[0].model_copy(update={"envelope": too_late}), *adjusted[1:]))
    assert align(target, delayed, policy="completed_at_utc_cutoff",
                 cutoff_lag=timedelta(hours=2), max_reference_age=timedelta(hours=6)).reference_ids[0] is None
    assert align(target, reference, policy="completed_at_utc_cutoff",
                 cutoff_lag=timedelta(hours=2), max_reference_age=timedelta(hours=4)).reference_ids[0] is None
    with pytest.raises(ValueError, match="CALENDAR_ALIGNMENT_REQUIRED"):
        align(target, reference, policy="same_session")

    other_currency = target.instrument.model_copy(update={"trading_currency": "USD"})
    foreign = replace(target, instrument=other_currency)
    rates = {day: FxPoint(2.0, as_of, "synthetic:fx") for day in foreign.dates}
    converted = align(foreign, replace(reference, calendar=target.calendar),
                      fx=FxConversion("USD", "USDT", uuid4(), rates))
    assert converted.target[0] == 200 and converted.fx_manifest_id is not None
    future_rates = {day: FxPoint(2.0, as_of + timedelta(days=1), "synthetic:fx") for day in foreign.dates}
    unavailable = align(foreign, replace(reference, calendar=target.calendar),
                        fx=FxConversion("USD", "USDT", uuid4(), future_rates))
    assert np.isnan(unavailable.target).all()


def test_provider_conflict_duplicate_date_and_quarantine_cannot_be_hidden():
    catalog, instruments, first = fixture([100, 110, 120])
    original = catalog.old_bars[0]
    alt = original.model_copy(update={"envelope": original.envelope.model_copy(update={
        "observation_id": uuid4(), "provider_id": "other_read_only_source"})})
    catalog.old_bars.append(alt)
    with pytest.raises(ValueError, match="PROVIDER_SELECTION_REQUIRED"):
        FeatureEngine(catalog).load(instrument_id=instruments[0].instrument_id,
            start_date=first, end_date=first + timedelta(days=2),
            as_of=datetime(2025, 1, 10, tzinfo=UTC), manifest_id=catalog.old_manifest)
    catalog.old_bars.remove(alt)
    intraday = original.model_copy(update={"interval": "PT1H",
        "end_at": original.start_at + timedelta(hours=1),
        "envelope": original.envelope.model_copy(update={"observation_id": uuid4()})})
    catalog.old_bars.append(intraday)
    daily = FeatureEngine(catalog).load(instrument_id=instruments[0].instrument_id,
        start_date=first, end_date=first + timedelta(days=2),
        as_of=datetime(2025, 1, 10, tzinfo=UTC), manifest_id=catalog.old_manifest,
        provider_id="binance")
    assert daily.bars[0].interval == "P1D"
    catalog.old_bars.remove(intraday)
    duplicate = original.model_copy(update={"start_at": original.start_at + timedelta(minutes=1),
                                     "envelope": original.envelope.model_copy(update={"observation_id": uuid4()})})
    catalog.old_bars.append(duplicate)
    with pytest.raises(ValueError, match="CONFLICTING_VISIBLE_BAR"):
        FeatureEngine(catalog).load(instrument_id=instruments[0].instrument_id,
            start_date=first, end_date=first + timedelta(days=2),
            as_of=datetime(2025, 1, 10, tzinfo=UTC), manifest_id=catalog.old_manifest,
            provider_id="binance")
    catalog.old_bars.remove(duplicate)
    catalog.old_bars.remove(catalog.old_bars[1])
    quarantined = bar(instruments[0], "BTCUSDT", first + timedelta(days=1), 110,
                      quality="quarantined")
    catalog.old_bars.append(quarantined)
    result = FeatureEngine(catalog).calculate(feature_request(
        instruments[0], first, first + timedelta(days=2), manifest=catalog.old_manifest))
    assert result.missing_sessions == [first + timedelta(days=1)]
    assert result.points[1].reason == "NO_VISIBLE_VALID_BAR"


def test_breadth_and_state_are_scoped_versioned_and_reproducible():
    catalog = MemoryCatalog()
    first = date(2025, 1, 1)
    count = 260
    for offset, symbol in enumerate(PILOT_SYMBOLS):
        instrument, mapping = identity(symbol)
        catalog.instruments.append(instrument)
        catalog.mappings.append(mapping)
        for index in range(count):
            price = 100 + offset * 20 + index * (1 + offset * .1)
            item = bar(instrument, symbol, first + timedelta(days=index), price,
                       volume=1000 + 10 * index + offset)
            catalog.old_bars.append(item)
            catalog.new_bars.append(item)
    evaluation = first + timedelta(days=count - 1)
    as_of = datetime.combine(evaluation + timedelta(days=1), datetime.min.time(), UTC) + timedelta(hours=1)
    request = MarketStateRequest(history_start=first, evaluation_date=evaluation, as_of=as_of,
                                 manifest_id=catalog.old_manifest)
    engine = MarketStateEngine(catalog)
    one = engine.compute(request)
    two = engine.compute(request)
    assert one.snapshot_id == two.snapshot_id
    assert one.source_manifest_id == catalog.old_manifest
    assert one.breadth.universe_id == "binance_pilot_5"
    assert one.breadth.total_members == 5 and one.breadth.observed_members == 5
    assert one.breadth.above_sma.eligible == 5
    assert one.breadth.above_sma.percentage == 100
    assert one.regime.rule_version == "regime_rules_v1"
    assert {item.name for item in one.dimensions} == {
        "trend", "momentum", "volatility", "volume_proxy", "market_participation",
        "breadth", "relative_strength", "correlation_state", "risk_appetite_proxy",
        "data_freshness", "uncertainty"}
    assert all(item.source_manifest_id == one.source_manifest_id for item in one.dimensions)
    assert all(item.evidence_refs or item.unknown_reason for item in one.dimensions if item.name != "uncertainty")
    assert one.dimensions[-2].category == "current"
    assert one.elapsed_ms > 0

    # An earlier as-of cutoff has no locally available backfilled observations.
    early = engine.compute(request.model_copy(update={"as_of": datetime(2024, 12, 31, tzinfo=UTC)}))
    assert early.regime.category == "insufficient_data"
    assert early.breadth.observed_members == 0
    assert early.snapshot_id != one.snapshot_id


def test_read_only_phase2_api_reports_lineage_and_insufficient_evidence():
    catalog, instruments, first = fixture([100, 110, 120, 130, 140])
    settings = Settings(database_url=None, data_root=Path.cwd(), owner_timezone="Asia/Kolkata",
                        base_currency="INR", cloud_model_allowed=False, owner_configured=False)
    client = TestClient(create_app(settings, catalog))
    assert len(client.get("/api/v1/features").json()["items"]) >= 35
    params = {"name": "sma", "instrument_id": str(instruments[0].instrument_id),
              "from": str(first), "to": str(first + timedelta(days=4)), "period": 3,
              "provider_id": "binance", "manifest_id": str(catalog.old_manifest),
              "as_of": "2025-02-01T00:00:00Z"}
    series = client.get("/api/v1/features/series", params=params)
    assert series.status_code == 200
    assert series.json()["points"][-1]["value"] == 130
    assert series.json()["source_manifest_id"] == str(catalog.old_manifest)
    scalar = client.get("/api/v1/features/compute", params=params)
    assert scalar.status_code == 200 and scalar.json()["latest"]["value"] == 130
    assert "points" not in scalar.json()
    bad = client.get("/api/v1/features/series", params={**params, "period": 0})
    assert bad.status_code == 422
    state = client.get("/api/v1/market-state", params={"history_from": str(first),
        "evaluation_date": str(first + timedelta(days=4)),
        "as_of": "2025-01-06T01:00:00Z", "manifest_id": str(catalog.old_manifest)})
    assert state.status_code == 200
    assert state.json()["regime"]["category"] == "insufficient_data"
    assert state.json()["missing_members"] == list(PILOT_SYMBOLS[1:])
    assert client.post("/api/v1/market-state").status_code == 405
    assert client.post("/api/v1/orders").status_code == 404


def test_transparent_regime_rules_and_stale_refusal():
    manifest = uuid4()

    def dimensions(trend, momentum, volatility, participation="complete", freshness="current"):
        return [MarketStateDimension(name=name, category=category, metrics={},
                evidence_refs=[f"feature:{name}"], scope="synthetic",
                source_manifest_id=manifest, eligible_members=1, total_members=1,
                freshness=freshness)
                for name, category in (("trend", trend), ("momentum", momentum),
                                       ("volatility", volatility),
                                       ("market_participation", participation),
                                       ("data_freshness", freshness))]

    up = classify_regime(dimensions("up", "positive", "elevated"))
    assert up.category == "uptrend_volatile" and "R1_UP_TREND" in up.rules_fired
    down = classify_regime(dimensions("down", "negative", "subdued"))
    assert down.category == "downtrend_other" and "R5_DOWN_TREND" in down.rules_fired
    assert classify_regime(dimensions("up", "negative", "middle")).category == "mixed"
    assert classify_regime(dimensions("up", "positive", "middle", participation="partial")).category == "insufficient_data"
    assert classify_regime(dimensions("up", "positive", "middle", freshness="stale")).category == "insufficient_data"
