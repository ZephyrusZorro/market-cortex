"""Hermetic safety and summary tests for the Phase 0.6 feasibility probe."""
import importlib.util
import os
from pathlib import Path
from unittest import TestCase, main, mock

spec = importlib.util.spec_from_file_location("probe", Path(__file__).resolve().parents[1] / "scripts" / "probe_sources.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeSafety(TestCase):
    def test_fixed_host_rejects_unlisted_host(self):
        with self.assertRaises(AssertionError):
            probe.get_json("evil.example", "/orders")

    def test_credentialless_providers_skip_without_network(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(probe, "get_json") as request:
            self.assertEqual(probe.upstox(None)["status"], "SKIPPED_NO_CREDENTIAL")
            self.assertEqual(probe.alpaca(None)["status"], "SKIPPED_NO_CREDENTIAL")
            request.assert_not_called()

    def test_sample_range_never_claims_full_history(self):
        self.assertEqual(probe.span(["2020-01-01", "2021-01-01"])["full_history_verified"], False)
        self.assertEqual(probe.span([])["sampled_earliest_timestamp"], None)

    def test_public_crypto_probe_uses_only_get_endpoints(self):
        calls = []
        def fake(host, path, params=None, headers=None):
            calls.append((host, path))
            return ({} if path.endswith("exchangeInfo") else []), {"http_status": 200}
        with mock.patch.object(probe, "get_json", side_effect=fake):
            report = probe.binance(None)
        self.assertEqual(len(report["symbols"]), 5)
        self.assertTrue(all(host == "data-api.binance.vision" and path in ("/api/v3/exchangeInfo", "/api/v3/klines") for host, path in calls))
        self.assertIsNone(report["symbols"]["BTCUSDT"]["daily_anchor_observed_utc_midnight"])


if __name__ == "__main__":
    main()
