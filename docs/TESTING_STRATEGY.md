# Testing Strategy

**Baseline:** [Phase 0 §12](architecture/PHASE_0_BASELINE_2026-09-26.md). [Phase 1 cases](planning/PHASE_1_TEST_PLAN.md) and [frozen synthetic fixture catalog](../tests/fixtures/phase1_cases.json).

Contract validation and migration checks guard shape and compatibility. Unit tests cover identity, calendar, dedup, OHLC, availability and supersession. Adapter contract tests replay licensed or synthetic response samples for success, quota, auth, partial and outage; never put credentials in fixtures. Integration tests commit source batches, manifests and outbox against disposable PostgreSQL and filesystem. System tests restart jobs, restore isolated backups, and compare as-of results before/after late corrections. Property tests check UTC ordering, manifest immutability and idempotency. Nightly credentialed probes are separate from hermetic CI; if not provisioned, coverage is unverified, not green. Every market claim is backed by provider/time/manifest evidence.
