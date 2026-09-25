# ADR 0013: Memory Architecture

**Status:** Accepted for Phase 0.5 architecture freeze · 2026-09-26  
**Baseline:** [Phase 0 Blueprint](../architecture/PHASE_0_BASELINE_2026-09-26.md) · [review](../architecture/ARCHITECTURE_REVIEW.md)

## Context
Personal history and market evidence require distinct retention/trust rules.

## Decision
Working, episodic, semantic, procedural, market, strategy, personal, failure and prediction stores by role; filtered lexical first.

## Alternatives
One opaque vector store, only conversation context.

## Consequences
More explicit metadata and lifecycle; avoids semantic retrieval becoming truth.

## Reconsideration triggers
Retrieval evaluation or scale proves another index essential.
