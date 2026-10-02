# Provider Usage Notes — private local research only

This is a short operational check, not a commercial compliance review. No order or broker execution operations are planned. Actual tier and retention terms must be checked in the owner's account before sustained ingestion. Third-party data rights and request limits can still affect a private cache.

| Candidate | Tier / auth | Practical request and caching notes | Status |
| --- | --- | --- | --- |
| [Upstox V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/) | Owner account bearer token via `UPSTOX_ACCESS_TOKEN`; exact tier unknown | Per-instrument coverage, timestamps, adjustment behavior and API usage terms need account verification. Cache policy/account access to verify. | `DEFERRED_NOT_CONFIGURED`; adapter mocked only. |
| [Alpaca](https://docs.alpaca.markets/us/reference/stockbars) | API key/secret in environment; adapter requests `iex` and `raw` by default; exact account tier unknown | Response may vary by feed/tier. Confirm private storage terms and desired SIP/IEX coverage. | `DEFERRED_NOT_CONFIGURED`; adapter mocked only. |
| [Binance Spot public market API](https://developers.binance.com/en/docs/products/spot/rest-api) | Public endpoint, no key for market data | IP-weight limits and 429 handling; verify owner-region access and local caching terms. Do not infer permission from public reachability. | Public read-only probe and bounded five-pair ingest tested 2026-10-03; retention rights pending. |
| [Coinbase Exchange public API](https://docs.cdp.coinbase.com/exchange/rest-api/requests) | Public market requests; exchange-specific products | Candidate fallback only; USD pairs may differ from Binance USDT pairs; verify rate/cache rules on selection. | Documentation verified; remote probe blocked; owner untested. |

No provider is production validated. Secrets are never written to `owner.yaml`, probe reports or Git. Upstox and Alpaca require an authenticated read-only owner-machine report to move to ACCOUNT-TESTED. Sustained operations require source-specific rights and repeated refresh/outage observations.
