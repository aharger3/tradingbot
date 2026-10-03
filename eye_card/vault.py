"""Secrets for the eye loop: env first, then the keys vault (python keys.py get NAME).

Never logs or prints a value. Returns '' when the name is unset or the vault is not on this box.
"""
from __future__ import annotations

import os
import subprocess
import sys

KEYS_PY = os.environ.get("TAP_KEYS_PY", r"C:\Users\aharg\.claude\sync-setup\keys.py")


def secret(name: str) -> str:
    v = os.environ.get(name, "")
    if v or not os.path.exists(KEYS_PY):
        return v
    r = subprocess.run([sys.executable, KEYS_PY, "get", name], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""
