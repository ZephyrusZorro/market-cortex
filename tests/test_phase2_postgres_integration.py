"""Opt-in isolated PostgreSQL gate for derived feature replay."""

from __future__ import annotations

import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from market_cortex.calendar import SessionCalendar
from market_cortex.contracts import Bar, IdentifierMapping, Instrument, ObservationEnvelope, Venue
from market_cortex.database import connect, migrate
from market_cortex.features import FeatureEngine, FeatureRequest
from market_cortex.storage import ArtifactStore, PostgresCatalog


DSN = os.environ.get("MARKET_CORTEX_TEST_DATABASE_URL")
SAFE = bool(DSN and conninfo_to_dict(DSN).get("dbname", "").lower().endswith("_test"))
UTC = timezone.utc


@pytest.mark.skipif(not SAFE, reason="dedicated *_test PostgreSQL URL required")
def test_feature_replay_over_real_manifest_correction():
    schema = f"market_cortex_p2_{uuid4().hex}"
    with tempfile.TemporaryDirectory(prefix="market-cortex-p2-") as directory:
        with connect(DSN) as connection:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            isolated = make_conninfo(DSN, options=f"-csearch_path={schema}")
            migrate(isolated, Path(__file__).resolve().parents[1])
            catalog = PostgresCatalog(isolated, ArtifactStore(Path(directory)))
            venue = Venue(venue_id="BINANCE_SPOT", timezone="UTC", session_kind="24x7")
            calendar = SessionCalendar(venue, "BINANCE_SPOT:utc_daily", "v1")
            instrument = Instrument(instrument_id=uuid4(), asset_class="crypto_spot",
                instrument_kind="spot_pair", primary_venue_id=venue.venue_id,
                trading_currency="USDT", price_unit="quote_currency", quantity_unit="BTC",
                listing_status="active", valid_from=datetime(2024, 1, 1, tzinfo=UTC))
            mapping = IdentifierMapping(mapping_id=uuid4(), instrument_id=instrument.instrument_id,
                provider_id="binance", venue_id=venue.venue_id, identifier_type="exchange_pair",
                identifier_value="BTCUSDT", valid_from=instrument.valid_from,
                available_at=datetime(2024, 1, 2, tzinfo=UTC))
            catalog.register_identity([venue], [instrument], [mapping])

            def make(index, close, batch, availability):
                day = date(2025, 1, 1) + timedelta(days=index)
                start = datetime.combine(day, datetime.min.time(), UTC)
                end = start + timedelta(days=1)
                envelope = ObservationEnvelope(observation_id=uuid4(), instrument_id=instrument.instrument_id,
                    venue_id=venue.venue_id, provider_id="binance", provider_record_id=f"BTCUSDT:{day}",
                    event_at=end, available_at=availability, availability_basis="observed_arrival",
                    ingested_at=availability, timestamp_precision="day", is_final=True,
                    quality_state="valid", freshness_policy_id="binance:daily", validation_codes=[],
                    source_ref=f"binance:daily:{batch}", source_batch_id=batch,
                    raw_content_hash="a" * 64, raw_retention_state="hash_only",
                    normalizer_version="daily_v1", license_policy_id="hash_only",
                    currency="USDT", unit="quote_currency", adjustment_basis="raw")
                return Bar(envelope=envelope, interval="P1D", start_at=start, end_at=end,
                           session_date=day, calendar_id=calendar.calendar_id,
                           open=close, high=str(float(close) + 1), low=str(float(close) - 1),
                           close=close, volume="100", aggregation_method="provider_spot_public:session",
                           quote_currency="USDT", volume_unit="BTC")

            batch1 = uuid4()
            original = [make(index, str(value), batch1,
                             datetime(2025, 1, 10, tzinfo=UTC))
                        for index, value in enumerate((10, 20, 30, 40, 50))]
            first = catalog.ingest(original, calendar, source_batch_id=batch1, provider_id="binance",
                                   raw_hash="a" * 64, fetched_at=datetime(2025, 1, 10, tzinfo=UTC))
            assert first.stored == 5 and first.manifest_id is not None
            batch2 = uuid4()
            correction = make(2, "60", batch2, datetime(2025, 1, 20, tzinfo=UTC))
            second = catalog.ingest([correction], calendar, source_batch_id=batch2,
                                    provider_id="binance", raw_hash="b" * 64,
                                    fetched_at=datetime(2025, 1, 20, tzinfo=UTC))
            assert second.stored == 1 and second.manifest_id != first.manifest_id
            engine = FeatureEngine(catalog)

            def request(manifest, cutoff):
                return FeatureRequest(instrument_id=instrument.instrument_id, feature="sma",
                    start_date=date(2025, 1, 1), end_date=date(2025, 1, 5),
                    as_of=cutoff, manifest_id=manifest, provider_id="binance",
                    parameters={"period": 3})

            before = engine.calculate(request(second.manifest_id, datetime(2025, 1, 10, tzinfo=UTC)))
            after = engine.calculate(request(second.manifest_id, datetime(2025, 1, 21, tzinfo=UTC)))
            pinned_old = engine.calculate(request(first.manifest_id, datetime(2025, 1, 21, tzinfo=UTC)))
            assert before.points[2].value == 20
            assert after.points[2].value == 30
            assert pinned_old.points[2].value == 20
            assert before.points[4].value == 40
            assert after.points[4].value == 50
            assert engine.calculate(request(second.manifest_id,
                                            datetime(2025, 1, 21, tzinfo=UTC))).feature_id == after.feature_id
            assert catalog.scan_storage()["corrupt"] == []
        finally:
            with connect(DSN) as connection:
                connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
