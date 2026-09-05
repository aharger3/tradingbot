"""g201 refute #3, SECOND PASS -- referee F9 (research/g158_mid_candle_arms.py).

Independent re-derivation of research/g201_refute3.py, written without reusing it.
It lands on the same verdict and the same dollars; the sections it adds are the
substitution ledger, the per-session concentration of what is left, the
size-gated paired R, and the risk-denominator shrink. Report:
research/g201_refute3.md, "Second pass".

Reproduce byte-for-byte, then run a NULL CONTROL and two adversarial variants.

THE CLAIM. Resting a limit strictly after the signal bar at 25% of that bar's
own range back toward the level (MID25) pays $100/day one-trade-a-day against
the shipped CLOSE arm's $34/day.

THE SUSPECTED DEFECT. g158's CLOSE control is NOT routed through the same
harness as its MID arms. CLOSE scores the raw book rows (`universe[k]`, the
`pnl` backtest_2y booked through backtest_week.simulate_day). The MID arms
score `g80_ordertype_grid.run_trade` results -- a different ladder replay, a
re-derived 2R target measured off the NEW (smaller) risk, and
`move_stop_to_entry_bar=True`. Any difference between the two harnesses is
charged to "mid-candle". This is the same failure class the 2026-09-05 morning
report caught in `stop-placement-routed` ("a different exit model, not a
different stop").

ARMS MEASURED HERE, all on the same 8227 candidates, same book, same
one-trade-a-day walk, same size gate:

  BOOK      g158's CLOSE control verbatim (raw book rows).
  CLOSE_RT  the SAME close entry on the SAME bar, routed through
            g80.run_trade -- the harness control g158 never ran.
  MID00     THE NULL CONTROL / PLACEBO. A limit resting at frac = 0.0, i.e.
            exactly AT the signal bar's close, strictly after the signal bar.
            Zero mid-candle depth. If the mid-candle idea is what pays, this
            must land on CLOSE. If it lands on MID25, the depth is doing
            nothing and the gain is harness + selection.
  MID25     g158's headline arm, reproduced.
  MID50     g158's second arm.

VARIANT A (matched selection). g158's one-a-day walk lets a MID arm SKIP a
day's first candidate when its limit never fills and trade a later one
instead. BOOK/CLOSE can never skip. Variant A fixes the day's pick to the
first sizeable candidate under the book and prices THAT candidate under every
arm, booking $0 when the limit never filled.

VARIANT B (paired per-trade R). g90's ruling is a PAIRED figure. Same here:
mean R difference over the candidates where both arms priced.

Reads only. Writes research/g201_refute3b.json. No engine file, no mark file
is touched.

    python research/g201_refute3b.py
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import g80_ordertype_grid as G   # noqa: E402
import signal_runner as sr                     # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"
OUT_JSON = ROOT / "research" / "g201_refute3b.json"

RISK = 1000.0
BAR_PER_DAY = 397.0
SPLIT_DAY = "2025-09-01"
FRACS = (0.0, 0.25, 0.50)
ARM_NAMES = {0.0: "MID00", 0.25: "MID25", 0.50: "MID50"}


def half(day):
    return "H1" if day < SPLIT_DAY else "H2"


def resting_price(entry_close, rng, long, frac):
    return entry_close - frac * rng if long else entry_close + frac * rng


def sizeable_of(res):
    if "sizeable" in res:
        return res["sizeable"]
    return abs(res["entry"] - res["stop"]) >= sr.min_risk_floor(
        res.get("close", res["entry"]))


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    meta, allrows = book["meta"], book["trades"]
    all_days = sorted({r["day"] for r in allrows})
    n_days = meta["sessions"]

    universe = {i: r for i, r in enumerate(allrows)
                if r.get("traded") or r["status"] == "halted"}
    keys = sorted(universe, key=lambda i: (allrows[i]["day"], allrows[i]["et"],
                                           allrows[i]["sym"], i))
    cand_by_day = defaultdict(list)
    for k in keys:
        cand_by_day[allrows[k]["day"]].append(k)
    for d in cand_by_day:
        cand_by_day[d].sort(key=lambda i: (allrows[i]["et"], allrows[i]["sym"], i))
    print("book %s: %d sessions, %d candidates" % (BOOK.name, n_days, len(keys)),
          flush=True)

    priced = {"CLOSE_RT": {}}
    for f in FRACS:
        priced[ARM_NAMES[f]] = {}
    nofill = {ARM_NAMES[f]: Counter() for f in FRACS}
    nofill["CLOSE_RT"] = Counter()
    risk_book, risk_mid25 = [], []

    for n, k in enumerate(keys):
        if n and n % 2000 == 0:
            print("   %d / %d" % (n, len(keys)), flush=True)
        r = universe[k]
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        i = r["entry_i"]
        if not bars or i >= len(bars):
            for a in nofill:
                nofill[a]["no_bars"] += 1
            continue
        cutoff = G.cutoff_idx(bars)
        rng = bars[i].high - bars[i].low

        # ---- CLOSE_RT: the book's own close entry, through THIS harness ----
        if i < len(bars) - 1:
            res = G.run_trade(r, bars, i, r["entry"], pdh, pdl, pmh, pml,
                              move_stop_to_entry_bar=True)
            if res is None:
                nofill["CLOSE_RT"]["risk_collapsed"] += 1
            else:
                priced["CLOSE_RT"][k] = res
                risk_book.append(res["risk"])
        else:
            nofill["CLOSE_RT"]["signal_bar_is_last"] += 1

        if rng <= 0 or i + 1 >= min(cutoff, len(bars) - 1):
            for f in FRACS:
                nofill[ARM_NAMES[f]]["no_bars_after_signal"] += 1
            continue

        long = r["dir"] == "call"
        entry_close = r["entry"]
        for f in FRACS:
            nm = ARM_NAMES[f]
            px = resting_price(entry_close, rng, long, f)
            j, fillpx = G.limit_touch(bars, px, long, i + 1, cutoff)
            if j is None:
                nofill[nm]["limit_never_touched"] += 1
                continue
            if j >= len(bars) - 1:
                nofill[nm]["filled_on_last_bar"] += 1
                continue
            res = G.run_trade(r, bars, j, fillpx, pdh, pdl, pmh, pml,
                              move_stop_to_entry_bar=True)
            if res is None:
                nofill[nm]["risk_collapsed"] += 1
                continue
            priced[nm][k] = res
            if f == 0.25:
                risk_mid25.append(res["risk"])

    # ------------------------------------------------- g158's own day walk
    def oneaday_for(rows_by_key, day_filter=None):
        picked = []
        for d in sorted(cand_by_day):
            if day_filter and not day_filter(d):
                continue
            for k in cand_by_day[d]:
                res = rows_by_key.get(k)
                if res is None:
                    continue
                if sizeable_of(res):
                    picked.append(res)
                    break
        return picked

    # --------------------------------- VARIANT A: fixed pick, $0 on no-fill
    fixed_pick = {}
    for d in sorted(cand_by_day):
        for k in cand_by_day[d]:
            if sizeable_of(universe[k]):
                fixed_pick[d] = k
                break

    def fixed_arm(rows_by_key, day_filter=None):
        picked = []
        for d, k in fixed_pick.items():
            if day_filter and not day_filter(d):
                continue
            res = rows_by_key.get(k)
            if res is not None and sizeable_of(res):
                picked.append(res)
        return picked

    def days_in_half(h):
        return [d for d in all_days if half(d) == h]

    def score(name, rows, tag, out):
        full = rows(None)
        h1 = rows(lambda d: half(d) == "H1")
        h2 = rows(lambda d: half(d) == "H2")
        st = G.price(full, n_days, all_days)
        s1 = G.price(h1, len(days_in_half("H1")), days_in_half("H1"))
        s2 = G.price(h2, len(days_in_half("H2")), days_in_half("H2"))
        out[name] = {"combined": st, "H1": s1, "H2": s2,
                     "pct_of_bar": round(st["per_day"] / BAR_PER_DAY * 100, 1)}
        print("  [%s] %-9s $%5d/day  H1 $%5d  H2 $%5d  meanR %+.3f  %d/%d green  n=%d"
              % (tag, name, st["per_day"], s1["per_day"], s2["per_day"],
                 st["mean_r"], st["months_green"], st["months"], st["trades"]),
              flush=True)

    book_rows = {k: universe[k] for k in keys}
    g158_arms, fixed_arms = {}, {}

    print("")
    print("-- g158's own one-a-day walk (a MID arm may SKIP a non-filling candidate)")
    score("BOOK", lambda f: oneaday_for(book_rows, f), "g158", g158_arms)
    score("CLOSE_RT", lambda f: oneaday_for(priced["CLOSE_RT"], f), "g158", g158_arms)
    for fr in FRACS:
        score(ARM_NAMES[fr], lambda f, nm=ARM_NAMES[fr]: oneaday_for(priced[nm], f),
              "g158", g158_arms)

    print("")
    print("-- VARIANT A: day's pick FIXED to the book's first sizeable candidate;"
          " $0 booked when the limit never filled")
    score("BOOK", lambda f: fixed_arm(book_rows, f), "fixed", fixed_arms)
    score("CLOSE_RT", lambda f: fixed_arm(priced["CLOSE_RT"], f), "fixed", fixed_arms)
    for fr in FRACS:
        score(ARM_NAMES[fr], lambda f, nm=ARM_NAMES[fr]: fixed_arm(priced[nm], f),
              "fixed", fixed_arms)

    # ------------------------------------------ VARIANT B: paired per-trade R
    def paired(a, b, gate=False):
        ka = book_rows if a == "BOOK" else priced[a]
        kb = book_rows if b == "BOOK" else priced[b]
        both = [k for k in keys if k in ka and k in kb]
        if gate:
            both = [k for k in both if sizeable_of(ka[k]) and sizeable_of(kb[k])]
        d = [ka[k]["r"] - kb[k]["r"] for k in both]
        if len(d) < 2:
            return None
        m = statistics.mean(d)
        se = statistics.stdev(d) / len(d) ** 0.5
        return {"n": len(both), "mean_diff_r": round(m, 4),
                "ci95": [round(m - 1.96 * se, 4), round(m + 1.96 * se, 4)]}

    pairs = {}
    for a, b in (("MID25", "BOOK"), ("MID25", "CLOSE_RT"), ("MID50", "CLOSE_RT"),
                 ("MID00", "CLOSE_RT"), ("CLOSE_RT", "BOOK")):
        pairs["%s_minus_%s" % (a, b)] = paired(a, b)
        pairs["%s_minus_%s__SIZE_GATED" % (a, b)] = paired(a, b, gate=True)
    print("")
    print("-- VARIANT B: paired per-trade R over candidates both arms priced")
    for k2, v in pairs.items():
        print("  %-34s n=%5d  %+0.4fR  CI95 [%+0.4f, %+0.4f]"
              % (k2, v["n"], v["mean_diff_r"], v["ci95"][0], v["ci95"][1]),
              flush=True)

    # ------------------- where g158's headline actually comes from: the swap
    swap = {}
    for nm in ("MID00", "MID25", "MID50"):
        same = subbed = dropped = 0
        d_same = d_sub = 0.0
        for d, k0 in fixed_pick.items():
            got = None
            for k in cand_by_day[d]:
                res = priced[nm].get(k)
                if res is not None and sizeable_of(res):
                    got = (k, res)
                    break
            if got is None:
                dropped += 1
            elif got[0] == k0:
                same += 1
                d_same += got[1]["pnl"]
            else:
                subbed += 1
                d_sub += got[1]["pnl"]
        swap[nm] = {"days_same_pick": same, "days_substituted": subbed,
                    "days_no_fill_at_all": dropped,
                    "dollars_from_same_pick": round(d_same, 0),
                    "dollars_from_substituted": round(d_sub, 0),
                    "per_day_from_substituted": round(d_sub / n_days, 0)}
    print("")
    print("-- WHERE THE HEADLINE COMES FROM: days the arm swapped to a later candidate")
    for nm, v in swap.items():
        print("  %-6s same=%3d  SUBSTITUTED=%3d  nofill=%3d  $ from swaps=%+8d "
              "(=$%+d/day of the arm's total)"
              % (nm, v["days_same_pick"], v["days_substituted"],
                 v["days_no_fill_at_all"], v["dollars_from_substituted"],
                 v["per_day_from_substituted"]), flush=True)

    # ---------------- concentration: is any arm's edge one or two sessions?
    conc = {}
    base = {r["day"]: r["pnl"] for r in fixed_arm(priced["CLOSE_RT"])}
    for nm in ("MID00", "MID25", "MID50"):
        rows = fixed_arm(priced[nm])
        got = {r["day"]: r["pnl"] for r in rows}
        delta = sorted(((got.get(d, 0.0) - base.get(d, 0.0)), d)
                       for d in set(base) | set(got))
        tot = sum(x for x, _ in delta)
        top = sorted(delta, key=lambda t: -abs(t[0]))[:5]
        conc[nm] = {"delta_total_vs_CLOSE_RT": round(tot, 0),
                    "delta_per_day": round(tot / n_days, 0),
                    "top5_days": [[d, round(x, 0)] for x, d in top],
                    "top1_share_pct": round(abs(top[0][0]) / abs(tot) * 100, 1)
                    if tot else 0.0,
                    "top5_share_pct": round(sum(abs(x) for x, _ in top)
                                            / abs(tot) * 100, 1) if tot else 0.0}
    print("")
    print("-- concentration of each MID arm's edge over CLOSE_RT (fixed-pick walk)")
    for nm, v in conc.items():
        print("  %-6s delta $%+d total ($%+d/day)  top-1 day = %.1f%%  top-5 = %.1f%%  %s"
              % (nm, v["delta_total_vs_CLOSE_RT"], v["delta_per_day"],
                 v["top1_share_pct"], v["top5_share_pct"],
                 [d for d, _ in v["top5_days"]]), flush=True)

    risk_stats = {
        "mean_risk_per_share_CLOSE_RT": round(statistics.mean(risk_book), 4),
        "mean_risk_per_share_MID25": round(statistics.mean(risk_mid25), 4),
        "median_risk_per_share_CLOSE_RT": round(statistics.median(risk_book), 4),
        "median_risk_per_share_MID25": round(statistics.median(risk_mid25), 4),
    }
    print("")
    print("-- risk denominator:", risk_stats, flush=True)

    out = {"book": BOOK.name, "sessions": n_days, "candidates": len(keys),
           "g158_walk": g158_arms, "variant_a_fixed_pick": fixed_arms,
           "variant_b_paired": pairs, "risk": risk_stats, "swap": swap, "concentration": conc,
           "nofill": {a: dict(c.most_common(6)) for a, c in nofill.items()}}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    main()
