# MARKET CORTEX

Private local-first market intelligence project. **Phase 0.5 architecture freeze; Phase 1 production code has not begun.**

Start at [Project Constitution](docs/PROJECT_CONSTITUTION.md), [Architecture Review](docs/architecture/ARCHITECTURE_REVIEW.md), [Phase 1 Plan](docs/planning/PHASE_1_MILESTONES.md), and the [archived Phase 0 baseline](docs/architecture/PHASE_0_BASELINE_2026-09-26.md). [Decision log](docs/DECISION_LOG.md) lists the ADRs.

This repository contains planning, formal draft contracts, synthetic fixtures, and a read-only hardware detection utility. No market ingestion, API, application, trading logic, or AI orchestration is implemented. Symbols and source rankings remain provisional until documented credentialed probes and owner settings are completed. See [readiness gate](docs/planning/READINESS.md).

## Structure

- `apps/api`, `apps/web`: reserved application surfaces.
- `packages/contracts`: versioned JSON Schema registry; other package directories reserve domain boundaries.
- `data/manifests`, `data/fixtures`: reserved runtime locations, never commit downloaded market data.
- `docs`: living documentation, research matrix, ADRs and archived baseline.
- `tests/fixtures`: synthetic Phase 1 acceptance cases and expected outcomes.
- `scripts/hardware_profile.py`: read-only host capability report.
- `config/owner.example.yaml`: nonsecret preferences; copy to ignored `config/owner.yaml`.

Git is initialized locally. A remote is not configured. Do not commit secrets, provider exports, journal or portfolio contents. Phase 1 starts only after owner approval and the readiness checks are cleared.
