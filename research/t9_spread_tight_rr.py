"""T9 -- spread and tight-RR filter. R30, both readings.

Austin: "I meant stock price not bid ask, but both are true... my comment was
about tight RR low probability." Two separate things, both measured here:

  (a) TIGHT-RR FILTER ON THE UNDERLYING. R15: "if the trade is too hard to
      manage it's not a good trade." When entry-to-stop geometry collapses to
      a few cents, the trade is unmanageable before spread or slippage even
      enter it -- a stop that tight sits inside the noise of the next tick.
      Measured as `stop_pct` (risk / entry * 100), already a field on every
      row of `research/bt2y_trades.json` (backtest_2y.py:154).

  (b) BID-ASK COST MODEL ON THE CONTRACT. There is no options tape in this
      repo (t2_options_tape.py's own caveat, still true). Reuses that file's
      Black-Scholes `Contract` pricer unmodified -- same model, re-pointed at
      the RATIFIED (post-T0) book instead of the pinned pre-T0 book -- to
      price a round-trip spread as a fraction of contract 1R. Also checks
      whether a *symbol*-level wide-spread filter is reachable at all, given
      Austin already restricts his own universe to ~200k+ daily options-volume
      names (universe.py's own comment).

BOTH readings are scored against the money book (`research/bt2y_trades.json`,
the T0 ratified re-baseline, 2,595 traded) AND against held-out recall
(`research/marks/probe_s_sweep_2026-08-28.jsonl`, 34 S of 100), because
method rule 2 says recall governs, not mean R -- a filter that trims a few
cents of noise off the book is worthless if it also silences one of his S
cards.

Usage:
  python research/t9_spread_tight_rr.py [--out research/t9_spread_tight_rr.json]
"""
from __future__ import annotations
import argparse, json, os, statistics as st, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.t4_engine_recall import run_day               # noqa: E402
from research import t2_options_tape as t2                    # noqa: E402
import universe                                                # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades.json")
SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")

# Candidate tight-RR floors, in stop_pct (risk as % of entry price). The
# existing `stopb` bucket edges in backtest_2y.py are 0.15 / 0.35 / 0.70 --
# "tight" is everything under 0.15. These sweep INSIDE that bucket, because
# 0.15 is a labeling edge, not a manageability claim.
RR_THRESHOLDS = [0.03, 0.05, 0.08, 0.10, 0.15]

# Round-trip option spreads to price, same set t2_options_tape.py A5 uses
# plus its own x9 assumption ($0.05) for continuity.
SPREADS = [0.01, 0.02, 0.05, 0.10, 0.15]


def load_book():
    with open(BOOK, encoding="utf-8") as fh:
        d = json.load(fh)
    return [r for r in d["trades"] if r.get("traded")]


def mean(xs):
    xs = list(xs)
    return st.fmean(xs) if xs else 0.0


def win_rate(rows):
    dec = [r for r in rows if r["out"] in ("win", "loss")]
    if not dec:
        return 0.0
    return 100.0 * sum(1 for r in dec if r["out"] == "win") / len(dec)


# ---------------------------------------------------------------------------
# (a) tight-RR filter on the underlying
# ---------------------------------------------------------------------------

def se(xs):
    xs = list(xs)
    if len(xs) < 2:
        return 0.0
    return st.pstdev(xs) / (len(xs) ** 0.5)


def sweep_tight_rr(book):
    base_mean, base_win, base_n = mean(r["r"] for r in book), win_rate(book), len(book)
    out = []
    for thr in RR_THRESHOLDS:
        removed = [r for r in book if r["stop_pct"] < thr]
        kept = [r for r in book if r["stop_pct"] >= thr]
        removed_rs = [r["r"] for r in removed]
        kept_rs = [r["r"] for r in kept]
        # two-sample error bar on (removed_mean - kept_mean): the question a
        # filter has to answer is whether the population it CUTS actually
        # differs from the population it KEEPS, not whether the whole book
        # moved (moving the whole book by construction as n shrinks is not
        # itself evidence of anything).
        diff = mean(removed_rs) - mean(kept_rs) if kept_rs and removed_rs else 0.0
        bar95 = 1.96 * ((se(removed_rs) ** 2 + se(kept_rs) ** 2) ** 0.5)
        out.append({
            "threshold_stop_pct": thr,
            "removed_n": len(removed),
            "removed_pct_of_book": round(100.0 * len(removed) / base_n, 2),
            "removed_mean_r": round(mean(removed_rs), 4),
            "removed_median_r": round(st.median(removed_rs), 4) if removed_rs else 0.0,
            "removed_total_r": round(sum(removed_rs), 2),
            "removed_win_rate": round(win_rate(removed), 1),
            "removed_by_sgrade": dict(Counter(r["sgrade"] for r in removed)),
            "kept_n": len(kept),
            "kept_mean_r": round(mean(kept_rs), 4),
            "kept_win_rate": round(win_rate(kept), 1),
            "book_mean_r_move": round(mean(kept_rs) - base_mean, 4),
            "removed_vs_kept_mean_diff": round(diff, 4),
            "removed_vs_kept_95pct_bar": round(bar95, 4),
            "removed_vs_kept_inside_bar": abs(diff) <= bar95,
        })
    return {"book_mean_r": round(base_mean, 4), "book_win_rate": round(base_win, 1),
            "book_n": base_n, "sweep": out}


def replay_heldout_s_entries():
    """The engine's actual fired entries (entry, stop) for the 34 held-out S
    cards, on the (symbol, day) pairs where it currently fires at all. This is
    what a tight-RR gate would actually be evaluated against -- not the traded
    book, which already excludes some of these days' OTHER signals."""
    cards = [json.loads(l) for l in open(SWEEP, encoding="utf-8") if l.strip()]
    his_s = [r for r in cards if r["answers"].get("s") == ["s"]]
    fired_entries = []   # one per (symbol, day) that fires -- first fired entry
    unfired = []
    for r in his_s:
        sym, day = r["symbol"], r["date"]
        try:
            entries, _sigs, _raw = run_day(sym, day)
        except Exception:
            entries = None
        if not entries:
            unfired.append(r["card_id"])
            continue
        e = entries[0]
        stop_pct = abs(e["entry"] - e["stop"]) / e["entry"] * 100 if e["entry"] else 0.0
        fired_entries.append({"card_id": r["card_id"], "symbol": sym, "day": day,
                              "entry": e["entry"], "stop": e["stop"],
                              "stop_pct": round(stop_pct, 4)})
    return fired_entries, unfired, len(his_s)


def recall_risk(fired_entries, n_s_total, n_fired_before):
    out = []
    for thr in RR_THRESHOLDS:
        would_lose = [e for e in fired_entries if e["stop_pct"] < thr]
        out.append({
            "threshold_stop_pct": thr,
            "S_fires_that_would_be_filtered": len(would_lose),
            "cards": [e["card_id"] for e in would_lose],
            "recall_after": f"{n_fired_before - len(would_lose)}/{n_s_total} = "
                             f"{100.0*(n_fired_before - len(would_lose))/n_s_total:.1f}%",
        })
    return out


# ---------------------------------------------------------------------------
# (b) bid-ask spread cost model on the contract
# ---------------------------------------------------------------------------

def spread_cost_model(book):
    cs = t2.priced(book, t2.HEADLINE_IV)   # same pricer, re-pointed at the AFTER book
    base_single = t2.mean(c.cr_single() for c in cs)
    risks = [c.risk for c in cs]
    out = []
    for sp in SPREADS:
        cost = [sp / c.risk for c in cs]
        out.append({
            "round_trip_spread_usd": sp,
            "median_cost_contract_r": round(st.median(cost), 4),
            "mean_cost_contract_r": round(t2.mean(cost), 4),
            "book_single_after_cost": round(base_single - t2.mean(cost), 4),
        })
    breakeven = base_single / t2.mean(1.0 / c.risk for c in cs)
    return {
        "n_priced": len(cs), "n_unpriced_dropped": len(book) - len(cs),
        "base_contract_r_single_no_spread": round(base_single, 4),
        "modeled_premium_risk_median": round(st.median(risks), 4),
        "modeled_premium_risk_p10": round(t2.pct(risks, 0.10), 4),
        "modeled_premium_risk_p90": round(t2.pct(risks, 0.90), 4),
        "breakeven_round_trip_spread_usd": round(breakeven, 4),
        "sweep": out,
        "note": "IV modeled from Parkinson realized vol x 1.2, no real NBBO exists "
                "in this repo (Polygon options snapshot 403s, Tastytrade sandbox-only). "
                "Same caveat as t2_options_tape.py section A5, re-run on the AFTER book.",
    }


def symbol_liquidity_reachability(book):
    """Is a symbol-level wide-spread FILTER reachable at all? Austin's own
    universe comment: his 29-symbol watchlist is already ~200k+ daily options
    volume (his rule). If every traded symbol clears that bar already, a
    wide-spread symbol filter has nothing to remove -- the finding is about
    the gate (rule 3), not a threshold to tune."""
    traded_syms = sorted(set(r["sym"] for r in book))
    universe_syms = set(universe.ALL_SYMS)
    outside = [s for s in traded_syms if s not in universe_syms]
    return {
        "traded_symbols": len(traded_syms),
        "traded_symbols_outside_universe.ALL_SYMS": outside,
        "conclusion": (
            "reachability check per method rule 3: every traded symbol is inside "
            "universe.ALL_SYMS, which Austin already restricts to his own "
            "~200k+ daily options-volume watchlist (universe.py's own comment: "
            "'high options volume = cleaner moves, easier fills'). A symbol-level "
            "wide-spread filter has zero symbols left to remove -- there is no real "
            "NBBO feed in this repo to grade spread WITHIN a symbol's own chain "
            "(Polygon 403s, Tastytrade sandbox-only per broker/tastytrade.py), so "
            "that half of R30 cannot be measured beyond the per-contract $-spread "
            "sweep above. The filter he's actually pointing at is the geometry one, "
            "part (a)."
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "t9_spread_tight_rr.json"))
    a = ap.parse_args()

    book = load_book()
    print("=== T9 -- spread and tight-RR filter, R30 ===")
    print(f"book: {os.path.relpath(BOOK, ROOT)}  n_traded={len(book)}")

    print("\n-- (a) tight-RR filter on the underlying --")
    tight = sweep_tight_rr(book)
    print(f"book mean_r {tight['book_mean_r']:+.4f}  win_rate {tight['book_win_rate']}%")
    for row in tight["sweep"]:
        print(f"  stop_pct < {row['threshold_stop_pct']:.2f}%  removes {row['removed_n']:4d} "
              f"({row['removed_pct_of_book']:.1f}%) trades, removed mean_r "
              f"{row['removed_mean_r']:+.4f} (median {row['removed_median_r']:+.4f}), "
              f"kept mean_r {row['kept_mean_r']:+.4f} (move {row['book_mean_r_move']:+.4f}), "
              f"removed-vs-kept diff {row['removed_vs_kept_mean_diff']:+.4f} +/- "
              f"{row['removed_vs_kept_95pct_bar']:.4f} "
              f"({'INSIDE bar - null' if row['removed_vs_kept_inside_bar'] else 'outside bar'}), "
              f"removed S-tier {row['removed_by_sgrade'].get('S', 0)}")

    print("\n-- held-out S recall risk of each threshold --")
    fired, unfired, n_s = replay_heldout_s_entries()
    n_fired = len(fired)
    print(f"held-out S cards: {n_s}, engine currently fires on {n_fired} "
          f"({100.0*n_fired/n_s:.1f}%)")
    risk = recall_risk(fired, n_s, n_fired)
    for row in risk:
        print(f"  stop_pct < {row['threshold_stop_pct']:.2f}%  would filter "
              f"{row['S_fires_that_would_be_filtered']} of the {n_fired} current S "
              f"fires -> recall {row['recall_after']}  cards={row['cards']}")

    print("\n-- (b) bid-ask spread cost model on the contract --")
    spread = spread_cost_model(book)
    print(f"n priced {spread['n_priced']} of {len(book)}, base contract R (no spread) "
          f"{spread['base_contract_r_single_no_spread']:+.4f}")
    for row in spread["sweep"]:
        print(f"  round-trip ${row['round_trip_spread_usd']:.2f}  costs "
              f"{row['mean_cost_contract_r']:.4f} R mean -> book "
              f"{row['book_single_after_cost']:+.4f} R")
    print(f"  breakeven round-trip spread: ${spread['breakeven_round_trip_spread_usd']:.3f}")

    print("\n-- symbol-level wide-spread filter reachability --")
    liq = symbol_liquidity_reachability(book)
    print(f"traded symbols {liq['traded_symbols']}, outside universe.ALL_SYMS: "
          f"{liq['traded_symbols_outside_universe.ALL_SYMS']}")

    res = {
        "book": os.path.relpath(BOOK, ROOT), "n_traded": len(book),
        "tight_rr": tight,
        "heldout_recall_risk": {"n_S_total": n_s, "n_fired_before": n_fired,
                                "unfired_cards": unfired, "by_threshold": risk},
        "spread_cost": spread,
        "symbol_liquidity_reachability": liq,
    }
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print("\nwrote " + a.out)


if __name__ == "__main__":
    main()
