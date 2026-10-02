"""Opt-in live PostgreSQL gate. Requires a dedicated *_test database URL.

Example: MARKET_CORTEX_TEST_DATABASE_URL=... pytest -q tests/test_postgres_integration.py
Never point this suite at an owner production database.
The test role needs CREATE on the test database; each run owns and drops its schema.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from market_cortex.calendar import SessionCalendar
from market_cortex.contracts import Bar, IdentifierMapping, Instrument, ObservationEnvelope, Venue
from market_cortex.database import connect, migrate
from market_cortex.jobs import JobQueue, OutboxConsumer
from market_cortex.storage import ArtifactStore, PostgresCatalog

DSN = os.environ.get("MARKET_CORTEX_TEST_DATABASE_URL")
SAFE = bool(DSN and conninfo_to_dict(DSN).get("dbname", "").lower().endswith("_test"))
Z = timezone.utc


@unittest.skipUnless(SAFE, "dedicated MARKET_CORTEX_TEST_DATABASE_URL required")
class PostgresIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.schema = f"market_cortex_it_{uuid4().hex}"
        cls.directory = tempfile.TemporaryDirectory()
        try:
            with connect(DSN) as connection:
                connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))
            # All catalog connections use this schema, leaving existing test data alone.
            cls.dsn = make_conninfo(DSN, options=f"-csearch_path={cls.schema}")
            with connect(cls.dsn) as connection:
                if connection.execute("SELECT current_schema()").fetchone()[0] != cls.schema:
                    raise RuntimeError("isolated test schema is not active")
            migrate(cls.dsn, cls.root)
            cls.catalog = PostgresCatalog(cls.dsn, ArtifactStore(Path(cls.directory.name)))
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            if hasattr(cls, "schema"):
                with connect(DSN) as connection:
                    connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(cls.schema)))
        finally:
            if hasattr(cls, "directory"):
                cls.directory.cleanup()

    def test_manifest_correction_idempotence_and_as_of(self):
        catalog = self.catalog
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
        with self.assertRaises(ValueError):
            catalog.ingest([original], cal, source_batch_id=batch1, provider_id="synthetic",
                           raw_hash="c" * 64, fetched_at=datetime(2026, 1, 1, tzinfo=Z))
        with connect(self.dsn) as connection:
            outbox_count = connection.execute("SELECT count(*) FROM outbox WHERE aggregate_id = %s",
                                              (str(one.manifest_id),)).fetchone()[0]
        self.assertEqual(outbox_count, 1)

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
        inventory = catalog.scan_storage()
        self.assertEqual(inventory["corrupt"], [])
        self.assertEqual(inventory["missing"], [])

    def test_failed_publication_leaves_recoverable_orphan(self):
        class FailAfterWrite(ArtifactStore):
            written = None

            def write_bars(self, bars):
                self.written = super().write_bars(bars)
                raise RuntimeError("injected failure after durable artifact write")

        venue = Venue(venue_id="XFAIL", timezone="UTC", session_kind="24x7")
        instrument = Instrument(instrument_id=uuid4(), asset_class="crypto_spot", instrument_kind="spot_pair",
                                primary_venue_id=venue.venue_id, trading_currency="USD", price_unit="USD",
                                quantity_unit="coin", listing_status="active",
                                valid_from=datetime(2020, 1, 1, tzinfo=Z))
        mapping = IdentifierMapping(mapping_id=uuid4(), instrument_id=instrument.instrument_id,
                                    provider_id="synthetic", venue_id=venue.venue_id,
                                    identifier_type="exchange_pair", identifier_value="FAILUSD",
                                    valid_from=instrument.valid_from,
                                    available_at=datetime(2020, 1, 2, tzinfo=Z))
        self.catalog.register_identity([venue], [instrument], [mapping])
        batch_id = uuid4()
        start = datetime(2025, 2, 1, tzinfo=Z)
        end = datetime(2025, 2, 2, tzinfo=Z)
        fetched_at = datetime(2026, 1, 1, tzinfo=Z)
        envelope = ObservationEnvelope(observation_id=uuid4(), instrument_id=instrument.instrument_id,
            venue_id=venue.venue_id, provider_id="synthetic", provider_record_id="FAILUSD:2025-02-01",
            event_at=end, available_at=end, availability_basis="documented_publication",
            ingested_at=fetched_at, timestamp_precision="day", is_final=True,
            quality_state="valid", freshness_policy_id="test", validation_codes=[], source_ref="synthetic",
            source_batch_id=batch_id, raw_content_hash="d" * 64, raw_retention_state="hash_only",
            normalizer_version="test", license_policy_id="hash_only", unit="USD", adjustment_basis="raw")
        observation = Bar(envelope=envelope, interval="P1D", start_at=start, end_at=end,
                          session_date=date(2025, 2, 1), calendar_id="test_daily", open="100", high="110",
                          low="90", close="105", volume="10", aggregation_method="test",
                          quote_currency="USD", volume_unit="coin")
        cal = SessionCalendar(venue, "test_daily", "v1")
        failing_store = FailAfterWrite(Path(self.directory.name))
        failing_catalog = PostgresCatalog(self.dsn, failing_store)
        original_head = self.catalog.head()
        with self.assertRaisesRegex(RuntimeError, "injected failure"):
            failing_catalog.ingest([observation], cal, source_batch_id=batch_id,
                                   provider_id="synthetic", raw_hash="d" * 64, fetched_at=fetched_at)
        self.assertEqual(self.catalog.head(), original_head)
        orphan = failing_store.written.relative_path
        self.assertIn(orphan, self.catalog.scan_storage()["unreferenced"])
        result = self.catalog.ingest([observation], cal, source_batch_id=batch_id,
                                     provider_id="synthetic", raw_hash="d" * 64, fetched_at=fetched_at)
        self.assertEqual(result.stored, 1)
        self.assertNotIn(orphan, self.catalog.scan_storage()["unreferenced"])
        self.assertEqual([bar.close for bar in self.catalog.bars(instrument_id=instrument.instrument_id,
            start=start, end=end + (end - start), as_of=end + (end - start),
            manifest_id=result.manifest_id)[1]], [105])

    def test_job_retry_dead_letter_and_execution_guard(self):
        queue = JobQueue(self.dsn)
        key = f"synthetic-sync:{uuid4()}"
        job_id = queue.enqueue("market.sync.daily", key, {"source": "synthetic"})
        self.assertEqual(queue.enqueue("market.sync.daily", key, {"source": "synthetic"}), job_id)
        with self.assertRaises(ValueError):
            queue.enqueue("broker_order", f"forbidden:{uuid4()}", {})
        first = queue.claim(lease_seconds=1)
        self.assertEqual(first.job_id, job_id)
        self.assertEqual(queue.finish(job_id, first.attempts, "PROVIDER_UNAVAILABLE", max_attempts=2), "ready")
        with connect(self.dsn) as connection:
            connection.execute("UPDATE jobs SET next_attempt_at = now() - interval '1 second' WHERE job_id = %s",
                               (job_id,))
        retry = queue.claim(lease_seconds=1)
        self.assertEqual(retry.job_id, job_id)
        self.assertEqual(retry.attempts, 2)
        self.assertEqual(queue.finish(job_id, retry.attempts, "PROVIDER_UNAVAILABLE", max_attempts=2), "dead")
        with connect(self.dsn) as connection:
            row = connection.execute("SELECT state, attempts, error_code FROM jobs WHERE job_id = %s",
                                     (job_id,)).fetchone()
        self.assertEqual(row, ("dead", 2, "PROVIDER_UNAVAILABLE"))
        self.assertIsNone(queue.claim())

    def test_invalid_ohlc_is_quarantined_and_not_published(self):
        venue = Venue(venue_id="XBAD", timezone="UTC", session_kind="24x7")
        instrument = Instrument(instrument_id=uuid4(), asset_class="crypto_spot", instrument_kind="spot_pair",
                                primary_venue_id=venue.venue_id, trading_currency="USD", price_unit="USD",
                                quantity_unit="coin", listing_status="active",
                                valid_from=datetime(2020, 1, 1, tzinfo=Z))
        mapping = IdentifierMapping(mapping_id=uuid4(), instrument_id=instrument.instrument_id,
                                    provider_id="synthetic", venue_id=venue.venue_id,
                                    identifier_type="exchange_pair", identifier_value="BADUSD",
                                    valid_from=instrument.valid_from,
                                    available_at=datetime(2020, 1, 2, tzinfo=Z))
        self.catalog.register_identity([venue], [instrument], [mapping])
        batch_id = uuid4()
        start, end = datetime(2025, 3, 1, tzinfo=Z), datetime(2025, 3, 2, tzinfo=Z)
        envelope = ObservationEnvelope(observation_id=uuid4(), instrument_id=instrument.instrument_id,
            venue_id=venue.venue_id, provider_id="synthetic", provider_record_id="BADUSD:2025-03-01",
            event_at=end, available_at=end, availability_basis="documented_publication",
            ingested_at=datetime(2026, 1, 1, tzinfo=Z), timestamp_precision="day", is_final=True,
            quality_state="valid", freshness_policy_id="test", validation_codes=[], source_ref="synthetic",
            source_batch_id=batch_id, raw_content_hash="e" * 64, raw_retention_state="hash_only",
            normalizer_version="test", license_policy_id="hash_only", unit="USD", adjustment_basis="raw")
        invalid = Bar(envelope=envelope, interval="P1D", start_at=start, end_at=end,
                      session_date=date(2025, 3, 1), calendar_id="test_daily", open="100", high="99",
                      low="90", close="105", volume="10", aggregation_method="test",
                      quote_currency="USD", volume_unit="coin")
        result = self.catalog.ingest([invalid], SessionCalendar(venue, "test_daily", "v1"),
                                     source_batch_id=batch_id, provider_id="synthetic",
                                     raw_hash="e" * 64, fetched_at=datetime(2026, 1, 1, tzinfo=Z))
        self.assertEqual((result.stored, result.quarantined, result.manifest_id), (0, 1, None))
        with connect(self.dsn) as connection:
            reasons = connection.execute("SELECT reason_codes FROM quarantine WHERE source_batch_id = %s",
                                         (batch_id,)).fetchone()[0]
            published = connection.execute("SELECT count(*) FROM observations WHERE instrument_id = %s",
                                           (instrument.instrument_id,)).fetchone()[0]
        self.assertIn("OHLC_RANGE", reasons)
        self.assertEqual(published, 0)

    def test_outbox_handler_rollback_and_receipts(self):
        consumer_id = f"integration-{uuid4()}"
        consumer = OutboxConsumer(self.dsn, consumer_id)
        first_seen = []

        def fail_once(connection, event):
            first_seen.append(event.event_id)
            raise RuntimeError("injected consumer failure")

        with self.assertRaisesRegex(RuntimeError, "injected consumer failure"):
            consumer.consume_one(fail_once)
        with connect(self.dsn) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM consumer_receipts WHERE consumer_id = %s",
                                                (consumer_id,)).fetchone()[0], 0)

        handled = []

        def handle(connection, event):
            self.assertEqual(connection.execute("SELECT status FROM dataset_manifests WHERE manifest_id = %s",
                                                (UUID(event.aggregate_id),)).fetchone()[0], "committed")
            handled.append(event.event_id)

        while consumer.consume_one(handle):
            pass
        self.assertEqual(handled[0], first_seen[0])
        self.assertEqual(len(handled), len(set(handled)))
        self.assertFalse(consumer.consume_one(handle))
        with connect(self.dsn) as connection:
            receipts = connection.execute("SELECT count(*) FROM consumer_receipts WHERE consumer_id = %s",
                                          (consumer_id,)).fetchone()[0]
            events = connection.execute("SELECT count(*) FROM outbox").fetchone()[0]
        self.assertEqual(receipts, events)
