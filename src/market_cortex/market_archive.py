"""Independent source evidence. Never opens a database or the owner data lake.

Discovery identities are provider-native evidence, not canonical instruments.
Catalog and candle snapshots can be reviewed before an approved catalog import.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .providers import ProviderFailure


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def link_path(path: Path):
    """CreateHardLinkW needs explicit long paths on some Windows installations."""
    absolute = str(path.resolve())
    if os.name != 'nt' or absolute.startswith('\\\\?\\'):
        return absolute
    return '\\\\?\\UNC\\' + absolute[2:] if absolute.startswith('\\\\') else '\\\\?\\' + absolute


def publish(directory: Path, payload: bytes, suffix: str, *, prefix=''):
    """Exclusive publication; existing evidence is verified, never overwritten."""
    directory.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(payload).hexdigest()
    target = directory / (prefix + key + suffix)
    target_io = Path(link_path(target))
    if target_io.exists():
        if hashlib.sha256(target_io.read_bytes()).hexdigest() != key:
            raise ProviderFailure('ARCHIVE_HASH_MISMATCH')
        return target
    with tempfile.NamedTemporaryFile(dir=link_path(directory), prefix='.staged-', delete=False) as stream:
        staged = Path(stream.name)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        try:
            os.link(link_path(staged), link_path(target))
        except FileExistsError:
            if hashlib.sha256(target_io.read_bytes()).hexdigest() != key:
                raise ProviderFailure('ARCHIVE_HASH_MISMATCH')
    finally:
        staged.unlink(missing_ok=True)
    return target


class MarketArchive:
    PURPOSE = 'INDEPENDENT_MARKET_DATA_TEST'

    def __init__(self, root: Path, *, initialize=False, maximum_bytes=None):
        if maximum_bytes is not None and (type(maximum_bytes) is not int or maximum_bytes<1024):
            raise ProviderFailure('INVALID_ARCHIVE_DISK_BUDGET')
        self.root = root.resolve()
        # Existing owner, pilot and recovery lakes cannot be reused accidentally.
        if any((p / 'lake').exists() for p in (self.root, *self.root.parents)):
            raise ProviderFailure('PROTECTED_MARKET_LAKE')
        if self.root == Path('C:/MarketCortexData').resolve() or any(
                name.lower().startswith(('owner-', 'binance_pilot')) for name in self.root.parts):
            raise ProviderFailure('PROTECTED_DATA_ROOT')
        marker = self.root / 'market-archive.json'
        if initialize and not marker.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            if any(self.root.iterdir()):
                raise ProviderFailure('ARCHIVE_ROOT_NOT_EMPTY')
            with marker.open('x', encoding='utf-8') as stream:
                json.dump({'purpose': self.PURPOSE, 'created_at': stamp(),
                           **({'maximum_bytes':maximum_bytes} if maximum_bytes is not None else {})}, stream)
        config = json.loads(marker.read_text()) if marker.exists() else {}
        if config.get('purpose') != self.PURPOSE:
            raise ProviderFailure('INDEPENDENT_ARCHIVE_REQUIRED')
        retained_budget = config.get('maximum_bytes')
        if retained_budget is not None and (type(retained_budget) is not int or retained_budget<1024):
            raise ProviderFailure('INVALID_ARCHIVE_DISK_BUDGET')
        budgets = [n for n in (retained_budget,maximum_bytes) if n is not None]
        self.maximum_bytes = min(budgets) if budgets else None
        self._legacy = None

    def assert_capacity(self, additional_bytes):
        if self.maximum_bytes is not None:
            used = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())
            if used+additional_bytes > self.maximum_bytes:
                raise ProviderFailure('ARCHIVE_DISK_BUDGET_EXCEEDED')

    @contextmanager
    def writer(self):
        path = self.root / '.writer.lock'
        try:
            stream = path.open('x', encoding='ascii')
        except FileExistsError:
            raise ProviderFailure('ARCHIVE_WRITER_BUSY', retryable=True) from None
        try:
            with stream:
                stream.write(str(os.getpid()))
                stream.flush()
            yield
        finally:
            path.unlink(missing_ok=True)

    def manifests(self, kind=None, provider=None, as_of=None):
        values = []
        base = self.root / 'manifests'
        paths = list(base.glob('*.json'))
        paths.extend((base / kind / provider).glob('*.json') if kind and provider else
                     (base / kind).rglob('*.json') if kind else base.glob('*/*/*.json'))
        for path in paths:
            raw = path.read_bytes()
            hash_ = path.stem.rsplit('-',1)[-1]
            if hashlib.sha256(raw).hexdigest() != hash_:
                raise ProviderFailure('MANIFEST_HASH_MISMATCH')
            item = json.loads(raw)
            if ((kind is None or item['kind'] == kind) and
                    (provider is None or item['provider'] == provider) and
                    (as_of is None or datetime.fromisoformat(item['observed_at']) <= as_of)):
                values.append({**item, 'manifest_hash': hash_})
        return sorted(values, key=lambda item: (item['observed_at'], item.get('sequence',0), item['manifest_hash']))

    def last_manifest(self, kind, provider):
        if self._legacy is None:
            self._legacy = {}
            for path in (self.root/'manifests').glob('*.json'):
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest()!=path.stem:
                    raise ProviderFailure('MANIFEST_HASH_MISMATCH')
                item=json.loads(raw)
                key=(item['kind'],item['provider'])
                candidate={**item,'manifest_hash':path.stem}
                old=self._legacy.get(key)
                if not old or (item['observed_at'],item.get('sequence',0))>(old['observed_at'],old.get('sequence',0)):
                    self._legacy[key]=candidate
        files=list((self.root/'manifests'/kind/provider).glob('*.json'))
        if files:
            path=max(files)
            raw=path.read_bytes();hash_=path.stem.rsplit('-',1)[-1]
            if hashlib.sha256(raw).hexdigest()!=hash_:
                raise ProviderFailure('MANIFEST_HASH_MISMATCH')
            return {**json.loads(raw),'manifest_hash':hash_}
        return self._legacy.get((kind,provider))

    def rows(self, manifest):
        path = self.artifact_path(manifest)
        table = pq.ParquetFile(path).read(columns=['record_json'])
        if table.num_rows != manifest['rows']:
            raise ProviderFailure('ARTIFACT_ROW_COUNT_MISMATCH')
        return [json.loads(r) for r in table.column('record_json').to_pylist()]

    def artifact_path(self, manifest):
        path = (self.root / manifest['artifact']).resolve()
        if not path.is_relative_to(self.root) or path.suffix != '.parquet':
            raise ProviderFailure('ARTIFACT_PATH_FORBIDDEN')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['artifact_hash']:
            raise ProviderFailure('ARTIFACT_HASH_MISMATCH')
        return path

    def latest(self, kind, provider, *, as_of=None):
        if as_of is None:
            manifest=self.last_manifest(kind,provider)
            return (manifest,self.rows(manifest)) if manifest else (None,[])
        manifests = self.manifests(kind, provider, as_of)
        return (manifests[-1], self.rows(manifests[-1])) if manifests else (None, [])

    def append(self, kind, provider, records, *, sources, metadata=None, observed_at=None):
        if kind not in {'catalog', 'candles', 'events', 'gaps', 'requests'} or provider not in {'binance', 'upstox', 'alpaca'}:
            raise ProviderFailure('INVALID_ARCHIVE_PARTITION')
        with self.writer():
            last = self.last_manifest(kind,provider)
            previous = last['manifest_hash'] if last else None
            observed = observed_at or stamp()
            if last and datetime.fromisoformat(observed) < datetime.fromisoformat(last['observed_at']):
                raise ProviderFailure('ARCHIVE_CLOCK_BEFORE_LAST_CAPTURE')
            columns = ['market','symbol','native_id','name','exchange','status','isin'] if kind == 'catalog' else []
            schema = [('record_json',pa.string()), *[(k,pa.string()) for k in columns]]
            if kind == 'catalog':
                schema.append(('present',pa.bool_()))
            serialized = []
            for r in records:
                item = {'record_json':encoded(r).decode(), **{k:r.get(k) for k in columns}}
                if kind == 'catalog':
                    item['present'] = r['present']
                serialized.append(item)
            table = pa.Table.from_pylist(serialized,schema=pa.schema(schema))
            sink = pa.BufferOutputStream()
            pq.write_table(table, sink, compression='zstd')
            payload = sink.getvalue().to_pybytes()
            artifact_hash = hashlib.sha256(payload).hexdigest()
            artifact_path = self.root/'artifacts'/(artifact_hash+'.parquet')
            item = {'version': 'market_source_v1', 'purpose': self.PURPOSE, 'kind': kind,
                    'provider': provider, 'observed_at': observed, 'parent': previous, 'sequence':last.get('sequence',0)+1 if last else 1,
                    'artifact': artifact_path.relative_to(self.root).as_posix(), 'artifact_hash': artifact_hash,
                    'rows': len(records), 'sources': sources, 'metadata': metadata or {}}
            manifest_payload = encoded(item)
            added = 0 if artifact_path.exists() else len(payload)
            # Include staged publication headroom; refuse before publishing any
            # part of the operation. No automatic cleanup of retained evidence.
            self.assert_capacity(added+len(manifest_payload)+max(added,len(manifest_payload)))
            publish(self.root/'artifacts',payload,'.parquet')
            manifest = publish(self.root / 'manifests' / kind / provider, manifest_payload, '.json',prefix=f"{item['sequence']:012d}-")
            return {**item, 'manifest_hash': manifest.stem.rsplit('-',1)[-1]}

    def integrity(self):
        manifests = self.manifests()
        known = set()
        for item in manifests:
            if item['parent'] and item['parent'] not in known:
                raise ProviderFailure('ARCHIVE_PARENT_MISSING_OR_OUT_OF_ORDER')
            self.rows(item)
            known.add(item['manifest_hash'])
        artifacts = list((self.root / 'artifacts').glob('*.parquet'))
        return {'status': 'VALIDATED', 'manifests': len(manifests), 'artifacts': len(artifacts),
                'bytes': sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file()),
                'database_access': False, 'owner_writes': False}
