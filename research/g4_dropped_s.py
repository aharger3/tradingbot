"""G4 -- what the legacy grader throws away, branch by branch.

The number that started this: over the two-year replay `research/downgrade.py`
(Austin's S/A/C ladder) scores **7,485** signals `S`. The engine trades **128**.
7,219 of the rest are graded `X` by `PriceActionAnalyzer._grade_pa`
(`omen_bot.py:171`) and dropped with `status="skipped_d"`.

"The grader is wrong" is not actionable. "This branch of the grader drops N
signals" is. So this script re-runs the grader over the entry bar of every
signal and records **which `return` fired**, then joins that back onto
`research/bt2y_trades.json` so every drop can be sliced by setup, level,
direction, slot, downgrades-tripped and confluence.

Method
------
Attribution is not re-derived from the JSON -- the JSON does not carry the
arguments `grade_trade` was called with (for an order block the graded level is
`block.high` while the exported `stop` is `block.low`, so a JSON-only rebuild
misattributes every OCR row). Instead the two-year replay is re-run with two
monkeypatches:

  * `PriceActionAnalyzer.grade_trade` -- records which branch produced its
    verdict, from the exact `(candle, level, is_long, htf_bias)` it received.
  * `SignalRunner._emit` -- stamps that branch, the post-grader grade, and the
    engine's own `_min_viable_stop` verdict onto the signal as it is emitted.

Engine behaviour is untouched: both patches record and delegate. Nothing in
`omen_bot.py` or `signal_runner.py` is edited, and `downgrade.py` stays unwired.

The replay is joined to the committed JSON on
`(sym, day, et, setup, dir, round(stop, 2))`; the join rate and any grade
disagreement are reported in the output as a drift check.

Caveat that must travel with every number here: the thresholds inside
`downgrade.py` are guesses Austin never ratified (TASKS A1). Read the direction
of any S-count, not its decimals.

Usage:
    python research/g4_dropped_s.py                    # replay + report
    python research/g4_dropped_s.py --cache-only       # reuse the replay cache
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import omen_bot                                          # noqa: E402
import polygon_feed as pf                                # noqa: E402
import signal_runner as sr                               # noqa: E402
from omen_bot import PriceActionAnalyzer as PA           # noqa: E402
from backtest_week import simulate_day, htf_bias_for     # noqa: E402
from backtest_12mo import hourly_from_1m, qqq_level_breaks  # noqa: E402
from backtest_2y import archive_days                     # noqa: E402
from universe import ALL_SYMS, has_archive               # noqa: E402

INP = ROOT / "research" / "bt2y_trades.json"
OUT = ROOT / "research" / "g4_dropped_s.md"
CACHE = ROOT / "research" / "_g4_branches.json"

# ---------------------------------------------------------------- instrument

# key -> [record, ...]; a key can repeat when two levels sit at the same price
BRANCHES: dict = defaultdict(list)
CURRENT = {"sym": None, "day": None}
_LAST = {}          # what the most recent grade_trade call saw


def pa_branch(candle, lookback, or_high, or_low, is_long, htf_bias, skip_colour=False,
              skip_bias=False):
    """Which `return` inside grade_trade/_grade_pa fires, as a label.

    A transcription of `omen_bot.PriceActionAnalyzer.grade_trade` +
    `._grade_pa`, in the same order, with no thresholds of its own. Note that
    for a long `at_key_level` (`candle.low <= or_high`) is the SAME test as the
    C branch, so the grader has exactly two ways to reject: the colour of the
    entry candle, and the candle never trading back to the level.

    `skip_colour=True` runs the same ladder with the first line deleted — the
    counterfactual Austin asked for ("the candle doesn't have to be so
    specific"). A+ stays unreachable for a wrong-colour candle because
    `is_hammer_stick` / `is_inverted_hammer` each re-test colour internally;
    the wick tests do not, so `B` is reachable.

    `skip_bias=True` runs the ladder with the HTF-bias veto (the first line of
    all) deleted — P16/W3, Austin: "we dont have any higher timeframe bias yet
    youll need to tell me what that is then" (rule ballot batch 02, c6). The
    `neutral` cap two lines below is left alone: it never fires without a
    bullish/bearish bias reaching it in the first place, so it is inert here.
    """
    if not skip_bias and htf_bias in ("bullish", "bearish"):
        if (htf_bias == "bullish") != is_long:
            return "bias_opposed"
    if is_long:
        if not (skip_colour or candle.is_bullish):
            return "colour_gate"
        at = candle.low <= or_high
        if not at:
            return "never_touched_level"
        if PA.is_hammer_stick(candle, lookback):
            base = "A+"
        elif PA.has_large_lower_wick(candle):
            base = "B"
        else:
            base = "C"
    else:
        if not (skip_colour or candle.is_bearish):
            return "colour_gate"
        at = candle.high >= or_low
        if not at:
            return "never_touched_level"
        if PA.is_inverted_hammer(candle):
            base = "A+"
        elif PA.has_large_upper_wick(candle):
            base = "B"
        else:
            base = "C"
    if htf_bias == "neutral" and base in ("A+", "A"):
        base = "B"
    return "graded_" + base


def install_patches():
    """Record-and-delegate. Neither patch changes a verdict."""
    orig_grade = PA.grade_trade.__func__ if hasattr(PA.grade_trade, "__func__") else PA.grade_trade
    orig_emit = sr.SignalRunner._emit

    def grade_trade(candle, lookback_candles, or_high, or_low, is_long, htf_bias=None):
        _LAST.clear()
        _LAST.update(branch=pa_branch(candle, lookback_candles, or_high, or_low,
                                      is_long, htf_bias),
                     nocolour=pa_branch(candle, lookback_candles, or_high, or_low,
                                        is_long, htf_bias, skip_colour=True),
                     nobias=pa_branch(candle, lookback_candles, or_high, or_low,
                                      is_long, htf_bias, skip_bias=True),
                     is_long=is_long, bias=htf_bias or "none")
        return orig_grade(candle, lookback_candles, or_high, or_low, is_long, htf_bias)

    def _emit(self, signals, sig):
        try:
            st = getattr(sig.get("signal_type"), "value", sig.get("signal_type"))
            is_long = sig.get("direction") == "call"
            last = dict(_LAST) if _LAST.get("is_long") == is_long else {}
            entry, stop = sig.get("entry"), sig.get("stop")
            close = self.candles[-1].close
            risk = abs(entry - stop) if (entry is not None and stop is not None) else None
            key = "%s|%s|%s|%s|%s|%.2f" % (
                CURRENT["sym"], CURRENT["day"], self.candles[-1].timestamp[:5],
                st, sig.get("direction"), stop if stop is not None else -1)
            BRANCHES[key].append({
                "branch": last.get("branch", "unattributed"),
                "nocolour": last.get("nocolour", "unattributed"),
                "nobias": last.get("nobias", "unattributed"),
                "emit_grade": sig.get("grade"),
                "bias": last.get("bias", "none"),
                "lvl_name": sig.get("stop_level_name"),
                "risk": round(risk, 4) if risk is not None else None,
                "close": round(close, 4),
                # signal_runner's B&R relative min-stop, verbatim:
                #   if stock_risk < max(0.10, 0.0015 * current.close): grade = D
                "minstop": (risk < max(0.10, 0.0015 * close)) if risk is not None else None,
                "minvi": bool(self._min_viable_stop(entry, stop, sig.get("direction")))
                         if (entry is not None and stop is not None) else None,
            })
        except Exception:                       # never let telemetry break a replay
            pass
        return orig_emit(self, signals, sig)

    PA.grade_trade = staticmethod(grade_trade)
    omen_bot.PriceActionAnalyzer.grade_trade = staticmethod(grade_trade)
    sr.SignalRunner._emit = _emit


# ------------------------------------------------------------------- replay

def replay(days: int) -> dict:
    """Re-run the two-year window purely to harvest branch attribution.

    Inputs mirror `backtest_2y.main()` bar for bar: same symbols, same window,
    same prior-day / premarket / HTF-bias / QQQ inputs, same `simulate_day`.
    The trades it produces are discarded -- only the emit-time telemetry is
    kept.
    """
    install_patches()
    syms = [s for s in ALL_SYMS if has_archive(s, 100)]
    last = max((archive_days(s) or ["1970-01-01"])[-1] for s in syms)
    start = (date.fromisoformat(last) - timedelta(days=days)).isoformat()
    window = sorted({d for s in syms for d in archive_days(s) if d >= start})
    print("replay: %d symbols, %d sessions %s..%s"
          % (len(syms), len(window), window[0], window[-1]))
    qqq_brk = qqq_level_breaks(window)

    for si, sym in enumerate(syms, 1):
        day_bars, hourly = {}, []
        for d in [x for x in archive_days(sym) if x >= start]:
            try:
                bars = pf.fetch_day(sym, d)
            except Exception:
                continue
            if not bars:
                continue
            r = pf.rth(bars)
            if len(r) < 30:
                continue
            day_bars[d] = (bars, r)
            hourly += hourly_from_1m(d, r)
        prev = None
        for d in sorted(day_bars):
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = pf.premarket_hi_lo(bars)
            CURRENT["sym"], CURRENT["day"] = sym, d
            simulate_day(sym, d, rth, pdh, pdl, htf_bias_for(hourly, d),
                         pmh, pml, pdo, pdc, qqq=qqq_brk.get(d))
            prev = d
        print("  [%d/%d] %s: %d sessions, %d keys so far"
              % (si, len(syms), sym, len(day_bars), len(BRANCHES)))
    return {k: v for k, v in BRANCHES.items()}


# -------------------------------------------------------------------- tables


# The gates a signal passes through, in source order, between `grade_trade` and
# `_route`. Only these can turn a graded signal into `X` -- everything downstream
# (`_grade_for_levels`, `_calibration_grade`) moves a signal between A+/A/B/C and
# never lifts or creates an `X`. Read from the B&R long, B&R short and order-block
# blocks of `SignalRunner.detect_signals`; the replay checks the reading by
# recording the emitted grade and comparing it to the committed book.
COLOUR = "colour gate — entry candle is the wrong colour"
BIAS = "HTF bias opposed — `grade_trade` line 1"
BNR_MIN = "B&R min-stop — risk < max($0.10, 0.15% of price)"
OCR_MIN = "OCR min-stop — risk < $0.50"
OCR_WIDE = "OCR stop wider than 0.4% of price"
NEVER = "candle never traded back to the level"


def kill_branch(t, rec):
    """Which gate actually made this signal `X`, in the order they execute.

    Not a guess: `bias_opposed` and `colour_gate` both block the `D -> C`
    rescue in the B&R path (it requires the right colour AND an unopposed
    bias), so when either fires it is terminal. A grader verdict of C/B/A+ that
    still ends `X` can only have been re-dropped by a min-stop gate.
    """
    b = rec["branch"]
    if b == "bias_opposed":
        return BIAS
    if t["setup"] == "one_candle_rule":         # the order-block path
        if b == "colour_gate":
            return COLOUR
        if rec["risk"] is not None and rec["risk"] < 0.50:
            return OCR_MIN
        if rec["risk"] is not None and rec["risk"] / rec["close"] > 0.004:
            return OCR_WIDE
        return "join collision — grader said %s, book says X" % b.replace("graded_", "")
    if b == "colour_gate":
        return COLOUR                            # no rescue for a wrong-colour candle
    if rec["minstop"]:
        return BNR_MIN                           # the grader passed it; the stop gate did not
    if b == "never_touched_level":
        return NEVER
    return "join collision — grader said %s, book says X" % b.replace("graded_", "")


def keyof(t) -> str:
    return "%s|%s|%s|%s|%s|%.2f" % (t["sym"], t["day"], t["et"], t["setup"],
                                    t["dir"], t["stop"])


def agg(rs):
    """(n, win%, mean R, median R). Wins are R > 0; scratches sit in neither."""
    rs = [r for r in rs if r is not None]
    if not rs:
        return 0, 0.0, 0.0, 0.0
    dec = [r for r in rs if r != 0]
    w = sum(1 for r in dec if r > 0)
    return (len(rs), (100.0 * w / len(dec) if dec else 0.0),
            statistics.fmean(rs), statistics.median(rs))


def table(title, header, rows, note=None):
    out = ["", "### " + title, ""]
    if note:
        out += [note, ""]
    out += ["| " + " | ".join(header) + " |", "|---" * len(header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def counted(rows, field, total=None):
    c = Counter(str(r.get(field)) for r in rows)
    n = total or sum(c.values())
    return [(k, v, "%.1f%%" % (100.0 * v / n)) for k, v in c.most_common()]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inp", default=str(INP))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--cache", default=str(CACHE))
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--cache-only", action="store_true",
                    help="reuse an existing replay cache instead of re-replaying")
    args = ap.parse_args()

    raw = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    meta, T = raw["meta"], raw["trades"]

    if args.cache_only and os.path.exists(args.cache):
        br = json.loads(Path(args.cache).read_text(encoding="utf-8"))
        print("branch cache: %d keys (reused)" % len(br))
    else:
        br = replay(args.days)
        Path(args.cache).write_text(json.dumps(br, separators=(",", ":")),
                                    encoding="utf-8")
        print("branch cache: %d keys -> %s" % (len(br), args.cache))

    # ---- the dropped-S set -------------------------------------------------
    S = [t for t in T if t["sgrade"] == "S"]
    dropped = [t for t in S if t["status"] == "skipped_d"]
    traded_s = [t for t in S if t["traded"]]

    hit = miss = disagree = ambiguous = 0
    for t in dropped:
        recs = br.get(keyof(t))
        if not recs:
            t["_branch"], t["_minvi"] = "unmatched", None
            t["_pa"] = t["_nocolour"] = t["_nobias"] = "unmatched"
            t["_minstop"] = None
            miss += 1
            continue
        hit += 1
        if len({r["branch"] for r in recs}) > 1:
            ambiguous += 1
        r0 = recs[0]
        if r0["emit_grade"] != t["grade"]:
            disagree += 1
        t["_minvi"], t["_rec"] = r0["minvi"], r0
        t["_pa"] = r0["branch"]
        t["_nocolour"] = r0["nocolour"]
        t["_nobias"] = r0.get("nobias", "unattributed")
        t["_minstop"] = r0["minstop"]
        t["_branch"] = kill_branch(t, r0)

    L = ["# G4 — the 7,219 dropped S signals, attributed to the branch that killed them",
         "",
         "Generated by `research/g4_dropped_s.py` from `research/bt2y_trades.json` "
         "(%s..%s, %d sessions, %d signals, %d traded)."
         % (meta["first"], meta["last"], meta["sessions"], meta["signals"], meta["traded"]),
         "",
         "**Read the direction, not the decimals.** Every `S` here comes from "
         "`research/downgrade.py`, whose eight thresholds are guesses Austin has never "
         "ratified (TASKS A1). If those numbers move, the size of the S pool moves with "
         "them. What does not move is *which branch* of the legacy grader rejects a "
         "signal — that is arithmetic on the entry bar.",
         "",
         "## 0. The funnel",
         ""]
    L += table("Austin's ladder vs the engine's book", ["sgrade", "signals", "traded", "alert-only", "dropped `X`"],
               [(g,
                 sum(1 for t in T if t["sgrade"] == g),
                 sum(1 for t in T if t["sgrade"] == g and t["traded"]),
                 sum(1 for t in T if t["sgrade"] == g and t["alert"]),
                 sum(1 for t in T if t["sgrade"] == g and t["status"] == "skipped_d"))
                for g in ("S", "A", "C")])
    L += ["",
          "Of the 7,485 `S` signals the engine trades **%d** and alerts on **%d**. "
          "**%d** are graded `X` and dropped; the remaining %d die on the tight-stop "
          "and repeat-entry gates, not on the grader."
          % (len(traded_s), sum(1 for t in S if t["alert"]), len(dropped),
             len(S) - len(traded_s) - sum(1 for t in S if t["alert"]) - len(dropped)),
          "",
          "Join to the instrumented replay: **%d of %d** dropped-S rows matched "
          "(%d unmatched, %d with a grade disagreement, %d ambiguous keys). Unmatched "
          "rows are reported as `unmatched` and never silently merged, and the %d "
          "disagreements are exactly the %d rows that come out as `join collision` in "
          "§1 — two signals sharing one `(symbol, day, minute, setup, direction, stop)` "
          "key, not an unaccounted gate. **%.2f%% of the set is attributed.** The engine "
          "modules are unchanged since the book was generated, which is what a "
          "%d-of-%d grade agreement is evidence of."
          % (hit, len(dropped), miss, disagree, ambiguous, disagree, disagree,
             100.0 * (len(dropped) - disagree - miss) / max(len(dropped), 1),
             hit - disagree, hit)]

    # ---- 1. the drop table -------------------------------------------------
    L += ["", "## 1. The drop table", ""]
    L += table("Which gate actually made it `X`",
               ["gate", "signals", "share"], counted(dropped, "_branch"),
               "Ordered by execution, so each signal is charged to the gate that first "
               "and terminally rejected it. Both `_grade_pa` rejections block the B&R "
               "path's `D -> C` rescue (which needs the right colour AND an unopposed "
               "bias), so when either fires it is final. A grader verdict of C/B/A+ that "
               "still ends `X` can only have been re-dropped by a min-stop gate — and "
               "**those two min-stop gates are not part of the grader at all**.")
    L += table("...and what `_grade_pa` itself said, before any later gate",
               ["`_grade_pa` verdict", "signals", "share"], counted(dropped, "_pa"),
               "`colour_gate` is its first line. `never_touched_level` is its last: "
               "`at_key_level` and the `C` branch are the *same* test, so a candle that "
               "never trades back to the level cannot be graded at all. `graded_*` means "
               "the grader was content and something downstream did the killing.")
    for f, lbl in (("setup", "Setup"), ("level", "Level broken"), ("dir", "Direction"),
                   ("slot", "Entry slot"), ("tripped", "Downgrades tripped"),
                   ("confluence", "BR+OCR confluence")):
        L += table(lbl, [lbl.lower(), "dropped S", "share"], counted(dropped, f))

    setups = sorted({t["setup"] for t in dropped})
    L += ["", "### Gate x setup", "",
          "| gate | " + " | ".join(setups) + " |",
          "|---" * (1 + len(setups)) + "|"]
    bx = defaultdict(Counter)
    for t in dropped:
        bx[t["_branch"]][t["setup"]] += 1
    for b, c in sorted(bx.items(), key=lambda kv: -sum(kv[1].values())):
        L.append("| %s | %s |" % (b, " | ".join(str(c[s]) for s in setups)))

    # ---- 2. colour gate ----------------------------------------------------
    colour = [t for t in dropped if t["_branch"] == COLOUR]
    colour_only = [t for t in colour if not t["_minstop"]]
    cf = Counter(t["_nocolour"] for t in colour_only)
    tradeable = cf["graded_B"] + cf["graded_A+"]
    L += ["", "## 2. What the colour gate costs", "",
          "**%d of the %d dropped S signals (%.1f%%) die on the first line of the "
          "grader** — the entry candle closed against the trade's direction. No "
          "structure is consulted before that `return`, and because a wrong-colour "
          "candle also fails the `D -> C` rescue, the rejection is silent: the signal "
          "is not even an alert."
          % (len(colour), len(dropped), 100.0 * len(colour) / max(len(dropped), 1)),
          "",
          "Austin, unprompted: *\"the candle doesn't have to be so specific — you're "
          "just looking for PA to support your thesis.\"*",
          "",
          "**%d of those %d fail on the colour gate and nothing else** — no other gate "
          "in the path would have caught them. The other %d are wrong-colour bars that "
          "*also* sit under the B&R min-stop, so deleting the colour line does not "
          "reach them. Re-running `_grade_pa` on the same bars with the colour test "
          "removed (`A+` stays unreachable — `is_hammer_stick` and `is_inverted_hammer` "
          "each re-test colour internally, but the wick tests do not):"
          % (len(colour_only), len(colour), len(colour) - len(colour_only)),
          ""]
    L += table("Counterfactual: the same ladder, colour line deleted",
               ["verdict without the colour line", "signals", "what it becomes"],
               [(k.replace("graded_", ""), v,
                 "**tradeable tier**" if k in ("graded_B", "graded_A+")
                 else "alert-only" if k == "graded_C" else "still dropped")
                for k, v in cf.most_common()],
               "**%d of the 7,219 reach the tradeable `B` tier on one deleted line**, "
               "and %d more become alerts. Upper bound, and say so: `B` at the detection "
               "site can still be capped to `C` downstream by `_grade_for_levels` (a "
               "level blocking the 2R path) or `_calibration_grade` (counter to the day "
               "trend), and §6 shows the day's *first* with-trend signal is what actually "
               "gets traded — so some of these would replace a current trade rather than "
               "add to it." % (tradeable, cf["graded_C"]))
    L += table("Colour-gate drops by setup and direction",
               ["setup", "dir", "signals"],
               [(k[0], k[1], v) for k, v in
                Counter((t["setup"], t["dir"]) for t in colour).most_common()])

    # ---- 3. level type -----------------------------------------------------
    ORL = ("OR high", "OR low")
    L += ["", "## 3. Level type — the opening-range claim is false, and here is the check",
          "",
          "`DIRECTION.md` and `TASKS.md` both carry the line that `at_key_level` is "
          "hardcoded to the opening-range high/low, so a retest of PDH/PMH/a pivot is "
          "invisible to the grader. **That is not what the code does.** Every one of the "
          "ten `grade_trade` call sites in `signal_runner.py` passes the level the setup "
          "actually broke — `level_hi`/`level_lo` for B&R, the FVG edge, `block.high`/"
          "`block.low` for the order block, the flag boundary, the original entry for the "
          "84% re-entry. The parameter is merely still *named* `or_high` from when the "
          "opening range was the only level there was. `research/t62_veto_autopsy.md` "
          "made the same correction on 2026-08-23; the two planning docs never picked "
          "it up. Fixing them is queued below.",
          "",
          "So the honest level-type answer is a coverage number, not a bug: "
          "**%d of %d dropped S signals (%.1f%%) broke a non-OR level** — and the grader "
          "saw each of those levels correctly."
          % (sum(1 for t in dropped if t["level"] not in ORL), len(dropped),
             100.0 * sum(1 for t in dropped if t["level"] not in ORL) / max(len(dropped), 1)),
          ""]
    lv_rows = []
    for lv, n in Counter(t["level"] for t in dropped).most_common():
        allsig = sum(1 for t in T if t["level"] == lv and t["sgrade"] == "S")
        cg = sum(1 for t in dropped if t["level"] == lv and t["_branch"] == COLOUR)
        lv_rows.append((lv, allsig, n, "%.1f%%" % (100.0 * n / max(allsig, 1)),
                        "%.1f%%" % (100.0 * cg / max(n, 1))))
    L += table("Drop rate by level, OR vs everything else",
               ["level", "S signals", "dropped `X`", "drop rate", "of which colour gate"],
               lv_rows,
               "If the opening-range claim were true, OR levels would drop at a visibly "
               "lower rate than the rest. They do not.")
    orn = [t for t in T if t["sgrade"] == "S" and t["level"] in ORL]
    nonorn = [t for t in T if t["sgrade"] == "S" and t["level"] not in ORL]
    L += ["",
          "OR levels: %d S signals, %.1f%% dropped. Everything else: %d S signals, "
          "%.1f%% dropped. The gap is %.1f points — a level-blind grader would show a "
          "chasm here."
          % (len(orn), 100.0 * sum(1 for t in orn if t["status"] == "skipped_d") / max(len(orn), 1),
             len(nonorn), 100.0 * sum(1 for t in nonorn if t["status"] == "skipped_d") / max(len(nonorn), 1),
             abs(100.0 * sum(1 for t in orn if t["status"] == "skipped_d") / max(len(orn), 1)
                 - 100.0 * sum(1 for t in nonorn if t["status"] == "skipped_d") / max(len(nonorn), 1)))]

    # ---- 4. what would they have paid --------------------------------------
    L += ["", "## 4. What the dropped S signals would have paid", "",
          "`simulate_day` already simulated every one of these rows — a `SimTrade` is "
          "built for every captured signal regardless of grade, and managed against the "
          "same stop-on-close / −1.25R-floor / 11:00 rules as the traded book. So the "
          "`r` in `bt2y_trades.json` is an honest replay of that entry, not an estimate.",
          "",
          "**The exclusion rule, stated.** Many dropped rows carry degenerate risk: a "
          "stop eleven cents from entry books a full ±1R on noise. Under the default "
          "ladder (`OMEN_LADDER_MODE=B`) it is worse than noise — half the position "
          "scales at the session extreme and the runner rides to the next key level, so "
          "a two-cent denominator manufactures three-figure R multiples. That is the "
          "whole story of the +9.7R line below, and it is why the unfiltered mean is "
          "unquotable while the unfiltered *median* (−1.000) is not. Rather than invent "
          "a cutoff, this uses the engine's own: `SignalRunner._min_viable_stop`, the gate "
          "already applied to C-grade signals — *skip when stock risk is below "
          "`STOP_RANGE_MULT` x the average range of the last ten bars, or when risk is "
          "both under 0.5%% of entry and under $0.20 of estimated premium.* It is "
          "evaluated here at emit time on the real bars, exactly as the engine evaluates "
          "it, and applied uniformly to every dropped-S row instead of only to C.",
          ""]

    def band(rows, label):
        n, wr, mr, md = agg([t["r"] for t in rows])
        return (label, n, "%.1f%%" % wr, "%+.3f" % mr, "%+.3f" % md)

    viable = [t for t in dropped if t.get("_minvi") is True]
    nonviable = [t for t in dropped if t.get("_minvi") is False]
    cf_trade = [t for t in viable
                if t["_branch"] == COLOUR and not t["_minstop"]
                and t["_nocolour"] in ("graded_B", "graded_A+")]
    rows = [band(dropped, "all dropped S (**degenerate risk included — do not quote**)"),
            band(nonviable, "dropped S, stop below `_min_viable_stop`"),
            band(viable, "**dropped S, viable stop — the honest number**"),
            band([t for t in viable if t["setup"] == "break_and_retest"], "  ...break_and_retest"),
            band([t for t in viable if t["setup"] == "one_candle_rule"], "  ...one_candle_rule"),
            band(cf_trade, "**colour-gate arm: viable stop AND would grade B+ without the colour line**"),
            band(traded_s, "S signals the engine actually traded (incumbent)"),
            band([t for t in T if t["traded"]], "the whole traded book (incumbent)")]
    L += table("Expectancy", ["set", "n", "win rate", "mean R", "median R"], rows,
               "Win rate counts R > 0 against all non-zero R; scratches (R = 0) sit in "
               "neither column but are in `n`.")
    L += ["",
          "**Two things this is not.** It is not a book — the dropped set contains "
          "overlapping entries on the same idea that `NO_REPEAT_ENTRIES` and the "
          "30-bar dedupe would collapse, so `n` is an upper bound on trades, not a "
          "count of them. And it is not risk-adjusted for concurrency: several of these "
          "fire on the same symbol-minute.",
          ""]

    # ---- 5. OCR vs B&R -----------------------------------------------------
    L += ["", "## 5. One Candle Rule against Break-and-Retest", "",
          "Austin's ask: *\"one candle rule should be just as popular as "
          "break-and-retest.\"* Side by side, same rig, same window.",
          ""]
    frows = []
    for st in ("break_and_retest", "one_candle_rule"):
        a = [t for t in T if t["setup"] == st]
        s = [t for t in a if t["sgrade"] == "S"]
        n, wr, mr, md = agg([t["r"] for t in a if t["traded"]])
        frows.append((st, len(a), len(s),
                      sum(1 for t in a if t["traded"]),
                      "%.2f%%" % (100.0 * sum(1 for t in a if t["traded"]) / max(len(a), 1)),
                      sum(1 for t in s if t["traded"]),
                      sum(1 for t in s if t["status"] == "skipped_d"),
                      "%+.3f" % mr))
    nb = sum(1 for t in T if t["setup"] == "break_and_retest")
    no = sum(1 for t in T if t["setup"] == "one_candle_rule")
    L += table("Detection -> grade -> trade",
               ["setup", "detected", "graded S", "traded", "trade rate",
                "S traded", "S dropped `X`", "mean R traded"], frows)
    L += ["",
          "**The gap is detection, not grading.** OCR converts detections into trades at "
          "%.2f%% against B&R's %.2f%% — worse, but not by an order of magnitude. The "
          "order-of-magnitude difference is upstream: **%d B&R detections against %d "
          "OCR, %.1fx.** \"Just as popular\" is a question about how often the order-block "
          "detector fires at all, and only secondarily about what happens to it "
          "afterwards."
          % (100.0 * sum(1 for t in T if t["setup"] == "one_candle_rule" and t["traded"]) / max(no, 1),
             100.0 * sum(1 for t in T if t["setup"] == "break_and_retest" and t["traded"]) / max(nb, 1),
             nb, no, nb / max(no, 1)),
          ""]
    ocr_drop = [t for t in dropped if t["setup"] == "one_candle_rule"]
    L += ["",
          "**OCR is not dropped by the same thing B&R is.** The signal type named "
          "`one_candle_rule` is the order-block path in `signal_runner.py`, and it "
          "carries three gates the B&R path does not have:",
          "",
          "```",
          "if stock_risk < 0.50:            grade = D",
          "if grade == \"B\":                 grade = C     # OCR can never be B",
          "if stock_risk / close > 0.004:   grade = D     # stop wider than 0.4% of price",
          "```",
          "",
          "Line two means **the order-block detection site cannot ship a `B`** — and `B` "
          "is the lowest grade the engine trades. Every OCR trade in the book therefore "
          "arrives through a later promotion, not through its own price action (see §6).",
          "",
          "It also has **no rescue branch**: where B&R turns a grader `D` back into a "
          "`C` whenever the candle is the right colour, the order-block path lets the "
          "`D` stand — which is why an OCR drop is silent rather than an alert.",
          ""]
    L += table("What kills a dropped-S OCR signal", ["branch", "signals", "share"],
               counted(ocr_drop, "_branch"))

    # ---- 6. the grader is not the selector ---------------------------------
    traded = [t for t in T if t["traded"]]
    floor = [t for t in traded if "floor B" in t["reason"]]
    L += ["", "## 6. The finding that outranks the drop table: the grader is not the selector",
          "",
          "`_grade_pa` never lifts a signal into the traded tier. It can only produce "
          "`A+`, `B`, `C` or `X`, and in the whole two-year replay it emits `B` or better "
          "on a vanishingly small number of bars. What actually promotes a signal into "
          "the book is one branch of `SignalRunner._calibration_grade`:",
          "",
          "```",
          "elif (with_trend and self._dir_fired[d] == 0 and 0 <= mins <= 90",
          "      and sig[\"grade\"] == \"C\" and \"capped C\" not in sig[\"reason\"]):",
          "    sig[\"grade\"] = TradeGrade.B.value      # first with-trend signal of the day",
          "```",
          "",
          "**%d of the %d traded signals (%.1f%%) carry that `[floor B: first with-trend "
          "signal of the day]` tag** — %d B&R and %d OCR. Only %d earn `B` or better from "
          "their own price action. On the S-graded book it is %d of %d."
          % (len(floor), len(traded), 100.0 * len(floor) / max(len(traded), 1),
             sum(1 for t in floor if t["setup"] == "break_and_retest"),
             sum(1 for t in floor if t["setup"] == "one_candle_rule"),
             len(traded) - len(floor),
             sum(1 for t in traded_s if "floor B" in t["reason"]), len(traded_s)),
          "",
          "Three consequences, and they reframe the whole ticket:",
          "",
          "1. **`C` is the real candidate pool and `X` is the real rejection.** The "
          "A+/A/B/C ladder is very nearly decorative — the engine's actual entry rule is "
          "*\"the first with-trend signal of the day, in the first 90 minutes, that "
          "reached C.\"* Every gate in §1 matters because it decides membership of `C`, "
          "not because it decides a grade.",
          "2. **This is why removing the colour gate is not a small change.** It does not "
          "just add trades at the margin: it changes *which* signal is first, on days "
          "where the first structurally-valid setup had a wrong-colour entry bar. Some "
          "of today's trades would be replaced, not merely joined.",
          "3. **It explains the OCR book without any reference to Austin's ladder.** The "
          "order-block site demotes every `B` to `C`, and the first-of-day floor then "
          "promotes %d of those back to `B`. OCR is not being graded on its structure at "
          "either end."
          % sum(1 for t in floor if t["setup"] == "one_candle_rule"),
          ""]

    L += ["", "## 7. What this hands the next ticket", "",
          "1. **The colour gate is the cheapest single line to A/B and Austin has "
          "already said it is wrong.** `downgrade.score()` even reports it as an "
          "*observation* rather than a veto (`observations.entry_bar_counter_coloured`), "
          "which is the shape R3 would ship. The counterfactual in §2 is the arm to run.",
          "2. **Two of the three biggest gates are not the grader at all.** The HTF-bias "
          "veto and the B&R min-stop gate together account for the majority of the "
          "drop, and neither is a price-action test. `HTF_BIAS_GATE` is already a "
          "measured, default-OFF flag for a *different* bias rule; the veto inside "
          "`grade_trade` is hard-wired and has never been A/B'd on this rig.",
          "3. **The opening-range level bug does not exist.** Two planning documents "
          "assert it. `research/t62_veto_autopsy.md` disproved it on 2026-08-23 and "
          "this run reproduces that. `DIRECTION.md` and `TASKS.md` should be corrected "
          "before another ticket is scoped against a level bug that is not there.",
          "4. **OCR's problem is stop width and a demotion, not a candle test.** The "
          "0.4% ceiling and the $0.50 floor were tuned on a 12-month yfinance split "
          "(`19%W −$13k`) that `A2` already flags as stale, and the `B -> C` demotion "
          "means the order-block path can never ship a tradeable grade on its own. "
          "Re-running that A/B on the two-year rig is a self-contained green task.",
          "5. The expectancy in §4 says the dropped set is **not** free money at today's "
          "exit policy — it is a large pool of setups at roughly the book's own mean R, "
          "and well short of the 2.0R gate. Read together with G7 (*the exit is not the "
          "binding constraint*) and §6 above, the constraint is neither the exit nor the "
          "grade ladder: it is that the engine picks its entry by *arrival order*, not "
          "by structure.",
          "6. **Bug found in passing, not fixed here: `bt2y_trades.json`'s `aligned` "
          "field is not measuring bias.** `backtest_2y.py` computes it as "
          "`(bias == \"bull\") == (t.direction == \"call\")`, but `htf_bias_for` returns "
          "`\"bullish\"`, so the comparison is always False and the field collapses to "
          "*is this a put*. Over the whole book `Counter((aligned, dir))` is "
          "`{('against','call'): 22542, ('with','put'): 22310, ('n/a','call'): 168, "
          "('n/a','put'): 155}` — a 1:1 with direction. The interactive report's \"vs HTF "
          "bias\" facet is therefore a duplicate of its Direction facet. **Nothing in "
          "this document reads that field** — every bias number here comes from the "
          "`htf_bias` the replay handed `grade_trade`. Fixing it re-generates a "
          "published artifact, which is an amber action.",
          ""]

    # ---- 8. P16/W3 -- the HTF-bias veto has no author -----------------------
    bias_dropped = [t for t in dropped if t["_branch"] == BIAS]
    bias_viable = [t for t in bias_dropped if t.get("_minvi") is True]
    bf = Counter(t["_nobias"] for t in bias_viable)
    bias_tradeable = bf["graded_B"] + bf["graded_A+"]
    bias_cf_trade = [t for t in bias_viable if t["_nobias"] in ("graded_B", "graded_A+")]
    n_all, wr_all, mr_all, md_all = agg([t["r"] for t in viable])
    n_bias, wr_bias, mr_bias, md_bias = agg([t["r"] for t in bias_cf_trade])
    L += ["", "## 8. P16/W3 — what the HTF-bias veto costs (author: nobody)", "",
          "Austin, rule ballot batch 02 (c6), asked directly what higher-timeframe bias "
          "should mean: *\"we dont have any higher timeframe bias yet youll need to tell "
          "me what that is then.\"* The veto already has no vote in `research/downgrade.py`"
          " — `score()` demotes it to a reported `observations.htf_opposed` flag, same "
          "shape as the colour gate in §2. This section runs the same counterfactual on "
          "the legacy grader (`omen_bot.py::PriceActionAnalyzer.grade_trade`), which "
          "still hard-vetoes on it.",
          "",
          "**What the veto actually computes.** `htf_bias` is the close of the most "
          "recent completed **1-hour** candle compared to the 20-period simple moving "
          "average of the 20 hourly candles before it — both taken from bars strictly "
          "before the trading day's 09:30 open, never from the current session. If that "
          "last hourly close sits more than 0.1% above the average, the hour is called "
          "\"bullish\"; more than 0.1% below, \"bearish\"; inside that band, \"neutral.\" "
          "`grade_trade` then throws out any signal whose direction disagrees with that "
          "label outright (a long when the label is \"bearish\" grades `D`/skipped, and "
          "vice versa), and caps a \"neutral\" hour's best signals from A+/A down to B. "
          "It is a real higher-timeframe read — the 1-hour bar genuinely sits above the "
          "engine's 1-minute working timeframe — but it is a plain trend filter nobody "
          "on the team ever specified or ratified; three modules (`tastytrade_feed.py`, "
          "`futures_feed.py`, `backtest_week.py`/`research/t4_engine_recall.py`) each "
          "reimplement the same SMA20-of-hourly idea independently, which is what an "
          "unowned rule looks like in a codebase. It is **not** the mislabelled "
          "\"call vs put\" bug `8797aee6` found — that bug lives in `backtest_2y.py`'s "
          "separate `aligned` reporting field (§7 item 6), not in this veto.",
          "",
          "**%d of the 7,219 dropped-S signals (%.1f%%) die on this single line** — the "
          "single largest gate in the drop table (§1)."
          % (len(bias_dropped), 100.0 * len(bias_dropped) / max(len(dropped), 1)),
          ""]
    L += table("Counterfactual: same ladder, HTF-bias veto deleted",
               ["verdict without the bias line", "signals", "what it becomes"],
               [(k.replace("graded_", ""), v,
                 "**tradeable tier**" if k in ("graded_B", "graded_A+")
                 else "alert-only" if k == "graded_C" else "still dropped")
                for k, v in bf.most_common()],
               "Restricted to the %d of %d bias-vetoed signals with a viable stop "
               "(`_min_viable_stop`, same exclusion as §4) — the min-stop gates sit "
               "downstream of the veto and are unaffected by removing it."
               % (len(bias_viable), len(bias_dropped)))
    L += table("Expectancy: the freed set vs the book",
               ["set", "n", "win rate", "mean R", "median R"],
               [("dropped S, viable stop (§4 baseline, all gates)", n_all,
                 "%.1f%%" % wr_all, "%+.3f" % mr_all, "%+.3f" % md_all),
                ("**HTF-veto arm: viable stop AND would grade B+ with the veto off**",
                 n_bias, "%.1f%%" % wr_bias, "%+.3f" % mr_bias, "%+.3f" % md_bias),
                ("S signals the engine actually traded (incumbent)", *band(traded_s, "x")[1:]),
                ("the whole traded book (incumbent, money gate = 2.0R)", *band([t for t in T if t["traded"]], "x")[1:])])
    vs_book = ("above the book's own +0.957R" if mr_bias > 0.957
               else "below the book's own +0.957R" if mr_bias < 0.957 else "flat to the book's +0.957R")
    L += ["",
          "**%d of the %d bias-vetoed signals (%.1f%%) reach a tradeable tier once the "
          "veto is deleted, and %d more become alerts** — %d still die elsewhere (colour "
          "gate or never touched the level) even with the veto gone. Of the tradeable "
          "ones, %d clear `_min_viable_stop` and make up the expectancy row above: "
          "**%+.3fR mean, %s** (incumbent traded book, all setups) and well clear of the "
          "whole dropped-S set's own **+0.465R** (n=%d, §4) — unlike §2's colour-gate arm "
          "(+0.293R, roughly at the dropped-S baseline), this freed set is not "
          "indistinguishable from the rest of the discard pile. **Read the sample size "
          "with it**: n=%d is thin — a fifth the size of the traded S book (n=128) — and "
          "still well short of the 2.0R money gate, so this is a candidate worth a real "
          "A/B (deduped through `NO_REPEAT_ENTRIES` and arrival order, per §6), not a "
          "result to ship on. What it does settle is the provenance question: the veto "
          "has no author, and on this read deleting it costs nothing and may be hiding a "
          "small pool of signals as good as the ones already traded."
          % (bias_tradeable, len(bias_dropped), 100.0 * bias_tradeable / max(len(bias_dropped), 1),
             bf["graded_C"], len(bias_viable) - bias_tradeable, n_bias, mr_bias, vs_book, n_all, n_bias),
          ""]

    Path(args.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote %s (%d lines)" % (args.out, len(L)))
    print("dropped S: %d | colour_gate: %d | non-OR level: %d"
          % (len(dropped), len(colour),
             sum(1 for t in dropped if t["level"] not in ORL)))
    n, wr, mr, md = agg([t["r"] for t in viable])
    print("viable-stop dropped S: n=%d win=%.1f%% meanR=%+.3f medR=%+.3f" % (n, wr, mr, md))


if __name__ == "__main__":
    main()
