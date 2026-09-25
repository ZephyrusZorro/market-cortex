# Domain Model

**Baseline:** [Phase 0 §§4–5](architecture/PHASE_0_BASELINE_2026-09-26.md). Formal [contracts](../packages/contracts/registry.schema.json), [dictionary](DATA_DICTIONARY.md).

`Instrument` is an immutable UUID for an economically distinct, venue-specific listing, index/series, spot pair or contract. Issuer/entity and underlying link instruments; a symbol does not identify one. `IdentifierMapping` is provider/venue/type/value scoped and valid for an interval; ambiguous overlaps quarantine. ISIN helps equity resolution but is not a universal key. `ContractSpecification` is a later separately versioned extension for derivatives, with underlying, expiry, strike, right, multiplier and settlement, rather than an optional blob on every cash instrument.

`TradingCalendar` identifies venue, IANA zone, dated sessions, exceptions and a 24/7 rule for crypto. Daily `Bar` has a session date plus UTC start/end; future intraday bars use the same half-open `[start,end)` interval. Event time, publish time, first-known time, ingest time and effective time answer different questions. A provider can revise an observation; the revision references the old observation, keeps raw provenance and increments a dataset version.

`CorporateAction` has separate announcement/record/ex/pay/effective times. `EconomicEvent` maintains release vintages. `NewsEvent` retains publisher and first-seen time. `MarketStateSnapshot`, `Candidate` and `TradeThesis` hold evidence and contradictory evidence but cannot replace raw facts. `JournalEntry` and `PredictionRecord` remain append-amended. `ResearchRunManifest` freezes every input and code version. Contract types beyond Bar are registered as draft shapes in Phase 0.5; no associated runtime logic exists.
