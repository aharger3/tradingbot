"""build_nq_br_trades.py -- regenerate the chosen setup's trade list.

Chosen setup (OMEN-SHIP-PLAN.md section 1, the only real-futures hypothesis
cell with both halves positive): NQ (MNQ-sized) break-and-retest,
PDH/PDL/ONH/ONL levels ("PRE"), stop = level - 0.25 x avg range ("LVL"),
3R target, flat 11:00. This is `research/agent_runs/t02-break-retest/bt.py`'s
grid row (levels=PRE, stop=LVL, tgt=3), NQ only -- bt.py's own combined
ES+NQ `comb` book picks whichever instrument fires first each day and never
writes a per-instrument trade list to disk, only the aggregate stats
(n_nq=150, R_nq=+0.369, win_nq=0.40) already in results.json. This script
calls bt.py's own `sessions()` / `signals()` / `trade()` functions UNCHANGED
(byte-identical import, no logic copied) restricted to root="NQ" to recover
the actual per-day trade rows behind that aggregate, so the scaling
simulator has something to replay.

Run from the PC: python build_nq_br_trades.py
Writes: research/nq_br_trades.json
"""
import json
import os
import statistics
import sys

BT_DIR = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t02-break-retest"
OUT_PATH = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\nq_br_trades.json"

sys.path.insert(0, BT_DIR)
import bt  # noqa: E402

ROOT = "NQ"
LEVELSET = "PRE"
STOPMODE = "LVL"
TGT = 3


def main():
    sess = bt.sessions(ROOT)
    dates = sorted(sess)
    rows = []
    for d in dates:
        s = sess[d]
        sigs = bt.signals(s, LEVELSET)
        for sig in sigs:
            t = bt.trade(s, sig, STOPMODE, TGT, ROOT, net=True)
            if t:
                rows.append(dict(day=d, usd=round(t["usd"], 2), r=round(t["R"], 6),
                                  n=t["n"], why=t["why"], lvl=t["lvl"], dir=t["d"]))
                break

    n = len(rows)
    mean_r = statistics.mean(r["r"] for r in rows) if rows else 0.0
    win = sum(1 for r in rows if r["r"] > 0) / n if n else 0.0
    print("n=%d mean_R=%.4f win=%.4f first=%s last=%s"
          % (n, mean_r, win, dates[0] if dates else None, dates[-1] if dates else None))

    out = dict(
        meta=dict(
            root=ROOT, levelset=LEVELSET, stopmode=STOPMODE, tgt=TGT,
            source="research/agent_runs/t02-break-retest/bt.py grid row "
                    "(levels=PRE, stop=LVL, tgt=3R), NQ only -- OMEN-SHIP-PLAN.md "
                    "section 1's 'hypothesis' cell",
            sessions_scanned=len(dates), first_session=dates[0] if dates else None,
            last_session=dates[-1] if dates else None,
            n_trades=n, mean_r=round(mean_r, 4), win_rate=round(win, 4),
            honest_fill=True, note="next-1m-open fill, hard stop-market, "
                                    "$1.24/side commission, 1-tick slippage per side",
        ),
        trades=rows,
    )
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("wrote", OUT_PATH)


if __name__ == "__main__":
    main()
