"""
MiMo TUI — Free-tier Auth
Bootstrap + fingerprint for opencode.ai free models.
"""

import hashlib
import json
import os
import platform
from pathlib import Path

BOOTSTRAP_URL = "https://api.xiaomimimo.com/api/free-ai/bootstrap"
FINGERPRINT_FILE = Path.home() / ".local" / "share" / "mimo-tui" / "fingerprint"


def get_fingerprint() -> str:
    """Generate or load device fingerprint."""
    if FINGERPRINT_FILE.exists():
        return FINGERPRINT_FILE.read_text().strip()

    hostname = platform.node()
    os_name = platform.system().lower()
    arch = platform.machine()
    username = os.getenv("USER", os.getenv("USERNAME", "unknown"))

    cpu_model = "unknown"
    try:
        if os_name == "linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.split(":")[1].strip()
                        break
        elif os_name == "windows":
            cpu_model = os.getenv("PROCESSOR_IDENTIFIER", "unknown")
    except Exception:
        pass

    raw = f"{hostname}|{os_name}|{arch}|{cpu_model}|{username}"
    fp = hashlib.sha256(raw.encode()).hexdigest()

    FINGERPRINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    FINGERPRINT_FILE.write_text(fp)
    return fp
