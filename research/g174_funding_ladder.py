"""g174 -- rank the funding ladder (P4 of the OMEN 9.0 spec).

One table, every funding arm measured tonight, in Austin's own ladder order:

    automatic futures prop -> manual prop -> Vanquish options (manual, one
    account) -> automatic personal.

This file does NOT re-run the arms. P0/P1/P2/P3 already did that; this
reproduces every ranked cell out of their committed JSONs
(`g171_futures_proxy_arms.json`, `g172_vanquish_refresh.json`,
`g173_shares_personal_refresh.json`) and adds the three things a ranking
needs that no single arm reported:

  1. the SAME per-stream edge table for all three candidate streams, on the
     one-trade-a-day unit, at a common $1,000/R price, H1/H2 -- so the rungs
     are comparable at all;
  2. an honest all-starts pass rate, because g171's committed
     "rolling-252 pass rate 0.0%" is a `window = min(252, n)` artifact with
     n = 234 -> exactly one window (REFUTED by
     `research/g171_refute_r2_sampling.md` and
     `research/g171_refute3_reproduce.md`);
  3. the drift sweep that answers "what one number would change the
     verdict" -- the per-trade mean R at which the cheapest rung-1 eval
     clears 50% of start days.

Fill, everywhere: signal-bar CLOSE entry, `stop_rule.stop_fill_price()`
stops, size-gated on `signal_runner.min_risk_floor`, out of
`research/bt2y_trades_retest_on.json` (RETEST_REQUIRED=1, shipped default).
1R = $1,000 unless a row says otherwise. H1 = day < 2025-09-01, H2 = day >=
2025-09-01. No network: every number here comes from the committed book and
the committed arm JSONs.

    python research/g174_funding_ladder.py
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from omen_metrics import (evaluate_prop_challenge, first_of_day_arm,  # noqa: E402
                          min_risk_floor)
from g71_propfirm_sim import FIRMS as G71_FIRMS               # noqa: E402
from universe import INDEX_POOL                               # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g174_funding_ladder.json")
SPLIT = "2025-09-01"
R_DOLLARS = 1000.0

ARM_JSONS = {
    "P1": os.path.join(HERE, "g171_futures_proxy_arms.json"),
    "P2": os.path.join(HERE, "g172_vanquish_refresh.json"),
    "P3": os.path.join(HERE, "g173_shares_personal_refresh.json"),
}


# --------------------------------------------------------------------------
# streams -- all three off the same book, same fill, same size gate
# --------------------------------------------------------------------------
def load_rows():
    if os.path.exists(BOOK):
        book = json.load(open(BOOK))
    else:
        book = json.loads(gzip.open(BOOK + ".gz", "rt").read())
    allrows = sorted(book["trades"], key=lambda r: (r["day"], r["et"], r["sym"]))
    rows = [r for r in allrows if r.get("traded") and r.get("r") is not None]
    return rows, allrows, book["meta"]


def sizeable(r):
    return abs(r["entry"] - r["stop"]) >= min_risk_floor(r["entry"])


def first_of_day(rows, keep):
    """First sizeable candidate of the day among rows `keep` accepts."""
    by_day = defaultdict(list)
    for r in rows:
        if keep(r):
            by_day[r["day"]].append(r)
    out = []
    for day in sorted(by_day):
        v = sorted(by_day[day], key=lambda r: (r["et"], r["sym"]))
        pick = next((r for r in v if sizeable(r)), None)
        if pick is not None:
            out.append(pick)
    return out


def edge(arm, label):
    """The per-stream money table at $1,000/R, on the one-trade-a-day unit."""
    if not arm:
        return {"label": label, "n": 0}
    pnl = [(r["day"], r["r"] * R_DOLLARS) for r in arm]
    total = sum(p for _, p in pnl)
    wins = sum(1 for r in arm if r["r"] > 0)
    by_month = defaultdict(float)
    for d, p in pnl:
        by_month[d[:7]] += p
    eq, peak, mdd = 0.0, 0.0, 0.0
    for _, p in pnl:
        eq += p
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
    return {
        "label": label,
        "n": len(arm),
        "first_day": arm[0]["day"],
        "last_day": arm[-1]["day"],
        "total_dollars": round(total, 2),
        "per_day": round(total / len(arm), 2),
        "mean_r": round(total / len(arm) / R_DOLLARS, 4),
        "win_pct": round(100.0 * wins / len(arm), 1),
        "months": len(by_month),
        "green_months": sum(1 for v in by_month.values() if v > 0),
        "max_dd_dollars": round(mdd, 0),
    }


def split_edge(arm, label):
    h1 = [r for r in arm if r["day"] < SPLIT]
    h2 = [r for r in arm if r["day"] >= SPLIT]
    return {"full": edge(arm, label), "H1": edge(h1, label + " H1"),
            "H2": edge(h2, label + " H2")}


# --------------------------------------------------------------------------
# firm evaluation -- honest all-starts pass rate
# --------------------------------------------------------------------------
def firm_kw(spec):
    """Identical mapping to g171_futures_proxy_arms.firm_kw."""
    name, start, target, dll, mdd, mode, _lock, max_days, cost = spec
    kw = dict(
        account_size=float(start),
        profit_target_pct=target / start,
        trailing_dd_pct=mdd / start,
        daily_loss_limit_pct=(dll / start) if dll is not None else 1.0,
        min_trading_days=0,
        consistency_pct=1.0,
        dd_mode="eod" if mode in ("eod", "static") else mode,
    )
    return kw, max_days, cost, name


def all_starts_pass_rate(arm, spec, r_offset=0.0, risk=R_DOLLARS):
    """The corrected statistic the g171 refuters asked for: start the eval on
    EVERY day in the stream, cap it at the firm's own max_days, count passes.
    g171's committed 'rolling-252 pass rate' had window = min(252, n) = n,
    i.e. exactly one start -- n=1 restated as a percentage."""
    kw, max_days, _cost, _name = firm_kw(spec)
    pnl = [(r["day"], (r["r"] + r_offset) * risk) for r in arm]
    n = len(pnl)
    if n == 0:
        return None, 0
    passed = 0
    for s in range(n):
        seg = pnl[s:s + max_days]
        if evaluate_prop_challenge(seg, **kw)["passed"]:
            passed += 1
    return round(100.0 * passed / n, 1), n


def required_mean_r(arm, spec, target_pass_pct=50.0, risk=R_DOLLARS):
    """The one number that would change the verdict: the smallest per-trade R
    offset at which this eval clears `target_pass_pct` of start days."""
    base = edge(arm, "x")["mean_r"]
    for step in range(0, 61):
        off = step * 0.01
        pct, _ = all_starts_pass_rate(arm, spec, r_offset=off, risk=risk)
        if pct is not None and pct >= target_pass_pct:
            return {"offset_r": round(off, 3), "mean_r_now": base,
                    "mean_r_needed": round(base + off, 4),
                    "pass_pct_there": pct}
    return {"offset_r": None, "mean_r_now": base, "mean_r_needed": None,
            "pass_pct_there": None}


# --------------------------------------------------------------------------
def firm_by_name(name):
    for spec in G71_FIRMS:
        if spec[0] == name:
            return spec
    raise KeyError(name)


def main():
    rows, allrows, meta = load_rows()
    idx_set = set(INDEX_POOL)

    # g171's index stream is `first_of_day_arm` restricted to INDEX_POOL --
    # which includes loss-halted rows (under one-trade-a-day the halt cannot
    # have fired yet), so it is built off the UNFILTERED book, not the
    # traded-only rows the other two arms use. The g171 refuters verified
    # the set-equality of these 234 picks against g171's own selection.
    idx_arm = [r for r in first_of_day_arm([r for r in allrows
                                            if r["sym"] in idx_set])
               if r.get("r") is not None]
    s_arm = first_of_day(rows, lambda r: r.get("sgrade") == "S")
    a_arm = first_of_day_arm(rows)

    streams = {
        "IDX_first_of_day": split_edge(idx_arm,
                                       "index pool QQQ/SPY/IWM, first of day"),
        "S_only_first_of_day": split_edge(s_arm, "S-graded only, first of day"),
        "A_base_first_of_day": split_edge(a_arm,
                                          "full pool, first of day (A_base)"),
    }

    # honest all-starts pass rates, one representative firm per rung
    reps = [
        ("rung 1 - auto futures prop", "Apex 50K Eval EOD", idx_arm),
        ("rung 1 - auto futures prop", "Topstep 50K Combine", idx_arm),
        ("rung 2 - manual shares prop", "TTP 25K FLEX day", a_arm),
        ("rung 2 - manual shares prop", "TTP 50K FLEX day", a_arm),
    ]
    starts = []
    for rung, fname, arm in reps:
        spec = firm_by_name(fname)
        pct, n = all_starts_pass_rate(arm, spec)
        starts.append({"rung": rung, "firm": fname, "stream_n": n,
                       "all_starts_pass_pct": pct})

    drift = {
        "Apex 50K Eval EOD / index stream":
            required_mean_r(idx_arm, firm_by_name("Apex 50K Eval EOD")),
        "TTP 25K FLEX day / full-pool stream":
            required_mean_r(a_arm, firm_by_name("TTP 25K FLEX day")),
    }

    arms = {k: json.load(open(v)) for k, v in ARM_JSONS.items()
            if os.path.exists(v)}

    out = {
        "book": os.path.basename(BOOK),
        "book_sessions": meta.get("sessions"),
        "split": SPLIT,
        "r_dollars": R_DOLLARS,
        "streams": streams,
        "all_starts_pass_rates": starts,
        "drift_to_50pct": drift,
        "arm_jsons_read": sorted(arms),
    }
    json.dump(out, open(OUT_JSON, "w"), indent=1)

    print("book %s, %s sessions" % (out["book"], out["book_sessions"]))
    for k, v in streams.items():
        for w in ("full", "H1", "H2"):
            e = v[w]
            print("%-22s %-3s n=%-4d $/day %8.2f  meanR %+7.4f  win %4.1f%%  "
                  "green %2d/%-2d  maxDD $%s"
                  % (k, w, e["n"], e["per_day"], e["mean_r"], e["win_pct"],
                     e["green_months"], e["months"], e["max_dd_dollars"]))
    print()
    for s in starts:
        print("all-starts pass  %-22s n=%-4d %5.1f%%"
              % (s["firm"], s["stream_n"], s["all_starts_pass_pct"]))
    print()
    for k, v in drift.items():
        print("drift to 50%% pass  %-38s now %+0.4fR  need %s  (+%sR)"
              % (k, v["mean_r_now"], v["mean_r_needed"], v["offset_r"]))
    print("\nwrote", OUT_JSON)


if __name__ == "__main__":
    main()
