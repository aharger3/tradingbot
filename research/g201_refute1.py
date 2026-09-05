"""g201 refute #1 -- lookahead / leakage attack on F9 (research/g158_mid_candle_arms.md).

Three independent attacks, all on the same book and the same candidate set F9 used:

 A. HARNESS CONTROL. F9's CLOSE control is the BOOK's own booked pnl; its MID arms
    are re-simulated through g80_ordertype_grid.run_trade. g80's own docstring says
    the BOOK policy exists to prove the harness reproduces the book before any other
    arm is believed -- F9 never ran it. Here CLOSE is routed through the IDENTICAL
    run_trade at the book's own entry price and entry bar (CLOSE_RT). If CLOSE_RT
    != CLOSE, F9's headline compares two harnesses, not two entries.

 B. FUTURE-CONDITIONED DAY PICK. F9's one-trade-a-day picker walks the day's
    candidates and takes the first one that HAS a result. A MID arm has no result
    when its limit never traded -- knowable only after 11:00. So on those days the
    MID arm silently picks a LATER candidate the CLOSE arm never saw. Here every arm
    is scored on the SAME pick (the day's first close-sizeable candidate); a MID arm
    whose limit never fills books $0 for that day, which is what actually happens to
    a resting order that expires.

 C. PENNY-EXACT / EPS-SLACK FILLS. g80.limit_touch fills on ``low <= lvl + EPS``
    (EPS = $0.005), so a bar whose low is up to half a cent ABOVE a buy limit still
    fills, and a bar that touches the limit to the penny and goes no further fills.
    The same class killed `scale-before-the-level` in the 09-05 morning report. Both
    populations are counted, and a STRICT arm requiring price to trade a full cent
    THROUGH the limit is priced.

Fill convention everywhere: entry = signal-bar CLOSE for the CLOSE arms, a resting
limit touched strictly after the signal bar (i+1) for the MID arms; exits via
backtest_week._ladder_bar through g80.run_trade; stops via stop_rule/intrabar_stop;
size gate signal_runner.min_risk_floor; 1R = $1,000. H1 = day < 2025-09-01.

    python research/g201_refute1.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import g80_ordertype_grid as G   # noqa: E402
import signal_runner as sr                     # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"
OUT_JSON = ROOT / "research" / "g201_refute1.json"
SPLIT_DAY = "2025-09-01"
FRACS = (0.25, 0.50, 0.75)
NAMES = {0.25: "MID25", 0.50: "MID50", 0.75: "MID75"}
CENT = 0.01


def half(d):
    return "H1" if d < SPLIT_DAY else "H2"


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    meta, allrows = book["meta"], book["trades"]
    all_days = sorted({r["day"] for r in allrows})
    n_days = meta["sessions"]
    h1_days = [d for d in all_days if half(d) == "H1"]
    h2_days = [d for d in all_days if half(d) == "H2"]

    universe = {i: r for i, r in enumerate(allrows)
                if r.get("traded") or r["status"] == "halted"}
    keys = sorted(universe, key=lambda i: (allrows[i]["day"], allrows[i]["et"],
                                           allrows[i]["sym"], i))
    cand_by_day = defaultdict(list)
    for k in keys:
        cand_by_day[allrows[k]["day"]].append(k)
    for d in cand_by_day:
        cand_by_day[d].sort(key=lambda i: (allrows[i]["et"], allrows[i]["sym"], i))
    print("book %s  sessions=%d  candidates=%d  entry_fill=%s"
          % (BOOK.name, n_days, len(keys), meta.get("entry_fill")), flush=True)

    def close_sizeable(r):
        return abs(r["entry"] - r["stop"]) >= sr.min_risk_floor(r["entry"])

    # ---- B: the matched pick -- the day's first close-sizeable candidate.
    pick = {}
    for d in sorted(cand_by_day):
        for k in cand_by_day[d]:
            if close_sizeable(universe[k]):
                pick[d] = k
                break
    print("matched picks: %d days of %d" % (len(pick), n_days), flush=True)

    priced = {f: {} for f in FRACS}          # g158's arm (as written)
    strictd = {f: {} for f in FRACS}         # requires a full cent THROUGH
    census = {f: Counter() for f in FRACS}
    nofill = {f: Counter() for f in FRACS}
    cat_counts = defaultdict(Counter)
    close_rt = {}                            # A: CLOSE through run_trade

    for n, k in enumerate(keys):
        if n and n % 1000 == 0:
            print("   %d / %d" % (n, len(keys)), flush=True)
        r = universe[k]
        h = half(r["day"])
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        i = r["entry_i"]
        if not bars or i >= len(bars):
            continue
        long = r["dir"] == "call"
        # ---- A: CLOSE routed through the SAME harness the MID arms use.
        rt = G.run_trade(r, bars, i, r["entry"], pdh, pdl, pmh, pml,
                         move_stop_to_entry_bar=True)
        if rt is not None:
            close_rt[k] = rt

        rng = bars[i].high - bars[i].low
        cutoff = G.cutoff_idx(bars)
        if rng <= 0 or i + 1 >= min(cutoff, len(bars) - 1):
            for f in FRACS:
                nofill[f]["no_bars_after_signal"] += 1
            cat_counts[h]["never-returns"] += 1
            cat_counts["ALL"]["never-returns"] += 1
            continue

        entry_close = r["entry"]
        depth = None
        for f in FRACS:
            px = entry_close - f * rng if long else entry_close + f * rng
            j, fillpx = G.limit_touch(bars, px, long, i + 1, cutoff)
            if j is None:
                nofill[f]["limit_never_touched"] += 1
                continue
            if j >= len(bars) - 1:
                nofill[f]["filled_on_last_bar"] += 1
                continue
            depth = f
            # --- C: classify the fill bar's relationship to the limit
            ext = bars[j].low if long else bars[j].high
            slack = (ext - px) if long else (px - ext)   # >0 => never reached px
            if slack > 0:
                census[f]["eps_slack_never_reached"] += 1
            elif slack > -CENT:
                census[f]["penny_exact_touch"] += 1
            else:
                census[f]["traded_through"] += 1
            census[f]["filled"] += 1
            res = G.run_trade(r, bars, j, fillpx, pdh, pdl, pmh, pml,
                              move_stop_to_entry_bar=True)
            if res is None:
                nofill[f]["risk_collapsed"] += 1
                continue
            priced[f][k] = res
            # --- strict: require a full cent THROUGH the limit
            spx = px - CENT if long else px + CENT
            js, fps = G.limit_touch(bars, spx, long, i + 1, cutoff)
            if js is not None and js < len(bars) - 1:
                rs = G.run_trade(r, bars, js, fps, pdh, pdl, pmh, pml,
                                 move_stop_to_entry_bar=True)
                if rs is not None:
                    strictd[f][k] = rs
        cat = ("never-returns" if depth is None else
               "close-only" if depth == 0.25 else "mid-fillable")
        cat_counts[h][cat] += 1
        cat_counts["ALL"][cat] += 1

    # ------------------------------------------------------------- scoring
    def sizeable_of(res):
        if "sizeable" in res:
            return bool(res["sizeable"])
        return abs(res["entry"] - res["stop"]) >= sr.min_risk_floor(res["entry"])

    def g158_pick(rows_by_key, days):
        """F9's own picker: first candidate of the day that HAS a result."""
        out = []
        for d in days:
            for k in cand_by_day.get(d, []):
                res = rows_by_key.get(k)
                if res is not None and sizeable_of(res):
                    out.append(res)
                    break
        return out

    def matched_pick(rows_by_key, days):
        """Same candidate for every arm; no result on that candidate => $0."""
        out = []
        for d in days:
            k = pick.get(d)
            if k is None:
                continue
            res = rows_by_key.get(k)
            if res is not None and sizeable_of(res):
                out.append(res)
        return out

    close_book = {k: universe[k] for k in keys}
    arms = {}

    def score(label, rows_by_key, picker):
        full = picker(rows_by_key, all_days)
        a = G.price(full, n_days, all_days)
        b = G.price(picker(rows_by_key, h1_days), len(h1_days), h1_days)
        c = G.price(picker(rows_by_key, h2_days), len(h2_days), h2_days)
        arms[label] = {"combined": a, "H1": b, "H2": c}
        print("  %-24s $%5d/day   H1 $%5d   H2 $%5d   meanR %+.3f  %4d trades  %d/%d green"
              % (label, a["per_day"], b["per_day"], c["per_day"], a["mean_r"],
                 a["trades"], a["months_green"], a["months"]), flush=True)

    print("\n--- F9's own picker (first candidate WITH a result) ---", flush=True)
    score("CLOSE (book pnl)", close_book, g158_pick)
    score("CLOSE_RT (harness)", close_rt, g158_pick)
    for f in FRACS:
        score(NAMES[f], priced[f], g158_pick)

    print("\n--- matched pick, unfilled day = $0 ---", flush=True)
    score("M:CLOSE (book pnl)", close_book, matched_pick)
    score("M:CLOSE_RT (harness)", close_rt, matched_pick)
    for f in FRACS:
        score("M:" + NAMES[f], priced[f], matched_pick)
    for f in FRACS:
        score("M:" + NAMES[f] + "-strict", strictd[f], matched_pick)

    # ---- D: g90's paired test, replicated. Same candidate, both arms filled.
    import random
    paired = {}
    rng_b = random.Random(20260830)
    for f in FRACS:
        d = [priced[f][k]["r"] - close_rt[k]["r"] for k in priced[f]
             if k in close_rt and sizeable_of(priced[f][k]) and sizeable_of(close_rt[k])]
        if not d:
            continue
        m = sum(d) / len(d)
        boots = sorted(sum(rng_b.choices(d, k=len(d))) / len(d) for _ in range(2000))
        paired[NAMES[f]] = {"n": len(d), "mean_mid_minus_close_R": round(m, 4),
                            "ci95_low": round(boots[50], 4),
                            "ci95_high": round(boots[1949], 4)}
        print("paired %s - CLOSE_RT: %+.4fR  95%% CI [%+.4f, %+.4f]  n=%d"
              % (NAMES[f], m, boots[50], boots[1949], len(d)), flush=True)

    diverge = {}
    for f in FRACS:
        n_diff = 0
        for d in all_days:
            base = pick.get(d)
            got = None
            for k in cand_by_day.get(d, []):
                res = priced[f].get(k)
                if res is not None and sizeable_of(res):
                    got = k
                    break
            if got is not None and got != base:
                n_diff += 1
        diverge[NAMES[f]] = n_diff
    print("\ndays where F9's picker took a different candidate than CLOSE:", diverge)
    print("fill census:", {NAMES[f]: dict(census[f]) for f in FRACS})
    print("categories:", {h: dict(c) for h, c in cat_counts.items()})

    json.dump({"arms": arms,
               "paired_vs_close_rt": paired,
               "diverge_days": diverge,
               "census": {NAMES[f]: dict(census[f]) for f in FRACS},
               "nofill": {NAMES[f]: dict(nofill[f]) for f in FRACS},
               "categories": {h: dict(c) for h, c in cat_counts.items()},
               "n_days": n_days, "h1_days": len(h1_days), "h2_days": len(h2_days),
               "matched_pick_days": len(pick)},
              open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    main()
