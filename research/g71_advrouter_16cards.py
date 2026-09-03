"""G7.1 adversarial verify / track `router`: run the BOOK's own path
(backtest_week.simulate_day, backtest_2y level inputs) and the recall harness
(t4_engine_recall.run_day with the delegating router) over every corrected-harness
S hit that is inside the book's symbol list, and attribute the gap.

Usage: python research/g71_advrouter_16cards.py
"""
from __future__ import annotations
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)

import backtest_week as bw
_o = bw.BacktestRunner._route
def _r(self, signals, sig):
    _o(self, signals, sig); sig["_bar"] = len(self.candles) - 1
bw.BacktestRunner._route = _r

import research.g71_advrouter_cardsplit as cs
import research.t4_engine_recall as t4
from research.g71_router_recall import _delegating_route, _ORIGINAL_ROUTE

BOOK = json.load(open(os.path.join(HERE, "bt2y_trades.json")))
SYMS = set(BOOK["meta"]["symbols"]); FIRST, LAST = BOOK["meta"]["first"], BOOK["meta"]["last"]
HITS = json.load(open(os.path.join(HERE, "g71_router_diag.json")))["hits"]["X_LIFT=clean / delegating"]

def main():
    out = []
    print("%-22s %-9s %-9s | harness raw/fired/ent | book cap/fired/rows/traded | attribution"
          % ("card", "H-bias", "B-bias"))
    for h in sorted(HITS):
        sym, day = h.rsplit("_", 1)
        if sym not in SYMS or not (FIRST <= day <= LAST):
            print("%-22s  SKIP (sym in book=%s, in window=%s)" % (h, sym in SYMS, FIRST <= day <= LAST))
            continue
        t4.CaptureRunner._route = _delegating_route
        ent, sigs, raw = t4.run_day(sym, day)
        t4.CaptureRunner._route = _ORIGINAL_ROUTE
        trades, r, ctx = cs.book_day(sym, day)
        hb = t4.htf_bias(sym, day)
        cap = r.captured
        bfired = [s for s in cap if s["status"] == "fired"]
        rowbars = {t.entry_idx for t in trades}
        fired_in_book = [s for s in bfired if s["_bar"] in rowbars]
        traded = sum(1 for t in trades if t.counted)
        # why did each book fire not reach the book?
        lost_to_dedupe = len(bfired) - len(fired_in_book)
        rec = dict(card=h, h_bias=hb, b_bias=ctx["bias"],
                   h_raw=len(raw), h_fired=sum(1 for x in raw if x["status"] == "fired"),
                   h_entries=len(ent), b_cap=len(cap), b_fired=len(bfired),
                   b_rows=len(trades), b_fired_rows=len(fired_in_book),
                   b_traded=traded, lost_to_dedupe=lost_to_dedupe,
                   detect_diff=len(cap) - len(raw))
        out.append(rec)
        print("%-22s %-9s %-9s | %3d/%2d/%2d | %3d/%2d/%2d/%2d | detect_diff=%+d fires_lost_to_dedupe=%d"
              % (h, hb, ctx["bias"], rec["h_raw"], rec["h_fired"], rec["h_entries"],
                 rec["b_cap"], rec["b_fired"], rec["b_rows"], rec["b_traded"],
                 rec["detect_diff"], lost_to_dedupe))
    tot = lambda k: sum(x[k] for x in out)
    print("\nn=%d cards | harness fired-raw %d, entries %d | book fires %d, fires reaching book %d, traded %d"
          % (len(out), tot("h_fired"), tot("h_entries"), tot("b_fired"),
             tot("b_fired_rows"), tot("b_traded")))
    print("cards where book fires >=1: %d ; cards where a fire reaches the book: %d ; cards traded: %d"
          % (sum(1 for x in out if x["b_fired"]), sum(1 for x in out if x["b_fired_rows"]),
             sum(1 for x in out if x["b_traded"])))
    print("cards where harness and book DISAGREE on htf_bias: %d/%d"
          % (sum(1 for x in out if x["h_bias"] != x["b_bias"]), len(out)))
    print("cards where detection counts differ: %d" % sum(1 for x in out if x["detect_diff"]))
    print("cards where fired counts differ (router effect): %d"
          % sum(1 for x in out if x["h_fired"] != x["b_fired"]))
    json.dump(out, open(os.path.join(HERE, "g71_advrouter_16cards.json"), "w"), indent=2)
    print("wrote research/g71_advrouter_16cards.json")

if __name__ == "__main__":
    main()
