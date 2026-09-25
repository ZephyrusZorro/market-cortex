# Adversarial Architecture Review — Phase 0.5

**Authority:** archived [Phase 0 baseline](PHASE_0_BASELINE_2026-09-26.md). The review refines contracts; no core technology choice is overturned. Classification refers to the gate for **Phase 1**, not eventual product importance.

| Class | Finding | Resolution / owner action |
| --- | --- | --- |
| BLOCKER | Provider availability, exact mappings, account entitlements, historical depth and retention are not established for all 25 candidates. | Provisional pilot only; credentialed symbol/backfill/rights probes and selection signoff before ingestion. |
| BLOCKER | Owner hardware, storage budget and cloud privacy settings lack verified values. | Run hardware profile on actual workstation; copy owner template and set budgets/privacy before runtime sizing. |
| BLOCKER | Backup/restore and licensed raw retention lack executable procedures. | Phase 1 milestone must prove isolated restore; per-source rights metadata gate before raw capture. |
| IMPORTANT | `available_at` can conflate first system receipt and historical first-publication proxy. | Add `availability_basis`; unknown availability excluded from strict point-in-time research; never backdate ingestion. |
| IMPORTANT | PostgreSQL pointer and Parquet files cannot share a single ACID transaction. | Stage/hash files, publish immutable manifest via DB transaction and outbox, reconcile orphans, verify referenced content on restore. |
| IMPORTANT | Provider ticker reuse, venue listing, ISIN and contract IDs can collide. | Venue-scoped UUID identity; valid-time mappings; ambiguous overlaps quarantine; derivative specification separate. |
| IMPORTANT | Daily-bar `event_at`/session date and crypto UTC anchors are insufficient alone. | Half-open UTC interval plus explicit local session date/calendar ID and aggregation rule. |
| IMPORTANT | Vendor-adjusted prices and later corporate actions can leak revisions. | Raw and adjusted views separate; source adjustment metadata, action vintages, as-of transforms. |
| IMPORTANT | In-process cache and events could break historical replay if keyed by live data. | Cache keyed by manifest/as-of/policy; outbox event references committed manifest; idempotency and versioned payload. |
| IMPORTANT | ML leakage may enter via selected universe, filings or publication lags. | Store membership vintages, effective/available times and run manifest; strict replay fixtures. |
| IMPORTANT | Provider/AI/storage lock-in through raw vendor fields or tool access. | Canonical domain interfaces, named provider capability, storage manifest, ModelGateway, typed tool permissions. |
| ACCEPTABLE DEBT | Source quality scoring and intraday partition sizing lack real workloads. | Profile Phase 1 daily data; change physical partitioner under manifest/catalog interface later. |
| ACCEPTABLE DEBT | Corporate action completeness and market holiday special sessions vary by source. | Mark incomplete and block claimed adjusted/complete coverage; exact special-session fixtures at provider gate. |
| ACCEPTABLE DEBT | No paid consolidated US feed selected. | Label IEX vs SIP coverage; buy access only after acceptance measurements. |
| FUTURE CONSIDERATION | Deep order books need sequence/resnapshot, derivatives need expiry/multiplier semantics. | Typed extension contracts and kind-specific partitions later; no runtime feeds now. |
| FUTURE CONSIDERATION | High-volume streaming, local LLM and vector retrieval may need separate infrastructure. | Measured triggers in ADRs and hardware profile; no premature services. |

**Freeze decision:** freeze structural choices and contract semantics in the ADRs; provider selection/universe and machine sizing are conditional. No evidence justifies a redesign. Unverified source feasibility prevents an unconditional READY status.
