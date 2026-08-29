"""T14 -- the arrival-order ladder, pinned.

Four things are asserted, and each one is a way this track could lie:

  1. `ARRIVAL_LADDER` defaults to `"off"` and an unknown mode is a hard error.
     A flag that silently falls back to the incumbent makes an ON arm a copy of
     the OFF arm and the A/B reports a null that was never run.
  2. THE R18 INVARIANT -- **arrival order may promote and must never cap an S.**
     Austin: "don't let it cap you of S opportunities". Asserted structurally on
     `s_promote` (its only write is `C -> B`, one rung UP) and behaviourally on
     a replayed sample (no signal's grade is lower in an arm than in `off`
     because of the arrival rung).
  3. Every rung is REACHABLE. `CLAUDE.md` standing rule 3, and four rules in
     this project have already turned out to be branches that could never fire.
  4. `B` is not in the range of `gate` or `credit` -- killing the legacy letter
     is what those arms are for -- while `s_promote` writes `B` on purpose,
     because it changes the population and not the alphabet.

    python research/test_t14_arrival_ladder.py

No mark file is read or written here.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.t14_arrival_ladder import ladder, credit_net    # noqa: E402

# A small fixed sample of archived symbol-days. Ten of them are days the
# committed `off` book (`research/bt2y_trades.json`) shows carrying at least one
# alert-only `C` whose downgrade count says **S** -- the exact rows `s_promote`
# exists to reach -- so the reachability assertions below test a rung that has
# something to act on rather than testing the sample. The other two are ordinary
# days, kept so the `off` arm is not measured only on hand-picked ones.
SAMPLE = [
    ("ORCL", "2026-04-30"), ("COIN", "2025-04-10"), ("SPY", "2025-03-07"),
    ("COIN", "2026-02-24"), ("CRM", "2025-08-15"), ("AVGO", "2024-09-20"),
    ("TSLA", "2024-10-28"), ("HOOD", "2025-01-21"), ("COIN", "2024-10-30"),
    ("NVDA", "2026-07-28"), ("NVDA", "2024-08-21"), ("QQQ", "2025-03-11"),
]

# The probe reads `runner.captured` -- the RAW signal dicts -- not
# `t4_engine_recall.run_day`'s return value: that projects a fixed field list and
# drops `reason` and `arrival_first`, which are exactly what has to be asserted
# here. The replay loop is the same one `run_day` runs, over the same helpers.
_PROBE = r"""
import json, sys
sys.path.insert(0, %r); sys.path.insert(0, %r)
from research.t4_engine_recall import (CaptureRunner, rth_candles,
                                       prior_day_levels, premarket_extremes,
                                       htf_bias)
out = {}
for sym, day in %r:
    candles = rth_candles(sym, day)
    if not candles:
        continue
    r = CaptureRunner(sym)
    r.pdh, r.pdl, r.pd_open, r.pd_close = prior_day_levels(sym, day)
    r.pmh, r.pml = premarket_extremes(sym, day)
    r.htf_bias = htf_bias(sym, day)
    r.qqq_breaks = None
    for i in range(5, len(candles)):
        r.candles = candles[: i + 1]
        r.detect_signals()
    for n, s in enumerate(r.captured):
        key = "%%s|%%s|%%d" %% (sym, day, n)
        out[key] = {"grade": s.get("grade"),
                    "arrival_first": s.get("arrival_first"),
                    "status": s.get("status"),
                    "reason": s.get("reason") or ""}
print("@@" + json.dumps(out))
"""


def probe(mode: str) -> dict:
    env = dict(os.environ)
    env.pop("ENABLE_SAC_LADDER", None)
    env.pop("ENABLE_KILL_B_FLOOR", None)
    if mode == "off":
        env.pop("ARRIVAL_LADDER", None)
    else:
        env["ARRIVAL_LADDER"] = mode
    p = subprocess.run([sys.executable, "-c", _PROBE % (ROOT, HERE, SAMPLE)],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-800:]
    line = [l for l in p.stdout.splitlines() if l.startswith("@@")][-1]
    return json.loads(line[2:])


RANK = {"A+": 4, "A": 3, "B": 2, "C": 1, "X": 0, "D": 0}


def main():
    # ---- 1. the flag ------------------------------------------------------
    import signal_runner as sr
    assert sr.ARRIVAL_LADDER == "off", \
        "ARRIVAL_LADDER must default to off, got %r" % sr.ARRIVAL_LADDER
    assert sr.ARRIVAL_LADDER_MODES == (
        "off", "s_promote", "gate", "credit", "credit_all"), sr.ARRIVAL_LADDER_MODES
    env = dict(os.environ, ARRIVAL_LADDER="not_a_mode")
    p = subprocess.run([sys.executable, "-c", "import signal_runner"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    assert p.returncode != 0 and "ARRIVAL_LADDER must be one of" in p.stderr, \
        "an unknown ARRIVAL_LADDER must be a hard error, not a silent fallback"
    print("1. flag: default off, unknown mode raises            OK")

    # ---- the ladder arithmetic -------------------------------------------
    assert [ladder(n) for n in (-2, 0, 1, 2, 5)] == ["S", "S", "A", "C", "C"]
    # a credit is a -1 and never a +1: it can only move a grade UP the ladder
    for net in range(-2, 6):
        assert RANK[{"S": "A+", "A": "A", "C": "C"}[ladder(credit_net(net, True))]] >= \
               RANK[{"S": "A+", "A": "A", "C": "C"}[ladder(credit_net(net, False))]]
    print("   the credit is signed so it can only promote        OK")

    # ---- replay every arm over the sample --------------------------------
    arms = {m: probe(m) for m in
            ("off", "s_promote", "gate", "credit", "credit_all")}
    off = arms["off"]
    assert off, "the sample replayed no signals at all -- fix SAMPLE"
    print("   sample: %d signals over %d symbol-days             OK"
          % (len(off), len(SAMPLE)))

    # ---- 2. THE R18 INVARIANT --------------------------------------------
    # `s_promote` leaves the incumbent chain alone and only ever floors a `C`
    # up to `B`. So no signal may come back with a LOWER grade than `off`.
    sp = arms["s_promote"]
    lowered = [k for k, v in sp.items()
               if k in off and RANK[v["grade"]] < RANK[off[k]["grade"]]]
    assert not lowered, \
        "s_promote lowered %d grades -- arrival order must never cap: %s" % (
            len(lowered), lowered[:5])
    promoted = [k for k, v in sp.items()
                if k in off and RANK[v["grade"]] > RANK[off[k]["grade"]]]
    for k in promoted:
        assert off[k]["grade"] == "C" and sp[k]["grade"] == "B", \
            "s_promote may only write C -> B, saw %s -> %s" % (
                off[k]["grade"], sp[k]["grade"])
        assert "T14/s_promote" in sp[k]["reason"], sp[k]["reason"]
    print("2. R18: s_promote never lowers a grade (%d promoted)  OK" % len(promoted))

    # The arrival predicate is a real column on every signal in every arm --
    # never None, or the reachability numbers below would be counting absence.
    for m, rows in arms.items():
        missing = [k for k, v in rows.items() if v["arrival_first"] is None]
        assert not missing, "%s left arrival_first unset on %d signals" % (
            m, len(missing))
    # It is NOT asserted to be the same population in every arm, and that is a
    # finding rather than a looser test: promoting an alert-only `C` to `B`
    # bypasses `_min_viable_stop` (the tight-stop skip applies only to `C`), so
    # a row that was skipped can now be accepted, increment `_dir_fired`, and
    # take `arrival_first` from a later signal. The count is printed because the
    # report has to carry it.
    moved = {m: sum(1 for k in set(rows) & set(off)
                    if rows[k]["arrival_first"] != off[k]["arrival_first"])
             for m, rows in arms.items() if m != "off"}
    print("   arrival_first set on every signal; moved by arm %s  OK" % moved)

    # ---- 3. every rung reachable -----------------------------------------
    n_first = sum(1 for v in off.values() if v["arrival_first"])
    assert n_first > 0, "the arrival rung never fired on the sample"
    floored = sum(1 for v in off.values() if "floor B: first with-trend" in v["reason"])
    assert floored > 0, "the B floor never fired on the sample"
    for m in ("gate", "credit", "credit_all"):
        tagged = sum(1 for v in arms[m].values() if "[T14/" in v["reason"])
        assert tagged > 0, "%s never wrote a grade on the sample" % m
    changed = {m: sum(1 for k, v in arms[m].items()
                      if k in off and v["grade"] != off[k]["grade"])
               for m in arms if m != "off"}
    for m, n in changed.items():
        assert n > 0, "%s changed no grade at all -- an unreachable arm" % m
    print("3. reachable: floor %d, changed grades %s   OK"
          % (floored, {m: n for m, n in sorted(changed.items())}))

    # ---- 4. the alphabet --------------------------------------------------
    for m in ("gate", "credit"):
        wrote_b = [k for k, v in arms[m].items()
                   if v["grade"] == "B" and "[T14/" in v["reason"]]
        assert not wrote_b, "%s wrote B on %d signals -- killing B is the point" % (
            m, len(wrote_b))
    mix = Counter(v["grade"] for v in arms["credit"].values())
    assert set(mix) <= {"A+", "A", "C", "B", "X", "D"}, mix
    print("4. gate/credit never write B                          OK")

    print("\nall T14 assertions pass")


if __name__ == "__main__":
    main()
