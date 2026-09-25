# Testing Strategy

**Baseline:** [Phase 0 §12](architecture/PHASE_0_BASELINE_2026-09-26.md). [Phase 1 cases](planning/PHASE_1_TEST_PLAN.md) and [frozen synthetic fixture catalog](../tests/fixtures/phase1_cases.json).

Contract validation and migration checks guard shape and compatibility. Unit tests cover identity, calendar, dedup, OHLC, availability and supersession. Adapter contract tests replay licensed or synthetic response samples for success, quota, auth, partial and outage; never put credentials in fixtures. Integration tests commit source batches, manifests and outbox against disposable PostgreSQL and filesystem. System tests restart jobs, restore isolated backups, and compare as-of results before/after late corrections. Property tests check UTC ordering, manifest immutability and idempotency. Nightly credentialed probes are separate from hermetic CI; if not provisioned, coverage is unverified, not green. Every market claim is backed by provider/time/manifest evidence.

Phase 0.6 finalization: [current readiness](planning/PHASE_0_6_READINESS.md). The 22 frozen cases still define the substantial Phase 1 tests. `scripts/probe_sources.py` is a bounded read-only feasibility probe; its sampled results are evidence to update fixtures and source decisions, not a green CI suite or production adapter.
