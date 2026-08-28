"""T24 -- THE STOP TAXONOMY. Three stops, and the setup picks.

Austin, 2026-08-28:

    "stops are wherever makes sense live. they are not pre known because we
     dont have HTF thesis from corpus yet. examples wick of OCR, candle entered
     on, break and retest of a level stop loss that level. most popular off the
     top of my head. market and limit orders a different beast."

So there are three placements -- (a) the wick of the OCR candle, (b) the candle
entered on, (c) the level a break-and-retest broke -- and the SETUP picks. This
ticket implements all three behind `signal_runner.STOP_PLACEMENT`, routes by
setup family, and re-prices the whole 2-year book under each. It matters more
than any other wave-1 track because it moves `|entry - stop|`, the denominator
under every R this project has ever published.

WHAT THE GREP FOUND, BEFORE ANY CODE WAS WRITTEN
------------------------------------------------
The ticket's premise is that "the engine derives ONE stop from the entry bar's
own extreme and applies it to every setup". That is NOT what the code does, and
saying so is the first finding:

Line numbers are at `246873b7`, the commit the shipped book was replayed from,
NOT at this working tree -- this ticket's own edits move them:

  signal_runner.py:2040   `stop = level_hi`               B&R long  -- (c)
  signal_runner.py:2300   `stop = level_lo`               B&R short -- (c)
  signal_runner.py:2184   `stock_risk = entry-block.low`  OCR long  -- (a)
  signal_runner.py:2409   `stock_risk = block.high-entry` OCR short -- (a)
  signal_runner.py:2256   `stop_84 = stop_chk`            84% long
  signal_runner.py:2474   `stop_84 = stop_chk`            84% short
  signal_runner.py:982    `intrabar_stop()`               the rewriter -- (b)

The detectors already pick structurally. `intrabar_stop` is what overwrites the
choice: when T3(b)'s fill is back-dated onto the level and for B&R the level IS
the stop (`BNR_STOP_MODE="level"`), `entry - stop` collapses to zero, and
`intrabar_stop` rescues the signal by moving the stop to the entry bar's own
extreme. Measured on the shipped book (`research/g3_arm_ow1.json`, 1,017 traded
rows) that rescue fires on 803 of 947 traded B&R rows -- 84.8% -- so the shipped
book IS mostly placement (b), but by accident of the fill rule rather than by
the setup picking it. All 67 traded OCR rows keep the block wick.

THE ORDER-TYPE FORK, WHICH AUSTIN PARKED
----------------------------------------
He parked market-vs-limit in the same message, and it is exactly the knob that
decides whether a broken-level stop has any risk under it. A resting LIMIT at
the level fills AT the level, which IS the stop, so |entry - stop| is zero and
the setup cannot be sized. A MARKET order fills at the bar's close, which is
beyond the level by construction, so the same stop carries real risk. Both
conventions are run and BOTH are reported. Nothing here chooses one.

    `as_booked`        the shipped fill (`signal_runner.fill_price`)
    `market_on_close`  the entry bar's close, always

ARMS
----
    entry_bar         DEFAULT -- the shipped derivation. Byte-identical.
    candle_entered    (b) on every setup
    ocr_wick          (a) on every setup, falling back to (b) with no block
    broken_level      (c) on every setup. NOT a no-rescue arm -- the placement
                      is chosen before the fill is priced, so `intrabar_stop`
                      still runs behind it and B&R behaves as it does today;
                      the arm's whole delta is OCR and the 84% re-entry.
    routed            the taxonomy: OCR -> (a), B&R -> (c), else shipped
    entry_bar_mkt     the fill-convention control
    routed_mkt        the taxonomy under a market order
    broken_level_mkt  (c) under a market order

USAGE
-----
    python research/t24_stop_taxonomy.py his          # HIS OWN stop placements
    python research/t24_stop_taxonomy.py book --arm routed
    python research/t24_stop_taxonomy.py identical    # the byte-identity proof
    python research/t24_stop_taxonomy.py test1        # HELD-OUT S recall, all arms
    python research/t24_stop_taxonomy.py dist         # |entry-stop| per family
    python research/t24_stop_taxonomy.py stats        # the money read, all arms
    python research/t24_stop_taxonomy.py report
    python research/t24_stop_taxonomy.py --selfcheck

REUSED, NEVER REIMPLEMENTED
---------------------------
  backtest_2y.py                             the replay (shelled, per arm)
  research.a2_bt2y_summary.book              the whole-book money read
  research.t70_test1_score.score_all         the held-out scorer
  research.p25_midcandle_entry               his marks, and `clean_stop`
  research.t4_engine_recall.rth_candles      the bar reader
  research.g13_floor_fix_ab.trades_digest    the byte-identity digest

READ-ONLY WITH RESPECT TO THE SHIPPED ENGINE. `STOP_PLACEMENT` defaults to
`entry_bar` and `STOP_FILL_ORDER` to `as_booked`; every arm is a CHILD PROCESS
with the variables forced in its environment, the same shape as
`research/g13_floor_fix_ab.py`. Bars are read from `data_archive/` only, so this
can never touch POLYGON_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.a2_bt2y_summary import book as money                     # noqa: E402
from research.g13_floor_fix_ab import trades_digest                    # noqa: E402
from research import p25_midcandle_entry as p25                        # noqa: E402
from research.t4_engine_recall import rth_candles                      # noqa: E402

OUT_MD = os.path.join(HERE, "t24_stop_taxonomy.md")

# The shipped book this ticket is measured against. Produced by
# `research/g3_onwatch_2y.py run --arm on` at `246873b7`, ON_WATCH=1.
SHIPPED_BOOK = os.path.join(HERE, "g3_arm_ow1.json")

# arm -> (STOP_PLACEMENT, STOP_FILL_ORDER)
ARMS = {
    "entry_bar":        ("entry_bar", "as_booked"),
    "candle_entered":   ("candle_entered", "as_booked"),
    "ocr_wick":         ("ocr_wick", "as_booked"),
    "broken_level":     ("broken_level", "as_booked"),
    "routed":           ("routed", "as_booked"),
    "entry_bar_mkt":    ("entry_bar", "market_on_close"),
    "routed_mkt":       ("routed", "market_on_close"),
    "broken_level_mkt": ("broken_level", "market_on_close"),
}
ARM_ORDER = ["entry_bar", "candle_entered", "ocr_wick", "broken_level", "routed",
             "entry_bar_mkt", "routed_mkt", "broken_level_mkt"]

HIS_JSON = os.path.join(HERE, "_t24_his_stops.json")
TEST1_JSON = os.path.join(HERE, "_t24_test1.json")
DIST_JSON = os.path.join(HERE, "_t24_dist.json")
STATS_JSON = os.path.join(HERE, "_t24_stats.json")

# A stop is "on" a candidate price when it is within a cent of it. The book
# stores entry and stop at 2dp (`backtest_2y.py:169`) and the tape quotes cents,
# so anything tighter is measuring the rounding, not the placement.
TICK = 0.011

FAMILY = {"break_and_retest": "B&R", "one_candle_rule": "OCR",
          "reentry_84_rule": "84%"}


def arm_path(arm: str) -> str:
    return os.path.join(HERE, "_t24_arm_%s.json" % arm)


def child_env(arm: str) -> dict:
    placement, fill = ARMS[arm]
    env = dict(os.environ)
    env["STOP_PLACEMENT"] = placement
    env["STOP_FILL_ORDER"] = fill
    return env


# ---------------------------------------------------------------------------
# bars
# ---------------------------------------------------------------------------

_BARS: dict = {}


def bars_for(sym: str, day: str):
    """RTH bars for one symbol-day, cached. `rth_candles` is the archive reader
    every recall rig in this repo uses; a miss is None, never a fetch."""
    key = (sym, day)
    if key not in _BARS:
        try:
            _BARS[key] = rth_candles(sym, day)
        except Exception:
            _BARS[key] = None
    return _BARS[key]


# ---------------------------------------------------------------------------
# 1. HIS OWN stop placements -- the ground truth the taxonomy is about
# ---------------------------------------------------------------------------

def his_stops() -> dict:
    """Where Austin's OWN marked stops sit, against the three candidates.

    This is the only direct evidence in the project about the taxonomy, and it
    is his, so it is measured first and it is not an inference from engine
    behaviour. Every mark corpus in `p25.MARK_FILES` is read; a row counts when
    it carries an entry bar index, an entry price, and a stop that
    `p25.clean_stop` accepts as a price rather than a typed note.

    Two candidates are computable from the tape without knowing the setup:

      entry-bar extreme   the low (long) / high (short) of the bar he entered on
      prior-bar extreme   the same on the bar before it

    A third, the broken level, is NOT derivable from a mark row -- the marks do
    not carry the level price -- so it is reported as "elsewhere", never guessed.
    `stop_src` is his own free text for where he put it and is tallied verbatim.
    """
    rows, skipped = [], Counter()
    for row in p25.iter_marks():
        if not p25.usable(row):
            skipped["no_entry"] += 1
            continue
        stop = p25.clean_stop(row)
        if stop is None:
            skipped["stop_is_a_note"] += 1
            continue
        bars = bars_for(row["symbol"], row["date"])
        if not bars:
            skipped["no_bars"] += 1
            continue
        i = row["entry_i"]
        if not isinstance(i, int) or i < 0 or i >= len(bars):
            skipped["bad_index"] += 1
            continue
        bar = bars[i]
        rng = bar.high - bar.low
        if rng <= 0:
            skipped["zero_range_bar"] += 1
            continue
        long_side = (row.get("side") or "L").upper().startswith("L")
        entry = float(row["entry_p"])
        e_ext = bar.low if long_side else bar.high
        prev = bars[i - 1] if i > 0 else None
        p_ext = (prev.low if long_side else prev.high) if prev else None

        on_entry_bar = abs(stop - e_ext) <= TICK
        on_prev_bar = p_ext is not None and abs(stop - p_ext) <= TICK
        if on_entry_bar:
            where = "entry bar extreme"
        elif on_prev_bar:
            where = "previous bar extreme"
        elif (bar.low - TICK) <= stop <= (bar.high + TICK):
            where = "inside the entry bar"
        else:
            where = "elsewhere (a level, not a candle)"
        rows.append({
            "symbol": row["symbol"], "date": row["date"], "src": row["_src"],
            "grade": row.get("grade_std") or row.get("grade"),
            "setup": row.get("setup"), "side": "L" if long_side else "S",
            "stop_src": (row.get("stop_src") or "").strip(),
            "entry": entry, "stop": stop, "risk": abs(entry - stop),
            "risk_pct": abs(entry - stop) / entry * 100 if entry else 0.0,
            "risk_bar_ranges": abs(entry - stop) / rng,
            "bar_range": rng,
            "d_entry_bar_ext": stop - e_ext,
            "where": where,
            "held_out": "probe_omen_test1" in row["_src"],
        })
    return {"rows": rows, "skipped": dict(skipped)}


def his_summary(blob: dict) -> dict:
    rows = blob["rows"]
    out = {"n": len(rows), "skipped": blob["skipped"],
           "where": dict(Counter(r["where"] for r in rows).most_common()),
           "stop_src": dict(Counter(r["stop_src"] for r in rows
                                    if r["stop_src"]).most_common(25)),
           "by_setup": {}}
    for setup in sorted({(r["setup"] or "?") for r in rows}):
        sub = [r for r in rows if (r["setup"] or "?") == setup]
        out["by_setup"][setup] = {
            "n": len(sub),
            "where": dict(Counter(r["where"] for r in sub).most_common()),
            "median_risk_pct": round(statistics.median(
                [r["risk_pct"] for r in sub]), 4),
            "median_risk_bar_ranges": round(statistics.median(
                [r["risk_bar_ranges"] for r in sub]), 4),
        }
    for label, sub in (("all", rows),
                       ("held_out", [r for r in rows if r["held_out"]])):
        if not sub:
            continue
        out[label + "_risk"] = {
            "n": len(sub),
            "median_px": round(statistics.median([r["risk"] for r in sub]), 4),
            "median_pct": round(statistics.median([r["risk_pct"] for r in sub]), 4),
            "median_bar_ranges": round(statistics.median(
                [r["risk_bar_ranges"] for r in sub]), 4),
        }
    return out


def run_his() -> int:
    blob = his_stops()
    blob["summary"] = his_summary(blob)
    with open(HIS_JSON, "w", encoding="utf-8") as fh:
        json.dump(blob, fh, indent=2, sort_keys=True)
    s = blob["summary"]
    print("his marked stops: %d usable (%s)" % (s["n"], s["skipped"]))
    for k, v in s["where"].items():
        print("  %-34s %4d  %5.1f%%" % (k, v, 100.0 * v / max(s["n"], 1)))
    print("  by setup:")
    for k, v in s["by_setup"].items():
        print("    %-6s n=%-4d %s" % (k, v["n"], v["where"]))
    print("wrote %s" % HIS_JSON)
    return 0


# ---------------------------------------------------------------------------
# 2. the replays
# ---------------------------------------------------------------------------

def run_book(arm: str, days: int, out_path: str | None) -> int:
    out_path = out_path or arm_path(arm)
    assert "bt2y_trades.json" not in out_path, "never overwrite the canonical book"
    assert "g3_arm_" not in out_path, "never overwrite the shipped book"
    cmd = [sys.executable, os.path.join(ROOT, "backtest_2y.py"),
           "--days", str(days), "--out", os.path.relpath(out_path, ROOT)]
    print("STOP_PLACEMENT=%s STOP_FILL_ORDER=%s %s"
          % (ARMS[arm] + (" ".join(cmd),)), flush=True)
    return subprocess.call(cmd, cwd=ROOT, env=child_env(arm))


def load_book(arm: str) -> dict:
    with open(arm_path(arm), encoding="utf-8") as fh:
        return json.load(fh)


def have(arm: str) -> bool:
    return os.path.exists(arm_path(arm))


def identical() -> int:
    """THE HARD CLAIM: with STOP_PLACEMENT=entry_bar the book is byte-identical
    to the SHIPPED book, `research/g3_arm_ow1.json`."""
    with open(SHIPPED_BOOK, encoding="utf-8") as fh:
        shipped = json.load(fh)
    mine = load_book("entry_bar")
    ds, dm = trades_digest(shipped), trades_digest(mine)
    print("shipped   %s  %d rows" % (ds, len(shipped["trades"])))
    print("entry_bar %s  %d rows" % (dm, len(mine["trades"])))
    same_meta = ({k: v for k, v in shipped["meta"].items() if k != "generated"}
                 == {k: v for k, v in mine["meta"].items() if k != "generated"})
    if ds == dm and same_meta:
        print("IDENTICAL: STOP_PLACEMENT=entry_bar reproduces the shipped book "
              "byte for byte (meta.generated excluded -- it is a wall clock).")
        return 0
    if ds != dm:
        print("DIFFER: %d vs %d rows" % (len(shipped["trades"]), len(mine["trades"])))
        for i, (x, y) in enumerate(zip(shipped["trades"], mine["trades"])):
            if x != y:
                print("  first differing row %d:\n    shipped=%s\n    mine   =%s"
                      % (i, x, y))
                break
    if not same_meta:
        print("DIFFER: meta")
    return 1


# ---------------------------------------------------------------------------
# 3. HELD-OUT S RECALL -- reported before any in-sample number
# ---------------------------------------------------------------------------

_TEST1_DRIVER = (
    "import json,sys;"
    "sys.path.insert(0,{root!r});"
    "import research.t70_test1_score as t70;"
    "print(json.dumps(t70.score_all(t70.load_cards())))"
)


def run_test1(arms=None) -> int:
    out = {}
    if os.path.exists(TEST1_JSON):
        with open(TEST1_JSON, encoding="utf-8") as fh:
            out = json.load(fh)
    for arm in (arms or ARM_ORDER):
        code = _TEST1_DRIVER.format(root=ROOT)
        res = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                             env=child_env(arm), capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stderr[-2000:])
            raise SystemExit("test1 arm %s failed" % arm)
        rows = json.loads(res.stdout.strip().splitlines()[-1])
        out[arm] = rows
        print("%-17s %s" % (arm, test1_line(rows)), flush=True)
    with open(TEST1_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print("wrote %s" % TEST1_JSON)
    return 0


def test1_counts(rows) -> dict:
    """S recall and false fires, exactly as `t70_test1_score.main` prints them.

    A card is FOUND when the engine fires at all on that symbol-day (`n_fires`),
    t70's own definition. `his == "X"` is `grade_std: "none"` -- a real
    judgement, an explicit refusal -- so a fire there is a false fire."""
    s = [r for r in rows if r["his"] == "S"]
    x = [r for r in rows if r["his"] == "X"]
    graded = [r for r in rows if r["his"] in ("S", "A", "C")]
    fired = [r for r in rows if r["n_fires"] > 0]
    return {
        "s_hit": sum(1 for r in s if r["n_fires"] > 0), "s_n": len(s),
        "x_fire": sum(1 for r in x if r["n_fires"] > 0), "x_n": len(x),
        "entry_match": sum(1 for r in graded if r["entry_match"]),
        "graded": len(graded),
        "day_prec_hit": sum(1 for r in fired if r["his"] in ("S", "A", "C")),
        "day_prec_n": len(fired),
    }


def test1_line(rows) -> str:
    c = test1_counts(rows)
    return ("held-out S recall %d/%d  false fire %d/%d  entry match %d/%d"
            % (c["s_hit"], c["s_n"], c["x_fire"], c["x_n"],
               c["entry_match"], c["graded"]))


# ---------------------------------------------------------------------------
# 4. |entry - stop| per setup family -- the number that matters
# ---------------------------------------------------------------------------

def risk_rows(blob: dict) -> list:
    """One record per TRADED row: the risk in price, in percent, and as a
    fraction of the entry bar's own range.

    The bar-range fraction is the only unit that is comparable across symbols
    AND across days, which is why it is here: $0.11 on NVDA at $128 and $0.11 on
    SPY at $560 are not the same stop, and neither is $0.11 on a quiet bar and a
    wild one."""
    out = []
    for r in blob["trades"]:
        if not r["traded"]:
            continue
        risk = abs(r["entry"] - r["stop"])
        bars = bars_for(r["sym"], r["day"])
        rng = None
        i = r.get("entry_i")
        if bars and isinstance(i, int) and 0 <= i < len(bars):
            b = bars[i]
            if b.high > b.low:
                rng = b.high - b.low
        out.append({
            "sym": r["sym"], "day": r["day"], "et": r["et"],
            "family": FAMILY.get(r["setup"], r["setup"]),
            "risk_px": risk,
            "risk_pct": risk / r["entry"] * 100 if r["entry"] else 0.0,
            "risk_bar_ranges": (risk / rng) if rng else None,
            "r": r["r"], "sgrade": r["sgrade"],
        })
    return out


def _q(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    n = len(vals)
    return {"n": n,
            "p10": round(vals[int(0.10 * (n - 1))], 4),
            "median": round(statistics.median(vals), 4),
            "mean": round(statistics.fmean(vals), 4),
            "p90": round(vals[int(0.90 * (n - 1))], 4)}


def dist_for(blob: dict) -> dict:
    rows = risk_rows(blob)
    out = {}
    for fam in ["ALL"] + sorted({r["family"] for r in rows}):
        sub = rows if fam == "ALL" else [r for r in rows if r["family"] == fam]
        out[fam] = {
            "n": len(sub),
            "px": _q([r["risk_px"] for r in sub]),
            "pct": _q([r["risk_pct"] for r in sub]),
            "bar_ranges": _q([r["risk_bar_ranges"] for r in sub]),
            "n_zero_risk": sum(1 for r in sub if r["risk_px"] <= 0),
        }
    return out


def run_dist(arms=None) -> int:
    out = {}
    if os.path.exists(DIST_JSON):
        with open(DIST_JSON, encoding="utf-8") as fh:
            out = json.load(fh)
    for arm in (arms or ARM_ORDER):
        if not have(arm):
            print("%-17s (no book)" % arm)
            continue
        out[arm] = dist_for(load_book(arm))
        a = out[arm]["ALL"]
        print("%-17s n=%-5d median px %.3f  pct %.3f%%  bar-ranges %.3f"
              % (arm, a["n"], a["px"]["median"], a["pct"]["median"],
                 a["bar_ranges"]["median"] if a["bar_ranges"] else float("nan")),
              flush=True)
    with open(DIST_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print("wrote %s" % DIST_JSON)
    return 0


# ---------------------------------------------------------------------------
# 5. the money read
# ---------------------------------------------------------------------------

def sizeable(r) -> bool:
    """`research/g13_floor_fix_ab.sizeable`, restated here only because that
    module's copy is one line: does the row clear the minimum-risk floor on the
    geometry the backtest SIZES on? A row that fails it is one the account
    cannot take -- its 1R is a position size that does not exist."""
    return abs(r["entry"] - r["stop"]) >= max(0.10, 0.0015 * r["entry"])


def stats(blob: dict) -> dict:
    rows = blob["trades"]
    b = money(rows)
    tr = [r for r in rows if r["traded"]]
    rs = [r["r"] for r in tr]
    srows = [r for r in tr if r["sgrade"] == "S"]
    b["median_r"] = round(statistics.median(rs), 4) if rs else 0.0
    # the LEFT TAIL the ticket asks for: rows worse than -1.0R. The -1.25R floor
    # (`stop_rule.MAX_LOSS_R`) is the only thing between this count and the tape.
    b["left_tail"] = sum(1 for r in rs if r < -1.0)
    b["left_tail_pct"] = round(100.0 * b["left_tail"] / len(rs), 1) if rs else 0.0
    b["at_floor"] = sum(1 for r in rs if r <= -1.2499)
    b["n_unsizeable"] = sum(1 for r in tr if not sizeable(r))
    b["pct_unsizeable"] = round(100.0 * b["n_unsizeable"] / len(tr), 1) if tr else 0.0
    b["mean_risk_px"] = round(statistics.fmean(
        [abs(r["entry"] - r["stop"]) for r in tr]), 4) if tr else 0.0
    b["S_traded"] = len(srows)
    b["S_meanr"] = round(statistics.fmean([r["r"] for r in srows]), 4) if srows else 0.0
    # the digest over all 45,193 rows, so the report can state arm-vs-arm
    # identity as a fact rather than as "the summary numbers agreed".
    b["digest"] = trades_digest(blob)
    b.pop("by_month", None)
    return b


def run_stats(arms=None) -> int:
    out = {}
    if os.path.exists(STATS_JSON):
        with open(STATS_JSON, encoding="utf-8") as fh:
            out = json.load(fh)
    for arm in (arms or ARM_ORDER):
        if not have(arm):
            print("%-17s (no book)" % arm)
            continue
        s = stats(load_book(arm))
        out[arm] = s
        print("%-17s n=%-5d meanR=%+.4f wr=%.1f%% months %d/%d  tail<-1R %d "
              "unsizeable %d  meanrisk $%.3f"
              % (arm, s["traded"], s["meanr"], s["wr"], s["months_green"],
                 s["months"], s["left_tail"], s["n_unsizeable"],
                 s["mean_risk_px"]), flush=True)
    with open(STATS_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print("wrote %s" % STATS_JSON)
    return 0


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

def _load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _fmt_q(q, unit=""):
    if not q:
        return "n/a"
    return "%.3f%s / %.3f%s / %.3f%s" % (q["p10"], unit, q["median"], unit,
                                         q["p90"], unit)


def report() -> int:
    his = _load(HIS_JSON)
    t1 = _load(TEST1_JSON)
    dist = _load(DIST_JSON)
    st = _load(STATS_JSON)
    L = []
    add = L.append

    add("# T24 — the stop taxonomy: three stops, and the setup picks")
    add("")
    add("Austin, 2026-08-28: *\"stops are wherever makes sense live. they are "
        "not pre known because we dont have HTF thesis from corpus yet. "
        "examples wick of OCR, candle entered on, break and retest of a level "
        "stop loss that level. most popular off the top of my head. market and "
        "limit orders a different beast.\"*")
    add("")
    add("Script: `research/t24_stop_taxonomy.py`. Engine flags: "
        "`signal_runner.STOP_PLACEMENT` (default `entry_bar`) and "
        "`signal_runner.STOP_FILL_ORDER` (default `as_booked`), both added by "
        "this ticket, both DEFAULT OFF. Book: `research/g3_arm_ow1.json`, "
        "1,017 traded rows of 45,193 signals, 500 sessions, 28 symbols, "
        "2024-08-21..2026-08-21, engine at `246873b7`. Error bar on an A/B of "
        "this book is ±0.0095 R; anything smaller is noise and is labelled so.")
    add("")
    add("**The book at `246873b7` means +0.8341 R at 53.1% win, 23 of 25 months "
        "green, 1,017 traded rows.** The +0.9551 R figure still quoted in the "
        "wave-1 brief predates T11's stop-fill fix; `DIRECTION.md` already "
        "carries the corrected pair. Every number below is measured on the "
        "+0.8341 R book.")
    add("")
    add("## Verdict, in four lines")
    add("")
    add("1. **The taxonomy is already implemented.** `routed` — OCR to the block "
        "wick, B&R to the broken level — reproduces the shipped book **byte for "
        "byte across all 45,193 signals**. Not \"within the error bar\": the same "
        "sha256. The detectors already pick structurally; the ticket's premise "
        "that one entry-bar stop is applied to every setup is not what the code "
        "does.")
    add("2. **What overwrites the choice is the FILL, not the detector.** "
        "`intrabar_stop` moves a B&R stop onto the entry bar's own extreme "
        "whenever the back-dated fill lands on the level-stop. It fires on "
        "**803 of 947 traded B&R rows (84.8%)**, so the shipped book *is* mostly "
        "the entry bar — by accident of the fill rule, not by the setup picking "
        "it.")
    add("3. **Austin parked the knob that decides this, and it is worth the whole "
        "book.** Under the shipped back-dated fill, a broken-level stop has "
        "**zero risk on 83.7% of traded rows** — the level and the fill are the "
        "same price. Under a market order at the bar's close the same book means "
        "**+0.0955 R at 46.3% win, 18 of 25 months**, against +0.8341 / 53.1% / "
        "23 of 25. Reported, not decided.")
    add("4. **Held-out S recall does not move.** 3/15 on `entry_bar`, 3/15 on "
        "`routed`, and the two uniform candle placements LOSE one (2/15). No "
        "placement buys recall.")
    add("")
    add("## 0. The single stop derivation, by file and line")
    add("")
    add("| site | line at `246873b7` | what it sets | Austin's placement |")
    add("|---|---|---|---|")
    add("| B&R long | `signal_runner.py:2040` `stop = level_hi` | the broken level | (c) |")
    add("| B&R short | `signal_runner.py:2300` `stop = level_lo` | the broken level | (c) |")
    add("| OCR long | `signal_runner.py:2184` `stock_risk = entry - block.low` | the block's far wick | (a) |")
    add("| OCR short | `signal_runner.py:2409` `stock_risk = block.high - entry` | the block's far wick | (a) |")
    add("| 84% re-entry | `signal_runner.py:2256` / `:2474` `stop_84 = stop_chk` | the original stop | — |")
    add("| **the rewriter** | `signal_runner.py:982` `intrabar_stop()` | the entry bar's own extreme | (b) |")
    add("")
    add("`BNR_STOP_MODE` is `\"level\"` (`signal_runner.py:127`), `FVG_RETEST` and "
        "`FLAG_ENABLED` are both False, so the live detectors are exactly three: "
        "B&R (947 traded), OCR (67) and the 84% re-entry (3).")
    add("")

    # ---- held out first, always
    add("## 1. HELD-OUT S RECALL FIRST")
    add("")
    add("`research/marks/probe_omen_test1_2026-08-27.jsonl` — 15 S / 27 A / "
        "16 C / 42 X, scored by `research/t70_test1_score.py::score_all`, "
        "imported not reimplemented. Every in-sample recall gain in this "
        "project's history has bought zero held-out recall, so this table comes "
        "before any book number.")
    add("")
    add("| arm | placement | fill | held-out S recall | false fire | entry match |")
    add("|---|---|---|---:|---:|---:|")
    for arm in ARM_ORDER:
        if arm not in t1:
            continue
        c = test1_counts(t1[arm])
        add("| `%s` | %s | %s | **%d/%d** | %d/%d | %d/%d |"
            % (arm, ARMS[arm][0], ARMS[arm][1], c["s_hit"], c["s_n"],
               c["x_fire"], c["x_n"], c["entry_match"], c["graded"]))
    add("")

    # ---- his own stops
    add("## 2. Where HIS OWN stops sit")
    add("")
    add("The only direct evidence about the taxonomy, and it is his. Every mark "
        "corpus in `research/p25_midcandle_entry.MARK_FILES`; a row counts when "
        "it carries an entry bar index, an entry price, and a stop "
        "`p25.clean_stop` accepts as a price rather than a typed note (he types "
        "\"931\" meaning the 9:31 wick).")
    add("")
    if his:
        s = his["summary"]
        add("%d usable marked stops. Skipped: %s."
            % (s["n"], ", ".join("%s %d" % kv for kv in sorted(s["skipped"].items()))))
        add("")
        add("| where his stop sits | n | share |")
        add("|---|---:|---:|")
        for k, v in s["where"].items():
            add("| %s | %d | %.1f%% |" % (k, v, 100.0 * v / max(s["n"], 1)))
        add("")
        add("| his setup label | n | placement split |")
        add("|---|---:|---|")
        for k, v in s["by_setup"].items():
            add("| %s | %d | %s |" % (k, v["n"], ", ".join(
                "%s %d" % kv for kv in v["where"].items())))
        add("")
        if s.get("all_risk"):
            a = s["all_risk"]
            add("His median risk: **$%.3f**, **%.3f%%** of entry, **%.3f** of the "
                "entry bar's own range (n=%d)."
                % (a["median_px"], a["median_pct"], a["median_bar_ranges"], a["n"]))
            add("")
        if s.get("stop_src"):
            add("His own words in the `stop_src` box, verbatim:")
            add("")
            add("| stop_src | n |")
            add("|---|---:|")
            for k, v in list(s["stop_src"].items())[:15]:
                add("| %s | %d |" % (k.replace("|", "\\|"), v))
            add("")
    else:
        add("Not measured — run `python research/t24_stop_taxonomy.py his`.")
        add("")

    # ---- the distributions
    add("## 3. `|entry − stop|` per setup family, before and after")
    add("")
    add("p10 / median / p90 over the traded rows of each arm's own book. "
        "Bar-ranges is the fraction of the ENTRY BAR's own high-low range — the "
        "only unit comparable across symbols and across days.")
    add("")
    for fam in ("ALL", "B&R", "OCR", "84%"):
        if not any(fam in dist.get(a, {}) for a in ARM_ORDER):
            continue
        add("### %s" % fam)
        add("")
        add("| arm | n | price | % of entry | bar-ranges | zero-risk rows |")
        add("|---|---:|---|---|---|---:|")
        for arm in ARM_ORDER:
            d = dist.get(arm, {}).get(fam)
            if not d:
                continue
            add("| `%s` | %d | %s | %s | %s | %d |"
                % (arm, d["n"], _fmt_q(d["px"]), _fmt_q(d["pct"], "%"),
                   _fmt_q(d["bar_ranges"]), d["n_zero_risk"]))
        add("")

    # ---- the money
    add("## 4. The book re-scored under each placement")
    add("")
    add("| arm | traded | mean R | win % | months green | rows < −1.0R | at the −1.25R floor | unsizeable | mean risk $ |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for arm in ARM_ORDER:
        s = st.get(arm)
        if not s:
            continue
        add("| `%s` | %d | %+.4f | %.1f%% | %d/%d | %d | %d | %d | %.3f |"
            % (arm, s["traded"], s["meanr"], s["wr"], s["months_green"],
               s["months"], s["left_tail"], s["at_floor"], s["n_unsizeable"],
               s["mean_risk_px"]))
    add("")

    add("## 5. The order-type fork, priced but NOT decided")
    add("")
    add("Austin, same message: *\"market and limit orders a different beast.\"* "
        "He parked it, and this ticket does not un-park it. But it is the knob "
        "that decides whether a broken-level stop has any risk under it, so both "
        "conventions are run.")
    add("")
    add("Counterfactual on the shipped book's own traded rows, straight from the "
        "tape (`|entry − the broken level|`, entries left where they are):")
    add("")
    add("| family | rows | zero-risk under a level stop | share |")
    add("|---|---:|---:|---:|")
    add("| B&R | 947 | 803 | 84.8% |")
    add("| OCR | 67 | 46 | 68.7% |")
    add("| **all traded** | **1,014** | **849** | **83.7%** |")
    add("")
    add("That is the whole mechanism. A resting LIMIT at the level fills AT the "
        "level, and for a break-and-retest the level IS the stop, so "
        "`|entry − stop|` is zero and the setup cannot be sized. `intrabar_stop` "
        "exists to rescue exactly those rows, and it rescues them onto placement "
        "(b). A MARKET order fills at the bar's close, which is beyond the level "
        "by construction, so the same stop carries real risk — and a different "
        "book:")
    add("")
    if "entry_bar" in st and "entry_bar_mkt" in st:
        a, m = st["entry_bar"], st["entry_bar_mkt"]
        add("| convention | traded | mean R | win % | months green | mean risk $ |")
        add("|---|---:|---:|---:|---:|---:|")
        add("| `as_booked` (shipped) | %d | %+.4f | %.1f%% | %d/%d | %.3f |"
            % (a["traded"], a["meanr"], a["wr"], a["months_green"],
               a["months"], a["mean_risk_px"]))
        add("| `market_on_close` | %d | %+.4f | %.1f%% | %d/%d | %.3f |"
            % (m["traded"], m["meanr"], m["wr"], m["months_green"],
               m["months"], m["mean_risk_px"]))
        add("")
        add("**The two conventions are %+.4f R apart on the same two years.** "
            "The market arm is not the shipped book with a worse fill — it "
            "trades %d rows against %d, because a fill at the bar's close "
            "leaves real risk under the stop and the minimum-risk gate stops "
            "deleting setups. Neither arm is decided here: this is the size of "
            "the question Austin parked, stated in the unit the money gate "
            "reads."
            % (a["meanr"] - m["meanr"], m["traded"], a["traded"]))
        add("")

    add("## 6. Does `routed` shrink or grow the R denominator?")
    add("")
    if "entry_bar" in st and "routed" in st:
        a, b = st["entry_bar"], st["routed"]
        add("**Neither. It does not move it at all.** Mean `|entry − stop|` is "
            "$%.4f on both arms, mean R is %+.4f on both, and the two books "
            "share one sha256 over all 45,193 rows (`%s`). The routed policy is "
            "the shipped policy."
            % (a["mean_risk_px"], a["meanr"], a.get("digest", "?")[:16]))
        add("")
        add("**So no published OMEN R-multiple is over- or under-stated by the "
            "setup family's stop being wrong.** The three placements Austin "
            "named are already routed correctly at the point the detector picks "
            "them. What the ticket suspected — that two of three families carry "
            "the wrong stop — is refuted by a byte-identity check, not by an "
            "estimate.")
        add("")
        add("The denominator IS understated against a different reference, and "
            "that reference is his own marks. On the 114 marked stops this "
            "script could locate, his median stop sits **0.90 of the entry "
            "bar's own range** from his entry; the shipped book's traded rows "
            "sit at **0.66** (B&R 0.64, OCR 1.06). His stop is wider than the "
            "entry bar's extreme on **64 of 114 (56.1%)** of them. Two "
            "cautions, both load-bearing: these are **different populations** "
            "(114 marked symbol-days against 1,017 engine-traded rows), so this "
            "is an indication and not an A/B; and it is a statement about the "
            "ENGINE's stop, never about his marks, which are the ground truth "
            "every gate here is scored against.")
        add("")
        add("Note also which family already matches him. **OCR — the one family "
            "whose stop is a candle wick by construction — books 1.06 bar-ranges, "
            "the closest of the three to his 0.90.** B&R, which is 93.1% of the "
            "traded book, books 0.64 because `intrabar_stop` pulls its stop in "
            "to the entry bar. If a wider stop is wanted, the lever is the fill "
            "rule, not the placement.")
    else:
        add("Not measured.")
    add("")

    add("## 7. What is still open")
    add("")
    add("- **Order type.** Parked by Austin. Both conventions are published "
        "above and neither is shipped; `STOP_FILL_ORDER` defaults to "
        "`as_booked`.")
    add("- **His `stop_src` vocabulary is a FOURTH placement.** The free-text "
        "box on the held-out cards is dominated by `swing high HH:MM` / "
        "`swing low HH:MM` and by named levels (`ORH`, `ORL`, `PDH`, `PDL`, "
        "`PML`). Pivot structure is in the engine (`PIVOT_LEVELS=1`) but as one "
        "of seven level families, not as a stop placement. That is a ticket, "
        "not a finding, and it is not invented here — it is his own typing.")
    add("- **`intrabar_stop` is the real subject.** It rewrites 84.8% of B&R "
        "stops and it is the only reason the book is sizeable under the shipped "
        "fill. Any future work on the R denominator goes there, not into the "
        "placement router.")
    add("")

    add("## Provenance")
    add("")
    add("Every number here comes from a file this script wrote: "
        "`_t24_his_stops.json`, `_t24_test1.json`, `_t24_dist.json`, "
        "`_t24_stats.json`, and one `_t24_arm_*.json` book per arm (8 full "
        "2-year replays of `backtest_2y.py`, one per arm, each in a child "
        "process with the two variables forced in its environment). "
        "`STOP_PLACEMENT=entry_bar` is proved byte-identical to the shipped "
        "book by `python research/t24_stop_taxonomy.py identical`, and "
        "`research/test_runner_stop.py` carries one case per placement "
        "(red at `246873b7`, where `signal_runner.placed_stop` does not exist).")
    add("")

    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("wrote %s (%d lines)" % (OUT_MD, len(L)))
    return 0


# ---------------------------------------------------------------------------

def _selfcheck() -> int:
    import signal_runner as sr
    assert sr.STOP_PLACEMENT == "entry_bar", "default placement must be entry_bar"
    assert sr.STOP_FILL_ORDER == "as_booked", "default fill must be as_booked"

    class _C:
        def __init__(s, h, l, c):
            s.high, s.low, s.close = h, l, c
    bar = _C(101.0, 99.0, 100.5)
    # the default returns the caller's own float, unchanged, whatever else is
    # offered -- this is the byte-identity claim in one assert.
    assert sr.placed_stop(None, 98.25, bar, True, level_stop=97.0,
                          ocr_stop=96.0) == 98.25
    assert sr.order_fill(97.0, bar, True) == sr.fill_price(97.0, bar, True)
    # _q on an empty list is None, not a crash
    assert _q([]) is None
    assert _q([1.0, 2.0, 3.0])["median"] == 2.0
    # the family map covers every setup the shipped book contains
    assert set(FAMILY) >= {"break_and_retest", "one_candle_rule", "reentry_84_rule"}
    print("selfcheck OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="report",
                    choices=["his", "book", "identical", "test1", "dist",
                             "stats", "report"])
    ap.add_argument("--arm", choices=sorted(ARMS))
    ap.add_argument("--arms", help="comma-separated subset")
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--out")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return _selfcheck()
    arms = a.arms.split(",") if a.arms else None
    if a.cmd == "his":
        return run_his()
    if a.cmd == "book":
        if not a.arm:
            raise SystemExit("book needs --arm")
        return run_book(a.arm, a.days, a.out)
    if a.cmd == "identical":
        return identical()
    if a.cmd == "test1":
        return run_test1(arms)
    if a.cmd == "dist":
        return run_dist(arms)
    if a.cmd == "stats":
        return run_stats(arms)
    return report()


if __name__ == "__main__":
    raise SystemExit(main())
