# Provider Usage Notes — private local research only

This is a short operational check, not a commercial compliance review. No order or broker execution operations are planned. Actual tier and retention terms must be checked in the owner's account before sustained ingestion. Third-party data rights and request limits can still affect a private cache.

| Candidate | Tier / auth | Practical request and caching notes | Status |
| --- | --- | --- | --- |
| [Upstox V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/) | Owner account bearer token via `UPSTOX_ACCESS_TOKEN`; exact tier unknown | Daily history documented from Jan 2000 as a product capability, request range at most one decade; per-instrument coverage and API usage terms untested. Cache policy/account access to verify. | Documentation verified; account not tested. |
| [Alpaca](https://docs.alpaca.markets/us/reference/stockbars) | API key/secret in environment; feed `iex` explicitly requested by probe; exact account tier unknown | Historical bars offer raw/split/dividend choices and page tokens; response might vary by feed/tier. Confirm private storage terms and desired SIP/IEX coverage. | Documentation verified; account not tested. |
| [Binance Spot public market API](https://developers.binance.com/en/docs/products/spot/rest-api) | Public endpoint, no key for market data | IP-weight limits and 429 handling; verify owner-region access and local caching terms. Do not infer permission from public reachability. | Documentation verified; remote probe blocked by network; owner untested. |
| [Coinbase Exchange public API](https://docs.cdp.coinbase.com/exchange/rest-api/requests) | Public market requests; exchange-specific products | Candidate fallback only; USD pairs may differ from Binance USDT pairs; verify rate/cache rules on selection. | Documentation verified; remote probe blocked; owner untested. |

No provider is production validated. Secrets are never written to `owner.yaml`, probe reports or Git. Provider status moves to ACCOUNT-TESTED only after an authenticated/read-only owner-machine report; production validated requires repeated refresh, correction, outage and restore observations.
