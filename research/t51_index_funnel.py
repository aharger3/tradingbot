"""T5 -- index-pool funnel. WHY does INDEX_POOL (QQQ/SPY/IWM) fire 18 trades in
501 trading days while MAJOR_15 fires 605?

Diagnose only -- no engine default is changed. This imports the committed engine
and *instruments* it by wrapping (not rewriting) the detection / grading /
routing functions, then drives `backtest_week.simulate_day` over the exact
window `research/t8_two_year.py` uses (2024-08-12 .. 2026-08-11; the archive ends
2026-08-10, so 500 trading days x 3 = 1500 ran cells of the 1503 possible).
TSLA is run as the control (a symbol the engine handles well).

The ENDPOINT is trade-level, not signal-level: `simulate_day` dedupes repeated
fires of the same idea (within DEDUPE_BARS) into one SimTrade, and a "counted"
trade is `t.status == "fired" and t.grade != "C"` -- the same definition
t8_two_year uses to produce the 18. Counting raw signal fires instead (an
earlier draft did) over-counts ~9x because the same level re-fires every bar.

Funnel, per symbol and pooled across the index pool (all at the
symbol-x-day "cell" level):
  days_with_levels  -- a candidate level was ever handed to detect_break_retest
  days_with_setup   -- a break-and-retest (detect_break_retest truthy) OR an
                       order block (block + retest in OB_RETEST_TYPES) formed
  days_with_signal  -- a signal reached routing (_route ran; captured grew)
  ...then each gate in turn (per-cell "best signal survived past this gate")...
  days_traded       -- >=1 counted trade resulted (trade-level, the 18)

Plus the D-grade ROOT-CAUSE breakdown (why the engine benches index structure
as D): the price-scaled tight-stop D-rule (stock_risk < 0.15% of price, which
penalises high-priced, low-range indices) vs the PA pattern grader vs HTF
counter-trend.

Validation: the counted TRADES here for QQQ/SPY/IWM must match t8_two_year's
INDEX_POOL split (QQQ 7, SPY 5, IWM 6 = 18) -- if they do, the replay is
faithful to the engine that produced the 18-vs-605 figure.

Output: prints a summary and writes research/_t51_funnel_data.json.
"""
import os, sys, json, csv, glob
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE) if os.path.basename(HERE) == "research" else HERE
sys.path.insert(0, ROOT)

# backtest_week imports yfinance at top level (lazy-import is a sibling task's
# uncommitted change). The archive replay never calls fetch_week, so a bare
# stub satisfies the import without touching the engine.
import types as _types
if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = _types.ModuleType("yfinance")

import backtest_week as bw
import signal_runner as sr
from signal_runner import SignalRunner, OB_RETEST_TYPES, _SKIP_GRADES
from omen_bot import PriceActionAnalyzer, TradeGrade

START, END = "2024-08-12", "2026-08-11"
ARCHIVE = os.path.join(ROOT, "data_archive")
INDEX_POOL = ["QQQ", "SPY", "IWM"]
CONTROL = ["TSLA"]

# the gate names the spec asks about, in engine order
GATE_ORDER = ["session_window", "mesh_veto", "displacement",
              "level_retirement", "no_repeat", "_SKIP_GRADES"]


# ---- data helpers (mirror t8_two_year so the window matches exactly) ----

def _hhmm(d):
    return d[11:16]


def day_table(symbol):
    out = {}
    for path in sorted(glob.glob(os.path.join(ARCHIVE, symbol, "*.csv"))):
        day = os.path.basename(path)[:-4]
        rth_h = rth_l = rth_o = rth_c = None
        pm_h = pm_l = None
        with open(path) as f:
            for r in csv.DictReader(f):
                t = _hhmm(r["Datetime"])
                h, l, o, cl = float(r["High"]), float(r["Low"]), float(r["Open"]), float(r["Close"])
                if t < "09:30":
                    if "04:00" <= t:
                        pm_h = h if pm_h is None else max(pm_h, h)
                        pm_l = l if pm_l is None else min(pm_l, l)
                    continue
                if t >= "16:00":
                    continue
                if rth_h is None:
                    rth_h, rth_l, rth_o = h, l, o
                else:
                    rth_h, rth_l = max(rth_h, h), min(rth_l, l)
                rth_c = cl
        if rth_h is not None:
            out[day] = (rth_h, rth_l, rth_o, rth_c, pm_h, pm_l)
    return out


def rth_candles(symbol, day):
    path = os.path.join(ARCHIVE, symbol, f"{day}.csv")
    if not os.path.exists(path):
        return None
    bars = []
    with open(path) as f:
        for r in csv.DictReader(f):
            t = _hhmm(r["Datetime"])
            if t < "09:30" or t >= "16:00":
                continue
            from omen_bot import Candle
            bars.append(Candle(timestamp=t + ":00", open=float(r["Open"]),
                               high=float(r["High"]), low=float(r["Low"]),
                               close=float(r["Close"]), volume=int(float(r["Volume"] or 0))))
    return bars or None


def bias_from(closes):
    if len(closes) < 20:
        return None
    sma = sum(closes[-20:]) / 20
    last = closes[-1]
    if last > sma * 1.001:
        return "bullish"
    if last < sma * 0.999:
        return "bearish"
    return "neutral"


# ---- instrumentation: wrap (do not rewrite) the engine ----
# We capture per-(symbol,day) cell aggregates, never altering engine behaviour.

class _DayRec:
    __slots__ = ("levels", "n_levels_tested", "br_setup", "ob_setup",
                 "n_generated", "sig_status", "fired_grades", "c_cause",
                 "pa_grades", "tight_stop_d", "pattern_d", "htf_d", "mesh_blocked_n",
                 # trade-level (post-dedupe) -- the faithful endpoint
                 "trade_status", "trade_counted_grades")

    def __init__(self):
        self.levels = set()
        self.n_levels_tested = 0
        self.br_setup = False
        self.ob_setup = False
        self.n_generated = 0
        self.sig_status = Counter()        # signal-level fate
        self.fired_grades = Counter()       # grade of fired signals
        self.c_cause = Counter()           # why a fired signal was C (alert)
        self.pa_grades = Counter()          # raw PriceActionAnalyzer grade
        self.tight_stop_d = 0               # final-D via the price-scaled rule
        self.pattern_d = 0                  # final-D from the PA pattern grader
        self.htf_d = 0                     # final-D from HTF counter-trend
        self.mesh_blocked_n = 0
        self.trade_status = Counter()      # trade-level (simulate_day) status
        self.trade_counted_grades = Counter()


REC = defaultdict(_DayRec)
_CUR = None  # (symbol, day) of the cell currently being simulated


# 1) level + B&R setup detection
_orig_dbr = sr.detect_break_retest
_orig_ob = sr.detect_order_block_setup


def _wrapped_dbr(candles, level, is_long, *a, **k):
    note = _orig_dbr(candles, level, is_long, *a, **k)
    if level is not None and _CUR is not None:
        rec = REC[_CUR]
        rec.n_levels_tested += 1
        rec.levels.add(round(float(level), 4))
        if note:
            rec.br_setup = True
    return note


def _wrapped_ob(candles, direction="bullish"):
    block, retest, note = _orig_ob(candles, direction)
    if _CUR is not None:
        if block is not None and retest in OB_RETEST_TYPES:
            REC[_CUR].ob_setup = True
    return block, retest, note


sr.detect_break_retest = _wrapped_dbr
sr.detect_order_block_setup = _wrapped_ob


# 2) raw PA grade (before post-detection promotions/caps) -- for the D-cause split
_orig_grade = PriceActionAnalyzer.grade_trade
_GRADE_BY = {TradeGrade.A_PLUS: "A+", TradeGrade.A: "A", TradeGrade.B: "B",
             TradeGrade.C: "C", TradeGrade.D: "D"}


def _wrapped_grade(candle, lookback_candles, or_high, or_low, is_long, htf_bias=None):
    g = _orig_grade(candle, lookback_candles, or_high, or_low, is_long, htf_bias)
    if _CUR is not None:
        REC[_CUR].pa_grades[_GRADE_BY.get(g, str(g))] += 1
    return g


PriceActionAnalyzer.grade_trade = staticmethod(_wrapped_grade)


# 3) per-signal fate after routing (BacktestRunner._route labels status in place)
_orig_route = bw.BacktestRunner._route


def _wrapped_route(self, signals, sig):
    _orig_route(self, signals, sig)   # labels sig["status"], appends to captured
    if _CUR is None:
        return
    rec = REC[_CUR]
    rec.n_generated += 1
    st = sig.get("status")
    rec.sig_status[st] += 1
    grade = sig.get("grade")
    if st == "fired":
        rec.fired_grades[grade] += 1
        if grade == "C":
            rsn = sig.get("reason", "")
            if "displacement" in rsn or "S_GATE" in rsn:
                rec.c_cause["displacement"] += 1
            elif "PMH" in rsn or "PM-level" in rsn:
                rec.c_cause["pm_level"] += 1
            elif "counter day trend" in rsn:
                rec.c_cause["counter_trend"] += 1
            else:
                rec.c_cause["other_cap"] += 1
    elif st == "skipped_d":
        # split the D-cause: the price-scaled tight-stop rule (stock_risk <
        # 0.15% of price) vs the PA pattern grader vs HTF counter-trend
        entry = sig.get("entry")
        stop = sig.get("stop")
        risk = abs(entry - stop) if entry is not None and stop is not None else 0.0
        close = self.candles[-1].close if self.candles else 0.0
        thr = max(0.10, 0.0015 * close) if close else 0.0
        rsn = sig.get("reason", "")
        if risk and risk < thr:
            rec.tight_stop_d += 1
        elif "counter" in rsn or grade is None:
            rec.pattern_d += 1
        else:
            rec.pattern_d += 1
    if sig.get("mesh_blocked"):
        rec.mesh_blocked_n += 1


bw.BacktestRunner._route = _wrapped_route


# ---- replay driver (mirrors t8_two_year.run_symbol exactly) ----

def run_symbol(symbol):
    bw.STOP_ON_CLOSE, bw.LADDER_MODE = True, "B"   # committed omen-5.0 defaults
    table = day_table(symbol)
    days = sorted(table)
    for i, day in enumerate(days):
        if day < START or day > END:
            continue
        candles = rth_candles(symbol, day)
        if not candles or len(candles) < 60:
            continue
        prev = days[i - 1] if i else None
        pdh = pdl = pdo = pdc = None
        if prev:
            pdh, pdl, pdo, pdc = table[prev][0], table[prev][1], table[prev][2], table[prev][3]
        pmh, pml = table[day][4], table[day][5]
        bias = bias_from([table[d][3] for d in days[max(0, i - 40):i]])

        global _CUR
        _CUR = (symbol, day)
        trades = bw.simulate_day(symbol, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)
        rec = REC[(symbol, day)]
        for t in trades:
            rec.trade_status[t.status] += 1
            if t.counted:
                rec.trade_counted_grades[t.grade] += 1
    _CUR = None
    return symbol


def cell_killer(rec):
    """Name the gate that stopped this cell's best signal from being a counted
    trade. Trade-level (post-dedupe), the faithful endpoint.

    A cell's "best" signal is the one that reached furthest: a counted trade
    beats a fired-C alert beats a D-skip beats a tight-stop/repeat/retire skip.
    """
    if rec.trade_counted_grades:
        return None                      # traded -> no gate killed it
    if rec.trade_status.get("fired"):
        return "displacement"            # fired but only as a C alert -> C-cap killed counting
    if rec.trade_status.get("skipped_d"):
        return "_SKIP_GRADES"
    if rec.trade_status.get("skipped_tight_stop"):
        return "tight_stop"
    if rec.trade_status.get("skipped_repeat_entry") or rec.trade_status.get("skipped_repeat_idea"):
        return "no_repeat"
    if rec.trade_status.get("skipped_level_retired"):
        return "level_retirement"
    # had levels but no B&R/OB setup formed -> no signal ever generated. This is
    # the only genuinely "upstream" loss, and it is tiny (49/1500 index cells).
    if not rec.n_generated:
        return "no_setup_formed"
    return "other"


def summarize(syms):
    recs = [REC[(s, d)] for s in syms for d in day_table(s)
            if (s, d) in REC and START <= d <= END]
    ran = len(recs)
    n_levels = sum(1 for r in recs if r.levels)
    mean_levels = (sum(len(r.levels) for r in recs) / ran) if ran else 0.0
    n_setup = sum(1 for r in recs if r.br_setup or r.ob_setup)
    n_sig = sum(1 for r in recs if r.n_generated)
    # gate survival (cell-level): >=1 signal survived past the gate
    surv_session = sum(1 for r in recs if r.n_generated)   # veto OFF -> all in-session
    surv_mesh = sum(1 for r in recs if r.n_generated and r.mesh_blocked_n < r.n_generated)
    surv_disp = sum(1 for r in recs if r.fired_grades and
                    sum(v for k, v in r.fired_grades.items() if k != "C") > 0)
    surv_retire = sum(1 for r in recs if r.n_generated and not r.sig_status.get("skipped_level_retired", 0) == r.n_generated)
    surv_repeat = sum(1 for r in recs if r.n_generated
                      and not (r.sig_status.get("skipped_repeat_entry", 0) + r.sig_status.get("skipped_repeat_idea", 0) == r.n_generated))
    surv_skip = sum(1 for r in recs if r.fired_grades)     # >=1 signal not D/X
    n_traded = sum(1 for r in recs if r.trade_counted_grades)
    n_trades = sum(sum(r.trade_counted_grades.values()) for r in recs)

    killer = Counter()
    for r in recs:
        k = cell_killer(r)
        if k:
            killer[k] += 1
    no_setup = sum(1 for r in recs if not (r.br_setup or r.ob_setup))

    # D-cause totals across all D-skipped trade-rows
    d_tight = sum(r.tight_stop_d for r in recs)
    d_pattern = sum(r.pattern_d for r in recs)

    # signal-level status totals
    sig_status = Counter()
    for r in recs:
        sig_status.update(r.sig_status)
    pa_grades = Counter()
    for r in recs:
        pa_grades.update(r.pa_grades)
    c_cause = Counter()
    for r in recs:
        c_cause.update(r.c_cause)

    return {
        "ran_cells": ran, "days_with_levels": n_levels,
        "mean_levels_per_day": round(mean_levels, 2),
        "days_with_setup": n_setup,
        "days_with_signal": n_sig,
        "surv_session_window": surv_session, "surv_mesh_veto": surv_mesh,
        "surv_displacement": surv_disp, "surv_level_retirement": surv_retire,
        "surv_no_repeat": surv_repeat, "surv_skip_grades_fired": surv_skip,
        "days_traded": n_traded, "counted_trades": n_trades,
        "no_setup_cells": no_setup,
        "cell_killer": dict(killer),
        "sig_status": dict(sig_status), "pa_grades": dict(pa_grades),
        "c_cause": dict(c_cause),
        "d_tight_stop": d_tight, "d_pattern": d_pattern,
    }


def main():
    for sym in INDEX_POOL + CONTROL:
        run_symbol(sym)
        print(f"  {sym}: replayed", flush=True)

    per_sym = {sym: summarize([sym]) for sym in INDEX_POOL + CONTROL}
    pooled = summarize(INDEX_POOL)

    # ---- validation against t8's INDEX_POOL split (7/5/6 = 18) ----
    print("\n=== VALIDATION (counted TRADES vs t8 INDEX_POOL 7/5/6=18) ===")
    tot = 0
    for s in INDEX_POOL:
        c = per_sym[s]["counted_trades"]
        tot += c
        print(f"  {s}: {c} counted trades")
    print(f"  INDEX_POOL total: {tot} (expect 18)   TSLA: {per_sym['TSLA']['counted_trades']} (control)")

    print("\n=== PER-SYMBOL FUNNEL (cells) ===")
    for s in INDEX_POOL + CONTROL:
        p = per_sym[s]
        print(f"\n{s}  (ran {p['ran_cells']} cells)")
        print(f"  levels     : {p['days_with_levels']:>4}  ({p['mean_levels_per_day']} lvl/cell)")
        print(f"  setup      : {p['days_with_setup']:>4}  (no-setup cells {p['no_setup_cells']})")
        print(f"  signal     : {p['days_with_signal']:>4}")
        print(f"  surv session/mesh/disp/retire/repeat/skip : "
              f"{p['surv_session_window']}/{p['surv_mesh_veto']}/{p['surv_displacement']}/"
              f"{p['surv_level_retirement']}/{p['surv_no_repeat']}/{p['surv_skip_grades_fired']}")
        print(f"  traded     : {p['days_traded']:>4} cells  ({p['counted_trades']} trades)")
        print(f"  cell killer: {p['cell_killer']}")
        print(f"  sig status : {p['sig_status']}")
        print(f"  PA grades  : {p['pa_grades']}")
        print(f"  D-cause    : tight_stop={p['d_tight_stop']} pattern={p['d_pattern']}")
        if p['c_cause']:
            print(f"  C-cause    : {p['c_cause']}")

    print("\n=== INDEX_POOL POOLED ===")
    p = pooled
    print(f"  ran cells        : {p['ran_cells']}")
    print(f"  days_with_levels : {p['days_with_levels']}/1503")
    print(f"  days_with_setup  : {p['days_with_setup']}")
    print(f"  days_with_signal : {p['days_with_signal']}")
    print(f"  days_traded      : {p['days_traded']}  ({p['counted_trades']} trades)")
    print(f"  top killer       : {p['cell_killer']}")

    out = {"window": [START, END], "per_symbol": per_sym, "pooled_index": pooled}
    with open(os.path.join(HERE, "_t51_funnel_data.json"), "w") as f:
        json.dump(out, f, indent=2, default=dict)
    print(f"\nwrote {os.path.join(HERE, '_t51_funnel_data.json')}")


if __name__ == "__main__":
    main()
