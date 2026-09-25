# Memory Architecture (design only)

**Baseline:** [Phase 0 §8](architecture/PHASE_0_BASELINE_2026-09-26.md). [Memory ADR](adr/0013-memory-architecture.md).

Working memory is bounded run context; episodic memory is immutable run/decision references; semantic memory is sourced concepts; procedural memory is owner-approved rules; market memory points to versioned as-of observations; strategy memory stores parameters/results; personal memory stores editable owner preferences; failure memory stores reviewed failures; prediction ledger stores frozen forecasts and append-only evaluations.

Retrieve with permission, instrument, source, and time filters first; lexical matching next; optional embeddings rerank. Summaries are rebuildable derived artifacts with source links. Deletions/retention are deliberate, especially for personal notes and licensed third-party text. No embedding can act as numeric source of truth or silently replace a corrected memory. Phase 1 only preserves data contracts that later memories reference.
