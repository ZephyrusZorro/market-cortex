"""Golden and property-style risk checks independent of the live pilot direction."""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from market_cortex.cortex_gateway import may_send_context
from market_cortex.config import Settings
from market_cortex.risk import calculate_position, research_sizing, run_scenario
from market_cortex.risk_contracts import PositionInput, ScenarioDefinition, SizingRequest


NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)


def position(**updates):
    base = dict(instrument_id=uuid4(), quantity=Decimal("10"), average_cost=Decimal("100"),
        native_currency="USDT", opened_at=NOW, invalidation_price=Decimal("95"))
    base.update(updates)
    return PositionInput(**base)


def test_golden_long_r_heat_and_pnl():
    p = position(target_price=Decimal("120"))
    result = calculate_position(p, "BTCUSDT", Decimal("110"), "2026-10-02", uuid4(),
        {"annualized_volatility":(.4,"vol1"),"atr":(4.0,"atr1")}, "current", 1)
    assert result.market_value == Decimal("1100")
    assert result.cost_basis == Decimal("1000")
    assert result.unrealized_pnl == Decimal("100")
    assert result.one_r == Decimal("50")
    assert result.current_r == Decimal("2")
    assert result.target_r == Decimal("4")
    assert result.risk_to_invalidation == Decimal("150")
    assert result.distance_to_invalidation == Decimal("15")


def test_missing_invalidation_is_unknown_not_zero_and_stale_is_visible():
    result = calculate_position(position(invalidation_price=None), "ETHUSDT", Decimal("100"),
        "2026-10-01", uuid4(), {}, "stale", .7)
    assert result.risk_to_invalidation is None and result.one_r is None
    assert result.reward_to_risk is None
    assert any("INVALIDATION_MISSING" in item for item in result.warnings)
    assert "PRICE_NOT_CURRENT:stale" in result.warnings


def test_breached_invalidation_does_not_become_zero_risk():
    result = calculate_position(position(), "BTCUSDT", Decimal("90"), "2026-10-01",
                                uuid4(), {}, "current", 1)
    assert result.risk_to_invalidation is None
    assert "INVALIDATION_BREACHED_RISK_NOT_ZERO" in result.warnings


def test_sizing_golden_fixed_amount_fractional_and_no_target():
    fixed = research_sizing(SizingRequest(capital=Decimal("10000"), entry_price=Decimal("100"),
        invalidation_price=Decimal("95"), risk_amount=Decimal("50"), target_price=Decimal("110")))
    fractional = research_sizing(SizingRequest(capital=Decimal("10000"), entry_price=Decimal("100"),
        invalidation_price=Decimal("95"), risk_percent=Decimal("0.005")))
    assert fixed["hypothetical_quantity"] == Decimal("10")
    assert fixed["hypothetical_notional"] == Decimal("1000")
    assert fixed["reward_to_risk"] == Decimal("2")
    assert fractional["hypothetical_quantity"] == Decimal("10")
    assert fractional["reward_to_risk"] is None


def test_sizing_rejects_target_at_or_below_long_entry():
    for target in (Decimal("95"), Decimal("100")):
        with pytest.raises(ValueError, match="LONG_TARGET_MUST_BE_ABOVE_ENTRY"):
            SizingRequest(capital=Decimal("10000"), entry_price=Decimal("100"),
                invalidation_price=Decimal("90"), risk_amount=Decimal("50"), target_price=target)


@pytest.mark.parametrize("invalidation", ["100", "105", "0", "-1"])
def test_invalid_long_invalidation_rejected(invalidation):
    with pytest.raises(ValueError):
        position(invalidation_price=Decimal(invalidation))


def test_scenario_golden_and_reconciliation():
    p1 = calculate_position(position(quantity=Decimal("1")), "BTCUSDT", Decimal("100"),
                            "2026-10-01", uuid4(), {}, "current", 1)
    p2 = calculate_position(position(quantity=Decimal("2")), "ETHUSDT", Decimal("50"),
                            "2026-10-01", uuid4(), {}, "current", 1)
    snapshot = SimpleNamespace(snapshot_id=uuid4(), positions=[p1,p2],
                               base_currency="USDT", capital=Decimal("1000"))
    scenario = ScenarioDefinition(name="Crypto -10%", shocks={"BTCUSDT":Decimal("-.1"),
        "ETHUSDT":Decimal("-.1")})
    result = run_scenario(snapshot, scenario)
    assert result.portfolio_pnl == Decimal("-20")
    assert result.portfolio_change_percent == Decimal("-.02")
    assert sum(result.position_pnl.values()) == result.portfolio_pnl
    assert run_scenario(snapshot, scenario).model_dump() == result.model_dump()


def test_private_holdings_never_sent_to_cloud_gateway():
    gateway = SimpleNamespace(locality="cloud")
    settings = Settings(None, __import__("pathlib").Path("."), "Asia/Kolkata", "INR", True, True)
    assert may_send_context(settings, gateway, contains_private_data=True) is False
