"""Stage A candidate policy: seven daily listings, durable GET limits, no SQL.

The viewer is cache-only. Credentialed acceptance is a separate operation;
opening/searching any of the full catalogs grants no download permission.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

from .market_archive import MarketArchive, stamp
from .market_data_app import create_market_app
from .market_fetch_scope import FetchScope, FetchWindow
from .market_universe import PacedTransport
from .providers import ProviderFailure

LIMITS = {'history': 42, 'metadata': 21, 'stream_authorization': 18}
LISTINGS = (
    ('upstox', 'NSE_EQ|INE002A01018', 'RELIANCE', 'NSE'),
    ('upstox', 'BSE_EQ|INE002A01018', 'RELIANCE', 'BSE'),
    ('upstox', 'NSE_EQ|INE009A01021', 'INFY', 'NSE'),
    ('upstox', 'BSE_EQ|INE009A01021', 'INFY', 'BSE'),
    ('alpaca', 'b0b6dd9d-8b9b-48a9-ba46-b9d54906e415', 'AAPL', 'NASDAQ'),
    ('alpaca', 'b28f4066-5c6d-479b-a2af-85dc1a8f16fb', 'SPY', 'ARCA'),
    ('alpaca', '2d9e926c-e17c-47c3-ad8c-26c7a594e48f', 'QQQ', 'NASDAQ'),
)
WINDOWS = {
    'upstox': (datetime(2026, 9, 30, 18, 30, tzinfo=timezone.utc),
               datetime(2026, 10, 13, 18, 30, tzinfo=timezone.utc)),
    'alpaca': (datetime(2026, 10, 1, 4, tzinfo=timezone.utc),
               datetime(2026, 10, 14, 4, tzinfo=timezone.utc)),
}


def approved_scope():
    return FetchScope(tuple(FetchWindow(provider, native, '1d', *WINDOWS[provider])
                            for provider, native, _, _ in LISTINGS))


def category(host, path):
    if host == 'api.upstox.com' and path == '/v3/feed/market-data-feed/authorize':
        return 'upstox', 'stream_authorization'
    if host == 'api.upstox.com':
        decoded = unquote(path)
        match = re.fullmatch(r'/v3/historical-candle/([^/]+)/days/1/(\d{4}-\d{2}-\d{2})/(\d{4}-\d{2}-\d{2})', decoded)
        if match and match[1] in {n for p, n, _, _ in LISTINGS if p == 'upstox'}:
            # Every network request must remain within the approved local dates.
            if '2026-10-01' <= match[3] <= match[2] <= '2026-10-13':
                return 'upstox', 'history'
    if host == 'data.alpaca.markets' and re.fullmatch(r'/v2/stocks/(AAPL|SPY|QQQ)/bars', path):
        return 'alpaca', 'history'
    if host in {'api.alpaca.markets', 'paper-api.alpaca.markets'} and path in {'/v2/assets', '/v2/calendar'}:
        return 'alpaca', 'metadata'
    if host == 'data-api.binance.vision' and path == '/api/v3/exchangeInfo':
        return 'binance', 'metadata'
    raise ProviderFailure('STAGE_A_ENDPOINT_NOT_APPROVED')


class StageATransport(PacedTransport):
    """Each retry admission is retained; restarting cannot reset the quota.

    Counts include conservative admissions that fail before an HTTP response.
    A second simultaneous process is rejected rather than racing the ledger.
    """
    def __init__(self, archive, client=None):
        super().__init__(client)
        self.archive = archive

    def usage(self):
        counts = {key: 0 for key in LIMITS}
        for manifest in self.archive.manifests('requests'):
            metadata = manifest['metadata']
            if metadata.get('operation') == 'stage_a_get_admission':
                key = metadata['category']
                if key not in counts:
                    raise ProviderFailure('STAGE_A_REQUEST_LEDGER_INVALID')
                counts[key] += 1
        return counts

    def before_attempt(self, host, path):
        provider, key = category(host, path)
        lock = self.archive.root / '.stage-a-request.lock'
        try:
            stream = lock.open('x', encoding='ascii')
        except FileExistsError:
            raise ProviderFailure('STAGE_A_REQUEST_PROCESS_BUSY') from None
        try:
            stream.close()
            used = self.usage()
            if used[key] >= LIMITS[key] or sum(used.values()) >= 81:
                raise ProviderFailure('STAGE_A_REQUEST_BUDGET_EXHAUSTED')
            super().before_attempt(host, path)
            self.archive.append('requests', provider, [], sources=[], metadata={
                'operation': 'stage_a_get_admission', 'category': key,
                'conservative_admission_not_response_count': True})
        finally:
            lock.unlink(missing_ok=True)

    def get(self, host, path, *, params=None, headers=None):
        # Validate Alpaca's request parameters as well as its ticker path.
        if host == 'data.alpaca.markets':
            params = params or {}
            try:
                start = datetime.fromisoformat(params['start'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(params['end'].replace('Z', '+00:00'))
                native = next(n for p, n, symbol, _ in LISTINGS
                              if p == 'alpaca' and path == f'/v2/stocks/{symbol}/bars')
                approved_scope().require('alpaca', native, '1d', start, end)
                valid = (set(params) <= {'start','end','timeframe','feed','adjustment','asof','sort','limit','page_token'}
                         and params.get('timeframe') == '1Day' and params.get('feed') == 'iex'
                         and params.get('adjustment') == 'raw' and params.get('asof') == '-'
                         and params.get('sort') in (None, 'asc') and 1 <= int(params.get('limit', 0)) <= 1000)
                if not valid:
                    raise ValueError()
            except (ValueError, KeyError, StopIteration):
                raise ProviderFailure('STAGE_A_ALPACA_PARAMETERS_NOT_APPROVED') from None
        return super().get(host, path, params=params, headers=headers)


def verify_profile(archive):
    profile = json.loads((archive.root / 'stage-a-profile.json').read_text())
    expected = [{'provider': p, 'native_id': n, 'symbol': s, 'exchange': e} for p, n, s, e in LISTINGS]
    if (Path(profile['source_root']).resolve() != archive.root or
        profile.get('authorized_stage') != 'A_CONDITIONAL_CANDIDATE_ONLY' or
        profile.get('source_origin_purpose_preserved') != MarketArchive.PURPOSE or
        profile.get('scoped_listings') != expected or
        profile.get('windows') != {p: [t.isoformat() for t in w] for p, w in WINDOWS.items()} or
        profile.get('provider_get_limits') != LIMITS or
        profile.get('capture_seconds_per_provider') != 120 or
        profile.get('maximum_daily_observations') != 91 or
        profile.get('maximum_source_bytes') != 512 * 1024 * 1024 or
        profile.get('owner_cutover_approved') is not False or
        any(profile.get(k) is not False for k in ('database_access','owner_writes','continuous_collection','scheduled_jobs'))):
        raise ProviderFailure('STAGE_A_PROFILE_CHANGED_OR_SCOPE_INVALID')
    return profile


def viewer(archive):
    app = create_market_app(archive, fetch_scope=FetchScope(()))

    @app.get('/api/v1/market-data/stage-a-policy')
    def policy():
        return {'mode': 'STAGE_A_CANDIDATE_CACHE_ONLY', 'history_fetch_enabled': False,
                'source_root': str(archive.root), 'owner_writes': False,
                'continuous_collection': False, 'scheduled_jobs': False,
                'provider_get_admissions': StageATransport(archive).usage()}
    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8678, choices=[8678])
    args = parser.parse_args(argv)
    archive = MarketArchive(args.root, maximum_bytes=512 * 1024 * 1024)
    verify_profile(archive)
    archive.integrity()
    import uvicorn
    uvicorn.run(viewer(archive), host='127.0.0.1', port=args.port, log_level='warning')


if __name__ == '__main__':
    raise SystemExit(main())
