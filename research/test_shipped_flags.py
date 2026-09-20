"""research/test_shipped_flags.py -- Austin's 2026-09-20 card: "Adopt shipped
flags into the PAPER engine automatically -- only when $/day improves AND
green months hold." Locks down research/shipped_flags.py's three jobs:

  1. decide_adopt() is the STRICT improvement rule -- $/day strictly better
     AND green months do not fall. This is stricter than loop_cycle.py's own
     ship gate (SWARM.md law 2), which tolerates up to a 5% $/day drop --
     a flag can "ship" there and still be recorded adopt:False here.
  2. load_and_apply() sets env[flag] only for adopt:True flags, and only
     when that env var is not already set (a human/.env override wins).
  3. the honest backtest baseline never reads this file -- a text-level
     check against backtest_2y.py and signal_runner.py, so this holds
     structurally rather than only by today's call graph.

    python research/test_shipped_flags.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import shipped_flags as sf  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: object = "") -> None:
    if not cond:
        FAILURES.append("%s: %r" % (name, detail))


# --------------------------------------------------------- decide_adopt()

def test_decide_adopt_strict_improvement_is_true():
    check("strict improvement, green holds", sf.decide_adopt(-52.0, -50.0, 11, 11) is True)
    check("strict improvement, green rises", sf.decide_adopt(100.0, 150.0, 20, 22) is True)


def test_decide_adopt_within_5pct_worse_is_false():
    # loop_cycle.py's OWN ship gate tolerates up to a 5% $/day drop -- this
    # pair would still pass THAT gate (4% worse), but must not adopt.
    before, after = 100.0, 96.0
    check("ship-tolerance-worse is not adopt", sf.decide_adopt(before, after, 11, 11) is False,
          (before, after))
    # tonight's real row (research/tape/cycles.md, 2026-09-19):
    # ship, BNR_DISPLACEMENT_GATE, -52.0 -> -54.0, 11 -> 11 green -- worse on
    # $/day under the loose gate, must record adopt: False.
    check("tonight's BNR row is adopt:false", sf.decide_adopt(-52.0, -54.0, 11, 11) is False)


def test_decide_adopt_false_when_green_falls_even_if_dollars_improve():
    check("green falling blocks adopt even on a $/day win",
          sf.decide_adopt(-52.0, -30.0, 11, 10) is False)


def test_decide_adopt_flat_dollars_is_not_strict_improvement():
    check("flat $/day is not a strict improvement", sf.decide_adopt(-52.0, -52.0, 11, 11) is False)


def test_decide_adopt_never_raises_on_bad_input():
    check("None input adopts nothing rather than raising",
          sf.decide_adopt(None, -50.0, 11, 11) is False)


# ------------------------------------------------------------ record_ship()

def test_record_ship_writes_adopt_field_and_appends(tmp_path: Path):
    path = tmp_path / "shipped_flags.json"
    entry = sf.record_ship("SOME_FLAG", "1", -52.0, -50.0, 11, 11,
                            when="2026-09-20", path=path)
    check("record_ship computes adopt True", entry["adopt"] is True, entry)
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    check("record_ship persists one row", len(on_disk) == 1, on_disk)
    check("record_ship stores flag/value", on_disk[0]["flag"] == "SOME_FLAG"
          and on_disk[0]["value"] == "1", on_disk)

    # A second ship of the same flag appends -- an append-only ledger, same
    # convention as cycles.md -- rather than overwriting the first row.
    entry2 = sf.record_ship("SOME_FLAG", "1", -52.0, -60.0, 11, 11,
                             when="2026-09-21", path=path)
    check("record_ship second row is adopt:false", entry2["adopt"] is False, entry2)
    on_disk2 = json.loads(path.read_text(encoding="utf-8"))
    check("record_ship appends, does not overwrite", len(on_disk2) == 2, on_disk2)
    latest = sf.latest_by_flag(on_disk2)
    check("latest_by_flag takes the LAST row for a repeated flag",
          latest["SOME_FLAG"]["adopt"] is False, latest)


# --------------------------------------------------------- load_and_apply()

def test_load_and_apply_sets_env_only_for_adopt_true(tmp_path: Path):
    path = tmp_path / "shipped_flags.json"
    path.write_text(json.dumps([
        {"flag": "ADOPT_ME", "value": "1", "adopt": True},
        {"flag": "DO_NOT_ADOPT", "value": "1", "adopt": False},
    ]), encoding="utf-8")
    env: dict = {}
    applied = sf.load_and_apply(env, path=path)
    check("adopted flag lands in env", env.get("ADOPT_ME") == "1", env)
    check("non-adopted flag is absent from env", "DO_NOT_ADOPT" not in env, env)
    check("applied list names only the adopted flag", applied == ["ADOPT_ME=1"], applied)


def test_load_and_apply_respects_existing_env_value(tmp_path: Path):
    path = tmp_path / "shipped_flags.json"
    path.write_text(json.dumps([{"flag": "ADOPT_ME", "value": "1", "adopt": True}]),
                     encoding="utf-8")
    env = {"ADOPT_ME": "0"}  # an explicit override: a real .env line, an exported shell var
    applied = sf.load_and_apply(env, path=path)
    check("an explicit env override is never clobbered", env["ADOPT_ME"] == "0", env)
    check("applied list is empty when nothing changed", applied == [], applied)


def test_load_and_apply_missing_file_applies_nothing(tmp_path: Path):
    path = tmp_path / "does_not_exist.json"
    env: dict = {}
    applied = sf.load_and_apply(env, path=path)
    check("missing shipped_flags.json applies nothing", applied == [] and env == {},
          (applied, env))


# --------------------------------------- baseline builder never reads this

def test_baseline_builder_never_reads_shipped_flags():
    """backtest_2y.py builds every book loop_cycle.py gates (it imports
    signal_runner directly -- see its own import list); signal_runner.py is
    also imported directly by backtest_week.py/backtest_12mo.py. Neither may
    ever import research.shipped_flags or the honest baseline stops being
    reproducible from a clean checkout of just the engine files -- the
    adopted-flags hook belongs ONLY on live_scanner.py's paper-engine start
    path (research/test_shipped_flags's sibling check is a grep, not a
    behavioural probe, so it holds even if the call graph changes later)."""
    for name in ("backtest_2y.py", "signal_runner.py"):
        src = (ROOT / name).read_text(encoding="utf-8")
        check("%s never mentions shipped_flags" % name, "shipped_flags" not in src, name)


def main() -> None:
    test_decide_adopt_strict_improvement_is_true()
    test_decide_adopt_within_5pct_worse_is_false()
    test_decide_adopt_false_when_green_falls_even_if_dollars_improve()
    test_decide_adopt_flat_dollars_is_not_strict_improvement()
    test_decide_adopt_never_raises_on_bad_input()

    with tempfile.TemporaryDirectory() as d:
        test_record_ship_writes_adopt_field_and_appends(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_load_and_apply_sets_env_only_for_adopt_true(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_load_and_apply_respects_existing_env_value(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_load_and_apply_missing_file_applies_nothing(Path(d))

    test_baseline_builder_never_reads_shipped_flags()

    if FAILURES:
        print("SHIPPED FLAGS TEST FAILED: %d check(s)" % len(FAILURES))
        for f in FAILURES:
            print("  " + f)
        sys.exit(1)

    print("shipped flags test ok (10 checks): strict adopt rule holds on green-drop "
          "and within-tolerance-worse cases, load_and_apply only sets adopt:true "
          "flags and never clobbers an explicit override, baseline builder never "
          "reads shipped_flags.")


if __name__ == "__main__":
    main()
