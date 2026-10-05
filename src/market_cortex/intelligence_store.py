"""Append-only contextual facts in the existing catalog and immutable Parquet lake."""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from uuid import UUID, NAMESPACE_URL, uuid5

import pyarrow as pa
import pyarrow.parquet as pq
from psycopg.types.json import Jsonb

from .database import connect
from .storage import Artifact
from .intelligence_contracts import FACTS, ContextSnapshot


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str, allow_nan=False).encode()).hexdigest()


def visible(facts, cutoff, instrument_id=None):
    """Period and event dates never establish knowledge; recorded arrivals do."""
    selected = {}
    for f in facts:
        e = f.envelope
        if (e.available_at is None or max(e.available_at, e.ingested_at) > cutoff or
            (e.published_at and e.published_at > cutoff) or e.quality_state == 'quarantined' or
            (f.domain == 'derivatives' and (f.contract.known_at > cutoff or e.event_at > cutoff))):
            continue
        if instrument_id and not (f.entity.kind in ('region', 'series') or
            f.entity.key == str(instrument_id) or instrument_id in f.related_instrument_ids or
            (f.domain == 'derivatives' and f.contract.underlying_instrument_id == instrument_id)):
            continue
        key = (e.provider_id, f.logical_key)
        if key not in selected or (f.revision_number, e.ingested_at, str(e.observation_id)) > (
                selected[key].revision_number, selected[key].envelope.ingested_at, str(selected[key].envelope.observation_id)):
            selected[key] = f
    return sorted(selected.values(), key=lambda f: (f.envelope.event_at, str(f.envelope.observation_id)))


def semantic_hash(f):
    p = f.model_dump(mode='json')
    for name in ('revision_number', 'revised_at'):
        p.pop(name, None)
    for name in ('observation_id', 'ingested_at', 'available_at', 'source_batch_id', 'raw_content_hash',
                 'supersedes_observation_id', 'revision'):
        p['envelope'].pop(name, None)
    if f.domain == 'derivatives':
        p['contract'].pop('known_at')
        p['contract'].pop('metadata_observed_at', None)
        p['contract'].pop('metadata_raw_hash', None)
    return digest(p)


class ContextStore:
    def __init__(self, catalog):
        self.catalog = catalog
        self.dsn = catalog.dsn

    def append(self, facts):
        if not facts or len(facts) > 10000:
            raise ValueError('CONTEXT_BATCH_SIZE')
        now = datetime.now(timezone.utc)
        from psycopg.conninfo import conninfo_to_dict
        if any(f.classification_scope == 'SYNTHETIC_TEST' for f in facts) and not conninfo_to_dict(self.dsn).get('dbname', '').endswith('_test'):
            raise ValueError('SYNTHETIC_CONTEXT_REQUIRES_TEST_DATABASE')
        with connect(self.dsn) as c:
            # Same backup exclusion lock as foundation publication.
            c.execute('SELECT pg_advisory_xact_lock_shared(%s)', (837241904,))
            c.execute('SELECT pg_advisory_xact_lock(%s)', (837241909,))
            head = c.execute('SELECT manifest_id FROM context_head WHERE singleton=true').fetchone()
            parent = head[0] if head else None
            fresh = []
            for original in facts:
                f = FACTS.validate_python(original.model_dump())
                if f.envelope.ingested_at > now:
                    raise ValueError('FUTURE_INGESTION')
                row = c.execute('SELECT revision,semantic_hash,payload FROM context_facts WHERE provider=%s AND logical_key=%s ORDER BY revision DESC LIMIT 1',
                                (f.envelope.provider_id, f.logical_key)).fetchone()
                sh = semantic_hash(f)
                if row and row[1] == sh:
                    continue
                p = f.model_dump(mode='json')
                if row:
                    p['revision_number'] = row[0] + 1
                    p['revised_at'] = now.isoformat()
                    p['envelope']['supersedes_observation_id'] = row[2]['envelope']['observation_id']
                    p['envelope']['revision'] = str(p['revision_number'])
                f = FACTS.validate_python(p)
                value_hash = digest(f.model_dump(mode='json'))
                c.execute('INSERT INTO context_facts VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                          (f.envelope.observation_id, f.logical_key, f.envelope.provider_id, f.domain, f.entity.key,
                           f.revision_number, f.envelope.available_at, f.envelope.ingested_at, now, value_hash, sh,
                           Jsonb(f.model_dump(mode='json'))))
                fresh.append(f)
            if not fresh:
                return {'manifest_id': str(parent) if parent else None, 'inserted': 0, 'duplicates': len(facts)}
            artifact = self._write(fresh)
            c.execute('INSERT INTO context_files VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                      (artifact.content_hash, artifact.relative_path, artifact.row_count,
                       artifact.min_event_at, artifact.max_event_at, artifact.venue_id))
            ids = [str(f.envelope.observation_id) for f in fresh]
            if parent:
                ids += [str(r[0]) for r in c.execute('SELECT fact_id FROM context_manifest_facts WHERE manifest_id=%s', (parent,)).fetchall()]
            p = {'schema_version': 'context_manifest_v1', 'parent_manifest_id': str(parent) if parent else None,
                 'fact_ids': sorted(ids), 'new_artifact_hash': artifact.content_hash,
                 'created_at': now.isoformat(), 'normalizer_versions': sorted({f.envelope.normalizer_version for f in fresh})}
            h = digest(p)
            key = uuid5(NAMESPACE_URL, 'context-manifest:' + h)
            c.execute('INSERT INTO context_manifests VALUES (%s,%s,%s,%s,%s)', (key, parent, now, h, Jsonb(p)))
            for fid in ids:
                c.execute('INSERT INTO context_manifest_facts VALUES (%s,%s)', (key, UUID(fid)))
            if parent:
                c.execute('INSERT INTO context_manifest_files SELECT %s,content_hash FROM context_manifest_files WHERE manifest_id=%s', (key, parent))
            c.execute('INSERT INTO context_manifest_files VALUES (%s,%s) ON CONFLICT DO NOTHING', (key, artifact.content_hash))
            c.execute('INSERT INTO context_head VALUES (true,%s) ON CONFLICT(singleton) DO UPDATE SET manifest_id=excluded.manifest_id', (key,))
        return {'manifest_id': str(key), 'inserted': len(fresh), 'duplicates': len(facts)-len(fresh),
                'artifact_hash': artifact.content_hash}

    def _write(self, facts):
        directory = self.catalog.artifacts.root / 'lake' / 'kind=ContextFact'
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=directory, prefix='.staged-', suffix='.parquet', delete=False) as f:
            from pathlib import Path
            path = Path(f.name)
        try:
            rows = [{'fact_id': str(f.envelope.observation_id), 'domain': f.domain,
                     'available_at': f.envelope.available_at.isoformat() if f.envelope.available_at else None,
                     'fact_json': f.model_dump_json()} for f in sorted(facts, key=lambda f: str(f.envelope.observation_id))]
            pq.write_table(pa.Table.from_pylist(rows), path, compression='zstd')
            with path.open('r+b') as stream:
                h = hashlib.file_digest(stream, 'sha256').hexdigest()
                os.fsync(stream.fileno())
            target = directory / (h + '.parquet')
            if target.exists():
                if self.catalog.artifacts.verify(target) != h:
                    raise ValueError('CONTEXT_FILE_HASH_MISMATCH')
            else:
                os.replace(path, target)
            return Artifact(h, target.relative_to(self.catalog.artifacts.root).as_posix(), len(facts),
                            min(f.envelope.event_at for f in facts), max(f.envelope.event_at for f in facts), 'CONTEXT')
        finally:
            path.unlink(missing_ok=True)

    def resolve(self, as_of, manifest_id=None):
        with connect(self.dsn) as c:
            if manifest_id:
                row = c.execute('SELECT manifest_id,created_at,payload,content_hash FROM context_manifests WHERE manifest_id=%s', (manifest_id,)).fetchone()
                if not row or row[1] > as_of:
                    raise LookupError('CONTEXT_MANIFEST_NOT_VISIBLE')
            else:
                row = c.execute('SELECT manifest_id,created_at,payload,content_hash FROM context_manifests WHERE created_at<=%s ORDER BY created_at DESC LIMIT 1', (as_of,)).fetchone()
            if row and digest(row[2]) != row[3]:
                raise ValueError('CONTEXT_MANIFEST_HASH_MISMATCH')
        return row[0] if row else None

    def facts(self, manifest_id, as_of, instrument_id=None):
        if manifest_id is None:
            return []
        self.resolve(as_of, manifest_id)
        with connect(self.dsn) as c:
            rows = c.execute('SELECT f.payload,f.content_hash FROM context_facts f JOIN context_manifest_facts m USING(fact_id) WHERE m.manifest_id=%s AND f.recorded_at<=%s', (manifest_id, as_of)).fetchall()
        for p, h in rows:
            if digest(p) != h:
                raise ValueError('CONTEXT_FACT_HASH_MISMATCH')
        return visible([FACTS.validate_python(p) for p, _ in rows], as_of, instrument_id)

    def inspect(self, fact_id, as_of):
        with connect(self.dsn) as c:
            rows = c.execute('SELECT payload,content_hash FROM context_facts WHERE fact_id=%s AND recorded_at<=%s', (fact_id, as_of)).fetchall()
        if not rows or not visible([FACTS.validate_python(rows[0][0])], as_of):
            raise LookupError('CONTEXT_FACT_NOT_VISIBLE')
        if digest(rows[0][0]) != rows[0][1]:
            raise ValueError('CONTEXT_FACT_HASH_MISMATCH')
        return rows[0][0]

    def freeze(self, as_of):
        """Freeze all recorded revisions, not just the values latest at source capture."""
        key = self.resolve(as_of)
        if key is None:
            return {'manifest_id': None, 'created_at': None, 'facts': [], 'recorded_at': {},
                    'manifest_times': {}, 'policy': 'AS_RECORDED_ONLY'}
        with connect(self.dsn) as c:
            rows = c.execute('SELECT f.fact_id,f.payload,f.content_hash,f.recorded_at FROM context_facts f JOIN context_manifest_facts m USING(fact_id) WHERE m.manifest_id=%s AND f.recorded_at<=%s ORDER BY f.fact_id', (key, as_of)).fetchall()
            chain = c.execute('''WITH RECURSIVE chain AS (
                SELECT manifest_id,parent_manifest_id,created_at,payload,content_hash FROM context_manifests WHERE manifest_id=%s
                UNION ALL SELECT m.manifest_id,m.parent_manifest_id,m.created_at,m.payload,m.content_hash
                FROM context_manifests m JOIN chain ON m.manifest_id=chain.parent_manifest_id)
                SELECT manifest_id,created_at,payload,content_hash FROM chain''', (key,)).fetchall()
        for _, payload, value_hash, _ in rows:
            if digest(payload) != value_hash:
                raise ValueError('CONTEXT_FACT_HASH_MISMATCH')
            FACTS.validate_python(payload)
        for _, _, payload, value_hash in chain:
            if digest(payload) != value_hash:
                raise ValueError('CONTEXT_MANIFEST_HASH_MISMATCH')
        return {'manifest_id': str(key), 'created_at': next(at.isoformat() for mid, at, _, _ in chain if mid == key),
                'facts': [p for _, p, _, _ in rows], 'recorded_at': {str(fid): at.isoformat() for fid, _, _, at in rows},
                'manifest_times': {str(mid): at.isoformat() for mid, at, _, _ in chain}, 'policy': 'AS_RECORDED_ONLY'}

    def save_snapshot(self, snapshot):
        p = snapshot.model_dump(mode='json')
        with connect(self.dsn) as c:
            c.execute('INSERT INTO context_snapshots VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                      (snapshot.snapshot_id, snapshot.content_hash, datetime.now(timezone.utc), Jsonb(p)))
            stored = c.execute('SELECT payload FROM context_snapshots WHERE snapshot_id=%s', (snapshot.snapshot_id,)).fetchone()[0]
            if stored != p:
                raise ValueError('IMMUTABLE_CONTEXT_SNAPSHOT_CONFLICT')
        return snapshot

    def snapshot(self, key):
        with connect(self.dsn) as c:
            row = c.execute('SELECT payload FROM context_snapshots WHERE snapshot_id=%s', (key,)).fetchone()
        if not row:
            raise LookupError('CONTEXT_SNAPSHOT_NOT_FOUND')
        result = ContextSnapshot.model_validate(row[0])
        core = {k: v for k, v in row[0].items() if k not in ('snapshot_id', 'content_hash')}
        if digest(core) != result.content_hash:
            raise ValueError('CONTEXT_SNAPSHOT_HASH_MISMATCH')
        return result

    def artifacts(self):
        with connect(self.dsn) as c:
            rows = c.execute('SELECT content_hash,relative_path,row_count,min_event_at,max_event_at,venue_id FROM context_files ORDER BY relative_path').fetchall()
        return [Artifact(*r) for r in rows]
