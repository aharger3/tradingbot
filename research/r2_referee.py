"""R2 referee -- independent re-derivation of research/g211_reconcile_ladder.py
(builder commit 3ae279a0). Nothing here imports the builder's script; every
statistic is recomputed from the stamped books in research/tape/ with local
code, on the unit the report names (every traded signal, status=="fired",
$1,000 risk/trade).

Checks, in order:
  1. Re-derive $/day, mean R, win rate, avg win, avg loss, green months for
     every forward step straight off its own book. Compare to the report.
  2. The biggest-step claim (step 1 -> step 2) re-run alone: paired match on
     (sym, day, entry_time, side, setup), entry-price identity, and a
     decomposition of the R delta into win-side / loss-side.
  3. Stamp diff between the two books of the biggest step: which stamped flags
     actually differ.
  4. fwd vs rev: are the two ladders independent evidence, or the same rows?
     (book_id equality settles it.)
  5. Is step 7 a window change? Restrict step 4's own book (SIM C, close fill,
     shipped ladder, full29) to the step-7 window and compare to step 7.
  6. Per-step, per-half sample sizes: H1 = day < 2025-09-01, H2 = day >=.
"""
import gzip
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TAPE = os.path.join(HERE, "tape")
SPLIT = "2025-09-01"
RISK = 1000.0

FWD = [
    (0, "start_next_open_blind2r_noC_no84"),
    (1, "add_C_grades"),
    (2, "swap_exit_shipped_ladder"),
    (3, "add_84_reentries"),
    (4, "switch_fill_close"),
    (5, "apply_size_gate"),
    (6, "dedupe_day_policy_shipped_noop"),
    (7, "window_500_to_498"),
    (8, "universe_29_to_11"),
]


def load(direction, n, name):
    p = os.path.join(TAPE, f"reconcile_{direction}_{n}_{name}.json.gz")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def stats(rows):
    """$/day on the unit the report names: total pnl over the count of unique
    days present in this population (the builder's generic_stats divides by
    the *candidate* population's days; for steps 0-4,7,8 kept==pop so the two
    are the same, and for step 5/6 the difference is stated separately)."""
    f = [r for r in rows if r.get("filled", True) and r.get("r") is not None]
    n = len(f)
    if not n:
        return None
    wins = sum(1 for r in f if r.get("outcome") == "win")
    losses = sum(1 for r in f if r.get("outcome") == "loss")
    dec = wins + losses
    tot_r = sum(r["r"] for r in f)
    w = [r["r"] for r in f if r["r"] > 0]
    l = [r["r"] for r in f if r["r"] <= 0]
    bym = defaultdict(float)
    for r in f:
        bym[r["day"][:7]] += r["r"]
    days = len({r["day"] for r in f})
    tot_pnl = sum(r["pnl"] for r in f)
    # 95% CI on mean R
    mu = tot_r / n
    var = sum((r["r"] - mu) ** 2 for r in f) / (n - 1) if n > 1 else 0.0
    se = (var / n) ** 0.5
    return dict(n=n, wr=100.0 * wins / dec if dec else None,
                mean_r=mu, ci=1.96 * se,
                avg_win=sum(w) / len(w) if w else None,
                avg_loss=sum(l) / len(l) if l else None,
                months=len(bym), green=sum(1 for v in bym.values() if v > 0),
                days=days, pnl=tot_pnl, dd=tot_pnl / days if days else None)


def line(tag, s):
    if s is None:
        return f"{tag}: EMPTY"
    return (f"{tag}: n={s['n']} wr={s['wr']:.1f}% meanR={s['mean_r']:+.4f}"
            f" (+/-{s['ci']:.4f}) aw={s['avg_win']:+.4f} al={s['avg_loss']:+.4f}"
            f" green={s['green']}/{s['months']} days={s['days']}"
            f" $/day={s['dd']:,.2f}")


def key(r, shift=0):
    """Steps 0-6 use this script's schema (entry_time HH:MM:SS, side=put/call);
    steps 7-8 carry research/bt2y_trades_retest_on.json's ORIGINAL schema
    (et HH:MM, dir=put/call, side='S'/'L') -- itself the first hard evidence
    that step 7 swaps the substrate, not the window.

    `shift` shifts the minute, because SIM A stamps a next_open trade with the
    SIGNAL bar's minute while SIM B (entry_fill) stamps it with the FILL bar's
    minute -- the same trade, one minute apart in the two books."""
    t = (r.get("entry_time") or r.get("et") or "")[:5]
    if shift:
        h, m = int(t[:2]), int(t[3:5])
        m += shift
        h += m // 60
        t = "%02d:%02d" % (h % 24, m % 60)
    d = r.get("dir") or r.get("side") or ""
    return (r["sym"], r["day"], t, d, r.get("setup", ""))


def main():
    out = []
    P = out.append

    books = {}
    for n, name in FWD:
        books[n] = load("fwd", n, name)

    P("=== 1. INDEPENDENT RE-DERIVATION, FORWARD LADDER ===")
    P("unit: every traded signal in the book (status=='fired'), $1,000 risk/trade,")
    P("$/day = sum(pnl) / unique days present in the book.")
    for n, name in FWD:
        d = books[n]
        s = stats(d["trades"])
        P(f"  step {n} {name} [{d['meta']['fill']}/{d['meta']['exit_plan']}/"
          f"{d['meta']['pool']}] " + line("", s))

    P("")
    P("=== 1b. HALVES (H1 day < %s, H2 day >= %s) ===" % (SPLIT, SPLIT))
    for n, name in FWD:
        rows = books[n]["trades"]
        h1 = [r for r in rows if r["day"] < SPLIT]
        h2 = [r for r in rows if r["day"] >= SPLIT]
        s1, s2 = stats(h1), stats(h2)
        P(f"  step {n} {name}")
        P("    " + line("H1", s1))
        P("    " + line("H2", s2))

    P("")
    P("=== 2. THE BIGGEST-STEP CLAIM, RE-RUN ALONE (step 1 -> step 2) ===")
    b1, b2 = books[1]["trades"], books[2]["trades"]
    s1, s2 = stats(b1), stats(b2)
    P("  " + line("step1 (next_open / blind_2R)", s1))
    P("  " + line("step2 (next_open / shipped_ladder)", s2))
    P(f"  delta $/day = {s2['dd'] - s1['dd']:,.2f}  (report claims -5,550)")
    P(f"  delta meanR = {s2['mean_r'] - s1['mean_r']:+.4f}")
    P(f"  delta green = {s1['green']}/{s1['months']} -> {s2['green']}/{s2['months']}")

    # adjacent deltas, all steps -- is step 1->2 really the biggest?
    P("")
    P("  adjacent $/day deltas across the whole forward ladder:")
    dds = [(n, stats(books[n]["trades"])["dd"]) for n, _ in FWD]
    for (na, da), (nb, db) in zip(dds, dds[1:]):
        P(f"    {na} -> {nb}: {da:,.0f} -> {db:,.0f}  delta {db - da:+,.0f}")

    # pairing -- SIM A stamps the signal bar's minute, SIM B the fill bar's,
    # so the same next_open trade sits one minute apart in the two books.
    k1 = defaultdict(list)
    for r in b1:
        k1[key(r, shift=1)].append(r)
    k2 = defaultdict(list)
    for r in b2:
        k2[key(r)].append(r)
    shared = set(k1) & set(k2)
    only1 = set(k1) - set(k2)
    only2 = set(k2) - set(k1)
    P("")
    P(f"  keys (sym,day,minute+1,dir,setup): step1={len(k1)} step2={len(k2)}"
      f" shared={len(shared)} only-in-1={len(only1)} only-in-2={len(only2)}")

    entry_same = entry_diff = 0
    stop_same = stop_diff = 0
    dr = []
    for k in shared:
        a, b = k1[k][0], k2[k][0]
        if abs((a.get("entry") or 0) - (b.get("entry") or 0)) < 1e-6:
            entry_same += 1
        else:
            entry_diff += 1
        if abs((a.get("stop") or 0) - (b.get("stop") or 0)) < 1e-6:
            stop_same += 1
        else:
            stop_diff += 1
        if a.get("r") is not None and b.get("r") is not None:
            dr.append((a["r"], b["r"]))
    P(f"  entry price identical on shared keys: {entry_same} same / {entry_diff} different"
      f"  -> {'FILL UNCHANGED' if entry_diff == 0 else 'FILL ALSO MOVED'}")
    P(f"  stop  price identical on shared keys: {stop_same} same / {stop_diff} different")

    if dr:
        tot = sum(b - a for a, b in dr)
        P(f"  paired mean R change over {len(dr)} matched trades:"
          f" {tot / len(dr):+.4f}R/trade")
        # decompose by what the trade did under the OLD exit
        oldwin = [(a, b) for a, b in dr if a > 0]
        oldloss = [(a, b) for a, b in dr if a <= 0]
        P(f"    trades the flat 2R exit WON  ({len(oldwin)}): mean"
          f" {sum(a for a, b in oldwin)/len(oldwin):+.4f}R ->"
          f" {sum(b for a, b in oldwin)/len(oldwin):+.4f}R"
          f"  (contributes {sum(b-a for a,b in oldwin)/len(dr):+.4f}R/trade)")
        P(f"    trades the flat 2R exit LOST ({len(oldloss)}): mean"
          f" {sum(a for a, b in oldloss)/len(oldloss):+.4f}R ->"
          f" {sum(b for a, b in oldloss)/len(oldloss):+.4f}R"
          f"  (contributes {sum(b-a for a,b in oldloss)/len(dr):+.4f}R/trade)")
        worse_than_1r_old = sum(1 for a, b in dr if a < -1.0001)
        worse_than_1r_new = sum(1 for a, b in dr if b < -1.0001)
        P(f"    per-fill R worse than -1.000R: step1={worse_than_1r_old}"
          f" step2={worse_than_1r_new}"
          f"  -> the STOP model changed too, not only the target"
          if worse_than_1r_new != worse_than_1r_old else
          f"    per-fill R worse than -1.000R: step1={worse_than_1r_old}"
          f" step2={worse_than_1r_new}")

    P("")
    P("=== 3. STAMP DIFF, step 1 vs step 2 (only the changed variable may differ) ===")
    f1 = books[1]["meta"]["stamp"]["flags"]
    f2 = books[2]["meta"]["stamp"]["flags"]
    diffs = [(k, f1.get(k), f2.get(k)) for k in sorted(set(f1) | set(f2))
             if f1.get(k) != f2.get(k)]
    if not diffs:
        P("  NO stamped flag differs between the two books -- the stamps cannot")
        P("  distinguish them. Both stamps were written in the MAIN process, which")
        P("  never set ENTRY_FILL or OMEN_SCALE_PLAN; the worker processes did.")
    for k, a, b in diffs:
        P(f"  {k}: {a!r} -> {b!r}")
    P(f"  stamp claims ENTRY_FILL={f1.get('entry_fill.ENTRY_FILL')!r} for a book whose"
      f" meta.fill={books[1]['meta']['fill']!r}")
    P(f"  stamp claims SCALE_PLAN={f1.get('backtest_week.SCALE_PLAN')!r} for a book whose"
      f" meta.exit_plan={books[1]['meta']['exit_plan']!r}")
    P(f"  stamp git commit = {books[1]['meta']['stamp']['git']['commit'][:8]}"
      f", dirty_py_count = {books[1]['meta']['stamp']['git']['dirty_py_count']}")

    P("")
    P("=== 4. IS THE REVERSE LADDER INDEPENDENT EVIDENCE? ===")
    same = 0
    for n, name in FWD:
        rv = load("rev", 8 - n, name)
        fid = books[n]["meta"]["stamp"].get("book_id")
        rid = rv["meta"]["stamp"].get("book_id")
        eq = (fid == rid)
        same += eq
        P(f"  fwd_{n} book_id {str(fid)[:12]}  ==  rev_{8-n} book_id {str(rid)[:12]}"
          f"  -> {'IDENTICAL ROWS' if eq else 'different'}")
    P(f"  {same}/9 reverse books hold byte-identical trade sets to their forward twin.")

    P("")
    P("=== 5. IS STEP 7 A WINDOW CHANGE? ===")
    w7 = books[7]["meta"]["window"]
    P(f"  step 6 window {books[6]['meta']['window']}  ->  step 7 window {w7}")
    s4 = books[4]["trades"]                      # SIM C, close, ladder, full29, wide
    s4w = [r for r in s4 if w7["start"] <= r["day"] <= w7["end"]]
    s7 = books[7]["trades"]
    P(f"  step 4 (same fill/exit/pool, own simulation) restricted to step 7's window:"
      f" {len(s4w)} rows")
    P(f"  step 7's book itself: {len(s7)} rows"
      f"  -> {'consistent' if abs(len(s4w)-len(s7)) < 0.02*len(s7) else 'NOT THE SAME POPULATION'}")
    st4 = stats(s4w)
    st7 = stats(s7)
    P("    " + line("step4 restricted to step7 window", st4))
    P("    " + line("step7 as published", st7))
    ks4 = {key(r) for r in s4w}
    ks7 = {key(r) for r in s7}
    P(f"    shared keys {len(ks4 & ks7)}, only in step4-restricted {len(ks4 - ks7)},"
      f" only in step7 {len(ks7 - ks4)}")
    P(f"    -> {100.0*len(ks4 & ks7)/max(1,len(ks7)):.1f}% of step 7's trades also exist"
      f" in step 6/4's own simulation over the same days.")
    P(f"    days: step4-restricted {len({r['day'] for r in s4w})},"
      f" step7 {len({r['day'] for r in s7})}")
    # what a pure window change would actually cost
    d6 = books[6]["trades"]
    d6w = [r for r in d6 if w7["start"] <= r["day"] <= w7["end"]]
    P("    A PURE window change, applied to step 6's own book (the only honest"
      " reading of 'window 500 -> 498'):")
    P("      " + line("step6 restricted to step7's window", stats(d6w)))
    P(f"      i.e. the window alone is worth"
      f" {stats(d6w)['dd'] - stats(d6)['dd']:+,.2f}/day, not"
      f" {st7['dd'] - stats(d6)['dd']:+,.2f}/day.")
    P("  NOTE: step 7's rows come from research/bt2y_trades_retest_on.json --")
    P("  a DIFFERENT book, built 2026-09-02 at a different commit. Its stamp of")
    P("  record is not the one written into this step's meta.")

    P("")
    P("=== 6. STEP 5/6 $/day DENOMINATOR ===")
    P("  the builder divides step 5/6 pnl by step 4's day count, not step 5's.")
    s5 = books[5]["trades"]
    d4 = len({r["day"] for r in books[4]["trades"]})
    d5 = len({r["day"] for r in s5})
    p5 = sum(r["pnl"] for r in s5 if r.get("r") is not None)
    P(f"  step5 pnl {p5:,.0f}; days-in-step5={d5}, days-in-step4={d4}")
    P(f"  $/day on step5's own days = {p5/d5:,.2f}; on step4's days = {p5/d4:,.2f}"
      f"  (report prints -812)")

    txt = "\n".join(out)
    print(txt)
    with open(os.path.join(HERE, "r2_referee_output.txt"), "w", encoding="utf-8") as f:
        f.write(txt + "\n")


if __name__ == "__main__":
    main()
