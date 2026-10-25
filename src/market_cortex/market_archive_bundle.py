"""Copy verified independent evidence into a new, offline review archive.

Original manifests and Parquet bytes remain identical. One source per provider;
no catalog refresh, ingestion, credentials, SQL, collector state or server start.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from .market_archive import MarketArchive, stamp
from .providers import ProviderFailure


def copy_verified(source, destination, expected_hash, *, archive=None):
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest()!=expected_hash:
        raise ProviderFailure('BUNDLE_SOURCE_CHANGED')
    if archive is not None:archive.assert_capacity(len(payload))
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    if hashlib.sha256(destination.read_bytes()).hexdigest()!=expected_hash:
        raise ProviderFailure('BUNDLE_COPY_HASH_MISMATCH')


def assemble(sources: dict[str,Path], destination: Path, *, maximum_bytes=512*1024*1024):
    if set(sources)!={'binance','upstox','alpaca'}:
        raise ProviderFailure('THREE_INDEPENDENT_PROVIDER_SOURCES_REQUIRED')
    if destination.exists():
        raise ProviderFailure('NEW_BUNDLE_DIRECTORY_REQUIRED')
    checked = {}
    for provider,path in sources.items():
        archive = MarketArchive(path)
        archive.integrity()
        if not archive.latest('catalog',provider)[0]:
            raise ProviderFailure('BUNDLE_PROVIDER_CATALOG_MISSING')
        checked[provider] = archive
    target = MarketArchive(destination,initialize=True,maximum_bytes=maximum_bytes)
    receipts, artifacts = {}, set()
    for provider,archive in checked.items():
        manifests = archive.manifests(provider=provider)
        paths = {p.stem.rsplit('-',1)[-1]:p for p in (archive.root/'manifests').rglob('*.json')}
        for manifest in manifests:
            original = paths[manifest['manifest_hash']]
            copy_verified(original,target.root/original.relative_to(archive.root),manifest['manifest_hash'],archive=target)
            source_artifact = archive.artifact_path(manifest)
            if manifest['artifact_hash'] not in artifacts:
                copy_verified(source_artifact,target.root/manifest['artifact'],manifest['artifact_hash'],archive=target)
                artifacts.add(manifest['artifact_hash'])
        receipts[provider] = {'source_root':str(archive.root),'manifest_hashes':[m['manifest_hash'] for m in manifests],
            'catalog_snapshot':archive.latest('catalog',provider)[0]['manifest_hash']}
    result = {'status':'THREE_MARKET_OFFLINE_REVIEW_BUNDLE','observed_at':stamp(),
        'sources':receipts,'root':str(target.root),'integrity':target.integrity(),
        'owner_writes':False,'database_access':False,'provider_calls':0,
        'collector_state_copied':False,'currently_live_subscriptions':0}
    payload=json.dumps(result,indent=2).encode('utf-8')
    target.assert_capacity(len(payload))
    with (target.root/'bundle-receipt.json').open('xb') as stream:
        stream.write(payload)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for provider in ('binance','upstox','alpaca'):
        parser.add_argument('--'+provider,type=Path,required=True)
    parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args(argv)
    result=assemble({p:getattr(args,p) for p in ('binance','upstox','alpaca')},args.destination)
    print(json.dumps({'status':result['status'],'root':result['root'],'owner_writes':False}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
