"""Hermetic synthetic cases. No provider responses are described as verified market data."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
from fastapi.testclient import TestClient

from market_cortex.api import create_app
from market_cortex.analytics import manifest_coverage
from market_cortex.backup import _safe_member, decrypt_file, encrypt_file, restore
from market_cortex.bootstrap import discover_crypto
from market_cortex.calendar import CalendarMissing, SessionCalendar
from market_cortex.config import Settings
from market_cortex.contracts import (Bar, CalendarSession, IdentifierMapping, Instrument,
                                     ObservationEnvelope, Venue, validate_registry)
from market_cortex.identity import AmbiguousIdentity, IdentityRegistry, UnknownIdentity
from market_cortex.providers import (AlpacaDaily, BinanceDaily, NotConfigured, Page,
                                     ProviderFailure, ReadTransport, UpstoxDaily)
from market_cortex.quality import disagreements, freshness, missing_sessions, validate_bar
from market_cortex.storage import ArtifactStore, filter_known_identity, logical_key, visible_bars

ROOT = Path(__file__).resolve().parents[1]
Z = timezone.utc


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def identity(venue_id: str = "XCRY", provider: str = "binance", native: str = "BTCUSDT",
             identifier_type: str = "exchange_pair"):
    instrument = Instrument(instrument_id=uuid4(), asset_class="crypto_spot" if venue_id == "XCRY" else "equity",
                            instrument_kind="spot_pair" if venue_id == "XCRY" else "listing",
                            primary_venue_id=venue_id, trading_currency="USDT" if venue_id == "XCRY" else "USD",
                            price_unit="quote_currency", quantity_unit="base_asset" if venue_id == "XCRY" else "shares",
                            listing_status="active", valid_from=instant("2020-01-01T00:00:00Z"))
    mapping = IdentifierMapping(mapping_id=uuid4(), instrument_id=instrument.instrument_id,
                                provider_id=provider, venue_id=venue_id, identifier_type=identifier_type,
                                identifier_value=native, valid_from=instant("2020-01-01T00:00:00Z"),
                                available_at=instant("2020-01-02T00:00:00Z"))
    return instrument, mapping


def calendar(venue_id: str = "XCRY", day: date = date(2025, 1, 2)) -> SessionCalendar:
    if venue_id == "XCRY":
        return SessionCalendar(Venue(venue_id=venue_id, timezone="UTC", session_kind="24x7"), "crypto_daily", "v1")
    venue = Venue(venue_id=venue_id, timezone="America/New_York", session_kind="regular")
    sessions = [CalendarSession(calendar_id="nyse", venue_id=venue_id, session_date=day,
                                open_at=instant("2025-01-02T14:30:00Z"),
                                close_at=instant("2025-01-02T21:00:00Z"), status="open", version="v1")]
    return SessionCalendar(venue, "nyse", "v1", sessions)


def bar(instrument: Instrument, mapping: IdentifierMapping, cal: SessionCalendar,
        day: date = date(2025, 1, 2), close: str = "100", available: str | None = "2025-01-03T00:00:00Z",
        revision: int = 1, adjustment: str = "raw", provider: str | None = None,
        adjustment_known: str | None = None) -> Bar:
    session = cal.session(day)
    fetched = instant("2026-01-01T00:00:00Z")
    envelope = ObservationEnvelope(
        observation_id=uuid4(), instrument_id=instrument.instrument_id, venue_id=mapping.venue_id,
        provider_id=provider or mapping.provider_id, provider_record_id=f"{mapping.identifier_value}:{day}",
        event_at=session.close_at, available_at=instant(available) if available else None,
        availability_basis="documented_publication" if available else "unknown", ingested_at=fetched,
        timestamp_precision="day", is_final=True, quality_state="valid", freshness_policy_id="test:daily",
        validation_codes=[], source_ref="synthetic:case", source_batch_id=uuid4(),
        raw_content_hash="a" * 64, raw_retention_state="hash_only", normalizer_version="test_v1",
        license_policy_id="hash_only", unit="price", adjustment_basis=adjustment,
        adjustment_vintage_id="synthetic-action-v1" if adjustment not in ("raw", "provider_unspecified") else None,
        adjustment_known_at=instant(adjustment_known or available) if available and adjustment not in ("raw", "provider_unspecified") else None)
    return Bar(envelope=envelope, interval="P1D", start_at=session.open_at, end_at=session.close_at,
               session_date=day, calendar_id=cal.calendar_id, open="100", high="110", low="90", close=close,
               volume="20", aggregation_method="test", quote_currency=instrument.trading_currency,
               volume_unit=instrument.quantity_unit)


class FoundationTests(unittest.TestCase):
    def test_registry_contracts_and_naive_timestamp_rejected(self):
        i, m = identity()
        b = bar(i, m, calendar())
        for obj in (i, m, b, b.envelope):
            validate_registry(obj, ROOT / "packages" / "contracts" / "registry.schema.json")
        with self.assertRaises(ValueError):
            ObservationEnvelope.model_validate({**b.envelope.model_dump(), "event_at": datetime(2025, 1, 3)})

    def test_venue_identity_ticker_changes_and_knowledge_time(self):
        a, first = identity("XNYS", "alpaca", "OLD", "ticker")
        b, second = identity("XNAS", "alpaca", "OLD", "ticker")
        at = instant("2025-01-02T12:00:00Z")
        first = first.model_copy(update={"valid_to": at})
        renamed = first.model_copy(update={"mapping_id": uuid4(), "identifier_value": "NEW",
                                           "valid_from": at, "valid_to": None})
        registry = IdentityRegistry([a, b], [first, renamed, second])
        with self.assertRaises(AmbiguousIdentity):
            registry.resolve(provider_id="alpaca", identifier_type="ticker", identifier_value="OLD", at=at - timedelta(days=1))
        self.assertEqual(registry.resolve(provider_id="alpaca", identifier_type="ticker", identifier_value="NEW",
                                          venue_id="XNYS", at=at).instrument_id, a.instrument_id)
        with self.assertRaises(UnknownIdentity):
            registry.resolve(provider_id="alpaca", identifier_type="ticker", identifier_value="OLD",
                             venue_id="XNYS", at=at)
        with self.assertRaises(UnknownIdentity):
            registry.resolve(provider_id="alpaca", identifier_type="ticker", identifier_value="NEW",
                             venue_id="XNYS", at=at, known_at=instant("2019-01-01T00:00:00Z"))
        c, _ = identity("XNYS", "alpaca", "OTHER", "ticker")
        collision = renamed.model_copy(update={"mapping_id": uuid4(), "instrument_id": c.instrument_id})
        with self.assertRaises(AmbiguousIdentity):
            IdentityRegistry([a, c], [renamed, collision]).mapping_for(a.instrument_id, "alpaca", "ticker", at)

    def test_reused_provider_token_never_merges_expired_contracts(self):
        first, first_mapping = identity("XNFO", "upstox", "REUSED_TOKEN", "provider_token")
        second, second_mapping = identity("XNFO", "upstox", "REUSED_TOKEN", "provider_token")
        expiry = instant("2025-01-15T00:00:00Z")
        first = first.model_copy(update={"asset_class": "future", "instrument_kind": "future_contract",
                                         "valid_to": expiry, "listing_status": "expired"})
        second = second.model_copy(update={"asset_class": "future", "instrument_kind": "future_contract",
                                           "valid_from": expiry})
        first_mapping = first_mapping.model_copy(update={"valid_to": expiry})
        second_mapping = second_mapping.model_copy(update={"valid_from": expiry})
        registry = IdentityRegistry([first, second], [first_mapping, second_mapping])
        old = registry.resolve(provider_id="upstox", identifier_type="provider_token",
                               identifier_value="REUSED_TOKEN", venue_id="XNFO",
                               at=instant("2025-01-14T00:00:00Z"))
        new = registry.resolve(provider_id="upstox", identifier_type="provider_token",
                               identifier_value="REUSED_TOKEN", venue_id="XNFO", at=expiry)
        self.assertEqual(old.instrument_id, first.instrument_id)
        self.assertEqual(new.instrument_id, second.instrument_id)
        self.assertNotEqual(old.instrument_id, new.instrument_id)

    def test_shared_isin_keeps_venue_listings_distinct(self):
        nse, nse_mapping = identity("XNSE", "reference", "INE000000001", "isin")
        bse, bse_mapping = identity("XBOM", "reference", "INE000000001", "isin")
        nse = nse.model_copy(update={"issuer_id": "issuer:synthetic"})
        bse = bse.model_copy(update={"issuer_id": "issuer:synthetic"})
        registry = IdentityRegistry([nse, bse], [nse_mapping, bse_mapping])
        at = instant("2025-01-02T00:00:00Z")
        with self.assertRaises(AmbiguousIdentity):
            registry.resolve(provider_id="reference", identifier_type="isin",
                             identifier_value="INE000000001", at=at)
        self.assertEqual(registry.resolve(provider_id="reference", identifier_type="isin",
            identifier_value="INE000000001", venue_id="XNSE", at=at).instrument_id, nse.instrument_id)
        self.assertNotEqual(nse.instrument_id, bse.instrument_id)

    def test_dst_holiday_early_close_and_missing_are_explicit(self):
        from zoneinfo import ZoneInfo
        zone = ZoneInfo("America/New_York")
        self.assertEqual(datetime(2026, 3, 9, 9, 30, tzinfo=zone).astimezone(Z).hour, 13)
        venue = Venue(venue_id="XNYS", timezone="America/New_York", session_kind="regular")
        sessions = [CalendarSession(calendar_id="nyse", venue_id="XNYS", session_date=date(2026, 7, 3),
                                    open_at=instant("2026-07-03T00:00:00Z"), close_at=instant("2026-07-03T00:00:00Z"),
                                    status="holiday", version="v1"),
                    CalendarSession(calendar_id="nyse", venue_id="XNYS", session_date=date(2026, 7, 4),
                                    open_at=instant("2026-07-04T13:30:00Z"), close_at=instant("2026-07-04T17:00:00Z"),
                                    status="early_close", version="v1")]
        cal = SessionCalendar(venue, "nyse", "v1", sessions)
        self.assertEqual(missing_sessions(cal, date(2026, 7, 3), date(2026, 7, 4), set()), (date(2026, 7, 4),))
        with self.assertRaises(CalendarMissing):
            cal.session(date(2026, 7, 5))

    def test_quarantine_quality_conflict_and_point_in_time_correction(self):
        i, m = identity()
        cal = calendar()
        old = bar(i, m, cal)
        bad = old.model_copy(update={"high": Decimal("99")})
        self.assertIn("OHLC_RANGE", validate_bar(bad, cal))
        corrected = bar(i, m, cal, close="101", available="2025-01-04T12:00:00Z", revision=2)
        other = bar(i, m, cal, close="99.5", provider="other")
        self.assertEqual(len(disagreements([old, other])), 1)
        start, end = instant("2025-01-02T00:00:00Z"), instant("2025-01-03T00:00:00Z")
        before = visible_bars([old, corrected, bad], instrument_id=i.instrument_id, start=start, end=end,
                              as_of=instant("2025-01-03T12:00:00Z"), adjustment_basis="raw")
        self.assertEqual([b.close for b in before], [Decimal("100")])
        after = visible_bars([old, corrected], instrument_id=i.instrument_id, start=start, end=end,
                             as_of=instant("2025-01-05T00:00:00Z"), adjustment_basis="raw")
        self.assertEqual([b.close for b in after], [Decimal("101")])
        unknown = bar(i, m, cal, available=None)
        self.assertEqual(visible_bars([unknown], instrument_id=i.instrument_id, start=start, end=end,
                                      as_of=instant("2026-01-02T00:00:00Z"), adjustment_basis="raw"), [])
        late_mapping = m.model_copy(update={"available_at": instant("2025-01-04T00:00:00Z")})
        self.assertEqual(filter_known_identity([old], [i], [late_mapping], instant("2025-01-03T12:00:00Z")), [])
        self.assertEqual(len(filter_known_identity([old], [i], [late_mapping], instant("2025-01-05T00:00:00Z"))), 1)

    def test_equal_timestamp_correction_is_independent_of_artifact_order(self):
        instrument, mapping = identity()
        cal = calendar()
        original = bar(instrument, mapping, cal)
        amended_envelope = original.envelope.model_copy(update={
            "observation_id": uuid4(), "supersedes_observation_id": original.envelope.observation_id,
            "quality_state": "corrected"})
        amended = original.model_copy(update={"envelope": amended_envelope, "close": Decimal("101")})
        for physical_order in ([original, amended], [amended, original]):
            with self.subTest(first=physical_order[0].close):
                visible = visible_bars(physical_order, instrument_id=instrument.instrument_id,
                                       start=original.start_at, end=original.end_at + timedelta(days=1),
                                       as_of=instant("2025-01-05T00:00:00Z"), adjustment_basis="raw")
                self.assertEqual([item.close for item in visible], [Decimal("101")])

    def test_adjustment_vintage_stays_separate_and_obeys_knowledge_time(self):
        instrument, mapping = identity()
        cal = calendar()
        raw = bar(instrument, mapping, cal)
        adjusted = bar(instrument, mapping, cal, close="50", adjustment="split",
                       available="2025-01-05T00:00:00Z", adjustment_known="2025-01-04T00:00:00Z")
        adjusted = adjusted.model_copy(update={"open": Decimal("50"), "high": Decimal("55"),
                                               "low": Decimal("45")})
        self.assertEqual(validate_bar(adjusted, cal), ())
        validate_registry(adjusted.envelope, ROOT / "packages" / "contracts" / "registry.schema.json")
        query = dict(instrument_id=instrument.instrument_id, start=raw.start_at,
                     end=raw.end_at + timedelta(days=1))
        self.assertEqual([item.close for item in visible_bars([raw, adjusted], **query,
            as_of=instant("2025-01-03T12:00:00Z"), adjustment_basis="raw")], [Decimal("100")])
        self.assertEqual(visible_bars([raw, adjusted], **query,
            as_of=instant("2025-01-04T12:00:00Z"), adjustment_basis="split"), [])
        result = visible_bars([raw, adjusted], **query,
                              as_of=instant("2025-01-06T00:00:00Z"), adjustment_basis="split")
        self.assertEqual([item.close for item in result], [Decimal("50")])
        self.assertEqual(result[0].envelope.adjustment_vintage_id, "synthetic-action-v1")
        with self.assertRaises(ValueError):
            ObservationEnvelope.model_validate({**adjusted.envelope.model_dump(), "adjustment_vintage_id": None})

    def test_daily_freshness_distinguishes_due_bars_closures_and_outages(self):
        instrument, mapping = identity()
        crypto = calendar()
        latest = bar(instrument, mapping, crypto)
        self.assertEqual(freshness(latest=latest, as_of=instant("2025-01-03T02:00:00Z"), calendar=crypto), "current")
        self.assertEqual(freshness(latest=latest, as_of=instant("2025-01-04T05:00:00Z"), calendar=crypto), "stale")
        self.assertEqual(freshness(latest=latest, as_of=instant("2025-01-04T05:00:00Z"),
                                   calendar=crypto, provider_error=True), "provider_outage")
        unknown = bar(instrument, mapping, crypto, available=None)
        self.assertEqual(freshness(latest=unknown, as_of=instant("2025-01-04T05:00:00Z"),
                                   calendar=crypto), "data_unavailable")

        venue = Venue(venue_id="XNYS", timezone="America/New_York", session_kind="regular")
        sessions = [CalendarSession(calendar_id="nyse", venue_id="XNYS", session_date=day,
                                    open_at=instant(open_at), close_at=instant(close_at),
                                    status=status, version="v1")
                    for day, open_at, close_at, status in (
                        (date(2025, 1, 2), "2025-01-02T14:30:00Z", "2025-01-02T21:00:00Z", "open"),
                        (date(2025, 1, 3), "2025-01-03T14:30:00Z", "2025-01-03T21:00:00Z", "open"),
                        (date(2025, 1, 4), "2025-01-04T00:00:00Z", "2025-01-04T00:00:00Z", "holiday"))]
        nyse = SessionCalendar(venue, "nyse", "v1", sessions)
        equity, equity_mapping = identity("XNYS", "alpaca", "AAPL", "ticker")
        thursday = bar(equity, equity_mapping, nyse)
        friday = bar(equity, equity_mapping, nyse, day=date(2025, 1, 3), available="2025-01-04T00:00:00Z")
        cases = (
            (thursday, "2025-01-03T13:00:00Z", "market_closed"),
            (thursday, "2025-01-03T16:00:00Z", "session_in_progress"),
            (thursday, "2025-01-03T23:00:00Z", "awaiting_publication"),
            (thursday, "2025-01-04T02:00:00Z", "stale"),
            (thursday, "2025-01-04T16:00:00Z", "stale"),
            (friday, "2025-01-04T16:00:00Z", "market_closed"),
        )
        for observed, at, expected in cases:
            with self.subTest(at=at, expected=expected):
                self.assertEqual(freshness(latest=observed, as_of=instant(at), calendar=nyse), expected)
        self.assertEqual(freshness(latest=thursday, as_of=instant("2025-01-05T16:00:00Z"),
                                   calendar=nyse), "calendar_unknown")

    def test_content_addressed_parquet_tamper_detection_and_adjustment_isolation(self):
        i, m = identity()
        raw = bar(i, m, calendar())
        split = bar(i, m, calendar(), close="50", adjustment="split")
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory))
            artifact = store.write_bars([raw, split])
            self.assertEqual([b.close for b in store.read_bars(artifact)], [Decimal("100"), Decimal("50")])
            class FakeCatalog:
                artifacts = store
                def artifacts_for(self, manifest_id): return [artifact]
            coverage = manifest_coverage(FakeCatalog(), uuid4())
            self.assertEqual(coverage[0]["physical_rows"], 2)
            self.assertNotEqual(logical_key(raw), logical_key(split))
            result = visible_bars(store.read_bars(artifact), instrument_id=i.instrument_id,
                                  start=raw.start_at, end=raw.end_at + timedelta(days=1),
                                  as_of=instant("2026-01-02T00:00:00Z"), adjustment_basis="raw")
            self.assertEqual(len(result), 1)
            path = Path(directory) / artifact.relative_path
            path.write_bytes(path.read_bytes() + b"tampered")
            with self.assertRaises(OSError):
                store.read_bars(artifact)


class FakeTransport:
    def __init__(self, data):
        self.data, self.calls = data, []

    def get(self, host, path, **kwargs):
        self.calls.append((host, path, kwargs))
        data = self.data.pop(0)
        return Page(data, hashlib.sha256(json.dumps(data).encode()).hexdigest(), 200)


class ProviderTests(unittest.TestCase):
    def test_binance_public_complete_daily_and_native_id(self):
        i, m = identity()
        opening = int(instant("2025-01-02T00:00:00Z").timestamp() * 1000)
        row = [opening, "100", "110", "90", "105", "4", opening + 86_400_000 - 1]
        transport = FakeTransport([[row]])
        with patch.dict(os.environ, {}, clear=True):
            result = BinanceDaily(transport).fetch_daily(i, m, calendar(),
                instant("2025-01-02T00:00:00Z"), instant("2025-01-03T00:00:00Z"))
        self.assertEqual(len(result.bars), 1)
        self.assertEqual(result.bars[0].envelope.instrument_id, i.instrument_id)
        self.assertEqual(result.bars[0].end_at, instant("2025-01-03T00:00:00Z"))
        self.assertEqual(transport.calls[0][0:2], ("data-api.binance.vision", "/api/v3/klines"))
        bad = row.copy()
        bad[6] += 1
        with self.assertRaises(ProviderFailure) as failure:
            BinanceDaily(FakeTransport([[bad]])).fetch_daily(i, m, calendar(),
                instant("2025-01-02T00:00:00Z"), instant("2025-01-03T00:00:00Z"))
        self.assertEqual(failure.exception.code, "UNEXPECTED_DAILY_WINDOW")

    def test_missing_credentials_and_native_upstox_key(self):
        i, m = identity("XNYS", "alpaca", "AAPL", "ticker")
        u, um = identity("XNSE", "upstox", "NSE_EQ|INE000000001", "provider_token")
        india = SessionCalendar(Venue(venue_id="XNSE", timezone="Asia/Kolkata", session_kind="regular"),
                                "nse", "v1")
        start, end = instant("2025-01-02T00:00:00Z"), instant("2025-01-03T00:00:00Z")
        for values in ({}, {"APCA_API_KEY_ID": "test-key"}, {"APCA_API_SECRET_KEY": "test-secret"}):
            transport = FakeTransport([])
            with self.subTest(values=tuple(values)), patch.dict(os.environ, values, clear=True), self.assertRaises(NotConfigured):
                AlpacaDaily(transport).fetch_daily(i, m, calendar("XNYS"), start, end)
            self.assertEqual(transport.calls, [])
        transport = FakeTransport([])
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(NotConfigured):
            UpstoxDaily(transport).fetch_daily(u, um, india, start, end)
        self.assertEqual(transport.calls, [])

    def test_equity_adapters_require_scoped_identity_and_calendar_before_network(self):
        start, end = instant("2025-01-02T00:00:00Z"), instant("2025-01-03T00:00:00Z")
        india = SessionCalendar(Venue(venue_id="XNSE", timezone="Asia/Kolkata", session_kind="regular"),
                                "nse", "v1")
        cases = ((AlpacaDaily, *identity("XNYS", "alpaca", "AAPL", "ticker"), india),
                 (UpstoxDaily, *identity("XNSE", "upstox", "NSE_EQ|INE000000001", "provider_token"),
                  calendar("XNSE")))
        for adapter, instrument, mapping, wrong_calendar in cases:
            transport = FakeTransport([])
            with self.subTest(provider=adapter.provider_id), patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ProviderFailure) as error:
                    adapter(transport).fetch_daily(instrument, mapping, wrong_calendar, start, end)
                self.assertEqual(error.exception.code, "IDENTITY_MISMATCH" if adapter is AlpacaDaily else
                                 "UNSUPPORTED_IDENTITY_OR_CALENDAR")
                self.assertEqual(transport.calls, [])
            expired = mapping.model_copy(update={"valid_to": start + timedelta(hours=12)})
            good_calendar = calendar("XNYS") if adapter is AlpacaDaily else india
            with patch.dict(os.environ, {}, clear=True), self.assertRaises(ProviderFailure) as error:
                adapter(transport).fetch_daily(instrument, expired, good_calendar, start, end)
            self.assertEqual(error.exception.code, "IDENTITY_OUTSIDE_VALID_INTERVAL")
            self.assertEqual(transport.calls, [])

    def test_alpaca_and_upstox_representative_success(self):
        i, m = identity("XNYS", "alpaca", "AAPL", "ticker")
        cal = calendar("XNYS")
        sample = {"bars": [{"t": "2025-01-02T05:00:00Z", "o": 100, "h": 110,
                             "l": 90, "c": 105, "v": 15}], "next_page_token": None}
        alpaca_transport = FakeTransport([sample])
        with patch.dict(os.environ, {"APCA_API_KEY_ID": "test-key", "APCA_API_SECRET_KEY": "test-secret"}):
            batch = AlpacaDaily(alpaca_transport).fetch_daily(i, m, cal,
                instant("2025-01-02T00:00:00Z"), instant("2025-01-03T00:00:00Z"))
        self.assertEqual(batch.feed_class, "iex")
        self.assertEqual([b.close for b in batch.bars], [Decimal("105")])
        self.assertEqual(batch.bars[0].end_at, instant("2025-01-03T05:00:00Z"))
        self.assertEqual(validate_bar(batch.bars[0], cal), ())
        self.assertEqual(alpaca_transport.calls[0][0:2], ("data.alpaca.markets", "/v2/stocks/AAPL/bars"))
        self.assertEqual(alpaca_transport.calls[0][2]["headers"],
                         {"APCA-API-KEY-ID": "test-key", "APCA-API-SECRET-KEY": "test-secret"})
        self.assertEqual(alpaca_transport.calls[0][2]["params"]["adjustment"], "raw")
        india = SessionCalendar(Venue(venue_id="XNSE", timezone="Asia/Kolkata", session_kind="regular"),
            "nse", "v1", [CalendarSession(calendar_id="nse", venue_id="XNSE", session_date=date(2025, 1, 2),
              open_at=instant("2025-01-02T03:45:00Z"), close_at=instant("2025-01-02T10:00:00Z"),
              status="open", version="v1")])
        u, um = identity("XNSE", "upstox", "NSE_EQ|INE000000001", "provider_token")
        transport = FakeTransport([{"data": {"candles": [["2025-01-02T00:00:00+05:30", 100, 110, 90, 105, 20, 0]]}}])
        with patch.dict(os.environ, {"UPSTOX_ACCESS_TOKEN": "test-token"}):
            batch = UpstoxDaily(transport).fetch_daily(u, um, india,
                instant("2025-01-02T00:00:00Z"), instant("2025-01-03T00:00:00Z"))
        self.assertEqual([b.session_date for b in batch.bars], [date(2025, 1, 2)])
        self.assertEqual(batch.adjustment_basis, "provider_unspecified")
        self.assertIn("NSE_EQ%7CINE000000001", transport.calls[0][1])
        self.assertEqual(transport.calls[0][2]["headers"], {"Authorization": "Bearer test-token"})

    def test_calendar_rejects_mixed_versions(self):
        old = calendar("XNYS").session(date(2025, 1, 2))
        with self.assertRaises(ValueError):
            SessionCalendar(Venue(venue_id="XNYS", timezone="America/New_York", session_kind="regular"),
                            "nyse", "v2", [old])

    def test_crypto_bootstrap_registers_only_verified_public_native_pair(self):
        class FakeCatalog:
            def __init__(self): self.registered = []
            def load_identity(self): return ([], [])
            def register_identity(self, venues, instruments, mappings):
                self.registered.append((venues, instruments, mappings))
        catalog = FakeCatalog()
        row = [int(instant("2020-01-01T00:00:00Z").timestamp() * 1000)]
        transport = FakeTransport([{"symbols": [{"symbol": "BTCUSDT", "status": "TRADING",
                                                 "baseAsset": "BTC", "quoteAsset": "USDT"}]}, [row]])
        result = discover_crypto(catalog, ["BTCUSDT"], transport)
        self.assertEqual(result[0]["status"], "registered")
        self.assertEqual(catalog.registered[0][2][0].identifier_value, "BTCUSDT")
        self.assertEqual(catalog.registered[0][1][0].valid_from, instant("2020-01-01T00:00:00Z"))

    def test_timeout_bad_response_and_read_only_allowlist_redact(self):
        key = "secret-token-for-test"
        def handler(request):
            self.assertEqual(request.method, "GET")
            raise httpx.ReadTimeout("request failed: " + key)
        client = httpx.Client(transport=httpx.MockTransport(handler), timeout=0.1)
        with patch("market_cortex.providers.time.sleep"):
            with self.assertRaises(ProviderFailure) as caught:
                ReadTransport(client).get("data-api.binance.vision", "/api/v3/klines")
        self.assertNotIn(key, str(caught.exception))
        with self.assertRaises(ProviderFailure):
            ReadTransport(client).get("api.upstox.com", "/v2/order/place")
        malformed = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=b"not json")))
        with self.assertRaises(ProviderFailure) as response:
            ReadTransport(malformed).get("data-api.binance.vision", "/api/v3/klines")
        self.assertEqual(response.exception.code, "MALFORMED_JSON")


class ApiTests(unittest.TestCase):
    def test_coverage_reports_visible_gap_without_inventing_a_bar(self):
        instrument, mapping = identity()
        cal = calendar()
        observed = bar(instrument, mapping, cal)

        class FakeCatalog:
            def load_identity(self): return [instrument], [mapping]
            def load_calendar(self, *args): return cal
            def bars(self, **kwargs): return uuid4(), [observed]

        settings = Settings(database_url=None, data_root=Path(tempfile.gettempdir()),
                            owner_timezone="Asia/Kolkata", base_currency="INR", cloud_model_allowed=False,
                            owner_configured=False)
        client = TestClient(create_app(settings, FakeCatalog()))
        response = client.get("/api/v1/coverage", params={"instrument_id": str(instrument.instrument_id),
            "from": "2025-01-02", "to": "2025-01-03", "as_of": "2025-01-04T00:00:00Z"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["expected_sessions"], 2)
        self.assertEqual(response.json()["observed_sessions"], 1)
        self.assertEqual(response.json()["gaps"], [{"session_date": "2025-01-03",
            "reason": "NO_VISIBLE_OBSERVATION_AT_CUTOFF"}])
        self.assertNotIn("items", response.json())

    def test_instrument_search_respects_mapping_knowledge_and_valid_time(self):
        active, mapping = identity("XNYS", "alpaca", "SAME", "ticker")
        mapping = mapping.model_copy(update={"available_at": instant("2025-01-04T00:00:00Z")})
        expired, old_mapping = identity("XNYS", "alpaca", "SAME", "ticker")
        expired = expired.model_copy(update={"valid_to": instant("2025-01-03T00:00:00Z")})

        class FakeCatalog:
            def load_identity(self): return [active, expired], [mapping, old_mapping]

        settings = Settings(database_url=None, data_root=Path(tempfile.gettempdir()),
                            owner_timezone="Asia/Kolkata", base_currency="INR", cloud_model_allowed=False,
                            owner_configured=False)
        client = TestClient(create_app(settings, FakeCatalog()))
        before = client.get("/api/v1/instruments", params={"query": "SAME", "as_of": "2025-01-03T12:00:00Z"})
        self.assertEqual(before.json()["items"], [])
        after = client.get("/api/v1/instruments", params={"query": "SAME", "as_of": "2025-01-05T00:00:00Z"})
        self.assertEqual(len(after.json()["items"]), 1)
        self.assertEqual(after.json()["items"][0]["instrument"]["instrument_id"], str(active.instrument_id))
        self.assertFalse(after.json()["ambiguous"])

    def test_health_and_no_write_routes_redact_dsn(self):
        settings = Settings(database_url="postgresql://secret:password@localhost/test", data_root=Path(tempfile.gettempdir()),
                            owner_timezone="Asia/Kolkata", base_currency="INR", cloud_model_allowed=False,
                            owner_configured=False)
        class FakeCatalog:
            def head(self): return None
            def load_identity(self): return ([], [])
            def bars(self, **kwargs):
                self.cutoff = kwargs["as_of"]
                return (None, [])
        catalog = FakeCatalog()
        client = TestClient(create_app(settings, catalog))
        response = client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("secret", response.text)
        self.assertEqual(client.post("/api/v1/orders").status_code, 404)
        bars_response = client.get("/api/v1/bars", params={"instrument_id": str(uuid4()),
            "from": "2025-01-01T00:00:00Z", "to": "2025-01-02T00:00:00Z"})
        self.assertEqual(bars_response.status_code, 200)
        self.assertEqual(bars_response.json()["as_of"], catalog.cutoff.isoformat())
        self.assertEqual(client.get("/api/v1/bars", params={"instrument_id": str(uuid4()),
            "from": "2025-01-01T00:00:00", "to": "2025-01-02T00:00:00Z"}).status_code, 422)


class BackupTests(unittest.TestCase):
    def test_encrypted_roundtrip_tamper_detection_and_safe_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            source, encrypted, restored = (Path(directory) / name for name in ("a", "a.mcbackup", "b"))
            source.write_bytes(os.urandom(1_200_000))
            encrypt_file(source, encrypted, "a-long-test-only-backup-passphrase")
            self.assertNotIn(source.read_bytes()[:128], encrypted.read_bytes())
            decrypt_file(encrypted, restored, "a-long-test-only-backup-passphrase")
            self.assertEqual(restored.read_bytes(), source.read_bytes())
            with self.assertRaises(ValueError):
                decrypt_file(encrypted, restored, "a-different-backup-passphrase")
            self.assertFalse(restored.exists())
            tampered = bytearray(encrypted.read_bytes())
            tampered[-20] ^= 1
            encrypted.write_bytes(tampered)
            with self.assertRaises(ValueError):
                decrypt_file(encrypted, restored, "a-long-test-only-backup-passphrase")
        self.assertFalse(_safe_member("artifacts/../../secret"))
        self.assertFalse(_safe_member("artifacts\\lake\\x.parquet"))
        self.assertTrue(_safe_member("artifacts/lake/kind=Bar/a.parquet"))

    def test_restore_rejects_live_database_even_with_different_password(self):
        with self.assertRaises(ValueError):
            restore(Path("missing"), Path("unused"), "postgresql://u:new@localhost/live",
                    "postgresql://u:old@localhost/live", "a-long-test-only-backup-passphrase")


if __name__ == "__main__":
    unittest.main()
