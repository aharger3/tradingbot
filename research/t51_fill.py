"""T2 (omen-5.1) -- pessimistic same-bar fill, A/B over the two-year archive.

Runs the SAME two-year backtest as `research/t8_two_year.py` (same 501-day
window, same 29 symbols in the three tracked pools, same $1,000 risk, same
omen-5.0 defaults: STOP_ON_CLOSE=1, LADDER_MODE="B") twice per session -- once
with `backtest_week.PESSIMISTIC_FILL` ON and once OFF -- and diffs the two books
trade by trade.

Both arms are replayed inside one worker per symbol so the two books are the
same signals with the same entries; the ONLY thing that can differ is how a bar
that both touched a profit rung and closed beyond the stop is resolved. (A
pessimistic flip never arms an 84% re-entry: the runner rung is a scaled trade,
and `_arm_84` has always refused those, so the entry set is identical.)

`trades_total` / the two win rates / the two EVs are the TRADED book
(`SimTrade.counted`: fired, engine grade != C) — the 1,047 trades and 55.5% of
the "traded (engine A+/A/B)" line in research/t8_two_year.md, so the two reports
are read against each other directly. Win rate counts decided trades only
(scratches out of the denominator); EV is mean R per trade at $1,000 risk.
`trades_flipped` counts those trades, and only those.

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
    bw.STOP_ON_CLOSE, bw.LADDER_MODE = True, "B"

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
    from collections import Counter
    print(f"fills moved: {len(flips)} (traded: {traded_flips}; outcome changed: {n_out})")
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
          f"ev_pessimistic: {ev_p:.3f}\n")
    with open(OUT_MD, "w") as f:
        f.write(md)
    print(md)
    print(f"wrote {OUT_MD} and {OUT_JSONL} ({len(flips)} flips)")


if __name__ == "__main__":
    main()
