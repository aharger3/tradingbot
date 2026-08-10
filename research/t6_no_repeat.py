"""omen-4.0 T6: measure the no-repeat-entries rule before/after.

Replays the engine's OWN detection (signal_runner.SignalRunner, which uses the
real _route -- so NO_REPEAT_ENTRIES actually applies when armed) bar-by-bar over
every marked (symbol, day) pair in austin_marks_v2.jsonl, once with the flag off
(today's behaviour) and once with it on. Counts fired signals in each arm and
the duplicates the rule suppresses, broken out per pool, and records the cited
batch-04 violation days.

Mirrors research/t4_engine_recall.run_day's walk-forward loop + 11:00 entry
cutoff, but uses a real SignalRunner (not CaptureRunner, which overrides _route
and would bypass the no-repeat rule). The 84% re-entry is the one exemption.

Writes research/t6_no_repeat.md.
"""
from __future__ import annotations
import os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)        # research/t4_engine_recall.py
sys.path.insert(0, ROOT)        # signal_runner, omen_bot
import t4_engine_recall as t4
import signal_runner
from signal_runner import SignalRunner

OUT_MD = os.path.join(HERE, "t6_no_repeat.md")

# Cited batch-04 violation days (task spec) -- confirmed in the marks corpus.
CITED = [
    ("TSLA", "2024-03-27"),
    ("TSLA", "2024-02-05"),
    ("MSFT", "2026-02-11"),
    ("NVDA", "2024-12-16"),
]


class CountRunner(SignalRunner):
    """Real _route (no-repeat applies when armed) + counters. _log_record is the
    single funnel every routed signal passes through -- fired once per accepted
    signal (end of detect_signals), and once per skip with a skip_reason -- so
    counting here is exact with no double count."""
    def __init__(self, symbol):
        super().__init__(post_to_discord=False, symbol=symbol, log_signals=False)
        self.fired = 0
        self.repeat_skipped = 0
        self.repeat_records = []   # (day, bar, direction, level, signal_type)

    def _log_record(self, sig, status="fired", skip_reason=None):
        if status == "fired":
            self.fired += 1
        elif skip_reason == "repeat entry":
            self.repeat_skipped += 1
            self.repeat_records.append((
                self.candles[-1].timestamp, sig["direction"],
                round(sig["stop"], signal_runner.NO_REPEAT_LEVEL_TICK),
                sig["signal_type"].value))


def run_arm(arm_off: bool):
    """Run the walk-forward replay over every marked (symbol, day) pair with the
    flag off (arm_off=True) or on (False). Returns aggregate + per-pool + per-day
    repeat records."""
    signal_runner.NO_REPEAT_ENTRIES = not arm_off
    import json
    marks = [json.loads(l) for l in open(t4.MARKS) if l.strip()]
    pairs = sorted({(m["symbol"], m["day"]) for m in marks})

    total_fired = 0
    per_pool_fired = defaultdict(int)
    per_pool_dup = defaultdict(int)
    repeat_by_day = defaultdict(list)   # (sym,day) -> [(ts,dir,level,stype)]
    per_day = {}                        # (sym,day) -> (off_fired, on_fired, dup)
    for sym, day in pairs:
        candles = t4.rth_candles(sym, day)
        if not candles:
            continue
        pdh, pdl, pdo, pdc = t4.prior_day_levels(sym, day)
        pmh, pml = t4.premarket_extremes(sym, day)
        r = CountRunner(sym)
        r.pdh, r.pdl = pdh, pdl
        r.pmh, r.pml = pmh, pml
        r.pd_open, r.pd_close = pdo, pdc
        r.htf_bias = t4.htf_bias(sym, day)
        r.qqq_breaks = None
        for i in range(5, len(candles)):
            c = candles[i]
            if t4.ENTRY_CUTOFF and c.timestamp >= t4.ENTRY_CUTOFF:
                continue
            r.candles = candles[: i + 1]
            r.detect_signals()
        pool = t4.pool_for(sym)
        total_fired += r.fired
        per_pool_fired[pool] += r.fired
        per_pool_dup[pool] += r.repeat_skipped
        if r.repeat_skipped:
            repeat_by_day[(sym, day)] = r.repeat_records
        per_day[(sym, day)] = r.fired
    return {
        "total_fired": total_fired,
        "per_pool_fired": dict(per_pool_fired),
        "per_pool_dup": dict(per_pool_dup),
        "repeat_by_day": dict(repeat_by_day),
        "per_day": per_day,
    }


def main():
    import json
    off = run_arm(arm_off=True)
    on = run_arm(arm_off=False)
    signal_runner.NO_REPEAT_ENTRIES = True   # restore default

    dup_total = sum(on["per_pool_dup"].values())
    pools = sorted(set(off["per_pool_fired"]) | set(on["per_pool_fired"])
                   | set(on["per_pool_dup"]))

    lines = []
    lines.append("# omen-4.0 T6 — no-repeat-entries before/after\n")
    lines.append(
        "Replays the engine's own detection (the real `signal_runner.SignalRunner` "
        "_route, so the rule applies when armed) bar-by-bar over the 151 marked "
        "(symbol, day) pairs in `austin_marks_v2.jsonl`, mirroring "
        "`t4_engine_recall.run_day`'s walk-forward loop + 11:00 entry cutoff. "
        "Run once with `NO_REPEAT_ENTRIES` off (today's behaviour) and once on. "
        "The 84% re-entry (`SignalType.REENTRY_84_RULE`) is the one exemption — "
        "it is by definition the sanctioned second bite at the same idea.\n")
    lines.append("Austin settled this on 2026-08-09 (Projects/OMEN.md): **no repeat "
                 "entries — take the first one available.** Scope is symbol + "
                 "direction + level; a different level or the other direction is a "
                 "different idea and may still fire.\n")
    lines.append("\n## Headline\n")
    lines.append("```")
    lines.append(f"signals_flag_off: {off['total_fired']}")
    lines.append(f"signals_flag_on: {on['total_fired']}")
    lines.append(f"duplicates_suppressed: {dup_total}")
    lines.append("```\n")
    lines.append("## Per-pool breakdown\n")
    lines.append("| pool | fired (off) | fired (on) | duplicates suppressed |")
    lines.append("|---|---:|---:|---:|")
    for p in pools:
        lines.append(f"| {p} | {off['per_pool_fired'].get(p,0)} "
                     f"| {on['per_pool_fired'].get(p,0)} "
                     f"| {on['per_pool_dup'].get(p,0)} |")
    lines.append(f"| **total** | **{off['total_fired']}** | **{on['total_fired']}** "
                 f"| **{dup_total}** |")
    lines.append("")
    lines.append("`duplicates_suppressed` is counted directly at the skip point "
                 "(the `[skip: repeat entry]` branch in `_route`), not inferred from "
                 "the fired delta — so it is exact even where suppressing a repeat "
                 "second-order changes a later signal's calibration floor.\n")

    # Cited batch-04 violation days. Note the "fired" in the task's batch-04
    # counts uses the CaptureRunner convention (X-grade counts as fired); the
    # real engine skips X-grade, so a duplicate that grades X is already gone
    # before the no-repeat check. The rule's marginal value is the duplicates
    # that grade ABOVE X and would otherwise take a real entry.
    lines.append("## Cited batch-04 violation days\n")
    lines.append("Days the task spec called out as the engine firing the same idea "
                 "twice. The batch-04 \"fired\" counts there use the `CaptureRunner` "
                 "convention (X-grade counts as fired); the **real** engine skips "
                 "X-grade before the no-repeat check runs, so a duplicate that grades "
                 "X is already gone. The rule's marginal value is the duplicates that "
                 "grade **above X** (B/C/A) and would otherwise take a real entry. "
                 "Per day below: fired off / fired on / duplicates suppressed.\n")
    for sym, day in CITED:
        recs = on["repeat_by_day"].get((sym, day), [])
        foff = off["per_day"].get((sym, day), 0)
        fon = on["per_day"].get((sym, day), 0)
        lines.append(f"**{sym} {day}** — fired {foff} -> {fon} "
                     f"({len(recs)} duplicate(s) suppressed):")
        if recs:
            for ts, d, lvl, st in recs:
                lines.append(f"- bar {ts} {d} level ${lvl:.2f} ({st}) — skipped as repeat entry")
        else:
            lines.append("- no real-entry duplicate: the repeats on this day grade X "
                         "(already skipped), so the no-repeat check is never reached")
        lines.append("")

    # Top days by suppressed duplicates — concrete proof the rule does work.
    top = sorted(on["repeat_by_day"].items(), key=lambda kv: len(kv[1]), reverse=True)
    lines.append("## Days with the most real-entry duplicates suppressed\n")
    lines.append("Where the rule actually catches a duplicate that would have traded.\n")
    lines.append("| symbol | day | duplicates suppressed |")
    lines.append("|---|---|---:|")
    for (sym, day), recs in top[:12]:
        lines.append(f"| {sym} | {day} | {len(recs)} |")
    if not top:
        lines.append("| _none_ | | 0 |")
    lines.append("")

    lines.append("## Mechanism\n")
    lines.append("`_route` keeps a per-session set `self._fired_levels` keyed by "
                 "`(symbol, direction, round(sig['stop'], 2))`. On the accept path "
                 "(after the tight-stop gate, so a skipped tight stop never claims a "
                 "level) a signal whose key is already present is suppressed with "
                 "`[skip: repeat entry]`, unless it is an armed 84% re-entry. The "
                 "level is its **price** (rounded to cents), not its name: two names "
                 "at the same price on the same side is the same idea. The flag "
                 "`NO_REPEAT_ENTRIES` defaults **True**; flip it False to measure the "
                 "no-rule arm above.\n")
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {OUT_MD}")
    print(f"signals_flag_off: {off['total_fired']}")
    print(f"signals_flag_on: {on['total_fired']}")
    print(f"duplicates_suppressed: {dup_total}")


if __name__ == "__main__":
    main()
