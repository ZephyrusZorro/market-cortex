# Deferred owner actions after Phase 1 foundation completion

The Binance public live pilot has validated the Phase 1 market-data pipeline. The actions below extend coverage or move the foundation from an isolated test deployment to the owner's intended installation. They do not block the Phase 1 exit decision in the [evidence matrix](docs/planning/PHASE_1_EXIT_MATRIX_2026-10-03.md).

1. Review current provider usage and local retention terms before sustained or broad Binance ingestion. Public technical access alone does not establish caching rights.
2. When available, keep Upstox and Alpaca credentials in environment variables and run the read-only probe. Their live status is `DEFERRED_NOT_CONFIGURED`. Record account entitlements, native identifiers, feed class, timestamp/adjustment behavior, quotas and rights without sharing secrets.
3. For any India or US equity support, import verified venue-scoped native mappings and source-backed, versioned NSE/US exchange sessions including holidays and early closes. Until then, equity candidates stay deferred and no calendar or identity is guessed.
4. For the intended installation, apply migrations to the owner's `market_cortex` database, use `C:\MarketCortexData`, select a separate backup destination, and rehearse an isolated restore. The Phase 1 proof used disposable test databases and workspace storage; it did not touch the owner's existing databases.

No broker order, trading, or write endpoint is included.
