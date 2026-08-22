"""omen-3.9 T8: S-only vs today's trading set, side by side.

Read-only measurement (no engine change). Replays the engine's OWN
detect_signals bar-by-bar over a fixed backtest window drawn from data_archive
(the same source `research/t4_engine_recall.py` uses — yfinance is dead for
OMEN), then for every deduped entry the engine would TAKE today:

  - computes austin_tier (S/A/C) via `compute_austin_tier`, maintaining the
    per-session `_fired_ideas` set exactly as SignalRunner._route does on the
    accept path, under BOTH arms of the clause-4 switch
    (HTF_OPPOSITION_VETO = "hard"  -> today's rule
                          "fill_override" -> the unsettled alternative);
  - simulates the outcome (binary 2R target vs stop, scratch at EOD — the
    default backtest_week path with RULE6 / LADDER / SSCORE all OFF, exactly
    today's shipped config) on the remaining intraday bars.

Two arms are cut from the SAME detection replay (S-only is a strict subset of
the all-grades set: austin_tier is reported-only and never routes, so the set of
taken trades is identical; only which arm a trade falls into changes):

  all_grades  - every fired entry (today's trading set: _SKIP_GRADES=("X","D"),
                i.e. A+/A/B/C all trade, exactly as shipped)
  s_only      - fired entries whose tier under "hard" == "S"

The 84% re-entry is NOT armed (detection-only replay, like the recall gate); it
needs a stopped prior trade's session state, which this replay does not carry.
That matches the detection set `research/regression_gate.py` already gates.

Also computes, on the v3 corpus (`austin_marks_v3.jsonl`, 184 marks / 77 S):
the S-grade FIRED recall (engine fired entry within +/-2 bars of an S mark) vs
the v2 baseline 10/77 = 13.0%, reusing t4_engine_recall's join.

Outputs a JSON summary to stdout. Does NOT touch signal_runner.py (TRADE_S_ONLY
stays False; HTF_OPPOSITION_VETO is restored to "hard" on exit).
"""
from __future__ import annotations
import json, os, sys, glob
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import t4_engine_recall as t4
import signal_runner as sr
from omen_bot import SignalType
from signal_runner import compute_austin_tier, idea_key

RISK_DOLLARS = 1000.0
DEDUPE_BARS = t4.DEDUPE_BARS
ENTRY_CUTOFF = t4.ENTRY_CUTOFF
TOL = t4.TOL
# Measurable priority-pool symbols (config.yaml: index 3 + equity 14, minus the
# 2 with no data_archive: SPCX, HTZ) = 15 symbols Austin actually trades.
# Derived from disk, not hand-maintained (OMEN 6 ticket 14). The old hardcoded
# list still carried MSTR (retired 2026-07-11) and omitted ACHR, fully archived
# since 2026-08-10 -- so a backfill silently failed to reach this headline.
from universe import archived_symbols, INDEX_POOL, MAJOR_15
WINDOW_SYMBOLS = archived_symbols(INDEX_POOL + MAJOR_15)


def _tier(sig, candles_upto, fired_ideas, htf_bias, mode):
    """compute_austin_tier with clause 4 read through `mode`."""
    sr.HTF_OPPOSITION_VETO = mode
    return compute_austin_tier(sig, candles_upto, fired_ideas, htf_bias)


def simulate_outcome(direction, entry, stop, target, candles, start_i):
    """Binary 2R path (RULE6/LADDER off = today's shipped default). Stop wins
    ties in a single bar (matches backtest_week.simulate_day). Returns
    (outcome, exit_price, r_mult)."""
    sign = 1.0 if direction == "call" else -1.0
    risk = abs(entry - stop)
    if risk <= 0:
        return "scratch", candles[-1].close, 0.0
    for j in range(start_i + 1, len(candles)):
        c = candles[j]
        if direction == "call":
            stopped, targeted = c.low <= stop, c.high >= target
        else:
            stopped, targeted = c.high >= stop, c.low <= target
        if stopped and targeted:
            return "loss", stop, -1.0
        if stopped:
            return "loss", stop, -1.0
        if targeted:
            r = sign * (target - entry) / risk
            return "win", target, round(r, 4)
    # EOD scratch at last close
    r = sign * (candles[-1].close - entry) / risk
    return "scratch", candles[-1].close, round(r, 4)


def run_window():
    """One detection replay over every archived day for WINDOW_SYMBOLS.
    Returns list of trade dicts (the all-grades set; each carries tier_hard and
    tier_fill so both arms are cut from it)."""
    trades = []
    for sym in WINDOW_SYMBOLS:
        files = sorted(glob.glob(os.path.join(t4.levels.ARCHIVE, sym, "*.csv")))
        days = [os.path.basename(f)[:-4] for f in files]
        for day in days:
            candles = t4.rth_candles(sym, day)
            if not candles:
                continue
            pdh, pdl, pdo, pdc = t4.prior_day_levels(sym, day)
            pmh, pml = t4.premarket_extremes(sym, day)
            runner = t4.CaptureRunner(sym)
            runner.pdh, runner.pdl = pdh, pdl
            runner.pmh, runner.pml = pmh, pml
            runner.pd_open, runner.pd_close = pdo, pdc
            bias = t4.htf_bias(sym, day)
            runner.htf_bias = bias
            runner.qqq_breaks = None
            fired_ideas = set()      # mirrors _route's accept-path bookkeeping
            seen = {}                # 30-bar dedupe (matches run_day / simulate_day)
            for i in range(5, len(candles)):
                c = candles[i]
                if ENTRY_CUTOFF and c.timestamp >= ENTRY_CUTOFF:
                    continue
                runner.candles = candles[: i + 1]
                before = len(runner.captured)
                runner.detect_signals()
                for sig in runner.captured[before:]:
                    if sig.get("status") != "fired":
                        continue  # D-grade / tight-stop-C not accepted, no bookkeeping
                    # engine accept-path bookkeeping happens for EVERY fired sig,
                    # even ones the 30-bar dedupe will suppress (mirrors _route).
                    # Tier uses fired_ideas BEFORE this sig's idea is added.
                    upto = candles[: i + 1]
                    tier_hard = _tier(sig, upto, fired_ideas, bias, "hard")
                    tier_fill = _tier(sig, upto, fired_ideas, bias, "fill_override")
                    ik = idea_key(sig)
                    # dedupe key (matches run_day: stop_level_name for B&R else round(stop,2))
                    idea = (sig.get("stop_level_name")
                            if sig["signal_type"].value == "break_and_retest"
                            else round(sig["stop"], 2))
                    key = (sig["signal_type"].value, sig["direction"], idea)
                    fired_ideas.add(ik)   # accept-path: AFTER tier, for ALL fired
                    if key in seen and i - seen[key] < DEDUPE_BARS:
                        seen[key] = i
                        continue
                    seen[key] = i
                    risk = abs(sig["entry"] - sig["stop"])
                    target = sig.get("target") or (
                        sig["entry"] + 2 * risk if sig["direction"] == "call"
                        else sig["entry"] - 2 * risk)
                    outcome, exit_price, r_mult = simulate_outcome(
                        sig["direction"], sig["entry"], sig["stop"], target,
                        candles, i)
                    trades.append({
                        "symbol": sym, "day": day, "bar": i,
                        "signal_type": sig["signal_type"].value,
                        "direction": sig["direction"], "grade": sig["grade"],
                        "entry": sig["entry"], "stop": sig["stop"],
                        "target": target, "outcome": outcome,
                        "exit_price": exit_price, "r_mult": r_mult,
                        "pnl": round(r_mult * RISK_DOLLARS, 2),
                        "tier_hard": tier_hard, "tier_fill": tier_fill,
                    })
    sr.HTF_OPPOSITION_VETO = "hard"   # restore today's rule
    return trades


def arm_stats(trades):
    n = len(trades)
    wins = sum(1 for t in trades if t["outcome"] == "win")
    losses = sum(1 for t in trades if t["outcome"] == "loss")
    scr = n - wins - losses
    decided = wins + losses
    wr = round(wins / decided * 100, 1) if decided else 0.0
    exp_r = round(sum(t["r_mult"] for t in trades) / n, 4) if n else 0.0
    pnl = round(sum(t["pnl"] for t in trades), 2)
    return {"trades": n, "wins": wins, "losses": losses, "scratches": scr,
            "win_rate_pct": wr, "expectancy_R": exp_r, "total_pnl": pnl}


def s_fired_recall_v3():
    """S-grade fired recall on the v3 corpus: of the 77 S marks, how many have
    an engine fired entry within +/-2 bars. Reuses t4.run_day's detection."""
    marks = [json.loads(l) for l in open(os.path.join(HERE, "austin_marks_v3.jsonl"))
             if l.strip()]
    by_pair = {}
    for m in marks:
        by_pair.setdefault((m["symbol"], m["day"]), []).append(m)
    fired_bars = {}
    testable = {"S": 0}
    for (sym, day), ms in by_pair.items():
        ent, sigs, raw = t4.run_day(sym, day)
        if ent is None:
            continue
        fired_bars[(sym, day)] = [e["bar"] for e in ent]
    s_total = sum(1 for m in marks if m["tier"] == "S")
    s_testable = 0
    s_fired = 0
    for m in marks:
        if m["tier"] != "S":
            continue
        key = (m["symbol"], m["day"])
        if key in fired_bars:
            s_testable += 1
            if any(abs(b - m["entry_i"]) <= TOL for b in fired_bars[key]):
                s_fired += 1
    return s_fired, s_total, s_testable


def main():
    s_fired, s_total, s_testable = s_fired_recall_v3()
    trades = run_window()
    allgrades = arm_stats(trades)
    s_only = arm_stats([t for t in trades if t["tier_hard"] == "S"])
    htf_hard_S = sum(1 for t in trades if t["tier_hard"] == "S")
    htf_fill_override_S = sum(1 for t in trades if t["tier_fill"] == "S")
    # per-setup breakdown of S-only, for context
    s_by_setup = dict(Counter(t["signal_type"] for t in trades if t["tier_hard"] == "S"))
    out = {
        "s_fired_recall_v3": f"{s_fired}/{s_total}",
        "s_fired_recall_v3_testable": f"{s_fired}/{s_testable}",
        "v2_baseline_recall": "10/77 = 13.0%",
        "window_symbols": len(WINDOW_SYMBOLS),
        "window_day_runs": len(trades) and sum(1 for _ in trades) or 0,
        "all_grades": allgrades,
        "s_only": s_only,
        "s_only_trades": s_only["trades"],
        "htf_hard_S": htf_hard_S,
        "htf_fill_override_S": htf_fill_override_S,
        "s_only_by_setup": s_by_setup,
        "TRADE_S_ONLY": sr.TRADE_S_ONLY,
        "HTF_OPPOSITION_VETO": sr.HTF_OPPOSITION_VETO,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
