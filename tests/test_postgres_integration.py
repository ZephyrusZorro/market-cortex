"""Opt-in live PostgreSQL gate. Requires a dedicated *_test database URL.

Example: MARKET_CORTEX_TEST_DATABASE_URL=... pytest -q tests/test_postgres_integration.py
Never point this suite at an owner production database.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from psycopg.conninfo import conninfo_to_dict

from market_cortex.calendar import SessionCalendar
from market_cortex.contracts import Bar, IdentifierMapping, Instrument, ObservationEnvelope, Venue
from market_cortex.database import migrate
from market_cortex.storage import ArtifactStore, PostgresCatalog

DSN = os.environ.get("MARKET_CORTEX_TEST_DATABASE_URL")
SAFE = bool(DSN and "test" in conninfo_to_dict(DSN).get("dbname", "").lower())
Z = timezone.utc


@unittest.skipUnless(SAFE, "dedicated MARKET_CORTEX_TEST_DATABASE_URL required")
class PostgresIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        migrate(DSN, cls.root)

    def test_manifest_correction_idempotence_and_as_of(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = PostgresCatalog(DSN, ArtifactStore(Path(directory)))
            venue = Venue(venue_id="XTEST", timezone="UTC", session_kind="24x7")
            start = datetime(2025, 1, 2, tzinfo=Z)
            first_available = datetime(2025, 1, 3, 1, tzinfo=Z)
            instrument = Instrument(instrument_id=uuid4(), asset_class="crypto_spot", instrument_kind="spot_pair",
                                    primary_venue_id=venue.venue_id, trading_currency="USD", price_unit="USD",
                                    quantity_unit="coin", listing_status="active",
                                    valid_from=datetime(2020, 1, 1, tzinfo=Z))
            mapping = IdentifierMapping(mapping_id=uuid4(), instrument_id=instrument.instrument_id,
                                        provider_id="synthetic", venue_id=venue.venue_id,
                                        identifier_type="exchange_pair", identifier_value="TESTUSD",
                                        valid_from=instrument.valid_from,
                                        available_at=datetime(2020, 1, 2, tzinfo=Z))
            catalog.register_identity([venue], [instrument], [mapping])
            cal = SessionCalendar(venue, "test_daily", "v1")

            def make(close: str, available_at: datetime, batch_id):
                end = datetime(2025, 1, 3, tzinfo=Z)
                env = ObservationEnvelope(observation_id=uuid4(), instrument_id=instrument.instrument_id,
                    venue_id=venue.venue_id, provider_id="synthetic", provider_record_id="TESTUSD:2025-01-02",
                    event_at=end, available_at=available_at, availability_basis="documented_publication",
                    ingested_at=datetime(2026, 1, 1, tzinfo=Z), timestamp_precision="day", is_final=True,
                    quality_state="valid", freshness_policy_id="test", validation_codes=[], source_ref="synthetic",
                    source_batch_id=batch_id, raw_content_hash="a" * 64, raw_retention_state="hash_only",
                    normalizer_version="test", license_policy_id="hash_only", unit="USD", adjustment_basis="raw")
                return Bar(envelope=env, interval="P1D", start_at=start, end_at=end, session_date=date(2025, 1, 2),
                           calendar_id="test_daily", open="100", high="110", low="90", close=close, volume="10",
                           aggregation_method="test", quote_currency="USD", volume_unit="coin")

            batch1 = uuid4()
            original = make("100", first_available, batch1)
            one = catalog.ingest([original], cal, source_batch_id=batch1, provider_id="synthetic",
                                 raw_hash="a" * 64, fetched_at=datetime(2026, 1, 1, tzinfo=Z))
            self.assertEqual(one.stored, 1)
            self.assertIsNotNone(one.manifest_id)
            repeat = catalog.ingest([original], cal, source_batch_id=batch1, provider_id="synthetic",
                                    raw_hash="a" * 64, fetched_at=datetime(2026, 1, 1, tzinfo=Z))
            self.assertEqual((repeat.stored, repeat.duplicates, repeat.manifest_id), (0, 1, None))

            batch2 = uuid4()
            correction = make("101", datetime(2025, 1, 4, 12, tzinfo=Z), batch2)
            two = catalog.ingest([correction], cal, source_batch_id=batch2, provider_id="synthetic",
                                 raw_hash="b" * 64, fetched_at=datetime(2026, 1, 1, tzinfo=Z))
            before = catalog.bars(instrument_id=instrument.instrument_id, start=start,
                end=datetime(2025, 1, 4, tzinfo=Z), as_of=datetime(2025, 1, 3, 12, tzinfo=Z),
                manifest_id=two.manifest_id)[1]
            after = catalog.bars(instrument_id=instrument.instrument_id, start=start,
                end=datetime(2025, 1, 4, tzinfo=Z), as_of=datetime(2025, 1, 5, tzinfo=Z),
                manifest_id=two.manifest_id)[1]
            pinned = catalog.bars(instrument_id=instrument.instrument_id, start=start,
                end=datetime(2025, 1, 4, tzinfo=Z), as_of=datetime(2025, 1, 5, tzinfo=Z),
                manifest_id=one.manifest_id)[1]
            self.assertEqual(([b.close for b in before], [b.close for b in after], [b.close for b in pinned]),
                             ([100], [101], [100]))
            self.assertEqual(catalog.scan_storage()["corrupt"], [])
