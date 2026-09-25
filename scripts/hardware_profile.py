"""Read-only best-effort host capability report; run on owner workstation."""
import argparse
import ctypes
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


def ram_bytes():
    if platform.system() == "Windows":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        s = MEMORYSTATUSEX(); s.dwLength = ctypes.sizeof(s)
        return int(s.ullTotalPhys) if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)) else None
    if platform.system() == "Linux":
        try:
            return int(next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines()
                            if line.startswith("MemTotal:"))) * 1024
        except (OSError, StopIteration, ValueError):
            return None
    try:
        return int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, timeout=3).strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def gpu():
    if not shutil.which("nvidia-smi"):
        return {"name": None, "vram_mib": None, "detection": "not_detected_or_non_nvidia"}
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], text=True, timeout=5)
        first = out.splitlines()[0].rsplit(",", 1)
        return {"name": first[0].strip(), "vram_mib": int(first[1].strip()), "detection": "nvidia_smi"}
    except (IndexError, OSError, ValueError, subprocess.SubprocessError):
        return {"name": None, "vram_mib": None, "detection": "query_failed"}


def cpu_model():
    if platform.system() == "Linux":
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or None


def profile(path, disk_type="unknown", vram_override=None):
    disk = shutil.disk_usage(path)
    memory = ram_bytes()
    graphics = gpu()
    if vram_override is not None:
        graphics = {"name": graphics["name"], "vram_mib": vram_override, "detection": "owner_override"}
    vram = graphics["vram_mib"]
    return {"profile_version": "1.0.0", "os": platform.system(), "os_version": platform.version(),
            "architecture": platform.machine(), "cpu_model": cpu_model(),
            "logical_cpu_cores": os.cpu_count(), "ram_bytes": memory, "gpu": graphics,
            "disk": {"path": str(path), "total_bytes": disk.total, "free_bytes": disk.free,
                     "type": disk_type, "note": "Owner override or unknown; confirm with OS-specific drive query"},
            "local_model_capability": {"status": "possible_small_model" if vram and vram >= 8192 and memory and memory >= 16 * 1024**3 else "benchmark_required",
                                       "note": "Heuristic only; context size, quantization and concurrent load must be measured"}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=".", help="Data disk path to measure")
    ap.add_argument("--output", help="Optional local JSON output; never commit")
    ap.add_argument("--disk-type", choices=["ssd", "hdd", "network", "unknown"], default="unknown")
    ap.add_argument("--gpu-vram-mib", type=int, help="Owner override if automatic GPU detection fails")
    args = ap.parse_args()
    result = profile(Path(args.path).resolve(), args.disk_type, args.gpu_vram_mib)
    rendered = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
