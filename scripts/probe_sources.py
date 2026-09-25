"""Small GET-only provider feasibility probe. Run on owner's workstation.

No order endpoints. Credentials read from environment and never written to report.
Report records sampled history, not guaranteed full historical depth.
"""
import argparse
import datetime as dt
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

INDIA = ["RELIANCE", "HDFCBANK", "INFY", "TCS", "M&M", "SBIN"]
US = ["AAPL", "NVDA", "MSFT", "SPY", "QQQ"]
CRYPTO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
ALLOWED_HOSTS = {"api.upstox.com", "paper-api.alpaca.markets", "data.alpaca.markets", "data-api.binance.vision"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("redirect_disabled")


def get_json(host, path, params=None, headers=None):
    assert host in ALLOWED_HOSTS and path.startswith("/") and not path.startswith("//")
    url = f"https://{host}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "MarketCortex-ReadOnlyProbe/0.6", **(headers or {})}, method="GET")
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(req, timeout=12) as res:
            if int(res.headers.get("Content-Length", "0")) > 3_000_000:
                raise ValueError("response_too_large")
            raw = res.read(3_000_001)
            if len(raw) > 3_000_000:
                raise ValueError("response_too_large")
            return json.loads(raw), {"http_status": res.status, "rate_limit": {k: v for k, v in res.headers.items() if k.lower() in ("x-mbx-used-weight-1m", "x-ratelimit-remaining", "ratelimit-remaining")}}
    except urllib.error.HTTPError as e:
        return None, {"http_status": e.code, "error": "HTTP response; inspect provider account separately"}
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        return None, {"error": type(e).__name__}


def span(values):
    return {"sampled_earliest_timestamp": min(values) if values else None, "sampled_latest_timestamp": max(values) if values else None, "sample_count": len(values), "full_history_verified": False}


def upstox(today):
    token = os.environ.get("UPSTOX_ACCESS_TOKEN")
    if not token:
        return {"status": "SKIPPED_NO_CREDENTIAL", "symbols": {}}
    hdr = {"Authorization": f"Bearer {token}"}
    report = {"status": "ACCOUNT_TEST_PENDING_RESULTS", "symbols": {}}
    for symbol in INDIA:
        found, lookup = get_json("api.upstox.com", "/v2/instruments/search", {"query": symbol, "exchanges": "NSE", "segments": "EQ", "page_number": 1, "records": 20}, hdr)
        choices = [x for x in (found or {}).get("data", []) if x.get("trading_symbol") == symbol and x.get("segment") == "NSE_EQ" and x.get("exchange") == "NSE"]
        row = {"lookup": lookup, "exact_matches": len(choices)}
        if len(choices) == 1:
            x = choices[0]; key = x.get("instrument_key")
            row.update({"native_id": key, "venue": x.get("exchange"), "isin": x.get("isin"), "symbol": x.get("trading_symbol")})
            if key:
                path = f"/v3/historical-candle/{urllib.parse.quote(key, safe='')}/days/1/"
                recent_start = (today - dt.timedelta(days=60)).isoformat()
                recent, recent_meta = get_json("api.upstox.com", path + f"{today.isoformat()}/{recent_start}", headers=hdr)
                old, old_meta = get_json("api.upstox.com", path + "2017-01-01/2016-01-01", headers=hdr)
                candles = (recent or {}).get("data", {}).get("candles", []) + (old or {}).get("data", {}).get("candles", [])
                row.update({"recent": recent_meta, "old_sample": old_meta, "history_sample": span([str(c[0]) for c in candles if isinstance(c, list) and c]), "first_candle_shape": len(candles[0]) if candles else None})
        report["symbols"][symbol] = row
    return report


def alpaca(today):
    key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        return {"status": "SKIPPED_NO_CREDENTIAL", "symbols": {}}
    hdr = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    report = {"status": "ACCOUNT_TEST_PENDING_RESULTS", "feed_requested": "iex", "symbols": {}}
    for symbol in US:
        asset, asset_meta = get_json("paper-api.alpaca.markets", f"/v2/assets/{symbol}", headers=hdr)
        row = {"asset_lookup": asset_meta, "native_id": (asset or {}).get("id"), "venue": (asset or {}).get("exchange"), "asset_status": (asset or {}).get("status")}
        base = f"/v2/stocks/{symbol}/bars"
        old, old_meta = get_json("data.alpaca.markets", base, {"timeframe": "1Day", "start": "2000-01-01", "end": today.isoformat(), "limit": 1, "adjustment": "raw", "feed": "iex"}, hdr)
        recent, recent_meta = get_json("data.alpaca.markets", base, {"timeframe": "1Day", "start": (today-dt.timedelta(days=60)).isoformat(), "end": today.isoformat(), "limit": 100, "adjustment": "raw", "feed": "iex"}, hdr)
        bars = (old or {}).get("bars", []) + (recent or {}).get("bars", [])
        row.update({"old_sample": old_meta, "recent": recent_meta, "history_sample": span([str(b.get("t")) for b in bars if isinstance(b, dict) and b.get("t")]), "page_token_present": bool((recent or {}).get("next_page_token"))})
        if symbol in ("AAPL", "NVDA"):
            adj, adj_meta = get_json("data.alpaca.markets", base, {"timeframe": "1Day", "start": "2020-01-02", "end": "2020-01-10", "limit": 10, "adjustment": "split", "feed": "iex"}, hdr)
            raw, raw_meta = get_json("data.alpaca.markets", base, {"timeframe": "1Day", "start": "2020-01-02", "end": "2020-01-10", "limit": 10, "adjustment": "raw", "feed": "iex"}, hdr)
            a, b = (adj or {}).get("bars", []), (raw or {}).get("bars", [])
            row["split_comparison"] = {"raw_request": raw_meta, "adjusted_request": adj_meta, "sample_raw_close": b[0].get("c") if b else None, "sample_split_close": a[0].get("c") if a else None, "same_timestamp": bool(a and b and a[0].get("t") == b[0].get("t"))}
        report["symbols"][symbol] = row
    return report


def binance(today):
    report = {"status": "PUBLIC_ENDPOINT_TEST_PENDING_RESULTS", "venue": "Binance Spot", "symbols": {}}
    now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    for symbol in CRYPTO:
        info, info_meta = get_json("data-api.binance.vision", "/api/v3/exchangeInfo", {"symbol": symbol})
        x = (info or {}).get("symbols", [{}])[0] if info else {}
        old, old_meta = get_json("data-api.binance.vision", "/api/v3/klines", {"symbol": symbol, "interval": "1d", "startTime": 0, "limit": 1})
        latest, latest_meta = get_json("data-api.binance.vision", "/api/v3/klines", {"symbol": symbol, "interval": "1d", "limit": 3})
        closed = [c for c in (latest or []) if isinstance(c, list) and len(c) > 6 and c[6] < now_ms]
        times = [dt.datetime.fromtimestamp(c[0]/1000, dt.timezone.utc).isoformat() for c in ((old or []) + closed) if isinstance(c, list) and c]
        report["symbols"][symbol] = {"metadata": info_meta, "native_id": x.get("symbol"), "status": x.get("status"), "base_asset": x.get("baseAsset"), "quote_asset": x.get("quoteAsset"), "old_sample": old_meta, "latest": latest_meta, "history_sample": span(times), "latest_complete_utc_open": dt.datetime.fromtimestamp(closed[-1][0]/1000, dt.timezone.utc).isoformat() if closed else None, "daily_anchor_observed_utc_midnight": (all(c[0] % 86_400_000 == 0 for c in ((old or []) + closed) if isinstance(c, list) and c) if ((old or []) + closed) else None)}
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="Make read-only GET calls to documented endpoints")
    ap.add_argument("--output", default="data/probes/phase_0_6_local.json", help="Gitignored result path")
    args = ap.parse_args()
    if not args.run:
        print("Dry run: --run required for network calls. Providers: Upstox (if token), Alpaca (if keys), Binance Spot public. No order endpoints.")
        return 0
    today = dt.datetime.now(dt.timezone.utc).date()
    report = {"report_version": "0.6", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "machine_os": sys.platform, "notice": "Sampled evidence only; not proof of complete coverage, entitlements, corrections, rights or owner approval.", "providers": {"upstox": upstox(today), "alpaca": alpaca(today), "binance": binance(today)}}
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote redacted probe summary to {out}; no credentials or raw response bodies stored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
