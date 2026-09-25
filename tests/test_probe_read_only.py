"""Hermetic Phase 0.6 probe tests. No internet or credentials required."""
import datetime as dt
import importlib.util
import json
import os
import tempfile
import urllib.error
from pathlib import Path
from unittest import TestCase, main, mock

spec = importlib.util.spec_from_file_location("probe", Path(__file__).resolve().parents[1] / "scripts" / "probe_sources.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
NOW = dt.datetime(2026, 9, 26, 12, 0, tzinfo=dt.timezone.utc)


class FakeResponse:
    status = 200
    headers = {}
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, _limit):
        return self.body


class ProbeTests(TestCase):
    def test_only_allowlisted_read_paths(self):
        for host, path in (("evil.example", "/api/v3/klines"),
                           ("data-api.binance.vision", "/api/v3/order"),
                           ("api.upstox.com", "/v2/order/place"),
                           ("paper-api.alpaca.markets", "/v2/orders")):
            with self.assertRaises(ValueError):
                probe.get_json(host, path)

    def test_missing_credentials_skip_and_binance_still_runs(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(probe, "get_json", return_value=(None, {"error": "TIMEOUT"})) as call:
            report = probe.build_report(NOW)
        self.assertEqual(report["providers"]["upstox"]["status"], "SKIPPED_NOT_CONFIGURED")
        self.assertEqual(report["providers"]["alpaca"]["status"], "SKIPPED_NOT_CONFIGURED")
        self.assertEqual(report["providers"]["binance"]["status"], "ERROR")
        self.assertEqual(len(call.call_args_list), 15)
        self.assertTrue(all(c.args[0] == "data-api.binance.vision" for c in call.call_args_list))

    def test_http_request_is_get_only(self):
        seen = []
        class Opener:
            def open(self, request, timeout):
                seen.append((request.get_method(), request.full_url, timeout))
                return FakeResponse(b"[]")
        with mock.patch.object(probe.urllib.request, "build_opener", return_value=Opener()):
            payload, meta = probe.get_json("data-api.binance.vision", "/api/v3/klines", {"symbol": "BTCUSDT"})
        self.assertEqual(payload, [])
        self.assertEqual(meta["http_status"], 200)
        self.assertEqual(seen[0][0], "GET")
        self.assertEqual(seen[0][2], probe.TIMEOUT_SECONDS)
        self.assertIn("/api/v3/klines", seen[0][1])

    def test_windows_without_tzdata_uses_labeled_conservative_fallback(self):
        with mock.patch.object(probe, "ZoneInfo", side_effect=probe.ZoneInfoNotFoundError("missing")):
            zone, basis = probe.venue_zone("America/New_York")
            self.assertEqual(basis, "UTC_fallback_without_tzdata")
            self.assertEqual(zone, dt.timezone.utc)
            self.assertIsNone(probe.conservative_complete(["2026-09-25T04:00:00Z"], zone,
                                                           dt.date(2026, 9, 26), fallback=True))

    def test_timeout_is_safe_metadata_without_exception_message(self):
        class Opener:
            def open(self, request, timeout):
                self.request = request
                raise TimeoutError("secret-in-exception-text")
        with mock.patch.object(probe.urllib.request, "build_opener", return_value=Opener()):
            payload, meta = probe.get_json("data-api.binance.vision", "/api/v3/klines", {"symbol": "BTCUSDT"})
        self.assertIsNone(payload)
        self.assertEqual(meta, {"error": "TIMEOUT"})
        self.assertNotIn("secret-in-exception-text", json.dumps(meta))

    def test_malformed_json_and_shape_do_not_crash(self):
        class Opener:
            def open(self, request, timeout):
                return FakeResponse(b"{broken")
        with mock.patch.object(probe.urllib.request, "build_opener", return_value=Opener()):
            payload, meta = probe.get_json("data-api.binance.vision", "/api/v3/exchangeInfo")
        self.assertIsNone(payload)
        self.assertEqual(meta["error"], "MALFORMED_JSON")
        with mock.patch.object(probe, "get_json", return_value=({"data": None}, {"http_status": 200})), \
             mock.patch.dict(os.environ, {"UPSTOX_ACCESS_TOKEN": "private-token"}):
            rows = probe.upstox(NOW)["symbols"]
        self.assertEqual(rows["RELIANCE"]["note"], "MALFORMED_INSTRUMENT_RESPONSE")
        self.assertEqual(len(rows), 6)

    def test_representative_upstox_lookup_uses_native_key(self):
        calls = []
        def fake(host, path, params=None, headers=None):
            calls.append((host, path, params))
            if path == "/v2/instruments/search":
                return {"data": [{"trading_symbol": params["query"], "segment": "NSE_EQ", "exchange": "NSE",
                                  "instrument_key": "NSE_EQ|INE000000001", "isin": "INE000000001"}],
                        "meta_data": {"page": {"page_number": 1, "total_pages": 1}}}, {"http_status": 200}
            return {"data": {"candles": [["2026-09-24T15:30:00+05:30", 1, 2, 1, 2, 100]]}}, {"http_status": 200}
        with mock.patch.object(probe, "get_json", side_effect=fake), mock.patch.dict(os.environ, {"UPSTOX_ACCESS_TOKEN": "private-token"}):
            result = probe.upstox(NOW)
        self.assertEqual(result["status"], "ACCOUNT_TESTED")
        self.assertEqual(result["symbols"]["M&M"]["native_instrument_key"], "NSE_EQ|INE000000001")
        self.assertTrue(any("NSE_EQ%7CINE000000001" in path for _, path, _ in calls))

    def test_representative_alpaca_feed_and_split_comparison(self):
        def fake(host, path, params=None, headers=None):
            if "/assets/" in path:
                return {"id": "asset-id", "exchange": "NASDAQ", "status": "active"}, {"http_status": 200}
            price = 10 if params["adjustment"] == "split" else 40
            return {"bars": [{"t": "2020-01-03T05:00:00Z", "c": price}], "next_page_token": "opaque"}, {"http_status": 200}
        with mock.patch.object(probe, "get_json", side_effect=fake), mock.patch.dict(os.environ, {"APCA_API_KEY_ID": "key-private", "APCA_API_SECRET_KEY": "secret-private"}):
            result = probe.alpaca(NOW)
        self.assertEqual(result["status"], "ACCOUNT_TESTED")
        row = result["symbols"]["AAPL"]
        self.assertEqual(row["tested_feed_class"], "iex")
        self.assertEqual(row["raw_vs_split_sample"]["split"]["sample_close"], 10)
        self.assertEqual(row["sip_historical_probe"]["real_time_sip_entitlement"], "UNKNOWN")

    def test_representative_binance_status_and_complete_bar(self):
        open_ms = int(dt.datetime(2026, 9, 24, tzinfo=dt.timezone.utc).timestamp() * 1000)
        def fake(host, path, params=None, headers=None):
            if path.endswith("exchangeInfo"):
                return {"symbols": [{"symbol": params["symbol"], "status": "TRADING", "baseAsset": "BTC", "quoteAsset": "USDT"}]}, {"http_status": 200}
            return [[open_ms, "1", "2", "1", "2", "100", open_ms + 86_399_999]], {"http_status": 200}
        with mock.patch.object(probe, "get_json", side_effect=fake):
            result = probe.binance(NOW)
        self.assertEqual(result["status"], "PUBLIC_TESTED")
        self.assertEqual(result["symbols"]["BTCUSDT"]["asset_status"], "TRADING")
        self.assertTrue(result["symbols"]["BTCUSDT"]["daily_anchor_observed_utc_midnight"])

    def test_cli_run_creates_requested_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "data" / "probes" / "phase_0_6_local.json"
            with mock.patch.object(probe, "build_report", return_value={"providers": {}}):
                self.assertEqual(probe.main(["--run", "--output", str(target)]), 0)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"providers": {}})

    def test_output_redaction_and_parent_directory(self):
        private = {"UPSTOX_ACCESS_TOKEN": "TOKEN_DO_NOT_WRITE_29381", "APCA_API_KEY_ID": "KEY_DO_NOT_WRITE_1879",
                   "APCA_API_SECRET_KEY": "SECRET_DO_NOT_WRITE_3902"}
        with mock.patch.dict(os.environ, private), mock.patch.object(probe, "get_json", return_value=(None, {"error": "TIMEOUT"})):
            report = probe.build_report(NOW)
        # Simulate a provider unexpectedly echoing a credential in an ID field.
        report["providers"]["alpaca"]["echoed_id"] = private["APCA_API_SECRET_KEY"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data" / "probes" / "phase_0_6_local.json"
            with mock.patch.dict(os.environ, private):
                probe.write_report(report, path)
            contents = path.read_text(encoding="utf-8")
            self.assertEqual(json.loads(contents)["providers"]["binance"]["status"], "ERROR")
            for value in private.values():
                self.assertNotIn(value, contents)
            self.assertIn("[REDACTED]", contents)
            self.assertFalse(list(path.parent.glob(".probe-*.tmp")))


if __name__ == "__main__":
    main()
