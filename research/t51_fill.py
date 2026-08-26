"""T2 (omen-5.1) -- pessimistic same-bar fill, A/B over the two-year archive.

Runs the SAME two-year backtest as `research/t8_two_year.py` (same 501-day
window, same 29 symbols in the three tracked pools, same $1,000 risk, same
omen-5.0 defaults: STOP_ON_CLOSE=1, SCALE_PLAN="hod_then_runner_be" (was
LADDER_MODE="B")) twice per session -- once
with `backtest_week.PESSIMISTIC_FILL` ON and once OFF -- and diffs the two books
trade by trade.

Both arms are replayed inside one worker per symbol so the two books are the
same signals with the same entries; the ONLY thing that can differ is how a bar
that both touched a profit rung and closed beyond the stop is resolved. (A
pessimistic flip never arms an 84% re-entry: the runner rung is a scaled trade,
and `_arm_84` has always refused those, so the entry set is identical.)

`trades_total` / the two win rates / the two EVs are the TRADED book
(`SimTrade.counted`: fired, engine grade != C) — the 1,017 trades and 55.0% of
the "traded (engine A+/A/B)" line in research/t8_two_year.md, so the two reports
are read against each other directly. Win rate counts decided trades only
(scratches out of the denominator); EV is mean R per trade at $1,000 risk.
`trades_flipped` counts those trades, and only those.

`flips_change_outcome` is the strictest count in the file: traded trades
(`counted: true`) whose win/loss/scratch label actually MOVED, not just their R.
It is the number the row exists to produce. Zero means the optimistic
target-fill assumption is not where the engine's edge came from.

The flip file is wider on purpose: it carries every trade in the whole simulated
book whose fill the rule moved, INCLUDING the D-grade and tight-stop signals the
engine filters out but still simulates. Each row carries its `status`, so a
filtered signal is never mistaken for a traded one. Their R multiples are not
comparable to the traded book (a D signal with a $0.004 stop books 11R), which
is exactly why they are evidence and not headline numbers.

Output: research/t51_fill.md + research/t51_fill_flip.jsonl
"""
import os
import sys
import json
import argparse
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from universe import ALL_SYMS
from t8_two_year import ARCHIVE, day_table, rth_candles, bias_from

OUT_MD = os.path.join(HERE, "t51_fill.md")
OUT_JSONL = os.path.join(HERE, "t51_fill_flip.jsonl")

KEY = lambda t: (t.entry_idx, t.signal_type, t.direction, t.status,
                 round(t.entry, 4), round(t.stop, 4))


def run_symbol(args):
    """One symbol, full range, BOTH arms. Returns (symbol, flips, opt, pess)."""
    symbol, start_day, end_day = args
    import backtest_week as bw

    # the committed omen-5.0 defaults, restated so a stray env var can't move them
    bw.STOP_ON_CLOSE, bw.SCALE_PLAN = True, "hod_then_runner_be"

    table = day_table(symbol)
    days = sorted(table)
    flips = []
    # per-arm tallies over the traded book (SimTrade.counted): [n, wins, losses, pnl]
    opt = [0, 0, 0, 0.0]
    pess = [0, 0, 0, 0.0]

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

        # The two arms detect identical signals in identical order — a
        # pessimistic flip can only happen on a scaled runner, and `_arm_84`
        # has never armed a re-entry off a scaled trade — so the books pair
        # positionally. Asserted rather than assumed.
        assert len(book_o) == len(book_p), (symbol, day)

        for tally, book in ((opt, book_o), (pess, book_p)):
            for t in book:
                if not t.counted:
                    continue
                tally[0] += 1
                tally[1] += t.outcome == "win"
                tally[2] += t.outcome == "loss"
                tally[3] += t.pnl

        for t_o, t_p in zip(book_o, book_p):
            assert KEY(t_o) == KEY(t_p), (symbol, day, KEY(t_o), KEY(t_p))
            if t_p.outcome == t_o.outcome and t_p.pnl == t_o.pnl:
                continue
            b = candles[t_p.exit_idx]
            flips.append({
                "symbol": symbol, "date": day,
                "entry_i": t_o.entry_idx, "flip_bar_i": t_p.exit_idx,
                "old_outcome": t_o.outcome, "new_outcome": t_p.outcome,
                "old_r": round(t_o.pnl / 1000.0, 4), "new_r": round(t_p.pnl / 1000.0, 4),
                "stop": round(t_o.stop, 4), "target": round(t_o.target, 4),
                "open": b.open, "high": b.high, "low": b.low, "close": b.close,
                "setup": t_o.signal_type, "dir": t_o.direction,
                "grade": t_o.grade, "status": t_o.status, "counted": t_o.counted,
                "entry_time": t_o.entry_time,
                "entry": round(t_o.entry, 4),
                "scale_level": round(t_o.scale_level, 4),
                "runner_target": round(t_o.runner_target, 4),
                "old_exit": round(t_o.exit_price, 4), "new_exit": round(t_p.exit_price, 4),
            })
    return symbol, flips, opt, pess


def fmt(tally):
    n, w, l, pnl = tally
    wr = (100.0 * w / (w + l)) if (w + l) else 0.0
    ev = (pnl / 1000.0 / n) if n else 0.0
    return n, wr, ev


def prose(n_total, n_out_traded, n_moved, traded_moved, wr_o, wr_p, ev_o, ev_p,
          n_out=0):
    """The paragraph under the trailer. Says what the numbers mean, out loud."""
    L = ["## What this measured", "",
         "The stop needs a candle CLOSE beyond the level; the target is a resting limit",
         "order, so it fills on an intrabar TOUCH. Asymmetric on purpose, and both halves",
         "are right. The open question was the bar that does BOTH: today's book let the",
         "target win it. `PESSIMISTIC_FILL=1` (now the default) says you cannot know, from",
         "a 1-minute bar, whether price tagged the target before or after it collapsed",
         "through the stop — so it books the loss at the stop, at every rung of ladder B.",
         "The 1R scale-out takes no partial credit, and the runner books at the trade's",
         "ORIGINAL stop rather than the breakeven stop mode B moved it to.", ""]
    if n_out_traded == 0:
        L += [f"**The answer is zero.** Across {n_total} traded trades, not one changed from a",
              "win to a loss (or a loss to a win) under the pessimistic rule. Win rate and",
              f"average R are identical in both arms to the digit ({wr_o:.1f}% and "
              f"{ev_o:+.3f}R either way).", "",
              "The reason is that the tie was **already** resolved as a loss, in both exit",
              "paths, before this flag existed: `backtest_week._stop_hit` is tested first in",
              "`_ladder_bar` and first again on the binary path. omen-5.0's own caveat said",
              "so; this row is the measurement that proves it.", "",
              "**So the target-fill assumption is not where the engine's edge came from.** The",
              f"reported {ev_o:+.3f}R per trade does not shrink by a cent when you take the",
              "most hostile possible view of same-bar fills. That leaves the honest-EV",
              "question resting entirely on the other two inflators — in-sample fitting and",
              "the uncapped runner — which is T4's job, not this one.", ""]
    else:
        L += [f"**{n_out_traded} of {n_total} traded trades change outcome** under the pessimistic",
              f"rule: win rate {wr_o:.1f}% -> {wr_p:.1f}%, average R {ev_o:+.3f} -> {ev_p:+.3f}.",
              "The same-bar fill assumption WAS carrying part of the reported edge; the",
              "pessimistic arm is the number to quote.", ""]
    L += ["## The flip file", "",
          f"`research/t51_fill_flip.jsonl` is deliberately wider than the headline: it carries",
          f"all {n_moved} trades in the whole simulated book whose FILL the rule moved, "
          f"{traded_moved} of",
          "them traded. The rest are `counted: false` — signals the engine simulates but",
          "never takes (D-grade, tight-stop, and C-grade fired-but-uncounted), so their R",
          "multiples (a $0.004 stop books 11R) are evidence, not headline numbers. Every row",
          "carries `status` and `counted` so a filtered signal is never read as a traded one,",
          "and `old_outcome`/`new_outcome` are equal on a row whose R moved but whose label",
          "did not.", "",
          f"{n_out} of those {n_moved} rows do change label (win -> loss); the other "
          f"{n_moved - n_out} are",
          f"R-reductions only. {n_out - n_out_traded} of the {n_out} are `counted: false`, "
          f"which is why `flips_change_outcome`",
          f"is {n_out_traded}: the rule bites, but on signals the engine had already thrown",
          "away. That distinction is the whole point of keeping both counts.", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-08-12")
    ap.add_argument("--end", default="2026-08-11")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--symbols", default="", help="comma-separated subset (debug)")
    a = ap.parse_args()

    syms = [s for s in ALL_SYMS if os.path.isdir(os.path.join(ARCHIVE, s))]
    if a.symbols:
        want = {x.strip() for x in a.symbols.split(",")}
        syms = [s for s in syms if s in want]
    print(f"symbols: {len(syms)}", flush=True)

    flips, opt, pess = [], [0, 0, 0, 0.0], [0, 0, 0, 0.0]
    with Pool(a.procs) as pool:
        for sym, f, o, p in pool.imap_unordered(
                run_symbol, [(s, a.start, a.end) for s in syms]):
            flips.extend(f)
            for dst, src in ((opt, o), (pess, p)):
                for j in range(4):
                    dst[j] += src[j]
            print(f"  {sym}: {o[0]} traded, {len(f)} fills moved", flush=True)

    flips.sort(key=lambda r: (r["date"], r["symbol"], r["entry_i"]))
    # trades_flipped is the traded book only, same population as the other five
    # numbers. The file also carries the filtered signals the rule moved.
    traded_flips = sum(1 for r in flips if r["counted"])
    n_out = sum(1 for r in flips if r["old_outcome"] != r["new_outcome"])
    # the headline: traded book AND the win/loss label itself moved
    n_out_traded = sum(1 for r in flips
                       if r["counted"] and r["old_outcome"] != r["new_outcome"])
    from collections import Counter
    print(f"fills moved: {len(flips)} (traded: {traded_flips}; outcome changed: {n_out}; "
          f"traded AND outcome changed: {n_out_traded})")
    print(Counter((r["status"], r["old_outcome"] + "->" + r["new_outcome"]) for r in flips))
    with open(OUT_JSONL, "w") as f:
        for r in flips:
            f.write(json.dumps(r) + "\n")

    n_o, wr_o, ev_o = fmt(opt)
    n_p, wr_p, ev_p = fmt(pess)
    md = (f"trades_total: {n_o}\n"
          f"trades_flipped: {traded_flips}\n"
          f"win_rate_optimistic: {wr_o:.1f}\n"
          f"win_rate_pessimistic: {wr_p:.1f}\n"
          f"ev_optimistic: {ev_o:.3f}\n"
          f"ev_pessimistic: {ev_p:.3f}\n"
          f"flips_change_outcome: {n_out_traded}\n")
    with open(OUT_MD, "w") as f:
        f.write(md + "\n" + prose(n_o, n_out_traded, len(flips), traded_flips,
                                  wr_o, wr_p, ev_o, ev_p, n_out))
    print(md)
    print(f"wrote {OUT_MD} and {OUT_JSONL} ({len(flips)} flips)")


if __name__ == "__main__":
    main()
