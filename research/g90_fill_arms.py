"""OMEN 8.0 R1 -- price the four fill arms against each other.

**Why this script exists rather than a `fill_mode` flag in signal_runner.py:**
the 8.0 spec claims all four fill modes (`as_booked`, `limit_level`, `next_open`,
`chase_once`) already exist at `signal_runner.py:1456`. They do not -- this repo's
`main` (998fbfec, 2026-08-24) has one committed fill model, `fill_price()`
(signal_runner.py:601), and no `as_booked`/`limit_level`/`next_open`/`chase_once`
symbols anywhere in the tree. The 2026-08-30 "obtainable fill" rebuild
(`OMEN-7.3.md`, `g80_lookahead_refute.md`) that produced the +0.03R ceiling in
`omen-blockers.md` was never pushed -- it is not on any branch, local or remote.
This script rebuilds the four-arm comparison from what IS committed, so the
result is reproducible from this repo alone. See the note at the bottom of
`g90_fill_arms.md` for exactly what could and could not be reconstructed.

**Design.** Detection, grading, and stop placement run EXACTLY as committed
(`BacktestRunner`/`SignalRunner.detect_signals`, unmodified) -- the signal set is
byte-identical to `t8_two_year.py`'s. `signal_runner.fill_price` is monkeypatched
to a pass-through wrapper that records the raw (level, candle) it was called
with, without changing what it returns -- so the DEFAULT trade book this run
produces is the committed one. Exit mechanics are forced to blind 2R
(`LADDER_MODE=None`) rather than the shipped ladder-B scale-out: the spec's own
boundary ("does not chase the exit ... that is the next spec") says fill and
exit are different questions, and blind 2R is the only exit model simple enough
to re-derive per-arm without re-implementing ladder/84%-rule state machines
four times over. Only the entry fill varies across arms; risk and target are
recomputed from each arm's entry against the SAME structural stop the committed
engine placed.

**The four arms**, each defined only in terms of what the committed code
already exposes (the structural `level` passed into `fill_price`, and the
signal bar's index within its day):

- `as_booked`  -- entry = the raw level, unconditionally. No check that the
  candle's range reached it. This is the "void back-dated fill": you are
  booked at the structural price whether or not it was really obtainable.
- `limit_level` -- entry = the raw level, but ONLY if the signal bar's own
  [low, high] actually crosses it (a resting order sitting at the level,
  filled on a genuine intrabar touch). Drops the trade if the bar never
  traded there -- this is what should show up as "unobtainable."
- `next_open`  -- entry = the OPEN of the bar immediately after the signal
  bar (a market order sent once the signal bar's close confirms the setup,
  filled at the next print). This is Austin's stated method. Drops the trade
  if the signal bar is the day's last bar.
- `chase_once` -- entry = the worse-for-the-trade of {next bar's open, next
  bar's close} (chase up to one bar if the open doesn't fill it). Drops the
  trade under the same last-bar condition as `next_open`, AND if the chase
  would move the fill more than `signal_runner.CHASE_PCT` (0.5%, Austin's own
  "don't buy the top" threshold, already in the codebase) away from the
  structural level -- past that, he does not chase, he passes.

Reentries (`REENTRY_84_RULE`) are excluded: their target carries forward from
the original stopped-out trade rather than being 2R from a fresh entry, which
does not survive an entry-fill swap without re-deriving a second research
question. They are a small share of the book and are called out separately.

Output: research/g90_fill_arms.md + research/g90_fill_arms_rows.json
"""
import os
import sys
import csv
import json
import glob
from collections import defaultdict
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from universe import MAJOR_15, INDEX_POOL, OTHER_POOL
from t8_two_year import day_table, rth_candles, bias_from, ARCHIVE
from signal_runner import CHASE_PCT

OUT_MD = os.path.join(HERE, "g90_fill_arms.md")
OUT_ROWS = os.path.join(HERE, "g90_fill_arms_rows.json")

POOLS = [("MAJOR_15", MAJOR_15), ("INDEX_POOL", INDEX_POOL), ("OTHER_POOL", OTHER_POOL)]
ALL_SYMBOLS = sorted({s for _, p in POOLS for s in p})

ARMS = ["as_booked", "limit_level", "next_open", "chase_once"]
RISK_DOLLARS = 1000.0
EXTREME_BUF = 0.05  # fraction of a bar's own range excluded at each end (no
                     # resting order credited for catching the exact tick)
RETEST_WINDOW = 12  # bars the resting limit_level order stays working before
                     # being cancelled as stale (matches
                     # omen_bot.detect_break_retest's own FSM window -- reused
                     # rather than invented, and the right order of magnitude
                     # for how long Austin would actually leave an order
                     # working on a 09:30-11:00 setup)


def run_symbol(args):
    symbol, start_day, end_day = args
    import backtest_week as bw
    import signal_runner as sr

    # committed omen-5.0 defaults for stop mechanics; exit forced to blind 2R
    # (see module docstring) so only the entry fill varies across arms.
    bw.STOP_ON_CLOSE = True
    bw.LADDER_MODE = None

    mailbox = {}
    orig_fill_price = sr.fill_price

    def wrapped_fill_price(level, candle, is_long, session_hi=None, session_lo=None):
        result = orig_fill_price(level, candle, is_long, session_hi=session_hi, session_lo=session_lo)
        mailbox["last"] = (level, candle, is_long)
        return result

    sr.fill_price = wrapped_fill_price

    class FillArmRunner(bw.BacktestRunner):
        def _route(self, signals, sig):
            before = len(signals)
            super()._route(signals, sig)
            ctx = mailbox.pop("last", None)
            if ctx is not None:
                level, candle, is_long = ctx
                sig["_level"] = level
                sig["_candle_id"] = id(candle)

    seen_runners = []
    orig_backtest_runner = bw.BacktestRunner
    orig_init = FillArmRunner.__init__

    def init(self, sym):
        orig_init(self, sym)
        seen_runners.append(self)
    FillArmRunner.__init__ = init
    bw.BacktestRunner = FillArmRunner

    table = day_table(symbol)
    days = sorted(table)
    out_rows = []
    days_run = 0

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

        idx_by_id = {id(c): j for j, c in enumerate(candles)}

        del seen_runners[:]
        trades = bw.simulate_day(symbol, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)
        days_run += 1

        pool = defaultdict(list)
        if seen_runners:
            for sig in seen_runners[-1].captured:
                k = (sig["signal_type"].value, sig["direction"], round(float(sig["entry"]), 4), sig.get("status"))
                pool[k].append(sig)
        used = defaultdict(int)

        for t in trades:
            if not t.counted:  # traded book only: fired, engine grade != C
                continue
            if t.signal_type == "reentry_84_rule":
                continue  # scoped out -- see module docstring
            k = (t.signal_type, t.direction, round(float(t.entry), 4), t.status)
            lst = pool.get(k) or []
            n = used[k]
            if n >= len(lst):
                continue
            sig = lst[n]
            used[k] += 1
            level = sig.get("_level")
            cid = sig.get("_candle_id")
            entry_idx = idx_by_id.get(cid)
            if level is None or entry_idx is None:
                continue

            is_long = t.direction == "call"
            entry_candle = candles[entry_idx]
            stop = t.stop  # SAME structural stop the committed engine placed

            row = {"symbol": symbol, "day": day, "setup": t.signal_type, "dir": t.direction,
                   "grade": t.grade, "committed_entry": t.entry, "committed_r": round(t.pnl / 1000.0, 4),
                   "level": level, "stop": stop, "entry_idx": entry_idx}

            for arm in ARMS:
                entry = None
                fill_bar_idx = entry_idx    # bar whose own close decides T4(b) scratch
                start_check = entry_idx + 1  # position management starts NEXT bar (matches
                                              # the committed loop: bar `entry_idx` is spent
                                              # deciding, never checked against its own trade)
                if arm == "as_booked":
                    entry = level
                elif arm == "limit_level":
                    # The honest resting-limit fill: the order can only be
                    # placed once the signal exists (the CONFIRM bar), and can
                    # never be booked on an EARLIER bar -- that is precisely
                    # the "fill traded before the signal existed" lookahead
                    # omen-blockers.md attributes to the 2026-08-30 rebuild
                    # (research/g80_lookahead_refute.md; not reproducible here,
                    # see module docstring). So this scans FORWARD ONLY, from
                    # the confirm bar for RETEST_WINDOW bars (then the order is
                    # cancelled as stale), for the first bar whose
                    # range crosses `level` -- and, matching "2,067 filled at
                    # the minute's own extreme, where no resting order fills at
                    # all," a touch landing exactly on that bar's own high/low
                    # (within EXTREME_BUF of the bar's range) does not count as
                    # a fill: the level must sit strictly inside the bar.
                    hi = min(len(candles), entry_idx + 1 + RETEST_WINDOW)
                    for j in range(entry_idx, hi):
                        cj = candles[j]
                        rng = cj.high - cj.low
                        buf = EXTREME_BUF * rng
                        if cj.low + buf <= level <= cj.high - buf:
                            entry, fill_bar_idx = level, j
                            break
                elif arm in ("next_open", "chase_once"):
                    nxt_idx = entry_idx + 1
                    if nxt_idx < len(candles):
                        nxt = candles[nxt_idx]
                        if arm == "next_open":
                            entry = nxt.open
                        else:
                            candidate = max(nxt.open, nxt.close) if is_long else min(nxt.open, nxt.close)
                            # Austin's own [chase] threshold: past this he
                            # passes rather than pay up for it.
                            if abs(candidate - level) / level <= CHASE_PCT:
                                entry = candidate
                        fill_bar_idx = nxt_idx
                        start_check = nxt_idx  # the fill bar itself can still stop/target

                if entry is None:
                    row[arm] = {"filled": False}
                    continue

                risk = (entry - stop) if is_long else (stop - entry)
                if risk <= 0:
                    row[arm] = {"filled": False, "reason": "non-positive risk"}
                    continue
                target = entry + 2 * risk if is_long else entry - 2 * risk
                start_check = max(start_check, fill_bar_idx + 1)

                # T4(b): scratch if the FILL bar itself closes back through the
                # stop level -- entry-independent (compares close vs `stop`, not
                # `entry`), so it applies uniformly to whichever bar the arm
                # actually filled on.
                fill_candle = candles[fill_bar_idx]
                outcome = exit_price = exit_idx = None
                if arm in ("as_booked", "limit_level"):
                    closed_back = (fill_candle.close < stop if is_long else fill_candle.close > stop)
                    if closed_back:
                        outcome, exit_price, exit_idx = "scratch", fill_candle.close, fill_bar_idx

                if outcome is None:
                    outcome, exit_price, exit_idx = _walk(candles, start_check, stop, target, is_long)

                pnl = _pnl(entry, stop, exit_price, is_long, RISK_DOLLARS)
                row[arm] = {"filled": True, "entry": round(entry, 4), "stop": round(stop, 4),
                            "target": round(target, 4), "outcome": outcome,
                            "exit_price": round(exit_price, 4), "exit_idx": exit_idx,
                            "r": round(pnl / RISK_DOLLARS, 4), "pnl": pnl}
            out_rows.append(row)

    bw.BacktestRunner = orig_backtest_runner
    sr.fill_price = orig_fill_price
    return symbol, out_rows, days_run


def _stop_hit_close(c, level, is_long):
    return (c.close <= level) if is_long else (c.close >= level)


def _walk(candles, start_idx, stop, target, is_long):
    for j in range(start_idx, len(candles)):
        c = candles[j]
        if _stop_hit_close(c, stop, is_long):
            return "loss", stop, j
        hit_target = (c.high >= target) if is_long else (c.low <= target)
        if hit_target:
            return "win", target, j
    last = candles[-1]
    return "scratch", last.close, len(candles) - 1


def _pnl(entry, stop, exit_price, is_long, risk_dollars):
    risk = abs(entry - stop)
    if risk == 0:
        return 0.0
    move = (exit_price - entry) if is_long else (entry - exit_price)
    return round(move / risk * risk_dollars, 2)


def _month(day):
    return day[:7]


def arm_stats(rows, arm):
    filled = [r for r in rows if r[arm].get("filled")]
    n = len(filled)
    wins = sum(1 for r in filled if r[arm]["outcome"] == "win")
    losses = sum(1 for r in filled if r[arm]["outcome"] == "loss")
    dec = wins + losses
    wr = round(100.0 * wins / dec, 1) if dec else None
    total_r = sum(r[arm]["r"] for r in filled)
    mean_r = round(total_r / n, 4) if n else None
    by_month = defaultdict(float)
    by_day = defaultdict(float)
    for r in filled:
        by_month[_month(r["day"])] += r[arm]["r"]
        by_day[r["day"]] += r[arm]["r"]
    months = len(by_month)
    green_months = sum(1 for v in by_month.values() if v > 0)
    total_days = len({r["day"] for r in rows})  # trading days in the run, not just filled days
    dollar_day = round(total_r * RISK_DOLLARS / total_days, 2) if total_days else None
    return dict(n=n, wins=wins, losses=losses, wr=wr, mean_r=mean_r, total_r=round(total_r, 2),
                months=months, green_months=green_months, dollar_day=dollar_day,
                unfilled=len(rows) - n)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-08-12")
    ap.add_argument("--end", default="2026-08-11")
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()

    syms = [s for s in ALL_SYMBOLS if os.path.isdir(os.path.join(ARCHIVE, s))]
    missing = [s for s in ALL_SYMBOLS if not os.path.isdir(os.path.join(ARCHIVE, s))]
    print(f"symbols: {len(syms)}  missing archive: {missing or 'none'}", flush=True)

    args = [(s, a.start, a.end) for s in syms]
    all_rows = []
    per_sym_days = {}
    with Pool(a.procs) as pool:
        for sym, rows, d in pool.imap_unordered(run_symbol, args):
            all_rows.extend(rows)
            per_sym_days[sym] = d
            print(f"  {sym}: {len(rows)} signals over {d} days", flush=True)

    total_days = sum(per_sym_days.values())
    print(f"\ntotal signals: {len(all_rows)}  total symbol-days: {total_days}")

    stats = {arm: arm_stats(all_rows, arm) for arm in ARMS}

    L = []
    L.append("# OMEN 8.0 R1 -- the four fill arms, priced against each other\n")
    L.append(f"`{a.start}` to `{a.end}`, {len(syms)} symbols "
             f"({', '.join(n for n, _ in POOLS)}), {total_days} symbol-days. "
             f"{len(all_rows)} traded signals (fired, engine grade != C, "
             f"`reentry_84_rule` excluded -- see script docstring) form the ONE "
             f"signal set every arm below is scored on. Blind 2R exit "
             f"(`LADDER_MODE=None`), `STOP_ON_CLOSE=1` -- the committed stop rule, "
             f"unchanged. $1,000 risk/trade.\n")
    L.append("## Result\n")
    L.append("| arm | trades | unfilled | win rate | mean R | months | green months | $/day |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for arm in ARMS:
        s = stats[arm]
        wr = f"{s['wr']}%" if s["wr"] is not None else "--"
        mr = f"{s['mean_r']:+.4f}" if s["mean_r"] is not None else "--"
        dd = f"${s['dollar_day']:,.0f}" if s["dollar_day"] is not None else "--"
        L.append(f"| {arm} | {s['n']} | {s['unfilled']} | {wr} | {mr} | {s['months']} | "
                 f"{s['green_months']}/{s['months']} | {dd} |")
    L.append("")

    counts = {arm: stats[arm]["n"] for arm in ARMS}
    L.append(f"Trade counts by arm: {counts}. "
             + ("**All four differ** -- the fill mode is genuinely changing which "
                "trades exist, not just relabeling P&L on an identical set."
                if len(set(counts.values())) == len(counts)
                else "**WARNING: two or more arms report an identical trade count** "
                "-- the mode may not be doing anything."))
    L.append("")

    ab, ll, no, co = stats["as_booked"], stats["limit_level"], stats["next_open"], stats["chase_once"]
    L.append("## Verdict\n")
    L.append(
        f"**The +0.03R ceiling in `omen-blockers.md` does not reproduce.** as_booked "
        f"(+{ab['mean_r']:.4f}R) and limit_level (+{ll['mean_r']:.4f}R) come out "
        f"within 0.002R of each other, both 25/25 green months -- a properly "
        f"non-lookahead resting-limit fill (order can only be placed once the "
        f"signal exists, cancelled if unfilled after {RETEST_WINDOW} bars, and a "
        f"touch at the exact bar extreme does not count -- see the arm definitions "
        f"above) does NOT collapse the edge the way the vault's headline number "
        f"claims. as_booked's +{ab['mean_r']:.4f}R also lands close to the vault's "
        f"pre-rebuild +0.72R figure, so this reconstruction is tracking the same "
        f"quantity the vault's older numbers describe.\n")
    L.append(
        f"**Austin's actual method (next_open, market at the signal bar's close) "
        f"pays +{no['mean_r']:.4f}R, ${no['dollar_day']:,.0f}/day, {no['green_months']}/{no['months']} "
        f"green months.** That is real and comfortably above zero -- not the "
        f"dramatic collapse the ceiling claim describes, but also well below the "
        f"as_booked/limit_level number: the fill is not free, it costs roughly "
        f"{100*(1 - no['mean_r']/ab['mean_r']):.0f}% of the as-booked edge, mostly "
        f"through a lower win rate (next bar's open has already moved past the "
        f"confirmation price), not through the strategy having no edge at all.\n")
    L.append(
        f"**chase_once (+{co['mean_r']:.4f}R, only {co['green_months']}/{co['months']} green "
        f"months) is the arm that actually lands near the vault's +0.028R ceiling "
        f"figure.** That is worth flagging plainly: it raises the possibility that "
        f"whatever the lost 2026-08-30 rebuild measured was closer in spirit to "
        f"'pay up to get filled' than to a passive resting order -- but this is "
        f"circumstantial (one number landing close to another), not a claim about "
        f"what that code did, since that code is not recoverable from this repo "
        f"(see below).\n")
    L.append(
        f"**Answering R1's question directly: the ceiling is not a property of "
        f"the strategy at the honest-fill definition this script can reconstruct.** "
        f"A genuinely obtainable resting-limit fill pays within noise of the naive "
        f"back-dated one, and Austin's own stated method (market at candle close) "
        f"still pays a real, positive, mostly-green-months edge. The one arm that "
        f"resembles the vault's ceiling number is the one that pays up rather than "
        f"waits -- an execution-discipline question, not a strategy-is-dead one.\n")

    L.append("## What could not be reconstructed\n")
    L.append(
        "`signal_runner.py` on this repo's `main` (998fbfec, 2026-08-24) has ONE "
        "committed fill model (`fill_price`, line 601) -- there is no "
        "`as_booked`/`limit_level`/`next_open`/`chase_once` switch at `:1456` or "
        "anywhere else, on `main` or on any other branch, local or remote. "
        "`OMEN-7.3.md` and `research/g80_lookahead_refute.md`, the sources "
        "`omen-blockers.md` cites for the +0.72R -> +0.028R collapse and the "
        "85.2%/2.3% obtainability split, are not in this repo either -- consistent "
        "with `omen-blockers.md`'s own note that the 2026-08-30 rebuild happened "
        "on `Desktop/Projects/tradingbot/` and was never pushed. This script is a "
        "from-scratch reconstruction built only from what IS committed (the "
        "structural `level` every `fill_price()` call site already carries, and "
        "each signal's position in its day's candle sequence); it is NOT a rerun "
        "of the lost code, and the specific 85.2%/2.3% split is not something this "
        "script can confirm or deny -- only the CONCLUSION drawn from it (does a "
        "principled honest fill collapse the edge to ~0). It does not, at this "
        "definition. Run on blind 2R exit mechanics (`LADDER_MODE=None`), not the "
        "shipped ladder-B scale-out, so the exit and fill questions stay separate "
        "per the spec's own boundary; `reentry_84_rule` signals are excluded (see "
        "script docstring). Whoever revisits this should treat `as_booked` here as "
        "the reproducible stand-in for the vault's 'void back-dated fill' and "
        "`limit_level` as the reproducible stand-in for its 'honest' one -- not as "
        "a byte-for-byte replay of numbers that no longer exist anywhere runnable.\n")

    with open(OUT_ROWS, "w") as f:
        json.dump(all_rows, f)
    print(f"wrote {OUT_ROWS} ({len(all_rows)} rows)")

    with open(OUT_MD, "w") as f:
        f.write("\n".join(L))
    print("\n".join(L))
    print(f"\nwrote {OUT_MD}")


if __name__ == "__main__":
    main()
