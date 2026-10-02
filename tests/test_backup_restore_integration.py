"""Opt-in encrypted backup/restore rehearsal using two disposable *_test databases.

Set MARKET_CORTEX_TEST_DATABASE_URL and MARKET_CORTEX_RESTORE_TEST_DATABASE_URL.
The restore database must be empty. Both databases must be distinct and the role
must be able to create and drop a schema; pg_dump and pg_restore must be on PATH.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from market_cortex.backup import backup, restore
from market_cortex.calendar import SessionCalendar
from market_cortex.config import Settings
from market_cortex.contracts import Bar, IdentifierMapping, Instrument, ObservationEnvelope, Venue
from market_cortex.database import connect, migrate
from market_cortex.storage import ArtifactStore, PostgresCatalog

SOURCE = os.environ.get("MARKET_CORTEX_TEST_DATABASE_URL")
TARGET = os.environ.get("MARKET_CORTEX_RESTORE_TEST_DATABASE_URL")


def _safe_pair() -> bool:
    if not SOURCE or not TARGET:
        return False
    source = conninfo_to_dict(SOURCE)
    target = conninfo_to_dict(TARGET)
    if not source.get("dbname", "").lower().endswith("_test") or not target.get("dbname", "").lower().endswith("_test"):
        return False
    return (source.get("host", "localhost"), source.get("port", "5432"), source["dbname"]) != (
        target.get("host", "localhost"), target.get("port", "5432"), target["dbname"])


@unittest.skipUnless(_safe_pair(), "two distinct dedicated *_test database URLs required")
class BackupRestoreIntegration(unittest.TestCase):
    def test_encrypted_restore_preserves_pinned_as_of_and_lineage(self):
        with connect(TARGET) as connection:
            tables = connection.execute("""SELECT count(*) FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')""").fetchone()[0]
        self.assertEqual(tables, 0, "restore test database must start empty")

        schema = f"market_cortex_drill_{uuid4().hex}"
        with tempfile.TemporaryDirectory(prefix="market-cortex-drill-") as directory:
            root = Path(directory)
            source_root, restored_root = root / "source", root / "restored"
            snapshot = root / "snapshot.mcbackup"
            with connect(SOURCE) as connection:
                connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            try:
                source_dsn = make_conninfo(SOURCE, options=f"-csearch_path={schema}")
                target_dsn = make_conninfo(TARGET, options=f"-csearch_path={schema}")
                with connect(source_dsn) as connection:
                    self.assertEqual(connection.execute("SELECT current_schema()").fetchone()[0], schema)
                migrate(source_dsn, Path(__file__).resolve().parents[1])
                catalog = PostgresCatalog(source_dsn, ArtifactStore(source_root))
                venue = Venue(venue_id="XDRILL", timezone="UTC", session_kind="24x7")
                instrument = Instrument(instrument_id=uuid4(), asset_class="crypto_spot", instrument_kind="spot_pair",
                                        primary_venue_id=venue.venue_id, trading_currency="USD", price_unit="USD",
                                        quantity_unit="coin", listing_status="active",
                                        valid_from=datetime(2020, 1, 1, tzinfo=timezone.utc))
                mapping = IdentifierMapping(mapping_id=uuid4(), instrument_id=instrument.instrument_id,
                                            provider_id="synthetic", venue_id=venue.venue_id,
                                            identifier_type="exchange_pair", identifier_value="DRILLUSD",
                                            valid_from=instrument.valid_from,
                                            available_at=datetime(2020, 1, 2, tzinfo=timezone.utc))
                catalog.register_identity([venue], [instrument], [mapping])
                calendar = SessionCalendar(venue, "drill_daily", "v1")
                start = datetime(2025, 1, 2, tzinfo=timezone.utc)
                end = datetime(2025, 1, 3, tzinfo=timezone.utc)
                fetched = datetime(2026, 1, 1, tzinfo=timezone.utc)

                def observation(close: str, available: datetime, batch_id):
                    envelope = ObservationEnvelope(observation_id=uuid4(), instrument_id=instrument.instrument_id,
                        venue_id=venue.venue_id, provider_id="synthetic", provider_record_id="DRILLUSD:2025-01-02",
                        event_at=end, available_at=available, availability_basis="documented_publication",
                        ingested_at=fetched, timestamp_precision="day", is_final=True, quality_state="valid",
                        freshness_policy_id="test", validation_codes=[], source_ref="synthetic",
                        source_batch_id=batch_id, raw_content_hash="a" * 64, raw_retention_state="hash_only",
                        normalizer_version="test", license_policy_id="hash_only", unit="USD", adjustment_basis="raw")
                    return Bar(envelope=envelope, interval="P1D", start_at=start, end_at=end,
                               session_date=date(2025, 1, 2), calendar_id="drill_daily", open="100",
                               high="110", low="90", close=close, volume="10", aggregation_method="test",
                               quote_currency="USD", volume_unit="coin")

                first_batch = uuid4()
                first = catalog.ingest([observation("100", datetime(2025, 1, 3, 1, tzinfo=timezone.utc), first_batch)],
                                       calendar, source_batch_id=first_batch, provider_id="synthetic",
                                       raw_hash="a" * 64, fetched_at=fetched)
                second_batch = uuid4()
                second = catalog.ingest([observation("101", datetime(2025, 1, 4, 12, tzinfo=timezone.utc), second_batch)],
                                        calendar, source_batch_id=second_batch, provider_id="synthetic",
                                        raw_hash="b" * 64, fetched_at=fetched)
                self.assertNotEqual(first.manifest_id, second.manifest_id)
                settings = Settings(source_dsn, source_root, "Asia/Kolkata", "INR", False, True)
                passphrase = "synthetic-test-passphrase-2026"
                result = backup(settings, snapshot, passphrase)
                self.assertEqual(result["artifact_count"], 2)
                self.assertTrue(snapshot.is_file())
                restored = restore(snapshot, restored_root, TARGET, SOURCE, passphrase)
                self.assertEqual(restored["head_manifest_id"], str(second.manifest_id))
                replay = PostgresCatalog(target_dsn, ArtifactStore(restored_root))
                self.assertEqual(replay.head(), catalog.head())
                self.assertEqual(replay.scan_storage()["missing"], [])
                self.assertEqual(replay.scan_storage()["corrupt"], [])
                self.assertEqual(replay.load_identity(), catalog.load_identity())
                with connect(target_dsn) as connection:
                    retention = connection.execute("""SELECT DISTINCT raw_retention_state, rights_policy_id
                        FROM source_batches""").fetchall()
                self.assertEqual(retention, [("hash_only", "hash_only")])
                self.assertTrue(all(path.suffix == ".parquet" for path in restored_root.rglob("*") if path.is_file()))
                for pinned, cutoff, expected in (
                    (second.manifest_id, datetime(2025, 1, 3, 12, tzinfo=timezone.utc), 100),
                    (second.manifest_id, datetime(2025, 1, 5, tzinfo=timezone.utc), 101),
                    (first.manifest_id, datetime(2025, 1, 5, tzinfo=timezone.utc), 100),
                ):
                    query = dict(instrument_id=instrument.instrument_id, start=start,
                                 end=end.replace(day=4), as_of=cutoff, manifest_id=pinned)
                    original = [bar.close for bar in catalog.bars(**query)[1]]
                    recovered = [bar.close for bar in replay.bars(**query)[1]]
                    self.assertEqual(original, recovered)
                    self.assertEqual(recovered, [expected])
            finally:
                # Catalog references are removed before their temporary files disappear.
                with connect(TARGET) as connection:
                    connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
                with connect(SOURCE) as connection:
                    connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
