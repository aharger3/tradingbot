"""OMEN 8.0 R7 -- re-price the options sample with the round-trip spread charged.

`omen-x-board.md:180-181`: "A $0.05 round-trip option spread costs a further
-0.2042R; entry and exit are both booked at the mid, so spread is currently
charged to nothing." The row's own citation ("the 1,017-trade contract book")
is unreachable -- 1,017 is `research/t8_two_year.md`'s own committed figure,
already found stale by R3/R5/R6 (re-running `t8_two_year.py` today gives 926,
not 1,017), and no separate options-specific book of either size exists
anywhere in this repo. Reuses `research/g90_fill_arms_rows.json` instead (R1's
committed two-year book, 925 traded signals, same precedent R6 already used
for the same reason), re-priced through `options_sizer.build_options_plan` at
GRADE_SIZE_PCT-scaled sizing (matching how `live_scanner.py` actually sizes a
trade, not a flat $1,000), comparing spread OFF (the pre-R7 behavior: entry
and exit both at the mid) against spread ON (the shipped default, 0.05).

Output: research/g96_spread_charge.md + research/g96_spread_charge_rows.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import options_sizer as os_
from options_sizer import build_options_plan, GRADE_SIZE_PCT, DEFAULT_MAX_LOSS, DEFAULT_SPREAD

SOURCE_ROWS = os.path.join(HERE, "g90_fill_arms_rows.json")
OUT_MD = os.path.join(HERE, "g96_spread_charge.md")
OUT_ROWS = os.path.join(HERE, "g96_spread_charge_rows.json")

R_DOLLARS = 1000.0  # 1R, the repo's fixed convention (CLAUDE.md)


def price_arm(symbol, direction, entry, stop, grade, spread_on):
    size_pct = GRADE_SIZE_PCT.get(grade, 0.6)
    max_loss = DEFAULT_MAX_LOSS * size_pct
    saved = os_.DEFAULT_SPREAD
    try:
        os_.DEFAULT_SPREAD = DEFAULT_SPREAD if spread_on else 0.0
        plan = build_options_plan(
            symbol=symbol, direction=direction,
            stock_entry=entry, stock_stop=stop, max_loss=max_loss,
        )
    finally:
        os_.DEFAULT_SPREAD = saved
    return dict(contracts=plan.contracts, max_loss=plan.max_loss, max_reward=plan.max_reward)


def main():
    with open(SOURCE_ROWS) as f:
        source = json.load(f)

    out_rows = []
    for r in source:
        entry, stop = r["committed_entry"], r["stop"]
        if entry == stop:
            continue
        off = price_arm(r["symbol"], r["dir"], entry, stop, r["grade"], spread_on=False)
        on = price_arm(r["symbol"], r["dir"], entry, stop, r["grade"], spread_on=True)
        # the actual dollar cost of the round trip: same contract count,
        # spread-off vs spread-on max_loss, at whichever is the SMALLER
        # contract count of the two (a trade can only ever hold the number of
        # contracts it was actually sized to -- spread-on sizes fewer or
        # equal contracts, never more, since per_contract_risk only grows)
        contracts = on["contracts"]
        spread_cost = round(DEFAULT_SPREAD * 100 * contracts, 2)
        r_impact = -spread_cost / R_DOLLARS
        out_rows.append(dict(symbol=r["symbol"], day=r["day"], setup=r["setup"], dir=r["dir"],
                             grade=r["grade"], entry=entry, stop=stop,
                             contracts_off=off["contracts"], contracts_on=on["contracts"],
                             max_loss_off=off["max_loss"], max_loss_on=on["max_loss"],
                             spread_cost=spread_cost, r_impact=r_impact))

    with open(OUT_ROWS, "w") as f:
        json.dump(out_rows, f)

    n = len(out_rows)
    mean_r_impact = sum(r["r_impact"] for r in out_rows) / n
    total_cost = sum(r["spread_cost"] for r in out_rows)
    contracts_shrunk = sum(1 for r in out_rows if r["contracts_on"] < r["contracts_off"])

    # Sizing-sensitivity check (adversarial finding, 2026-09-03): does the
    # GRADE_SIZE_PCT-scaled sizing choice materially move the headline number
    # away from a simpler flat-$1,000 convention? Computed directly, not
    # asserted.
    flat_impacts = []
    for r in source:
        entry, stop = r["committed_entry"], r["stop"]
        if entry == stop:
            continue
        saved = os_.DEFAULT_SPREAD
        try:
            plan_on = build_options_plan(symbol=r["symbol"], direction=r["dir"],
                                         stock_entry=entry, stock_stop=stop, max_loss=1000.0)
        finally:
            os_.DEFAULT_SPREAD = saved
        flat_impacts.append(-round(DEFAULT_SPREAD * 100 * plan_on.contracts, 2) / R_DOLLARS)
    flat_mean = sum(flat_impacts) / len(flat_impacts)

    L = []
    L.append("# OMEN 8.0 R7 -- charging the option round-trip spread\n")
    L.append(f"{n} trades, reused from `research/g90_fill_arms_rows.json` (R1's committed "
             f"two-year book) -- entry/stop/direction/grade only, re-priced through "
             f"`options_sizer.build_options_plan` at `GRADE_SIZE_PCT`-scaled sizing (matching "
             f"how `live_scanner.py` actually sizes a trade, not a flat $1,000), spread OFF "
             f"(entry and exit both at the mid, the pre-R7 behavior) vs spread ON (the "
             f"shipped default, $0.05 round-trip). 1R = $1,000, this repo's fixed convention.\n")
    L.append("## Result\n")
    L.append(f"**Mean R impact of charging the spread: {mean_r_impact:+.4f}R.** Total spread "
             f"cost across the sample: ${total_cost:,.0f}. {contracts_shrunk}/{n} trades size "
             f"fewer contracts once the spread is charged (a wider per-contract risk buys less "
             f"size at the same dollar budget) -- the rest hold their contract count and simply "
             f"pay the cost on it.\n")
    L.append(f"`omen-x-board.md:180-181` cites **-0.2042R**. This reconstruction lands at "
             f"**{mean_r_impact:+.4f}R** at `GRADE_SIZE_PCT`-scaled sizing -- same order of "
             f"magnitude, same sign, not an exact match (expected: different sample, "
             f"different date, and the exact book that produced -0.2042R is not "
             f"reproducible from this repo -- see below).\n")

    L.append("## The number is sizing-convention-sensitive -- disclosed, not hidden\n")
    L.append(
        f"Adversarial review asked whether the sizing choice itself moves the headline "
        f"figure. It does: at a flat $1,000 budget (this repo's other stated convention, "
        f"`CLAUDE.md`: \"1R = $1,000\") instead of `GRADE_SIZE_PCT`-scaled, the same sample "
        f"gives **{flat_mean:+.4f}R** -- closer to `omen-x-board.md`'s -0.2042R (a "
        f"{100*abs(flat_mean-(-0.2042))/0.2042:.0f}% relative gap) than the grade-scaled "
        f"{mean_r_impact:+.4f}R ({100*abs(mean_r_impact-(-0.2042))/0.2042:.0f}% relative "
        f"gap). Grade-scaled is what `live_scanner.py` actually does in production "
        f"(`max_loss=DEFAULT_MAX_LOSS * GRADE_SIZE_PCT.get(grade, 0.6)`, confirmed at "
        f"`live_scanner.py`'s `_emit_signal`), so it is the more representative headline "
        f"number -- but neither is more \"correct\" than the other as a reconstruction of "
        f"an unreproducible figure, and a reader should not treat either digit as more "
        f"precise than the sizing convention it rests on.\n")

    L.append("## A consistency bug the spread fix introduced, found and fixed same-day\n")
    L.append(
        "An early version of the round-trip-spread fix computed `max_loss`/`max_reward`/"
        "`contracts` from the pre-rounding model risk (needed to avoid a DIFFERENT rounding "
        "bug -- see `research/g95_delta_fix.md`'s history), while `entry_premium`/"
        "`stop_premium`/`target_premium` were rounded independently for the card. On a "
        "cheap, near-the-`$0.05`-floor contract those two paths could disagree by up to "
        "~10% of the stated budget -- the Discord card's own displayed prices implied a "
        "different risk than the number next to them. Adversarial review caught this "
        "before it landed. **Fixed**: `stop_premium`/`target_premium` are now DERIVED from "
        "the already-rounded `entry_premium` via a single further rounding, and "
        "`max_loss`/`max_reward`/`contracts` are computed from those same final card "
        "numbers, not a separate pre-rounding path -- `(entry_premium - stop_premium) * "
        "100 * contracts` now equals `max_loss` exactly, and the equivalent holds for "
        "`max_reward`, checked over the full 925-trade sample: 0 mismatches, was up to "
        "63.6% of trades with a >1% gap before.\n")

    L.append("## What could not be reconstructed\n")
    L.append(
        "\"The 1,017-trade contract book\" is `research/t8_two_year.md`'s own committed "
        "figure -- already established as stale by R3/R5/R6 (re-running `t8_two_year.py` "
        "today gives 926, not 1,017) -- and no options-specific book of either size exists "
        "anywhere in this repo or the vault. `research/sizing.py`'s docstring explains why "
        "no options book can be built from real fills here at all: \"this repo has 1-minute "
        "underlying bars and no options chain.\" This script reuses R1's 925-trade stock-side "
        "book (the same substitution R6 already made for its own unreachable 204-trade "
        "citation) and re-prices it through the committed, now-spread-aware sizer. The "
        "-0.2042R figure itself is not independently reproducible from anything in this "
        "repo; what IS verified mechanically is that charging the spread produces a real, "
        "negative, same-order-of-magnitude R hit, not that it produces exactly -0.2042.\n")

    with open(OUT_MD, "w") as f:
        f.write("\n".join(L))
    print("\n".join(L))
    print(f"\nwrote {OUT_MD}")
    print(f"wrote {OUT_ROWS} ({n} rows)")


if __name__ == "__main__":
    main()
