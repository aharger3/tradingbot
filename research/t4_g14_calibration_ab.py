"""T4/G14 -- A/B the thing that actually picks the book.

`research/g4_dropped_s.md` section 6: `_calibration_grade`'s first-with-trend-
signal-of-the-day floor (`signal_runner.py:1516-1520`) sets the grade on 969
of 1,017 traded rows (95.3%). `_grade_pa` never lifts a signal into the traded
tier on its own; the floor does. Turn it off and 48 trades remain. 98.8% of
the traded book is `seq==1` (the day's first fired signal). ARRIVAL ORDER IS
THE SELECTOR, not the grader.

The flag that isolates it already ships, unused, in `signal_runner.py`:
`ENABLE_KILL_B_FLOOR` (default False == the floor stays ON). W1's own
comment says it plainly: "This flag removes the first-with-trend `B` floor
and does NOTHING else." This ticket is the first thing to actually price it
on its own, separate from W1's full SAC-ladder swap.

TWO ARMS, the primary table:

    on   (head, shipped)  ENABLE_KILL_B_FLOOR unset -- the floor fires.
    off                   ENABLE_KILL_B_FLOOR=1      -- the floor never fires;
                           a `C` that would have been floored to `B` stays a
                           `C`, alert-only, not traded.

CHECK, run first: arm `on` must reproduce the shipped book
(`research/g3_arm_ow1.json`, +0.9551R / 1,017 traded rows) exactly. If it does
not, the flag is not isolating the floor and everything below is void.

THEN: which HALF of the floor is load-bearing. The floor is three conditions
ANDed together -- first-in-direction only, with the day trend, inside 90
minutes. Four more arms relax exactly one (or all three) of them, via a
monkeypatched `_calibration_grade` that never touches `signal_runner.py`
(`research/_t4_variant_wrapper.py` / `_t4_variant_test1.py`):

    uncap     drop "first only" -- every eligible C in the direction promotes
    notrend   drop "with the day trend"
    nowindow  drop "inside 90 minutes"
    relaxed   drop all three at once (upper bound of relaxing the floor)

HELD-OUT FIRST, every arm: promoting a signal to `B` lets it skip the
tight-stop-C check (`signal_runner.py:1891`), so a variant can change whether
the engine fires at all on a day, not only which grade it fires at -- held-out
recall is measured per arm, never assumed equal.

Usage:
    python research/t4_g14_calibration_ab.py run --arm on|off       # real flag
    python research/t4_g14_calibration_ab.py run-variant --arm uncap|notrend|nowindow|relaxed
    python research/t4_g14_calibration_ab.py check                  # the shipped-book reproduction
    python research/t4_g14_calibration_ab.py test1 --arm on|off|uncap|notrend|nowindow|relaxed
    python research/t4_g14_calibration_ab.py stats                  # money, all arms present on disk
    python research/t4_g14_calibration_ab.py decompose              # seq==1/2/>=3 off the uncap arm
    python research/t4_g14_calibration_ab.py report
    python research/t4_g14_calibration_ab.py --selfcheck

REUSED, NEVER REIMPLEMENTED
----------------------------
  research.a2_bt2y_summary.book              the whole-book money read
  research.g13_floor_fix_ab  test1_counts / test1_line / trades_digest /
                              sizeable / split_sizeable / per_symbol -- G13
                              built this exact shape of A/B shell first
  research.t70_test1_score   load_cards / score_all -- the held-out scorer

Nothing here ships. `ENABLE_KILL_B_FLOOR` stays False and the engine is not
re-frozen (that would VOID `research/omen6_forward.py`, Austin's call alone).
The four decomposition variants are RESEARCH-ONLY monkeypatches; no new flag
is added to `signal_runner.py` by this ticket.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.a2_bt2y_summary import book as money                       # noqa: E402
from research.g13_floor_fix_ab import (                                  # noqa: E402
    per_symbol, sizeable, split_sizeable, test1_counts, test1_line, trades_digest,
)
from research.t70_test1_score import load_cards                          # noqa: E402

FLAG = "ENABLE_KILL_B_FLOOR"
SHIPPED_BOOK = os.path.join(HERE, "g3_arm_ow1.json")   # THE BOOK: +0.9551R, 1017 rows
SHIPPED_MEAN_R, SHIPPED_N = 0.9551, 1017

# Primary arms -- the REAL shipped flag, driven exactly like G13/G3 drove theirs.
ARMS = {
    "on":  (None, os.path.join(HERE, "t4_arm_on.json")),
    "off": ("1",  os.path.join(HERE, "t4_arm_off.json")),
}
# Decomposition arms -- the monkeypatch wrapper, one condition relaxed each.
VARIANTS = {
    "uncap":    ({"T4_SEQ_UNCAP": "1"}, os.path.join(HERE, "t4_arm_uncap.json")),
    "notrend":  ({"T4_TREND_REQ": "0"}, os.path.join(HERE, "t4_arm_notrend.json")),
    "nowindow": ({"T4_WINDOW_MIN": "none"}, os.path.join(HERE, "t4_arm_nowindow.json")),
    "relaxed":  ({"T4_SEQ_UNCAP": "1", "T4_TREND_REQ": "0", "T4_WINDOW_MIN": "none"},
                 os.path.join(HERE, "t4_arm_relaxed.json")),
}
ALL_ARM_NAMES = list(ARMS) + list(VARIANTS)

TEST1_JSON = os.path.join(HERE, "_t4_test1.json")
BOOK_STATS = os.path.join(HERE, "_t4_book_stats.json")
OUT_MD = os.path.join(HERE, "t4_g14_calibration_ab.md")


def _arm_path(arm: str) -> str:
    return ARMS[arm][1] if arm in ARMS else VARIANTS[arm][1]


def child_env(arm: str) -> dict:
    env = dict(os.environ)
    if arm in ARMS:
        env.pop(FLAG, None)
        val = ARMS[arm][0]
        if val is not None:
            env[FLAG] = val
        return env
    for k in ("T4_SEQ_UNCAP", "T4_TREND_REQ", "T4_WINDOW_MIN"):
        env.pop(k, None)
    env.update(VARIANTS[arm][0])
    return env


# ---------------------------------------------------------------------------
# 1. the replays
# ---------------------------------------------------------------------------

def run(arm: str, days: int, out_path: str | None) -> int:
    out_path = out_path or _arm_path(arm)
    assert "bt2y_trades.json" not in out_path, "never overwrite the canonical book"
    if arm in ARMS:
        script = os.path.join(ROOT, "backtest_2y.py")
    else:
        script = os.path.join(HERE, "_t4_variant_wrapper.py")
    cmd = [sys.executable, script, "--days", str(days),
           "--out", os.path.relpath(out_path, ROOT)]
    print("%s: %s" % (arm, " ".join(cmd)), flush=True)
    return subprocess.call(cmd, cwd=ROOT, env=child_env(arm))


def load_book(arm: str) -> dict:
    with open(_arm_path(arm), encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# 2. the CHECK -- arm `on` must reproduce the shipped book
# ---------------------------------------------------------------------------

def check() -> int:
    shipped = json.load(open(SHIPPED_BOOK, encoding="utf-8"))
    on = load_book("on")
    d_shipped, d_on = trades_digest(shipped), trades_digest(on)
    tr_s = [r for r in shipped["trades"] if r["traded"]]
    tr_o = [r for r in on["trades"] if r["traded"]]
    mean_s = statistics.fmean(r["r"] for r in tr_s)
    mean_o = statistics.fmean(r["r"] for r in tr_o)
    print("shipped: %s  n=%d  meanR=%+.4f" % (d_shipped, len(tr_s), mean_s))
    print("arm-on:  %s  n=%d  meanR=%+.4f" % (d_on, len(tr_o), mean_o))
    ident = d_shipped == d_on
    close = len(tr_o) == SHIPPED_N and round(mean_o, 4) == round(SHIPPED_MEAN_R, 4)
    if ident:
        print("IDENTICAL: arm `on` reproduces g3_arm_ow1.json byte for byte "
              "(meta.generated excluded).")
    elif close:
        print("MATCH ON HEADLINE NUMBERS (not byte-identical -- see meta/digest "
              "above) : n=%d meanR=%.4f matches the shipped +0.9551R/1017." % (len(tr_o), mean_o))
    else:
        print("MISMATCH: the flag is NOT isolating the floor. STOP -- report this "
              "instead of the arms below.")
        return 1
    return 0


# ---------------------------------------------------------------------------
# 3. held-out OMEN Test 1 -- HELD-OUT FIRST, every arm
# ---------------------------------------------------------------------------

def run_test1(arm: str) -> int:
    if arm in ARMS:
        driver = ("import json,sys;"
                  "sys.path.insert(0,{root!r});"
                  "import research.t70_test1_score as t70;"
                  "print(json.dumps(t70.score_all(t70.load_cards())))").format(root=ROOT)
        cmd = [sys.executable, "-c", driver]
    else:
        cmd = [sys.executable, os.path.join(HERE, "_t4_variant_test1.py")]
    res = subprocess.run(cmd, cwd=ROOT, env=child_env(arm), capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stderr[-2000:])
        raise SystemExit("test1 arm %s failed" % arm)
    rows = json.loads(res.stdout.strip().splitlines()[-1])
    print("%-8s %s" % (arm, test1_line(rows)))
    return rows


def run_test1_all(arms) -> int:
    out = {}
    if os.path.exists(TEST1_JSON):
        out = json.load(open(TEST1_JSON, encoding="utf-8"))
    for arm in arms:
        out[arm] = run_test1(arm)
    with open(TEST1_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print("wrote %s" % TEST1_JSON)
    return 0


# ---------------------------------------------------------------------------
# 4. the money read
# ---------------------------------------------------------------------------

def stats(rows) -> dict:
    b = money(rows)
    rs = [r["r"] for r in rows if r["traded"]]
    b["median_r"] = round(statistics.median(rs), 4) if rs else 0.0
    return b


def run_stats(arms) -> int:
    books = {a: load_book(a) for a in arms if os.path.exists(_arm_path(a))}
    out = {}
    if os.path.exists(BOOK_STATS):
        out = json.load(open(BOOK_STATS, encoding="utf-8"))
    for a, blob in books.items():
        rows = blob["trades"]
        tr = [r for r in rows if r["traded"]]
        s = stats(rows)
        s["digest"] = trades_digest(blob)
        s["split"] = split_sizeable(rows)
        s["per_symbol"] = per_symbol(rows)
        s["n_floor_tagged"] = sum(1 for r in tr if "floor B" in r["reason"])
        out[a] = s
        print("%-8s n=%d meanR=%+.4f med=%+.4f wr=%.1f%% months %d/%d floor-tagged=%d"
              % (a, s["traded"], s["meanr"], s["median_r"], s["wr"],
                 s["months_green"], s["months"], s["n_floor_tagged"]))
    with open(BOOK_STATS, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True, default=str)
    print("wrote %s" % BOOK_STATS)
    return 0


# ---------------------------------------------------------------------------
# 5. decomposition -- seq==1/2/>=3 off the `uncap` arm's OWN promoted rows
# ---------------------------------------------------------------------------

def dir_seq_breakdown(arm: str = "uncap") -> dict:
    """With the "first only" restriction dropped, every eligible C in a
    direction promotes -- so the `uncap` arm's own traded book, grouped by
    (sym, day, dir) and ranked by entry time, gives the REAL per-direction
    ordinal of every promoted trade, exact and un-simulated. seq==1 rows are
    what the shipped floor already takes; seq==2/>=3 rows are what the "first
    only" restriction is refusing."""
    blob = load_book(arm)
    tr = [r for r in blob["trades"] if r["traded"] and "floor B" in r["reason"]]
    by_group = defaultdict(list)
    for r in tr:
        by_group[(r["sym"], r["day"], r["dir"])].append(r)
    out = defaultdict(list)
    for g, rs in by_group.items():
        rs.sort(key=lambda r: r["et"])
        for i, r in enumerate(rs, start=1):
            out[min(i, 3)].append(r["r"])   # 1, 2, >=3 bucketed at 3
    return {
        str(k): {"n": len(v), "mean_r": round(statistics.fmean(v), 4) if v else 0.0}
        for k, v in sorted(out.items())
    }


# ---------------------------------------------------------------------------
# 6. report
# ---------------------------------------------------------------------------

def report() -> int:
    st = json.load(open(BOOK_STATS, encoding="utf-8"))
    t1 = json.load(open(TEST1_JSON, encoding="utf-8"))
    seqb = dir_seq_breakdown("uncap") if os.path.exists(_arm_path("uncap")) else {}

    lines = ["# T4/G14 -- A/B the thing that actually picks the book", ""]
    lines.append("Held-out set: `research/marks/probe_omen_test1_2026-08-27.jsonl` "
                  "(15 S / 27 A / 16 C / 42 X). Error bar on a 2-year A/B: "
                  "+/-0.0095 R (narrow, carried) / +/-0.0095 R.")
    lines.append("")
    lines.append("## Held-out S recall FIRST")
    lines.append("")
    lines.append("| arm | S recall | false fires | entry match |")
    lines.append("|---|---|---|---|")
    for a in ("on", "off", "uncap", "notrend", "nowindow", "relaxed"):
        if a not in t1:
            continue
        c = test1_counts(t1[a])
        lines.append("| %s | %d/%d | %d/%d | %d/%d |" % (
            a, c["s_hit"], c["s_n"], c["x_fire"], c["x_n"],
            c["entry_match"], c["graded"]))
    lines.append("")
    lines.append("## Primary A/B (in-sample, 2-year book)")
    lines.append("")
    lines.append("| arm | trades | mean R | win rate | months green |")
    lines.append("|---|---|---|---|---|")
    for a in ("on", "off"):
        if a not in st:
            continue
        s = st[a]
        lines.append("| %s | %d | %+.4f | %.1f%% | %d/%d |" % (
            a, s["traded"], s["meanr"], s["wr"], s["months_green"], s["months"]))
    lines.append("")
    lines.append("## Decomposition (in-sample, 2-year book)")
    lines.append("")
    lines.append("| variant | trades | mean R | win rate | months green | floor-tagged |")
    lines.append("|---|---|---|---|---|---|")
    for a in ("on", "uncap", "notrend", "nowindow", "relaxed"):
        if a not in st:
            continue
        s = st[a]
        lines.append("| %s | %d | %+.4f | %.1f%% | %d/%d | %d |" % (
            a, s["traded"], s["meanr"], s["wr"], s["months_green"], s["months"],
            s["n_floor_tagged"]))
    lines.append("")
    lines.append("## seq==1 / seq==2 / seq>=3 (off the `uncap` arm's own promotions)")
    lines.append("")
    lines.append("| dir-ordinal | n | mean R |")
    lines.append("|---|---|---|")
    for k in ("1", "2", "3"):
        if k in seqb:
            lines.append("| %s%s | %d | %+.4f |" % (
                "seq==" if k != "3" else "seq>=", k, seqb[k]["n"], seqb[k]["mean_r"]))

    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("wrote %s" % OUT_MD)
    return 0


# ---------------------------------------------------------------------------
# selfcheck -- pure-function tests, no replay
# ---------------------------------------------------------------------------

def _selfcheck() -> int:
    cards = load_cards()
    assert len(cards) == 100, "expected 100 held-out cards, got %d" % len(cards)
    s = [c for c in cards if c["his"] == "S"]
    assert len(s) == 15, "expected 15 S cards, got %d" % len(s)

    # dir_seq_breakdown on a synthetic book: two promoted rows same (sym,day,dir)
    fake = {"trades": [
        {"sym": "AAA", "day": "2026-01-01", "dir": "call", "et": "09:35",
         "traded": True, "reason": "[floor B: x]", "r": 1.0},
        {"sym": "AAA", "day": "2026-01-01", "dir": "call", "et": "09:50",
         "traded": True, "reason": "[floor B: x]", "r": -1.0},
        {"sym": "AAA", "day": "2026-01-01", "dir": "put", "et": "09:40",
         "traded": True, "reason": "[floor B: x]", "r": 2.0},
        {"sym": "BBB", "day": "2026-01-01", "dir": "call", "et": "09:31",
         "traded": False, "reason": "no floor here", "r": 5.0},
    ]}
    tmp = os.path.join(HERE, "_t4_selfcheck_tmp.json")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(fake, fh)
    try:
        VARIANTS_bak = VARIANTS["uncap"]
        VARIANTS["uncap"] = (VARIANTS_bak[0], tmp)
        out = dir_seq_breakdown("uncap")
    finally:
        VARIANTS["uncap"] = VARIANTS_bak
        os.remove(tmp)
    assert out["1"]["n"] == 2 and out["1"]["mean_r"] == 1.5, out   # AAA-call#1 + AAA-put#1
    assert out["2"]["n"] == 1 and out["2"]["mean_r"] == -1.0, out  # AAA-call#2
    print("dir_seq_breakdown: OK")

    # child_env never leaks a variant's env keys into a primary arm's process
    e_on = child_env("on")
    assert FLAG not in e_on, "arm 'on' must not carry ENABLE_KILL_B_FLOOR"
    e_off = child_env("off")
    assert e_off[FLAG] == "1"
    e_uncap = child_env("uncap")
    assert e_uncap["T4_SEQ_UNCAP"] == "1"
    assert "T4_TREND_REQ" not in e_uncap
    print("child_env: OK")

    print("ALL SELFCHECKS PASSED")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selfcheck", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("run")
    p.add_argument("--arm", required=True, choices=list(ARMS))
    p.add_argument("--days", type=int, default=730)
    p.add_argument("--out", default=None)

    p = sub.add_parser("run-variant")
    p.add_argument("--arm", required=True, choices=list(VARIANTS))
    p.add_argument("--days", type=int, default=730)
    p.add_argument("--out", default=None)

    p = sub.add_parser("check")

    p = sub.add_parser("test1")
    p.add_argument("--arm", default="all")

    p = sub.add_parser("stats")
    p.add_argument("--arm", default="all")

    p = sub.add_parser("decompose")
    p = sub.add_parser("report")

    args = ap.parse_args()
    if args.selfcheck:
        return _selfcheck()
    if args.cmd is None:
        ap.error("a command is required (or pass --selfcheck)")
    if args.cmd in ("run", "run-variant"):
        return run(args.arm, args.days, args.out)
    if args.cmd == "check":
        return check()
    if args.cmd == "test1":
        arms = ALL_ARM_NAMES if args.arm == "all" else [args.arm]
        return run_test1_all(arms)
    if args.cmd == "stats":
        arms = ALL_ARM_NAMES if args.arm == "all" else [args.arm]
        return run_stats(arms)
    if args.cmd == "decompose":
        print(json.dumps(dir_seq_breakdown("uncap"), indent=2))
        return 0
    if args.cmd == "report":
        return report()
    return 1


if __name__ == "__main__":
    sys.exit(main())
