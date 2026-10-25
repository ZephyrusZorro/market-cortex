# Multi-market provider capabilities — verified documentation, 2026-10-11

This is independent development after `v1.0.1-operational`. The release tag and owner runtime remain protected. Discovery is a provider-native evidence layer; metadata is not an authorization to import candles or subscribe to every instrument.

## Capability matrix

| Capability | Binance spot | Upstox Indian cash securities | Alpaca US equity/ETF assets |
|---|---|---|---|
| Discovery | Public spot exchangeInfo; spot permission, status, base/quote, precision, filters | Public NSE/BSE JSON and suspended list; authenticated instrument search | Authenticated GET assets for active and inactive `us_equity` assets; native ID, exchange, status, tradable flag, attributes |
| Authentication | No key for public REST/streams | Free Analytics Token, generated in Developer Apps; one-year validity; market-data GET and WebSocket categories | API key ID/secret matching a paper or live account; use paper by default; Basic data plan |
| Historical API capability | 1s through monthly intervals; maximum 1,000 klines/request; UTC request timestamps | V3 minutes 1–300 and hours 1–5 from January 2022; days/weeks/months from January 2000, subject to listing/source history | History from 2016, subject to asset/feed coverage; Basic documentation lists a latest-15-minute history limitation |
| Historical request limits | Klines weight 2; exchangeInfo returns current IP rate policies | Minutes ≤15: one month/request; larger minutes/hours: quarter; daily: decade; weeks/months: no documented retrieval window cap | Basic: 200 historical requests/minute; paginate bars; select feed explicitly |
| Free real-time coverage | Public selected spot mini-tickers and klines | V3 LTPC or full, subject to actual token/entitlements | Basic IEX only; maximum 30 subscribed symbols. IEX is not a consolidated US tape |
| WebSocket restrictions | 24-hour connection lifetime, ping every 20s, matching pong required; 5 inbound control/ping/pong messages/s; 1,024 streams/connection; 300 connection attempts/5min/IP | Normal: two connections/user. Single category: LTPC 5,000 keys, full 2,000; mixed-mode limits differ. Binary subscriptions and Protobuf responses | Authentication must succeed for the selected feed; subscription acknowledgment is checked. Delayed SIP is a separate endpoint, not an assumed Basic entitlement |
| Free implementation default | One shared connection, maximum 50 selected symbols/100 streams | One shared connection, maximum 50 selected keys, LTPC default; optional full; no Plus modes | One shared connection, maximum 30 selected assets, IEX; optional explicit delayed-SIP probe |
| Time/calendar | UTC, 24×7; final candle boundaries checked | Asia/Kolkata; verified NSE and BSE sessions required before canonical import, including special sessions/holidays | America/New_York; verified exchange sessions, DST and early closes required before canonical import; source bars may include extended hours |
| Adjustment/identity | Raw; native pair remains separate from canonical UUID | Adjustment status `provider_unspecified`; preserve ISIN, native key, exchange and series variants; do not merge corporate-action history by ticker | Raw + `asof=-` to disable implicit ticker remapping; asset ID retained; ETF classification is not guessed from names |
| Offline recovery | Bounded REST bar recovery; ticker/trade gaps remain missing | Provider-available history after re-authentication; native source windows remain unverified until calendar gate passes | Entitled historical recovery only; no inferred consolidated prices or fabricated ticks |
| Current evidence | Live public discovery, additional-symbol daily/minute OHLCV, stream capture and restart recovery passed | Full public catalog captured; credentialed history/stream probes deferred | Adapter and feed-schema tests passed; asset discovery/history/stream probes deferred |

The history/chart implementation currently exposes `1m`, `5m`, `15m`, `1h`, `4h`, `1d`, `1w`, `1M`. Provider-supported intervals outside this subset are not advertised as implemented. Canonical conversion supports daily and the implemented intraday intervals; weekly/monthly canonical calendar aggregation remains a review gate.

## Realistic ₹0 coverage

Full provider-discoverable metadata can be kept locally without downloading full-market minute history. Selected-symbol charts and watchlist backfills are bounded. Public Upstox catalogs contain other cash-security types as well as equities/ETFs; the report counts cash identities, not a guessed equity count. The suspended file contains repeated keys for different exchange series. Variants are preserved; an exact listed/suspended-series conflict is flagged rather than silently resolved.

Alpaca Basic live prices/volume cover IEX. Delayed SIP must pass its own entitlement check and remain labeled DELAYED. No paid plan is selected automatically. None of the current snapshots is a complete historical delisting or corporate-action archive. Free access also remains subject to account eligibility and provider terms; connectivity is not redistribution permission.

## Official sources

- [Binance REST specification](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md)
- [Binance WebSocket specification](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md)
- [Upstox instrument files](https://upstox.com/developer/api-documentation/instruments/)
- [Upstox historical V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/)
- [Upstox Analytics Token](https://upstox.com/developer/api-documentation/analytics-token/)
- [Upstox standard API rate limits](https://upstox.com/developer/api-documentation/rate-limiting/)
- [Upstox V3 feed and limits](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/)
- [Upstox one-use feed authorization URL](https://upstox.com/developer/api-documentation/get-market-data-feed-authorize-v3/)
- [Official V3 Protobuf schema](https://assets.upstox.com/feed/market-data-feed/v3/MarketDataFeed.proto): downloaded SHA256 `3e1c939dce2c83a3fef91405c5ca268dfa089aae973319f56685f12a5afcf612`; checked-in generated code, runtime dependency only, no broker SDK.
- [Alpaca Basic plan](https://docs.alpaca.markets/us/docs/about-market-data-api)
- [Alpaca assets API](https://alpaca.markets/sdks/python/api_reference/trading/assets.html)
- [Alpaca live stock feed schemas](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data)

## Reused architecture

Existing `Bar`, observation envelopes, identity mappings, `SessionCalendar`, GET-only transport, daily adapters, immutable owner storage and as-of selection remain the canonical ingestion foundation. The explicit `market_canonical.canonical_bars` bridge returns existing contracts in memory and requires matching identity/currency/knowledge timestamps and calendar coverage. It performs no catalog writes. Existing research/AI endpoints and pinned hashes are unchanged.

The existing workstation context loops over `PILOT_SYMBOLS` and labels its universe `binance_pilot_5`. That fixed research universe explains the limited visible selection. Existing `PriceChart` renders supplied stored bars; the new `/markets` route reuses the canvas chart component for provider OHLCV and volume. New data routes use a separately configured loopback service and refuse owner/pilot ports.

## Operational gates

1. Independent source archive and regression validation: authorized; no owner DB access.
2. Upstox/Alpaca credentials and actual read-only probes: owner-local credential entry required.
3. Isolated browser acceptance: owner terminal required because automatic execution review rejected starting the independent test API/UI.
4. Verified Indian/US canonical mappings/calendars and reviewed import/storage/API-load proposal: pending probes.
5. Owner import, production integration, catalog schedule and persistent collection: separate explicit approval required. No tasks registered, no release/tag change or push.
