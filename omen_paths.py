"""Where the 1-minute price archive (data_archive/) lives.

Resolution order:
  1. env OMEN_DATA_DIR (explicit override)
  2. <this checkout>/data_archive if it exists (the main checkout, or a full clone)
  3. the MAIN checkout's data_archive, found via git's common dir (linked worktrees)
  4. <this checkout>/data_archive (default; archive_1m.py creates it)

A linked worktree therefore never needs its own copy of the ~800 MB archive.
"""
import os
import subprocess
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _main_checkout(here: Path = _HERE):
    try:
        out = subprocess.run(
            ["git", "-C", str(here), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return None
    return Path(out).parent if out else None


def data_archive_dir(here: Path = _HERE, env=None) -> Path:
    env = os.environ if env is None else env
    override = env.get("OMEN_DATA_DIR", "").strip()
    if override:
        return Path(override)
    local = here / "data_archive"
    if local.is_dir():
        return local
    main = _main_checkout(here)
    if main and (main / "data_archive").is_dir():
        return main / "data_archive"
    return local


DATA_ARCHIVE = data_archive_dir()
