# Owner recovery accepted and catalog latency remediation — 17 October 2026

**RECOVERED.** Original OWNER_MAIN is healthy at http://127.0.0.1:3000 with API http://127.0.0.1:8765. The approved ETHUSDT research run was reopened in the actual original browser and replayed: all six hashes match. The private post-recovery receipt matches all 51 table fingerprints, 13 migrations, 1,825 bars and one saved research record to the pre-cutover state. All 65 current Parquets independently match the verified owner restore. Another 198 original application core files and the original frontend build ID match the application recovery copy. Retained backups were verified by the successful private receipt. No collector locks, active source sockets, MarketCortex scheduled tasks, provider operations, imports, deployments or merges were introduced by recovery acceptance or the isolated investigation.

Final recovery evidence: `runtime/owner-final-recovery-acceptance-2026-10-17.json`. The original recovery state is `runtime/application-93578cf6a36a46a39509fc1f488204b9.json`; browser receipt and screenshot are `runtime/owner-recovery-browser-2026-10-17.json` / `.png`. All original and failed Stage A receipts remain retained.

The failed three-market cutover remains failed: real Alpaca catalog p95 267.6171 ms direct / 264.9893 ms proxy, above the unchanged 250 ms threshold. Stage A candidate 3019/8678 remains frozen and independent; no new OWNER_MAIN cutover was attempted.

## Isolated remediation delivered

Workspace: `C:\MarketCortexEngineering\stage-a-catalog-latency-2026-10-17`
Branch: `engineering/stage-a-catalog-latency-2026-10-17`
Commit: `cf0fab4d9f57e81e14b8f20196a06ff571a82583` (local only).

The confirmed avoidable work is repeated DuckDB connection creation, SQL scans and result decoding for identical immutable catalog searches. Legacy manifest traversal also consumes request time. The historical timing increase cannot be attributed completely to a software change because frozen code/catalog hashes did not change; host/workload/filesystem/transport effects remain unisolated.

The prototype caches query results per archive, bounded at 64 entries / 4 MiB of encoded payload. It still resolves manifests and validates artifact SHA256 on every request, including hits; snapshot/filter keys prevent stale revisions or cross-market results, and caller mutation cannot alter stored entries. Cold query behavior and API contracts are preserved.

Matched retained-data benchmarks (30 samples, no new server/provider access):

| Isolated workload | Before p95 | After p95 |
|---|---:|---:|
| Alpaca AAPL in-process API | 135.60 ms | 14.45 ms |
| Binance BTC in-process API | 70.55 ms | 10.69 ms |
| Upstox RELIANCE in-process API | 117.79 ms | 12.46 ms |
| Alpaca cache miss, direct function | 134.10 ms | 134.43 ms |

These results are not a replacement for production socket/Next.js acceptance. No new production success is claimed. Tests: 59 relevant passed, including 15 new cache integrity/bounds/revision tests. Two tests were deselected: an out-of-scope credential/DPAPI test and an existing deep Windows publication failure in unchanged frozen code. The latter must be addressed or scoped during future candidate review. No Track B/B2 fix was merged. An existing Starlette/httpx warning remains.

Before/after hashes verified 2,608 protected candidate/source/owner/evidence files unchanged. Main HEAD, operational tag and prior engineering branches remain isolated. No push or release was performed.

## Proposed next stage

Review the local fix, then prepare a separate cache-only candidate and test actual production HTTP plus Next.js proxy on unused isolated ports. Repeat the unchanged 250 ms gate with matched load and retained observations, plus browser/search/pagination/concurrency/corruption/freshness checks. Resolve the required remaining regression scope and preserve all failed measurements. Agent startup may require one owner-terminal execution because of the earlier automatic execution-review rejection. No broker credentials or provider requests are needed for this work. Return candidate acceptance evidence before requesting a separately authorized OWNER_MAIN cutover.

Full implementation, test limitations, reproducible commands and remediation procedure:
`C:\MarketCortexEngineering\stage-a-catalog-latency-2026-10-17\docs\operations\CATALOG_LATENCY_REMEDIATION_2026-10-17.md`
