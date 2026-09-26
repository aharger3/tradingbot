"""v2-paper-harness: frozen-engine hash guard (s12 build order #1).

Clones the omen6_forward "REFUSING TO SCORE" pattern: Lane R must run on the exact
frozen v2 engine file (research/agent_runs/v2-t02-ocr-1m/ocr1m.py). If that file's
sha256 no longer matches FROZEN_SHA256, refuse to replay rather than silently
scoring on a moved engine.

To re-freeze after a deliberate engine change: run this file with `--refreeze` and
paste the printed hash in as the new FROZEN_SHA256 (a Build decision, not automatic).
"""
import hashlib
import sys
from pathlib import Path

ENGINE_PATH = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-t02-ocr-1m\ocr1m.py")

# Frozen 2026-09-26, matches the file as committed in research/agent_runs/v2-t02-ocr-1m/ocr1m.py
FROZEN_SHA256 = "ad18236bc999bee0fe57829b233a4399f0674206bdfd44e15fa1d7fedd63d968"


class EngineDriftError(RuntimeError):
    pass


def engine_sha256(path: Path = ENGINE_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
