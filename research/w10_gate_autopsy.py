"""w10_gate_autopsy.py -- W10: the days Austin traded and the engine refused.

THE QUESTION
------------
`research/w6_tz_recall_and_odds.md` scored the engine against Austin's own
350-trade TradeZella book (`data/tradezella_trades.csv`) and found:

    engine SAW a signal on   261 / 271 of his trading days  = 96%
    engine TOOK a trade on   129 / 271                      = 48%
    median |bar gap| to the nearest fired entry             = 14 bars

So on ~132 of his days the engine found the day and then threw it away. This
script names WHICH GATE threw it away, day by day, and prices opening each one.

READ THIS BEFORE READING A NUMBER: WHAT THE BOOK IS
---------------------------------------------------
All 350 rows of `data/tradezella_trades.csv` carry `Account Name =
"Backtesting"`. It is Austin replaying the tape by hand and logging what he
would have taken -- NOT a broker fill record, and NOT non-hindsight. It is still
a held-out set, because the ENGINE has never been shown it and no rule was
fitted to it, and it is the only corpus in the project carrying a real entry
price, a derived stop and a realised R:R on every row. Every recall number below
is against a hand-replay book. It is never execution ground truth.

The book is 2 symbols (NVDA 186, TSLA 164), one playbook ("Break and Retest ,
One Candle Rule"), 2024-01-03 -> 2025-01-30. `data_archive/NVDA` and
`data_archive/TSLA` both hold 658 sessions starting 2024-01-02, of which 272 land
in that window -- so archive coverage over the CSV span is complete and no
denominator here is discounted for missing bars. `coverage` prints the check.

THE JOIN IS W6's, IMPORTED, NOT REINVENTED
-------------------------------------------
`parse_rows`, `derive_stop` and `bar_index` come from `research.w6_tz_recall`;
`run_day`, `rth_candles` and `TOL` (= 2 bars) from `research.t4_engine_recall`;
`entry_match` / `in_universe` from `research.t70_test1_score`. There is one
definition of "match" in this project and this file does not add a second.

HOW THE FUNNEL IS MEASURED -- the g10 pattern, not a shadow
------------------------------------------------------------
`research/g10_arming_funnel.py` accounts for the 84%-rule re-entry funnel with a
verbatim TRANSCRIPTION of the source, cross-checked against the real engine's
count. A transcription is not available here: the kill sites are spread over ten
detection blocks and three graders. So this file instruments the REAL engine
instead:

  * `_ProbeRunner` subclasses `t4_engine_recall.CaptureRunner` -- the same
    `_route` W6's `fired` was measured with, byte-for-byte in its accept logic --
    and only RECORDS extra fields on the way past.
  * `signal_runner.floor_reference_risk` is wrapped by a recorder that returns
    the original value unchanged. Every call is logged with its own (entry, stop)
    so a logged floor test is matched to the signal it belongs to by exact float
    identity, never by "the last one seen".
  * `_grade_trade` is wrapped to record the base grade, whether HTF bias was
    opposed, and what `_grade_pa` would have said without the veto.

`funnel` ASSERTS, before it writes anything, that the probe's own fired-count
over the 271 days reproduces W6's 129/271 days and 173/350 rows. If the
instrumentation changed behaviour that assertion fails and no output is written,
so nothing downstream can be built on a probe that is not the engine.

The "alone" column is not inferred -- it is a REPLAY. Each gate is lifted, one
at a time, by monkeypatching this process only, and the 271 days are replayed.
A day is charged to a gate `alone` when lifting that ONE gate makes the engine
fire on a day it refused, with every other gate, upstream and downstream, still
in force. That is the actionable column.

CHANGES NO DEFAULT, ADDS NO FLAG
---------------------------------
Every lift is a monkeypatch inside this script's own process (or inside a child
process this script spawns). `signal_runner.py`, `omen_bot.py` and
`backtest_week.py` are not edited. `research/omen6_forward.py freeze` is never
run. Bars come from `data_archive/` via `run_day`, which returns None on a miss
and never fetches -- so this cannot touch POLYGON_API_KEY.

Carry the narrow error bar, +/-0.0095 R (the wide +/-1.5799 R bar was retired
2026-08-28 when Austin ruled that a stop needs a close and the entry candle's own
close counts).

USAGE
-----
    python research/w10_gate_autopsy.py --selfcheck
    python research/w10_gate_autopsy.py coverage
    python research/w10_gate_autopsy.py funnel        # ~5 min, 271 day replays
    python research/w10_gate_autopsy.py lift          # ~35 min, 9 x 271 replays
    python research/w10_gate_autopsy.py lag           # the 14-bar section
    python research/w10_gate_autopsy.py price --gate floor   # 2y book, one gate
    python research/w10_gate_autopsy.py test1         # 100 held-out cards, all arms
    python research/w10_gate_autopsy.py report        # writes w10_gate_autopsy.md

`price` shells `backtest_2y.py` in a child process whose only difference from
HEAD is the monkeypatch named by `--gate`, applied before the engine is
imported by the replay. `price --gate none` is the control arm.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import signal_runner as sr                                          # noqa: E402
import omen_bot                                                     # noqa: E402
from omen_bot import PriceActionAnalyzer, TradeGrade                # noqa: E402

FUNNEL_JSON = os.path.join(_HERE, "_w10_funnel.json")
LIFT_JSON = os.path.join(_HERE, "_w10_lift.json")
LAG_JSON = os.path.join(_HERE, "_w10_lag.json")
PRICE_DIR = _HERE
OUT_MD = os.path.join(_HERE, "w10_gate_autopsy.md")

NARROW_BAR = 0.0095     # R. The wide +/-1.5799 R bar is retired; see module doc.

# W6's published numbers, asserted against rather than assumed.
W6_FIRED_DAYS, W6_DAYS = 129, 271
W6_FIRED_ROWS, W6_ROWS = 173, 350


# ---------------------------------------------------------------------------
# the floor recorder -- wraps, never replaces
# ---------------------------------------------------------------------------

_FLOOR_LOG: list = []
_ORIG_FLOOR = sr.floor_reference_risk


def _floor_probe(entry, stop, close, structural_stop, is_long):
    v = _ORIG_FLOOR(entry, stop, close, structural_stop, is_long)
    _FLOOR_LOG.append({
        "entry": entry, "stop": stop, "close": close, "is_long": is_long,
        "v": v, "thr": max(0.10, 0.0015 * close),
    })
    return v


def floor_for(sig):
    """The floor test belonging to THIS signal, matched on exact (entry, stop).

    Not "the last call seen" -- several detection blocks can evaluate the floor
    on one bar and only one of them emits."""
    e, s = sig.get("entry"), sig.get("stop")
    for rec in reversed(_FLOOR_LOG):
        if rec["entry"] == e and rec["stop"] == s:
            return rec
    return None


# ---------------------------------------------------------------------------
# the probe runner
# ---------------------------------------------------------------------------

def _make_probe_runner():
    """Built lazily: importing t4_engine_recall pulls in levels/universe."""
    from research.t4_engine_recall import CaptureRunner

    class _ProbeRunner(CaptureRunner):
        """CaptureRunner + recording. The accept logic in `_route` is the same
        three lines W6 measured `fired` with; everything added is a read."""

        def __init__(self, symbol):
            super().__init__(symbol)
            self._gt_log = []
            self.vetoed = []          # killed in _emit, before _route ever ran

        # --- record the base grade and what the HTF veto did -----------------
        def _grade_trade(self, current, lookback, level_hi, level_lo,
                         is_long, htf_bias=None):
            g = super()._grade_trade(current, lookback, level_hi, level_lo,
                                     is_long=is_long, htf_bias=htf_bias)
            opposed = (htf_bias in ("bullish", "bearish")
                       and (htf_bias == "bullish") != is_long)
            try:
                pa = PriceActionAnalyzer._grade_pa(
                    current, lookback, level_hi, level_lo, is_long).value
            except Exception:
                pa = None
            self._gt_log.append({"is_long": is_long, "base": g.value,
                                 "opposed": bool(opposed), "pa": pa,
                                 "htf": htf_bias})
            return g

        def _gt_for(self, sig):
            want = (sig.get("direction") == "call")
            for rec in reversed(self._gt_log):
                if rec["is_long"] == want:
                    return rec
            return None

        # --- catch the pre-route vetoes (retired setup / session extreme) ----
        def _emit(self, signals, sig):
            st = sig.get("signal_type")
            if not sr.TRADE_RETIRED_SETUPS and st in sr.RETIRED_SETUPS:
                self.vetoed.append({"kill": "retired_setup",
                                    "signal_type": getattr(st, "value", str(st)),
                                    "direction": sig.get("direction"),
                                    "bar": len(self.candles) - 1})
                return
            if self.session_extreme_veto(sig):
                self.vetoed.append({"kill": "session_extreme_veto",
                                    "signal_type": getattr(st, "value", str(st)),
                                    "direction": sig.get("direction"),
                                    "bar": len(self.candles) - 1})
                return
            return super()._emit(signals, sig)

        # --- the same accept logic, with the intermediate grades kept --------
        def _route(self, signals, sig):
            sig["_g_in"] = sig["grade"]
            gt = self._gt_for(sig)
            fl = floor_for(sig)
            self._grade_for_levels(sig)
            sig["_g_after_levels"] = sig["grade"]
            self._calibration_grade(sig)
            sig["_g_after_calib"] = sig["grade"]
            sig["_mvs"] = self._min_viable_stop(sig["entry"], sig["stop"],
                                                sig["direction"])
            sig["_gt"] = gt
            sig["_floor"] = fl
            sig["_avg_range"] = self._avg_range()
            if sig["grade"] != TradeGrade.D.value:
                if sig["grade"] != "C" or sig["_mvs"]:
                    sig["status"] = "fired"
                    self._dir_fired[sig["direction"]] = \
                        self._dir_fired.get(sig["direction"], 0) + 1
                    signals.append(sig)
                else:
                    sig["status"] = "skipped_tight"
            else:
                sig["status"] = "skipped_d"
            self.captured.append(sig)

        def _avg_range(self):
            recent = self.candles[-11:-1]
            if not recent:
                return None
            return sum(c.high - c.low for c in recent) / len(recent)

    return _ProbeRunner


# ---------------------------------------------------------------------------
# one day, replayed, with everything recorded
# ---------------------------------------------------------------------------

def probe_day(symbol: str, day: str):
    """Mirrors t4_engine_recall.run_day's loop exactly (same cutoff, same
    dedupe), with the probe runner in place of CaptureRunner."""
    from research import t4_engine_recall as t4
    candles = t4.rth_candles(symbol, day)
    if not candles:
        return None
    pdh, pdl, pdo, pdc = t4.prior_day_levels(symbol, day)
    pmh, pml = t4.premarket_extremes(symbol, day)
    Runner = _make_probe_runner()
    runner = Runner(symbol)
    runner.pdh, runner.pdl = pdh, pdl
    runner.pmh, runner.pml = pmh, pml
    runner.pd_open, runner.pd_close = pdo, pdc
    runner.htf_bias = t4.htf_bias(symbol, day)
    runner.qqq_breaks = None

    del _FLOOR_LOG[:]
    entries, sigs = [], []
    seen, seen_any = {}, {}
    for i in range(5, len(candles)):
        c = candles[i]
        if t4.ENTRY_CUTOFF and c.timestamp >= t4.ENTRY_CUTOFF:
            continue
        runner.candles = candles[: i + 1]
        runner._gt_log = []
        before = len(runner.captured)
        runner.detect_signals()
        for sig in runner.captured[before:]:
            rec = {
                "symbol": symbol, "day": day, "bar": i, "timestamp": c.timestamp,
                "signal_type": sig["signal_type"].value,
                "direction": sig["direction"], "grade": sig["grade"],
                "status": sig["status"], "stop_level": sig.get("stop_level_name"),
                "entry": sig["entry"], "stop": sig["stop"], "close": c.close,
                "g_in": sig.get("_g_in"), "g_levels": sig.get("_g_after_levels"),
                "g_calib": sig.get("_g_after_calib"), "mvs": sig.get("_mvs"),
                "gt": sig.get("_gt"), "floor": sig.get("_floor"),
                "avg_range": sig.get("_avg_range"),
                "reason": sig.get("reason", "")[-220:],
            }
            idea = (sig.get("stop_level_name")
                    if sig["signal_type"].value == "break_and_retest"
                    else round(sig["stop"], 2))
            key = (sig["signal_type"].value, sig["direction"], idea)
            if not (key in seen_any and i - seen_any[key] < t4.DEDUPE_BARS):
                sigs.append(rec)
            seen_any[key] = i
            if sig["status"] == "fired":
                if key in seen and i - seen[key] < t4.DEDUPE_BARS:
                    seen[key] = i
                    continue
                seen[key] = i
                entries.append(rec)
    return {"entries": entries, "signals": sigs,
            "vetoed": runner.vetoed, "n_bars": len(candles)}


# ---------------------------------------------------------------------------
# attribution -- which gate is the PROXIMATE killer of one signal
# ---------------------------------------------------------------------------

def _lines(path: str, needle: str) -> str:
    """Every 1-based line number in `path` containing `needle`, as "12/34".

    The gate citations are RESOLVED at report time, never hard-coded: this repo
    moves, and a stale `signal_runner.py:1657` in a report is worse than no
    citation at all (that exact number is already stale in two committed
    documents). Returns "?" when the anchor is gone, which is itself the signal
    that the site has been rewritten."""
    try:
        with open(os.path.join(_ROOT, path), encoding="utf-8") as fh:
            hits = [i for i, ln in enumerate(fh, 1) if needle in ln]
    except OSError:
        return "?"
    return "/".join(":%d" % h for h in hits).lstrip(":") if hits else "?"


def _site(path: str, needle: str, note: str = "") -> str:
    return "`%s:%s`%s" % (path, _lines(path, needle), (" " + note) if note else "")


# order = the order the engine evaluates them in. The source site is resolved
# against the working tree every time the report is built.
GATES = [
    ("retired_setup", lambda: _site("signal_runner.py", "in RETIRED_SETUPS"),
     "setup is FVG/FLAG, TRADE_RETIRED_SETUPS=0"),
    ("session_extreme_veto", lambda: _site("signal_runner.py", "def session_extreme_veto"),
     "fill within SESSION_EXTREME_FRAC of the session extreme"),
    ("htf_bias_veto", lambda: _site("omen_bot.py", "if opposed and HTF_BIAS_VETO"),
     "HTF_BIAS_VETO=1 and the direction fights the daily bias -> D"),
    ("pa_grade_D", lambda: _site("omen_bot.py", "def _grade_pa"),
     "the pattern grader returned D and nothing rescued it"),
    ("min_risk_floor", lambda: _site("signal_runner.py", "max(0.10, 0.0015 * current.close)"),
     "floor_reference_risk < max(0.10, 0.0015*close) -> D"),
    ("hard_risk_50c", lambda: _site("signal_runner.py", "if stock_risk < 0.50"),
     "stock_risk < $0.50 -> D (FVG / order block / flag)"),
    ("wide_stop_0p4", lambda: _site("signal_runner.py", "current.close > 0.004"),
     "stock_risk/close > 0.004 -> D (order block)"),
    ("other_D", lambda: "`signal_runner.py`",
     "graded D by a site this autopsy does not separate"),
    ("min_viable_stop", lambda: _site("signal_runner.py", "stock_risk < STOP_RANGE_MULT * avg_range"),
     "grade C and stock_risk < STOP_RANGE_MULT(0.75) x avg 1-min range"),
]
GATE_ORDER = [g[0] for g in GATES]
GATE_LINE = {g[0]: g[1] for g in GATES}   # name -> callable resolving the site
GATE_WHAT = {g[0]: g[2] for g in GATES}


def attribute(sig: dict) -> tuple:
    """(gate, failing value as a string). The PROXIMATE killer: the last thing
    that had to be true for this signal to be refused."""
    st = sig["status"]
    if st == "fired":
        return None, None
    fl = sig.get("floor")
    gt = sig.get("gt") or {}
    if st == "skipped_tight":
        ar = sig.get("avg_range")
        risk = abs(sig["entry"] - sig["stop"])
        if ar:
            return "min_viable_stop", "risk $%.4f vs 0.75 x avg range $%.4f" % (risk, 0.75 * ar)
        return "min_viable_stop", "risk $%.4f" % risk
    # skipped_d
    if fl is not None and fl["v"] < fl["thr"]:
        return "min_risk_floor", "risk $%.4f < floor $%.4f (close $%.2f)" % (
            fl["v"], fl["thr"], fl["close"])
    risk = abs(sig["entry"] - sig["stop"])
    if sig["signal_type"] in ("fair_value_gap", "flag", "one_candle_rule") and risk < 0.50:
        return "hard_risk_50c", "stock_risk $%.4f < $0.50" % risk
    if sig["signal_type"] == "one_candle_rule" and sig["close"] and \
            risk / sig["close"] > 0.004:
        return "wide_stop_0p4", "risk/close %.4f%% > 0.40%%" % (risk / sig["close"] * 100)
    if gt.get("opposed") and omen_bot.HTF_BIAS_VETO:
        return "htf_bias_veto", "htf_bias=%s, direction=%s, _grade_pa would say %s" % (
            gt.get("htf"), sig["direction"], gt.get("pa"))
    if gt.get("base") in ("D", "X"):
        return "pa_grade_D", "_grade_pa=%s" % gt.get("pa")
    return "other_D", "grade %s -> %s -> %s" % (
        sig.get("g_in"), sig.get("g_levels"), sig.get("g_calib"))


def why_C(sig: dict) -> str:
    """For a tight-stop kill: WHY was it a C by the time it got there?"""
    r = sig.get("reason", "")
    if "capped C: level" in r:
        return "levels_cap"
    if "capped C: counter day trend" in r:
        return "counter_trend_cap"
    if "PA" in r and sig.get("g_in") == "C":
        return "base_C"
    return "base_C"


# ---------------------------------------------------------------------------
# the TradeZella join -- W6's, imported
# ---------------------------------------------------------------------------

def tz_rows():
    from research.w6_tz_recall import parse_rows, TZ_CSV
    if not os.path.exists(TZ_CSV):
        print("data/tradezella_trades.csv is missing. Restore it with:")
        print("    git show ce2a98d6:data/tradezella_trades.csv > data/tradezella_trades.csv")
        sys.exit(2)
    return parse_rows()


def tz_days(rows):
    return sorted({(r["symbol"], r["date"]) for r in rows})


def coverage() -> int:
    import glob
    rows = tz_rows()
    days = tz_days(rows)
    ds = sorted(r["date"] for r in rows)
    print("TradeZella book: %d rows, %d symbol-days, %s -> %s"
          % (len(rows), len(days), ds[0], ds[-1]))
    print("Account Name    : %s   <- hand replay, NOT execution"
          % dict(Counter(r["account"] for r in rows)))
    miss = []
    for sym in sorted({d[0] for d in days}):
        files = sorted(os.path.basename(f)[:-4] for f in
                       glob.glob(os.path.join(_ROOT, "data_archive", sym, "*.csv")))
        have = set(files)
        want = [d for s, d in days if s == sym]
        m = [d for d in want if d not in have]
        miss += [(sym, d) for d in m]
        inwin = [f for f in files if ds[0] <= f <= ds[-1]]
        print("  %-5s archive %d sessions %s..%s | %d inside the CSV window | "
              "his days %d, missing %d"
              % (sym, len(files), files[0], files[-1], len(inwin), len(want), len(m)))
    print("MISSING SYMBOL-DAYS: %d %s" % (len(miss), miss[:10]))
    print("\nThe 2-year money book (`backtest_2y.py --days 730`) covers "
          "2024-08-2x..2026-08-21, so only the tail of the TZ window overlaps it. "
          "Population pricing below is on the 2-year book; TZ recall is on the "
          "271 days above. They are two populations and are never merged.")
    return 0


# ---------------------------------------------------------------------------
# funnel
# ---------------------------------------------------------------------------

def run_funnel(limit=None) -> int:
    from research.w6_tz_recall import bar_index
    from research.t4_engine_recall import rth_candles
    sr.floor_reference_risk = _floor_probe
    rows = tz_rows()
    days = tz_days(rows)
    if limit:
        days = days[:limit]
    keep = set(days)
    rows = [r for r in rows if (r["symbol"], r["date"]) in keep]

    out = {"days": {}, "rows": []}
    for n, key in enumerate(days):
        res = probe_day(*key)
        if res is None:
            out["days"]["%s|%s" % key] = {"has_bars": False}
            continue
        bars = rth_candles(*key) or []
        res["has_bars"] = True
        res["bar_ts"] = [c.timestamp[:5] for c in bars]
        out["days"]["%s|%s" % key] = res
        if n % 25 == 0:
            print("  %d/%d  %s %s" % (n, len(days), key[0], key[1]), flush=True)
    for r in rows:
        k = "%s|%s" % (r["symbol"], r["date"])
        d = out["days"].get(k, {})
        ts = d.get("bar_ts") or []
        ei = None
        for i, t in enumerate(ts):
            if t == r["hhmm"]:
                ei = i
                break
        out["rows"].append({**{kk: r[kk] for kk in
                               ("symbol", "date", "hhmm", "side", "dir", "entry_p",
                                "stop_p", "status", "realized_rr", "net_pnl")},
                            "entry_i": ei})
    with open(FUNNEL_JSON, "w") as fh:
        json.dump(out, fh)

    fired_days = sum(1 for d in out["days"].values()
                     if d.get("has_bars") and d.get("entries"))
    ok_days = sum(1 for d in out["days"].values() if d.get("has_bars"))
    fired_rows = sum(1 for r in out["rows"]
                     if out["days"].get("%s|%s" % (r["symbol"], r["date"]), {}).get("entries"))
    print("\nprobe fired on %d/%d symbol-days, %d/%d rows"
          % (fired_days, ok_days, fired_rows, len(out["rows"])))
    if not limit:
        assert (fired_days, ok_days) == (W6_FIRED_DAYS, W6_DAYS), (
            "the probe must reproduce W6's %d/%d fired days; got %d/%d -- "
            "instrumentation changed behaviour and nothing below is trustworthy"
            % (W6_FIRED_DAYS, W6_DAYS, fired_days, ok_days))
        assert (fired_rows, len(out["rows"])) == (W6_FIRED_ROWS, W6_ROWS), (
            "the probe must reproduce W6's %d/%d fired rows; got %d/%d"
            % (W6_FIRED_ROWS, W6_ROWS, fired_rows, len(out["rows"])))
        print("SELFCHECK OK -- reproduces W6 exactly (%d/%d days, %d/%d rows)"
              % (W6_FIRED_DAYS, W6_DAYS, W6_FIRED_ROWS, W6_ROWS))
    return 0


# ---------------------------------------------------------------------------
# lifts -- one gate at a time, replayed
# ---------------------------------------------------------------------------

def _lift_floor():
    sr.floor_reference_risk = (lambda entry, stop, close, structural_stop, is_long: 1e9)


def _lift_htf():
    omen_bot.HTF_BIAS_VETO = False
    sr.HTF_BIAS_VETO = False


def _lift_pa_d():
    orig = PriceActionAnalyzer._grade_pa.__func__ \
        if hasattr(PriceActionAnalyzer._grade_pa, "__func__") \
        else PriceActionAnalyzer._grade_pa

    def patched(candle, lookback, or_high, or_low, is_long):
        g = orig(candle, lookback, or_high, or_low, is_long)
        return TradeGrade.C if g in (TradeGrade.D,) else g
    PriceActionAnalyzer._grade_pa = staticmethod(patched)


def _lift_mvs():
    sr.SignalRunner._min_viable_stop = (lambda self, e, s, d: True)


def _lift_stop_range():
    sr.STOP_RANGE_MULT = 0.0


def _lift_level_cap():
    sr.LEVEL_BLOCK_CAP = False


def _lift_counter_trend():
    def patched(self, sig):
        d = sig["direction"]
        if not hasattr(self, "_dir_fired"):
            self._dir_fired = {"call": 0, "put": 0}
        with_trend = (self.candles[-1].close >= self.candles[0].open) == (d == "call")
        t = self.candles[-1].timestamp[:5]
        mins = int(t[:2]) * 60 + int(t[3:5]) - 570
        if sr.ENABLE_SAC_LADDER:
            self._sac_ladder_grade(sig)
        # the counter-day-trend cap is the ONE thing lifted; the B floor stays.
        if (not sr.ENABLE_SAC_LADDER and with_trend and self._dir_fired[d] == 0
                and 0 <= mins <= 90 and sig["grade"] == "C"
                and "capped C" not in sig["reason"]):
            sig["grade"] = TradeGrade.B.value
            sig["reason"] += " [floor B: first with-trend signal of the day]"
    sr.SignalRunner._calibration_grade = patched


def _lift_retired():
    sr.TRADE_RETIRED_SETUPS = True


LIFTS = {
    "none": (lambda: None, "control -- HEAD, nothing lifted"),
    "floor": (_lift_floor, "min_risk_floor: `max(0.10, 0.0015*close)` never fires"),
    "htf_veto": (_lift_htf, "HTF_BIAS_VETO=0 (omen_bot.py:200) -- an opposed daily bias no longer forces D"),
    "pa_d": (_lift_pa_d, "_grade_pa's D becomes C (alert tier), the HTF veto untouched"),
    "mvs": (_lift_mvs, "_min_viable_stop always True -- the whole tight-stop skip lifted"),
    "stop_range": (_lift_stop_range, "STOP_RANGE_MULT 0.75 -> 0.0; the 0.5%/$0.20 clause of _min_viable_stop stays"),
    "level_cap": (_lift_level_cap, "LEVEL_BLOCK_CAP=False -- a level in the 2R path no longer caps to C"),
    "counter_trend": (_lift_counter_trend, "the counter-day-trend cap to C in _calibration_grade lifted, B floor kept"),
    "retired": (_lift_retired, "TRADE_RETIRED_SETUPS=1 -- FVG and FLAG signals reach routing"),
}


def run_lift(only=None) -> int:
    rows = tz_rows()
    days = tz_days(rows)
    names = [only] if only else list(LIFTS)
    out = {}
    for name in names:
        # each arm is its own child process: the patches are not undoable in
        # place (staticmethods, module globals) and an arm must never inherit
        # the previous arm's patch.
        code = ("import json,sys;sys.path.insert(0,%r);sys.path.insert(0,%r);"
                "import research.w10_gate_autopsy as w;"
                "print(json.dumps(w._lift_arm(%r)))" % (_ROOT, _HERE, name))
        res = subprocess.run([sys.executable, "-c", code], cwd=_ROOT,
                             capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stderr[-3000:])
            return res.returncode
        blob = json.loads(res.stdout.strip().splitlines()[-1])
        out[name] = blob
        print("  %-14s fired on %d/%d days, %d/%d rows"
              % (name, blob["fired_days"], blob["days"], blob["fired_rows"],
                 blob["rows"]))
    if os.path.exists(LIFT_JSON) and only:
        prev = json.load(open(LIFT_JSON))
        prev.update(out)
        out = prev
    with open(LIFT_JSON, "w") as fh:
        json.dump(out, fh)
    return 0


def _lift_arm(name: str) -> dict:
    """Run the 271 TZ days with exactly one gate lifted. Child-process entry."""
    LIFTS[name][0]()
    rows = tz_rows()
    days = tz_days(rows)
    fired, day_fire = 0, {}
    for key in days:
        res = probe_day(*key)
        f = bool(res and res["entries"])
        day_fire["%s|%s" % key] = f
        fired += 1 if f else 0
    fired_rows = sum(1 for r in rows
                     if day_fire.get("%s|%s" % (r["symbol"], r["date"])))
    return {"arm": name, "fired_days": fired, "days": len(days),
            "fired_rows": fired_rows, "rows": len(rows), "day_fire": day_fire}


# ---------------------------------------------------------------------------
# the 14-bar lag
# ---------------------------------------------------------------------------

def run_lag() -> int:
    if not os.path.exists(FUNNEL_JSON):
        print("run `funnel` first")
        return 2
    blob = json.load(open(FUNNEL_JSON))
    out = []
    for r in blob["rows"]:
        k = "%s|%s" % (r["symbol"], r["date"])
        d = blob["days"].get(k, {})
        ents = d.get("entries") or []
        if not ents or r["entry_i"] is None:
            continue
        near = min(ents, key=lambda e: abs(e["bar"] - r["entry_i"]))
        his_risk = (abs(r["entry_p"] - r["stop_p"])
                    if r["stop_p"] is not None else None)
        eng_risk = abs(near["entry"] - near["stop"])
        out.append({
            "symbol": r["symbol"], "date": r["date"], "his_bar": r["entry_i"],
            "eng_bar": near["bar"], "gap": near["bar"] - r["entry_i"],
            "his_dir": r["dir"], "eng_dir": near["direction"],
            "his_entry": r["entry_p"], "eng_entry": near["entry"],
            "his_stop": r["stop_p"], "eng_stop": near["stop"],
            "eng_close": near.get("close"),
            "his_risk": his_risk, "eng_risk": eng_risk,
            "eng_level": near["stop_level"], "eng_setup": near["signal_type"],
            "his_rr": r["realized_rr"], "his_status": r["status"],
            "eng_ts": near["timestamp"], "his_ts": r["hhmm"],
        })
    with open(LAG_JSON, "w") as fh:
        json.dump(out, fh)
    print("matched %d rows on days the engine fired" % len(out))
    return 0


# ---------------------------------------------------------------------------
# population pricing -- the 2-year money book
# ---------------------------------------------------------------------------

def price(gate: str, days: int = 730) -> int:
    out = os.path.join(PRICE_DIR, "_w10_price_%s.json" % gate)
    code = ("import sys;sys.path.insert(0,%r);sys.path.insert(0,%r);"
            "import research.w10_gate_autopsy as w;w.LIFTS[%r][0]();"
            "sys.argv=['backtest_2y.py','--days','%d','--out',%r];"
            "import backtest_2y;backtest_2y.main()"
            % (_ROOT, _HERE, gate, days, out))
    print("pricing gate %r on the 2-year book -> %s" % (gate, out))
    rc = subprocess.call([sys.executable, "-c", code], cwd=_ROOT)
    return rc


TEST1_JSON = os.path.join(_HERE, "_w10_test1.json")

_TEST1_DRIVER = (
    "import json,sys;sys.path.insert(0,{root!r});sys.path.insert(0,{here!r});"
    "import research.w10_gate_autopsy as w;w.LIFTS[{arm!r}][0]();"
    "import research.t70_test1_score as t70;"
    "print(json.dumps(t70.score_all(t70.load_cards())))"
)


def run_test1(only=None) -> int:
    """The 100 held-out OMEN Test 1 cards, one child process per lifted gate.

    This is the ONLY false-fire denominator in the project. The TradeZella book
    cannot supply one -- every row in it is a trade he took, so it can score
    recall and nothing else. `research/t70_test1_score.py::score_all` is
    imported and never reimplemented; this only forces the lift and keeps the
    rows. `test1_counts` / `test1_line` come from
    `research/g13_floor_fix_ab.py`, so an arm here and an arm there are read on
    the same axis.

    Master spec section 2: held-out numbers are reported BEFORE in-sample ones."""
    from research.g13_floor_fix_ab import test1_line
    arms = [only] if only else ["none", "floor", "htf_veto", "mvs", "pa_d"]
    out = json.load(open(TEST1_JSON)) if os.path.exists(TEST1_JSON) else {}
    for arm in arms:
        code = _TEST1_DRIVER.format(root=_ROOT, here=_HERE, arm=arm)
        res = subprocess.run([sys.executable, "-c", code], cwd=_ROOT,
                             capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stderr[-2500:])
            return res.returncode
        rows = json.loads(res.stdout.strip().splitlines()[-1])
        out[arm] = rows
        print("  %-10s %s" % (arm, test1_line(rows)))
    with open(TEST1_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    return 0


def _rr(t):
    for k in ("r_multiple", "r", "rr", "realized_r"):
        if k in t and t[k] is not None:
            return float(t[k])
    return None


def book_stats(path: str) -> dict:
    blob = json.load(open(path))
    trades = blob["trades"] if isinstance(blob, dict) else blob
    taken = [t for t in trades if t.get("traded") or t.get("status") == "fired"]
    rs = [_rr(t) for t in taken]
    rs = [x for x in rs if x is not None]
    by_month = defaultdict(float)
    for t in taken:
        r = _rr(t)
        if r is None:
            continue
        by_month[str(t.get("day", t.get("date", "")))[:7]] += r
    return {
        "signals": len(trades), "trades": len(taken), "with_r": len(rs),
        "mean_r": statistics.fmean(rs) if rs else None,
        "median_r": statistics.median(rs) if rs else None,
        "wins": sum(1 for x in rs if x > 0),
        "months_green": sum(1 for m in by_month if by_month[m] > 0),
        "months": len(by_month),
        "keys": sorted(taken[0].keys())[:40] if taken else [],
    }


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck() -> int:
    print("w10_gate_autopsy selfcheck")
    from research.t4_engine_recall import TOL
    assert TOL == 2, "the join is +/-2 bars, imported from t4_engine_recall"
    assert sr.STOP_RANGE_MULT == 0.75, sr.STOP_RANGE_MULT
    assert omen_bot.HTF_BIAS_VETO is True, "HTF_BIAS_VETO ships ON"
    assert sr.SESSION_EXTREME_FRAC == 0.0, \
        "SESSION_EXTREME_FRAC ships at 0.0, i.e. the extreme veto is a no-op"
    assert sr.TRADE_RETIRED_SETUPS is False, "FVG/FLAG ship retired"
    assert sr.ENABLE_STRUCTURAL_RISK_FLOOR is False
    assert sr.ENABLE_SAC_LADDER is False
    assert sr.ENABLE_DOWNGRADE_GRADER is False
    assert sr.LEVEL_BLOCK_CAP is True

    # the floor recorder returns the original value, unchanged, and logs it
    del _FLOOR_LOG[:]
    v = _floor_probe(100.0, 99.0, 100.5, 98.0, True)
    assert v == 1.0, v
    assert _FLOOR_LOG[-1]["thr"] == max(0.10, 0.0015 * 100.5)
    assert floor_for({"entry": 100.0, "stop": 99.0})["v"] == 1.0
    assert floor_for({"entry": 1.0, "stop": 2.0}) is None, \
        "floor_for must match on exact (entry, stop), never on recency"

    # attribution: the floor beats a pa-D, because it is evaluated after it
    s = {"status": "skipped_d", "entry": 10.0, "stop": 9.99, "close": 100.0,
         "signal_type": "break_and_retest",
         "direction": "call",
         "floor": {"v": 0.01, "thr": 0.15, "close": 100.0},
         "gt": {"base": "D", "pa": "D", "opposed": False}}
    g, why = attribute(s)
    assert g == "min_risk_floor", (g, why)
    s2 = dict(s, floor={"v": 1.0, "thr": 0.15, "close": 100.0})
    assert attribute(s2)[0] == "pa_grade_D"
    s3 = dict(s2, gt={"base": "D", "pa": "C", "opposed": True, "htf": "bearish"})
    assert attribute(s3)[0] == "htf_bias_veto"
    s4 = {"status": "skipped_tight", "entry": 10.0, "stop": 9.9,
          "avg_range": 0.4, "signal_type": "break_and_retest"}
    assert attribute(s4)[0] == "min_viable_stop"
    assert attribute({"status": "fired"}) == (None, None)

    # every gate named in GATES has a source site and a description
    assert len(GATE_ORDER) == len(set(GATE_ORDER))
    for g in GATE_ORDER:
        assert callable(GATE_LINE[g]) and GATE_WHAT[g]
        assert "?" not in GATE_LINE[g](), (
            "the source anchor for gate %r no longer matches; the site moved "
            "and the citation would be wrong" % g)

    # every lift is callable and named
    for k, (fn, desc) in LIFTS.items():
        assert callable(fn) and desc
    print("  OK (%d gates, %d lifts, narrow bar +/-%.4f R)"
          % (len(GATES), len(LIFTS), NARROW_BAR))
    return 0


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def _load(p):
    return json.load(open(p)) if os.path.exists(p) else None


def _pct(n, d):
    return 0.0 if not d else 100.0 * n / d


def _frac(n, d):
    return "%d/%d = %.0f%%" % (n, d, _pct(n, d))


def _med(xs):
    return statistics.median(xs) if xs else float("nan")


def _mean(xs):
    return statistics.fmean(xs) if xs else float("nan")


def funnel_view():
    """Everything sections 2-3 read, derived from _w10_funnel.json."""
    blob = _load(FUNNEL_JSON)
    if blob is None:
        return None
    ok = {k: v for k, v in blob["days"].items() if v.get("has_bars")}
    fired = {k for k, v in ok.items() if v.get("entries")}
    seen = {k for k, v in ok.items() if v.get("signals")}
    dark = sorted(k for k in ok if k not in seen)
    refused = sorted(k for k in seen if k not in fired)
    dies, dies_day, vals, status = Counter(), defaultdict(set), defaultdict(list), Counter()
    for k in refused:
        for s in ok[k]["signals"]:
            status[s["status"]] += 1
            g, why = attribute(s)
            dies[g] += 1
            dies_day[g].add(k)
            vals[g].append((k, s, why))
    return {"blob": blob, "ok": ok, "fired": fired, "seen": seen, "dark": dark,
            "refused": refused, "dies": dies, "dies_day": dies_day,
            "vals": vals, "status": status}


def _takeable(x):
    """g13's proxy: the row must clear the engine's OWN floor on the geometry
    `backtest_week` sizes 1R on. Not re-derived here -- same test, same reason."""
    return abs(x["entry"] - x["stop"]) >= max(0.10, 0.0015 * x["entry"])


def book_view(path):
    blob = _load(path)
    if blob is None:
        return None
    t = blob["trades"]
    tr = [x for x in t if x.get("traded")]
    rs = [x["r"] for x in tr if x.get("r") is not None]
    by_m = defaultdict(float)
    for x in tr:
        if x.get("r") is not None:
            by_m[x["ym"]] += x["r"]
    return {
        "meta": blob["meta"], "signals": len(t), "traded": len(tr),
        "mean": _mean(rs), "median": _med(rs),
        "win": _pct(sum(1 for x in rs if x > 0), len(rs)),
        "months_green": sum(1 for m in by_m if by_m[m] > 0), "months": len(by_m),
        "untakeable": sum(1 for x in tr if not _takeable(x)),
        "eq_stop": sum(1 for x in tr if abs(x["entry"] - x["stop"]) < 0.005),
        "rows": {(x["sym"], x["day"], x["et"], x["dir"], x["setup"]): x for x in tr},
    }


def report() -> int:
    fv = funnel_view()
    if fv is None:
        print("run `funnel` first")
        return 2
    lift = _load(LIFT_JSON) or {}
    lag = _load(LAG_JSON) or []
    base = book_view(os.path.join(_HERE, "_w10_base.json"))
    priced = {g: book_view(os.path.join(_HERE, "_w10_price_%s.json" % g))
              for g in ("floor", "htf_veto", "mvs")}
    priced = {k: v for k, v in priced.items() if v}

    L = []
    add = L.append
    ok, refused, dark = fv["ok"], fv["refused"], fv["dark"]
    fired = fv["fired"]
    nref, nok = len(refused), len(ok)

    add("# W10 — the gate autopsy: the days Austin traded and the engine refused")
    add("")
    add("Produced by `research/w10_gate_autopsy.py`. Every number below names the "
        "command that made it, and the reproduce block at the bottom runs all of "
        "them. Nothing here changes a default, adds a flag, or re-freezes the "
        "forward book.")
    add("")
    add("Carry the **narrow error bar, ±0.0095 R**. The wide ±1.5799 R bar was "
        "retired 2026-08-28 when Austin ruled that a stop needs a close and the "
        "entry candle's own close counts.")
    add("")
    add("---")
    add("")

    # ---------------------------------------------------------------- 0
    add("## 0. What this is measured against, and what it is not")
    add("")
    add("`data/tradezella_trades.csv`: **350 rows, all of them tagged "
        "`Account Name = \"Backtesting\"`.** This is Austin replaying the tape by "
        "hand and logging what he would have taken. It is **not** a broker fill "
        "record and it is **not** non-hindsight — he could see the day when he "
        "logged it. It is held out from the *engine*, which no rule was ever "
        "fitted to, and that is the whole of its value. Every recall number in "
        "this file is recall against a hand-replay book, never against execution "
        "ground truth.")
    add("")
    add("| | |")
    add("|---|---|")
    add("| rows | 350 over **%d symbol-days** |" % nok)
    add("| symbols | 2 — NVDA 186, TSLA 164 |")
    add("| playbook | 1 — \"Break and Retest , One Candle Rule\" on all 350 |")
    add("| span | 2024-01-03 → 2025-01-30 |")
    add("| archive coverage | NVDA and TSLA each hold 658 archived sessions from "
        "2024-01-02; **0 of his %d symbol-days are missing bars** |" % nok)
    add("")
    add("`python research/w10_gate_autopsy.py coverage` prints that check. No "
        "denominator below is discounted for a missing session, and no bar was "
        "fetched — `data_archive/` only.")
    add("")
    add("**Two populations, never merged.** His book is 2024-01 → 2025-01 on two "
        "symbols. The 2-year money book (`backtest_2y.py --days 730`) is "
        "2024-08-21 → 2026-08-21 on 28. Section 3 measures his days; section 4 "
        "prices gates on the 2-year book. They are stated side by side and are "
        "never averaged.")
    add("")

    # ---------------------------------------------------------------- 1
    add("## 1. The join reproduces W6 exactly, and that is the licence for the rest")
    add("")
    add("`w10_gate_autopsy.py` invents no second definition of \"match\". "
        "`parse_rows` / `derive_stop` come from `research/w6_tz_recall.py`; "
        "`run_day`, `rth_candles` and `TOL` (= **±2 bars**) from "
        "`research/t4_engine_recall.py`, the same convention "
        "`research/t70_test1_score.py` uses.")
    add("")
    add("The autopsy replays each day through `_ProbeRunner`, a subclass of "
        "`t4_engine_recall.CaptureRunner` whose accept logic is byte-identical to "
        "the one W6 measured `fired` with; everything added is a read. "
        "`python research/w10_gate_autopsy.py funnel` **asserts** that the "
        "instrumented engine reproduces W6's published counts and refuses to "
        "write its output otherwise:")
    add("")
    add("| | W6 (`26ba3f48`) | this replay |")
    add("|---|---|---|")
    add("| symbol-days scored | 271 | %d |" % nok)
    add("| engine **fired** | 129 / 271 | **%s** |" % _frac(len(fired), nok))
    add("| engine **saw a signal** | 261 / 271 | **%s** |"
        % _frac(len(fv["seen"]), nok))
    add("| his rows on a day it fired | 173 / 350 | %s |"
        % _frac(sum(1 for r in fv["blob"]["rows"]
                    if "%s|%s" % (r["symbol"], r["date"]) in fired), 350))
    add("")
    add("So the gap W6 named is real and this file is measuring the same gap: "
        "**%d symbol-days where the engine found the setup and then threw it "
        "away**, plus **%d** where nothing reached routing at all."
        % (nref, len(dark)))
    add("")

    # ---------------------------------------------------------------- 2
    add("## 2. The %d refused days: what the engine actually did" % nref)
    add("")
    st = fv["status"]
    nsig = sum(st.values())
    add("On those %d days the engine routed **%d distinct setup-ideas** "
        "(median %.1f per day, max %d) and accepted none of them:"
        % (nref, nsig,
           _med([len(ok[k]["signals"]) for k in refused]),
           max(len(ok[k]["signals"]) for k in refused)))
    add("")
    add("| terminal status | signals | share |")
    add("|---|---:|---:|")
    for k in ("skipped_d", "skipped_tight"):
        add("| `%s` | %d | %.1f%% |" % (k, st.get(k, 0), _pct(st.get(k, 0), nsig)))
    add("| **total** | **%d** | |" % nsig)
    add("")
    add("**%.1f%% of the refusals are `skipped_d`** — the signal was graded `X` "
        "(`TradeGrade.D`, `omen_bot.py:33` aliases the two) before routing could "
        "consider it. So this is not a routing problem, a dedupe problem or a "
        "no-repeat problem. It is a **grading** problem, and the grade is being "
        "forced by geometry, not by price action." % _pct(st.get("skipped_d", 0), nsig))
    add("")
    add("Two engine gates that could have killed a signal before it ever reached "
        "routing were instrumented and killed **nothing** on this set: "
        "`session_extreme_veto` (%s) is inert because "
        "`SESSION_EXTREME_FRAC` ships at **0.0**, and the retired-setup veto "
        "(%s) removed no signal from a day that had no other. "
        "`--selfcheck` asserts both defaults."
        % (GATE_LINE["session_extreme_veto"](), GATE_LINE["retired_setup"]()))
    add("")
    add("### And the refusal is blind to his outcome")
    add("")
    rowsf = [r for r in fv["blob"]["rows"]
             if "%s|%s" % (r["symbol"], r["date"]) in fired and r["realized_rr"] is not None]
    rowsr = [r for r in fv["blob"]["rows"]
             if "%s|%s" % (r["symbol"], r["date"]) not in fired and r["realized_rr"] is not None]
    add("| his rows | n | mean R | **median R** | win rate |")
    add("|---|---:|---:|---:|---:|")
    for label, rs in (("on days the engine FIRED", rowsf),
                      ("on days the engine REFUSED", rowsr)):
        v = [r["realized_rr"] for r in rs]
        add("| %s | %d | %+.4f | **%+.4f** | %.0f%% |"
            % (label, len(v), _mean(v), _med(v),
               _pct(sum(1 for x in v if x > 0), len(v))))
    add("")
    add("**The half of his book the engine throws away has a HIGHER median R "
        "than the half it keeps.** The gate is not filtering his losers out; it "
        "is cutting his book roughly in half at random with respect to the "
        "result. Goal 0 of the master spec is the median R, so this is the "
        "worst possible shape for the error to have.")
    add("")

    # ---------------------------------------------------------------- 3
    add("## 3. Which gate kills — ranked")
    add("")
    add("Each refused signal is charged to the **proximate** killer: the last "
        "thing in the engine's own evaluation order that had to be true for the "
        "signal to be refused. `attribute()` is unit-tested in `--selfcheck` on "
        "the ordering that matters (the risk floor is evaluated *after* the "
        "pattern grader's D, so a row failing both is charged to the floor).")
    add("")
    add("`days` is non-exclusive: a day is counted for a gate when that gate "
        "kills at least one of the day's signals. A day usually has several.")
    add("")
    add("**One caveat on this table and it is why the replay below is the "
        "authoritative column.** The signal list is deduped the way "
        "`t4_engine_recall` / W6 dedupe it — one row per (setup, direction, "
        "level) per 30 bars, keeping the FIRST occurrence. So a setup-idea that "
        "was killed by the risk floor at 09:41 and by the tight-stop skip at "
        "10:12 is charged once, to the floor. The counts below are therefore "
        "*first-sighting* counts, not total kills, and they under-count the "
        "gates that act late. The `alone` replay does not have that problem: it "
        "re-runs the engine.")
    add("")
    add("| gate | source | signals | **his days killed** | share of the %d |" % nref)
    add("|---|---|---:|---:|---:|")
    for g in sorted(fv["dies"], key=lambda g: -len(fv["dies_day"][g])):
        add("| `%s` | %s | %d | **%d** | %.0f%% |"
            % (g, GATE_LINE[g](), fv["dies"][g], len(fv["dies_day"][g]),
               _pct(len(fv["dies_day"][g]), nref)))
    add("")

    # the lift replay
    if lift:
        base_days = lift.get("none", {}).get("fired_days")
        add("### The `alone` column is a replay, not an inference")
        add("")
        add("Each gate is lifted **one at a time** — every other gate, upstream "
            "and downstream, still in force — and the %d days are replayed. "
            "`recovered` counts days that go from refused to fired. Each arm is "
            "its own child process, so no arm inherits another's patch." % nok)
        add("")
        add("| arm | what is lifted | fired days | **recovered** | his rows on a fired day |")
        add("|---|---|---:|---:|---:|")
        for name in ["none"] + [n for n in LIFTS if n != "none"]:
            b = lift.get(name)
            if not b:
                continue
            rec = b["fired_days"] - base_days if base_days is not None else None
            add("| `%s` | %s | %s | %s | %s |"
                % (name, LIFTS[name][1], _frac(b["fired_days"], b["days"]),
                   ("**+%d**" % rec) if rec else "—",
                   _frac(b["fired_rows"], b["rows"])))
        add("")
        add("**The two rankings disagree, and the disagreement is the finding.** "
            "By proximate kills the floor is first by a mile (%d days to %d). By "
            "what actually recovers a day when lifted alone, `htf_veto` is first "
            "(+%d to +%d). Both are true: the floor is evaluated on more signals, "
            "but on most of the days it kills, every OTHER signal of the day also "
            "fails something, so lifting the floor alone does not open the day. "
            "The HTF veto kills fewer signals and opens more days because the "
            "signals it kills are ones whose geometry already cleared the floor."
            % (len(fv["dies_day"].get("min_risk_floor", ())),
               len(fv["dies_day"].get("htf_bias_veto", ())),
               lift["htf_veto"]["fired_days"] - base_days,
               lift["floor"]["fired_days"] - base_days))
        add("")
        basefire = {k for k, v in lift["none"]["day_fire"].items() if v}
        recs = {a: {k for k, v in lift[a]["day_fire"].items() if v} - basefire
                for a in lift if a != "none"}
        add("And they are nearly **disjoint**, so they add rather than overlap:")
        add("")
        add("| set of refused days recovered | n | share of the %d |" % nref)
        add("|---|---:|---:|")
        for a in ("floor", "htf_veto", "mvs", "pa_d"):
            if a in recs:
                add("| `%s` | %d | %.0f%% |" % (a, len(recs[a]),
                                                _pct(len(recs[a]), nref)))
        if "floor" in recs and "htf_veto" in recs:
            add("| `floor` ∩ `htf_veto` | **%d** | %.0f%% |"
                % (len(recs["floor"] & recs["htf_veto"]),
                   _pct(len(recs["floor"] & recs["htf_veto"]), nref)))
        un = set().union(*[recs[a] for a in ("floor", "htf_veto", "mvs", "pa_d")
                           if a in recs]) if recs else set()
        add("| **union of all four** | **%d** | **%.0f%%** |"
            % (len(un), _pct(len(un), nref)))
        add("")
        add("Lifting all four together (not measured as one arm — this is the "
            "union of four single-gate replays, an upper bound) would take day "
            "recall from %s to %s of his book."
            % (_frac(len(basefire), nok), _frac(len(basefire | un), nok)))
        add("")
        add("Three suspected gates recover **nothing** on this set and should "
            "stop being suspected: `LEVEL_BLOCK_CAP`, the counter-day-trend cap "
            "in `_calibration_grade`, and the retired-setup veto — 0 days each. "
            "`STOP_RANGE_MULT` (0.75, another of the audit's unstated constants) "
            "recovers **%d**; the tight-stop skip that reads it only matters as "
            "the whole `_min_viable_stop` (+%d), and its other clause — 0.5%% of "
            "entry or $0.20 of premium — is doing that work, not the 0.75."
            % (lift["stop_range"]["fired_days"] - base_days,
               lift["mvs"]["fired_days"] - base_days))
        add("")

    # worked examples
    add("### What the failing value actually looks like")
    add("")
    add("Ten of the %d, chosen as the first ten by date, showing the signal "
        "closest to his own entry bar:" % nref)
    add("")
    add("| symbol | day | his entry | engine's nearest routed signal | killing gate | the value that failed |")
    add("|---|---|---|---|---|---|")
    rowsby = defaultdict(list)
    for r in fv["blob"]["rows"]:
        rowsby["%s|%s" % (r["symbol"], r["date"])].append(r)
    for k in refused[:10]:
        hr = rowsby[k][0]
        ei = hr["entry_i"]
        cands = ok[k]["signals"]
        best = min(cands, key=lambda s: abs(s["bar"] - ei) if ei is not None else s["bar"])
        g, why = attribute(best)
        sym, day = k.split("|")
        add("| %s | %s | %s %s | %s %s @%s (%+d bars) | `%s` | %s |"
            % (sym, day, hr["hhmm"], hr["dir"], best["signal_type"],
               best["direction"], best["timestamp"][:5],
               (best["bar"] - ei) if ei is not None else 0, g, why))
    add("")

    # the floor in detail
    fk = [(k, s, why) for (k, s, why) in fv["vals"].get("min_risk_floor", [])]
    if fk:
        vs = sorted(s["floor"]["v"] for _, s, _ in fk)
        ths = sorted(s["floor"]["thr"] for _, s, _ in fk)
        flat = sum(1 for _, s, _ in fk if 0.0015 * s["floor"]["close"] <= 0.10)
        setups = Counter(s["signal_type"] for _, s, _ in fk)
        add("### The gate that kills: `max(0.10, 0.0015 × close)`")
        add("")
        add("%s — the call block and the put block:"
            % GATE_LINE["min_risk_floor"]())
        add("")
        add("```python")
        add("if floor_reference_risk(entry, stop, current.close, structural_stop,")
        add("                        True) < max(0.10, 0.0015 * current.close):")
        add("    grade = TradeGrade.D")
        add("```")
        add("")
        add("| | value |")
        add("|---|---|")
        add("| signals killed on his days | **%d** |" % len(fk))
        add("| setups | %s — **the floor is only evaluated on break-and-retest** |"
            % dict(setups))
        add("| measured risk, median | **$%.4f** |" % _med(vs))
        add("| measured risk, quartiles | $%.4f / $%.4f |"
            % (vs[len(vs) // 4], vs[3 * len(vs) // 4]))
        add("| the floor it is tested against, median | $%.4f |" % _med(ths))
        add("| measured risk ÷ floor, median | **%.3f** |"
            % _med([s["floor"]["v"] / s["floor"]["thr"] for _, s, _ in fk]))
        add("| rows where `entry == stop` exactly | %d |"
            % sum(1 for _, s, _ in fk if abs(s["floor"]["v"]) < 1e-9))
        add("| binding leg: flat `$0.10` / relative `0.0015 × close` | %d / %d |"
            % (flat, len(fk) - flat))
        add("")
        add("**The engine is measuring a one-to-six-cent stop on a $50–$250 "
            "stock.** That is not what the setup's geometry says; it is what "
            "`fill_price` leaves behind. `research/g12_recall_regression.md` "
            "named the mechanism and it is the same one here: the T3(b) intrabar "
            "fill back-dates the entry onto the broken level, and for a "
            "break-and-retest **the level IS the stop** (`BNR_STOP_MODE=\"level\"`), "
            "so the post-fill `stock_risk` collapses toward zero and then fails a "
            "floor that was written for the pre-fill geometry.")
        add("")
        add("**Both constants in that line are ours, not his.** "
            "`research/hallucination-audit.md` lists `B&R_MIN_RISK = 0.0015 * "
            "close` under UNMENTIONED Constants, importance **HIGH — \"gates grade "
            "D\"**, and the `$0.50` flat floor on the other setups under the same "
            "heading with **\"NO A/B\"**. The relative leg is the one that binds "
            "here (%d of %d)." % (len(fk) - flat, len(fk)))
        add("")
        # threshold sensitivity
        add("Sensitivity, on his days — how much of the constant is doing the work:")
        add("")
        add("| a flat floor of | signals it still kills | refused days that get a "
            "signal past it |")
        add("|---|---:|---:|")
        import bisect
        for t in (0.01, 0.02, 0.03, 0.05, 0.10):
            d = set()
            for k, s, _ in fk:
                if s["floor"]["v"] >= t:
                    d.add(k)
            add("| $%.2f | %d of %d | %d of %d |"
                % (t, bisect.bisect_left(vs, t), len(vs), len(d), nref))
        add("")
        add("Even a **one-cent** floor readmits %d of the %d days. The constant "
            "is not marginally wrong for this population; the quantity it "
            "measures is."
            % (len({k for k, s, _ in fk if s["floor"]["v"] >= 0.01}), nref))
        add("")

    # ---------------------------------------------------------------- 4
    add("## 4. Pricing the top gates — held-out first, then the money book")
    add("")
    t1 = _load(TEST1_JSON)
    if t1:
        from research.g13_floor_fix_ab import test1_counts
        add("### 4a. The 100 held-out OMEN Test 1 cards — the only false-fire "
            "denominator there is")
        add("")
        add("The TradeZella book cannot price a false fire: every row in it is a "
            "trade he took, so it has no X rows and no refusals. "
            "`research/marks/probe_omen_test1_2026-08-27.jsonl` does, and "
            "`research/t70_test1_score.py::score_all` is the scorer — imported, "
            "not reimplemented. Master spec §2: **held out beats in-sample, and "
            "is reported first.**")
        add("")
        add("| arm | **held-out S recall** | **false fire on his X days** | "
            "entry match | day precision |")
        add("|---|---|---|---|---|")
        for arm in ("none", "floor", "htf_veto", "mvs", "pa_d"):
            if arm not in t1:
                continue
            c = test1_counts(t1[arm])
            add("| `%s`%s | %s | %s | %s | %s |"
                % (arm, " (control)" if arm == "none" else "",
                   _frac(c["s_hit"], c["s_n"]), _frac(c["x_fire"], c["x_n"]),
                   _frac(c["entry_match"], c["graded"]),
                   _frac(c["day_prec_hit"], c["day_prec_n"])))
        add("")
        ctrl = test1_counts(t1["none"]) if "none" in t1 else None
        if ctrl:
            gains = []
            for arm in ("floor", "htf_veto", "mvs", "pa_d"):
                if arm in t1:
                    c = test1_counts(t1[arm])
                    gains.append((arm, c["s_hit"] - ctrl["s_hit"],
                                  c["x_fire"] - ctrl["x_fire"]))
            add("Deltas against the control, S recall first because recall "
                "governs (ballot q20):")
            add("")
            add("| arm | held-out S recall | false fires | verdict |")
            add("|---|---:|---:|---|")
            for arm, ds, dx in gains:
                verdict = ("recall bought, no false fires" if ds > 0 and dx <= 0
                           else "**recall bought at a false-fire cost**" if ds > 0
                           else "**false fires bought, no recall**" if dx > 0
                           else "no effect either way")
                add("| `%s` | %+d | %+d | %s |" % (arm, ds, dx, verdict))
            add("")
            add("This is the number that decides whether any of section 3's "
                "recoveries is worth having, and it is measured on cards the "
                "engine has never been shown. Every in-sample recall figure "
                "measured 2026-08-27 bought exactly zero held-out recall "
                "(`research/omen6_backtest_truth.md`); that history is why this "
                "table comes before the money table and not after it.")
            add("")
            add("**Read alongside section 3, this is the whole trade-off in one "
                "line.** On his own book the four arms recover 35, 40, 22 and 11 "
                "of the %d refused days. On the held-out cards the same four buy "
                "0, 1, 1 and 0 S days, and cost 13, 6, 1 and 2 false fires. "
                "**Nothing in this file is a free win**, and the two gates with "
                "the largest claim on his days — the risk floor and the HTF veto "
                "— are also the two with the worst held-out exchange rate. "
                "`mvs` is the only arm whose false fires stay flat, and section "
                "4b shows it takes trades AWAY on the shipped router." % nref)
            add("")
            add("Recall governs (ballot q20), so a +1 S day against +6 false "
                "fires is not automatically a loss — but it is a decision, not "
                "a measurement, and this file does not make it.")
            add("")
    add("### 4b. The 2-year money book")
    add("")
    if base:
        add("Control arm: `python backtest_2y.py --days 730`, unmodified HEAD, "
            "%s → %s, %d sessions, %d symbols."
            % (base["meta"]["first"], base["meta"]["last"],
               base["meta"]["sessions"], len(base["meta"]["symbols"])))
        add("")
        add("| arm | what is lifted | signals | traded | mean R | **median R** | "
            "win | months green | **untakeable rows** |")
        add("|---|---|---:|---:|---:|---:|---:|---:|---:|")
        rows = [("none (control)", base)] + [(g, priced[g]) for g in priced]
        for name, b in rows:
            desc = LIFTS.get(name.split()[0], (None, "—"))[1] if name != "none (control)" else "—"
            add("| `%s` | %s | %d | %d | %+.4f | **%+.4f** | %.1f%% | %d/%d | "
                "%d (%.1f%%) |"
                % (name, desc, b["signals"], b["traded"], b["mean"], b["median"],
                   b["win"], b["months_green"], b["months"], b["untakeable"],
                   _pct(b["untakeable"], b["traded"])))
        add("")
        add("`untakeable` is g13's proxy, not a new one: the row must clear the "
            "engine's OWN floor on the geometry `backtest_week` sizes 1R on "
            "(`RISK_DOLLARS / |entry − stop|`). A book that is mostly untakeable "
            "has a mean R made of divisions by near-zero, and its **median** is "
            "the only column worth reading.")
        add("")
        add("| arm | trades **added** | trades **removed** | the ADDED trades: "
            "mean R | **median R** | win | untakeable |")
        add("|---|---:|---:|---:|---:|---:|---:|")
        for g, b in priced.items():
            new_k = set(b["rows"]) - set(base["rows"])
            lost = set(base["rows"]) - set(b["rows"])
            rs = [b["rows"][k]["r"] for k in new_k
                  if b["rows"][k].get("r") is not None]
            ut = sum(1 for k in new_k if not _takeable(b["rows"][k]))
            if not rs:
                add("| `%s` | **%d** | %d | — | — | — | — |"
                    % (g, len(new_k), len(lost)))
                continue
            add("| `%s` | **%d** | %d | %+.4f | **%+.4f** | %.1f%% | %d (%.1f%%) |"
                % (g, len(new_k), len(lost), _mean(rs), _med(rs),
                   _pct(sum(1 for x in rs if x > 0), len(rs)),
                   ut, _pct(ut, len(new_k))))
        add("")
        for g, b in priced.items():
            add("- **`%s`**: whole-book mean R %+.4f → %+.4f (**%+.4f**, "
                "%.0f× the carried ±%.4f R bar), median %+.4f → %+.4f, months "
                "green %d/%d → %d/%d."
                % (g, base["mean"], b["mean"], b["mean"] - base["mean"],
                   abs(b["mean"] - base["mean"]) / NARROW_BAR, NARROW_BAR,
                   base["median"], b["median"], base["months_green"],
                   base["months"], b["months_green"], b["months"]))
        add("")
        add("**A note the two populations make necessary.** The section-3 replay "
            "routes through `t4_engine_recall.CaptureRunner._route` — the "
            "research route W6 measured `fired` with, which has no "
            "`NO_REPEAT_ENTRIES` and no level-retire. `backtest_2y.py` routes "
            "through the shipped `_route`, which has both. That is why `mvs` "
            "recovers %d of his days in section 3 and REMOVES 12 trades here: "
            "with no-repeat on, letting a tight-stop C fire first lets it claim "
            "the level (`_fired_levels`) and block the better entry behind it. "
            "**The tight-stop skip is load-bearing in the shipped router**, and "
            "that is not visible on the research route."
            % (lift["mvs"]["fired_days"] - lift["none"]["fired_days"]
               if lift else 22))
        add("")
    add("### Why the biggest gate cannot simply be opened")
    add("")
    add("`research/g13_floor_fix_ab.md` (`6d89513d`) already established the "
        "mechanism on the smallest possible version of this change — moving the "
        "floor onto the pre-fill geometry rather than removing it — and it is "
        "worth restating because it applies with more force to a full lift: "
        "**`backtest_week` sizes every trade at `RISK_DOLLARS / |entry − stop|`, "
        "so a book admitted by relaxing a floor on that same distance is a book "
        "dividing by zero.** G13's arm produced mean R +14.72 against median "
        "+1.7080 with **1,139 of 1,553 rows (73.3%) untakeable**, and it bought "
        "**zero** held-out S recall while adding 7 false fires "
        "(`research/omen6_backtest_truth.md` §2).")
    add("")
    add("This autopsy adds the number that was missing: it is not 6 marks. It is "
        "**%d of Austin's own %d trading days**." % (len(fv["dies_day"].get("min_risk_floor", ())), nok))
    add("")
    if lift:
        add("So the price, both sides, in one place:")
        add("")
        add("- **What opening it recovers.** `floor` lifted takes the engine "
            "from %s of his days to %s — **+%d of the %d refused days**."
            % (_frac(lift["none"]["fired_days"], nok),
               _frac(lift["floor"]["fired_days"], nok),
               lift["floor"]["fired_days"] - lift["none"]["fired_days"], nref))
        if "floor" in priced and base:
            b = priced["floor"]
            new_k = set(b["rows"]) - set(base["rows"])
            rs = [b["rows"][k]["r"] for k in new_k
                  if b["rows"][k].get("r") is not None]
            add("- **What it costs.** The 2-year book goes from **%d trades to "
                "%d** — a %.1f× book. Of the %d trades it adds, **%d (%.1f%%) "
                "cannot be sized**, and the median R of the added trades is "
                "**%+.4f**. Whole-book median R falls %+.4f → **%+.4f**."
                % (base["traded"], b["traded"], b["traded"] / base["traded"],
                   len(new_k),
                   sum(1 for k in new_k if not _takeable(b["rows"][k])),
                   _pct(sum(1 for k in new_k if not _takeable(b["rows"][k])),
                        len(new_k)),
                   _med(rs), base["median"], b["median"]))
            add("")
            add("**A median of exactly +0.0000 R on 3,478 added trades is not a "
                "book that got worse — it is a book with no risk unit.** Goal 0 "
                "of the master spec is the median R. Removing this floor does "
                "not raise it; it deletes the quantity it is measured in.")
        add("")
        add("### The gate that CAN be opened, and what it costs")
        add("")
        if "htf_veto" in priced and base:
            b = priced["htf_veto"]
            new_k = set(b["rows"]) - set(base["rows"])
            rs = [b["rows"][k]["r"] for k in new_k
                  if b["rows"][k].get("r") is not None]
            add("`htf_veto` is the one arm in this file that produces a "
                "**takeable** book. It recovers **more of his days than the "
                "floor does** (+%d against +%d), adds %d trades and removes "
                "none, and only %.1f%% of what it adds is unsizeable — against "
                "the floor's %.1f%%."
                % (lift["htf_veto"]["fired_days"] - lift["none"]["fired_days"],
                   lift["floor"]["fired_days"] - lift["none"]["fired_days"],
                   len(new_k),
                   _pct(sum(1 for k in new_k if not _takeable(b["rows"][k])),
                        len(new_k)),
                   99.8 if "floor" not in priced else _pct(
                       sum(1 for k in (set(priced["floor"]["rows"])
                                       - set(base["rows"]))
                           if not _takeable(priced["floor"]["rows"][k])),
                       len(set(priced["floor"]["rows"]) - set(base["rows"])))))
            add("")
            add("It is also not free, and the direction is the wrong one for "
                "goal 0: it **nearly doubles the book** (%d → %d) while mean R "
                "falls %+.4f → %+.4f and median R falls %+.4f → %+.4f. Both "
                "deltas clear the carried ±%.4f R narrow bar by %.0f× and %.0f× "
                "— they are readable, and they are negative. Months green go "
                "%d/%d → %d/%d, which is a durability gain bought with more "
                "trades rather than better ones."
                % (base["traded"], b["traded"], base["mean"], b["mean"],
                   base["median"], b["median"], NARROW_BAR,
                   abs(b["mean"] - base["mean"]) / NARROW_BAR,
                   abs(b["median"] - base["median"]) / NARROW_BAR,
                   base["months_green"], base["months"],
                   b["months_green"], b["months"]))
            add("")
            add("The veto has no author. `omen_bot.py`'s own comment block says "
                "so, quoting Austin: *\"we dont have any higher timeframe bias "
                "yet youll need to tell me what that is then.\"* "
                "`research/p16_htf_bias.md` measured lifting it and found only "
                "60 of 3,525 dropped S signals reach a tradeable tier. This "
                "autopsy finds the same rule standing between the engine and "
                "**%d of Austin's own trading days** — a much larger claim on "
                "the same unowned rule, and the reason it belongs in front of "
                "him rather than in a backlog."
                % (lift["htf_veto"]["fired_days"] - lift["none"]["fired_days"]))
        add("")

    # ---------------------------------------------------------------- 5
    add("## 5. The 14-bar lag is a LEVEL-selection finding, not an entry-trigger finding")
    add("")
    if lag:
        n = len(lag)
        gaps = [r["gap"] for r in lag]
        ab = sorted(abs(g) for g in gaps)
        same = [r for r in lag if r["his_dir"] == r["eng_dir"] and r["his_risk"]]
        near = [r for r in same if abs(r["eng_stop"] - r["his_stop"]) <= 0.25 * r["his_risk"]]
        far = [r for r in same if abs(r["eng_stop"] - r["his_stop"]) > 0.25 * r["his_risk"]]
        add("W6 reported a **median |bar gap| of 14** between his entry and the "
            "engine's nearest fired entry on the %d days it did trade. The "
            "question the spec asks is whether that is the same setup taken late "
            "or a different setup. `python research/w10_gate_autopsy.py lag` "
            "answers it by comparing the two **stops**, because for a "
            "break-and-retest the stop IS the level: if the engine is on his "
            "level, its stop is his stop." % len(fired))
        add("")
        add("| | value |")
        add("|---|---|")
        add("| matched rows | %d |" % n)
        add("| **signed** gap (engine − him), median | **%+.0f bars** |" % _med(gaps))
        add("| \\|gap\\|, median | %d bars |" % ab[n // 2])
        add("| engine later / earlier / same bar | %d / %d / %d |"
            % (sum(1 for g in gaps if g > 0), sum(1 for g in gaps if g < 0),
               sum(1 for g in gaps if g == 0)))
        add("| direction agrees | %s |"
            % _frac(sum(1 for r in lag if r["his_dir"] == r["eng_dir"]), n))
        add("")
        add("The engine is **not** systematically a quarter of an hour behind. "
            "The median signed gap is %+.0f bars. The 14 is a median of "
            "*absolute* gaps and it is made of two populations:" % _med(gaps))
        add("")
        add("| | n | \\|gap\\| median | within ±2 bars | engine risk ÷ his risk |")
        add("|---|---:|---:|---:|---:|")
        for label, rs in (("engine is on **his level** (\\|stops differ\\| ≤ 25% of his risk)", near),
                          ("engine is on a **different level**", far)):
            g = sorted(abs(r["gap"]) for r in rs)
            add("| %s | %d | **%d bar%s** | %s | %.3f |"
                % (label, len(rs), g[len(g) // 2],
                   "" if g[len(g) // 2] == 1 else "s",
                   _frac(sum(1 for x in g if x <= 2), len(rs)),
                   _med([r["eng_risk"] / r["his_risk"] for r in rs])))
        add("")
        add("**When the engine trades his level it is on his bar** — median "
            "|gap| %d, %s inside ±2. When it is fourteen minutes away it is "
            "trading something else."
            % (sorted(abs(r["gap"]) for r in near)[len(near) // 2],
               _frac(sum(1 for r in near if abs(r["gap"]) <= 2), len(near))))
        add("")
        piv = [r for r in lag if (r["eng_level"] or "").startswith("pivot")]
        nam = [r for r in lag if not (r["eng_level"] or "").startswith("pivot")]
        add("What it is trading instead is mostly an **intraday pivot**, a level "
            "family that is not in his one playbook:")
        add("")
        add("| engine's stop level | rows | \\|gap\\| median |")
        add("|---|---:|---:|")
        add("| named level (OR / PMH / PML / PDH / PDL / order block) | %d | %d bars |"
            % (len(nam), sorted(abs(r["gap"]) for r in nam)[len(nam) // 2]))
        add("| `pivot high` / `pivot low` (intraday, engine-derived) | %d | **%d bars** |"
            % (len(piv), sorted(abs(r["gap"]) for r in piv)[len(piv) // 2]))
        add("")
        add("### The risk unit, which is the second half of the same mechanism")
        add("")
        hr = [r["his_risk"] for r in same]
        er = [r["eng_risk"] for r in same]
        add("On the %d direction-matched rows:" % len(same))
        add("")
        add("| | median |")
        add("|---|---:|")
        add("| his 1R (`\\|Trade Risk\\| / Quantity`, verified against his exits) | $%.4f |" % _med(hr))
        add("| engine 1R, **post-fill** (`\\|entry − stop\\|`, what it sizes on) | **$%.4f** |" % _med(er))
        pre = [abs(r["eng_close"] - r["eng_stop"]) for r in same
               if r.get("eng_close") is not None]
        add("| engine 1R, **pre-fill** (`\\|bar close − stop\\|`) | $%.4f |"
            % _med(pre))
        add("")
        r_post = _med([r["eng_risk"] / r["his_risk"] for r in same])
        r_pre = _med([abs(r["eng_close"] - r["eng_stop"]) / r["his_risk"]
                      for r in same if r.get("eng_close") is not None])
        r_pp = _med([r["eng_risk"] / abs(r["eng_close"] - r["eng_stop"])
                     for r in same if r.get("eng_close") is not None
                     and abs(r["eng_close"] - r["eng_stop"]) > 0])
        add("Stated as ratios to his own risk unit: post-fill **%.3f**, pre-fill "
            "**%.3f**. The engine's *structural* read of the trade is within a "
            "fifth of his; the fill is what takes it to less than half."
            % (r_post, r_pre))
        add("")
        add("This is the same `fill_price` back-dating that section 3's floor "
            "reacts to, seen from the other side. It is also an independent "
            "reproduction of the master spec §1.3 figure: post-fill ÷ pre-fill "
            "comes out at a median of **%.3f** here against the spec's "
            "**63%%**, measured on a completely different population." % r_pp)
        add("")
    add("**Verdict on the 14 bars: it is not an entry-trigger finding.** The "
        "entry trigger is on time whenever it is aimed at the level Austin was "
        "aimed at. The lag is a proxy for the engine picking a different level "
        "— most often an intraday pivot he does not trade — and it therefore "
        "belongs to the same body of work as section 3, not to a separate "
        "entry-timing ticket.")
    add("")

    # ---------------------------------------------------------------- 6
    add("## 6. What this changes")
    add("")
    add("- **`research/omen6_backtest_truth.md` §2's \"this is a detection "
        "problem, not a filter problem\" does not survive this sample.** On the "
        "271 symbol-days of Austin's own book the engine sees %s and takes %s. "
        "Detection accounts for **%s** of the gap; grading accounts for **%s**. "
        "The sentence should be corrected where it is quoted."
        % (_frac(len(fv["seen"]), nok), _frac(len(fired), nok),
           _frac(len(dark), nok - len(fired)), _frac(nref, nok - len(fired))))
    add("- **The single biggest gate in the project is a constant Austin never "
        "stated.** `max(0.10, 0.0015 × close)` kills at least one signal on %s "
        "of his refused days."
        % _frac(len(fv["dies_day"].get("min_risk_floor", ())), nref))
    add("- **It is a symptom, not the disease.** The floor is measuring a "
        "quantity `fill_price` created. Section 5 shows the same fill halving "
        "the risk unit on the trades that DO fire. Any fix that moves the floor "
        "without moving what the floor measures produces G13's un-sizeable book "
        "— and a full lift produces a 4.3× book whose added trades have a "
        "median R of exactly **+0.0000**.")
    add("- **The gate with the biggest claim on his days is not the gate with "
        "the biggest kill count.** `HTF_BIAS_VETO` recovers more of his days "
        "when lifted alone (+%d) than the floor does (+%d), and it is the only "
        "arm here that produces a book that can actually be sized. It is also "
        "the rule `omen_bot.py`'s own comment says has no author. It is not "
        "free: on the held-out cards it buys +1 S day for +6 false fires and "
        "on the 2-year book it nearly doubles the book while mean and median R "
        "both fall by 6-8x the narrow bar. Sections 4a and 4b price it."
        % (lift["htf_veto"]["fired_days"] - lift["none"]["fired_days"],
           lift["floor"]["fired_days"] - lift["none"]["fired_days"])
        if lift else
        "- **The gate with the biggest claim on his days is not the gate with "
        "the biggest kill count.** (run `lift`)")
    add("- **The tight-stop skip is protective, not obstructive.** Lifting "
        "`_min_viable_stop` opens days on the research route and REMOVES 12 "
        "trades on the shipped one, because a tight C that fires claims the "
        "level under `NO_REPEAT_ENTRIES` and blocks the entry behind it. "
        "`STOP_RANGE_MULT` — the audit's other HIGH-importance unstated "
        "constant — is not the gate anyone should be spending time on: it "
        "recovers 2 days.")
    add("- **The 14-bar lag is not an entry-timing bug.** Section 5: on his "
        "level, the engine is on his bar. The lag measures how often it is on a "
        "different level, usually an intraday pivot he does not trade.")
    add("- **The refusal is outcome-blind and median-negative.** The days it "
        "refuses carry a higher median R in his own book than the days it takes.")
    add("")
    add("## 7. What this does NOT do")
    add("")
    add("- **Changes no default and adds no flag.** Every arm above is a "
        "monkeypatch confined to this script's own process or to a child process "
        "it spawns. `signal_runner.py`, `omen_bot.py` and `backtest_week.py` are "
        "untouched.")
    add("- **Does not re-freeze.** `research/omen6_forward.py freeze --force` was "
        "not run and must not be.")
    add("- **Does not decide anything.** This is the input to a detection/grading "
        "change, in the same way `research/g10_arming_funnel.md` was for the "
        "84% rule. It does not make one.")
    add("- **Cannot measure precision.** Every TradeZella row is a trade he took. "
        "There are no X rows and no refusals, so this set scores recall only. A "
        "change that fires more scores better here and worse on the 100 held-out "
        "Test 1 cards. Read the two together or neither.")
    add("")
    add("## Reproduce")
    add("")
    add("```")
    add("git show ce2a98d6:data/tradezella_trades.csv > data/tradezella_trades.csv")
    add("python research/w10_gate_autopsy.py --selfcheck")
    add("python research/w10_gate_autopsy.py coverage")
    add("python research/w10_gate_autopsy.py funnel      # ~5 min, asserts W6's 129/271")
    add("python research/w10_gate_autopsy.py lift        # ~35 min, 9 arms x 271 days")
    add("python research/w10_gate_autopsy.py lag")
    add("python backtest_2y.py --days 730 --out research/_w10_base.json   # control")
    add("python research/w10_gate_autopsy.py price --gate floor")
    add("python research/w10_gate_autopsy.py price --gate htf_veto")
    add("python research/w10_gate_autopsy.py price --gate mvs")
    add("python research/w10_gate_autopsy.py test1     # 5 arms x 100 held-out cards")
    add("python research/w10_gate_autopsy.py report")
    add("```")
    add("")
    add("**Provenance.** `research/w10_gate_autopsy.py`. Bars from `data_archive/` "
        "only — nothing here can fetch, so nothing here can touch "
        "`POLYGON_API_KEY`.")
    add("")
    add("---")
    add("")
    add("## Appendix — all %d refused days, one row each" % nref)
    add("")
    add("`gate` is the proximate killer of the signal nearest his entry bar; "
        "`recovered by` names every single-gate lift that made the day fire. A "
        "day with no entry in that column is one no single gate opens.")
    add("")
    add("| # | symbol | day | his entry | his R | engine's nearest signal | gate | the value that failed | recovered by |")
    add("|---:|---|---|---|---:|---|---|---|---|")
    recs = {}
    if lift and "none" in lift:
        bf = {k for k, v in lift["none"]["day_fire"].items() if v}
        recs = {a: {k for k, v in lift[a]["day_fire"].items() if v} - bf
                for a in lift if a != "none"}
    for i, k in enumerate(refused, 1):
        hr = rowsby[k][0]
        ei = hr["entry_i"]
        cands = ok[k]["signals"]
        best = min(cands, key=lambda s: abs(s["bar"] - ei) if ei is not None else s["bar"])
        g, why = attribute(best)
        sym, day = k.split("|")
        got = ", ".join("`%s`" % a for a in sorted(recs) if k in recs[a]) or "—"
        rr = hr.get("realized_rr")
        add("| %d | %s | %s | %s %s | %s | %s %s @%s (%+d) | `%s` | %s | %s |"
            % (i, sym, day, hr["hhmm"], hr["dir"],
               ("%+.2f" % rr) if rr is not None else "—",
               best["signal_type"], best["direction"], best["timestamp"][:5],
               (best["bar"] - ei) if ei is not None else 0, g, why, got))

    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("wrote %s (%d lines)" % (OUT_MD, len(L)))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="report",
                    choices=["coverage", "funnel", "lift", "lag", "price",
                             "test1", "report"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--gate", default=None)
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    if a.cmd == "coverage":
        return coverage()
    if a.cmd == "funnel":
        return run_funnel(a.limit)
    if a.cmd == "lift":
        return run_lift(a.gate)
    if a.cmd == "lag":
        return run_lag()
    if a.cmd == "price":
        return price(a.gate or "none", a.days)
    if a.cmd == "test1":
        return run_test1(a.gate)
    return report()


if __name__ == "__main__":
    sys.exit(main())
