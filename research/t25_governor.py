"""t25_governor.py -- replay live_scanner.py's `_tier()` governor, before and
after T25, over the 2-year book.

BEFORE (the code at HEAD before this ticket, `research/x7_entry_surface_map.md`
section 0): TRADE = first signal of the day, ACROSS ALL SYMBOLS, graded
legacy A+/A, at or after 09:40 ET. 14 trades in 500 sessions.

AFTER (`live_scanner.py:_tier()`, this ticket): TRADE = sgrade S (Austin's
ladder, `research/downgrade.py`, read off the book's own `sgrade` column --
the same call `signal_runner.py::_sac_ladder_grade` makes when
`ENABLE_SAC_LADDER=1`, which T25 now forces on for the live process only), at
or after TRADE_FLOOR (still "09:40", still a parameter -- see section 2), at
most GOVERNOR_S_CAP S signals PER SYMBOL per day (default None = uncapped).
Grade A and C are ALERT-only at any floor/cap setting, exactly like the old
A/C alert never traded either.

Both replays run over every NON-X signal in `research/g3_arm_ow1.json`
(`status != "skipped_d"`, 2,256 of 45,193) -- not the 1,017 the legacy grader
chose to TRADE (an A+/A- or S-graded signal is a candidate for the governor
whether or not the legacy engine's separate B/A/A+ acceptance rule happened
to trade it, matching x7's own methodology), but ALSO not the full 45,193.

**Why the X-graded 42,937 are excluded, and it is not optional:** they carry
placeholder entry/stop pairs (median stop distance ~$0.01, several under
`stop_pct` 0.01%) left over from a signal `_grade_pa` vetoed on candle shape
before any real stop was placed -- one row prices at **+109R**, another at
**+212R**, the worst at **+67169R**, against a real-fill population capped at
-1.25R/+21.4R. Treating them as tradeable inflates mean R by two orders of
magnitude (confirmed against an earlier draft of this script: n=7,044,
mean R +9.59, before this filter was added -- not a real number, a data
artifact, caught and removed rather than published). This is not a new
convention invented for this ticket: it is exactly what
`signal_runner.py::_sac_ladder_grade` already does live --
`SAC_LADDER_REGRADE_ALL` defaults False, so "a signal the incumbent chain
already graded X is LEFT alone" and never reaches `_tier()` at all. Excluding
`skipped_d` here is the replay matching the shipped code, not a new filter
invented for the report.

NOT MODELED, same caveat x7 already carries for its 14-trade figure:
`consecutive_losses < 2`, the 20-minute per-symbol-direction cooldown, and
`WATCH_DAILY_CAP` (alert suppression). All three are session/live-only state
with no equivalent column in the book. Every count below is therefore an
UPPER BOUND on trades, same as x7's 14.

    python research/t25_governor.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

BOOK_PATH = "research/g3_arm_ow1.json"


def load_book(path: str = BOOK_PATH):
    d = json.load(open(path, encoding="utf-8"))
    return d["trades"], d["meta"]


def stats(rows: list) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0, "mean_r": None, "win_pct": None, "total_r": None}
    wins = sum(1 for t in rows if t["out"] == "win")
    losses = sum(1 for t in rows if t["out"] == "loss")
    total_r = sum(t["r"] for t in rows)
    win_pct = 100.0 * wins / (wins + losses) if (wins + losses) else None
    return {"n": n, "mean_r": total_r / n, "win_pct": win_pct, "total_r": total_r}


def legacy_tier_replay(trades: list, trade_floor: str = "09:40") -> list:
    """The governor as it stood at HEAD before this ticket
    (`live_scanner.py:_tier()`, pre-T25): TRADE = first {A+, A}-graded signal
    of the day, at/after trade_floor, ACROSS ALL SYMBOLS (one trade per day,
    book-wide -- `s.signals_today == 0` was a global counter, not per-symbol).
    84% re-entries are excluded here and reported separately (3 signals total,
    see `main()`)."""
    pool = [t for t in trades
            if t["grade"] in ("A+", "A") and t["et"][:5] >= trade_floor
            and t["setup"] != "reentry_84_rule"]
    by_day = defaultdict(list)
    for t in pool:
        by_day[t["day"]].append(t)
    out = []
    for day, sigs in by_day.items():
        sigs.sort(key=lambda t: (t["et"], t["sym"]))
        out.append(sigs[0])
    return sorted(out, key=lambda t: (t["day"], t["et"]))


def sac_governor_replay(trades: list, trade_floor: "str | None" = "09:40",
                        daily_cap: "int | None" = None) -> dict:
    """The governor as of this ticket (`live_scanner.py:_tier()`, post-T25).
    One pass, mirrors the live predicates exactly:

        grade != "A+" (his S)  or  et < trade_floor   -> WATCH
        else: per-symbol-per-day count >= daily_cap    -> WATCH
        else                                            -> TRADE

    trade_floor=None reproduces "no floor" (TRADE_FLOOR removed).
    daily_cap=None reproduces the shipped default (uncapped).
    84% re-entries are excluded here and reported separately (see `main()`).

    Returns a dict with four buckets: trade, alert_a, alert_c, alert_s_gated
    (S-graded signals that would alert rather than trade -- pre-floor or
    over-cap), so nothing in the S population silently disappears."""
    non_84 = [t for t in trades
              if t["setup"] != "reentry_84_rule" and t["status"] != "skipped_d"]
    alert_a = [t for t in non_84 if t["sgrade"] == "A"]
    alert_c = [t for t in non_84 if t["sgrade"] == "C"]
    s_signals = [t for t in non_84 if t["sgrade"] == "S"]

    per_symday = defaultdict(list)
    for t in s_signals:
        per_symday[(t["day"], t["sym"])].append(t)

    trade, alert_s_gated = [], []
    for key, sigs in per_symday.items():
        sigs.sort(key=lambda t: t["et"])
        for i, t in enumerate(sigs):
            blocked_by_floor = trade_floor is not None and t["et"][:5] < trade_floor
            blocked_by_cap = daily_cap is not None and i >= daily_cap
            if blocked_by_floor or blocked_by_cap:
                alert_s_gated.append(t)
            else:
                trade.append(t)
    trade.sort(key=lambda t: (t["day"], t["et"]))
    return {"trade": trade, "alert_a": alert_a, "alert_c": alert_c,
            "alert_s_gated": alert_s_gated}


def fmt_stats(label: str, rows: list) -> str:
    s = stats(rows)
    if s["n"] == 0:
        return f"| {label} | 0 | -- | -- | -- |"
    return (f"| {label} | {s['n']} | {s['mean_r']:+.4f}R | "
            f"{s['win_pct']:.1f}% | {s['total_r']:+.1f}R |")


def main():
    trades, meta = load_book()
    n84 = sum(1 for t in trades if t["setup"] == "reentry_84_rule")

    print(f"# t25_governor -- book meta: generated {meta['generated']}, "
          f"{meta['sessions']} sessions, {meta['signals']} signals, "
          f"{meta['traded']} legacy-traded\n")

    # 1. Sanity check: reproduce x7's legacy-tier trade count.
    legacy = legacy_tier_replay(trades, "09:40")
    ls = stats(legacy)
    print("## 1. Legacy tier replay (pre-T25 `_tier()`, sanity check vs x7)\n")
    print(f"grade in (A+, A), et>=09:40, first-of-day across ALL symbols: "
          f"n={ls['n']}, mean R={ls['mean_r']:+.4f}, win={ls['win_pct']:.1f}%")
    print("x7_entry_surface_map.md reported n=14, mean R +1.1101 against an "
          "earlier regeneration of this book (g3_arm_ow1.json is gitignored, "
          "regenerable, and was regenerated 2026-08-28 by another wave-1 "
          "track after x7 was written -- 18 A+/A raw signals here vs x7's 17, "
          "count still lands on 14 after the floor+first-of-day dedupe, mean "
          "R differs slightly). The METHOD reproduces; the exact snapshot "
          "does not, because the book moved under it, not because the replay "
          "is wrong.\n")

    # 2. The new governor at its shipped default (TRADE_FLOOR kept, no cap).
    default = sac_governor_replay(trades, trade_floor="09:40", daily_cap=None)
    ds = stats(default["trade"])
    print("## 2. New governor, shipped default (S only, floor kept, uncapped)\n")
    print(f"n={ds['n']}, mean R={ds['mean_r']:+.4f}, win={ds['win_pct']:.1f}%, "
          f"total R={ds['total_r']:+.1f}\n")
    print(f"Trade count moves **{ls['n']} -> {ds['n']}** "
          f"({ds['n'] / max(ls['n'], 1):.1f}x). "
          f"Alert-only: A={len(default['alert_a'])}, C={len(default['alert_c'])}, "
          f"S blocked by floor/cap={len(default['alert_s_gated'])}. "
          f"84% re-entries (exempt from the grade gate, not modeled -- "
          f"consecutive_losses state has no book column): {n84}.\n")

    # 3. The 09:40 floor -- what it costs.
    nofloor = sac_governor_replay(trades, trade_floor=None, daily_cap=None)
    nfs = stats(nofloor["trade"])
    print("## 3. The 09:40 floor, measured\n")
    print("| arm | n | mean R | win% | total R |")
    print("|---|---:|---:|---:|---:|")
    print(fmt_stats("floor kept (09:40)", default["trade"]))
    print(fmt_stats("floor removed", nofloor["trade"]))
    gained = [t for t in nofloor["trade"] if t not in default["trade"]]
    gs = stats(gained)
    in_best_block = sum(1 for t in gained if "09:30" <= t["et"][:5] < "09:45")
    print(f"\nRemoving the floor adds {gs['n']} trades (all in 09:35-09:40, "
          f"since the earliest entry in the book is 09:35), mean R "
          f"{gs['mean_r']:+.4f}, win {gs['win_pct']:.1f}%. "
          f"{in_best_block} of {gs['n']} land in x8's best 15-minute block "
          f"(09:30-09:45, +1.1619R at 60.7% win). Not silently kept or "
          f"dropped: this table is the report, the flag stays 09:40 in "
          f"`live_scanner.py` (see the file's own T25 comment) and Austin's "
          f"call is which arm to ship.\n")

    # 4. Per-symbol daily cap, swept (parameterized, not resolved).
    print("## 4. Per-symbol daily cap, swept (batch 02 c3/c4 conflict, "
          "parameterized not resolved)\n")
    print("| cap | n | mean R | win% | total R |")
    print("|---|---:|---:|---:|---:|")
    for cap in (None, 1, 2, 3):
        arm = sac_governor_replay(trades, trade_floor="09:40", daily_cap=cap)
        label = "none (shipped default)" if cap is None else str(cap)
        print(fmt_stats(label, arm["trade"]))
    print("\nThis is a DIFFERENT population from `research/a3_s_cap_sweep.md`'s "
          "cap sweep (n=129 there): a3 capped the S-graded subset of the "
          "1,017 legacy-TRADED rows; this sweeps the S-graded subset of the "
          "governor's own (much larger) TRADE population, which is not "
          "gated by the legacy A+/A tier at all any more. Neither reading is "
          "wrong; they answer different questions (\"cap the current book's S "
          "trades\" vs \"cap the new governor's S trades\"), and a3's "
          "conclusion (no CI is decisive, every cap arm gives up total R) is "
          "not re-litigated here -- ballot batch 03 is where Austin resolves "
          "which number he meant.\n")

    print("## Ballot item for batch 03\n")
    print("Unresolved per Austin's own three numbers (batch 02, c3/c4): "
          "\"max 2 S trades per symbol\" vs \"max 3 s trades per symbol\" vs "
          "\"cap at .8 s trades a day per symbol\". `GOVERNOR_S_CAP` in "
          "`live_scanner.py` implements per-symbol daily cap as an integer "
          "parameter (env `GOVERNOR_S_CAP`, default unset = uncapped); it "
          "cannot express \".8 per day\" (a probabilistic thin-out, not a hard "
          "cap) without a different mechanism -- that reading needs its own "
          "ballot answer, not a guessed rounding to 1.")


if __name__ == "__main__":
    main()
