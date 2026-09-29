"""Content-addressed Parquet artifacts and an atomic PostgreSQL manifest head.

Files are durable before the catalog transaction commits. A crash between those
steps leaves an unreferenced file, never a partially visible dataset. Retrying is
idempotent by observation fingerprint, not by the provider batch timestamp.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pyarrow as pa
import pyarrow.parquet as pq
from psycopg.types.json import Jsonb

from .calendar import CalendarMissing, SessionCalendar
from .contracts import Bar, CalendarSession, IdentifierMapping, Instrument, Venue, utc
from .database import connect
from .quality import validate_bar


def fingerprint(bar: Bar) -> str:
    """Logical source record content, excluding arrival, batch and observation IDs."""
    payload = {
        "provider": bar.envelope.provider_id, "record": bar.envelope.provider_record_id,
        "instrument": str(bar.envelope.instrument_id), "venue": bar.envelope.venue_id,
        "interval": bar.interval, "start": bar.start_at.isoformat(), "end": bar.end_at.isoformat(),
        "adjustment": bar.envelope.adjustment_basis,
        "prices": [str(bar.open), str(bar.high), str(bar.low), str(bar.close)],
        "volume": str(bar.volume) if bar.volume is not None else None,
        "trade_count": bar.trade_count, "is_final": bar.envelope.is_final,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def logical_key(bar: Bar) -> str:
    parts = [bar.envelope.provider_id, bar.envelope.venue_id, str(bar.envelope.instrument_id),
             bar.interval, bar.start_at.isoformat(), bar.envelope.adjustment_basis]
    return hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Artifact:
    content_hash: str
    relative_path: str
    row_count: int
    min_event_at: datetime
    max_event_at: datetime
    venue_id: str


class ArtifactStore:
    def __init__(self, data_root: Path):
        self.root = data_root.resolve()

    def write_bars(self, bars: list[Bar]) -> Artifact:
        if not bars:
            raise ValueError("empty artifact")
        venue = bars[0].envelope.venue_id
        if not re.fullmatch(r"[A-Za-z0-9_-]+", venue) or any(b.envelope.venue_id != venue for b in bars):
            raise ValueError("invalid or mixed venue partition")
        year, month = bars[0].start_at.year, bars[0].start_at.month
        if any((b.start_at.year, b.start_at.month) != (year, month) for b in bars):
            raise ValueError("mixed month partition")
        directory = self.root / "lake" / "kind=Bar" / f"venue={venue}" / f"year={year}" / f"month={month:02}"
        directory.mkdir(parents=True, exist_ok=True)
        rows = [{"observation_id": str(b.envelope.observation_id), "instrument_id": str(b.envelope.instrument_id),
                 "event_at": b.end_at.isoformat(), "bar_json": b.model_dump_json()} for b in bars]
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, prefix=".staged-", suffix=".parquet", delete=False) as tmp:
                temp_path = Path(tmp.name)
            pq.write_table(pa.Table.from_pylist(rows), temp_path, compression="zstd")
            with temp_path.open("rb") as stream:
                content_hash = hashlib.file_digest(stream, "sha256").hexdigest()
                os.fsync(stream.fileno())
            final = directory / f"{content_hash}.parquet"
            if final.exists():
                if self.verify(final) != content_hash:
                    raise OSError("existing artifact hash mismatch")
                temp_path.unlink()
            else:
                os.replace(temp_path, final)
                if os.name != "nt":
                    fd = os.open(directory, os.O_RDONLY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
            return Artifact(content_hash, final.relative_to(self.root).as_posix(), len(bars),
                            min(b.end_at for b in bars), max(b.end_at for b in bars), venue)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    @staticmethod
    def verify(path: Path) -> str:
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    def read_bars(self, artifact: Artifact) -> list[Bar]:
        path = (self.root / artifact.relative_path).resolve()
        if not path.is_relative_to(self.root) or path.suffix != ".parquet":
            raise ValueError("artifact outside data root")
        if self.verify(path) != artifact.content_hash:
            raise OSError("artifact checksum mismatch")
        table = pq.read_table(path, columns=["bar_json"])
        if table.num_rows != artifact.row_count:
            raise OSError("artifact row count mismatch")
        return [Bar.model_validate_json(item) for item in table.column("bar_json").to_pylist()]


def visible_bars(bars: list[Bar], *, instrument_id: UUID, start: datetime, end: datetime,
                 as_of: datetime, adjustment_basis: str, provider_id: str | None = None) -> list[Bar]:
    """Strict replay: select latest *available* revision within the pinned manifest."""
    start, end, as_of = utc(start), utc(end), utc(as_of)
    if start >= end:
        raise ValueError("query interval must be nonempty")
    selected: dict[str, Bar] = {}
    for bar in bars:
        env = bar.envelope
        if (env.instrument_id != instrument_id or not start <= bar.start_at < end or
            env.adjustment_basis != adjustment_basis or provider_id is not None and env.provider_id != provider_id or
            env.quality_state not in ("valid", "corrected") or env.availability_basis == "unknown" or
            env.available_at is None or env.available_at > as_of):
            continue
        key = logical_key(bar)
        prior = selected.get(key)
        if prior is None or (env.available_at, env.ingested_at) > (prior.envelope.available_at, prior.envelope.ingested_at):
            selected[key] = bar
    return sorted(selected.values(), key=lambda b: (b.start_at, b.envelope.provider_id))


def filter_known_identity(bars: list[Bar], instruments: list[Instrument],
                          mappings: list[IdentifierMapping], as_of: datetime) -> list[Bar]:
    """Do not resolve an old candle through an identifier learned after cutoff."""
    cutoff = utc(as_of)
    identities = {item.instrument_id: item for item in instruments}
    result = []
    for bar in bars:
        env = bar.envelope
        instrument = identities.get(env.instrument_id)
        if instrument is None or not instrument.valid_from <= bar.start_at or (
            instrument.valid_to is not None and bar.start_at >= instrument.valid_to):
            continue
        if any(m.instrument_id == env.instrument_id and m.provider_id == env.provider_id
               and m.venue_id == env.venue_id and m.valid_from <= bar.start_at
               and (m.valid_to is None or bar.start_at < m.valid_to)
               and m.available_at is not None and m.available_at <= cutoff for m in mappings):
            result.append(bar)
    return result


@dataclass(frozen=True)
class IngestResult:
    manifest_id: UUID | None
    stored: int
    duplicates: int
    quarantined: int


class PostgresCatalog:
    def __init__(self, dsn: str, artifacts: ArtifactStore):
        self.dsn = dsn
        self.artifacts = artifacts

    def register_identity(self, venues: list[Venue], instruments: list[Instrument],
                          mappings: list[IdentifierMapping], sessions: list[CalendarSession] = ()) -> None:
        """Bootstrap verified identities only. Existing rows cannot be silently overwritten."""
        with connect(self.dsn) as connection:
            with connection.transaction():
                connection.execute("SELECT pg_advisory_xact_lock_shared(%s)", (837_241_904,))
                for venue in venues:
                    row = connection.execute("""INSERT INTO venues VALUES (%s,%s,%s,%s)
                        ON CONFLICT (venue_id) DO UPDATE SET document = EXCLUDED.document
                        WHERE venues.document = EXCLUDED.document RETURNING venue_id""",
                        (venue.venue_id, venue.timezone, venue.session_kind, Jsonb(venue.model_dump(mode="json")))).fetchone()
                    if not row:
                        raise ValueError("venue identifier conflicts with existing definition")
                for instrument in instruments:
                    row = connection.execute("""INSERT INTO instruments VALUES (%s,%s,%s,%s,%s)
                        ON CONFLICT (instrument_id) DO UPDATE SET document = EXCLUDED.document
                        WHERE instruments.document = EXCLUDED.document RETURNING instrument_id""",
                        (instrument.instrument_id, instrument.primary_venue_id, instrument.valid_from,
                         instrument.valid_to, Jsonb(instrument.model_dump(mode="json")))).fetchone()
                    if not row:
                        raise ValueError("instrument identifier conflicts with existing definition")
                for mapping in mappings:
                    row = connection.execute("""INSERT INTO identifier_mappings VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (mapping_id) DO UPDATE SET document = EXCLUDED.document
                        WHERE identifier_mappings.document = EXCLUDED.document RETURNING mapping_id""",
                        (mapping.mapping_id, mapping.instrument_id, mapping.provider_id, mapping.venue_id,
                         mapping.identifier_type, mapping.identifier_value, mapping.valid_from, mapping.valid_to,
                         mapping.available_at, Jsonb(mapping.model_dump(mode="json")))).fetchone()
                    if not row:
                        raise ValueError("mapping identifier conflicts with existing definition")
                for session in sessions:
                    row = connection.execute("""INSERT INTO calendar_sessions VALUES (%s,%s,%s,%s,%s)
                        ON CONFLICT (calendar_id,session_date,version) DO UPDATE SET document = EXCLUDED.document
                        WHERE calendar_sessions.document = EXCLUDED.document RETURNING calendar_id""",
                        (session.calendar_id, session.session_date, session.venue_id, session.version,
                         Jsonb(session.model_dump(mode="json")))).fetchone()
                    if not row:
                        raise ValueError("calendar session conflicts with existing definition")

    def load_identity(self) -> tuple[list[Instrument], list[IdentifierMapping]]:
        with connect(self.dsn) as connection:
            instruments = [Instrument.model_validate(row[0]) for row in connection.execute("SELECT document FROM instruments")]
            mappings = [IdentifierMapping.model_validate(row[0]) for row in connection.execute("SELECT document FROM identifier_mappings")]
        return instruments, mappings

    def load_calendar(self, venue_id: str, start: datetime, end: datetime,
                      calendar_id: str | None = None, version: str | None = None) -> SessionCalendar:
        with connect(self.dsn) as connection:
            row = connection.execute("SELECT document FROM venues WHERE venue_id = %s", (venue_id,)).fetchone()
            if not row:
                raise CalendarMissing("venue not registered")
            venue = Venue.model_validate(row[0])
            if venue.session_kind == "24x7":
                return SessionCalendar(venue, calendar_id or f"{venue_id}:utc_daily", version or "v1")
            first = (utc(start) - timedelta(days=2)).date()
            last = (utc(end) + timedelta(days=2)).date()
            sql = "SELECT document FROM calendar_sessions WHERE venue_id = %s AND session_date BETWEEN %s AND %s"
            params: list = [venue_id, first, last]
            if calendar_id is not None:
                sql += " AND calendar_id = %s"
                params.append(calendar_id)
            if version is not None:
                sql += " AND version = %s"
                params.append(version)
            rows = connection.execute(sql, params).fetchall()
        sessions = [CalendarSession.model_validate(row[0]) for row in rows]
        choices = {(s.calendar_id, s.version) for s in sessions}
        if len(choices) != 1:
            raise CalendarMissing("calendar identity or version missing/ambiguous")
        chosen_id, chosen_version = choices.pop()
        return SessionCalendar(venue, chosen_id, chosen_version, sessions)

    def ingest(self, bars: list[Bar], calendar: SessionCalendar, *, source_batch_id: UUID,
               provider_id: str, raw_hash: str, rights_policy_id: str = "hash_only",
               fetched_at: datetime) -> IngestResult:
        if not re.fullmatch(r"[a-f0-9]{64}", raw_hash):
            raise ValueError("raw_hash must be SHA-256")
        if any(b.envelope.source_batch_id != source_batch_id or b.envelope.provider_id != provider_id for b in bars):
            raise ValueError("batch identity mismatch")
        instruments, mappings = self.load_identity()
        accepted, rejected = [], []
        for bar in bars:
            codes = list(validate_bar(bar, calendar))
            if not filter_known_identity([bar], instruments, mappings, fetched_at):
                codes.append("IDENTITY_MAPPING_UNKNOWN")
            (rejected if codes else accepted).append((bar, codes))
        duplicates = 0
        manifest_id: UUID | None = None
        with connect(self.dsn) as connection:
            with connection.transaction():
                connection.execute("SELECT pg_advisory_xact_lock_shared(%s)", (837_241_904,))
                head = connection.execute("SELECT manifest_id FROM dataset_head WHERE singleton = true FOR UPDATE").fetchone()
                if head is None:
                    raise RuntimeError("database is not migrated")
                connection.execute("INSERT INTO source_batches VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                                   (source_batch_id, provider_id, utc(fetched_at), raw_hash, "hash_only", rights_policy_id, "processed"))
                for bar, codes in rejected:
                    connection.execute("INSERT INTO quarantine VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                       (uuid4(), source_batch_id, provider_id, bar.envelope.instrument_id,
                                        list(codes), bar.envelope.raw_content_hash, utc(fetched_at)))
                fresh: list[Bar] = []
                seen = set()
                seen_keys: set[str] = set()
                catalog_revisions: dict[UUID, int] = {}
                for bar, _ in accepted:
                    signature = fingerprint(bar)
                    if signature in seen or connection.execute("SELECT 1 FROM observations WHERE fingerprint = %s", (signature,)).fetchone():
                        duplicates += 1
                        continue
                    seen.add(signature)
                    key = logical_key(bar)
                    if key in seen_keys:
                        connection.execute("INSERT INTO quarantine VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                           (uuid4(), source_batch_id, provider_id, bar.envelope.instrument_id,
                                            ["CONFLICTING_BATCH_DUPLICATE"], bar.envelope.raw_content_hash, utc(fetched_at)))
                        rejected.append((bar, ("CONFLICTING_BATCH_DUPLICATE",)))
                        continue
                    seen_keys.add(key)
                    previous = connection.execute("SELECT observation_id, revision, available_at FROM observations WHERE logical_key = %s ORDER BY revision DESC LIMIT 1", (key,)).fetchone()
                    if previous:
                        previous_at = previous[2]
                        current_at = bar.envelope.available_at
                        if previous_at is not None and (current_at is None or current_at < previous_at):
                            connection.execute("INSERT INTO quarantine VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                               (uuid4(), source_batch_id, provider_id, bar.envelope.instrument_id,
                                                ["CORRECTION_AVAILABILITY_REGRESSION"], bar.envelope.raw_content_hash, utc(fetched_at)))
                            rejected.append((bar, ("CORRECTION_AVAILABILITY_REGRESSION",)))
                            continue
                        env = bar.envelope.model_copy(update={"supersedes_observation_id": previous[0],
                                                               "quality_state": "corrected"})
                        bar = bar.model_copy(update={"envelope": env})
                    catalog_revisions[bar.envelope.observation_id] = previous[1] + 1 if previous else 1
                    fresh.append(bar)
                if fresh:
                    manifest_id = uuid4()
                    connection.execute("INSERT INTO dataset_manifests VALUES (%s,%s,%s,%s,%s,%s)",
                                       (manifest_id, head[0], utc(fetched_at), "1.0.0-draft", "all_providers_v1", "committed"))
                    # Keep files moderately sized and partitioned by venue/month.
                    partitions: dict[tuple[str, int, int], list[Bar]] = {}
                    for bar in fresh:
                        partitions.setdefault((bar.envelope.venue_id, bar.start_at.year, bar.start_at.month), []).append(bar)
                    for group in partitions.values():
                        artifact = self.artifacts.write_bars(group)
                        connection.execute("INSERT INTO dataset_files VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                                           (artifact.content_hash, artifact.relative_path, artifact.row_count, "Bar", artifact.venue_id,
                                            artifact.min_event_at, artifact.max_event_at, "1.0.0-draft", rights_policy_id))
                        connection.execute("INSERT INTO manifest_members VALUES (%s,%s)", (manifest_id, artifact.content_hash))
                        for bar in group:
                            env = bar.envelope
                            connection.execute("""INSERT INTO observations
                                (observation_id,fingerprint,logical_key,revision,supersedes_observation_id,
                                 instrument_id,venue_id,provider_id,interval,start_at,end_at,session_date,
                                 adjustment_basis,available_at,availability_basis,quality_state,source_batch_id,
                                 content_hash,manifest_id)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                                               (env.observation_id, fingerprint(bar), logical_key(bar), catalog_revisions[env.observation_id],
                                                env.supersedes_observation_id, env.instrument_id, env.venue_id, env.provider_id,
                                                bar.interval, bar.start_at, bar.end_at, bar.session_date,
                                                env.adjustment_basis, env.available_at, env.availability_basis, env.quality_state,
                                                source_batch_id, artifact.content_hash, manifest_id))
                    connection.execute("UPDATE dataset_head SET manifest_id = %s WHERE singleton = true", (manifest_id,))
                    connection.execute("INSERT INTO outbox VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL)",
                                       (uuid4(), "market.dataset.published.v1", "1.0.0-draft", utc(fetched_at),
                                        utc(fetched_at), str(manifest_id), uuid4(), f"manifest:{manifest_id}", str(manifest_id)))
        return IngestResult(manifest_id, len(fresh), duplicates, len(rejected))

    def head(self) -> UUID | None:
        with connect(self.dsn) as connection:
            row = connection.execute("SELECT manifest_id FROM dataset_head WHERE singleton = true").fetchone()
        return row[0] if row else None

    def scan_storage(self) -> dict:
        """Read-only crash recovery inventory; never deletes unreferenced files."""
        with connect(self.dsn) as connection:
            rows = connection.execute("SELECT relative_path, content_hash FROM dataset_files").fetchall()
        expected = {path: digest for path, digest in rows}
        lake = self.artifacts.root / "lake"
        actual = {path.relative_to(self.artifacts.root).as_posix(): path for path in lake.rglob("*.parquet")} if lake.exists() else {}
        staged = [path for path in lake.rglob(".staged-*")] if lake.exists() else []
        return {"referenced": len(expected), "unreferenced": sorted(set(actual) - set(expected)),
                "missing": sorted(set(expected) - set(actual)),
                "corrupt": sorted(path for path in set(expected) & set(actual)
                                  if self.artifacts.verify(actual[path]) != expected[path]),
                "staged_count": len(staged), "deletion_performed": False}

    def artifacts_for(self, manifest_id: UUID) -> list[Artifact]:
        with connect(self.dsn) as connection:
            present = connection.execute("SELECT 1 FROM dataset_manifests WHERE manifest_id = %s", (manifest_id,)).fetchone()
            if not present:
                raise KeyError("manifest not found")
            rows = connection.execute("""WITH RECURSIVE chain AS (
                SELECT manifest_id, parent_manifest_id FROM dataset_manifests WHERE manifest_id = %s
                UNION ALL SELECT m.manifest_id, m.parent_manifest_id FROM dataset_manifests m
                JOIN chain ON chain.parent_manifest_id = m.manifest_id)
                SELECT DISTINCT f.content_hash, f.relative_path, f.row_count, f.min_event_at, f.max_event_at, f.venue_id
                FROM chain JOIN manifest_members mm USING (manifest_id)
                JOIN dataset_files f USING (content_hash) ORDER BY f.relative_path""", (manifest_id,)).fetchall()
        return [Artifact(*row) for row in rows]

    def bars(self, *, instrument_id: UUID, start: datetime, end: datetime, as_of: datetime,
             adjustment_basis: str = "raw", provider_id: str | None = None,
             manifest_id: UUID | None = None) -> tuple[UUID | None, list[Bar]]:
        pinned = manifest_id or self.head()
        if pinned is None:
            return None, []
        all_bars = []
        for artifact in self.artifacts_for(pinned):
            if artifact.min_event_at <= end and artifact.max_event_at > start:
                all_bars.extend(self.artifacts.read_bars(artifact))
        visible = visible_bars(all_bars, instrument_id=instrument_id, start=start, end=end,
                               as_of=as_of, adjustment_basis=adjustment_basis, provider_id=provider_id)
        instruments, mappings = self.load_identity()
        return pinned, filter_known_identity(visible, instruments, mappings, as_of)
