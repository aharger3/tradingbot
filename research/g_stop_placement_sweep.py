"""g_stop_placement_sweep.py -- stop VARIANT sweep, headline in EV/R.

Austin, 2026-09-03: EV/R is the headline everywhere, $/day is a supporting
row. The bar is passing a prop evaluation, not a dollar figure. R1 is law:
the level stop is final and MAX LOSS IS -1R HARD (no -1.25R floor). That
rule is applied identically to every variant below -- changing the stop's
PLACEMENT changes the risk denominator (and therefore whether a bar's close
crosses it, and what R-multiple a target-hit becomes), but a genuine
stop-out is always scored at exactly -1.0R, never worse, by construction.

Six stop-placement families, all held against the SAME entry, SAME target
price and SAME bars as the shipped book -- only the stop moves, so this
isolates stop placement as the one variable under test:

  shipped_level        the committed book's own stop (== level_px), control
  entry_candle_extreme low/high of the signal (entry) candle itself
  prior_candle_extreme low/high of the candle immediately before entry
  ocr_far_edge         the One-Candle-Rule candle's far edge (downgrade.find_ocr)
  atr_Nx               N x a 14-bar causal ATR off entry, N in (0.5, 1.0, 1.5, 2.0)
  fixed_pct_P          entry x P%, P in (0.10, 0.25, 0.50, 1.00)

Population: the book's own 4,022 traded rows (status fired, traded=True),
resimulated bar-by-bar from entry_i+1 -- causal, no look-ahead -- against
the committed bar archive (research/g80_ordertype_grid.py::day_pack,
cache-first, read-only). backtest_week.py / stop_rule.py / live_scanner.py
are mid-edit tonight and their current ladder (BE moves, scale-outs, the
R2 entry-candle-return rule) is deliberately NOT reproduced here: this rig
answers "where should the stop sit", nothing else. The shipped_level arm is
resimulated through the identical mechanism as every other arm (not read
off the book's own `r` column) so the comparison stays like-for-like; it is
checked against the book's own numbers as a sanity footnote, not assumed
equal.

Per-bar resolution, in order (rules from CLAUDE.md / Austin's ruling):
  1. stop fires on the bar's CLOSE (STOP_ON_CLOSE convention already shipped)
  2. target fires on intrabar TOUCH (book stamp: TARGET_ON_CLOSE=false)
  3. a bar that touches both goes to the STOP (within-bar order is unknowable
     on 1-minute OHLC)
  4. a stop-out is scored at exactly -1.0R, never worse (R1, "hard")
  5. no hit by end of session -> EOD scratch at the last bar's close

    python research/g_stop_placement_sweep.py
"""
import json
import os
import sys
import time
import importlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research.omen_metrics import (ev_r_scoreboard, evaluate_prop_challenge,
                                    min_risk_floor, first_of_day_arm,
                                    MIN_RISK_FLOOR_SOURCE, BOOK_PATH)

RISK_DOLLARS = 1000.0


def _import_with_retry(modname, what):
    """backtest_week.py / stop_rule.py / live_scanner.py / test_runner_stop.py
    are mid-edit tonight. g80_ordertype_grid imports backtest_week at module
    load; if that transiently fails to parse, wait once and retry rather than
    treating it as broken (Austin's instruction, this round)."""
    for attempt in range(2):
        try:
            importlib.invalidate_caches()
            return importlib.import_module(modname)
        except Exception as e:
            if attempt == 0:
                print("  (%s import failed, retrying once in 2s: %r)" % (what, e))
                time.sleep(2)
                continue
            raise


g80 = _import_with_retry("research.g80_ordertype_grid", "g80_ordertype_grid")
dg = _import_with_retry("research.downgrade", "downgrade")

day_pack = g80.day_pack
find_ocr = dg.find_ocr

ATR_LOOKBACK = 14
ATR_MULTIPLES = (0.5, 1.0, 1.5, 2.0)
FIXED_PCTS = (0.0010, 0.0025, 0.0050, 0.0100)


def _dict_bars(bars):
    return [{"o": c.open, "h": c.high, "l": c.low, "c": c.close} for c in bars]


def _causal_atr(bars, entry_i, lookback=ATR_LOOKBACK):
    """Mean 1m true range over up to `lookback` bars ending at entry_i
    (inclusive) -- causal, uses nothing at or after the decision is unneeded
    for entry (entry itself is already known/filled by entry_i)."""
    lo = max(0, entry_i - lookback + 1)
    window = bars[lo:entry_i + 1]
    if not window:
        return None
    trs = [c.high - c.low for c in window]
    return sum(trs) / len(trs)


# ---------------------------------------------------------------------------
# stop-placement variants: each returns (stop_price, reason_if_unshippable)
# ---------------------------------------------------------------------------

def variant_shipped(row, bars, entry_i, entry, is_long):
    return row["level_px"], None


def variant_entry_candle(row, bars, entry_i, entry, is_long):
    c = bars[entry_i]
    return (c.low if is_long else c.high), None


def variant_prior_candle(row, bars, entry_i, entry, is_long):
    if entry_i < 1:
        return None, "no_prior_bar"
    c = bars[entry_i - 1]
    return (c.low if is_long else c.high), None


def variant_ocr(row, bars, entry_i, entry, is_long):
    dbars = _dict_bars(bars[:entry_i + 1])
    j = find_ocr(dbars, entry_i, is_long)
    if j is None:
        return None, "no_ocr_in_lookback"
    edge = dbars[j]["l"] if is_long else dbars[j]["h"]
    usable = (edge <= entry) if is_long else (edge >= entry)
    if not usable:
        return None, "ocr_wrong_side"
    return edge, None


def _make_atr_variant(mult):
    def f(row, bars, entry_i, entry, is_long):
        atr = _causal_atr(bars, entry_i)
        if not atr or atr <= 0:
            return None, "no_atr"
        return (entry - mult * atr) if is_long else (entry + mult * atr), None
    f.__name__ = "atr_%sx" % mult
    return f


def _make_pct_variant(pct):
    def f(row, bars, entry_i, entry, is_long):
        return (entry * (1 - pct)) if is_long else (entry * (1 + pct)), None
    f.__name__ = "fixed_pct_%.2f" % (pct * 100)
    return f


VARIANTS = [("shipped_level", variant_shipped),
            ("entry_candle_extreme", variant_entry_candle),
            ("prior_candle_extreme", variant_prior_candle),
            ("ocr_far_edge", variant_ocr)]
VARIANTS += [("atr_%sx" % m, _make_atr_variant(m)) for m in ATR_MULTIPLES]
VARIANTS += [("fixed_pct_%.2f" % (p * 100), _make_pct_variant(p)) for p in FIXED_PCTS]


# ---------------------------------------------------------------------------
# resimulation
# ---------------------------------------------------------------------------

def resim_one(row, bars, variant_fn):
    """Returns a dict (day/r/pnl/entry/stop/out) or None with a reason string
    when the row is unshippable / untradeable under this variant."""
    entry_i = row["entry_i"]
    if entry_i >= len(bars):
        return None, "entry_i_out_of_range"
    entry = row["entry"]
    is_long = row["dir"] == "call"
    target = row["target"]

    stop, reason = variant_fn(row, bars, entry_i, entry, is_long)
    if stop is None:
        return None, reason
    risk = abs(entry - stop)
    if risk <= 1e-9:
        return None, "zero_risk"
    # wrong-side guard: a "stop" that sits on the wrong side of entry is not
    # a stop (only reachable for atr/pct if someone mis-signs mult/pct, kept
    # as a hard guard rather than trusting the formula)
    if is_long and stop >= entry:
        return None, "stop_wrong_side"
    if (not is_long) and stop <= entry:
        return None, "stop_wrong_side"
    if risk < min_risk_floor(entry):
        return None, "below_min_risk_floor"

    out = None
    exit_px = None
    for j in range(entry_i + 1, len(bars)):
        c = bars[j]
        stop_hit = (c.close <= stop) if is_long else (c.close >= stop)
        target_hit = (c.high >= target) if is_long else (c.low <= target)
        if stop_hit and target_hit:
            out, exit_px = "stop", stop
            break
        if stop_hit:
            out, exit_px = "stop", stop
            break
        if target_hit:
            out, exit_px = "target", target
            break
    if out is None:
        out, exit_px = "scratch", bars[-1].close

    if out == "stop":
        r = -1.0                      # R1: hard floor, never worse
    else:
        r = (exit_px - entry) / risk if is_long else (entry - exit_px) / risk

    return {"day": row["day"], "et": row["et"], "sym": row["sym"],
            "entry": entry, "stop": round(stop, 4), "target": target,
            "exit": round(exit_px, 4), "out": out,
            "r": round(r, 6), "pnl": round(r * RISK_DOLLARS, 2),
            "risk": round(risk, 4)}, None


_bar_cache = {}


def get_bars(sym, day):
    k = (sym, day)
    if k not in _bar_cache:
        bars, *_ = day_pack(sym, day)
        _bar_cache[k] = bars
    return _bar_cache[k]


def run_sweep():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    sessions = meta.get("sessions") or len({r["day"] for r in rows})
    traded = [r for r in rows if r["status"] == "fired" and r.get("traded")]
    firsts_pop = first_of_day_arm(rows)   # same one-a-day population as omen_metrics

    print("population: %d traded rows, %d first-of-day rows, %d sessions\n"
          % (len(traded), len(firsts_pop), sessions))
    print("min_risk_floor source: %s\n" % MIN_RISK_FLOOR_SOURCE)

    results = {}   # variant_name -> {"traded": [...], "firsts": [...], "reasons": Counter, "n_bad_bars": int}
    for name, fn in VARIANTS:
        results[name] = {"traded": [], "firsts": [], "reasons": defaultdict(int), "n_bad_bars": 0}

    t0 = time.time()
    for idx, row in enumerate(traded):
        bars = get_bars(row["sym"], row["day"])
        if not bars:
            for name, _ in VARIANTS:
                results[name]["n_bad_bars"] += 1
            continue
        for name, fn in VARIANTS:
            rec, reason = resim_one(row, bars, fn)
            if rec is None:
                results[name]["reasons"][reason] += 1
            else:
                results[name]["traded"].append(rec)
        if (idx + 1) % 1000 == 0:
            print("  ... %d/%d traded rows resimulated (%.1fs)" %
                  (idx + 1, len(traded), time.time() - t0))

    for row in firsts_pop:
        bars = get_bars(row["sym"], row["day"])
        if not bars:
            continue
        for name, fn in VARIANTS:
            rec, reason = resim_one(row, bars, fn)
            if rec is not None:
                results[name]["firsts"].append(rec)

    print("resim done in %.1fs\n" % (time.time() - t0))
    return meta, sessions, traded, firsts_pop, results


def main():
    meta, sessions, traded, firsts_pop, results = run_sweep()

    print("=" * 100)
    print("ARM COUNT: %d stop-placement variants tested" % len(VARIANTS))
    print("=" * 100)

    header = ("%-24s %8s %8s %7s %8s %8s %8s %8s %8s %10s" %
              ("variant", "n", "n_drop", "ev_r", "win%", "avg_win", "avg_loss",
               "PF", "stop%", "yearly_R"))
    print("\n--- ALL TRADED ROWS (n_input=%d), EV/R headline ---" % len(traded))
    print(header)
    for name, _ in VARIANTS:
        d = results[name]
        trs = d["traded"]
        sb = ev_r_scoreboard(trs, risk_dollars=RISK_DOLLARS, sessions=sessions)
        n_stop = sum(1 for t in trs if t["out"] == "stop")
        stop_pct = (100.0 * n_stop / len(trs)) if trs else None
        n_unshippable = sum(d["reasons"].values()) + d["n_bad_bars"]
        print("%-24s %8s %8s %7s %8s %8s %8s %8s %8s %10s" % (
            name, sb["n"], n_unshippable,
            sb["ev_r"], sb["win_rate"], sb["avg_win_R"], sb["avg_loss_R"],
            sb["profit_factor"], ("%.1f" % stop_pct if stop_pct is not None else "-"),
            sb["yearly_R"]))

    print("\n  unshippable-reason breakdown (all-traded population):")
    for name, _ in VARIANTS:
        d = results[name]
        if d["reasons"] or d["n_bad_bars"]:
            parts = ["%s=%d" % (k, v) for k, v in sorted(d["reasons"].items(), key=lambda kv: -kv[1])]
            if d["n_bad_bars"]:
                parts.append("bad_bars=%d" % d["n_bad_bars"])
            print("    %-24s %s" % (name, ", ".join(parts)))

    # sanity footnote: shipped_level resim vs the book's own numbers
    book_traded_r = [t["r"] for t in traded]
    book_sb = ev_r_scoreboard([{"r": r, "day": rw["day"]} for r, rw in zip(book_traded_r, traded)],
                               risk_dollars=RISK_DOLLARS, sessions=sessions, size_gate=False)
    resim_sb = ev_r_scoreboard(results["shipped_level"]["traded"], risk_dollars=RISK_DOLLARS,
                                sessions=sessions)
    print("\n  sanity: book's own ev_r=%.4f (n=%d, no R2/BE/scale-out) vs this rig's "
          "shipped_level resim ev_r=%s (n=%s) -- expected to differ (R2 entry-candle-return, "
          "BE-to-entry, and F1 scale-out are the shipped ladder's, not reproduced here)."
          % (book_sb["ev_r"], book_sb["n"], resim_sb["ev_r"], resim_sb["n"]))

    print("\n" + "=" * 100)
    print("--- FIRST-OF-DAY ARM (%d candidate days), EV/R + prop-eval $50k defaults ---"
          % len(firsts_pop))
    print("=" * 100)
    print(header)
    for name, _ in VARIANTS:
        d = results[name]
        trs = d["firsts"]
        sb = ev_r_scoreboard(trs, risk_dollars=RISK_DOLLARS, sessions=sessions)
        n_stop = sum(1 for t in trs if t["out"] == "stop")
        stop_pct = (100.0 * n_stop / len(trs)) if trs else None
        n_drop = len(firsts_pop) - len(trs)
        print("%-24s %8s %8s %7s %8s %8s %8s %8s %8s %10s" % (
            name, sb["n"], n_drop,
            sb["ev_r"], sb["win_rate"], sb["avg_win_R"], sb["avg_loss_R"],
            sb["profit_factor"], ("%.1f" % stop_pct if stop_pct is not None else "-"),
            sb["yearly_R"]))

    print("\n--- prop-eval PASS/FAIL, first-of-day arm, $50k eval, defaults, several risk/trade ---")
    print("  %-24s %-10s %-6s %-22s %-8s" %
          ("variant", "risk/trade", "PASS?", "fail_reason", "final%"))
    for name, _ in VARIANTS:
        trs = results[name]["firsts"]
        if not trs:
            print("  %-24s %-10s %-6s %-22s" % (name, "-", "-", "no shippable trades"))
            continue
        for risk_per_trade in (100, 250, 500, 1000):
            daily = [(t["day"], t["r"] * risk_per_trade) for t in trs]
            res = evaluate_prop_challenge(daily, account_size=50000.0)
            print("  %-24s $%-9s %-6s %-22s %-8s" % (
                name, risk_per_trade,
                "PASS" if res["passed"] else "FAIL",
                res["fail_reason"] or "-",
                "%.1f" % res["final_equity_pct"]))


if __name__ == "__main__":
    main()
