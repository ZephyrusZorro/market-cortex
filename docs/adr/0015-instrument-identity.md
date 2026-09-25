# ADR 0015: Instrument Identity

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Tickers change/reuse; one issuer has listings, pairs and derivatives.

## Decision
Opaque UUID per economic venue instrument; valid-time provider/venue mappings; separate derivative contract specification.

## Alternatives
Ticker/ISIN/provider token as global PK.

## Consequences
Resolution service needed; stable joins and history.

## Reconsideration triggers
A new asset class cannot be expressed with typed extension.
