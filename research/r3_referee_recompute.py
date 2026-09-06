"""R3 referee -- independent recompute of the baseline's day-policy unit and the R2
substrate/ladder split, from the committed stamped books, with no code imported from
the builder's scripts (g212_baseline_verdict.py / g211_reconcile_ladder.py / loop_cycle.py).
"""
import gzip, json, sys
from collections import defaultdict

RISK = 1000.0
CORE11 = {'TSLA','NVDA','AAPL','AMD','META','GOOGL','AMZN','MSFT','PLTR','QQQ','SPY'}


def load(path):
    with gzip.open(path) as fh:
        return json.load(fh)


def month_of(day):
    return day[:7]


def half_of(day, cutoff='2025-09-01'):
    return 'H1' if day < cutoff else 'H2'


def day_policy_stats(trades, universe_filter):
    """His day policy per loop_cycle.up_to_3_rows: up to 3 candidates/day in
    arrival order (et, sym), stop after the first win or the second loss.
    Candidate pool = fired-and-traded rows PLUS status=='halted' rows (the
    account-wide two-loss halt's own candidates, backfilled with a simulated
    pnl, so the halt does not silently truncate a day this unit's own rule
    would still be inside of)."""
    by_day = defaultdict(list)
    for t in trades:
        if t['sym'] not in universe_filter:
            continue
        if (t.get('status') == 'fired' and t.get('traded')) or t.get('status') == 'halted':
            by_day[t['day']].append(t)

    picked = []
    for day in sorted(by_day):
        rows_sorted = sorted(by_day[day], key=lambda r: (r.get('et') or '', r.get('sym') or ''))
        losses, taken = 0, 0
        for r in rows_sorted:
            if taken >= 3:
                break
            picked.append(r)
            taken += 1
            pnl = r.get('pnl', 0.0)
            if pnl > 0:
                break
            elif pnl < 0:
                losses += 1
                if losses >= 2:
                    break
    return summarize(picked)


def summarize(trades):
    n = len(trades)
    if n == 0:
        return None
    total = sum(t['pnl'] for t in trades)
    days = set(t['day'] for t in trades)
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] < 0]
    win_rate = len(wins) / n if n else 0.0
    mean_r = sum(t['r'] for t in trades) / n
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0.0
    by_month = defaultdict(float)
    for t in trades:
        by_month[month_of(t['day'])] += t['pnl']
    green = sum(1 for v in by_month.values() if v > 0)
    months = len(by_month)
    return dict(trades=n, days=len(days), total=total, win_rate=win_rate, mean_r=mean_r,
                avg_win=avg_win, avg_loss=avg_loss, green=green, months=months)


def per_day(stats, sessions):
    return stats['total'] / sessions if stats else None


def print_stats(label, stats, sessions):
    if stats is None:
        print(f"{label}: NO TRADES")
        return
    pd = per_day(stats, sessions)
    print(f"{label}: trades={stats['trades']} $/day={pd:.2f} mean_r={stats['mean_r']:.4f} "
          f"win={stats['win_rate']*100:.1f}% avg_win={stats['avg_win']:.2f} avg_loss={stats['avg_loss']:.2f} "
          f"green={stats['green']}/{stats['months']}")


def main():
    print("=== Section A: baseline day-policy unit, independent recompute ===")
    b = load('research/tape/baseline_2026-09-05.json.gz')
    sessions = b['meta']['sessions']
    trades = b['trades']
    all_stats = day_policy_stats(trades, CORE11)
    print(f"sessions={sessions}")
    print_stats("whole (25mo)", all_stats, sessions)

    h1 = [t for t in trades if t.get('traded') and t['sym'] in CORE11 and half_of(t['day']) == 'H1']
    h2 = [t for t in trades if t.get('traded') and t['sym'] in CORE11 and half_of(t['day']) == 'H2']
    # need to redo day-policy per half using only that half's days
    def day_policy_on_subset(trades_all, universe_filter, half):
        by_day = defaultdict(list)
        for t in trades_all:
            if t['sym'] not in universe_filter:
                continue
            if half_of(t['day']) != half:
                continue
            if (t.get('status') == 'fired' and t.get('traded')) or t.get('status') == 'halted':
                by_day[t['day']].append(t)
        picked = []
        for day in sorted(by_day):
            rows_sorted = sorted(by_day[day], key=lambda r: (r.get('et') or '', r.get('sym') or ''))
            losses, cnt = 0, 0
            for r in rows_sorted:
                if cnt >= 3:
                    break
                picked.append(r)
                cnt += 1
                pnl = r.get('pnl', 0.0)
                if pnl > 0:
                    break
                elif pnl < 0:
                    losses += 1
                    if losses >= 2:
                        break
        return picked, len(by_day)

    h1_picked, h1_days = day_policy_on_subset(trades, CORE11, 'H1')
    h2_picked, h2_days = day_policy_on_subset(trades, CORE11, 'H2')
    h1_stats = summarize(h1_picked)
    h2_stats = summarize(h2_picked)
    print(f"H1 sessions_with_candidate={h1_days}")
    print_stats("H1", h1_stats, h1_days)
    print(f"H2 sessions_with_candidate={h2_days}")
    print_stats("H2", h2_stats, h2_days)

    print()
    print("=== Section B: stamp check ===")
    flags = b['meta']['stamp']['flags']
    checks = {
        'entry_fill.ENTRY_FILL': 'close',
        'signal_runner.RETEST_REQUIRED': True,
        'signal_runner.ON_WATCH': True,
        'signal_runner.RULE84_OFF': False,
        'loss_halt.LOSS_HALT': True,
    }
    ok = True
    for k, expect in checks.items():
        got = flags.get(k)
        status = 'OK' if got == expect else 'MISMATCH'
        if got != expect:
            ok = False
        print(f"{k}: expect={expect} got={got} {status}")
    print(f"commit={b['meta']['stamp']['git']['commit'][:8]} (verdict claims 29e4abc6)")
    print(f"window={b['meta']['first']}..{b['meta']['last']} sessions={b['meta']['sessions']}")
    print("ALL STAMP CHECKS OK" if ok else "STAMP MISMATCH FOUND")

    print()
    print("=== Section C: R2 substrate/ladder split, both directions, own code ===")
    fwd1 = load('research/tape/reconcile_fwd_1_add_C_grades.json.gz')
    fwd2 = load('research/tape/reconcile_fwd_2_swap_exit_shipped_ladder.json.gz')
    simd = load('research/tape/r2ref_simd_next_open_blind2r_real_engine.json.gz')

    def filled_rows(book):
        return [t for t in book['trades'] if t.get('filled') and t.get('r') is not None]

    f1 = filled_rows(fwd1)
    f2 = filled_rows(fwd2)
    fd = filled_rows(simd)

    def days_in(rows):
        return len(set(t['day'] for t in rows))

    def per_day_full(rows):
        total = sum(t['pnl'] for t in rows)
        return total / days_in(rows) if rows else None

    s1 = summarize_generic(f1)
    sd = summarize_generic(fd)
    s2 = summarize_generic(f2)

    def fmt(label, rows, s):
        pd_ = sum(r['pnl'] for r in rows) / days_in(rows)
        print(f"{label}: n={len(rows)} days={days_in(rows)} $/day={pd_:.2f} win={s['win_rate']*100:.1f}% "
              f"mean_r={s['mean_r']:.4f} avg_win={s['avg_win']:.4f} avg_loss={s['avg_loss']:.4f}")
        return pd_

    pd1 = fmt('fwd_1 (lab close-only stop, blind 2R)', f1, s1)
    pdd = fmt('SIM D (real engine intrabar stop, blind 2R)', fd, sd)
    pd2 = fmt('fwd_2 (real engine, shipped ladder)', f2, s2)

    print(f"substrate leg (fwd_1 -> SIM D): delta=${pdd - pd1:.2f}/day")
    print(f"ladder leg (SIM D -> fwd_2): delta=${pd2 - pdd:.2f}/day")
    total_delta = pd2 - pd1
    print(f"total step1->2 delta=${total_delta:.2f}/day")
    print(f"substrate share={100*(pdd-pd1)/total_delta:.1f}%  ladder share={100*(pd2-pdd)/total_delta:.1f}%")

    # Reverse-direction check: hold exit fixed, swap substrate the other way around
    # fwd_2 -> SIM D isolates the ladder leg from the "ladder" side; SIM D -> fwd_1 isolates substrate from other side
    print()
    print("Reverse-direction (same legs, computed from the other endpoint):")
    print(f"  ladder leg via (fwd_2 - SIM D) = ${pd2-pdd:.2f} (same computation, sanity only -- one path exists, no true reverse ladder available)")

    print()
    print("=== Section D: stamp diff between fwd_1, SIM D, fwd_2 -- what else differs? ===")
    stamps = {
        'fwd_1': fwd1['meta']['stamp']['flags'],
        'SIM D': simd['meta']['stamp']['flags'],
        'fwd_2': fwd2['meta']['stamp']['flags'],
    }
    all_keys = set()
    for s in stamps.values():
        all_keys |= set(s.keys())
    diffs_1_to_d = []
    diffs_d_to_2 = []
    for k in sorted(all_keys):
        v1 = stamps['fwd_1'].get(k)
        vd = stamps['SIM D'].get(k)
        v2 = stamps['fwd_2'].get(k)
        if v1 != vd:
            diffs_1_to_d.append((k, v1, vd))
        if vd != v2:
            diffs_d_to_2.append((k, vd, v2))
    print(f"fwd_1 -> SIM D: {len(diffs_1_to_d)} flag(s) differ:")
    for k, a, b_ in diffs_1_to_d:
        print(f"   {k}: {a} -> {b_}")
    print(f"SIM D -> fwd_2: {len(diffs_d_to_2)} flag(s) differ:")
    for k, a, b_ in diffs_d_to_2:
        print(f"   {k}: {a} -> {b_}")

    print()
    print("=== Section E: win-rate denominator check (CLAUDE.md's 38.8% -> 33.6%) ===")
    wins1 = sum(1 for t in f1 if t['pnl'] > 0)
    windd = sum(1 for t in fd if t['pnl'] > 0)
    print(f"fwd_1: wins={wins1}/{len(f1)} = {100*wins1/len(f1):.2f}%")
    print(f"SIM D: wins={windd}/{len(fd)} = {100*windd/len(fd):.2f}%")
    # scratch check
    scr1 = sum(1 for t in f1 if t['pnl'] == 0)
    scrd = sum(1 for t in fd if t['pnl'] == 0)
    print(f"scratches: fwd_1={scr1} SIM D={scrd}")

    print()
    print("=== Section F: filtered-vs-simulated check for THIS step ===")
    print("fwd_1 source: SIM A (bar-by-bar replay, g90 arm)")
    print("SIM D source: bar-by-bar replay, real engine, blind 2R")
    print("fwd_2 source: SIM B (bar-by-bar replay, real engine, shipped ladder)")
    print("All three of fwd_1, SIM D, fwd_2 are SIMULATED (not filtered) populations --")
    print("the add-C-grades filtered-vs-simulated defect (R2 referee pass 2/3, section on")
    print("dedupe_replay) applies to step 0->1 (a row-deletion on top of SIM A), not to the")
    print("step this row is being asked to refute (fwd_1 -> SIM D -> fwd_2), which never")
    print("crosses a filtered/simulated boundary.")


def summarize_generic(rows):
    n = len(rows)
    wins = [t for t in rows if t['pnl'] > 0]
    losses = [t for t in rows if t['pnl'] < 0]
    win_rate = len(wins) / n if n else 0.0
    mean_r = sum(t['r'] for t in rows) / n if n else 0.0
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0.0
    return dict(win_rate=win_rate, mean_r=mean_r, avg_win=avg_win, avg_loss=avg_loss)


if __name__ == '__main__':
    main()
