# Single owner research persistence check — 2026-10-11

**Explicitly authorized by the owner:** "Authorize this single owner research record". This is separate from the earlier schema and market-data permissions. Submit once; inspect any partial result before retrying.

Question: "Analyze ETHUSDT momentum and data quality in the pinned owner daily dataset. Include uncertainty and whether available evidence supports an edge."

Use the existing production CORTEX UI/API in OWNER_MAIN, market_cortex on 5432, with ETHUSDT compared to BTCUSDT, deep deterministic research, manifest `94368463-0587-46f0-8c3d-7b5dfee1826b` and cutoff `2026-10-11T12:48:07.699784Z`. The current gateway is deterministic and no LLM is configured. This uses actual owner observations; no synthetic record is imported.

Expected database change: exactly one row in `cortex_research_runs`, including its question, source context, evidence, citations and hashes. No additional market bars, Parquets, jobs, personal preferences, journal, portfolio, prediction, thesis, mission or experiment is authorized. No broker writes or paid service.

Acceptance: inspect the saved ID, reopen it through the existing UI/API, replay its evidence, then have the owner execute the existing controlled Stop/Start procedure. Reopen and replay the same ID after restart. Compare all table counts against the validated owner baseline with only the approved research row added, and verify schema/checksums/head/storage unchanged using read-only preflight. Keep the pilot running separately. OWNER_READY remains pending until these checks succeed.

The retained encrypted pre-ingestion baseline and isolated recovery remain intact; they contain the fully migrated catalog before the 1,825 market bars were added. They are not a current populated-catalog backup. Preserve them and the original onboarding failure/successful verification receipts.
