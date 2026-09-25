# Conditional Phase 1A Proposal — Core Data Foundation

**Do not start automatically.** Once the [Phase 0.6 readiness gate](PHASE_0_6_READINESS.md) clears and the owner approves, build only: reproducible local runtime, PostgreSQL initialization and migrations, formal contracts, instrument master, venue registry, valid-time identifier mappings, trading calendars, provider capability registry, owner configuration loading, health/status surface, frozen source fixtures and tests. Verify backup target and isolated restore mechanics before persistent ingestion.

No live ingestion in Phase 1A without a separate explicit decision. No CORTEX, dashboard, strategy, screener, options, ML, agents, broker connection or order flow. Later Phase 1B can add approved daily adapters and immutable storage after Phase 1A tests and provider probes pass.
