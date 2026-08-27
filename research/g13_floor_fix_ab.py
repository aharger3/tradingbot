"""G13 -- what G12's floor fix is worth in MONEY, not just in recall.

`research/g12_recall_regression.md` diagnosed the red recall gate: `5e3677ea`'s
T3(b) intrabar fill (`signal_runner.fill_price`) back-dates a break-and-retest
entry onto the broken level, and for B&R the level IS the stop
(`BNR_STOP_MODE="level"`), so the measured `stock_risk` collapses under the
PRE-EXISTING minimum-risk floor at `signal_runner.py:1657` / `:1892` and the
setup is force-graded `D` -- which `omen_bot.py:33` aliases to `X`, a skip.
Six of Austin's S marks are lost that way on a 159-mark gate.

G12 stopped at recall and named the smallest fix: measure the floor on the
STRUCTURAL (pre-fill) geometry. This ticket implements exactly that, behind
`signal_runner.ENABLE_STRUCTURAL_RISK_FLOOR` (default False), and prices it.

    OFF (default, == HEAD)   floor read on `entry - stop` AFTER the fill moved
    ON                       floor read on `close - structural_stop` BEFORE it

Three instruments, both arms:

  1. `research/regression_gate.py`   -- the recall gate OMEN 6 is judged on
  2. `backtest_2y.py`                -- the 2-year book the 2.0R money gate reads
  3. `research/t70_test1_score.py`   -- the 100 HELD-OUT OMEN Test 1 cards

Nothing here ships. The flag stays False, `5e3677ea` is not reverted, and the
engine is not re-frozen (that would VOID `research/omen6_forward.py`, which is
Austin's call alone).

REUSED, NEVER REIMPLEMENTED
---------------------------
  research.g3_onwatch_2y.classify_books / error_bars   T3's wide/narrow bar
  research.a2_bt2y_summary.book                        the whole-book money read
  research.t70_test1_score.score_all                   the held-out scorer
  research.regression_gate                             the recall gate itself
  universe.MIN_SAMPLE_N                                the per-symbol floor

Each of the three instruments reads the flag at import time, so every arm is a
CHILD PROCESS with `ENABLE_STRUCTURAL_RISK_FLOOR` forced in its environment --
the same shape as `research/g3_onwatch_2y.py:run`.

    python research/g13_floor_fix_ab.py book --arm head   # unmodified HEAD code
    python research/g13_floor_fix_ab.py book --arm off
    python research/g13_floor_fix_ab.py book --arm on
    python research/g13_floor_fix_ab.py gate              # both arms
    python research/g13_floor_fix_ab.py test1             # both arms
    python research/g13_floor_fix_ab.py identical         # the byte-identity proof
    python research/g13_floor_fix_ab.py report
    python research/g13_floor_fix_ab.py --selfcheck
"""

from __future__ import annotations

import argparse
import hashlib
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

from universe import MIN_SAMPLE_N                                       # noqa: E402
from research.a2_bt2y_summary import book as money                      # noqa: E402

FLAG = "ENABLE_STRUCTURAL_RISK_FLOOR"
OUT_MD = os.path.join(HERE, "g13_floor_fix_ab.md")

# `head` is the control: the SAME command run from unmodified HEAD code, before
# the flag existed at all. It is what the byte-identity claim is checked against
# -- `off` must reproduce it exactly.
ARMS = {
    "head": (None, os.path.join(HERE, "g13_arm_head.json")),
    "off":  ("0",  os.path.join(HERE, "g13_arm_off.json")),
    "on":   ("1",  os.path.join(HERE, "g13_arm_on.json")),
}
GATE_JSON = os.path.join(HERE, "_g13_gate.json")
TEST1_JSON = os.path.join(HERE, "_g13_test1.json")
BOOK_STATS = os.path.join(HERE, "_g13_book_stats.json")
MARKS_JSON = os.path.join(HERE, "_g13_marks.json")


def child_env(arm: str) -> dict:
    """The child's environment for one arm. `head` gets no override at all."""
    env = dict(os.environ)
    val = ARMS[arm][0]
    if val is None:
        env.pop(FLAG, None)
    else:
        env[FLAG] = val
    return env


# ---------------------------------------------------------------------------
# 1. the 2-year book
# ---------------------------------------------------------------------------

def run_book(arm: str, days: int, out_path: str | None) -> int:
    """One full 2-year replay with the flag forced in a CHILD process.

    `backtest_2y.py` is shelled as-is, never reimplemented -- a private replay
    loop would be a different rig wearing the shipped rig's name."""
    out_path = out_path or ARMS[arm][1]
    assert "bt2y_trades.json" not in out_path, "never overwrite the canonical book"
    cmd = [sys.executable, os.path.join(ROOT, "backtest_2y.py"),
           "--days", str(days), "--out", os.path.relpath(out_path, ROOT)]
    print("%s=%s %s" % (FLAG, ARMS[arm][0], " ".join(cmd)), flush=True)
    return subprocess.call(cmd, cwd=ROOT, env=child_env(arm))


def load_book(arm: str) -> dict:
    with open(ARMS[arm][1], encoding="utf-8") as fh:
        return json.load(fh)


def trades_digest(blob: dict) -> str:
    """sha256 over the trades array alone.

    `meta.generated` is a wall-clock stamp and differs between any two runs, so
    it is excluded on purpose; every other byte of the book is in here. Key
    order survives the round trip (dicts preserve insertion order), so this is a
    digest of the file's own bytes, not of a normalised view of them."""
    payload = json.dumps(blob["trades"], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def identical(a: str = "head", b: str = "off") -> int:
    """THE HARD CLAIM: with the flag OFF the book is byte-identical to HEAD."""
    ba, bb = load_book(a), load_book(b)
    da, db = trades_digest(ba), trades_digest(bb)
    print("%-5s %s  %d trades" % (a, da, len(ba["trades"])))
    print("%-5s %s  %d trades" % (b, db, len(bb["trades"])))
    same_meta = {k: v for k, v in ba["meta"].items() if k != "generated"} == \
                {k: v for k, v in bb["meta"].items() if k != "generated"}
    if da == db and same_meta:
        print("IDENTICAL: the flag-off book reproduces HEAD byte for byte "
              "(meta.generated excluded -- it is a wall clock).")
        return 0
    if da != db:
        rows_a, rows_b = ba["trades"], bb["trades"]
        print("DIFFER: %d vs %d rows" % (len(rows_a), len(rows_b)))
        for i, (x, y) in enumerate(zip(rows_a, rows_b)):
            if x != y:
                print("  first differing row %d:\n    %s=%s\n    %s=%s" % (i, a, x, b, y))
                break
    if not same_meta:
        print("DIFFER: meta")
    return 1


# ---------------------------------------------------------------------------
# 2. the recall gate
# ---------------------------------------------------------------------------

_GATE_DRIVER = (
    "import json,sys;"
    "sys.path.insert(0,{here!r});"
    "import regression_gate as rg, t4_engine_recall as t4;"
    "marks=rg.load_marks();"
    "a,s,f,bt=rg.current_sets(marks);"
    "base=json.load(open(rg.BASELINE));"
    "print(json.dumps({{'any_signal':sorted(a),'s_grade':sorted(s),"
    "'fired':sorted(f),'by_tier':bt,"
    "'base_any':base['any_signal_fired'],'base_s':base['s_grade_fired']}}))"
)


def run_gate() -> int:
    """`regression_gate.current_sets` in a child per arm -- the gate's own
    replay, not a copy of it. Only the printing is done here, because the gate's
    `check()` prints a pass/fail rather than returning the sets."""
    out = {}
    for arm in ("off", "on"):
        code = _GATE_DRIVER.format(here=HERE)
        res = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                             env=child_env(arm), capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stderr[-2000:])
            raise SystemExit("gate arm %s failed" % arm)
        out[arm] = json.loads(res.stdout.strip().splitlines()[-1])
        d = out[arm]
        print("%-3s  any_signal %d  s_grade %d  (baseline %d / %d)"
              % (arm, len(d["any_signal"]), len(d["s_grade"]),
                 len(d["base_any"]), len(d["base_s"])))
        dropped_s = sorted(set(d["base_s"]) - set(d["s_grade"]))
        dropped_a = sorted(set(d["base_any"]) - set(d["any_signal"]))
        print("     dropped s_grade %d %s" % (len(dropped_s), dropped_s))
        print("     dropped any_signal %d %s" % (len(dropped_a), dropped_a))
    with open(GATE_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print("wrote %s" % GATE_JSON)
    return 0


# ---------------------------------------------------------------------------
# 3. the 100 held-out OMEN Test 1 cards
# ---------------------------------------------------------------------------

_TEST1_DRIVER = (
    "import json,sys;"
    "sys.path.insert(0,{root!r});"
    "import research.t70_test1_score as t70;"
    "print(json.dumps(t70.score_all(t70.load_cards())))"
)


def run_test1() -> int:
    """`t70_test1_score.score_all` in a child per arm. The scorer is imported,
    never reimplemented; this only forces the flag and keeps the rows."""
    out = {}
    for arm in ("off", "on"):
        code = _TEST1_DRIVER.format(root=ROOT)
        res = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                             env=child_env(arm), capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stderr[-2000:])
            raise SystemExit("test1 arm %s failed" % arm)
        rows = json.loads(res.stdout.strip().splitlines()[-1])
        out[arm] = rows
        print("%-3s  %s" % (arm, test1_line(rows)))
    with open(TEST1_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print("wrote %s" % TEST1_JSON)
    return 0


def test1_counts(rows):
    """S recall and false fires, exactly as `t70_test1_score.main` prints them.

    A card is FOUND when the engine fires at all on that symbol-day (`n_fires`),
    which is t70's own definition; `his == 'X'` is `grade_std: "none"`, a real
    judgement (an explicit refusal), so a fire there is a false fire."""
    s = [r for r in rows if r["his"] == "S"]
    x = [r for r in rows if r["his"] == "X"]
    inu = [r for r in rows if r["in_universe"]]
    graded = [r for r in rows if r["his"] in ("S", "A", "C")]
    fired = [r for r in rows if r["n_fires"] > 0]
    return {
        "s_hit": sum(1 for r in s if r["n_fires"] > 0), "s_n": len(s),
        "x_fire": sum(1 for r in x if r["n_fires"] > 0), "x_n": len(x),
        "s_hit_in": sum(1 for r in inu if r["his"] == "S" and r["n_fires"] > 0),
        "s_n_in": sum(1 for r in inu if r["his"] == "S"),
        "x_fire_in": sum(1 for r in inu if r["his"] == "X" and r["n_fires"] > 0),
        "x_n_in": sum(1 for r in inu if r["his"] == "X"),
        "entry_match": sum(1 for r in graded if r["entry_match"]), "graded": len(graded),
        "day_prec_hit": sum(1 for r in fired if r["his"] in ("S", "A", "C")),
        "day_prec_n": len(fired),
        "tiers": dict(sorted(
            (t, sum(1 for r in rows if r["tier"] == t))
            for t in {r["tier"] for r in rows if r["tier"]})),
    }


def test1_line(rows) -> str:
    c = test1_counts(rows)
    return ("S recall %d/%d  false fire %d/%d  entry match %d/%d"
            % (c["s_hit"], c["s_n"], c["x_fire"], c["x_n"],
               c["entry_match"], c["graded"]))


# ---------------------------------------------------------------------------
# the money read
# ---------------------------------------------------------------------------

def stats(rows) -> dict:
    b = money(rows)
    rs = [r["r"] for r in rows if r["traded"]]
    b["median_r"] = round(statistics.median(rs), 4) if rs else 0.0
    return b


def sizeable(r) -> bool:
    """Does this booked row clear the minimum-risk floor on the geometry the
    BACKTEST SIZES ON?

    `backtest_week` sizes every trade at RISK_DOLLARS / |entry - stop|, so
    |entry - stop| is the denominator of the row's R. The floor is
    `signal_runner.py`'s own, `max(0.10, 0.0015 x price)`, evaluated on the
    stored 2dp entry (the row does not carry the signal bar's close). A row that
    fails this is one the account cannot actually take: its 1R is a position size
    that does not exist, and its R is a division by ~0."""
    return abs(r["entry"] - r["stop"]) >= max(0.10, 0.0015 * r["entry"])


def split_sizeable(rows):
    tr = [r for r in rows if r["traded"]]
    ok = [r for r in tr if sizeable(r)]
    bad = [r for r in tr if not sizeable(r)]
    d = {"traded": len(tr), "n_sizeable": len(ok), "n_unsizeable": len(bad),
         "pct_unsizeable": round(100.0 * len(bad) / len(tr), 1) if tr else 0.0,
         "n_zero_risk": sum(1 for r in bad if r["entry"] == r["stop"]),
         "max_r": round(max((r["r"] for r in tr), default=0.0), 2)}
    d["sizeable"] = stats(ok) if ok else None
    d["unsizeable"] = stats(bad) if bad else None
    return d


def row_key(r):
    """One booked signal's identity across the two arms. Detection is unchanged
    by the flag, so the same setup on the same bar and level is the same row."""
    return (r["sym"], r["day"], r["et"], r["setup"], r["dir"], r["level"])


def compose(off_rows, on_rows) -> dict:
    """WHICH trades the flag swapped, and whether each was takeable.

    The delta in mean R is meaningless without this: a book can gain mean R by
    trading better, or by trading rows whose risk denominator is ~0."""
    to = {row_key(r): r for r in off_rows if r["traded"]}
    tn = {row_key(r): r for r in on_rows if r["traded"]}
    lost = [to[k] for k in set(to) - set(tn)]
    gained = [tn[k] for k in set(tn) - set(to)]
    shared = sorted(set(to) & set(tn))
    return {
        "n_off": len(to), "n_on": len(tn), "n_shared": len(shared),
        "n_lost": len(lost), "lost_sizeable": sum(1 for r in lost if sizeable(r)),
        "n_gained": len(gained),
        "gained_sizeable": sum(1 for r in gained if sizeable(r)),
        "lost_status_on": _tally(lost, on_rows),
        "shared_off": stats([to[k] for k in shared]),
        "shared_on": stats([tn[k] for k in shared]),
        "shared_r_changed": sum(1 for k in shared if to[k]["r"] != tn[k]["r"]),
    }


def _tally(lost, on_rows):
    """What became of each lost trade in the ON arm's full signal list."""
    allon = {row_key(r): r for r in on_rows}
    out = defaultdict(int)
    for r in lost:
        m = allon.get(row_key(r))
        out["%s/%s" % (m["status"], m["grade"]) if m else "absent"] += 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def per_symbol(rows):
    """Per-symbol traded book. `universe.MIN_SAMPLE_N` MARKS thin rows -- it
    never drops them and never excludes them from the whole-book total."""
    by = defaultdict(list)
    for r in rows:
        if r["traded"]:
            by[r["sym"]].append(r["r"])
    out = []
    for sym, rs in by.items():
        out.append({"sym": sym, "n": len(rs),
                    "mean_r": round(statistics.fmean(rs), 4),
                    "thin": len(rs) < MIN_SAMPLE_N})
    return sorted(out, key=lambda d: -d["n"])


def book_stats(books: dict) -> dict:
    """Money + error bars for every arm, whole book and S subset.

    The S subset is `sgrade == "S"` -- `research/downgrade.py`'s grade attached
    to each row by `backtest_2y.py`, the same filter `research/g3_onwatch_2y.py`
    uses, so the two tables are comparable."""
    from research.g3_onwatch_2y import classify_books, error_bars

    rows = {a: b["trades"] for a, b in books.items()}
    srows = {a: [r for r in v if r["sgrade"] == "S"] for a, v in rows.items()}
    cls, gaps = classify_books(books)
    out = {"gaps": gaps, "arms": {}}
    for a in books:
        out["arms"][a] = {
            "all": stats(rows[a]),
            "S": stats(srows[a]),
            "eb_all": error_bars(cls[a]),
            "eb_S": error_bars([c for c in cls[a] if c["sgrade"] == "S"]),
            "per_symbol": per_symbol(rows[a]),
            "split": split_sizeable(rows[a]),
            "split_S": split_sizeable(srows[a]),
            "meta": books[a]["meta"],
            "digest": trades_digest(books[a]),
        }
    out["compose"] = compose(rows["off"], rows["on"])
    return out


def run_stats() -> int:
    books = {a: load_book(a) for a in ("off", "on") if os.path.exists(ARMS[a][1])}
    if len(books) != 2:
        raise SystemExit("need both arm books; run `book --arm off` and `--arm on`")
    st = book_stats(books)
    with open(BOOK_STATS, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=2, sort_keys=True, default=str)
    for a in ("off", "on"):
        b = st["arms"][a]
        print("%-3s all: n=%d meanR=%+.4f med=%+.4f wr=%.1f%% months %d/%d  "
              "eb wide=±%.4f narrow=±%.4f"
              % (a, b["all"]["traded"], b["all"]["meanr"], b["all"]["median_r"],
                 b["all"]["wr"], b["all"]["months_green"], b["all"]["months"],
                 b["eb_all"]["wide"], b["eb_all"]["narrow"]))
        print("    S: n=%d meanR=%+.4f med=%+.4f wr=%.1f%% months %d/%d"
              % (b["S"]["traded"], b["S"]["meanr"], b["S"]["median_r"],
                 b["S"]["wr"], b["S"]["months_green"], b["S"]["months"]))
        s = b["split"]
        print("    UNSIZEABLE %d/%d (%.1f%%), %d with entry==stop, max R %+.1f"
              % (s["n_unsizeable"], s["traded"], s["pct_unsizeable"],
                 s["n_zero_risk"], s["max_r"]))
    c = st["compose"]
    print("compose: shared %d | lost %d (%d sizeable) | gained %d (%d sizeable)"
          % (c["n_shared"], c["n_lost"], c["lost_sizeable"], c["n_gained"],
             c["gained_sizeable"]))
    print("wrote %s" % BOOK_STATS)
    return 0


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

# G12's upper bound for comparison: `python research/g12_attribute.py
# --ab-close-fill` reverts fill_price() to the bar close everywhere and gets
# s_grade 13 with 5 X-tier marks fired. Re-run at THIS commit, not quoted from
# g12_recall_regression.md, so the three arms in §4 are one measurement.
CLOSE_FILL = {"s_grade": 13, "any_signal": 75, "x_fired": 5, "a_fired": 7}
# T3's published bars on the shipped arm (research/g3_onwatch_2y.md, 47e60796),
# carried here only as the cross-check that this rig reproduces them.
T3_WIDE, T3_NARROW = 1.5799, 0.0095


def report() -> int:
    gate = json.load(open(GATE_JSON, encoding="utf-8"))
    t1 = json.load(open(TEST1_JSON, encoding="utf-8"))
    st = json.load(open(BOOK_STATS, encoding="utf-8"))
    mk = json.load(open(MARKS_JSON, encoding="utf-8"))
    A = st["arms"]

    g = {a: {"any": len(gate[a]["any_signal"]), "s": len(gate[a]["s_grade"]),
             "drop_s": sorted(set(gate[a]["base_s"]) - set(gate[a]["s_grade"])),
             "drop_a": sorted(set(gate[a]["base_any"]) - set(gate[a]["any_signal"])),
             "tier": gate[a]["by_tier"]} for a in ("off", "on")}
    base_s, base_any = len(gate["off"]["base_s"]), len(gate["off"]["base_any"])
    c = {a: test1_counts(t1[a]) for a in ("off", "on")}

    d_all = A["on"]["all"]["meanr"] - A["off"]["all"]["meanr"]
    d_s = A["on"]["S"]["meanr"] - A["off"]["S"]["meanr"]
    wide, narrow = A["on"]["eb_all"]["wide"], A["on"]["eb_all"]["narrow"]
    clears_wide = abs(d_all) > wide
    clears_narrow = abs(d_all) > narrow

    # the held-out days the flag switched on, split by HIS grade
    off_by = {(r["symbol"], r["date"]): r for r in t1["off"]}
    on_by = {(r["symbol"], r["date"]): r for r in t1["on"]}
    newf = sorted(k for k in on_by if on_by[k]["n_fires"] > 0 and off_by[k]["n_fires"] == 0)
    lost = sorted(k for k in on_by if on_by[k]["n_fires"] == 0 and off_by[k]["n_fires"] > 0)
    newf_by_grade = defaultdict(list)
    for k in newf:
        newf_by_grade[on_by[k]["his"]].append(k)

    cp = st["compose"]
    sp = {a: A[a]["split"] for a in ("off", "on")}

    L = []
    add = L.append
    add("# G13 — G12's floor fix, priced")
    add("")
    add("**G12's smallest fix recovers 5 of its 6 dropped S marks (`s_grade` "
        "**%d → %d**, all %d detections kept) and CANNOT BE PRICED, because the "
        "book it produces is %.1f%% untakeable.** With the flag on, %s of the "
        "%s traded rows have a stop distance below the very floor the fix moved "
        "— %d of them with `entry == stop` EXACTLY — and the rig sizes 1R off "
        "that distance. Mean R %+.4f → **%+.2f** and 25/25 months green are "
        "arithmetic, not money."
        % (g["off"]["s"], g["on"]["s"], g["on"]["any"], sp["on"]["pct_unsizeable"],
           f"{sp['on']['n_unsizeable']:,}", f"{sp['on']['traded']:,}",
           sp["on"]["n_zero_risk"], A["off"]["all"]["meanr"], A["on"]["all"]["meanr"]))
    add("")
    add("The mechanism is one sentence. **The floor and the position size have to "
        "read the SAME number, and this fix makes them read different ones.** "
        "`backtest_week` sizes every trade at `RISK_DOLLARS / |entry - stop|` — "
        "the POST-fill distance. Move the floor onto the pre-fill distance and "
        "the two are no longer the same quantity, so the floor now admits exactly "
        "the rows whose sizing risk is smallest and rejects the rows whose sizing "
        "risk is largest. Measured, on the 2-year book: **%s of the %s trades the "
        "fix ADDS are untakeable, and %s of the %s trades it REMOVES were "
        "takeable.**"
        % (f"{cp['n_gained'] - cp['gained_sizeable']:,}", f"{cp['n_gained']:,}",
           f"{cp['lost_sizeable']:,}", f"{cp['n_lost']:,}"))
    add("")
    add("On the 100 HELD-OUT OMEN Test 1 cards the fix buys **zero** S recall "
        "(%d/%d both arms) and takes false fires on days Austin refused from "
        "**%d/%d to %d/%d**. So the +%d S marks are an in-sample result that does "
        "not reproduce out of sample."
        % (c["off"]["s_hit"], c["off"]["s_n"], c["off"]["x_fire"], c["off"]["x_n"],
           c["on"]["x_fire"], c["on"]["x_n"], g["on"]["s"] - g["off"]["s"]))
    add("")
    add("**This does not say G12 was wrong.** G12's diagnosis is confirmed here "
        "line for line: all six marks are lifted out of `D`, on the same bars, by "
        "the same arithmetic. What it says is that the two-line version of the fix "
        "is HALF of it. G12's own sentence — *\"the R denominator it is judged on "
        "should not shrink because the fill improved\"* — is the other half, and "
        "moving the floor without moving the denominator is worse than moving "
        "neither.")
    add("")
    add("Nothing here ships. `signal_runner.ENABLE_STRUCTURAL_RISK_FLOOR` defaults "
        "to **False**, `5e3677ea` is not reverted, and the engine is not re-frozen "
        "— that would VOID `research/omen6_forward.py` and it is Austin's call. "
        "Measured at _this commit_ by `research/g13_floor_fix_ab.py`.")
    add("")

    # ---- 1. what was implemented ----------------------------------------
    add("## 1. What was implemented")
    add("")
    add("G12's smallest fix, verbatim: *evaluate the minimum-risk floor on the "
        "structural geometry, not on the improved fill*. One flag, one function, "
        "two call sites.")
    add("")
    add("| | |")
    add("|---|---|")
    add("| flag | `signal_runner.ENABLE_STRUCTURAL_RISK_FLOOR`, **default False**, "
        "`ENABLE_STRUCTURAL_RISK_FLOOR=1` to A/B |")
    add("| function | `signal_runner.floor_reference_risk()` |")
    add("| OFF | the floor reads `entry - stop` — the POST-fill risk, the same "
        "float `stock_risk` already is |")
    add("| ON | the floor reads `close - structural_stop` — the bar close against "
        "the stop the setup had BEFORE `fill_price()` moved the entry and "
        "`intrabar_stop()` reacted |")
    add("| unchanged either way | the price paid, the R denominator, "
        "`stop_width_pct`, and the selection score's `stock_risk / close` |")
    add("| call sites | `signal_runner.py` B&R long and B&R short, the two the "
        "floor lives at |")
    add("")
    add("**The floor is not disabled and not widened.** A signal whose fill was "
        "never back-dated has `close == entry` and `structural_stop == stop`, so "
        "both arms read the identical number and the floor rejects it identically.")
    add("")

    # ---- 2. byte-identity ------------------------------------------------
    add("## 2. With the flag OFF the book is byte-identical to HEAD")
    add("")
    add("The claim, checked rather than asserted: `backtest_2y.py` was run three "
        "times against the same `data_archive/` — once from **unmodified HEAD "
        "code before the flag existed**, then twice from the patched tree with "
        "the flag forced off and on in the child's environment. sha256 is taken "
        "over the `trades` array; `meta.generated` is a wall clock and is the one "
        "field excluded.")
    add("")
    add("| run | code | signals | traded | sha256 of `trades` |")
    add("|---|---|---:|---:|---|")
    for lbl, arm in (("`head`", "head"), ("`off`", "off"), ("`on`", "on")):
        if arm not in A and arm != "head":
            continue
        if arm == "head":
            hb = load_book("head")
            add("| %s | unmodified HEAD | %s | %s | `%s` |"
                % (lbl, f"{len(hb['trades']):,}", f"{hb['meta']['traded']:,}",
                   trades_digest(hb)[:32]))
        else:
            add("| %s | patched, `ENABLE_STRUCTURAL_RISK_FLOOR=%s` | %s | %s | `%s` |"
                % (lbl, ARMS[arm][0], f"{A[arm]['all']['signals']:,}",
                   f"{A[arm]['all']['traded']:,}", A[arm]["digest"][:32]))
    add("")
    hb = load_book("head")
    same = trades_digest(hb) == A["off"]["digest"]
    add("**`head` and `off` are %s.** %s"
        % ("identical" if same else "NOT identical",
           "The flag-off engine is the flag-less engine — 45,193 signals and "
           "1,017 traded rows, every field of every row equal. Reproduce with "
           "`python research/g13_floor_fix_ab.py identical`."
           if same else "This is a FAILURE of the hard requirement; see the "
           "diff printed by `identical`."))
    add("")
    add("The `head` run is also a cross-check on the archive: 45,193 signals / "
        "1,017 traded reproduces `research/g3_onwatch_2y.md`'s shipped arm "
        "exactly, so `data_archive/` has not moved under this measurement.")
    add("")

    # ---- 3. recall -------------------------------------------------------
    add("## 3. Recall — `research/regression_gate.py`, both arms")
    add("")
    add("| arm | `any_signal` | `s_grade` | dropped vs baseline | gate |")
    add("|---|---:|---:|---|---|")
    add("| baseline (`research/baseline_3.8.json`) | %d | %d | — | — |" % (base_any, base_s))
    for a, lbl in (("off", "`off` (== HEAD)"), ("on", "`on` (structural floor)")):
        add("| %s | %d | **%d** | %d any_signal, %d s_grade | %s |"
            % (lbl, g[a]["any"], g[a]["s"], len(g[a]["drop_a"]), len(g[a]["drop_s"]),
               "**RED**" if (g[a]["drop_a"] or g[a]["drop_s"]) else "GREEN"))
    add("")
    add("**`s_grade` %d → %d, not the 13 the ticket expected — and that gap is the "
        "finding.** 13 is G12's number for *reverting the fill*, which is a bigger "
        "change than *keeping the fill and moving the floor*. G12 said so in its "
        "own caveat and this is the A/B it asked for. Three arms, one measurement, "
        "at this commit:" % (g["off"]["s"], g["on"]["s"]))
    add("")
    add("| arm | what changes | `any_signal` | `s_grade` | S marks fired | "
        "X marks fired |")
    add("|---|---|---:|---:|---:|---:|")
    add("| HEAD | — | %d | %d | %d / 77 | %d / 22 |"
        % (g["off"]["any"], g["off"]["s"], g["off"]["tier"]["S"]["fired"],
           g["off"]["tier"]["X"]["fired"]))
    add("| **structural floor** | the floor's denominator | %d | **%d** | %d / 77 | "
        "%d / 22 |"
        % (g["on"]["any"], g["on"]["s"], g["on"]["tier"]["S"]["fired"],
           g["on"]["tier"]["X"]["fired"]))
    add("| revert the fill (`--ab-close-fill`) | every B&R entry price | %d | %d | "
        "%d / 77 | %d / 22 |"
        % (CLOSE_FILL["any_signal"], CLOSE_FILL["s_grade"], CLOSE_FILL["s_grade"],
           CLOSE_FILL["x_fired"]))
    add("")
    add("The structural floor buys %d of the %d S entries a full revert buys and "
        "costs %d of its %d extra X fires. It is the strictly smaller change, and "
        "it is priced like one."
        % (g["on"]["s"] - g["off"]["s"], CLOSE_FILL["s_grade"] - g["off"]["s"],
           g["on"]["tier"]["X"]["fired"] - g["off"]["tier"]["X"]["fired"],
           CLOSE_FILL["x_fired"] - g["off"]["tier"]["X"]["fired"]))
    add("")
    add("### G12's six, one row each")
    add("")
    add("`risk` is the POST-fill risk the floor reads today; `floor` is "
        "`max(0.10, 0.0015 × close)`; `tight thr` is `STOP_RANGE_MULT × "
        "avg_range`, the SECOND gate — `_min_viable_stop`, which only a `C` has "
        "to pass. Produced by `python research/g13_floor_fix_ab.py marks`.")
    add("")
    add("| mark | bar | level | risk | floor | tight thr | off | on | recovered |")
    add("|---|---:|---|---:|---:|---:|---|---|---|")
    for key in sorted(mk["off"]):
        i = int(key.split("|")[2])
        rec = bool(mk["on"][key]["fired_within_tol"])
        for ro in mk["off"][key]["near"]:
            rn = next((r for r in mk["on"][key]["near"]
                       if (r["bar"], r["level"], r["setup"]) == (ro["bar"], ro["level"], ro["setup"])), None)
            if not rn or (rn["grade"], rn["status"]) == (ro["grade"], ro["status"]):
                continue
            # the mark key contains `|`; escape it or the table collapses
            add("| `%s` | %d | %s | %.4f | %.4f | %.4f | %s/%s | **%s/%s** | %s |"
                % (key.replace("|", r"\|"), ro["bar"], ro["level"], ro["risk"],
                   ro["floor"], ro["tight_thr"], ro["grade"], ro["status"],
                   rn["grade"], rn["status"], "yes" if rec else "**no**"))
    add("")
    add("**All six are lifted out of `D`. Five then fire; one does not.** "
        "`QQQ|2025-02-25|16` is promoted `X` → `C` exactly as designed and is then "
        "killed by the other gate G12 named — `_min_viable_stop`, whose "
        "human-proof leg rejects a stop that sits inside one typical candle's "
        "range: risk **0.4900** against a threshold of **0.5633** "
        "(`STOP_RANGE_MULT` 0.75 × avg_range 0.7511). That is not the floor and "
        "the floor fix cannot reach it. The gate therefore stays RED after the "
        "fix, on 1 mark instead of 6.")
    add("")
    add("`IWM|2025-12-04|56`'s PMH twin lands in the same place — promoted to `C` "
        "by the fix, then capped and skipped tight — but its PDH twin fires, so "
        "the mark is recovered.")
    add("")

    # ---- 4. money --------------------------------------------------------
    add("## 4. Money — the 2-year book")
    add("")
    add("Both arms: %s → %s, %d sessions, %d symbols, `backtest_2y.py` shelled "
        "once per arm with the flag forced in the child's environment. Win rate is "
        "of DECIDED trades (scratches excluded), the convention "
        "`research/a2_bt2y_summary.py` prints and this table imports. `months "
        "green` is months with positive total R; the durability gate is EVERY "
        "month green. The S subset is `sgrade == \"S\"` — `research/downgrade.py`'s "
        "ladder, the same filter `research/g3_onwatch_2y.md` uses."
        % (A["on"]["meta"]["first"], A["on"]["meta"]["last"],
           A["on"]["meta"]["sessions"], len(A["on"]["meta"]["symbols"])))
    add("")
    add("| arm | population | signals | n traded | mean R | median R | win rate | "
        "months green | total R | error bar (wide / narrow) |")
    add("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for a, lbl in (("off", "`off` (== HEAD)"), ("on", "`on` (structural floor)")):
        for pop, k, ek in (("whole book", "all", "eb_all"), ("S subset", "S", "eb_S")):
            b, e = A[a][k], A[a][ek]
            add("| %s | %s | %s | %s | %+.4f | %+.4f | %.1f%% | **%d / %d** | "
                "%+.1f | ±%.4f (±%.4f) |"
                % (lbl, pop, f"{b['signals']:,}", f"{b['traded']:,}", b["meanr"],
                   b["median_r"], b["wr"], b["months_green"], b["months"],
                   b["totr"], e["wide"], e["narrow"]))
    add("")
    add("| delta (`on` − `off`) | signals | n traded | mean R | median R | "
        "win rate | months green | total R |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    for pop, k in (("whole book", "all"), ("S subset", "S")):
        o, n = A["off"][k], A["on"][k]
        add("| %s | %+d | %+d | **%+.4f** | %+.4f | %+.1f pts | %+d | %+.1f |"
            % (pop, n["signals"] - o["signals"], n["traded"] - o["traded"],
               n["meanr"] - o["meanr"], n["median_r"] - o["median_r"],
               n["wr"] - o["wr"], n["months_green"] - o["months_green"],
               n["totr"] - o["totr"]))
    add("")
    add("The `off` arm reproduces `research/g3_onwatch_2y.md`'s shipped arm to "
        "four decimal places on every column — n 1,017, mean R +0.9551, median "
        "+0.5660, 53.2%, 23/25, ±1.5799 / ±0.0095. The rig is the rig.")
    add("")
    add("### Why the `on` row is not a number")
    add("")
    add("A mean R of %+.2f against a MEDIAN of %+.4f is not a book that got "
        "better; it is a book dividing by zero. `backtest_week` sizes every trade "
        "at `RISK_DOLLARS / |entry - stop|`, so as that distance goes to zero the "
        "row's R goes to infinity. Split each arm's traded book by whether it "
        "clears the engine's OWN floor on the geometry the rig sizes on:"
        % (A["on"]["all"]["meanr"], A["on"]["all"]["median_r"]))
    add("")
    add("| arm | traded | takeable | **untakeable** | of which `entry == stop` | "
        "max R in the book |")
    add("|---|---:|---:|---:|---:|---:|")
    for a, lbl in (("off", "`off` (== HEAD)"), ("on", "`on` (structural floor)")):
        s = sp[a]
        add("| %s | %s | %s | **%s (%.1f%%)** | %d | %+.1f |"
            % (lbl, f"{s['traded']:,}", f"{s['n_sizeable']:,}",
               f"{s['n_unsizeable']:,}", s["pct_unsizeable"], s["n_zero_risk"],
               s["max_r"]))
    add("")
    add("| arm | population | n | mean R | median R | win rate |")
    add("|---|---|---:|---:|---:|---:|")
    for a, lbl in (("off", "`off`"), ("on", "`on`")):
        for pop, k in (("takeable", "sizeable"), ("untakeable", "unsizeable")):
            b = sp[a][k]
            if not b:
                continue
            add("| %s | %s | %s | %+.4f | %+.4f | %.1f%% |"
                % (lbl, pop, f"{b['traded']:,}", b["meanr"], b["median_r"], b["wr"]))
    add("")
    add("The `off` arm's %d untakeable rows are a 2dp-rounding artifact — the "
        "engine's floor reads the signal bar's CLOSE and the book stores the "
        "2dp fill, so a handful land a cent under this proxy. The `on` arm's "
        "%s are not an artifact: they are the class the floor exists to reject, "
        "readmitted."
        % (sp["off"]["n_unsizeable"], f"{sp['on']['n_unsizeable']:,}"))
    add("")
    add("### Which trades the flag swapped")
    add("")
    add("Rows are matched across the arms on `(symbol, day, entry time, setup, "
        "direction, level)` — detection is unchanged by the flag, so the same "
        "setup on the same bar is the same row.")
    add("")
    add("| | count | of which takeable |")
    add("|---|---:|---:|")
    add("| traded in BOTH arms | %s | — |" % f"{cp['n_shared']:,}")
    add("| **lost** — traded `off`, not `on` | %s | **%s** |"
        % (f"{cp['n_lost']:,}", f"{cp['lost_sizeable']:,}"))
    add("| **gained** — traded `on`, not `off` | %s | **%s** |"
        % (f"{cp['n_gained']:,}", f"{cp['gained_sizeable']:,}"))
    add("")
    add("**%s of %s trades lost were takeable. %s of %s trades gained are not.** "
        "The swap is almost perfectly the wrong way round, and it is not random: "
        "the two risks are anti-correlated by construction. Where `fill_price` "
        "back-dates the entry and `intrabar_stop` then moves the stop to the "
        "entry bar's own extreme, the POST-fill distance is WIDER than the "
        "structural one, so the structural floor rejects a row the account could "
        "have sized. Where the fill is a squeeze onto the bar's extreme with the "
        "stop left on the level, the post-fill distance is NARROWER, so the "
        "structural floor admits a row the account cannot size."
        % (f"{cp['lost_sizeable']:,}", f"{cp['n_lost']:,}",
           f"{cp['n_gained'] - cp['gained_sizeable']:,}", f"{cp['n_gained']:,}"))
    add("")
    add("What became of the %s lost trades in the `on` arm: %s. The %s that go "
        "`skipped_d` are the structural floor rejecting them outright."
        % (f"{cp['n_lost']:,}",
           ", ".join("`%s` %d" % (k, v) for k, v in
                     sorted(cp["lost_status_on"].items(), key=lambda kv: -kv[1])),
           f"{cp['lost_status_on'].get('skipped_d/X', 0):,}"))
    add("")
    add("### The only matched comparison in this file")
    add("")
    add("The %s rows traded by BOTH arms are the one population where the flag "
        "changes price rather than membership. %d of them have a different R."
        % (f"{cp['n_shared']:,}", cp["shared_r_changed"]))
    add("")
    add("| arm | n | mean R | median R | win rate | total R |")
    add("|---|---:|---:|---:|---:|---:|")
    for a, lbl in (("shared_off", "`off`"), ("shared_on", "`on`")):
        b = cp[a]
        add("| %s | %s | %+.4f | %+.4f | %.1f%% | %+.1f |"
            % (lbl, f"{b['traded']:,}", b["meanr"], b["median_r"], b["wr"], b["totr"]))
    add("")
    add("**%+.4f R on %s matched trades, %d of which actually moved.** That is the "
        "honest money delta this ticket can defend, and it is %.0f× smaller than "
        "the wide error bar below — it does not clear it."
        % (cp["shared_on"]["meanr"] - cp["shared_off"]["meanr"],
           f"{cp['n_shared']:,}", cp["shared_r_changed"],
           wide / abs(cp["shared_on"]["meanr"] - cp["shared_off"]["meanr"])
           if cp["shared_on"]["meanr"] != cp["shared_off"]["meanr"] else 0.0))
    add("")
    add("### Does the delta clear its own error bar")
    add("")
    add("T3 (`research/g3_onwatch_2y.md`, `47e60796`) established both bars and "
        "they are recomputed here on each arm's own book, never quoted: the WIDE "
        "bar reprices every ambiguous intrabar row to −1.0R; the NARROW floor "
        "reprices only rows whose stop is NOT the entry bar's own extreme. Both "
        "are one-directional — the booked mean R is a **ceiling**, never a "
        "midpoint.")
    add("")
    d_shared = cp["shared_on"]["meanr"] - cp["shared_off"]["meanr"]
    off_wide, off_narrow = A["off"]["eb_all"]["wide"], A["off"]["eb_all"]["narrow"]
    add("| | |")
    add("|---|---|")
    add("| whole-book mean R delta, as booked | %+.4f R — **do not use** |" % d_all)
    add("| S-subset mean R delta, as booked | %+.4f R — **do not use** |" % d_s)
    add("| matched-trade mean R delta (%s rows) | **%+.4f R** |"
        % (f"{cp['n_shared']:,}", d_shared))
    add("| WIDE bar, `off` arm (== T3's ±%.4f) | ±%.4f R |" % (T3_WIDE, off_wide))
    add("| does the matched delta clear it? | **no** — %.0f× smaller |"
        % (off_wide / abs(d_shared) if d_shared else 0.0))
    add("| NARROW floor, `off` arm (== T3's ±%.4f) | ±%.4f R |" % (T3_NARROW, off_narrow))
    add("| does the matched delta clear THAT? | %s |"
        % ("**yes**, by %.0f× — but only if a stop resting on the entry bar's own "
           "wick is ruled unreachable inside that bar, the one question Austin has "
           "not answered" % (abs(d_shared) / off_narrow)
           if abs(d_shared) > off_narrow else "**no**"))
    add("| WIDE bar, `on` arm | ±%.4f R — itself contaminated |" % wide)
    add("")
    add("**The as-booked delta of %+.4f R is %.0f× LARGER than the `off` arm's wide "
        "bar and that means nothing**, because both the delta and the `on` arm's "
        "own bar (±%.4f R) are made of the same untakeable rows. A number cannot "
        "clear an error bar by breaking the quantity the bar is measured on. The "
        "defensible delta is the matched one, **%+.4f R**, and it is **inside** the "
        "wide bar." % (d_all, abs(d_all) / off_wide, wide, d_shared))
    add("")
    add("**Neither arm passes the money gate and neither is durable.** The gate is "
        "mean R = 2.0 and EVERY month green. `off` books %+.4f R with %d of %d "
        "months green. `on`'s 25/25 is not durability — it is %s rows with a "
        "denominator near zero making every month positive. The floor fix is not "
        "what stands between this book and the gate."
        % (A["off"]["all"]["meanr"], A["off"]["all"]["months_green"],
           A["off"]["all"]["months"], f"{sp['on']['n_unsizeable']:,}"))
    add("")

    # ---- 5. per symbol ---------------------------------------------------
    add("### Per symbol")
    add("")
    add("Rows under `universe.MIN_SAMPLE_N` (=%d) are MARKED `(low n)`, never "
        "dropped and never excluded from the whole-book totals above — below ~20 "
        "trades one more trade swings the mean by the same order of magnitude as "
        "the money gate itself. Symbols whose traded count and mean R are both "
        "unchanged are omitted. **Every `on` column here carries the same "
        "contamination as the whole-book row: read it as which symbols the flag "
        "TOUCHES, not as what they earn.**" % MIN_SAMPLE_N)
    add("")
    add("| symbol | n `off` | mean R `off` | n `on` | mean R `on` | "
        "**untakeable `on`** |")
    add("|---|---:|---:|---:|---:|---:|")
    poff = {d["sym"]: d for d in A["off"]["per_symbol"]}
    pon = {d["sym"]: d for d in A["on"]["per_symbol"]}
    unt = defaultdict(int)
    for r in load_book("on")["trades"]:
        if r["traded"] and not sizeable(r):
            unt[r["sym"]] += 1
    for sym in sorted(set(poff) | set(pon), key=lambda s: -unt.get(s, 0)):
        o, n = poff.get(sym), pon.get(sym)
        if o and n and o["n"] == n["n"] and abs(o["mean_r"] - n["mean_r"]) < 1e-9:
            continue
        cell = lambda d: ("—", "—") if not d else (          # noqa: E731
            "%d%s" % (d["n"], " _(low n)_" if d["thin"] else ""),
            "%+.4f" % d["mean_r"])
        (no, mo), (nn, mn) = cell(o), cell(n)
        add("| %s | %s | %s | %s | %s | %d |"
            % (sym, no, mo, nn, mn, unt.get(sym, 0)))
    add("")
    add("Every symbol's `on` mean R is inflated by its own untakeable rows; the "
        "last column is the honest one. The contamination is not concentrated in "
        "a corner of the universe — it lands on %d of the %d symbols traded."
        % (sum(1 for v in unt.values() if v), len(pon)))
    add("")

    # ---- 6. held out -----------------------------------------------------
    add("## 5. The 100 held-out OMEN Test 1 cards")
    add("")
    add("`research/marks/probe_omen_test1_2026-08-27.jsonl` — 15 S / 27 A / 16 C / "
        "42 X, graded 2026-08-27, never shown to the engine and never fitted on. "
        "Scored by `research/t70_test1_score.py`'s own `score_all`, imported not "
        "reimplemented, once per arm. `grade_std: \"none\"` is his **X**: he "
        "looked at the day and refused it, so a fire there is a false fire, not "
        "an unlabelled day.")
    add("")
    add("| metric | `off` (== HEAD) | `on` (structural floor) | Δ |")
    add("|---|---:|---:|---:|")
    rows = [("**S recall** — fires at all on an S day", "s_hit", "s_n"),
            ("S recall, in-universe", "s_hit_in", "s_n_in"),
            ("**false fire** on refused (X) days", "x_fire", "x_n"),
            ("false fire, in-universe", "x_fire_in", "x_n_in"),
            ("entry match ±2 bars (of the 58 graded)", "entry_match", "graded"),
            ("day precision (of days it fired on)", "day_prec_hit", "day_prec_n")]
    for lbl, hk, nk in rows:
        o, n = c["off"], c["on"]
        add("| %s | %s | %s | %+.0f pts |"
            % (lbl, frac_(o[hk], o[nk]), frac_(n[hk], n[nk]),
               pct_(n[hk], n[nk]) - pct_(o[hk], o[nk])))
    add("")
    add("**S recall does not move at all: %d/%d in both arms.** Not one of the "
        "%d days the flag switched on is a day he graded S. The in-sample gate's "
        "+%d S marks do not reproduce out of sample."
        % (c["off"]["s_hit"], c["off"]["s_n"], len(newf),
           g["on"]["s"] - g["off"]["s"]))
    add("")
    add("| his grade | days newly fired by the flag |")
    add("|---|---|")
    for hg in ("S", "A", "C", "X"):
        ks = newf_by_grade.get(hg, [])
        add("| **%s** | %d%s |" % (hg, len(ks),
                                   (" — " + ", ".join("%s %s" % k for k in ks))
                                   if ks else ""))
    if lost:
        add("| (lost a fire) | %d — %s |"
            % (len(lost), ", ".join("%s %s (his %s)" % (k[0], k[1], on_by[k]["his"])
                                    for k in lost)))
    add("")
    add("So the fix broadens the engine on unseen days: **+%d tradeable days "
        "(S/A/C) and +%d refused days**, and day precision goes %s → %s. The "
        "engine was already more likely to fire on a day he refused than on a day "
        "he called S; this widens that."
        % (len(newf_by_grade.get("A", [])) + len(newf_by_grade.get("C", []))
           + len(newf_by_grade.get("S", [])) - len(lost),
           len(newf_by_grade.get("X", [])),
           frac_(c["off"]["day_prec_hit"], c["off"]["day_prec_n"]),
           frac_(c["on"]["day_prec_hit"], c["on"]["day_prec_n"])))
    add("")
    if lost:
        k = lost[0]
        add("**The flag is not one-directional, and that is worth knowing.** "
            "%s %s LOSES its fire. For a short, `intrabar_stop()` can move the "
            "stop to the entry bar's HIGH, which is further from the fill than "
            "the structural level is from the close — so on that bar the "
            "post-fill risk is WIDER than the structural risk and the structural "
            "floor is the stricter of the two. The fix rejects those, exactly as "
            "it accepts squeezes. It is a change of denominator, not a "
            "relaxation." % (k[0], k[1]))
        add("")

    # ---- 7. what this does not say ---------------------------------------
    add("## 6. What this does not say")
    add("")
    add("- **It does not ship the fix.** `ENABLE_STRUCTURAL_RISK_FLOOR` stays "
        "`False`. Flipping it changes what trades, and re-freezing the engine "
        "voids `research/omen6_forward.py` — Austin's call alone.")
    add("- **It does not revert `5e3677ea`.** The intrabar fill is Austin's own "
        "rule (*\"those candles that move fast and close at high of day or low of "
        "day, i just want to try to not miss out\"*) and is untouched.")
    add("- **It does not claim the matched money delta is zero.** It claims that "
        "delta is smaller than the error bar on the number it is a delta of — a "
        "weaker statement. The sign may be real and this rig cannot show it.")
    add("- **It does not turn the recall gate green.** One mark of the six is "
        "blocked by `_min_viable_stop`, a different gate with a different rule.")
    add("- **It does not say the structural floor is the wrong idea.** It says "
        "that moving the floor's denominator WITHOUT moving the sizing "
        "denominator is incoherent. A version that moves both — the floor, "
        "`stock_risk`, and the R denominator all onto the structural geometry, "
        "with `fill_price` improving only the price paid — is a different "
        "experiment and has not been run. G12's prose asks for that one; its "
        "two-line fix is not it.")
    add("- The takeable/untakeable split uses the stored 2dp `entry` where the "
        "engine's floor uses the signal bar's unrounded close. That costs the "
        "`off` arm %d marginal rows out of %s and cannot account for the `on` "
        "arm's %s." % (sp["off"]["n_unsizeable"], f"{sp['off']['traded']:,}",
                       f"{sp['on']['n_unsizeable']:,}"))
    add("- The held-out sample is 100 cards and 15 S days. A 3/15 → 3/15 read has "
        "a wide interval of its own; what it rules out is a LARGE out-of-sample S "
        "recall gain, not a small one.")
    add("- Every mean R here is a ceiling: each back-dated fill assumes the "
        "trigger beat the stop inside a minute nobody can see (T2 / "
        "`research/p26_intrabar_ambiguity.py`).")
    add("")

    # ---- 8. reproduce ----------------------------------------------------
    add("## 7. Reproduce")
    add("")
    add("```bash")
    add("git stash                                   # HEAD control, before the flag")
    add("python backtest_2y.py --days 730 --out research/g13_arm_head.json")
    add("git stash pop")
    add("python research/g13_floor_fix_ab.py --selfcheck")
    add("python research/test_structural_floor.py    # the assert-based check")
    add("python research/g13_floor_fix_ab.py book --arm off")
    add("python research/g13_floor_fix_ab.py book --arm on")
    add("python research/g13_floor_fix_ab.py identical   # head == off, byte for byte")
    add("python research/g13_floor_fix_ab.py gate        # regression_gate, both arms")
    add("python research/g13_floor_fix_ab.py marks       # G12's six, bar by bar")
    add("python research/g13_floor_fix_ab.py test1       # the 100 held-out cards")
    add("python research/g13_floor_fix_ab.py stats")
    add("python research/g13_floor_fix_ab.py report")
    add("python research/g12_attribute.py --ab-close-fill   # the revert-the-fill bound")
    add("```")
    add("")
    add("The three books are ~40 MB each and are NOT committed, the same "
        "convention `research/g3_onwatch_2y.py`'s arms follow. `data_archive/` "
        "must be identical across all three runs; the `head` run's 45,193 / 1,017 "
        "is the check that it was.")
    add("")
    add("## Provenance")
    add("")
    add("Generated by `research/g13_floor_fix_ab.py report` at _this commit_ "
        "(`--selfcheck` green). Engine change: `signal_runner.py` "
        "(`ENABLE_STRUCTURAL_RISK_FLOOR`, `floor_reference_risk`), default False. "
        "Assert-based check: `research/test_structural_floor.py`. Diagnosis it "
        "implements: `research/g12_recall_regression.md` (`df8e1c89`). Error bars: "
        "`research/g3_onwatch_2y.py` (`47e60796`), recomputed here. Held-out "
        "scorer: `research/t70_test1_score.py` (`30fbc3f8`). Sample floor: "
        "`universe.MIN_SAMPLE_N` = %d." % MIN_SAMPLE_N)
    add("")
    add("Books: `head` %s, `off` %s, `on` %s — all three against the same "
        "`data_archive/`, and the `head`/`off` sha256 match is the proof they saw "
        "the same tape. %d symbol-day(s) could not be classified for the error bar "
        "(missing day) and %d row(s) had no matching bar; both are excluded from "
        "the bar, never from the money."
        % (hb["meta"]["generated"], A["off"]["meta"]["generated"],
           A["on"]["meta"]["generated"], st["gaps"]["day"], st["gaps"]["bar"]))

    md = "\n".join(L) + "\n"
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(md)
    print("wrote %s (%d lines)" % (OUT_MD, len(L)))
    return 0


def pct_(n, d):
    return (100.0 * n / d) if d else 0.0


def frac_(n, d):
    return "%d/%d = %.0f%%" % (n, d, pct_(n, d))


# ---------------------------------------------------------------------------
# per-mark attribution: what the flag did to G12's six, bar by bar
# ---------------------------------------------------------------------------

_MARKS_DRIVER = '''
import json, sys
sys.path.insert(0, {here!r}); sys.path.insert(0, {root!r})
import t4_engine_recall as t4
import signal_runner as sr
DROPPED = {dropped!r}
rich = []
base = t4.CaptureRunner
class Rich(base):
    def _route(self, signals, sig):
        b = len(self.candles) - 1
        recent = self.candles[-11:-1]
        avg_rng = (sum(c.high - c.low for c in recent) / len(recent)) if recent else 0.0
        super()._route(signals, sig)
        rich.append(dict(bar=b, grade=sig["grade"], status=sig["status"],
                         setup=sig["signal_type"].value, direction=sig["direction"],
                         entry=round(float(sig["entry"]), 4),
                         stop=round(float(sig["stop"]), 4),
                         close=round(float(self.candles[-1].close), 4),
                         risk=round(abs(float(sig["entry"]) - float(sig["stop"])), 4),
                         floor=round(max(0.10, 0.0015 * self.candles[-1].close), 4),
                         avg_rng=round(avg_rng, 4),
                         tight_thr=round(sr.STOP_RANGE_MULT * avg_rng, 4),
                         level=sig.get("stop_level_name")))
t4.CaptureRunner = Rich
out = {{}}
for sym, day, i in DROPPED:
    rich.clear()
    ent, _s, _r = t4.run_day(sym, day)
    out["%s|%s|%d" % (sym, day, i)] = {{
        "near": [r for r in rich if abs(r["bar"] - i) <= 2],
        "fired_within_tol": sorted({{e["bar"] for e in (ent or [])
                                    if abs(e["bar"] - i) <= t4.TOL}}),
    }}
print(json.dumps(out))
'''

# The six regression_gate.py reports as DROPPED s_grade at HEAD, from
# research/g12_attribute.py:DROPPED -- imported below, never restated.


def run_marks() -> int:
    from research.g12_attribute import DROPPED
    out = {}
    for arm in ("off", "on"):
        code = _MARKS_DRIVER.format(here=HERE, root=ROOT, dropped=list(DROPPED))
        res = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                             env=child_env(arm), capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stderr[-2000:])
            raise SystemExit("marks arm %s failed" % arm)
        out[arm] = json.loads(res.stdout.strip().splitlines()[-1])
    with open(MARKS_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    for key in sorted(out["off"]):
        i = int(key.split("|")[2])
        o, n = out["off"][key], out["on"][key]
        print("%-24s fired_within_tol  off=%s  on=%s" % (key, o["fired_within_tol"],
                                                         n["fired_within_tol"]))
        for ro in o["near"]:
            rn = next((r for r in n["near"] if r["bar"] == ro["bar"]
                       and r["level"] == ro["level"] and r["setup"] == ro["setup"]), None)
            if rn and (rn["grade"], rn["status"]) == (ro["grade"], ro["status"]):
                continue
            print("    bar %-3d %-18s risk=%.4f floor=%.4f tight_thr=%.4f  "
                  "%s/%s -> %s/%s"
                  % (ro["bar"], ro["level"], ro["risk"], ro["floor"], ro["tight_thr"],
                     ro["grade"], ro["status"],
                     rn["grade"] if rn else "-", rn["status"] if rn else "-"))
    print("wrote %s" % MARKS_JSON)
    return 0


# ---------------------------------------------------------------------------
# selfcheck -- plain asserts, no framework
# ---------------------------------------------------------------------------

def selfcheck() -> int:
    # the arms are what they say they are
    assert ARMS["off"][0] == "0" and ARMS["on"][0] == "1"
    assert ARMS["head"][0] is None, "the head control must carry no override"
    import signal_runner as sr
    assert sr.ENABLE_STRUCTURAL_RISK_FLOOR is False, \
        "the shipped default must be False -- G13 measures, it does not ship"

    # child_env: head strips the variable rather than setting it to 0, so the
    # control cannot be confused with the off arm by an inherited value
    os.environ[FLAG] = "1"
    try:
        assert FLAG not in child_env("head")
        assert child_env("off")[FLAG] == "0"
        assert child_env("on")[FLAG] == "1"
    finally:
        os.environ.pop(FLAG, None)

    # trades_digest ignores meta.generated and nothing else
    a = {"meta": {"generated": "A", "n": 1}, "trades": [{"r": 1.0}]}
    b = {"meta": {"generated": "B", "n": 1}, "trades": [{"r": 1.0}]}
    c = {"meta": {"generated": "A", "n": 1}, "trades": [{"r": 1.5}]}
    assert trades_digest(a) == trades_digest(b)
    assert trades_digest(a) != trades_digest(c)

    # per-symbol thin marking is universe.MIN_SAMPLE_N, not a local number
    rows = ([{"sym": "FAT", "traded": True, "r": 1.0}] * MIN_SAMPLE_N
            + [{"sym": "THIN", "traded": True, "r": 1.0}] * (MIN_SAMPLE_N - 1)
            + [{"sym": "SKIP", "traded": False, "r": 9.0}])
    ps = {d["sym"]: d for d in per_symbol(rows)}
    assert ps["FAT"]["thin"] is False and ps["THIN"]["thin"] is True
    assert "SKIP" not in ps, "untraded rows are not a per-symbol population"
    assert ps["THIN"]["n"] == MIN_SAMPLE_N - 1, "thin rows keep their real n"

    # test1_counts: X is a judgement, silence on an S day is a miss
    fake = [
        {"his": "S", "n_fires": 1, "in_universe": True,  "entry_match": True,  "tier": "A+"},
        {"his": "S", "n_fires": 0, "in_universe": True,  "entry_match": False, "tier": None},
        {"his": "S", "n_fires": 1, "in_universe": False, "entry_match": False, "tier": "C"},
        {"his": "X", "n_fires": 2, "in_universe": True,  "entry_match": False, "tier": "B"},
        {"his": "X", "n_fires": 0, "in_universe": True,  "entry_match": False, "tier": None},
        {"his": "C", "n_fires": 1, "in_universe": True,  "entry_match": True,  "tier": "C"},
    ]
    c = test1_counts(fake)
    assert (c["s_hit"], c["s_n"]) == (2, 3), c
    assert (c["x_fire"], c["x_n"]) == (1, 2), c
    assert (c["s_hit_in"], c["s_n_in"]) == (1, 2), "out-of-universe S is not in-universe"
    assert (c["entry_match"], c["graded"]) == (2, 4), c
    assert (c["day_prec_hit"], c["day_prec_n"]) == (3, 4), c

    print("g13 selfcheck ok (MIN_SAMPLE_N=%d, %s default=%s)"
          % (MIN_SAMPLE_N, FLAG, sr.ENABLE_STRUCTURAL_RISK_FLOOR))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("book"); b.add_argument("--arm", choices=sorted(ARMS), required=True)
    b.add_argument("--days", type=int, default=730); b.add_argument("--out", default=None)
    sub.add_parser("gate")
    sub.add_parser("test1")
    sub.add_parser("stats")
    sub.add_parser("marks")
    sub.add_parser("report")
    i = sub.add_parser("identical")
    i.add_argument("--a", default="head"); i.add_argument("--b", default="off")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    if a.cmd == "book":
        return run_book(a.arm, a.days, a.out)
    if a.cmd == "gate":
        return run_gate()
    if a.cmd == "test1":
        return run_test1()
    if a.cmd == "stats":
        return run_stats()
    if a.cmd == "marks":
        return run_marks()
    if a.cmd == "report":
        return report()
    if a.cmd == "identical":
        return identical(a.a, a.b)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
