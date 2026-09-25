"""Read-only Phase 0.6 market-data feasibility probe (Python 3.10+, stdlib only).

Run from the market-cortex root with --run. Only fixed HTTPS GET market-data and
instrument-lookup paths are reachable. Credentials come from environment variables;
response bodies, request headers and exception messages are never saved or printed.
This samples history; it does not establish full coverage or production reliability.
"""

import argparse
import datetime as dt
import json
import os
import re
import ssl
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

INDIA = ("RELIANCE", "HDFCBANK", "INFY", "TCS", "M&M", "SBIN")
US = ("AAPL", "NVDA", "MSFT", "SPY", "QQQ")
CRYPTO = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT")
MAX_BYTES = 3_000_000
TIMEOUT_SECONDS = 12
ENDPOINTS = {
    "api.upstox.com": (r"/v2/instruments/search", r"/v3/historical-candle/[^/]+/days/1/\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}"),
    "paper-api.alpaca.markets": (r"/v2/assets/(?:AAPL|NVDA|MSFT|SPY|QQQ)",),
    "api.alpaca.markets": (r"/v2/assets/(?:AAPL|NVDA|MSFT|SPY|QQQ)",),
    "data.alpaca.markets": (r"/v2/stocks/(?:AAPL|NVDA|MSFT|SPY|QQQ)/bars",),
    "data-api.binance.vision": (r"/api/v3/exchangeInfo", r"/api/v3/klines"),
}
RATE_HEADERS = {"x-mbx-used-weight-1m", "x-ratelimit-remaining", "ratelimit-remaining", "retry-after"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("redirect_disabled")


def get_json(host, path, params=None, headers=None):
    """Return parsed JSON and safe metadata. Never surface a provider response body."""
    if host not in ENDPOINTS or not any(re.fullmatch(pattern, path) for pattern in ENDPOINTS[host]):
        raise ValueError("endpoint_not_allowed")
    url = f"https://{host}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "MarketCortex-ReadOnlyProbe/0.6", **(headers or {})},
        method="GET",
    )
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_BYTES:
                return None, {"http_status": response.status, "error": "RESPONSE_TOO_LARGE"}
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                return None, {"http_status": response.status, "error": "RESPONSE_TOO_LARGE"}
            meta = {"http_status": response.status,
                    "rate_headers": {key.lower(): value for key, value in response.headers.items() if key.lower() in RATE_HEADERS}}
            try:
                return json.loads(raw), meta
            except (UnicodeError, json.JSONDecodeError):
                return None, {**meta, "error": "MALFORMED_JSON"}
    except urllib.error.HTTPError as exc:
        return None, {"http_status": exc.code, "error": "HTTP_ERROR"}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        category = "TIMEOUT" if isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError) else "NETWORK_ERROR"
        return None, {"error": category}
    except (ValueError, OverflowError):
        return None, {"error": "INVALID_RESPONSE_OR_REDIRECT"}


def mapping(value):
    return value if isinstance(value, dict) else {}


def records(value):
    return value if isinstance(value, list) else []


def iso_time(value):
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc).isoformat()
    except (AttributeError, ValueError, OverflowError):
        return None


def span(values):
    timestamps = sorted(t for value in values if (t := iso_time(value)) is not None)
    return {"oldest_sampled_timestamp_utc": timestamps[0] if timestamps else None,
            "latest_sampled_timestamp_utc": timestamps[-1] if timestamps else None,
            "sample_count": len(timestamps), "full_history_verified": False}


def venue_zone(name):
    if name == "Asia/Kolkata":
        return dt.timezone(dt.timedelta(hours=5, minutes=30)), "fixed_UTC_plus_05_30"
    try:
        return ZoneInfo(name), "IANA"
    except ZoneInfoNotFoundError:
        return dt.timezone.utc, "UTC_fallback_without_tzdata"


def conservative_complete(values, zone, today, fallback=False):
    """Exclude today's session; UTC fallback excludes an additional day."""
    candidates = []
    cutoff = today - dt.timedelta(days=1) if fallback else today
    for value in values:
        timestamp = iso_time(value)
        if timestamp and dt.datetime.fromisoformat(timestamp).astimezone(zone).date() < cutoff:
            candidates.append(timestamp)
    return max(candidates) if candidates else None


def status_from(rows):
    states = [row.get("result_status") for row in rows.values()]
    if states and all(x == "SUCCESS" for x in states):
        return "ACCOUNT_TESTED"  # or PUBLIC_TESTED for unauthenticated data
    if any(x in ("SUCCESS", "PARTIAL") for x in states):
        return "PARTIAL"
    return "ERROR"


def upstox(now):
    token = os.environ.get("UPSTOX_ACCESS_TOKEN")
    if not token:
        return {"status": "SKIPPED_NOT_CONFIGURED", "reason": "UPSTOX_ACCESS_TOKEN absent", "symbols": {}}
    headers = {"Authorization": f"Bearer {token}"}
    report = {"status": "ERROR", "provider": "Upstox", "symbols": {}}
    zone, zone_basis = venue_zone("Asia/Kolkata")
    today = now.astimezone(zone).date()
    for symbol in INDIA:
        row = {"provider": "Upstox", "symbol": symbol, "result_status": "ERROR", "adjustment_mode": "provider_unspecified"}
        try:
            found, lookup = get_json("api.upstox.com", "/v2/instruments/search",
                                     {"query": symbol, "exchanges": "NSE", "segments": "EQ", "page_number": 1, "records": 20}, headers)
            row["lookup"] = lookup
            data = mapping(found).get("data")
            if lookup.get("http_status") == 200 and not isinstance(data, list):
                row["note"] = "MALFORMED_INSTRUMENT_RESPONSE"
            choices = [x for x in records(data) if isinstance(x, dict) and x.get("trading_symbol") == symbol
                       and x.get("segment") == "NSE_EQ" and x.get("exchange") == "NSE"]
            row["exact_matches_on_page"] = len(choices)
            page = mapping(mapping(mapping(found).get("meta_data")).get("page"))
            row["pagination"] = {"page_number": page.get("page_number"), "total_pages": page.get("total_pages"),
                                 "complete_search": page.get("total_pages") == 1}
            if len(choices) != 1:
                row.setdefault("note", "NO_EXACT_MATCH_OR_AMBIGUOUS_PAGE")
            else:
                instrument = choices[0]
                key = instrument.get("instrument_key")
                row.update({"native_instrument_key": key, "venue": "NSE", "isin": instrument.get("isin")})
                if isinstance(key, str) and key.startswith("NSE_EQ|"):
                    base = f"/v3/historical-candle/{urllib.parse.quote(key, safe='')}/days/1/"
                    recent, recent_meta = get_json("api.upstox.com", base +
                        f"{today.isoformat()}/{(today - dt.timedelta(days=60)).isoformat()}", headers=headers)
                    old, old_meta = get_json("api.upstox.com", base + "2017-01-01/2016-01-01", headers=headers)
                    row["daily_requests"] = {"recent": recent_meta, "2016_sample": old_meta}
                    def candles(obj):
                        result = mapping(mapping(obj).get("data")).get("candles")
                        return records(result)
                    recent_candles, old_candles = candles(recent), candles(old)
                    timestamps = [c[0] for c in recent_candles + old_candles
                                  if isinstance(c, list) and c and isinstance(c[0], str)]
                    row["history_sample"] = span(timestamps)
                    row["latest_complete_daily_candle_utc"] = conservative_complete(
                        [c[0] for c in recent_candles if isinstance(c, list) and c and isinstance(c[0], str)],
                        zone, today)
                    row["timestamp_format"] = "ISO8601_offset_or_Z" if row["history_sample"]["sample_count"] else None
                    row["session_note"] = "NSE-local session; current local day excluded conservatively"
                    row["timezone_basis"] = zone_basis
                    if recent_meta.get("http_status") == 200 and not isinstance(mapping(recent).get("data"), dict):
                        row["note"] = "MALFORMED_CANDLE_RESPONSE"
                    if recent_candles and row["history_sample"]["sample_count"]:
                        row["result_status"] = "SUCCESS" if row["pagination"]["complete_search"] else "PARTIAL"
                    elif not row.get("note"):
                        row["note"] = "NO_VALID_RECENT_DAILY_CANDLES"
                else:
                    row["note"] = "MISSING_OR_UNEXPECTED_NATIVE_KEY"
        except Exception:  # a bad provider row must not stop remaining symbols; no exception text leaks
            row["note"] = "UNEXPECTED_PROBE_ERROR"
        report["symbols"][symbol] = row
    report["status"] = status_from(report["symbols"])
    return report


def alpaca(now):
    key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        return {"status": "SKIPPED_NOT_CONFIGURED", "reason": "APCA_API_KEY_ID or APCA_API_SECRET_KEY absent", "symbols": {}}
    environment = os.environ.get("ALPACA_TRADING_ENV", "paper").lower()
    if environment not in ("paper", "live"):
        return {"status": "SKIPPED_NOT_CONFIGURED", "reason": "ALPACA_TRADING_ENV must be paper or live", "symbols": {}}
    asset_host = "paper-api.alpaca.markets" if environment == "paper" else "api.alpaca.markets"
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    report = {"status": "ERROR", "provider": "Alpaca", "requested_feed": "iex", "trading_api_environment": environment, "symbols": {}}
    zone, zone_basis = venue_zone("America/New_York")
    today = now.astimezone(zone).date()
    for symbol in US:
        row = {"provider": "Alpaca", "symbol": symbol, "result_status": "ERROR", "requested_feed": "iex",
               "adjustment_mode": "raw"}
        try:
            asset, asset_meta = get_json(asset_host, f"/v2/assets/{symbol}", headers=headers)
            asset = mapping(asset)
            row.update({"asset_lookup": asset_meta, "native_asset_id": asset.get("id"),
                        "venue": asset.get("exchange"), "asset_status": asset.get("status")})
            base = f"/v2/stocks/{symbol}/bars"
            params = {"timeframe": "1Day", "feed": "iex", "adjustment": "raw"}
            old, old_meta = get_json("data.alpaca.markets", base,
                                     {**params, "start": "2000-01-01", "end": now.date().isoformat(), "limit": 1}, headers)
            recent, recent_meta = get_json("data.alpaca.markets", base,
                {**params, "start": (now.date()-dt.timedelta(days=60)).isoformat(), "end": now.date().isoformat(), "limit": 100}, headers)
            row["daily_requests"] = {"old_sample": old_meta, "recent": recent_meta}
            old_bars, recent_bars = records(mapping(old).get("bars")), records(mapping(recent).get("bars"))
            times = [b.get("t") for b in old_bars + recent_bars if isinstance(b, dict) and isinstance(b.get("t"), str)]
            row["history_sample"] = span(times)
            row["latest_complete_daily_candle_utc"] = conservative_complete(
                [b.get("t") for b in recent_bars if isinstance(b, dict) and isinstance(b.get("t"), str)],
                zone, today, fallback=zone_basis != "IANA")
            row["timestamp_format"] = "RFC3339_offset_or_Z" if row["history_sample"]["sample_count"] else None
            row["session_note"] = "US equity daily timestamp; current New York date excluded conservatively when IANA data available"
            row["timezone_basis"] = zone_basis
            row["pagination"] = {"next_page_token_present": bool(mapping(recent).get("next_page_token")),
                                 "old_sample_next_page_token_present": bool(mapping(old).get("next_page_token")),
                                 "exhausted": False}
            row["tested_feed_class"] = "iex" if recent_meta.get("http_status") == 200 and recent_bars else None
            if recent_meta.get("http_status") == 200 and not isinstance(mapping(recent).get("bars"), list):
                row["note"] = "MALFORMED_BARS_RESPONSE"
            if recent_bars and row["history_sample"]["sample_count"]:
                row["result_status"] = "SUCCESS" if asset_meta.get("http_status") == 200 and asset.get("id") else "PARTIAL"
            elif not row.get("note"):
                row["note"] = "NO_VALID_RECENT_DAILY_BARS"
            if symbol in ("AAPL", "NVDA"):
                comparison = {}
                for mode in ("raw", "split"):
                    payload, meta = get_json("data.alpaca.markets", base,
                        {"timeframe": "1Day", "feed": "iex", "adjustment": mode,
                         "start": "2020-01-02", "end": "2020-01-10", "limit": 10}, headers)
                    bars = records(mapping(payload).get("bars"))
                    first = next((b for b in bars if isinstance(b, dict) and b.get("t") and b.get("c") is not None), None)
                    comparison[mode] = {"request": meta, "timestamp": first.get("t") if first else None,
                                        "sample_close": first.get("c") if first else None}
                comparison["same_timestamp"] = bool(comparison["raw"]["timestamp"] and
                    comparison["raw"]["timestamp"] == comparison["split"]["timestamp"])
                row["raw_vs_split_sample"] = comparison
            if symbol == "AAPL":
                sip, sip_meta = get_json("data.alpaca.markets", base,
                    {"timeframe": "1Day", "feed": "sip", "adjustment": "raw", "start": "2020-01-02",
                     "end": "2020-01-10", "limit": 1}, headers)
                row["sip_historical_probe"] = {"request": sip_meta,
                    "historical_sample_returned": bool(records(mapping(sip).get("bars"))),
                    "real_time_sip_entitlement": "UNKNOWN"}
        except Exception:
            row["note"] = "UNEXPECTED_PROBE_ERROR"
        report["symbols"][symbol] = row
    report["status"] = status_from(report["symbols"])
    return report


def binance(now):
    report = {"status": "ERROR", "provider": "Binance Spot", "symbols": {}}
    now_ms = int(now.timestamp() * 1000)
    for symbol in CRYPTO:
        row = {"provider": "Binance Spot", "symbol": symbol, "result_status": "ERROR", "venue": "Binance Spot"}
        try:
            info, info_meta = get_json("data-api.binance.vision", "/api/v3/exchangeInfo", {"symbol": symbol})
            symbols = records(mapping(info).get("symbols"))
            asset = next((x for x in symbols if isinstance(x, dict) and x.get("symbol") == symbol), {})
            old, old_meta = get_json("data-api.binance.vision", "/api/v3/klines",
                                     {"symbol": symbol, "interval": "1d", "startTime": 0, "limit": 1})
            recent, recent_meta = get_json("data-api.binance.vision", "/api/v3/klines",
                                           {"symbol": symbol, "interval": "1d", "limit": 3})
            row.update({"exchange_info": info_meta, "native_symbol": asset.get("symbol"),
                        "asset_status": asset.get("status"), "base_asset": asset.get("baseAsset"),
                        "quote_asset": asset.get("quoteAsset"), "daily_requests": {"old_sample": old_meta, "recent": recent_meta},
                        "timestamp_format": "Unix_epoch_milliseconds", "timezone_session": "UTC_midnight_1d_kline",
                        "pagination": "startTime/endTime cursor; not exhausted", "adjustment_mode": "raw_exchange_klines"})
            def valid_bars(items):
                return [x for x in records(items) if isinstance(x, list) and len(x) >= 7
                        and isinstance(x[0], int) and isinstance(x[6], int)]
            old_bars, recent_bars = valid_bars(old), valid_bars(recent)
            complete = [bar for bar in recent_bars if bar[6] < now_ms]
            def utc(milliseconds):
                try:
                    return dt.datetime.fromtimestamp(milliseconds / 1000, dt.timezone.utc).isoformat()
                except (ValueError, OverflowError, OSError):
                    return None
            times = [utc(bar[0]) for bar in old_bars + complete]
            times = [t for t in times if t]
            row["history_sample"] = span(times)
            row["latest_complete_daily_candle_utc"] = utc(max(complete, key=lambda b: b[0])[0]) if complete else None
            row["daily_anchor_observed_utc_midnight"] = (all(bar[0] % 86_400_000 == 0 for bar in old_bars + complete)
                                                          if old_bars or complete else None)
            if info_meta.get("http_status") == 200 and not isinstance(mapping(info).get("symbols"), list):
                row["note"] = "MALFORMED_EXCHANGE_INFO"
            if recent_meta.get("http_status") == 200 and not isinstance(recent, list):
                row["note"] = "MALFORMED_KLINES_RESPONSE"
            if asset and complete:
                row["result_status"] = "SUCCESS"
            elif not row.get("note"):
                row["note"] = "NO_RESOLVED_SYMBOL_OR_COMPLETE_DAILY_KLINE"
        except Exception:
            row["note"] = "UNEXPECTED_PROBE_ERROR"
        report["symbols"][symbol] = row
    result = status_from(report["symbols"])
    report["status"] = "PUBLIC_TESTED" if result == "ACCOUNT_TESTED" else result
    return report


def build_report(now):
    providers = {}
    for name, function in (("upstox", upstox), ("alpaca", alpaca), ("binance", binance)):
        try:
            providers[name] = function(now)
        except Exception:
            providers[name] = {"status": "ERROR", "error": "UNEXPECTED_PROBE_ERROR", "symbols": {}}
    return {"report_version": "0.6.1", "generated_at_utc": now.isoformat(), "machine_os": sys.platform,
            "notice": "Small read-only samples only; full history, production reliability, rights and realtime entitlements unverified.",
            "providers": providers}


def redact_report(value):
    """Last-resort scrub if an upstream response unexpectedly echoes a credential."""
    secrets = [os.environ.get(name) for name in ("UPSTOX_ACCESS_TOKEN", "APCA_API_KEY_ID", "APCA_API_SECRET_KEY")]
    secrets = sorted((secret for secret in secrets if secret), key=len, reverse=True)
    def scrub(item):
        if isinstance(item, str):
            for secret in secrets:
                item = item.replace(secret, "[REDACTED]")
            return item
        if isinstance(item, dict):
            return {scrub(k): scrub(v) for k, v in item.items()}
        if isinstance(item, list):
            return [scrub(v) for v in item]
        return item
    return scrub(value)


def write_report(report, output):
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".probe-",
                                         suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(redact_report(report), handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Make read-only GET calls")
    parser.add_argument("--output", default="data/probes/phase_0_6_local.json", help="Redacted JSON report path")
    args = parser.parse_args(argv)
    if not args.run:
        print("Dry run only. Add --run to make GET-only market-data requests. No report written.")
        return 0
    try:
        report = build_report(dt.datetime.now(dt.timezone.utc))
        write_report(report, args.output)
    except OSError:
        print("Could not write the redacted report. Check output directory permissions.", file=sys.stderr)
        return 2
    print("Read-only probe finished; redacted JSON report written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
