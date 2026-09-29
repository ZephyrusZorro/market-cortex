# Owner action required for live Phase 1 validation

The source-independent core and synthetic tests can progress without credentials. To validate the actual pilot:

1. On the Windows machine, keep `config/hardware.local.json` and `config/owner.yaml` local. Choose `C:\MarketCortexData` or another spacious data root and a **separate** backup location. Fill budgets and review settings.
2. Install PostgreSQL locally, create a dedicated empty database, and set `MARKET_CORTEX_DATABASE_URL` in the process environment. Apply migrations and run an isolated backup/restore drill.
3. Run the existing Phase 0.6 probe locally and retain its redacted report. Binance public samples, while useful, do not prove full historical coverage.
4. When ready, set Upstox and Alpaca tokens as environment variables on the owner machine and rerun the read-only probe. Share only the redacted report, never the keys. Confirm Upstox instrument keys, Alpaca feed entitlement and AAPL/NVDA raw-versus-split samples.
5. Supply or approve a versioned NSE and US session calendar, including holidays and early closes. Do not infer market holidays from weekdays. Verify the provider daily aggregation boundaries against real responses before broad backfill.

Current blocker impact: live India/US coverage, full pilot identity mapping, real provider disagreement, Postgres migration/restore and production freshness remain **unverified**. These are validation gates, not reasons to stop independent implementation.
