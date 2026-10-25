# Secure local multi-market credential onboarding

**Next stage prepared after actual Binance production acceptance, 2026-10-14.** See `PRODUCTION_MARKET_VALIDATION_2026-10-14.md`. The remaining boundary is private broker credential entry and real authenticated observations. No owner import or experimental owner deployment is authorized by this procedure.

No owner database connection is needed. Keep the existing owner/pilot terminals and applications unchanged. Never paste credentials, passphrases or database URLs into chat, `.env` files, JSON profiles or source control.

## Credentials to obtain

**Upstox:** Sign in to [Developer Apps](https://account.upstox.com/developer/apps), open Analytics and generate the free read-only Analytics Token. Configure it as `UPSTOX_ACCESS_TOKEN`. A standard OAuth access token is not required for this onboarding. Confirm the displayed expiry and retain it privately; the documented Analytics Token validity is one year.

**Alpaca:** Create/sign in to an eligible Alpaca account, choose the free Basic data plan and generate a **paper-account API key ID and secret** in its dashboard. Configure `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`; `MARKET_CORTEX_ALPACA_ACCOUNT=paper` selects the matching GET-only asset host. Do not supply a paper key with live mode. The application does not call account, orders or position endpoints. No paid subscription is required or automatically enabled.

## Exact owner-executed commands

Run in a fresh PowerShell terminal. These commands use hidden prompts and create unique current-user DPAPI files under `%LOCALAPPDATA%\MarketCortex\Secrets`, outside the repository/OneDrive. Prior secret files are preserved. The file path is safe to show; its contents and plaintext values are private. DPAPI decryption requires the same Windows user.

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
$taskUpstoxCredentialFile = & .\scripts\Set-MarketDataCredentials.ps1 -Provider upstox
& .\scripts\Invoke-MultiMarketProbe.ps1 -Provider upstox -CredentialFile $taskUpstoxCredentialFile
```

For Alpaca, when its keys are available:

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
$ErrorActionPreference = 'Stop'
$taskAlpacaCredentialFile = & .\scripts\Set-MarketDataCredentials.ps1 -Provider alpaca -AlpacaAccount paper
& .\scripts\Invoke-MultiMarketProbe.ps1 -Provider alpaca -CredentialFile $taskAlpacaCredentialFile
```

An optional additional delayed-SIP probe is explicit:

```powershell
& .\scripts\Invoke-MultiMarketProbe.ps1 -Provider alpaca -CredentialFile $taskAlpacaCredentialFile -DelayedSip
```

The probe temporarily loads only the relevant credential variables, restores prior values in `finally`, and does not persist plaintext. It uses a new independent archive for metadata/history/events. Existing owner data, pilot data, backups, applications and schedules are untouched.

## What the receipt means

Receipts are `runtime\multi-market-probe-<id>.json`. They include authentication/sample status, full metadata count/hash, actual OHLCV sample availability, conservative rate-limit headers if returned, selected-feed connection/auth/subscription diagnostics, actual observed event counts, source hashes, timestamps and local integrity. A separate bounded GET compares all stored daily OHLCV values against fresh raw provider values, independently of the history normalizer. Empty history, missing/extra timestamps or changed values stop acceptance and preserve the original independent observations. No raw headers, secret values or signed WebSocket URLs are reported. No stress test is used to discover provider limits.

`AUTH_AND_FEED_PROBED` requires exact historical OHLCV comparison, confirmed feed authentication, confirmed subscriptions and a capture without a reported stream error. Authentication alone cannot pass the probe. If the optional delayed-SIP feed is requested, these same checks must pass for that feed. A successfully authenticated/subscribed connection with no market observations during closed hours does not prove live price accuracy; its `market_updates_observed` flag stays false. Actual received events and price/timestamp comparisons are a separate live acceptance gate. Indian/US calendar authority and corporate-action identity remain explicit review gates even after a successful source probe. Missing credentials produce `DEFERRED_NOT_CONFIGURED`; no fallback provider or simulated price is substituted.

## Prepared credentialed probe scope

Each command above uses a new unique `runtime/multi-market-probe-<id>` archive and receipt. It does not load keys into OWNER_MAIN or the already running explorer. Upstox uses the candidate NSE RELIANCE native identity, public catalog snapshots, about fourteen days of daily observations, one independent accuracy comparison and a bounded thirty-second V3 LTPC subscription. Alpaca uses the matching paper account, active/inactive US asset metadata, AAPL daily IEX history, one independent accuracy comparison and a bounded thirty-second IEX subscription. Optional delayed SIP remains a separate explicit probe and entitlement gate.

Alpaca paper API keys are standard account credentials. The application enforces its approved GET endpoint allowlist and does not call order, position or account mutation routes. Never select a paid plan as part of this procedure. Source entitlements are established from the actual receipt, not assumed from a successful HTTP login.

The October 14 regression includes a real Windows current-user DPAPI encryption/decryption and restricted-ACL roundtrip using an explicitly synthetic credential. That verifies local secret handling; it is not a live Upstox/Alpaca result. The loader restores parent environment values in `finally`, signed socket URLs and raw auth headers are not included in reports, and old credential/backup files are preserved.

Only credential creation/entry requires the owner. Return safe receipt paths afterward; all technical review, error diagnosis, provider comparisons and follow-up validation are agent work. Do not send secret values. If no credential is available, retain DEFERRED_NOT_CONFIGURED and do not rerun the unrelated Binance bootstrap or owner migration procedure.

## Official authentication and free-plan references

Rechecked October 14: [Upstox Analytics Token](https://upstox.com/developer/api-documentation/analytics-token/) documents free read-only GET access, one-year validity, and historical/WebSocket categories without a static IP. [Upstox V3 feed](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/) describes the binary/protobuf modes and connection/subscription constraints. [Alpaca Market Data](https://docs.alpaca.markets/us/docs/about-market-data-api) documents API-key/secret header authentication for individual accounts and the free Basic equities plan: IEX real-time coverage, thirty symbols and two hundred historical calls per minute. Full consolidated coverage and optional delayed feeds are not inferred from that plan; actual authorization must be observed.

If a probe fails, retain its receipt and source archive. Do not repeat owner onboarding or change owner migrations. Refresh/revoke a token in the provider dashboard when necessary, then create a new unique credential file. Report only the receipt path and safe error code.

## Before any owner import

After actual receipts pass, prepare an exact instrument/mapping/session scope, ranges, intervals, adjustment policy, expected bar/file counts, observed bytes/bar, request budget, retention and recovery plan. Reconcile ambiguous Indian series and US ticker/asset history first. Use the existing retained encrypted backup procedure for the inspected current owner state and an isolated restore gate. Obtain explicit authorization for the scoped owner writes. Do not use this credential probe as an owner-ingestion approval.
# Current probe review — 2026-10-14

Both secure owner-executed probes completed and their immutable archives have been audited. See `THREE_MARKET_PROBE_REVIEW_2026-10-14.md`. Credential setup is no longer the general blocker. Upstox fresh market-session events, canonical identities/calendars/source windows, retention rights and owner deployment remain gated. Reuse existing DPAPI files; successful probes do not authorize owner imports or background collection.

