"""R1 repair -- fixes to research/g210_fill_arms_v2.{py,md} that do NOT
require re-running the hour-long replay, driven off the 12 already-stamped
books in research/tape/fillarms_*.json.gz.

Referee (research/r1_referee.md, commit e5a9ed7f) refuted R1's ranking: the
`close` arm is exited by the real `simulate_day` (an intrabar DISASTER_STOP
touch), the other five arms by `g90_fill_arms._walk` (a close-only structural
stop) -- so the headline table compares six fills under two exit models, and
92% of the published next_open-over-close gap is that exit difference, not
the fill. FIXING that requires re-running the replay with one exit model held
constant across all six arms -- a second change (touches every arm's exit
mechanics, not one flag), out of this row's one-change scope. The referee
said as much: "R2 must not start from next_open-as-winner; it needs one exit
model held constant". That defect is NOT fixed here -- see r1_referee.md and
the report's new "Refereed" section.

What THIS script fixes, from the existing books alone (no rerun):
  1. Honest avg win / avg loss -- mean R of every row with r>0 vs every row
     with r<0 (a "scratch" outcome that lost money belongs in the loss
     column; g210 excluded it, so every arm read the tautological +2.0/-1.0
     the walk's win/loss labels imply, on purpose or not).
  2. Honest per-trade win rate -- wins / (wins+losses+scratches), not
     wins / (wins+losses) with scratches silently dropped from the
     denominator.
  3. The worst single loss per arm per pool (surfaces mid_candle's -75.5491R
     row the referee flagged as contradicting CLAUDE.md's -1R floor, and
     confirms which arms' losses are provably capped at -1R in the real
     books, since the docstring's claim about the disaster-stop asymmetry's
     DIRECTION was backwards).
  4. Sized stats: min_risk_floor(entry) = max(0.10, 0.0015 x entry) is used
     as a floor on abs(entry-stop) (entry stands in for the candle close
     signal_runner.min_risk_floor actually reads -- the books do not carry
     the raw candle close, and entry is the same order of magnitude on
     every fill mode priced here). Rows below the floor are excluded and
     mean R / $/day / green months are recomputed. This is the same
     computation CLAUDE.md's "Size-gate every money number" rule calls for
     and g210 never ran.

Output: prints a set of markdown tables consumed by hand into
research/g210_fill_arms_v2.md's new "Refereed" section (not appended
automatically -- the section also carries prose the referee's defects
require, which this script does not generate).
"""
import gzip
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TAPE = os.path.join(HERE, "tape")

ARMS = ["as_booked", "limit_level", "next_open", "chase_once", "close", "mid_candle"]
POOLS = ["core11", "full29"]

TRADING_DAYS_PER_MONTH = 21  # matches g90_fill_arms.arm_stats's convention


def min_risk_floor(entry):
    return max(0.10, 0.0015 * entry)


def load(arm, pool):
    path = os.path.join(TAPE, f"fillarms_{arm}_{pool}.json.gz")
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def month_key(day):
    return day[:7]


def honest_avg_win_loss(trades):
    wins = [t["r"] for t in trades if not t["unfilled"] and t["r"] is not None and t["r"] > 0]
    losses = [t["r"] for t in trades if not t["unfilled"] and t["r"] is not None and t["r"] <= 0]
    aw = sum(wins) / len(wins) if wins else None
    al = sum(losses) / len(losses) if losses else None
    return aw, al, len(wins), len(losses)


def per_trade_win_rate(trades):
    filled = [t for t in trades if not t["unfilled"] and t["r"] is not None]
    if not filled:
        return None, 0
    wins = sum(1 for t in filled if t["r"] > 0)
    return round(100.0 * wins / len(filled), 1), len(filled)


def worst_loss(trades):
    losses = [(t["r"], t["sym"], t["day"]) for t in trades if not t["unfilled"] and t["r"] is not None and t["r"] < 0]
    if not losses:
        return None
    return min(losses, key=lambda x: x[0])


def below_neg1r(trades):
    return sum(1 for t in trades if not t["unfilled"] and t["r"] is not None and t["r"] < -1.0)


def sized_stats(all_trades):
    """Same convention as g90_fill_arms.arm_stats/close_stats: $/day divides
    by unique trading DAYS across every candidate row in the pool (filled or
    not), not by days that happen to carry a sized trade."""
    kept = [t for t in all_trades if not t["unfilled"] and t["r"] is not None
            and t.get("entry") is not None and t.get("stop") is not None
            and abs(t["entry"] - t["stop"]) >= min_risk_floor(t["entry"])]
    n = len(kept)
    total_days = len({t["day"] for t in all_trades})
    if n == 0 or not total_days:
        return {"n": 0, "mean_r": None, "dollar_day": None, "green": None, "months": 0}
    mean_r = sum(t["r"] for t in kept) / n
    by_month = {}
    for t in kept:
        by_month.setdefault(month_key(t["day"]), []).append(t["pnl"])
    total_pnl = sum(t["pnl"] for t in kept)
    dollar_day = total_pnl / total_days
    months = len(by_month)
    green = sum(1 for v in by_month.values() if sum(v) > 0)
    return {"n": n, "mean_r": mean_r, "dollar_day": dollar_day, "green": green, "months": months}


def main():
    print("## Honest avg win / avg loss, per-trade win rate, worst loss\n")
    print("| pool | arm | avg win | avg loss | wins | losses | per-trade win% | filled | worst loss (R) | sym/day | rows < -1.000R |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|")
    for pool in POOLS:
        for arm in ARMS:
            d = load(arm, pool)
            trades = d["trades"]
            aw, al, nw, nl = honest_avg_win_loss(trades)
            wr, nfilled = per_trade_win_rate(trades)
            wl = worst_loss(trades)
            nbelow = below_neg1r(trades)
            wl_s = f"{wl[0]:+.4f}" if wl else "--"
            wl_who = f"{wl[1]} {wl[2]}" if wl else "--"
            print(f"| {pool} | {arm} | {aw:+.4f} | {al:+.4f} | {nw} | {nl} | {wr}% | {nfilled} | {wl_s} | {wl_who} | {nbelow} |")

    print("\n## Sized stats (min_risk_floor(entry) = max($0.10, 0.0015 x entry) applied as a floor on abs(entry-stop))\n")
    print("| pool | arm | trades (sized) | mean R (sized) | $/day (sized) | green/months (sized) |")
    print("|---|---|---:|---:|---:|---:|")
    for pool in POOLS:
        for arm in ARMS:
            d = load(arm, pool)
            s = sized_stats(d["trades"])
            mr = f"{s['mean_r']:+.4f}" if s["mean_r"] is not None else "--"
            dd = f"${s['dollar_day']:,.0f}" if s["dollar_day"] is not None else "--"
            gm = f"{s['green']}/{s['months']}" if s["months"] else "--"
            print(f"| {pool} | {arm} | {s['n']} | {mr} | {dd} | {gm} |")


if __name__ == "__main__":
    main()
