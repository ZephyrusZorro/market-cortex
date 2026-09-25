# ADR 0002: Python Backend

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Data/quant tools and owner skills favor a productive ecosystem.

## Decision
Python domain/backend with selective optimized libraries.

## Alternatives
Rust/Go/Node as primary backend.

## Consequences
Strong data ecosystem; profile hot paths and control memory.

## Reconsideration triggers
Measured workload misses targets after profiling or runtime limitations dominate.
