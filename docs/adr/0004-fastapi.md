# ADR 0004: Fastapi

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Typed HTTP endpoints and OpenAPI are needed for a bounded client.

## Decision
FastAPI at apps/api composition boundary, contracts outside route code.

## Alternatives
Django REST, GraphQL, gRPC.

## Consequences
Straightforward schemas; avoid framework types in domain.

## Reconsideration triggers
Workflow/admin requirements or clients make alternatives simpler.
