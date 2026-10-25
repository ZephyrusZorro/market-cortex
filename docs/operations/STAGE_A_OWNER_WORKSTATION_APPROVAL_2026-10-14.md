# Stage A — owner workstation integration approval proposal

Prepared 2026-10-14. **Independent cached production-browser acceptance passed. Owner deployment is not approved or performed.** Technical evidence: `THREE_MARKET_BROWSER_ACCEPTANCE_2026-10-14.md`; detailed design: `THREE_MARKET_OWNER_INTEGRATION_PROPOSAL.md`.

## Exact requested authorization

Authorize only Stage A: a backup-first candidate installation adding the native three-market Explorer to the owner workstation, with separate source storage, restricted provider reads and bounded acceptance captures. **No owner database record writes, canonical broker imports, continuous collectors, schedules, trading endpoints, push or release/tag changes.** Stage B and C remain separate decisions.

### 1. Protect and inspect owner state

- Fresh read-only owner inventory: all tables/full row fingerprints, migration ledger/checksums/schema/head, manifests/Parquets and the saved research replay. Compare with the last accepted receipts; stop on material difference.
- Create and retain a new encrypted current-owner backup; restore that specific bundle into a new isolated UTF8 recovery database and unique data directory. Verify every table fingerprint, migration/storage hash and saved research evidence. Do not overwrite/drop/reset owner, pilot, any backup or existing restore target.
- Rehearse an encrypted export/isolated restore for the new source-cache tree as part of candidate acceptance. The existing owner protection tool does **not** yet cover this separate tree. A source-backup implementation and successful drill are required before cutover; copying the review bundle is not an encrypted-backup claim.
- Private owner connection/passphrase operations and any execution-review-blocked launcher must use the existing owner-terminal procedure. No credential/passphrase is displayed or requested in chat. Recovery-cluster unavailability stops the procedure; no database instance or pilot is recreated.

### 2. Prepare a separate candidate

- Preserve operational tag `v1.0.1-operational`, commit `cfe696d`, current installation/build/dependency inventory, OWNER_MAIN and PILOT_TEST.
- Build a versioned candidate alongside the existing installation. Keep the owner's current `.next` intact. Record exact code/build/config/dependency hashes before running acceptance.
- Proposed source root: `C:\MarketCortexSources\three-market-v1\<operation-id>`, **512 MiB ceiling**, no automatic evidence deletion. Source API port **8678**, distinct from independent 8677 and owner API 8765. It receives no owner/pilot database connection.
- Preserve original independent evidence provenance. Record an explicit approved installation/profile receipt; do not silently relabel old manifests or treat their independent marker as owner acceptance.
- Reuse all three verified native catalog snapshots: **73,494 searchable records** in this baseline. Suspended/inactive/ambiguous records remain labeled; only exact provider-native IDs identify fetched evidence. Do not create 73,494 canonical SQL identities.

### 3. Restrict new source-cache observations

Existing Binance owner daily datasets and research records remain intact; no Binance onboarding/backfill is repeated.

New broker source observations are limited to these seven listings:

| Listing | Exact native ID |
|---|---|
| RELIANCE / NSE | `NSE_EQ|INE002A01018` |
| RELIANCE / BSE | `BSE_EQ|INE002A01018` |
| INFY / NSE | `NSE_EQ|INE009A01021` |
| INFY / BSE | `BSE_EQ|INE009A01021` |
| AAPL / NASDAQ listing | `b0b6dd9d-8b9b-48a9-ba46-b9d54906e415` |
| SPY / ARCA listing | `b28f4066-5c6d-479b-a2af-85dc1a8f16fb` |
| QQQ / NASDAQ listing | `2d9e926c-e17c-47c3-ad8c-26c7a594e48f` |

- Daily only: **October 1, 2026 inclusive through October 14 exclusive**, interpreted in the provider's native market timezone. At most **91 accepted source daily rows**; actual observations may be fewer. This is a bound, not a calendar-derived forecast.
- At most **42 history/comparison GET attempts**, **21 metadata GET attempts**, **18 Upstox stream-authorization GET attempts**: total at most **81 provider GET attempts** across the acceptance operation. No bulk history download.
- Load existing matching current-user DPAPI credentials only into the scoped acceptance/service process; restore previous process environment afterward. Do not persist secrets in the source cache, database, UI, reports or command line.
- Source-cache writes only. Canonical identity/calendar/corporate-action imports, migration/job/research writes and adjusted-data fabrication are excluded. Upstox remains `provider_unspecified`; Alpaca remains raw IEX and explicitly not consolidated/NBBO.
- Bind the candidate's backend to an explicit fetch scope. The tested `FetchScope` can deny any other provider/native ID/interval/date range before a network call. The current independent CLI does not load an owner scope automatically. **Verify candidate binding with unapproved-symbol/date tests before enabling credentialed fetches.** No automatic unbounded fetch should be triggered by selecting another discovered instrument.
- The existing browser's `NOT_CONFIGURED` diagnostics are expected because this independent service has no broker credentials. Owner credential loading would be part of approved A; it has not happened during browser acceptance.

### 4. Bounded real-feed and candidate acceptance

- One **120-second** capture per provider: Binance BTCUSDT/ETHUSDT; the four selected Indian listings; AAPL/SPY/QQQ on IEX. At most 200,000 events/provider, one socket/provider, five reconnects and existing provider rate budgets. Captures end explicitly; no collector remains active.
- India must be tested during an authoritative active exchange session. Authentication or an old last-trade snapshot cannot satisfy fresh-event acceptance. US quotes/prices are attributed to IEX separately from listing exchange; unavailable/no-event outcomes are recorded honestly.
- Check all seven selected broker historical charts against fresh approved provider responses and verify exact rendered readouts/tooltips, native timestamps, volume/adjustment/feed attribution and manifest lineage. Calendar/source-window uncertainty remains visible; native-cache charts do not become canonical equity research.
- Recheck clean production browser errors, search/status/pagination, unsupported/uncached symbols, provider expiry/denial, cache idempotence, quota exhaustion, pinned as-of evidence and owner/pilot isolation.
- Performance gates: first cached chart ≤1.5 s, cached switch ≤750 ms, search ≤1 s, warm API p95 ≤250 ms. These passed in the independent four-chart acceptance; **the actual owner candidate must pass again**.
- No continuous collection, automatic gap recovery, Windows task/logon startup or broader on-demand universe write permission is included. Gap/reconnect evidence must not silently fill ticks/quotes.

### 5. Owner cutover only after gates pass

Use the accepted candidate for owner UI **3000** / owner API **8765**, routing only the new native Explorer to the separate source service **8678**. Preserve the independent UI/API and pilot. Keep all original owner research/evidence reproducible; verify unchanged owner fingerprints, ledger/head/storage/research replay after startup and controlled restart.

If a gate fails, stop and retain every receipt, encrypted backup, candidate and partial source artifact. Do not modify migration history, reset/restore over owner or attempt an unverified data rollback. Application recovery uses the preserved installation/launcher and separately reviewed process/routing reversal; no database rollback is implied.

## Approval wording

**“Authorize Stage A only as scoped in `STAGE_A_OWNER_WORKSTATION_APPROVAL_2026-10-14.md`, with all backup, isolation, source-fetch and candidate acceptance gates enforced. Do not execute Stage B or C, enable schedules/continuous collectors, perform owner database record writes, push or change the operational release.”**

This proposal is an authorization request, not an executable operations profile or a claim that those owner gates have already passed. No owner-terminal action is required before the approval decision.
