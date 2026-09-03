"""G7.2 liveexit — how wrong the trade card's reward number was, in dollars.

Board bug #3 (`research/g71_board.md`, from `research/g71_rrcapv.md`):

    "The options sizer floors the stop premium at 5 cents but leaves the
     unfloored number in the target, so the card under-reports your reward by
     up to 3.8x -- one trade booked $6,560 on an $872 risk while the card said
     $1,744."

`options_sizer.OptionsPlan.max_reward` used to be `per_contract_risk * contracts
* rr`, which is `max_loss * rr` -- an identity, not a measurement. It could only
ever say `rr`, and on every row where the $0.05 stop-premium floor binds it
disagreed with the target sitting next to it on the same card.

This replays every traded row of the shipped two-year book through the REAL
`build_options_plan` (estimate fallback, no network -- and that fallback IS the
live path whenever the Tastytrade quote fails, `options_sizer.py:255-267`) and
reports the old card number against the new one.

It does NOT change how any trade exits. The exit trigger is `stock_target`,
which is `stock_entry +/- rr * stock_risk` and is untouched by this fix. All
that changed is what the card CLAIMS.

Run:

    python research/g72_liveexit_cardcheck.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import options_sizer as osz          # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"


def main() -> int:
    d = json.load(open(BOOK))
    meta = d.get("meta", {})
    rows = [t for t in d["trades"] if t.get("traded")]
    print(f"book: {BOOK.name}  generated {meta.get('generated', '?')}")
    print(f"rows {len(d['trades']):,}  traded {len(rows):,}  "
          f"rr = {osz.DEFAULT_RR:g}  1R sized at $1,000 of max loss")
    print()

    floored = 0
    understated = []
    total_old = total_new = 0.0
    rejected = 0

    for t in rows:
        e, s = float(t["entry"]), float(t["stop"])
        try:
            p = osz.build_options_plan("TEST", t["dir"], e, s, max_loss=1000.0)
        except ValueError:
            rejected += 1
            continue
        # The old formula, reproduced here so the comparison is a measurement
        # and not a memory of what the file used to say.
        old_card = round(p.max_loss * p.rr, 2)
        new_card = p.max_reward
        total_old += old_card
        total_new += new_card
        # The floor bound iff the sizer wanted a stop premium below $0.05.
        floor_bound = p.entry_premium - p.premium_risk < 0.05 - 1e-9
        if floor_bound:
            floored += 1
        if new_card > old_card + 0.01:
            understated.append((new_card / old_card, new_card - old_card,
                                t["sym"], t["day"], e, s, p.entry_premium,
                                p.stop_premium, p.target_premium, p.contracts,
                                p.max_loss, old_card, new_card, floor_bound))

    n = len(rows) - rejected
    print(f"the $0.05 stop-premium floor binds on {floored} of {n:,} traded rows "
          f"({100.0 * floored / max(n, 1):.2f}%)")
    print(f"the card understated its own target on {len(understated)} of {n:,} rows "
          f"({100.0 * len(understated) / max(n, 1):.2f}%)")
    # Two separate causes, and only the first is worth a headline. The floor is
    # the 3.8x error. Cent rounding on the target price is `g71_rrcapv.md`
    # finding #4 and is worth pennies -- it is listed so nobody reads the 26%
    # above and thinks a quarter of the book was badly mis-stated.
    big = [w for w in understated if w[13]]
    small = [w for w in understated if not w[13]]
    print(f"  {len(big)} of them are the FLOOR — the real bug, up to "
          f"{max((w[0] for w in big), default=1):.2f}x, "
          f"${sum(w[1] for w in big):,.0f} of reward not shown")
    print(f"  {len(small)} are half a cent of rounding on the target price "
          f"(${sum(w[1] for w in small):,.0f} total, "
          f"worst {max((w[0] for w in small), default=1):.3f}x) — that is")
    print(f"     research/g71_rrcapv.md finding #4 and it is not what this fixes")
    print()

    understated.sort(reverse=True)
    if understated:
        worst = understated[0]
        print(f"worst row: {worst[2]} {worst[3]}  stock {worst[4]:.2f} -> stop {worst[5]:.2f}")
        print(f"  contract ${worst[6]:.2f} entry / ${worst[7]:.2f} stop / "
              f"${worst[8]:.2f} target, {worst[9]} contracts")
        print(f"  risk ${worst[10]:,.0f}   card USED to say ${worst[11]:,.0f}   "
              f"card NOW says ${worst[12]:,.0f}   ({worst[0]:.2f}x)")
        print()
        print("  the 8 most understated cards (multiple, dollars missed, symbol, day):")
        for w in understated[:8]:
            print(f"    {w[0]:5.2f}x  ${w[1]:9,.0f}  {w[2]:<5} {w[3]}  "
                  f"risk ${w[10]:,.0f} -> reward ${w[12]:,.0f}")
        print()

    print(f"summed across the whole traded book, the reward the cards claimed")
    print(f"  old: ${total_old:14,.0f}")
    print(f"  new: ${total_new:14,.0f}   (+${total_new - total_old:,.0f}, "
          f"{100.0 * (total_new - total_old) / max(total_old, 1):.2f}% more)")
    print()
    print("This is a LABEL correction, not a P&L change: the exit trigger is")
    print("stock_target = stock_entry +/- rr * stock_risk, which this fix does")
    print("not touch. No trade exits anywhere different. What changed is that")
    print("the card no longer contradicts its own target price.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
