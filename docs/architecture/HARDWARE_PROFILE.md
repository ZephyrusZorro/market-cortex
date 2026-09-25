# Hardware Capability Profile

Run `python scripts/hardware_profile.py --output config/hardware.local.json` **on the owner workstation**, not a remote build container. The resulting local file is gitignored and may include device metadata. No detection has yet been performed on the owner's machine. The prior description of a ROG G16 / i7 13th gen / RTX 4060 is an unverified hint, not the sizing result.

Detect: OS/version/architecture, logical CPU cores, RAM, disk filesystem/free capacity and SSD/HDD classification where available, GPU/VRAM and local-model capability heuristic. Unknown values remain null. Disk type can be supplied with `--disk-type ssd|hdd|network`; GPU VRAM can be supplied with `--gpu-vram-mib` if the probe cannot detect it. Configure actual storage and budget in [owner template](../../config/owner.example.yaml). Reserve capacity for PostgreSQL, Parquet, artifacts, immutable manifests and encrypted backups on another volume/device.

Later scheduler uses explicit workload labels (CPU, GPU, local LLM, cloud LLM, batch, background), measured RAM/VRAM/disk/time and owner privacy/cost limits; no task automatically receives model or cloud permission because a GPU exists. A heuristic is not a benchmark. Phase 1 uses CPU daily batch unless measurements justify more.
