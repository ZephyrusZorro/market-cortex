# Contract and Intraday Compatibility Review — Phase 0.6

**Evidence level:** architecture and official provider documentation, not account-tested samples. No observed provider behavior justifies changing the Phase 0.5 registry yet. Review again when the local probe report exists.

| Boundary | Daily Phase 1A | Future intraday / complex feeds | Result |
| --- | --- | --- | --- |
| Instrument / IdentifierMapping | UUID listing, venue/provider/native ID and valid intervals | ContractSpecification links underlying, expiry, option right, multiplier; exchange pair distinct | Sufficient conceptually; verify native ID reuse. |
| TradingCalendar / Bar | IANA zone, local session date, UTC `[start_at,end_at)` and resolution | 1/5/15-minute/hourly bars use same interval; overnight/crypto anchors explicit | Sufficient; day bar timestamp must be interpreted per provider. |
| ObservationEnvelope | event/published/available/ingested/effective times, source, feed, adjustment, quality | Trades, quotes, book, funding, OI and liquidation payloads add kind-specific schema; stream sequence/checkpoint and book resnapshot requirements | Envelope sufficient; payload schemas deferred until each feed. |
| Provider abstraction | `fetch(kind, identity, resolution, interval)` + capability | `subscribe()`/cursor with native sequence, gap handling, snapshot/delta | Ports reserved; no runtime implementation. |
| Storage abstraction | Immutable manifest of Parquet files, DB pointer | Different event-day/hour/shard partitioners and derivative attributes under same catalog/query | No core redesign; benchmark before choosing high-volume layout. |
| Event abstraction | Versioned outbox and idempotency key | Duplicate/reordered delivery, broker replacement | Sufficient; event payload ref points to committed manifest. |
| Source semantics | Explicit feed class and raw/split adjustment | Exchange timestamp precision, book sequence, funding interval, option snapshot | Need provider sample to validate; no advance feed logic built. |

**Concrete pre-Phase 1 checks:** Upstox/Kite daily candle offset vs session date; Alpaca feed (`iex`/`sip`), `adjustment=raw|split` and symbol as-of behavior; Binance kline open/close milliseconds and UTC day anchor. Keep raw and adjusted records as distinct named series/transformations and never overwrite raw. A rate/yield observation must remain an EconomicEvent/series value, not be forced into OHLC.
