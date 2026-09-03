"""g71 adversarial verify of track `rrcap`.

The rrcap proof measured R on the STOCK side, where rr appears on both sides of
the ratio -- (stock_entry + rr*risk - stock_entry)/risk == rr identically, and
max_reward is DEFINED as per_contract_risk*contracts*rr, so max_reward/max_loss
== rr identically. Neither number can come back anything but 2.000; they test
arithmetic, not the cap.

The R a live/paper position actually BOOKS is in PREMIUM terms, because 1R is
`per_contract_risk = (entry_premium - stop_premium) * 100` (options_sizer.py:294)
and paper_trader.realized_pnl books (exit_premium - entry_premium)*100*contracts
against exactly that. options_sizer.py:290 floors stop_premium at $0.05 while
:291 keeps the UNfloored premium_risk in the target, so whenever the floor binds
the booked target R is strictly greater than rr.

This replays every traded row of the shipped 2-year book through the real
build_options_plan (estimate fallback -- no network, and that fallback IS the
live path whenever the Tastytrade quote fails) and reports the booked R.
"""
import json, os, sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import options_sizer as osz

BOOK = ROOT / "research" / "bt2y_trades.json"
d = json.load(open(BOOK))
rows = [t for t in d["trades"] if t.get("traded")]
print("book meta:", {k: d["meta"][k] for k in list(d["meta"])[:6]})
print("rows total %d  traded %d" % (len(d["trades"]), len(rows)))

def booked_r(p):
    denom = p.entry_premium - p.stop_premium
    return (p.target_premium - p.entry_premium) / denom if denom > 0 else float("nan")

over, exact, under, floored, bad = 0, 0, 0, 0, 0
worst = []
for t in rows:
    e, s = float(t["entry"]), float(t["stop"])
    try:
        p = osz.build_options_plan("TEST", t["dir"], e, s, max_loss=1000.0)
    except ValueError:
        bad += 1
        continue
    r = booked_r(p)
    if p.stop_premium <= 0.05 + 1e-9 and (p.entry_premium - round(abs(e - s) * 0.5, 2)) < 0.05:
        floored += 1
    if r > 2.0 + 1e-9:
        over += 1
        worst.append((r, t["sym"], t["day"], e, s, p.entry_premium, p.stop_premium,
                      p.target_premium, p.contracts))
    elif abs(r - 2.0) <= 1e-9:
        exact += 1
    else:
        under += 1
print("booked target R  >2.0: %d (%.2f%%)   ==2.0: %d   <2.0: %d   sizing-rejected: %d"
      % (over, 100.0 * over / max(len(rows), 1), exact, under, bad))
print("stop_premium floor bound on: %d rows (%.2f%%)"
      % (floored, 100.0 * floored / max(len(rows), 1)))
worst.sort(reverse=True)
print("\nworst 8 (booked R, sym, day, stock entry/stop, prem entry/stop/target, contracts):")
for w in worst[:8]:
    print("  %.3fR  %-5s %s  %.2f/%.2f  $%.2f/$%.2f/$%.2f  x%d" % w)
if worst:
    print("\nP&L check on the top row via paper_trader (whole position at target):")
    from paper_trader import PaperBook, PaperPosition
    import tempfile
    r, sym, day, e, s, ep, sp, tp, ct = worst[0]
    p = osz.build_options_plan("TEST", "call" if e > s else "put", e, s, max_loss=1000.0)
    book = PaperBook(ledger_path=Path(tempfile.mkdtemp()) / "v.jsonl")
    pos = book.open_from_plan(p, ts="09:35:00")
    hi = p.stock_target + 0.01 if p.direction == "call" else p.stock_entry
    lo = p.stock_target - 0.01 if p.direction == "put" else p.stock_entry
    evs = book.mark("TEST", high=hi, low=lo, close=p.stock_entry)
    pnl = evs[0]["pnl"]
    print("  max_loss (1R) $%.2f   booked pnl at target $%.2f  -> %.3f R  (outcome=%s)"
          % (p.max_loss, pnl, pnl / p.max_loss, evs[0]["outcome"]))
    print("  plan.max_reward SAYS $%.2f (= max_loss*rr, circular)" % p.max_reward)
