"""OMEN 8.0 R5 -- the live promotion gate, counted under the old rule and the new one.

**Why this script exists rather than a rerun of the spec row's numbers.** The row
cites `live_scanner.py:546` promoting to TRADE "only on `A+`", firing "twice in
45,193 signals", with "zero of the entries taken on Austin's S days" being A+,
sourced to `OMEN-7.3.md:288`. None of that is reproducible from this repo:

  * `live_scanner.py:546` is inside an unrelated `except ValueError` block in
    `_emit_signal`. The promotion gate is `_tier()`, ~40 lines earlier.
  * The committed gate was never `grade == "A+"`. It reads
    `grade not in ("A+", "A")` and has since the repo's first commit (998fbfec,
    the initial import -- `git log -S` finds no earlier form). The vault's
    `grade != "A+"` citation describes a variant that does not exist here.
  * `OMEN-7.3.md` is not in the tree, on any branch, same as R1's and R3's lost
    sources (`research/g90_fill_arms.md`, `research/g92_x_lift.md`, both
    "what could not be reconstructed").

So 45,193 / "fires twice" / "zero on S days" are NOT targets and were not aimed
at. This script builds its own reproducible signal sample from committed code
and reports the promotion count under the old gate and the new one over THAT
sample, which is what R5's verify asks for structurally.

--------------------------------------------------------------------------
THE TWO GATES
--------------------------------------------------------------------------

OLD (`live_scanner._tier`, before this row):

    if signal_type == reentry_84_rule:      return TRADE if losses < 2 else WATCH
    if grade not in ("A+","A") or ts < TRADE_FLOOR:  return WATCH
    return TRADE if signals_today == 0 and losses < 2 else WATCH

`grade` is `PriceActionAnalyzer.grade_trade`'s A+/A/B/C/D ladder -- the RETIRED
classification. NEW replaces that one clause with Austin's settled scheme:

    if austin_tier != "S" or ts < TRADE_FLOOR:  return WATCH

Everything else (the 09:40 floor, first-of-day, the 2-loss halt, the 84%
re-entry exemption) is an OPERATIONAL safeguard with its own source and is
carried across unchanged. See research/g94_live_tier.md for the reasoning on
each piece.

Two extra arms are scored for disclosure, not as candidates:
  * `new_notC`  -- `austin_tier == "S" and grade != "C"`, i.e. the new gate with
    the engine ladder's "C is alert-only" convention kept on top. Measures what
    the pure migration costs relative to a half-migrated hybrid.
  * `new_reentryS` -- the new gate with the 84% re-entry ALSO required to be S.
    Measures what the exemption is worth, since this row keeps it.

--------------------------------------------------------------------------
THE SAMPLE
--------------------------------------------------------------------------

`backtest_week.simulate_day` replayed over the full two-year archive at the
committed omen-5.0 defaults (STOP_ON_CLOSE=1, LADDER_MODE="B"), exactly as R3
did. Every signal `SignalRunner._route` sees is captured, with its engine
`grade`, its `austin_tier` (computed by `compute_austin_tier` inside `_route`,
so it is the shipped value, not a reconstruction) and the timestamp of the bar
it fired on. Nothing in `signal_runner.py`, `omen_bot.py` or `backtest_week.py`
is modified; the two hooks below (capture the runner, stamp the bar timestamp)
are installed and restored in-process, R1/R3 house style.

The signals the LIVE scanner would see are the ACCEPTED ones -- `status ==
"fired"` -- because `live_scanner` calls `runner.detect_signals()`, which
returns only what `_route` appended. Those are replayed per DAY, universe-wide
and in timestamp order, through a faithful re-implementation of
`live_scanner._emit_signal`'s pre-`_tier` path (the 20-minute per
symbol+direction cooldown, the daily governor, `session.day_ended()`), with the
gate swapped underneath. The cooldown and the governor are identical across
arms, so every arm sees the identical set of signals arriving at `_tier`.

Known and deliberate differences from a bar-exact live replay, all identical
across arms:
  * `consecutive_losses` is held at 0. Live, `record_loss` is only ever called
    from `--paper` mode (`live_scanner.scan_once`), so a signal-only production
    run never increments it. That is the shipped behaviour.
  * The sample carries `backtest_week`'s DEDUPE_BARS=30 suppression at trade
    construction, but that happens AFTER routing, so it does not touch this
    signal set -- `captured` is pre-dedupe.
  * `armed_84` is likewise only populated in `--paper` mode live, so the 84%
    re-entry path is reachable in this sample (the backtest arms it) but not in
    a signal-only production run.

Output: research/g94_live_tier_rows.json (every ACCEPTED signal in full, plus a
(status, tier, grade) cross-tab of the ones `_route` refused),
research/g94_live_tier_summary.json (what research/g94_verify.py reads), and the
counts printed to stdout and pasted into research/g94_live_tier.md.
Re-analyse without re-running the two-year replay:
    python3 research/g94_live_tier.py --rows research/g94_live_tier_rows.json
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from t8_two_year import day_table, rth_candles, bias_from  # noqa: E402
from universe import MAJOR_15, INDEX_POOL, OTHER_POOL  # noqa: E402

ARCHIVE = os.path.join(ROOT, "data_archive")
OUT_ROWS = os.path.join(HERE, "g94_live_tier_rows.json")
MARKS = os.path.join(HERE, "austin_marks_v7.jsonl")

# read from live_scanner so the replay cannot drift from the shipped constants
sys.path.insert(0, ROOT)
import live_scanner as ls  # noqa: E402

TRADE_FLOOR = ls.TRADE_FLOOR
ALERT_COOLDOWN_MIN = ls.ALERT_COOLDOWN_MIN
WATCH_DAILY_CAP = ls.WATCH_DAILY_CAP
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "3"))


# ===========================================================================
# sample
# ===========================================================================

def _rows_for(args):
    """Every signal `_route` saw, for one symbol over the range."""
    symbol, start_day, end_day = args
    import backtest_week as bw
    bw.STOP_ON_CLOSE, bw.LADDER_MODE = True, "B"   # committed omen-5.0 defaults

    seen_runners = []
    orig_init = bw.BacktestRunner.__init__
    orig_route = bw.BacktestRunner._route

    def init(self, sym):
        orig_init(self, sym)
        seen_runners.append(self)

    def route(self, signals, sig):
        # the bar the signal fired on; `_route` runs with candles[:i+1] set
        sig["_ts"] = self.candles[-1].timestamp if self.candles else ""
        orig_route(self, signals, sig)

    bw.BacktestRunner.__init__ = init
    bw.BacktestRunner._route = route
    try:
        table = day_table(symbol)
        days = sorted(table)
        out, days_run = [], 0
        for i, day in enumerate(days):
            if day < start_day or day > end_day:
                continue
            candles = rth_candles(symbol, day)
            if not candles or len(candles) < 60:
                continue
            prev = days[i - 1] if i else None
            pdh = pdl = pdo = pdc = None
            if prev:
                pdh, pdl, pdo, pdc = (table[prev][0], table[prev][1],
                                      table[prev][2], table[prev][3])
            pmh, pml = table[day][4], table[day][5]
            bias = bias_from([table[d][3] for d in days[max(0, i - 40):i]])
            del seen_runners[:]
            bw.simulate_day(symbol, day, candles, pdh, pdl, bias,
                            pmh, pml, pdo, pdc, None)
            days_run += 1
            if not seen_runners:
                continue
            for sig in seen_runners[-1].captured:
                out.append({
                    "symbol": symbol,
                    "day": day,
                    "ts": sig.get("_ts", ""),
                    "setup": sig["signal_type"].value,
                    "dir": sig["direction"],
                    "grade": sig["grade"],
                    "tier": sig.get("austin_tier"),
                    "status": sig.get("status"),
                    # carried for the adversarial pass: options_sizer sizes off
                    # the engine grade, so a newly-promotable tier-S / grade-C
                    # signal with a wide stop can size to ZERO contracts
                    "entry": round(float(sig["entry"]), 4),
                    "stop": round(float(sig["stop"]), 4),
                })
    finally:
        bw.BacktestRunner.__init__ = orig_init
        bw.BacktestRunner._route = orig_route
    return symbol, out, days_run


# ===========================================================================
# the gates
# ===========================================================================

def tier_old(row, signals_today, losses):
    """`live_scanner._tier` as it shipped BEFORE this row."""
    if row["setup"] == "reentry_84_rule":
        return "TRADE" if losses < 2 else "WATCH"
    if row["grade"] not in ("A+", "A") or row["ts"][:5] < TRADE_FLOOR:
        return "WATCH"
    return "TRADE" if signals_today == 0 and losses < 2 else "WATCH"


def tier_new(row, signals_today, losses):
    """`live_scanner._tier` as it ships AFTER this row."""
    if row["setup"] == "reentry_84_rule":
        return "TRADE" if losses < 2 else "WATCH"
    if row["tier"] != "S" or row["ts"][:5] < TRADE_FLOOR:
        return "WATCH"
    return "TRADE" if signals_today == 0 and losses < 2 else "WATCH"


def tier_new_notc(row, signals_today, losses):
    """Disclosure arm: the new gate PLUS the ladder's `C is alert-only`."""
    if row["setup"] == "reentry_84_rule":
        return "TRADE" if losses < 2 else "WATCH"
    if row["tier"] != "S" or row["grade"] == "C" or row["ts"][:5] < TRADE_FLOOR:
        return "WATCH"
    return "TRADE" if signals_today == 0 and losses < 2 else "WATCH"


def tier_new_reentry_s(row, signals_today, losses):
    """Disclosure arm: the new gate with the 84% re-entry ALSO S-gated."""
    if row["setup"] == "reentry_84_rule":
        return "TRADE" if (losses < 2 and row["tier"] == "S") else "WATCH"
    if row["tier"] != "S" or row["ts"][:5] < TRADE_FLOOR:
        return "WATCH"
    return "TRADE" if signals_today == 0 and losses < 2 else "WATCH"


def tier_new_nofloor(row, signals_today, losses):
    """Disclosure arm: the new gate with TRADE_FLOOR removed. Prices the 09:40
    floor, which under the old gate almost never got consulted."""
    if row["setup"] == "reentry_84_rule":
        return "TRADE" if losses < 2 else "WATCH"
    if row["tier"] != "S":
        return "WATCH"
    return "TRADE" if signals_today == 0 and losses < 2 else "WATCH"


def tier_aplus_only(row, signals_today, losses):
    """Disclosure arm: the gate the VAULT describes (`grade != "A+"`), which is
    not what this repo has ever committed. Prices the "fires twice" claim on a
    reproducible sample."""
    if row["setup"] == "reentry_84_rule":
        return "TRADE" if losses < 2 else "WATCH"
    if row["grade"] != "A+" or row["ts"][:5] < TRADE_FLOOR:
        return "WATCH"
    return "TRADE" if signals_today == 0 and losses < 2 else "WATCH"


ARMS = [
    ("aplus_only", tier_aplus_only),
    ("old", tier_old),
    ("new", tier_new),
    ("new_notC", tier_new_notc),
    ("new_reentryS", tier_new_reentry_s),
    ("new_nofloor", tier_new_nofloor),
]


# ===========================================================================
# the live replay
# ===========================================================================

def replay(rows, gate):
    """Replay `live_scanner`'s per-day promotion path over one arm.

    `rows` is every FIRED signal, already grouped and ordered per day. Returns
    (promotions, watch_dings, per_day_trade_days, promoted_rows).

    Mirrors scan_once + _emit_signal in order:
      session.day_ended() breaks the day; the 20-minute per symbol+direction
      cooldown suppresses before `_tier` is consulted (84% re-entries exempt);
      `_tier` decides; a WATCH past WATCH_DAILY_CAP is dropped; a TRADE
      increments signals_today.
    """
    promotions, dings, promoted = 0, 0, []
    trade_days = set()
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(r)
    for day in sorted(by_day):
        signals_today, losses, watch_n = 0, 0, 0
        last_alert = {}
        for r in sorted(by_day[day], key=lambda x: (x["ts"], x["symbol"])):
            # scan_once: session halt check, once per scan cycle
            if losses >= 2 or signals_today >= MAX_TRADES_PER_DAY:
                break
            is_reentry = r["setup"] == "reentry_84_rule"
            # _emit_signal: cooldown, before the tier is consulted
            if not is_reentry:
                mins = int(r["ts"][:2]) * 60 + int(r["ts"][3:5])
                prev = last_alert.get((r["symbol"], r["dir"]))
                if prev is not None and mins - prev < ALERT_COOLDOWN_MIN:
                    continue
                last_alert[(r["symbol"], r["dir"])] = mins
            t = gate(r, signals_today, losses)
            if t != "TRADE":
                if watch_n >= WATCH_DAILY_CAP:
                    continue
                watch_n += 1
                dings += 1
                continue
            promotions += 1
            promoted.append(r)
            trade_days.add(day)
            signals_today += 1
    return promotions, dings, trade_days, promoted


# ===========================================================================
# Austin's S days
# ===========================================================================

def load_s_days():
    """Symbol-days Austin marked S, restricted to days the archive carries."""
    days, marks = set(), 0
    if not os.path.exists(MARKS):
        return days, 0
    with open(MARKS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if (m.get("austin_tier") or "").strip() != "S":
                continue
            sym, day = m.get("symbol"), m.get("day")
            if not sym or not day:
                continue
            if not os.path.exists(os.path.join(ARCHIVE, sym, day + ".csv")):
                continue
            marks += 1
            days.add((sym, day))
    return days, marks


# ===========================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-08-12")
    ap.add_argument("--end", default="2026-08-11")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--rows", default="", help="reuse a previously dumped rows JSON")
    a = ap.parse_args()

    if a.rows and os.path.exists(a.rows):
        blob = json.load(open(a.rows))
        fired, days_run, syms = blob["fired"], blob["days_run"], blob["symbols"]
        captured = blob["captured"]
        skipped = blob["skipped_by_status_tier_grade"]
        print(f"reusing {a.rows}: {captured} captured signals, "
              f"{len(fired)} accepted", flush=True)
    else:
        syms = [s for s in (MAJOR_15 + INDEX_POOL + OTHER_POOL)
                if os.path.isdir(os.path.join(ARCHIVE, s))]
        print(f"symbols: {len(syms)}  range {a.start}..{a.end}", flush=True)
        rows, days_run = [], 0
        with Pool(a.procs) as pool:
            for sym, r, d in pool.imap_unordered(
                    _rows_for, [(s, a.start, a.end) for s in syms]):
                rows.extend(r)
                days_run += d
                print(f"  {sym}: {len(r)} signals over {d} days", flush=True)
        # The dump carries every ACCEPTED signal in full -- that is the set the
        # arms replay -- plus a (status, tier, grade) cross-tab for the ~125k
        # signals `_route` refused, which is all the report needs from them and
        # keeps the artifact the size of R1's and R3's rather than 25 MB.
        skipped_xtab = defaultdict(int)
        for r in rows:
            if r["status"] != "fired":
                skipped_xtab[f"{r['status']}|{r['tier']}|{r['grade']}"] += 1
        json.dump({"fired": [r for r in rows if r["status"] == "fired"],
                   "captured": len(rows),
                   "skipped_by_status_tier_grade": dict(sorted(skipped_xtab.items())),
                   "days_run": days_run, "symbols": syms,
                   "start": a.start, "end": a.end},
                  open(OUT_ROWS, "w"))
        print(f"wrote {OUT_ROWS}", flush=True)
        captured = len(rows)
        fired = [r for r in rows if r["status"] == "fired"]
        skipped = dict(sorted(skipped_xtab.items()))

    print()
    print(f"symbol-days replayed        : {days_run}")
    print(f"signals `_route` saw        : {captured}")
    print(f"  ...ACCEPTED (status=fired): {len(fired)}   <- what the live path sees")
    print(f"  ...skipped by _route      : {captured - len(fired)}")
    s_skipped = sum(v for k, v in skipped.items() if k.split("|")[1] == "S")
    s_x = sum(v for k, v in skipped.items()
              if k.split("|")[1] == "S" and k.split("|")[2] in ("X", "D"))
    print(f"tier-S signals _route REFUSED before the live path could see them: "
          f"{s_skipped} (engine X/D: {s_x})")
    print()

    # composition of the fired set
    by_tier = defaultdict(int)
    by_grade = defaultdict(int)
    cross = defaultdict(int)
    for r in fired:
        by_tier[r["tier"]] += 1
        by_grade[r["grade"]] += 1
        cross[(r["tier"], r["grade"])] += 1
    print("fired signals by austin_tier :",
          dict(sorted(by_tier.items(), key=lambda kv: str(kv[0]))))
    print("fired signals by engine grade:",
          dict(sorted(by_grade.items(), key=lambda kv: str(kv[0]))))
    s_rows = [r for r in fired if r["tier"] == "S"]
    s_by_grade = defaultdict(int)
    for r in s_rows:
        s_by_grade[r["grade"]] += 1
    print(f"of the {len(s_rows)} tier-S fired signals, engine grade:",
          dict(sorted(s_by_grade.items())))
    old_eligible = [r for r in fired if r["grade"] in ("A+", "A")]
    print(f"engine A+/A fired signals    : {len(old_eligible)} "
          f"(A+ alone: {sum(1 for r in fired if r['grade'] == 'A+')})")
    print(f"overlap S AND A+/A           : "
          f"{sum(1 for r in fired if r['tier'] == 'S' and r['grade'] in ('A+', 'A'))}")
    print()

    s_days, s_marks = load_s_days()
    print(f"Austin S-marked symbol-days with archived bars: {len(s_days)} "
          f"({s_marks} marks)")
    s_mark_days = {d for _, d in s_days}
    print()

    results = {}
    print(f"{'arm':<14}{'promotions':>11}{'trade-days':>12}{'watch dings':>13}"
          f"{'on S days':>11}{'on S sym-days':>14}{'S sym-day recall':>18}")
    for name, gate in ARMS:
        n, dings, tdays, promoted = replay(fired, gate)
        on_s_day = sum(1 for r in promoted if r["day"] in s_mark_days)
        on_s_symday = sum(1 for r in promoted if (r["symbol"], r["day"]) in s_days)
        hit_symdays = {(r["symbol"], r["day"]) for r in promoted
                       if (r["symbol"], r["day"]) in s_days}
        results[name] = dict(promotions=n, dings=dings, trade_days=len(tdays),
                             on_s_day=on_s_day, on_s_symday=on_s_symday,
                             s_symday_recall=len(hit_symdays),
                             s_symdays_hit=sorted(hit_symdays),
                             promoted=promoted)
        rec = f"{len(hit_symdays)}/{len(s_days)}"
        print(f"{name:<14}{n:>11}{len(tdays):>12}{dings:>13}"
              f"{on_s_day:>11}{on_s_symday:>14}{rec:>18}")
    print()
    for name, _ in ARMS:
        print(f"{name} S symbol-days hit: {results[name]['s_symdays_hit']}")
    print()

    for name in ("aplus_only", "old", "new"):
        promoted = results[name]["promoted"]
        gm = defaultdict(int)
        tm = defaultdict(int)
        sm = defaultdict(int)
        for r in promoted:
            gm[r["grade"]] += 1
            tm[r["tier"]] += 1
            sm[r["setup"]] += 1
        print(f"{name} promotions by engine grade: {dict(sorted(gm.items()))}")
        print(f"{name} promotions by austin_tier : "
              f"{dict(sorted(tm.items(), key=lambda kv: str(kv[0])))}")
        print(f"{name} promotions by setup       : {dict(sorted(sm.items()))}")
        nr = [r for r in promoted if r["setup"] != "reentry_84_rule"]
        nrt = defaultdict(int)
        for r in nr:
            nrt[r["tier"]] += 1
        print(f"{name} NON-re-entry promotions ({len(nr)}) by austin_tier: "
              f"{dict(sorted(nrt.items(), key=lambda kv: str(kv[0])))}")
    print()

    re_fired = [r for r in fired if r["setup"] == "reentry_84_rule"]
    re_tier = defaultdict(int)
    for r in re_fired:
        re_tier[r["tier"]] += 1
    print(f"84% re-entries in the fired set: {len(re_fired)}, by austin_tier: "
          f"{dict(sorted(re_tier.items(), key=lambda kv: str(kv[0])))}")
    for name in ("new", "new_reentryS"):
        n_re = sum(1 for r in results[name]["promoted"]
                   if r["setup"] == "reentry_84_rule")
        print(f"  {name}: {n_re} of {results[name]['promotions']} promotions are re-entries")
    print()

    summary = {k: {kk: vv for kk, vv in v.items() if kk != "promoted"}
               for k, v in results.items()}
    summary["sample"] = dict(days_run=days_run, symbols=len(syms),
                             captured=captured, fired=len(fired),
                             s_tier_refused_upstream=s_skipped,
                             s_tier_refused_as_engine_x=s_x,
                             s_marks=s_marks, s_symdays=len(s_days),
                             start=a.start, end=a.end)
    out = os.path.join(HERE, "g94_live_tier_summary.json")
    json.dump(summary, open(out, "w"), indent=2)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
