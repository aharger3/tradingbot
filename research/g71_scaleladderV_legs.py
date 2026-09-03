"""ADVERSARIAL VERIFY of research/g71_scaleladder.md section 3.

Independently recomputes, from research/bt2y_trades.json:
  - the book identity (traded count vs the T0 2,595 book)
  - his-ladder win rate / mean loss / mean winner / required winner T
  - per-leg means, UNCONDITIONAL and CONDITIONAL ON THE TRADE WINNING
  - the runner-leg R actually required at f=10% with the other three legs at
    their MEASURED exits (the report instead grants them a flat 2R)
  - the f sweep, and whether mean_at() is linear in f (so "any f" is testable)
  - a HONEST f=100% runner: no rung exists, so the BE trail can never arm.

Reuses run_ladder from g71_scaleladder (no fill re-implementation).
"""
from __future__ import annotations
import json, os, statistics, sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(os.path.dirname(HERE))
for p in (str(ROOT), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import g71_scaleladder as SL
import p21_target_availability as p21

raw = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))
meta = raw["meta"]
book = [t for t in raw["trades"] if t["traded"]]
print("BOOK meta:", {k: meta[k] for k in ("generated", "signals", "traded", "sessions", "loss_halt", "halted") if k in meta})
print("traded rows in file:", len(book))

ctx = []
for t in book:
    ei = t.get("entry_i")
    if ei is None:
        ei = p21.entry_index(t["sym"], t["day"], t["et"])
    bars = SL.bars_for(t["sym"], t["day"])
    if not bars or ei is None or ei >= len(bars) - 1:
        continue
    long = t["dir"] == "call"
    lv = p21.levels_for_entry(t["sym"], t["day"], ei) or {}
    six = [px for k, px in lv.items() if k in SL.SIX]
    t2_px, _ = SL.tranche2_target(t["entry"], t["stop"], long, six)
    ctx.append({"t": t, "bars": bars, "ei": ei, "long": long, "t2_px": t2_px,
                "mfe": SL.mfe_r(bars, ei, t["entry"], t["stop"], long)})
print("usable ctx:", len(ctx))

legs_all, own_all, comps, fss = [], [], [], []
for c in ctx:
    comp, legs, fs, own = SL.run_ladder(c["bars"], c["ei"], c["t"]["entry"], c["t"]["stop"],
                                        c["long"], (0.30, 0.30, 0.30, 0.10), c["t2_px"],
                                        trail="be", struct="swing", clock=SL.EOD,
                                        per_tranche=True)
    legs_all.append(legs); own_all.append(own); comps.append(comp); fss.append(fs)

rs = [r for r in comps if r is not None]
w = [r for r in rs if r > 0]; l = [r for r in rs if r <= 0]
wr = len(w) / len(rs); ml = sum(l) / len(l); mw = sum(w) / len(w)
print("\n== HIS LADDER, recomputed ==")
print("n=%d win=%.2f%% meanR=%+.4f meanWin=%+.4f meanLoss=%+.4f"
      % (len(rs), 100 * wr, sum(rs) / len(rs), mw, ml))
print("required winner T for meanR 2.0 = %+.4f" % ((2.0 - (1 - wr) * ml) / wr))

def legmean(k, sel=None):
    v = [lg[k] for lg, comp in zip(legs_all, comps)
         if k in lg and comp is not None and (sel is None or sel(comp))]
    return (statistics.fmean(v) if v else 0.0), len(v)

print("\n== per-leg mean R (unweighted leg R) ==")
print("leg | all trades       | WINNING trades only | own-rung only")
for k in (1, 2, 3, 4):
    a, na = legmean(k)
    b, nb = legmean(k, lambda r: r > 0)
    ov = [lg[k] for lg, ow, comp in zip(legs_all, own_all, comps)
          if comp is not None and k in ow and k in lg]
    om = statistics.fmean(ov) if ov else float("nan")
    print("T%d  | %+.4f (n=%4d) | %+.4f (n=%4d)  | %+.4f (n=%4d)" % (k, a, na, b, nb, om, len(ov)))

# honest required runner leg R at f=10%, other three at MEASURED exits
m1, m2, m3 = legmean(1)[0], legmean(2)[0], legmean(3)[0]
need_uncond = (2.0 - 0.30 * (m1 + m2 + m3)) / 0.10
print("\nHONEST required runner leg mean R at f=10%% (others at measured exits): %+.3fR" % need_uncond)
# report's version: grant the other three a flat 2R, target the WINNER T
need_report = (((2.0 - (1 - wr) * ml) / wr) - 0.9 * 2.0) / 0.10
print("REPORT's version (others granted 2R, target = winner T): %+.3fR" % need_report)
# same frame but with the legs' own actual conditional-on-win values
c1, c2, c3 = legmean(1, lambda r: r > 0)[0], legmean(2, lambda r: r > 0)[0], legmean(3, lambda r: r > 0)[0]
print("SAME FRAME, legs at their real winner-conditional means (%.3f/%.3f/%.3f): %+.3fR"
      % (c1, c2, c3, (((2.0 - (1 - wr) * ml) / wr) - 0.30 * (c1 + c2 + c3)) / 0.10))

def mean_at(f, r4s):
    s3 = (1.0 - f) / 3.0
    v = [s3 * (lg.get(1, 0.0) + lg.get(2, 0.0) + lg.get(3, 0.0)) + f * (r4 if r4 is not None else 0.0)
         for lg, r4 in zip(legs_all, r4s) if lg]
    return statistics.fmean(v) if v else 0.0

real_r4 = [lg.get(4) for lg in legs_all]
print("\n== f sweep, real runner ==")
for f in (0.0, 0.10, 0.20, 0.30, 0.50, 0.75, 1.00):
    print("  f=%3d%%  %+.4f" % (round(f * 100), mean_at(f, real_r4)))
a0, a1 = mean_at(0.0, real_r4), mean_at(1.0, real_r4)
mx = max(mean_at(i / 100, real_r4) for i in range(101))
print("linear? f=0 %.4f, f=1 %.4f, max over grid %.4f (linear => max at an endpoint)" % (a0, a1, mx))

# HONEST f=100% runner: nothing scales, so the BE trail never arms.
honest = []
for c in ctx:
    r = SL.run_ladder(c["bars"], c["ei"], c["t"]["entry"], c["t"]["stop"], c["long"],
                      (0.0, 0.0, 0.0, 1.0), c["t2_px"], trail="be", struct="swing", clock=SL.EOD)
    if r is not None:
        honest.append(r)
print("\nHONEST 100%%-runner re-simulation (weights 0/0/0/1, so no rung ever arms BE):")
print("  n=%d meanR=%+.4f win=%.2f%%" % (len(honest), sum(honest) / len(honest),
      100 * sum(1 for r in honest if r > 0) / len(honest)))
print("  report's reweighted f=100%% figure: %+.4f" % a1)
