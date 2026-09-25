# Data Dictionary

**Source:** [Phase 0 §5](architecture/PHASE_0_BASELINE_2026-09-26.md); machine definitions in [JSON Schema registry](../packages/contracts/registry.schema.json). Contracts are `1.0.0-draft` for architecture freeze; breaking changes before the first runtime release require ADR and fixture update.

| Field | Meaning / invariant |
| --- | --- |
| `instrument_id` | Opaque UUID for one venue-specific economic instrument; never ticker. |
| `series_id` | Stable ID for nontradable economic or calculated index series. Exactly one of instrument/series on observations. |
| `venue_id` | Controlled venue code; source provider is separate. |
| `event_at` | UTC time event occurred or bar interval started; never the date-only session. |
| `published_at` | Provider/public release instant if known; nullable. |
| `available_at` | Earliest defensible use time, qualified by `availability_basis`; may be null/unknown. |
| `ingested_at` | First system receipt UTC time; never backdated. |
| `effective_from`/`effective_to` | Legal/economic validity, half-open; not availability. |
| `session_date` | ISO local trading date for named calendar; crypto daily anchor configurable and recorded. |
| `start_at`/`end_at` | UTC half-open bar boundaries, `start_at < end_at`; daily is one resolution, not a special timestamp type. |
| `quality_state` | Valid, suspect, quarantined, corrected; quarantined is invisible to standard read. |
| `missing_reason` | Explicit reason; absent bar != zero-volume bar. |
| `adjustment_basis` | Raw, split, dividend, total return or other named transformation and version; raw inputs retained. |
| `provider_record_id` | Vendor-scoped reference, not globally unique. |
| `supersedes_observation_id` | Revision link; original remains addressable. |
| `source_batch_id`, `raw_content_hash` | Immutable provenance; hash is of retained or inspected source bytes. |
| `manifest_id` | Immutable published dataset snapshot listing file/content hashes and policies. |
| `currency`, `unit` | ISO/controlled codes; rates are percent or decimal explicitly, crypto base/quote distinct. |
| `is_final` | Whether provider marks observation complete; a revision remains possible. |

Price and quantity are decimal strings in JSON to avoid float drift. Ordering, positive dimensions, OHLC inequalities, uniqueness and as-of selection are application/database constraints tested by fixtures; JSON Schema cannot express all of them.
