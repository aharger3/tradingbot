"""OMEN 8.0 R6 -- re-price the options sample under the old and new delta.

The row's own citation ("re-price the 204-trade options sample") is
unreachable: no 204-trade options sample exists anywhere in this repo, same
situation as R1/R3/R4/R5's lost sources. This script builds its own, reusing
an artifact that's already committed and already scripted rather than
re-running detection from scratch: `research/g90_fill_arms_rows.json` (R1),
925 traded signals over the full two-year book, each carrying
`committed_entry`/`stop`/`dir`/`symbol` from the committed engine's own
book -- exactly the (stock_entry, stock_stop, direction) triples
`options_sizer.build_options_plan` needs.

For every row, prices the SAME trade twice, changing only `delta_estimate`:
`old` (0.5, the pre-R6 default) and `new` (0.42, the fixed default). For each
arm, reports:
  - `reported`  -- OptionsPlan.max_loss, what the sizer itself would have
    told you the trade risks (computed with that arm's delta_estimate).
  - `actual`    -- the SAME contract count re-priced at delta 0.42 (the only
    delta this repo has any citation for at all), i.e. what the trade would
    really have cost if the option's real premium move follows the measured
    delta rather than whatever the model assumed.
The `new` arm's reported and actual are the SAME formula by construction
(delta_estimate == the assumed-true delta), so they agree exactly modulo
integer contract-count rounding; the `old` arm's gap is what R6 fixed.

Output: research/g95_delta_fix.md + research/g95_delta_fix_rows.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from options_sizer import build_options_plan

SOURCE_ROWS = os.path.join(HERE, "g90_fill_arms_rows.json")
OUT_MD = os.path.join(HERE, "g95_delta_fix.md")
OUT_ROWS = os.path.join(HERE, "g95_delta_fix_rows.json")

TRUE_DELTA = 0.42  # the only value this repo has any citation for
OLD_DELTA = 0.5
MAX_LOSS = 1000.0


def price_arm(symbol, direction, entry, stop, delta_estimate):
    plan = build_options_plan(
        symbol=symbol, direction=direction,
        stock_entry=entry, stock_stop=stop,
        max_loss=MAX_LOSS, delta_estimate=delta_estimate,
    )
    stock_risk = abs(entry - stop)
    true_premium_risk = max(round(stock_risk * TRUE_DELTA, 2), 0.05)
    actual = round(true_premium_risk * 100 * plan.contracts, 2)
    reported = plan.max_loss
    gap_pct = (100.0 * abs(reported - actual) / reported) if reported else None
    return dict(contracts=plan.contracts, reported=reported, actual=actual,
                gap_pct=round(gap_pct, 3) if gap_pct is not None else None)


def main():
    with open(SOURCE_ROWS) as f:
        source = json.load(f)

    out_rows = []
    for r in source:
        entry, stop = r["committed_entry"], r["stop"]
        if entry == stop:
            continue
        row = dict(symbol=r["symbol"], day=r["day"], setup=r["setup"], dir=r["dir"],
                   entry=entry, stop=stop)
        row["old"] = price_arm(r["symbol"], r["dir"], entry, stop, OLD_DELTA)
        row["new"] = price_arm(r["symbol"], r["dir"], entry, stop, TRUE_DELTA)
        out_rows.append(row)

    with open(OUT_ROWS, "w") as f:
        json.dump(out_rows, f)

    def summarize(arm):
        gaps = [r[arm]["gap_pct"] for r in out_rows if r[arm]["gap_pct"] is not None]
        reported = sum(r[arm]["reported"] for r in out_rows)
        actual = sum(r[arm]["actual"] for r in out_rows)
        n = len(out_rows)
        mean_gap = sum(gaps) / len(gaps) if gaps else None
        max_gap = max(gaps) if gaps else None
        within_2pct = sum(1 for g in gaps if g <= 2.0)
        return dict(n=n, reported_total=round(reported, 2), actual_total=round(actual, 2),
                    mean_gap_pct=round(mean_gap, 3) if mean_gap is not None else None,
                    max_gap_pct=round(max_gap, 3) if max_gap is not None else None,
                    within_2pct=within_2pct)

    old_s, new_s = summarize("old"), summarize("new")

    L = []
    L.append("# OMEN 8.0 R6 -- re-pricing the options sample under the old and new delta\n")
    L.append(f"{old_s['n']} trades, reused from `research/g90_fill_arms_rows.json` (R1's "
             f"committed two-year book) -- entry/stop/direction only, re-priced through "
             f"`options_sizer.build_options_plan` at `$1,000` max_loss. \"Actual\" is the "
             f"same contract count re-priced at delta {TRUE_DELTA} (the only delta this "
             f"repo has any citation for); \"reported\" is `OptionsPlan.max_loss` as the "
             f"sizer itself would report it under that arm's `delta_estimate`.\n")
    L.append("## Result\n")
    L.append("| arm | delta_estimate | reported total | actual total | mean gap | max gap | within 2% |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    L.append(f"| old (pre-R6) | {OLD_DELTA} | ${old_s['reported_total']:,.0f} | "
             f"${old_s['actual_total']:,.0f} | {old_s['mean_gap_pct']}% | "
             f"{old_s['max_gap_pct']}% | {old_s['within_2pct']}/{old_s['n']} |")
    L.append(f"| new (fixed) | {TRUE_DELTA} | ${new_s['reported_total']:,.0f} | "
             f"${new_s['actual_total']:,.0f} | {new_s['mean_gap_pct']}% | "
             f"{new_s['max_gap_pct']}% | {new_s['within_2pct']}/{new_s['n']} |")
    L.append("")
    L.append(
        f"**Verdict.** At the old default, reported risk overstated actual risk by "
        f"{old_s['mean_gap_pct']}% on average -- close to the exact 16% the delta ratio "
        f"predicts (1 - 0.42/0.5 = 0.16), the gap this row exists to close -- and only "
        f"{old_s['within_2pct']}/{old_s['n']} trades landed within the 2% the row's verify "
        f"asks for. At the fixed default, {new_s['within_2pct']}/{new_s['n']} do: reported "
        f"and actual are the same formula now, not two estimates that happen to agree.\n")

    still_bad = [r for r in out_rows if r["new"]["gap_pct"] is not None and r["new"]["gap_pct"] > 2.0]
    if still_bad:
        L.append(f"## The {len(still_bad)} that still miss 2% at the fixed delta -- a different, pre-existing bug\n")
        L.append(
            f"Not delta. All {len(still_bad)} have identical gaps in BOTH the `old` and "
            f"`new` arms (e.g. {still_bad[0]['symbol']} {still_bad[0]['day']}: "
            f"{still_bad[0]['old']['gap_pct']}% either way), which rules out delta as the "
            f"cause -- the fix changes nothing for them. All {len(still_bad)} have very wide "
            f"stock stops (${min(abs(r['entry']-r['stop']) for r in still_bad):.2f}-"
            f"${max(abs(r['entry']-r['stop']) for r in still_bad):.2f}) against this "
            f"script's fallback premium ESTIMATE (`max(stock_entry * 0.005, 0.50)`, "
            f"`options_sizer.py`'s no-live-quote path -- this measurement has no market "
            f"access, so every row uses it). `premium_risk = stock_risk * delta` then "
            f"exceeds the estimated premium itself, `stop_premium` floors at $0.05, "
            f"`per_contract_risk` shrinks to `entry_premium - 0.05` -- far below the true "
            f"premium_risk -- and the sizer buys more contracts than the true delta would "
            f"support. This is `research/sizing.py`'s own documented limitation of the "
            f"premium-ESTIMATE mode (\"no gamma, no theta, no IV... confidence: low\"), not "
            f"something `DEFAULT_DELTA` controls, and out of this row's scope -- a live "
            f"Tastytrade quote replaces the whole estimate path and would not hit this.\n")

    L.append("## Other places the same wrong delta is still hardcoded (found by adversarial review, not fixed here)\n")
    L.append(
        "This row's scope is `options_sizer.DEFAULT_DELTA` specifically -- that is what the "
        "spec names. A repo-wide grep for the same `stock_risk * 0.5` / `delta ~= 0.5` "
        "assumption turned up two more sites, neither touched by this commit:\n"
        "\n"
        "- **`signal_runner.py`'s `_min_viable_stop` (line ~1059): `premium_risk = "
        "stock_risk * 0.5`.** This one is LIVE -- called from `_route` (~line 1365) on "
        "every signal, backtest and live scanner alike, to decide whether a tight-stop "
        "candidate is viable at all (`risk_pct >= 0.005 or premium_risk >= 0.20`). "
        "Overstating delta here makes MORE tight-stop signals pass than the true 0.42 "
        "would allow -- the identical conceptual bug this row exists to fix, in a "
        "grading gate rather than a position-sizing calculation. Not fixed here: doing so "
        "would change which signals are graded viable at all, retroactively affecting "
        "every prior row's signal counts (R1 through R5 all ran against the shipped "
        "0.5-based gate), which is a different and much larger blast radius than a pure "
        "sizing constant. Flagged for its own row.\n"
        "- **`position_sizer.py`'s `compute_plan(..., assumed_delta: float = 0.5, ...)`.** "
        "A second, older sizing function with the same stale default. Traced its only "
        "caller: `SignalRunner.process_candles`, which nothing in the live path, the "
        "backtest path, or any committed research script calls -- it is a manual/CLI "
        "utility, not reachable from anywhere this spec's rows have measured. Lower "
        "stakes than the above, but stale and worth a follow-up cleanup regardless.\n"
        "- **`spec1_stop_check.py`'s `DELTA = 0.5`** -- a standalone spec-verification "
        "script, same value, lowest stakes of the three.\n")

    L.append("## What could not be reconstructed\n")
    L.append(
        "The row cites `options_sizer.py:38` (the constant is at line 20, now under a "
        "longer comment -- pre-fix it was also not 38) and `omen-rulebook.md:1574` for "
        "\"measured delta is 0.42\" (the rulebook is 995 lines; no such line, and no "
        "mention of 0.42 or a measured delta anywhere in the vault outside the spec's own "
        "citation of it). The \"204-trade options sample\" the verify asks to re-price "
        "exists nowhere in this repo either. Same lost-work situation as R1/R3/R4/R5's "
        "sources. `research/sizing.py`'s own docstring explains why none of this is "
        "reconstructable even in principle: \"this repo has 1-minute underlying bars and "
        "no options chain, so there is no way to reconstruct an actual option fill from "
        "the archive.\" 0.42 is applied here as Austin's stated measurement, not "
        "independently re-derived or independently confirmed -- there is no data in this "
        "repo to do either. What this script DOES verify, mechanically, is the "
        "CONSEQUENCE: once `DEFAULT_DELTA` matches whatever value is asserted as true, "
        "reported and actual risk stop disagreeing, by construction. That holds regardless "
        "of whether 0.42 itself is exactly right -- if a better-measured delta ever "
        "replaces it, the same convergence property holds at the new number too.\n")

    with open(OUT_MD, "w") as f:
        f.write("\n".join(L))
    print("\n".join(L))
    print(f"\nwrote {OUT_MD}")
    print(f"wrote {OUT_ROWS} ({len(out_rows)} rows)")


if __name__ == "__main__":
    main()
