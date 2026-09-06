"""R2 referee, PASS 3 -- independent re-derivation of commit fed8d97f's claims.

Nothing is imported from research/g211_reconcile_ladder.py. Every statistic below
is recomputed from the committed stamped books in research/tape/ with the code in
this file, and the raw-bar checks go straight to the archive.

Unit for every dollar figure printed here: every traded signal in the book
(status/`filled` true and `r` not null), $1,000 risk per trade,
$/day = sum(pnl) / distinct trading days in the population.

Usage:  python research/r2_referee_pass3.py            (books only, ~20s)
        python research/r2_referee_pass3.py --bars     (adds the raw-bar replay)
"""
import gzip
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TAPE = os.path.join(HERE, "tape")

FWD = [
    (0, "reconcile_fwd_0_start_next_open_blind2r_noC_no84"),
    (1, "reconcile_fwd_1_add_C_grades"),
    (2, "reconcile_fwd_2_swap_exit_shipped_ladder"),
    (3, "reconcile_fwd_3_add_84_reentries"),
    (4, "reconcile_fwd_4_switch_fill_close"),
    (5, "reconcile_fwd_5_apply_size_gate"),
    (6, "reconcile_fwd_6_dedupe_day_policy_shipped_noop"),
    (7, "reconcile_fwd_7_window_500_to_498"),
    (8, "reconcile_fwd_8_universe_29_to_11"),
]
SIMD = "r2ref_simd_next_open_blind2r_real_engine"


def load(name):
    p = os.path.join(TAPE, name + ".json.gz")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def stats(rows):
    f = [r for r in rows if r.get("filled", True) and r.get("r") is not None]
    n = len(f)
    if not n:
        return None
    wins = sum(1 for r in f if r.get("outcome") == "win")
    losses = sum(1 for r in f if r.get("outcome") == "loss")
    dec = wins + losses
    aw = [r["r"] for r in f if r["r"] > 0]
    al = [r["r"] for r in f if r["r"] <= 0]
    bym = defaultdict(float)
    for r in f:
        bym[r["day"][:7]] += r["r"]
    days = len({r["day"] for r in f})
    pnl = sum(r["pnl"] for r in f)
    mean_r = pnl / 1000.0 / n
    # 95% CI on mean R
    var = sum((r["r"] - mean_r) ** 2 for r in f) / (n - 1) if n > 1 else 0.0
    ci = 1.96 * (var / n) ** 0.5
    return dict(n=n, wr=100.0 * wins / dec if dec else None,
                mean_r=mean_r, ci=ci,
                avg_win=sum(aw) / len(aw) if aw else None,
                avg_loss=sum(al) / len(al) if al else None,
                months=len(bym), green=sum(1 for v in bym.values() if v > 0),
                days=days, pnl=pnl, dpd=pnl / days if days else None)


def show(tag, s):
    if s is None:
        print(f"{tag:<46} EMPTY")
        return
    print(f"{tag:<46} n={s['n']:>6}  wr={s['wr']:5.1f}%  meanR={s['mean_r']:+.4f}"
          f" +-{s['ci']:.4f}  aw={s['avg_win']:+.4f} al={s['avg_loss']:+.4f}"
          f"  green={s['green']}/{s['months']}  days={s['days']}  $/day={s['dpd']:>10,.2f}")


def main():
    print("=" * 118)
    print("A. FORWARD LADDER -- recomputed from the committed books, my own code")
    print("=" * 118)
    books = {}
    ladder = []
    for n, name in FWD:
        d = load(name)
        books[n] = d
        s = stats(d["trades"])
        ladder.append((n, name, s))
        show(f"fwd_{n} {name[17:]}", s)

    dsim = load(SIMD)
    books["D"] = dsim
    ssim = stats(dsim["trades"])
    show("SIM_D real_engine blind_2R", ssim)

    print()
    print("B. ADJACENT DELTAS ($/day) -- which step is biggest")
    for i in range(len(ladder) - 1):
        n0, nm0, s0 = ladder[i]
        n1, nm1, s1 = ladder[i + 1]
        print(f"   {n0}->{n1} {nm1[17:]:<40} {s0['dpd']:>10,.0f} -> {s1['dpd']:>10,.0f}"
              f"   delta {s1['dpd'] - s0['dpd']:>+10,.0f}")

    print()
    print("C. THE HEADLINE SPLIT (fwd_1 -> SIM D -> fwd_2)")
    s1, s2 = ladder[1][2], ladder[2][2]
    swing = s2["dpd"] - s1["dpd"]
    sub = ssim["dpd"] - s1["dpd"]
    lad = s2["dpd"] - ssim["dpd"]
    print(f"   total swing step1->step2       {swing:>+12,.2f}/day")
    print(f"   substrate leg fwd_1 -> SIM D   {sub:>+12,.2f}/day  ({100*abs(sub)/abs(swing):.1f}%)")
    print(f"   ladder    leg SIM D -> fwd_2   {lad:>+12,.2f}/day  ({100*abs(lad)/abs(swing):.1f}%)")

    print()
    print("D. HALVES -- two split rules")
    def halves(rows, mid):
        h1 = [r for r in rows if r["day"] < mid]
        h2 = [r for r in rows if r["day"] >= mid]
        return stats(h1), stats(h2)

    # rule used by the builder's script: median distinct trading day of the population
    for tag, rows in (("fwd_1", books[1]["trades"]), ("SIM_D", dsim["trades"]),
                      ("fwd_2", books[2]["trades"]), ("fwd_7", books[7]["trades"])):
        ds = sorted({r["day"] for r in rows})
        mid = ds[len(ds) // 2]
        a, b = halves(rows, mid)
        print(f"   [own-median mid={mid}] {tag:<6} H1 n={a['n']:>5} {a['months']}mo ${a['dpd']:>9,.0f}"
              f"   H2 n={b['n']:>5} {b['months']}mo ${b['dpd']:>9,.0f}")
    print()
    for tag, rows in (("fwd_1", books[1]["trades"]), ("SIM_D", dsim["trades"]),
                      ("fwd_2", books[2]["trades"])):
        a, b = halves(rows, "2025-09-01")
        print(f"   [SWARM  mid=2025-09-01] {tag:<6} H1 n={a['n']:>5} {a['months']}mo ${a['dpd']:>9,.0f}"
              f"   H2 n={b['n']:>5} {b['months']}mo ${b['dpd']:>9,.0f}")

    print()
    print("E. STAMP DIFFS")
    def flat(d, pre=""):
        out = {}
        for k, v in (d or {}).items():
            if isinstance(v, dict):
                out.update(flat(v, pre + k + "."))
            else:
                out[pre + k] = v
        return out

    def stampdiff(a, b, ta, tb):
        fa, fb = flat(a["meta"].get("stamp")), flat(b["meta"].get("stamp"))
        keys = sorted(set(fa) | set(fb))
        diffs = [(k, fa.get(k), fb.get(k)) for k in keys if fa.get(k) != fb.get(k)]
        print(f"   {ta} vs {tb}: {len(diffs)} differing stamp key(s)")
        for k, x, y in diffs:
            print(f"      {k}: {x!r} -> {y!r}")

    stampdiff(books[1], books[2], "fwd_1", "fwd_2")
    stampdiff(books[1], dsim, "fwd_1", "SIM_D")
    stampdiff(dsim, books[2], "SIM_D", "fwd_2")
    print("   fwd_1 stamp commit:", flat(books[1]["meta"].get("stamp")).get("git.commit"),
          "dirty_py:", flat(books[1]["meta"].get("stamp")).get("git.dirty_py_count"))
    print("   SIM_D stamp commit:", flat(dsim["meta"].get("stamp")).get("git.commit"),
          "dirty_py:", flat(dsim["meta"].get("stamp")).get("git.dirty_py_count"))

    print()
    print("F. PAIRING fwd_1 <-> SIM_D (substrate leg) -- is it one variable?")
    def key(r, shift=0):
        hh, mm, _ = r["entry_time"].split(":")
        m = int(hh) * 60 + int(mm) + shift
        return (r["sym"], r["day"], m, r["side"], r.get("setup"))

    a = {key(r, 1): r for r in books[1]["trades"]}
    b = {key(r, 0): r for r in dsim["trades"]}
    common = sorted(set(a) & set(b))
    print(f"   fwd_1 keys {len(a)}  SIM_D keys {len(b)}  matched {len(common)}")
    same_entry = sum(1 for k in common if abs(a[k]["entry"] - b[k]["entry"]) < 1e-9)
    same_stop = sum(1 for k in common if abs(a[k]["stop"] - b[k]["stop"]) < 1e-9)
    print(f"   identical entry price: {same_entry}/{len(common)}   identical stop: {same_stop}/{len(common)}")

    # outcome transition matrix
    trans = defaultdict(int)
    dollars = defaultdict(float)
    for k in common:
        ra, rb = a[k], b[k]
        if ra.get("r") is None or rb.get("r") is None:
            continue
        trans[(ra.get("outcome"), rb.get("outcome"))] += 1
        dollars[(ra.get("outcome"), rb.get("outcome"))] += rb["pnl"] - ra["pnl"]
    print("   outcome transition  fwd_1 -> SIM_D   (count, total $ change)")
    for k in sorted(trans, key=lambda x: -abs(dollars[x])):
        print(f"      {str(k[0]):<8} -> {str(k[1]):<8}  {trans[k]:>6}   {dollars[k]:>+14,.0f}")

    # r-value shape: how many rows are exactly the flat target / exactly -1R / neither
    def shape(rows, tag):
        f = [r for r in rows if r.get("r") is not None]
        at2 = sum(1 for r in f if abs(r["r"] - 2.0) < 0.02)
        at1 = sum(1 for r in f if abs(r["r"] + 1.0) < 0.02)
        worse = sum(1 for r in f if r["r"] < -1.02)
        print(f"   {tag}: n={len(f)}  r~+2R:{at2}  r~-1R:{at1}  worse than -1R:{worse}"
              f"  other:{len(f)-at2-at1}")
    shape(books[1]["trades"], "fwd_1")
    shape(dsim["trades"], "SIM_D")

    print()
    print("G. VERIFY ASSERTION 1 -- step 0 vs R1's next_open book, tuple for tuple")
    r1 = load("fillarms_next_open_full29")
    def tup(r):
        return (r["sym"], r["day"], r["entry_time"], round(r["entry"], 6),
                None if r.get("r") is None else round(r["r"], 6))
    s0 = sorted(tup(r) for r in books[0]["trades"])
    # R1 book: only S/A grades, no 84%, full29 -- same population step 0 claims
    r1rows = [r for r in r1["trades"] if r.get("filled", True)]
    s1r = sorted(tup(r) for r in r1rows)
    print(f"   step0 rows {len(s0)}   R1 next_open full29 rows {len(s1r)}   identical tuples: {s0 == s1r}")
    if s0 != s1r:
        print(f"      set overlap {len(set(s0) & set(s1r))}")
    try:
        r1c = load("fillarms_next_open_core11")
        s0c = sorted(tup(r) for r in books[0]["trades"] if r["sym"] in
                     {t["sym"] for t in r1c["trades"]})
        s1c = sorted(tup(r) for r in r1c["trades"] if r.get("filled", True))
        print(f"   core11: step0-filtered {len(s0c)} vs R1 {len(s1c)} identical: {s0c == s1c}")
    except Exception as e:
        print("   core11 book not readable:", e)

    print()
    print("H. VERIFY ASSERTION 2 -- step 7 vs research/bt2y_trades_retest_on.json")
    p = os.path.join(HERE, "bt2y_trades_retest_on.json")
    with open(p, "r", encoding="utf-8") as f:
        rt = json.load(f)
    meta = rt.get("meta", {})
    trades = rt.get("trades", rt if isinstance(rt, list) else [])
    fired = [t for t in trades if t.get("status") == "fired"]
    sess = meta.get("sessions")
    rt_dpd = sum(t.get("pnl", 0.0) for t in fired) / sess
    days = sorted({t["day"] for t in fired})
    print(f"   retest_on: sessions={sess} fired={len(fired)} window={days[0]}..{days[-1]}"
          f"  $/day={rt_dpd:,.2f}")
    # step 7 unsized = step 4's population inside that window
    win = (days[0], days[-1])
    s4 = [r for r in books[4]["trades"] if win[0] <= r["day"] <= win[1]]
    s4s = stats(s4)
    print(f"   step-4 rows in that window (unsized) n={s4s['n']} $/day={s4s['dpd']:,.2f}")
    gap = abs(s4s["dpd"] - rt_dpd) / abs(rt_dpd) * 100
    print(f"   gap = {gap:.1f}%  -> {'WITHIN 1%' if gap <= 1 else 'DOES NOT RECONCILE'}")
    s7s = ladder[7][2]
    gap7 = abs(s7s["dpd"] - rt_dpd) / abs(rt_dpd) * 100
    print(f"   published step 7 (sized) $/day={s7s['dpd']:,.2f}  gap {gap7:.1f}%")

    print()
    print("I. SAMPLE SIZES per step and per half (SWARM split 2025-09-01)")
    for n, name, s in ladder:
        h1, h2 = halves(books[n]["trades"], "2025-09-01")
        def f(x):
            return f"n={x['n']:>5} {x['months']}mo" if x else "EMPTY"
        flag = ""
        if s["n"] < 30 or s["months"] < 12:
            flag = "  <-- NOT ENOUGH"
        if h1 and (h1["n"] < 30 or h1["months"] < 12):
            flag += "  H1 short"
        if h2 and (h2["n"] < 30 or h2["months"] < 12):
            flag += "  H2 short"
        print(f"   step {n}: whole n={s['n']:>5} {s['months']}mo | H1 {f(h1)} | H2 {f(h2)}{flag}")

    print()
    print("J. STEP 8 pool check -- is fwd_8 really core11?")
    core = sorted({r["sym"] for r in books[8]["trades"]})
    print("   symbols in fwd_8:", core)
    try:
        sys.path.insert(0, os.path.dirname(HERE))
        from universe import CORE_SYMBOLS
        print("   universe.CORE_SYMBOLS:", sorted(CORE_SYMBOLS))
        print("   equal:", sorted(CORE_SYMBOLS) == core)
    except Exception as e:
        print("   could not import universe:", e)

    if "--bars" in sys.argv:
        bar_replay(books, dsim, a, b, common)


def bar_replay(books, dsim, a, b, common):
    """For the flipped trades (fwd_1 win -> SIM_D loss), go to the raw 1-minute
    bars and ask: did the low/high wick through the stop BEFORE any close beyond
    it, and before the +2R target was reached?  That is the report's mechanism
    claim.  If a flip is not explained that way, the substrate leg is not (only)
    the intrabar stop."""
    print()
    print("K. RAW-BAR REPLAY of the win->loss flips (the headline mechanism)")
    sys.path.insert(0, os.path.dirname(HERE))
    import data_archive
    flips = [k for k in common
             if a[k].get("outcome") == "win" and b[k].get("outcome") == "loss"]
    print(f"   flips fwd_1 win -> SIM_D loss: {len(flips)}")
    import random
    random.seed(11)
    sample = random.sample(flips, min(40, len(flips)))
    intrabar = closebeyond = neither = err = 0
    detail = []
    for k in sample:
        ra, rb = a[k], b[k]
        try:
            bars = data_archive.load_day(rb["sym"], rb["day"])
        except Exception as e:
            err += 1
            continue
        if not bars:
            err += 1
            continue
        et = rb["entry_time"][:5]
        idx = None
        for i, bar in enumerate(bars):
            t = str(bar.get("t") or bar.get("time") or "")
            if t[11:16] == et or t[:5] == et:
                idx = i
                break
        if idx is None:
            err += 1
            continue
        entry, stop = rb["entry"], rb["stop"]
        long = rb["side"] == "call"
        risk = abs(entry - stop)
        target = entry + 2 * risk if long else entry - 2 * risk
        first = None
        for bar in bars[idx + 1:]:
            lo, hi, cl = bar["l"], bar["h"], bar["c"]
            touch = (lo <= stop) if long else (hi >= stop)
            closebey = (cl <= stop) if long else (cl >= stop)
            hitt = (hi >= target) if long else (lo <= target)
            if touch and not closebey:
                first = "intrabar_touch"
                break
            if closebey:
                first = "close_beyond"
                break
            if hitt:
                first = "target_first"
                break
        if first == "intrabar_touch":
            intrabar += 1
        elif first == "close_beyond":
            closebeyond += 1
        else:
            neither += 1
            detail.append((k, first))
    print(f"   of {len(sample)} sampled flips: intrabar wick to stop first = {intrabar},"
          f" close beyond stop first = {closebeyond}, other/none = {neither}, unreadable = {err}")
    for k, f in detail[:10]:
        print("      unexplained:", k, f)


if __name__ == "__main__":
    main()
