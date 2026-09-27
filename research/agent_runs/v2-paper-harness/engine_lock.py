"""v2-paper-harness: frozen-engine hash guard (s12 build order #1).

Clones the omen6_forward "REFUSING TO SCORE" pattern: Lane R must run on the exact
frozen strategy chosen by OMEN-SHIP-PLAN-v3.md sec 2 -- ORB5 + displacement + wick
retest + strong-bar trigger, 10:30 cutoff, 2R, MNQ only
(research/agent_runs/v2-t01-orb-1m/orb1m.py). If that file's sha256 no longer
matches FROZEN_SHA256, refuse to replay rather than silently scoring on a moved
engine.

FIXED 2026-09-26 (v3 b1): PR #34 froze research/agent_runs/v2-t02-ocr-1m/ocr1m.py
(ORB+OCR confluence), which v3-referee struck and OMEN-SHIP-PLAN-v3.md sec 1/6
dropped -- OCR confluence, MES, and every non-MNQ instrument are dead out-of-sample.
The only cell that survived to "run first, paper only" is orb1m.py's MNQ / OR5 /
disp>=1 ATR / strong / 10:30 / 2R cell. Re-point the lock at that file.

To re-freeze after a deliberate engine change: run this file with `--refreeze` and
paste the printed hash in as the new FROZEN_SHA256 (a Build decision, not automatic).
"""
import hashlib
import sys
from pathlib import Path

# Repo-relative so a worktree checks its own copy, not production's (k/lane-r parity).
ENGINE_PATH = Path(__file__).resolve().parent.parent / "v2-t01-orb-1m" / "orb1m.py"

# Frozen 2026-09-26 (v3 b1), matches the file as committed in
# research/agent_runs/v2-t01-orb-1m/orb1m.py -- this is the sha OMEN-SHIP-PLAN-v3.md
# sec 2 cites as "BAFD7CE4..." for the frozen MNQ mantra cell.
FROZEN_SHA256 = "bafd7ce4e4f69250c0cef80acdbd26057ee04a6a658c95b11ed92bba08bc8ef1"


class EngineDriftError(RuntimeError):
    pass


def engine_sha256(path: Path = ENGINE_PATH) -> str:
    # Hash LF-normalized bytes (= the git blob): a CRLF checkout of the same code is
    # not drift. The 9/26 recovery restored orb1m.py as CRLF and the raw hash broke.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def assert_frozen(path: Path = ENGINE_PATH, frozen: str = FROZEN_SHA256) -> str:
    """Returns the engine's sha256 if it matches the frozen value; raises EngineDriftError otherwise."""
    got = engine_sha256(path)
    if frozen == "REPLACE_AT_BUILD":
        raise EngineDriftError(
            "engine_lock.FROZEN_SHA256 was never set at build time -- refusing to replay on an unpinned engine"
        )
    if got != frozen:
        raise EngineDriftError(
            f"REFUSING TO REPLAY: frozen engine hash changed. path={path} frozen={frozen} got={got}"
        )
    return got


if __name__ == "__main__":
    h = engine_sha256()
    print("engine_sha256", h)
    if len(sys.argv) > 1 and sys.argv[1] == "--refreeze":
        print("paste this into FROZEN_SHA256:", h)
    else:
        try:
            assert_frozen()
            print("OK: engine matches frozen hash")
        except EngineDriftError as e:
            print(str(e))
            sys.exit(1)
