# Phase 1 Daily Source Selection — Phase 0.6

The [broad Phase 0.5 matrix](DATA_SOURCE_MATRIX.md) remains background research. This short selection table distinguishes **DOCUMENTATION-VERIFIED**, **ACCOUNT-TESTED**, and **PRODUCTION-VALIDATED**. A failed call from a network-restricted remote workspace is not a provider failure. No account-level probe result exists yet.

| Market | Provisional primary | Fallback | Evidence level | Decision and next action |
| --- | --- | --- | --- | --- |
| India | Upstox V3 daily historical candles and instrument search | Kite Connect | DOCUMENTATION-VERIFIED | Preserve as primary candidate; run six-symbol owner-machine probe, confirm account, raw/adjusted semantics and private caching. |
| US | Alpaca explicit `iex` daily stock bars plus asset lookup | Massive/Polygon or a verified SIP tier | DOCUMENTATION-VERIFIED | Preserve as candidate; check five symbols, split comparison, raw vs split, IEX vs SIP entitlement; choose feed class explicitly. |
| Crypto | Binance Spot public market data | Coinbase Exchange USD pairs | DOCUMENTATION-VERIFIED | Preserve as candidate; five pairs, exchange status, UTC daily anchor, owner-region access and limits. |

**Rank criteria:** actual access > identity and coverage > timestamp/adjustment clarity > reliability > simplicity/cost > future intraday/stream support > lock-in. None of the first three has actual successful access in this environment. Therefore **final Phase 1 primary choices are not yet frozen**. No fallback adapter is required in Phase 1A.
