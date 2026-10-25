"""Authenticated, exclusive source-cache export/recovery. No SQL or network calls.

The original independent evidence marker is retained byte-for-byte. Collector
locks and active checkpoints block a snapshot; recovery cannot activate a feed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from .backup import decrypt_file, encrypt_file
from .market_archive import MarketArchive, encoded, stamp
from .providers import ProviderFailure

LIMIT = 512 * 1024 * 1024
MAX_FILES = 200_000
FORMAT = 'MARKET_SOURCE_BACKUP_V1'


def require(condition, code):
    if not condition:
        raise ProviderFailure(code)


def allowed(name):
    parts = PurePosixPath(name).parts
    if (not parts or '\\' in name or ':' in name or name.startswith('/') or '..' in parts
            or PurePosixPath(name).as_posix() != name):
        return False
    if name in {'market-archive.json', 'bundle-receipt.json', 'stage-a-profile.json'}:
        return True
    return (len(parts) >= 2 and (
        parts[0] == 'manifests' and name.endswith('.json') or
        parts[0] == 'artifacts' and len(parts) == 2 and name.endswith('.parquet') or
        parts[0] == 'collector' and name.endswith('.json')))


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(archive):
    files = {}
    checkpoints = {}
    for path in archive.root.rglob('*'):
        require(not path.is_symlink() and not path.is_junction(), 'SOURCE_LINK_FORBIDDEN')
        if path.is_dir():
            continue
        name = path.relative_to(archive.root).as_posix()
        if name == '.writer.lock':
            continue
        require(allowed(name), 'SOURCE_UNEXPECTED_FILE_OR_ACTIVE_COLLECTOR')
        if name.startswith('collector/'):
            checkpoint = json.loads(path.read_text(encoding='utf-8'))
            provider = checkpoint['provider']
            prior = checkpoints.get(provider)
            if prior is None or checkpoint['updated_at'] > prior['updated_at']:
                checkpoints[provider] = checkpoint
        files[name] = {'bytes': path.stat().st_size, 'sha256': file_hash(path)}
    require(len(files) <= MAX_FILES and sum(f['bytes'] for f in files.values()) <= LIMIT,
            'SOURCE_BACKUP_BUDGET_EXCEEDED')
    require(all(not c.get('stats', {}).get('connected', False) for c in checkpoints.values()),
            'SOURCE_ACTIVE_CHECKPOINT')
    return files


def export_source(root, destination, phrase):
    require(len(phrase) >= 16, 'BACKUP_PASSPHRASE_REQUIRED')
    archive = MarketArchive(Path(root))
    destination = Path(destination).resolve()
    require(not destination.is_relative_to(archive.root), 'BACKUP_OUTSIDE_SOURCE_REQUIRED')
    require(not destination.exists(), 'NEW_SOURCE_BACKUP_REQUIRED')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with archive.writer(), tempfile.TemporaryDirectory(prefix='mc-source-export-') as temp:
        checked = archive.integrity()
        files = inventory(archive)
        description = {'format': FORMAT, 'created_at': stamp(), 'files': files,
                       'integrity': {k: checked[k] for k in ('status', 'manifests', 'artifacts')},
                       'manifest_hashes': [m['manifest_hash'] for m in archive.manifests()],
                       'database_access': False, 'owner_writes': False}
        plain = Path(temp) / 'source.tar'
        with tarfile.open(plain, 'w', format=tarfile.PAX_FORMAT) as bundle:
            payload = encoded(description)
            member = tarfile.TarInfo('source-backup.json')
            member.size = len(payload)
            bundle.addfile(member, io.BytesIO(payload))
            for name, expected in files.items():
                path = archive.root / name
                require(file_hash(path) == expected['sha256'], 'SOURCE_CHANGED_DURING_BACKUP')
                member = tarfile.TarInfo('source/' + name)
                member.size = expected['bytes']
                with path.open('rb') as stream:
                    bundle.addfile(member, stream)
        require(files == inventory(archive), 'SOURCE_CHANGED_DURING_BACKUP')
        encrypt_file(plain, destination, phrase)
        require(files == inventory(archive), 'SOURCE_CHANGED_DURING_BACKUP')
    return {'status': 'SOURCE_ENCRYPTED_BACKUP_CREATED', 'backup': str(destination),
            'sha256': file_hash(destination), 'encrypted_bytes': destination.stat().st_size,
            'source_bytes': sum(v['bytes'] for v in files.values()),
            'files': len(files), 'manifest_hashes': description['manifest_hashes'],
            'database_access': False, 'owner_writes': False}


def restore_source(source, destination, phrase):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    require(not destination.exists(), 'NEW_SOURCE_RESTORE_ROOT_REQUIRED')
    # Reuse the archive's protected-lake/root guard without creating a marker.
    try:
        MarketArchive(destination)
    except ProviderFailure as error:
        if error.code != 'INDEPENDENT_ARCHIVE_REQUIRED':
            raise
    require(source.stat().st_size <= LIMIT + MAX_FILES * 4096 + 1024 * 1024,
            'SOURCE_BACKUP_BUDGET_EXCEEDED')
    original_hash = file_hash(source)
    with tempfile.TemporaryDirectory(prefix='mc-source-restore-') as temp:
        plain = Path(temp) / 'authenticated.tar'
        # No destination is created until GCM authentication and all tar headers
        # pass. Tar links, duplicate names and unchecked extraction are forbidden.
        decrypt_file(source, plain, phrase)
        with tarfile.open(plain, 'r:') as bundle:
            members, names = [], set()
            for member in bundle:
                require(member.isfile() and member.name not in names, 'SOURCE_UNSAFE_BACKUP_MEMBER')
                require(member.name == 'source-backup.json' or
                        member.name.startswith('source/') and allowed(member.name[7:]),
                        'SOURCE_UNSAFE_BACKUP_MEMBER')
                require(len(members) < MAX_FILES + 1 and 0 <= member.size <= LIMIT,
                        'SOURCE_BACKUP_BUDGET_EXCEEDED')
                names.add(member.name)
                members.append(member)
            require('source-backup.json' in names, 'SOURCE_BACKUP_INVENTORY_MISSING')
            header = bundle.getmember('source-backup.json')
            require(header.size <= 32 * 1024 * 1024, 'SOURCE_BACKUP_INVENTORY_TOO_LARGE')
            description = json.load(bundle.extractfile(header))
            require(description.get('format') == FORMAT, 'SOURCE_BACKUP_FORMAT_INVALID')
            files = description['files']
            require('market-archive.json' in files and
                    names == {'source-backup.json', *('source/' + n for n in files)},
                    'SOURCE_BACKUP_INVENTORY_MISMATCH')
            require(sum(m.size for m in members) <= LIMIT + header.size,
                    'SOURCE_BACKUP_BUDGET_EXCEEDED')
            for member in members:
                if member.name == 'source-backup.json':
                    continue
                expected = files[member.name[7:]]
                require(member.size == expected['bytes'], 'SOURCE_BACKUP_SIZE_MISMATCH')
                stream = bundle.extractfile(member)
                require(hashlib.file_digest(stream, 'sha256').hexdigest() == expected['sha256'],
                        'SOURCE_BACKUP_HASH_MISMATCH')
            marker = json.load(bundle.extractfile(bundle.getmember('source/market-archive.json')))
            require(marker.get('purpose') == MarketArchive.PURPOSE, 'SOURCE_BACKUP_PURPOSE_INVALID')
            require(file_hash(source) == original_hash, 'SOURCE_BACKUP_CHANGED')
            destination.mkdir(parents=True, exist_ok=False)
            for member in members:
                if member.name == 'source-backup.json':
                    continue
                target = destination / member.name[7:]
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream, bundle.extractfile(member) as incoming:
                    while chunk := incoming.read(1024 * 1024):
                        stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
    recovered = MarketArchive(destination)
    checked = recovered.integrity()
    require(inventory(recovered) == description['files'], 'SOURCE_RESTORE_INVENTORY_MISMATCH')
    require([m['manifest_hash'] for m in recovered.manifests()] == description['manifest_hashes'],
            'SOURCE_RESTORE_LINEAGE_MISMATCH')
    require({k: checked[k] for k in ('status', 'manifests', 'artifacts')} == description['integrity'],
            'SOURCE_RESTORE_INTEGRITY_MISMATCH')
    require(file_hash(source) == original_hash, 'SOURCE_BACKUP_CHANGED')
    return {'status': 'VALIDATED_ENCRYPTED_SOURCE_RESTORE', 'backup': str(source),
            'sha256': original_hash, 'restore_root': str(destination), 'integrity': checked,
            'manifest_hashes': description['manifest_hashes'], 'database_access': False,
            'owner_writes': False, 'collector_started': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--backup', required=True, type=Path)
    parser.add_argument('--restore-root', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args(argv)
    require(not args.report.exists(), 'NEW_SOURCE_REPORT_REQUIRED')
    phrase = os.environ.get('MARKET_CORTEX_SOURCE_BACKUP_PASSPHRASE', '')
    report = {'owner_writes': False, 'database_access': False, 'started_at': stamp()}
    try:
        report['backup'] = export_source(args.root, args.backup, phrase)
        report['restore'] = restore_source(args.backup, args.restore_root, phrase)
        report['status'] = 'VALIDATED_SOURCE_BACKUP_AND_ISOLATED_RESTORE'
    except Exception as error:
        report.update(status='STOPPED_PRESERVE_PARTIAL_STATE', error_code=(
            error.code if isinstance(error, ProviderFailure) else 'SOURCE_BACKUP_OR_RESTORE_FAILED'))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'status': report['status'], 'report': str(args.report.resolve()),
                      'owner_writes': False, 'error_code': report.get('error_code')}))
    return 0 if report['status'].startswith('VALIDATED_') else 1


if __name__ == '__main__':
    raise SystemExit(main())
