# ADR 0008: Provider Abstraction

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Providers differ in coverage, adjustment, availability and rights.

## Decision
Typed fetch/stream capability interfaces; adapters emit canonical envelopes and explicit limitations.

## Alternatives
Vendor DTOs throughout system, one-source schema.

## Consequences
Substitution and comparison possible; extra translation work.

## Reconsideration triggers
Capability manifest cannot represent a needed semantic without destructive change.
