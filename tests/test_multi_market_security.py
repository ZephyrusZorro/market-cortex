"""Synthetic local credential/wire checks. No authenticated provider claims."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import subprocess

import httpx
import pytest

from market_cortex.market_stream import decode_events
from market_cortex.market_universe import sync_catalog
from market_cortex.market_archive import MarketArchive
from market_cortex.providers import ReadTransport


def test_windows_current_user_dpapi_roundtrip_and_restricted_acl():
    if os.name!='nt':
        pytest.skip('Windows DPAPI required')
    shell=shutil.which('pwsh') or shutil.which('powershell')
    assert shell is not None
    script=r'''
$ErrorActionPreference='Stop'
$taskSynthetic='synthetic-local-credential-'+[guid]::NewGuid().ToString('N')
function Read-Host { param($Prompt,[switch]$AsSecureString) ConvertTo-SecureString $taskSynthetic -AsPlainText -Force }
$taskFile=$null
try {
 $taskFile=& .\scripts\Set-MarketDataCredentials.ps1 -Provider upstox
 $taskRoot=[IO.Path]::GetFullPath((Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'MarketCortex\Secrets'))
 if (-not $taskFile.StartsWith($taskRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'UNEXPECTED_SYNTHETIC_SECRET_PATH' }
 if (-not ([IO.Path]::GetFileName($taskFile) -match '^upstox-[a-f0-9]{32}\.dpapi$')) {throw 'UNEXPECTED_SYNTHETIC_FILENAME'}
 $taskCipher=Get-Content -LiteralPath $taskFile -Raw
 if($taskCipher.Contains($taskSynthetic)){throw 'PLAINTEXT_CREDENTIAL_EXPOSED'}
 $taskSecure=ConvertTo-SecureString $taskCipher
 try {
  $taskValue=([Net.NetworkCredential]::new('', $taskSecure).Password | ConvertFrom-Json).UPSTOX_ACCESS_TOKEN
  if($taskValue -ne $taskSynthetic){throw 'DPAPI_ROUNDTRIP_FAILED'}
 } finally {$taskSecure.Dispose();$taskValue=$null}
 $taskAcl=Get-Acl -LiteralPath $taskFile
 if(-not $taskAcl.AreAccessRulesProtected -or $taskAcl.Access.Count -ne 1){throw 'CREDENTIAL_ACL_NOT_RESTRICTED'}
 Write-Output 'SYNTHETIC_CURRENT_USER_DPAPI_AND_ACL_VALIDATED'
} finally {
 if($taskFile -and $taskFile.StartsWith($taskRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
  Remove-Item -LiteralPath $taskFile
 }
 $taskSynthetic=$null;$taskCipher=$null
}
'''
    result=subprocess.run([shell,'-NoProfile','-Command',script],cwd=Path(__file__).resolve().parents[1],
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert 'SYNTHETIC_CURRENT_USER_DPAPI_AND_ACL_VALIDATED' in result.stdout
    assert 'synthetic-local-credential-' not in result.stdout


def test_upstox_full_feed_uses_real_ohlcv_and_provisional_label():
    from market_cortex.feed_proto.MarketDataFeed_pb2 import FeedResponse
    now=datetime(2026,10,12,5,tzinfo=timezone.utc)
    message=FeedResponse();message.currentTs=int(now.timestamp()*1000)
    full=message.feeds['NSE_EQ|INE000A01010'].fullFeed.marketFF
    full.ltpc.ltp=101;full.ltpc.ltt=int(now.timestamp()*1000)
    sample=full.marketOHLC.ohlc.add();sample.interval='I1';sample.ts=int(now.timestamp()*1000)
    sample.open=100;sample.high=102;sample.low=99;sample.close=101;sample.vol=123
    item={'native_id':'NSE_EQ|INE000A01010','symbol':'SAMPLE'}
    events=decode_events('upstox',message.SerializeToString(),[item],received_at=now)
    candle=next(e for e in events if e['kind']=='candle')
    assert candle['feed']=='v3_full' and not candle['is_final']
    assert candle['candle']['volume']=='123' and candle['candle']['close']=='101.0'
    sample.low=999
    with pytest.raises(ValueError):
        decode_events('upstox',message.SerializeToString(),[item],received_at=now)


def test_suspended_series_do_not_deactivate_listed_series(tmp_path):
    archive=MarketArchive(tmp_path/'source',initialize=True)
    base={'instrument_key':'NSE_EQ|INE000A01010','symbol':'SAMPLE','trading_symbol':'SAMPLE','name':'Sample',
          'segment':'NSE_EQ','exchange':'NSE','isin':'INE000A01010','instrument_type':'EQ','exchange_token':'1'}
    def public(name):
        rows=[base] if name=='NSE' else [] if name=='BSE' else [
            {**base,'instrument_type':'BE','exchange_token':'2'},
            {**base,'instrument_type':'BL','exchange_token':'3'}]
        return rows,{'sha256':'b'*64}
    manifest=sync_catalog(archive,'upstox',public_fetch=public)
    row=archive.rows(manifest)[0]
    assert row['status']=='LISTED' and row['instrument_type']=='EQ'
    assert len(row['attributes']['suspended_source_variants'])==2


def test_rate_limit_diagnostics_are_whitelisted_numeric_only():
    transport=ReadTransport(httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=[],headers={
        'X-RateLimit-Remaining':'199','X-RateLimit-Limit':'private-token','X-MBX-USED-WEIGHT-1M':'4',
        'Authorization':'must-never-serialize'}))))
    page=transport.get('data-api.binance.vision','/api/v3/klines')
    assert page.rate_limit_headers=={'x-ratelimit-remaining':199,'x-mbx-used-weight-1m':4}
