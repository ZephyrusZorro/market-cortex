"""Materialize a new versioned candidate; never starts/deploys an application.

Run as a module. No secrets, SQL, downloads, package installation or schedules.
Copies installed dependencies rather than sharing the production node_modules.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from market_cortex.market_archive import MarketArchive, stamp
from market_cortex.market_archive_bundle import assemble
from market_cortex.market_stage_a import LISTINGS, WINDOWS, LIMITS
from market_cortex.market_universe import search_catalog

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    operation = 'stage-a-' + uuid4().hex
    candidate = Path('C:/MarketCortexCandidates') / operation
    source = Path('C:/MarketCortexSources/three-market-v1') / operation
    if candidate.exists() or source.exists():
        raise RuntimeError('NEW_CANDIDATE_AND_SOURCE_REQUIRED')
    original = ROOT / 'apps/workstation'
    protected_build = original / '.next/BUILD_ID'
    original_build = sha(protected_build) if protected_build.exists() else None
    operational = subprocess.check_output(['git', 'rev-parse', 'v1.0.1-operational^{}'], cwd=ROOT, text=True).strip()
    if operational != 'cfe696d51b137566c15eebaf734ff7ee0ca95197':
        raise RuntimeError('OPERATIONAL_RELEASE_TAG_CHANGED')
    candidate.mkdir(parents=True)
    shutil.copytree(ROOT / 'src', candidate / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.egg-info'))
    shutil.copy2(ROOT / 'pyproject.toml', candidate / 'pyproject.toml')
    frontend = candidate / 'workstation'
    shutil.copytree(original, frontend, ignore=shutil.ignore_patterns(
        '.next', 'node_modules', '.env*', 'tsconfig.tsbuildinfo', '__pycache__'))
    shutil.copytree(original / 'node_modules', frontend / 'node_modules')
    page = frontend / 'app/markets/page.tsx'
    contents = page.read_text(encoding='utf-8')
    old = "        const fetched = await marketJson<{items:SourceCandle[];state:string}>('history/fetch', {"
    tail = '        if (current()) { setRows(fetched.items); setState(fetched.state);knownEnd=range.end.getTime(); }'
    if contents.count(old) != 1 or contents.count(tail) != 1:
        raise RuntimeError('CANDIDATE_UI_PATCH_CONTEXT_CHANGED')
    # Candidate-only source changes. Selection and polling cannot request source
    # downloads. Backend separately denies every POST history operation.
    contents = contents.replace(old, "        if (process.env.NEXT_PUBLIC_MARKET_CORTEX_CACHE_ONLY !== '1') {\n" + old)
    contents = contents.replace(tail, tail + '\n        }')
    contents = contents.replace("if(selected.provider==='binance' && ordered.some", 
        "if(process.env.NEXT_PUBLIC_MARKET_CORTEX_CACHE_ONLY !== '1' && selected.provider==='binance' && ordered.some")
    contents = contents.replace('<h1>Market data explorer</h1>',
        '<h1>Market data explorer</h1><p>Stage A candidate · cached observations · source downloads and continuous collection disabled</p>')
    page.write_text(contents, encoding='utf-8')
    review = ROOT / 'runtime/three-market-capped-review-2026-10-14'
    copied = assemble({p: review for p in ('binance', 'upstox', 'alpaca')}, source)
    archive = MarketArchive(source)
    identity_checks = []
    for provider, native, symbol, exchange in LISTINGS:
        values = search_catalog(archive, provider=provider, native_id=native, limit=2)['items']
        if len(values) != 1 or values[0]['symbol'] != symbol or values[0]['exchange'] != exchange:
            raise RuntimeError('SCOPED_NATIVE_LISTING_IDENTITY_MISMATCH')
        identity_checks.append({'provider': provider, 'native_id': native, 'symbol': symbol, 'exchange': exchange})
    profile = {'operation': operation, 'authorized_stage': 'A_CONDITIONAL_CANDIDATE_ONLY',
        'source_origin_purpose_preserved': MarketArchive.PURPOSE, 'owner_cutover_approved': False,
        'source_root': str(source), 'candidate_root': str(candidate), 'api_port': 8678, 'frontend_port': 3019,
        'maximum_source_bytes': 512 * 1024 * 1024, 'maximum_daily_observations': 91,
        'provider_get_limits': LIMITS, 'capture_seconds_per_provider': 120,
        'scoped_listings': identity_checks,
        'windows': {p: [t.isoformat() for t in w] for p, w in WINDOWS.items()},
        'database_access': False, 'owner_writes': False, 'continuous_collection': False, 'scheduled_jobs': False}
    with (source / 'stage-a-profile.json').open('x', encoding='utf-8') as stream:
        json.dump(profile, stream, indent=2)
    if (sha(protected_build) if protected_build.exists() else None) != original_build:
        raise RuntimeError('OPERATIONAL_FRONTEND_BUILD_CHANGED')
    files = {str(p.relative_to(candidate)).replace('\\', '/'): sha(p)
             for p in candidate.rglob('*') if p.is_file() and 'node_modules' not in p.parts}
    receipt = {'status': 'PREPARED_NOT_BUILT_OR_DEPLOYED', 'prepared_at': stamp(), **profile,
        'operational_tag_commit': operational, 'original_build_id_hash': original_build,
        'candidate_source_hashes': files, 'dependency_lock_hash': sha(frontend / 'package-lock.json'),
        'next_package_hash': sha(frontend / 'node_modules/next/package.json'),
        'source_copy': copied, 'catalog_counts': {p: search_catalog(archive, provider=p, limit=1)['total']
                        for p in ('binance', 'upstox', 'alpaca')},
        'provider_requests_performed': 0, 'new_broker_history_operations': 0,
        'owner_backup_gate': 'PENDING_PRIVATE_TERMINAL_RECEIPT', 'source_encrypted_recovery_gate': 'PENDING',
        'live_acceptance_gate': 'PENDING_FRESH_INDIAN_SESSION', 'cutover_performed': False}
    report = ROOT / 'runtime' / (operation + '-candidate.json')
    with report.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2)
    print(json.dumps({'status': receipt['status'], 'report': str(report),
                      'candidate': str(candidate), 'source_root': str(source)}))


if __name__ == '__main__':
    prepare()
