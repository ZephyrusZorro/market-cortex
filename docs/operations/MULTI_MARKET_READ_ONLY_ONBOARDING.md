# Multi-market read-only readiness

Official documentation checked 2026-10-11. Upstox and Alpaca credentials are absent. Live authenticated validation remains **DEFERRED_NOT_CONFIGURED**; neither market has been ingested into OWNER_MAIN. The existing adapters/canonical contracts remain in place. No authentication POST, account mutation, order endpoint or broker SDK execution is added.

## Upstox

Preferred for this private research scope: the documented **Analytics Token**, generated manually under Developer Apps / Analytics. It is free, valid one year, read-only and supports historical data without static-IP whitelisting. One token/account is allowed; generating or revoking it is an owner action. Store its value only in the hidden local prompt; the adapter uses the existing `UPSTOX_ACCESS_TOKEN` environment name. Account eligibility and accepted data terms still need owner verification. [Official Analytics Token](https://upstox.com/developer/api-documentation/analytics-token/).

Standard OAuth remains compatible: interactive authorization-code flow or manual dashboard generation. Standard access tokens expire at 03:30 the following morning; do not assume one-year validity for them. Automated token exchange/refresh is outside the GET-only application boundary and is not implemented. [Authentication](https://upstox.com/developer/api-documentation/authentication/), [token lifetime](https://upstox.com/developer/api-documentation/get-token/).

Historical candles are standard APIs with published limits of 50 requests/second, 500/minute and 2,000/30 minutes, per API/user. Our small sequential samples are bounded below these limits; account-specific restrictions can still fail. [Rate limits](https://upstox.com/developer/api-documentation/rate-limiting/).

The adapter calls only GET `/v3/historical-candle/NSE_EQ%7C<key>/days/1/<inclusive-to>/<from>` using Bearer authorization. Daily availability is documented from January 2000 with up to a decade per request; that is a provider ceiling, not proof every listing has that history. Existing bounded 180-day chunks remain conservative. Adjustment is `provider_unspecified`, never mislabeled raw/adjusted. [Historical V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/).

The new probe uses GET instrument search and a 14-day daily sample. An exact unique result on one page is a **candidate native mapping**, not verified historical canonical identity. Keep ISIN, listing/exchange, validity/knowledge timestamps and evidence of renames/reused identifiers before ingestion. Upstox recommends `instrument_key`; `exchange_token` can be reused. [Instruments](https://upstox.com/developer/api-documentation/instruments/).

## Alpaca

Generate owner-controlled API credentials in Alpaca's dashboard and enter `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` through hidden prompts. Market data uses `data.alpaca.markets` with those two headers; no broker-host account/order request is needed. The application cannot narrow a broadly capable API key's account permissions; its transport enforces GET-only history paths. Do not assume paper credentials are inherently read-only. [Authentication and entitlement diagnostics](https://docs.alpaca.markets/us/docs/market-data-faq).

Basic is the documented free default plan: equities/ETFs, real-time IEX only, history since 2016, restricted latest 15 minutes, 200 historical calls/minute. These are published plan descriptions, not verified entitlements for this owner. No paid subscription is enabled. Closed daily IEX samples avoid recent-SIP access; IEX prices/volume are not the consolidated market. The adapter's optional SIP capability remains, but the onboarding probe requests only IEX. [Current subscription table](https://docs.alpaca.markets/us/docs/about-market-data-api).

GET `/v2/stocks/<ticker>/bars` specifies `1Day`, `feed=iex`, `adjustment=raw`. `asof=-` now disables provider automatic ticker-name remapping so canonical validity intervals govern identity. This provider `asof` parameter is distinct from MARKET CORTEX's observation knowledge cutoff. Historical ticker transitions still need explicit verified mappings. [Provider ticker mapping and feeds](https://docs.alpaca.markets/us/docs/market-data-faq).

## Canonical calendar and coverage gate

India requires verified XNSE cash-session records in Asia/Kolkata, including holidays and special sessions. NSE's published holiday page itself notes Muhurat timing follows a separate circular; weekdays alone are insufficient. US calendars require venue-specific sessions in America/New_York, DST, holidays and early closes. A price sample does not establish calendar authority. [NSE calendars/circulars](https://www.nseindia.com/resources/exchange-communication-holidays), [NYSE calendar/hours](https://www.nyse.com/trade/hours-calendars).

An optional `--bundle` uses typed `Instrument`, `IdentifierMapping`, `Venue`, `CalendarSession` contracts plus `calendar_id`, `calendar_version`, `sessions`, aware `start/end` (max 31 days), `identity_evidence` and `calendar_evidence` references. The existing adapter normalizes that sample in memory and reports missing declared sessions/duplicate sessions. References must be independently reviewed; the probe does not certify source authority. Missing calendar entries stop normalization. No fixture dates are inferred as real exchange sessions or written to owner storage.

## Secure independent probes

No credentials required to record the current deferred state:

```powershell
Set-Location 'C:\Users\faris\OneDrive\Documents\MARKET_CORTEX_Phase_1_Completed'
& .\scripts\Invoke-ProviderReadiness.ps1 -Provider upstox
& .\scripts\Invoke-ProviderReadiness.ps1 -Provider alpaca
```

When credentials become available, the owner may explicitly choose a local hidden-prompt sample:

```powershell
& .\scripts\Invoke-ProviderReadiness.ps1 -Provider upstox -Configure
& .\scripts\Invoke-ProviderReadiness.ps1 -Provider alpaca -Configure
```

Each provider runs independently; one failure does not require or call the other provider. The wrapper restores prior process environment values; credentials are not persisted or passed on command lines. Outputs are new exclusive `runtime\provider-<provider>-<uuid>.json` receipts with whitelisted codes, response hashes, sample span, feed and explicit identity/calendar/rights limitations. Raw responses, headers, credentials and exception bodies are excluded; redirects and non-allowlisted hosts/paths are rejected. HTTP 401/403 is ACCESS_DENIED without guessing invalid credential vs missing entitlement.

Optional typed adapter sampling: add `-Bundle '<absolute path to independently verified JSON bundle>'`. Do not put tokens, DSNs or personal broker data in that bundle. Sample coverage never asserts full historical coverage, realtime entitlement, redistribution permission or production readiness. Missing credentials are a deferred state, not success/failure fabrication.

Future OWNER_MAIN ingestion of either market requires explicit approval after authenticated samples, canonical mapping/calendar review, freshness/data-quality assessment, rights review and an isolated ingestion/replay acceptance gate. No migrations or owner market bootstrap occur here.
