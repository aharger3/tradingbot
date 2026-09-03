"""g100_universe_ev_sweep.py -- universe slice sweep, headlined in EV/R per
Austin's 2026-09-03 ruling (pass ONE prop evaluation within 12 months; EV/R
is THE headline, $/day is a supporting row).

Read-only measurement over the committed book
(research/bt2y_trades_retest_on.json, 498 sessions, honest close-fill,
first-of-day arrival order). Scores research/omen_metrics.py::ev_r_scoreboard
and evaluate_prop_challenge() per universe slice:

  full 28 | index only (QQQ/SPY/IWM) | QQQ+SPY | equities only (MAJOR_15,
  universe.py's own equity pool) | core tier (CORE_SYMBOLS) | experimental
  tier (EXPERIMENTAL_SYMBOLS) | top-5 by EV/R | bottom-5 by EV/R

For each slice: restrict the book to that symbol set FIRST, then rebuild the
first-of-day arrival arm within that restricted set (a different universe
changes which candidate is "first" on a given day -- this is not the
full-book first-of-day arm filtered after the fact). Score EV/R, then sweep
risk-per-trade against the $50k prop eval at Austin's stated defaults to find
the best PASS, or report which rule breaks and where.

    python research/g100_universe_ev_sweep.py
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research.omen_metrics import (
    ev_r_scoreboard, evaluate_prop_challenge, first_of_day_arm,
    BOOK_PATH, MIN_RISK_FLOOR_SOURCE, _row_is_sizeable,
)
from universe import (
    INDEX_POOL, MAJOR_15, CORE_SYMBOLS, EXPERIMENTAL_SYMBOLS,
)

RISK_LEVELS = (100, 150, 200, 250, 300, 500, 750, 1000, 2000, 5000)
ACCOUNT_SIZE = 50000.0


def restrict(rows, symbols):
    syms = set(symbols)
    return [r for r in rows if r["sym"] in syms]


def per_symbol_ev(rows, all_syms, min_n=1):
    """EV/R per symbol on that symbol's own first-of-day-eligible fired
    trades (fired-and-traded or halted rows for that symbol alone, not
    re-competed against other symbols -- this answers 'how good are this
    symbol's own signals', which is what a top/bottom cut over EV/R means).
    """
    out = {}
    for sym in all_syms:
        sym_rows = [r for r in rows if r["sym"] == sym and
                    ((r["status"] == "fired" and r.get("traded")) or r["status"] == "halted")]
        sb = ev_r_scoreboard(sym_rows, risk_dollars=1000.0)
        if sb["n"] >= min_n:
            out[sym] = sb
    return out


def best_prop_pass(daily_r_rows, sessions):
    """Sweep risk/trade; return the richest PASS (highest $/trade that still
    passes) or, if none pass, the FAIL at $ (the level Austin cares about
    to size against -- report the fail nearest the size the edge could
    plausibly support: try in ascending order, report first FAIL reason at
    a representative level and note none passed)."""
    results = []
    for risk in RISK_LEVELS:
        daily = [(r["day"], r["r"] * risk) for r in daily_r_rows]
        res = evaluate_prop_challenge(daily, account_size=ACCOUNT_SIZE)
        results.append((risk, res))
    passes = [r for r in results if r[1]["passed"]]
    if passes:
        best = max(passes, key=lambda x: x[0])
        return "PASS", best[0], best[1], results
    # no pass -- report the failure at $500/trade as representative, since
    # that is the size a ~0 EV/R book can sometimes still survive on
    rep = next((r for r in results if r[0] == 500), results[len(results) // 2])
    return "FAIL", rep[0], rep[1], results


def score_slice(name, rows, symbols, sessions):
    sub_rows = restrict(rows, symbols)
    firsts = first_of_day_arm(sub_rows)
    sb = ev_r_scoreboard(firsts, risk_dollars=1000.0, sessions=sessions)
    # The prop-eval equity curve MUST use the same size-gated stream as the
    # EV/R headline -- omen_metrics.main()'s own reference table builds the
    # daily curve straight off `firsts` with no gate, which lets rows with
    # |entry-stop| below min_risk_floor (arithmetic, not money, per CLAUDE.md)
    # into the trailing-drawdown/daily-loss walk. That inflated two arms in
    # this sweep's first pass (index_only and QQQ+SPY both "PASSED" ungated,
    # at $150-250/trade) -- gating them out flips both back to FAIL at every
    # tested level. Never feed an unsized row into the prop-eval curve.
    sizeable_firsts = [r for r in firsts if _row_is_sizeable(r)]
    verdict, risk, res, all_results = best_prop_pass(sizeable_firsts, sessions)
    return {
        "slice": name,
        "symbols": sorted(symbols),
        "n_symbols": len(symbols),
        "n_days_with_first": len(firsts),
        "n_sizeable_for_prop_eval": len(sizeable_firsts),
        "scoreboard": sb,
        "prop_eval": {
            "verdict": verdict,
            "risk_per_trade_shown": risk,
            "result": res,
        },
        "prop_eval_all_levels": [
            {"risk": rk, "passed": rr["passed"], "fail_reason": rr["fail_reason"],
             "final_equity_pct": rr["final_equity_pct"],
             "max_drawdown_seen_pct": rr["max_drawdown_seen_pct"]}
            for rk, rr in all_results
        ],
    }


def main():
    print("min_risk_floor source: %s\n" % MIN_RISK_FLOOR_SOURCE)
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    sessions = meta.get("sessions") or len({r["day"] for r in rows})
    all_syms = meta["symbols"]
    print("book: %d sessions, %d symbols, %d rows, %d fired-and-traded"
          % (sessions, len(all_syms), len(rows), meta["traded"]))

    # per-symbol EV/R for the top/bottom-5 cut
    per_sym = per_symbol_ev(rows, all_syms, min_n=1)
    ranked = sorted(per_sym.items(), key=lambda kv: kv[1]["ev_r"])
    print("\nper-symbol EV/R (own fired signals, n>=1), low to high:")
    for sym, sb in ranked:
        print("  %-6s ev_r=%7.4f  n=%-4d win=%s  dd=%s" %
              (sym, sb["ev_r"], sb["n"], sb["win_rate"], sb["max_drawdown_R"]))

    MIN_N_FOR_RANK = 20  # universe.py MIN_SAMPLE_N -- below this a symbol's
    # EV/R is noise, not signal; rank only symbols that clear it
    rankable = [(s, sb) for s, sb in ranked if sb["n"] >= MIN_N_FOR_RANK]
    print("\n%d of %d symbols clear MIN_SAMPLE_N=%d for top/bottom ranking"
          % (len(rankable), len(ranked), MIN_N_FOR_RANK))
    bottom5 = [s for s, _ in rankable[:5]]
    top5 = [s for s, _ in rankable[-5:]]
    print("  top-5 by EV/R (n>=20):    %s" % top5)
    print("  bottom-5 by EV/R (n>=20): %s" % bottom5)

    slices = [
        ("full_28", all_syms),
        ("index_only_QQQ_SPY_IWM", INDEX_POOL),
        ("QQQ_SPY_only", ["QQQ", "SPY"]),
        ("equities_only_MAJOR_15", [s for s in MAJOR_15 if s in all_syms]),
        ("core_tier", [s for s in CORE_SYMBOLS if s in all_syms]),
        ("experimental_tier", [s for s in EXPERIMENTAL_SYMBOLS if s in all_syms]),
        ("top5_by_evr_n20", top5),
        ("bottom5_by_evr_n20", bottom5),
    ]

    out = []
    print("\n%s\n=== SLICE SWEEP (%d arms) -- headline is EV/R, $/day is supporting ===\n%s"
          % ("=" * 78, len(slices), "=" * 78))
    for name, syms in slices:
        if not syms:
            print("\n[%s] SKIPPED -- empty symbol set" % name)
            continue
        result = score_slice(name, rows, syms, sessions)
        out.append(result)
        sb = result["scoreboard"]
        pe = result["prop_eval"]
        print("\n[%s]  (%d symbols: %s)" % (name, len(syms), ",".join(sorted(syms))))
        print("  n_days_first=%-4d  EV/R=%-8s win=%-7s avg_win_R=%-7s avg_loss_R=%-7s pf=%-7s"
              % (result["n_days_with_first"], sb["ev_r"], sb["win_rate"],
                 sb["avg_win_R"], sb["avg_loss_R"], sb["profit_factor"]))
        print("  total_R=%-8s yearly_R=%-8s max_dd_R=%-8s months_green=%-8s $/day=%s"
              % (sb["total_R"], sb["yearly_R"], sb["max_drawdown_R"], sb["months_green"],
                 sb["expectancy_per_day"]))
        print("  n_dropped_size_gate=%d (of n_input=%d)  n_sizeable_for_prop_eval=%d"
              % (sb["n_dropped_size_gate"], sb["n_input"], result["n_sizeable_for_prop_eval"]))
        print("  prop-eval (size-gated): best=%s at $%s/trade -- fail_reason=%s final_eq%%=%.1f dd%%=%.1f"
              % (pe["verdict"], pe["risk_per_trade_shown"], pe["result"]["fail_reason"],
                 pe["result"]["final_equity_pct"], pe["result"]["max_drawdown_seen_pct"]))

    with open(os.path.join(HERE, "g100_universe_ev_sweep.json"), "w", encoding="utf-8") as f:
        json.dump({
            "book": os.path.basename(BOOK_PATH),
            "sessions": sessions,
            "min_risk_floor_source": MIN_RISK_FLOOR_SOURCE,
            "per_symbol_ev": {s: sb for s, sb in ranked},
            "top5_by_evr_n20": top5,
            "bottom5_by_evr_n20": bottom5,
            "slices": out,
        }, f, indent=2)
    print("\nwrote research/g100_universe_ev_sweep.json")


if __name__ == "__main__":
    main()
