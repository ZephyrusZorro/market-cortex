# ADR 0016: Local First

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Owner wants exportable private research and offline inspection.

## Decision
Local transactional/analytical/artifact stores; optional remote services behind interfaces.

## Alternatives
Cloud-only managed stack.

## Consequences
Backup and maintenance rest with owner; private data can stay local.

## Reconsideration triggers
Multi-device/team access or local constraints justify change.
