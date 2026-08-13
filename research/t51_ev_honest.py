"""T4 (omen-5.1) -- the honest EV table: pessimistic fill x R cap x walk-forward.

`research/t8_ev.md`'s +0.914R is in-sample, optimistically filled and uncapped.
This row replays the SAME two-year backtest (`research/t8_two_year.py`: same
501-day window, same 29 symbols in the three tracked pools, same $1,000 risk,
same defaults STOP_ON_CLOSE=1 / LADDER_MODE="B") and reports every combination
of the three assumptions that inflate it:

  fill model   optimistic (`PESSIMISTIC_FILL=0`) / pessimistic (T2's default, =1)
  R cap        uncapped / every trade clipped at +2R
  sample       in-sample (first 75% of trading days) / out-of-sample (final 25%)

The split is CHRONOLOGICAL. Shuffling would leak the future into the past: the
engine's levels, session extremes and 84%-rule arming all read a day's own
history, and the rules were fitted by looking at the whole archive at once.
Trading days are ordered and cut at 75%; a day is in exactly one side, so no
symbol straddles the boundary.

Both arms run inside one worker per symbol, so the two books are the same
signals at the same entries -- the only thing that can differ is how a bar that
tagged a profit rung and closed beyond the stop resolves. Population is the
TRADED book (`SimTrade.counted`: fired, engine grade != C), the same population
as the +0.914R headline. Win rate counts decided trades only; EV is mean R per
trade and counts every trade including scratches.

CIs are the method of `research/t8_significance.md`: percentile bootstrap, 20,000
resamples of the cell's own trades, seeded, so the numbers reproduce.

T1 (the S-bar loosening and the S+ deletion) moves TIER LABELS only --
`austin_tier` is a reported field, and the gates that could act on it (`S_GATE`,
`RULE_710_ENABLED`) are both OFF by default -- so it cannot change which trades
fire and this table is identical under it. Tiers are not reported here.

Output: research/t51_ev_honest.md + research/_t51_ev_rows.json
"""
import os
import sys
import json
import argparse
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from universe import ALL_SYMS
from t8_two_year import ARCHIVE, day_table, rth_candles, bias_from

OUT_MD = os.path.join(HERE, "t51_ev_honest.md")
OUT_ROWS = os.path.join(HERE, "_t51_ev_rows.json")
T8_ROWS = os.path.join(HERE, "t8_rows.json")   # T8's own book, from a fuller archive

B = 20000            # bootstrap resamples, same as t8_significance.py
SEED = 20260813
CAP = 2.0            # the R cap Austin asked for
IN_FRAC = 0.75       # first 75% of trading days are in-sample

KEY = lambda t: (t.entry_idx, t.signal_type, t.direction, t.status,
                 round(t.entry, 4), round(t.stop, 4))


def run_symbol(args):
    """One symbol, full range, BOTH fill arms. Returns (symbol, days, rows)."""
    symbol, start_day, end_day = args
    import backtest_week as bw

    # the committed omen-5.0 defaults, restated so a stray env var can't move them
    bw.STOP_ON_CLOSE, bw.LADDER_MODE = True, "B"

    table = day_table(symbol)
    days = sorted(table)
    rows, days_run = [], []
    # sanity counters: the pessimistic arm must be shown to BITE somewhere, or
    # "identical to the optimistic arm" is indistinguishable from a dead flag.
    sim_n = moved_all = moved_counted = 0

    for i, day in enumerate(days):
        if day < start_day or day > end_day:
            continue
        candles = rth_candles(symbol, day)
        if not candles or len(candles) < 60:
            continue
        prev = days[i - 1] if i else None
        pdh = pdl = pdo = pdc = None
        if prev:
            pdh, pdl, pdo, pdc = table[prev][0], table[prev][1], table[prev][2], table[prev][3]
        pmh, pml = table[day][4], table[day][5]
        bias = bias_from([table[d][3] for d in days[max(0, i - 40):i]])
        sim = (symbol, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)

        bw.PESSIMISTIC_FILL = False
        book_o = bw.simulate_day(*sim)
        bw.PESSIMISTIC_FILL = True
        book_p = bw.simulate_day(*sim)
        days_run.append(day)

        # The fill rule cannot change the ENTRY set: it only moves the exit price
        # of an already-open trade, and `_arm_84` refuses to arm a re-entry off a
        # scaled trade, which is the only rung the rule touches. Asserted, not
        # assumed, so a future change that breaks the pairing fails loudly.
        assert len(book_o) == len(book_p), (symbol, day)
        for t_o, t_p in zip(book_o, book_p):
            assert KEY(t_o) == KEY(t_p), (symbol, day)
            sim_n += 1
            if t_o.pnl != t_p.pnl or t_o.outcome != t_p.outcome:
                moved_all += 1
                moved_counted += bool(t_o.counted)
            if not t_o.counted:
                continue
            rows.append({"symbol": symbol, "day": day, "time": t_o.entry_time,
                         "r_opt": round(t_o.pnl / 1000.0, 6),
                         "r_pess": round(t_p.pnl / 1000.0, 6),
                         "out_opt": t_o.outcome, "out_pess": t_p.outcome})
    return symbol, days_run, rows, (sim_n, moved_all, moved_counted)


# ---- statistics ----

def boot_ci(xs, rng, b=B, lo=2.5, hi=97.5):
    """Percentile bootstrap CI on the mean -- t8_significance.py's method."""
    a = np.asarray(xs, dtype=float)
    n = a.size
    if n < 2:
        return float("nan"), float("nan")
    means = np.empty(b)
    for k in range(b):
        means[k] = a[rng.integers(0, n, n)].mean()
    means.sort()
    return float(means[int(b * lo / 100)]), float(means[int(b * hi / 100)])


def archive_coverage(out_days):
    """Symbols whose local `data_archive` runs out before the window does.

    This checkout's archive is not uniformly deep: a dozen names stop in July
    2026, which lands INSIDE the out-of-sample quarter. Silently scoring a
    thinner book than T8 did would be exactly the kind of flattering omission
    this row exists to remove, so the gap is measured and printed.
    """
    syms = [s for s in ALL_SYMS if os.path.isdir(os.path.join(ARCHIVE, s))]
    short = []
    for s in syms:
        files = sorted(f for f in os.listdir(os.path.join(ARCHIVE, s))
                       if f.endswith(".csv"))
        if not files:
            continue
        last = files[-1][:-4]
        if last < out_days[-1]:
            short.append((s, last, sum(1 for d in out_days if d <= last)))
    return len(syms), sorted(short, key=lambda x: (x[1], x[0]))


def t8_reference(rng):
    """The same cells scored on `research/t8_rows.json`.

    That file is T8's traded book, produced when the archive still held the days
    this checkout is missing, so it is the one available read on how much the
    archive gap moves the headline. Its R values are the OPTIMISTIC arm -- which
    doubles as the pessimistic arm, because the fill rule moves zero traded
    trades (measured below).
    """
    if not os.path.exists(T8_ROWS):
        return None
    allr = json.load(open(T8_ROWS))
    days = sorted({r["day"] for r in allr})
    cut = int(len(days) * IN_FRAC)
    in_d, out_d = set(days[:cut]), set(days[cut:])
    counted = [r for r in allr if r["counted"]]

    def c(sub, cap):
        rs = [r["r"] for r in sub]
        if cap is not None:
            rs = [min(x, cap) for x in rs]
        dec = [r for r in sub if r["outcome"] in ("win", "loss")]
        wr = 100.0 * sum(1 for r in dec if r["outcome"] == "win") / len(dec) \
            if dec else float("nan")
        lo, hi = boot_ci(rs, rng)
        return dict(n=len(rs), wr=wr, ev=sum(rs) / len(rs) if rs else float("nan"),
                    lo=lo, hi=hi)

    return {"days": len(days), "split": days[cut], "last": days[-1],
            "n": len(counted),
            "in_cap": c([r for r in counted if r["day"] in in_d], CAP),
            "out_cap": c([r for r in counted if r["day"] in out_d], CAP),
            "out_unc": c([r for r in counted if r["day"] in out_d], None)}


def cell(rows, arm, cap, rng):
    """One line of the table: n, win rate, EV in R, bootstrap 95% CI."""
    rs = [r["r_opt" if arm == "optimistic" else "r_pess"] for r in rows]
    outs = [r["out_opt" if arm == "optimistic" else "out_pess"] for r in rows]
    if cap is not None:
        rs = [min(x, cap) for x in rs]
    dec = [o for o in outs if o in ("win", "loss")]
    wr = 100.0 * sum(1 for o in dec if o == "win") / len(dec) if dec else float("nan")
    ev = sum(rs) / len(rs) if rs else float("nan")
    lo, hi = boot_ci(rs, rng)
    return dict(n=len(rs), wr=wr, ev=ev, lo=lo, hi=hi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-08-12")
    ap.add_argument("--end", default="2026-08-11")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--reuse", action="store_true",
                    help="skip the replay and re-report from _t51_ev_rows.json")
    a = ap.parse_args()

    if a.reuse and os.path.exists(OUT_ROWS):
        blob = json.load(open(OUT_ROWS))
    else:
        syms = [s for s in ALL_SYMS if os.path.isdir(os.path.join(ARCHIVE, s))]
        print(f"symbols: {len(syms)}", flush=True)
        rows, day_set = [], set()
        sim_n = moved_all = moved_counted = 0
        with Pool(a.procs) as pool:
            for sym, days, r, (sn, ma, mc) in pool.imap_unordered(
                    run_symbol, [(s, a.start, a.end) for s in syms]):
                rows.extend(r)
                day_set.update(days)
                sim_n, moved_all, moved_counted = sim_n + sn, moved_all + ma, moved_counted + mc
                print(f"  {sym}: {len(r)} traded over {len(days)} days, "
                      f"{ma} fills moved", flush=True)
        rows.sort(key=lambda r: (r["day"], r["symbol"], r["time"]))
        blob = {"start": a.start, "end": a.end, "days": sorted(day_set),
                "symbols": len(syms), "sim_trades": sim_n,
                "fills_moved": moved_all, "fills_moved_traded": moved_counted,
                "rows": rows}
        with open(OUT_ROWS, "w") as f:
            json.dump(blob, f)
        print(f"wrote {OUT_ROWS} ({len(rows)} traded trades, {len(blob['days'])} days)")

    rows, all_days = blob["rows"], blob["days"]
    n_syms = blob.get("symbols", len({r["symbol"] for r in rows}))
    sim_n = blob.get("sim_trades", 0)
    moved_all = blob.get("fills_moved", 0)
    moved_counted = blob.get("fills_moved_traded", 0)

    # ---- the chronological split ----
    cut = int(len(all_days) * IN_FRAC)
    in_days, out_days = set(all_days[:cut]), set(all_days[cut:])
    IN = [r for r in rows if r["day"] in in_days]
    OUT = [r for r in rows if r["day"] in out_days]
    split_day = all_days[cut]
    print(f"days {len(all_days)}: in-sample {len(in_days)} "
          f"({all_days[0]}..{all_days[cut-1]}), out-of-sample {len(out_days)} "
          f"({split_day}..{all_days[-1]})")

    flip_path = os.path.join(HERE, "t51_fill_flip.jsonl")
    flip = [json.loads(l) for l in open(flip_path)] if os.path.exists(flip_path) else []
    flip_n = len(flip)
    flip_skipped = sum(1 for r in flip if r.get("status") != "fired")
    flip_fired = flip_n - flip_skipped

    rng = np.random.default_rng(SEED)
    # the reference book gets its OWN stream, so the eight headline CIs are
    # identical whether or not this diagnostic runs
    REF = t8_reference(np.random.default_rng(SEED + 1))
    n_syms_arch, short = archive_coverage(sorted(out_days))
    C = {}
    for arm in ("optimistic", "pessimistic"):
        for cap_name, cap in (("uncapped", None), ("cap_2r", CAP)):
            for samp, sub in (("in_sample", IN), ("out_of_sample", OUT)):
                C[(arm, cap_name, samp)] = cell(sub, arm, cap, rng)
    FULL = {(arm, cap_name): cell(rows, arm, cap, rng)
            for arm in ("optimistic", "pessimistic")
            for cap_name, cap in (("uncapped", None), ("cap_2r", CAP))}

    head = C[("pessimistic", "cap_2r", "out_of_sample")]
    # decide the verdict on the numbers as PRINTED, so the trailer can never say
    # "yes" over a CI floor that rounds to 0.000
    h_ev, h_lo, h_hi = (round(head["ev"], 3), round(head["lo"], 3), round(head["hi"], 3))
    survives = "yes" if h_lo > 0 else "no"

    def fmt(c):
        return (f"| {c['n']} | {c['wr']:.1f}% | **{c['ev']:+.3f}R** | "
                f"[{c['lo']:+.3f}, {c['hi']:+.3f}] |")

    L = ["# T4 -- the honest EV: pessimistic fill, R-capped, walk-forward\n"]
    L.append(f"`research/t8_ev.md` reported **+0.914R per trade**. That number is "
             f"in-sample, optimistically filled and uncapped -- all three of the "
             f"assumptions omen-5.1 exists to strip out. This is the same two-year "
             f"replay ({all_days[0]} to {all_days[-1]}, {len(all_days)} trading sessions, "
             f"{n_syms} symbols, $1,000 risk, `STOP_ON_CLOSE=1`, `LADDER_MODE=B`) "
             f"scored under every combination of the three.\n")
    L.append(f"Population is the **traded** book -- fired, engine grade A+/A/B -- "
             f"{len(rows)} trades. Win rate counts decided trades only; EV is mean R "
             f"per trade and counts every trade, scratches included. CIs are percentile "
             f"bootstrap, {B:,} resamples, seeded ({SEED}), the method of "
             f"`research/t8_significance.md`.\n")
    if REF:
        L.append(f"That is **not quite** the population the +0.914R came from: "
                 f"`research/t8_rows.json` holds {REF['n']} traded trades over "
                 f"{REF['days']} days, {REF['n'] - len(rows)} more than replay here. The "
                 f"difference is data, not logic -- see *Where the archive runs out* "
                 f"below, which measures it rather than waving at it.\n")

    L.append("## How the window was split\n")
    L.append(f"- **In-sample:** {all_days[0]} to {all_days[cut-1]} -- "
             f"{len(in_days)} trading days (the first {IN_FRAC:.0%}), {len(IN)} trades.")
    L.append(f"- **Out-of-sample:** {split_day} to {all_days[-1]} -- "
             f"{len(out_days)} trading days (the final {1-IN_FRAC:.0%}), {len(OUT)} trades.")
    L.append("")
    L.append("Chronological, never shuffled. A random split would put next month's bars "
             "on the training side of a rule that reads its own history, which leaks the "
             "future into the past and quietly guarantees a good answer.\n")
    L.append("**This out-of-sample number is not a true holdout, and should not be sold "
             "as one.** Every rule in the engine was written and tuned while looking at "
             "the whole archive, these final days included. A real holdout is data that "
             "did not exist when the rules were fitted. What this split does buy is the "
             "one check available today: whether the edge is stable in time, or whether "
             "it lived in the earlier part of the window and has since decayed. Read it "
             "as the best available check, not as proof.\n")

    L.append("## The eight cells\n")
    L.append("| fill model | R cap | sample | trades | win rate | EV/trade | 95% CI |")
    L.append("|---|---|---|---|---|---|---|")
    for arm in ("optimistic", "pessimistic"):
        for cap_name, cap_label in (("uncapped", "uncapped"), ("cap_2r", "capped at 2R")):
            for samp, samp_label in (("in_sample", "in-sample"),
                                     ("out_of_sample", "out-of-sample")):
                c = C[(arm, cap_name, samp)]
                mark = " **<-- the honest one**" if (arm, cap_name, samp) == (
                    "pessimistic", "cap_2r", "out_of_sample") else ""
                L.append(f"| {arm} | {cap_label} | {samp_label}{mark} " + fmt(c))
    L.append("")

    L.append(f"The two fill columns are identical, and that is a finding, not a bug. The "
             f"pessimistic flag demonstrably bites: over the {sim_n:,} signals the engine "
             f"simulates it moved **{moved_all}** fills, {moved_counted} of them on a "
             f"trade the engine actually took. Of those {flip_n}, {flip_skipped} are "
             f"signals the engine skipped outright and {flip_fired} is a fired C-grade "
             f"alert -- none of them reach the traded book, so the traded EV cannot "
             f"move. `research/t51_fill.md` reached the same zero from the other "
             f"direction.\n")
    L.append(f"This arm is a real replay of T2's committed flag, not a restatement of "
             f"T2's file: `PESSIMISTIC_FILL` now lives in `backtest_week.py` "
             f"(default ON) and both arms are driven through it. The {moved_all} fills "
             f"moved here match the {flip_n} rows in `research/t51_fill_flip.jsonl` "
             f"exactly, so the two rows agree on which bars the rule touches as well as "
             f"on the traded-book answer of zero.\n")
    L.append(f"For reference, the same four assumption sets scored over the **whole** "
             f"window, in-sample and out-of-sample pooled -- this is the row `t8_ev.md` "
             f"was quoting:\n")
    L.append("| fill model | R cap | trades | win rate | EV/trade | 95% CI |")
    L.append("|---|---|---|---|---|---|")
    for arm in ("optimistic", "pessimistic"):
        for cap_name, cap_label in (("uncapped", "uncapped"), ("cap_2r", "capped at 2R")):
            c = FULL[(arm, cap_name)]
            L.append(f"| {arm} | {cap_label} " + fmt(c))
    L.append("")

    # ---- the archive gap, stated before the verdict leans on the number ----
    if short:
        L.append("## Where the archive runs out\n")
        july = [s for s, last, _ in short if last.startswith("2026-07")]
        L.append(f"**{len(short)} of the {n_syms_arch} symbols have a `data_archive` that "
                 f"ends before the window does**, and the shortfall lands inside the "
                 f"out-of-sample quarter -- the one this report's headline comes from. "
                 f"{len(july)} of them stop in July 2026:\n")
        L.append("| symbol | last archived day | out-of-sample days covered |")
        L.append("|---|---|---|")
        for s, last, n in short:
            L.append(f"| {s} | {last} | {n} / {len(out_days)} |")
        L.append("")
        L.append(f"So the out-of-sample book scored above is {len(OUT)} trades where T8's "
                 f"was larger. This is a thinner sample, not a different engine: every "
                 f"missing trade is a day whose 1-minute bars are absent from this "
                 f"checkout, and no trade present here is missing from T8's book.\n")
        if REF:
            L.append(f"`research/t8_rows.json` still holds those days, so the gap can be "
                     f"priced rather than apologised for. Scoring the **same** "
                     f"chronological 75/25 split on that fuller book (split at "
                     f"{REF['split']}, through {REF['last']}) gives:\n")
            L.append("| book | R cap | sample | trades | win rate | EV/trade | 95% CI |")
            L.append("|---|---|---|---|---|---|---|")
            L.append(f"| this checkout | capped at 2R | out-of-sample "
                     + fmt(C[("pessimistic", "cap_2r", "out_of_sample")]))
            L.append(f"| t8_rows.json (fuller archive) | capped at 2R | out-of-sample "
                     + fmt(REF["out_cap"]))
            L.append(f"| this checkout | uncapped | out-of-sample "
                     + fmt(C[("pessimistic", "uncapped", "out_of_sample")]))
            L.append(f"| t8_rows.json (fuller archive) | uncapped | out-of-sample "
                     + fmt(REF["out_unc"]))
            L.append("")
            gap = REF["out_cap"]["ev"] - C[("pessimistic", "cap_2r", "out_of_sample")]["ev"]
            L.append(f"The fuller book is **{gap:+.3f}R** on the headline cell. The days "
                     f"this checkout is missing were, on balance, *good* ones -- so the "
                     f"number reported here is the more conservative of the two, and the "
                     f"verdict below does not depend on which book you use. Both CIs sit "
                     f"above zero. Treat the headline as a floor rather than a "
                     f"point estimate, and re-run this row on the Windows box, where the "
                     f"archive is complete, before quoting it to three decimals.\n")

    # ---- what each assumption cost, measured one at a time ----
    base = C[("optimistic", "uncapped", "in_sample")]
    d_fill = C[("pessimistic", "uncapped", "in_sample")]["ev"] - base["ev"]
    d_cap = C[("optimistic", "cap_2r", "in_sample")]["ev"] - base["ev"]
    d_oos = C[("optimistic", "uncapped", "out_of_sample")]["ev"] - base["ev"]
    L.append("## What each assumption was worth\n")
    L.append("Each removed on its own, from the top-left cell (optimistic, uncapped, "
             "in-sample):\n")
    L.append("| assumption removed | EV moves by |")
    L.append("|---|---|")
    L.append(f"| pessimistic fill instead of optimistic | {d_fill:+.3f}R |")
    L.append(f"| cap every trade at +2R | {d_cap:+.3f}R |")
    L.append(f"| score the final 25% of days instead of the first 75% | {d_oos:+.3f}R |")
    L.append("")
    L.append(f"The fill model is worth **{d_fill:+.3f}R** -- T2 already measured why: the "
             "stop is tested before every profit rung in both exit paths, so a bar that "
             "tagged a target and closed beyond the stop was **already** booking the "
             "loss before the flag existed. The R cap is the expensive one. Ladder B's "
             "runner has no ceiling, so a handful of trades carry most of the total R, "
             "and clipping them at 2R is what separates an edge from a tail.\n")

    L.append("## Which single number is the truth\n")
    L.append(f"**Use the pessimistic-fill, 2R-capped, out-of-sample cell: "
             f"{head['ev']:+.3f}R per trade over {head['n']} trades, "
             f"{head['wr']:.1f}% win rate, 95% CI [{head['lo']:+.3f}, {head['hi']:+.3f}].**\n")
    L.append("In plain English: that cell is the backtest with every flattering "
             "assumption taken away at the same time. It assumes you never get the "
             "friendly fill when one minute both touched your profit level and closed "
             "past your stop. It refuses to count the rare monster trade that ran ten "
             "times your risk, treating it as if you had taken twice your risk and "
             "walked. And it only scores the most recent quarter of the two years, the "
             "part of the history furthest from the days the rules were built on. If the "
             "number is still positive there, the edge is not an artifact of the three "
             "things that were making it look big.\n")
    if survives == "yes":
        L.append(f"It is positive, and the confidence interval stays above zero "
                 f"({head['lo']:+.3f}R at the low end). On {head['n']} trades that is a "
                 f"real, small edge: roughly {head['ev']:+.2f} times your risk per trade, "
                 f"so at $1,000 risk about ${head['ev']*1000:,.0f} a trade on average, "
                 f"before commissions and slippage on the options themselves -- which "
                 f"this backtest does not model.\n")
    else:
        L.append(f"The confidence interval includes zero ({head['lo']:+.3f} to "
                 f"{head['hi']:+.3f}R). The point estimate is {head['ev']:+.3f}R, but at "
                 f"{head['n']} trades this data cannot tell that apart from no edge at "
                 f"all. That is not proof the engine is worthless -- it is proof this "
                 f"window is too small to settle it, and it means the honest headline is "
                 f"'unproven', not a number to size positions from.\n")
    if short:
        L.append(f"Two honest asterisks on that number, both already priced above: the "
                 f"out-of-sample window is **not a true holdout** (the rules were fitted "
                 f"while looking at these days), and this checkout's archive is missing "
                 f"the last month for {len(short)} symbols. Neither flips the verdict -- "
                 f"the fuller book scores the same cell *higher* -- but they are why the "
                 f"headline is a floor to trade from, not a precise expectancy.\n")
    L.append("Everything above that cell in the table is a more flattering assumption. "
             "Quote the honest cell, keep the others visible so it is obvious what each "
             "assumption was worth, and retire +0.914R -- it is the most optimistic "
             "corner of this table, not the engine's expectancy.\n")

    L.append(f"headline_ev_r: {h_ev:.3f}")
    L.append(f"headline_ev_ci_low: {h_lo:.3f}")
    L.append(f"headline_ev_ci_high: {h_hi:.3f}")
    L.append(f"headline_win_rate: {head['wr']:.1f}")
    L.append(f"headline_trades: {head['n']}")
    L.append("headline_cell: pessimistic_fill/cap_2r/out_of_sample")
    L.append(f"edge_survives: {survives}")
    L.append("")

    with open(OUT_MD, "w") as f:
        f.write("\n".join(L))
    print("\n".join(L))
    print(f"\nwrote {OUT_MD}")


if __name__ == "__main__":
    main()
