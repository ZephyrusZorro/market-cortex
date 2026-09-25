# Hardware Validation — Phase 0.6

**Result: BLOCKED for owner workstation.** `config/hardware.local.json` is absent. A previous memory mentions an ASUS ROG G16, i7 13th generation and RTX 4060; this is not a measured profile, and its RAM, VRAM and free disk are unknown. The available execution environment is a remote Linux container, so its hardware cannot substitute for the Windows workstation.

| Capability | Observed on owner PC | Required evidence / interpretation |
| --- | --- | --- |
| OS, CPU model, logical/physical cores | Unknown | Run `python scripts/hardware_profile.py --output config/hardware.local.json` locally; physical cores best effort. |
| RAM | Unknown | At least enough for local PostgreSQL plus batch queries; size empirically after profile. |
| GPU / VRAM | Unknown | `nvidia-smi` probe if NVIDIA; use manual `--gpu-vram-mib` only if detection fails. Phase 1 does not need GPU. |
| Disk type / available space | Unknown | Use `--path` on intended primary data volume and `--disk-type ssd|hdd|network`; confirm backup on another volume. |
| Python | Unknown on owner PC | Aim for 3.12+ and verify chosen pinned dependency versions on Windows. This remote runtime is Python 3.12.14, not owner validation. |
| PostgreSQL, DuckDB, Polars | Unknown on owner PC | Verify install, a database create/restore and a small Parquet round-trip in Phase 1A. No benchmark can be inferred from a remote container. |
| Local LLM / embeddings | Deferred | Small quantized model/embedding jobs may be possible if RAM/VRAM suffice; benchmark later. Cloud use remains disallowed by example config. |

**Phase 1 suitability:** daily data likely modest, but cannot certify owner-machine suitability until the local profile and installation check. Put PostgreSQL and Parquet on a volume with free-space headroom; keep a separate backup target. No GPU optimization is needed for initial daily ingestion. The script never sends the profile elsewhere.
