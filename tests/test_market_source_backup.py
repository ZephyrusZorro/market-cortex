"""Populated synthetic recovery tests, no owner connection or real credentials."""
import io
import json
import tarfile

import pytest

from market_cortex.backup import encrypt_file
from market_cortex.market_archive import MarketArchive
from market_cortex.market_source_backup import export_source, restore_source, inventory
from market_cortex.providers import ProviderFailure

KEY = 'synthetic-test-source-passphrase-only'


@pytest.fixture
def source(tmp_path):
    archive = MarketArchive(tmp_path / 'source', initialize=True, maximum_bytes=1024 * 1024)
    archive.append('catalog', 'binance', [{'symbol': 'BTCUSDT', 'present': True}], sources=[])
    archive.append('candles', 'binance', [{'synthetic': True, 'close': '12.34'}], sources=[])
    archive.append('events', 'binance', [{'synthetic': True, 'price': '12.35'}], sources=[])
    return archive


def test_full_recovery_preserves_bytes_lineage_and_source(source, tmp_path, monkeypatch):
    def forbidden(*a, **kw):
        raise AssertionError('SQL must never be called')
    monkeypatch.setattr('market_cortex.backup.connect', forbidden)
    before = inventory(source)
    bundle = tmp_path / 'retained.mcsourcebackup'
    exported = export_source(source.root, bundle, KEY)
    restored = restore_source(bundle, tmp_path / 'restored', KEY)
    assert restored['status'] == 'VALIDATED_ENCRYPTED_SOURCE_RESTORE'
    assert restored['manifest_hashes'] == exported['manifest_hashes']
    assert inventory(MarketArchive(tmp_path / 'restored')) == before == inventory(source)
    assert bundle.exists() and not restored['collector_started']


@pytest.mark.parametrize('bad', ['wrong_phrase', 'tamper'])
def test_authentication_failure_creates_no_recovery_root(source, tmp_path, bad):
    bundle = tmp_path / 'retained.mcsourcebackup'
    export_source(source.root, bundle, KEY)
    if bad == 'tamper':
        payload = bundle.read_bytes()
        bundle.write_bytes(payload[:-1] + bytes([payload[-1] ^ 1]))
    with pytest.raises(ValueError, match='authentication failed'):
        restore_source(bundle, tmp_path / 'rejected', KEY if bad == 'tamper' else KEY + '!')
    assert not (tmp_path / 'rejected').exists() and bundle.exists()


def test_exclusive_backup_and_restore_never_overwrite(source, tmp_path):
    bundle = tmp_path / 'retained.mcsourcebackup'
    export_source(source.root, bundle, KEY)
    original = bundle.read_bytes()
    with pytest.raises(ProviderFailure, match='NEW_SOURCE_BACKUP_REQUIRED'):
        export_source(source.root, bundle, KEY)
    restore_source(bundle, tmp_path / 'restored', KEY)
    with pytest.raises(ProviderFailure, match='NEW_SOURCE_RESTORE_ROOT_REQUIRED'):
        restore_source(bundle, tmp_path / 'restored', KEY)
    assert original == bundle.read_bytes()


@pytest.mark.parametrize('name,kind', [
    ('source/../escape.json', 'file'), ('source//artifacts/a.parquet', 'file'),
    ('source/market-archive.json', 'link'), ('source/unknown-secret.json', 'file'),
])
def test_authenticated_unsafe_tar_rejected_before_destination(tmp_path, name, kind):
    plain = tmp_path / 'malicious.tar'
    with tarfile.open(plain, 'w') as tar:
        member = tarfile.TarInfo(name)
        if kind == 'link':
            member.type = tarfile.SYMTYPE
            member.linkname = '../../escape'
            tar.addfile(member)
        else:
            member.size = 2
            tar.addfile(member, io.BytesIO(b'{}'))
    encrypted = tmp_path / 'retained.mcsourcebackup'
    encrypt_file(plain, encrypted, KEY)
    with pytest.raises(ProviderFailure, match='SOURCE_UNSAFE_BACKUP_MEMBER'):
        restore_source(encrypted, tmp_path / 'rejected', KEY)
    assert not (tmp_path / 'rejected').exists()


def test_active_writer_collector_and_unknown_file_block_export(source, tmp_path):
    with source.writer():
        with pytest.raises(ProviderFailure, match='ARCHIVE_WRITER_BUSY'):
            export_source(source.root, tmp_path / 'writer.mcsourcebackup', KEY)
    for name in ('.collector-binance.lock', 'private-secret.txt'):
        (source.root / name).write_text('synthetic')
        with pytest.raises(ProviderFailure, match='SOURCE_UNEXPECTED_FILE_OR_ACTIVE_COLLECTOR'):
            export_source(source.root, tmp_path / 'blocked.mcsourcebackup', KEY)
        (source.root / name).unlink()
    assert not (tmp_path / 'blocked.mcsourcebackup').exists()


def test_historical_connected_checkpoints_retained_only_after_finite_stop(source, tmp_path):
    folder = source.root / 'collector' / 'binance'
    folder.mkdir(parents=True)
    for name, at, connected in [('a', '2026-10-14T12:00:00Z', True),
                                 ('b', '2026-10-14T12:02:00Z', False)]:
        (folder / (name + '.json')).write_text(json.dumps({
            'provider': 'binance', 'updated_at': at, 'stats': {'connected': connected}}))
    bundle = tmp_path / 'finite.mcsourcebackup'
    export_source(source.root, bundle, KEY)
    restore_source(bundle, tmp_path / 'restored', KEY)
    assert inventory(source) == inventory(MarketArchive(tmp_path / 'restored'))
    (folder / 'c.json').write_text(json.dumps({'provider': 'binance',
        'updated_at': '2026-10-14T12:03:00Z', 'stats': {'connected': True}}))
    with pytest.raises(ProviderFailure, match='SOURCE_ACTIVE_CHECKPOINT'):
        export_source(source.root, tmp_path / 'active.mcsourcebackup', KEY)


def test_protected_lake_cannot_be_recovery_target(source, tmp_path):
    bundle = tmp_path / 'retained.mcsourcebackup'
    export_source(source.root, bundle, KEY)
    protected = tmp_path / 'protected'
    (protected / 'lake').mkdir(parents=True)
    with pytest.raises(ProviderFailure, match='PROTECTED_MARKET_LAKE'):
        restore_source(bundle, protected / 'target', KEY)
