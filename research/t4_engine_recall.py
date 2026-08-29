"""omen-3.6 T4: does the engine fire where Austin says S?

Run the engine's OWN entry detection over the 151 marked (symbol, day) pairs
and record every entry it would take, with its bar index. Then join against
research/austin_marks_v2.jsonl on symbol|day with +/-2 bar tolerance and score:

  - Recall by tier (S / A / X): of each tier's marks, how many the engine fired
    an entry within +/-2 bars of.
  - Precision: of all engine entries on the marked days, the fraction that land
    on a marked bar, and the tier mix of those that do.
  - Engine entries on marked days Austin did not mark at all.

Detection module/function: signal_runner.SignalRunner.detect_signals (replayed
bar-by-bar, mirroring backtest_week.simulate_day's walk-forward loop + 30-bar
per-setup-idea dedupe + 11:00 entry cutoff). Level inputs (PDH/PDL/PMH/PML/HTF
bias) are reconstructed from data_archive so the engine sees the same structure
live_scanner would feed it. The 84% re-entry rule is NOT armed (it needs a
stopped prior trade's state, which this detection-only replay does not carry).

Reads only T1 (austin_marks_v2.jsonl) and T2 (the data_archive bar material +
levels.py that mark_features.py already established coverage for). Independent
of T3.
"""

from __future__ import annotations
import json, os, sys, csv, glob
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)        # research/levels.py
sys.path.insert(0, ROOT)        # signal_runner, omen_bot
import levels
from signal_runner import SignalRunner
from omen_bot import Candle, TradeGrade

MARKS = os.path.join(HERE, "austin_marks_v2.jsonl")
OUT_SIGNALS = os.path.join(HERE, "engine_signals.jsonl")
OUT_ENTRIES = os.path.join(HERE, "engine_entries.jsonl")
OUT_MD = os.path.join(HERE, "engine_recall.md")

# R16: mirrors backtest_week.dedupe_window() -- dedupe by LEVEL, not by clock.
# Austin: "it doesent matter when the trade re sets up as long as it happens
# during the window". Imported rather than copied so the recall harness and the
# book can never disagree about what one idea is again.
from backtest_week import dedupe_window as _dedupe_window  # noqa: E402
DEDUPE_BARS = _dedupe_window()
ENTRY_CUTOFF = "11:00:00"  # Scarface trades 9:30-11 only (production)
TOL = 2                 # +/-2 bar join tolerance
TIER_RANK = {"S": 3, "A": 2, "X": 1}

# Pools come from universe.py (OMEN 6 ticket 14). The copy that used to live
# here still carried MSTR and HTZ -- both retired 2026-07-11 -- and omitted
# ACHR, NFLX and ORCL, so per-pool reporting had drifted from the traded set.
from universe import (INDEX_POOL_SET as INDEX_POOL,  # noqa: F401
                      EQUITY_POOL, pool_for)


def _to_min(dtstr: str) -> str:
    return dtstr[11:16]  # "HH:MM"


def _raw_rows(symbol: str, day: str):
    p = os.path.join(levels.ARCHIVE, symbol, f"{day}.csv")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return list(csv.DictReader(f))


def rth_candles(symbol: str, day: str):
    rows = _raw_rows(symbol, day)
    if not rows:
        return None
    rth = [r for r in rows if _to_min(r["Datetime"]) >= "09:30"]
    if not rth:
        return None
    return [Candle(timestamp=_to_min(r["Datetime"]) + ":00",
                  open=float(r["Open"]), high=float(r["High"]),
                  low=float(r["Low"]), close=float(r["Close"]),
                  volume=int(float(r["Volume"] or 0))) for r in rth]


def premarket_extremes(symbol: str, day: str):
    """Same-day PMH/PML: high/low of 04:00-09:29 extended-hours bars (what
    live_scanner feeds as runner.pmh/pml)."""
    rows = _raw_rows(symbol, day)
    if not rows:
        return (None, None)
    pm = [r for r in rows if "04:00" <= _to_min(r["Datetime"]) < "09:30"]
    if not pm:
        return (None, None)
    return (max(float(r["High"]) for r in pm), min(float(r["Low"]) for r in pm))


def prior_day_levels(symbol: str, day: str):
    """PDH/PDL + prior-day open/close from the prior archived trading day
    (levels._prior_day + load_rth_bars)."""
    prev = levels._prior_day(symbol, day)
    if not prev:
        return (None, None, None, None)
    bars = levels.load_rth_bars(symbol, prev)
    if not bars:
        return (None, None, None, None)
    return (max(b["h"] for b in bars), min(b["l"] for b in bars),
            bars[0]["o"], bars[-1]["c"])


def htf_bias(symbol: str, day: str):
    """Close-vs-SMA20 over prior archived days' RTH closes (mirrors
    signal_runner.daily_trend_bias / backtest_week.htf_bias_for)."""
    files = sorted(glob.glob(os.path.join(levels.ARCHIVE, symbol, "*.csv")))
    names = [os.path.basename(f)[:-4] for f in files]
    if day not in names:
        return None
    i = names.index(day)
    closes = []
    for d in names[max(0, i - 40):i]:
        b = levels.load_rth_bars(symbol, d)
        if b:
            closes.append(b[-1]["c"])
    if len(closes) < 20:
        return None
    sma = sum(closes[-20:]) / 20
    last = closes[-1]
    if last > sma * 1.001:
        return "bullish"
    if last < sma * 0.999:
        return "bearish"
    return "neutral"


class CaptureRunner(SignalRunner):
    """Capture EVERY signal the engine produces (fired + D-grade/tight-stop
    skips) so we can separate detection (any signal) from filtering (fired
    only). Mirrors backtest_week.BacktestRunner, but records the status."""
    def __init__(self, symbol):
        super().__init__(post_to_discord=False, symbol=symbol, log_signals=False)
        self.captured = []

    def _route(self, signals, sig):
        self._grade_for_levels(sig)
        self._calibration_grade(sig)
        # T10: this replay does NOT delegate to super()._route (it labels the
        # rejection reason instead), so every gate the base grows has to be
        # named here or it is inert in exactly the rig that scores held-out
        # recall -- regression_gate, t70_test1_score and t0_heldout_recall all
        # run through this class. `_apply_x_lift` is a no-op unless X_LIFT is
        # set. research/test_t10_x_lift.py fails if this call disappears.
        self._apply_x_lift(sig)
        if sig["grade"] != TradeGrade.D.value:
            if (sig["grade"] != "C"
                    or self._min_viable_stop(sig["entry"], sig["stop"], sig["direction"])):
                sig["status"] = "fired"
                self._dir_fired[sig["direction"]] = self._dir_fired.get(sig["direction"], 0) + 1
                signals.append(sig)
            else:
                sig["status"] = "skipped_tight"
        else:
            sig["status"] = "skipped_d"
        self.captured.append(sig)


def run_day(symbol: str, day: str):
    """Replay detect_signals bar-by-bar. Returns (entries, all_sigs):
      entries  - deduped entries the engine would TAKE (status fired), with bar
      all_sigs - every signal produced (any grade/status), with bar (deduped too
                 so repeat fires of the same setup don't double-count detection).
    """
    candles = rth_candles(symbol, day)
    if not candles:
        return None, None, None  # no archived bars -> engine cannot run
    pdh, pdl, pdo, pdc = prior_day_levels(symbol, day)
    pmh, pml = premarket_extremes(symbol, day)
    runner = CaptureRunner(symbol)
    runner.pdh, runner.pdl = pdh, pdl
    runner.pmh, runner.pml = pmh, pml
    runner.pd_open, runner.pd_close = pdo, pdc
    runner.htf_bias = htf_bias(symbol, day)
    runner.qqq_breaks = None

    entries = []
    all_sigs = []
    raw_sigs = []  # every captured signal, no dedupe (true upper bound)
    seen = {}     # (signal_type, direction, idea) -> last bar index (fired dedupe)
    seen_any = {}  # same key for all-signal dedupe (detection counting)
    for i in range(5, len(candles)):
        c = candles[i]
        if ENTRY_CUTOFF and c.timestamp >= ENTRY_CUTOFF:
            continue
        runner.candles = candles[: i + 1]
        before = len(runner.captured)
        runner.detect_signals()
        for sig in runner.captured[before:]:
            rec = {"symbol": symbol, "day": day, "bar": i,
                   "timestamp": c.timestamp, "signal_type": sig["signal_type"].value,
                   "direction": sig["direction"], "grade": sig["grade"],
                   "status": sig["status"], "stop_level": sig.get("stop_level_name"),
                   "entry": sig["entry"], "stop": sig["stop"]}
            raw_sigs.append(rec)
            idea = (sig.get("stop_level_name")
                    if sig["signal_type"].value == "break_and_retest"
                    else round(sig["stop"], 2))
            key = (sig["signal_type"].value, sig["direction"], idea)
            # all-signal dedupe (one per setup per window, first occurrence)
            if key in seen_any and i - seen_any[key] < DEDUPE_BARS:
                seen_any[key] = i
            else:
                seen_any[key] = i
                all_sigs.append(rec)
            # fired-only dedupe (entries it would take): first FIRED per setup
            if sig["status"] == "fired":
                if key in seen and i - seen[key] < DEDUPE_BARS:
                    seen[key] = i
                    continue
                seen[key] = i
                entries.append({
                    "symbol": symbol, "day": day, "bar": i,
                    "timestamp": c.timestamp, "signal_type": sig["signal_type"].value,
                    "direction": sig["direction"], "grade": sig["grade"],
                    "stop_level": sig.get("stop_level_name"),
                    "entry": sig["entry"], "stop": sig["stop"],
                })
    return entries, all_sigs, raw_sigs


def main():
    marks = [json.loads(l) for l in open(MARKS) if l.strip()]
    by_pair = defaultdict(list)
    for m in marks:
        by_pair[(m["symbol"], m["day"])].append(m)

    all_entries = []
    all_sigs = []
    raw_sigs = []
    raw_by_day = defaultdict(list)
    firedraw_by_day = defaultdict(list)
    pair_has_archive = {}
    for (sym, day) in sorted(by_pair):
        ent, sigs, raw = run_day(sym, day)
        pair_has_archive[(sym, day)] = ent is not None
        if ent is not None:
            all_entries.extend(ent)
            all_sigs.extend(sigs)
            raw_sigs.extend(raw)
            for r in raw:
                raw_by_day[(sym, day)].append(r["bar"])
                if r["status"] == "fired":
                    firedraw_by_day[(sym, day)].append(r["bar"])

    with open(OUT_ENTRIES, "w") as f:
        for e in all_entries:
            f.write(json.dumps(e) + "\n")
    with open(OUT_SIGNALS, "w") as f:
        for s in all_sigs:
            f.write(json.dumps(s) + "\n")

    sig_by_day = defaultdict(list)
    for s in all_sigs:
        sig_by_day[(s["symbol"], s["day"])].append(s)

    # ---- recall: a mark is detected if any engine entry bar within +/-2 ----
    tier_total = Counter(m["tier"] for m in marks)
    tier_hit = Counter()        # by fired entry (deduped)
    tier_any = Counter()        # by any signal (any grade/status, deduped)
    tier_raw = Counter()        # by any captured signal bar (no dedupe)
    tier_firedraw = Counter()   # by any fired captured bar (no dedupe)
    testable_total = Counter()
    testable_hit = Counter()
    testable_any = Counter()
    testable_raw = Counter()
    for m in marks:
        key = (m["symbol"], m["day"])
        ent_bars = [e["bar"] for e in all_entries
                    if e["symbol"] == m["symbol"] and e["day"] == m["day"]]
        sig_bars = [s["bar"] for s in sig_by_day.get(key, [])]
        hit = any(abs(b - m["entry_i"]) <= TOL for b in ent_bars)
        any_hit = any(abs(b - m["entry_i"]) <= TOL for b in sig_bars)
        raw_hit = any(abs(b - m["entry_i"]) <= TOL for b in raw_by_day.get(key, []))
        firedraw_hit = any(abs(b - m["entry_i"]) <= TOL
                           for b in firedraw_by_day.get(key, []))
        if pair_has_archive.get(key):
            testable_total[m["tier"]] += 1
            if hit:
                testable_hit[m["tier"]] += 1
            if any_hit:
                testable_any[m["tier"]] += 1
            if raw_hit:
                testable_raw[m["tier"]] += 1
        if hit:
            tier_hit[m["tier"]] += 1
        if any_hit:
            tier_any[m["tier"]] += 1
        if raw_hit:
            tier_raw[m["tier"]] += 1
        if firedraw_hit:
            tier_firedraw[m["tier"]] += 1

    # ---- precision: engine entries on marked days ----
    marked_days = set(by_pair)  # the 151 (symbol,day) pairs
    day_marks = defaultdict(list)
    for m in marks:
        day_marks[(m["symbol"], m["day"])].append(m)

    on_marked_days = [e for e in all_entries
                      if (e["symbol"], e["day"]) in marked_days]
    matched = []
    unmatched = []
    for e in on_marked_days:
        ms = day_marks[(e["symbol"], e["day"])]
        near = [m for m in ms if abs(e["bar"] - m["entry_i"]) <= TOL]
        if near:
            best = max(near, key=lambda m: TIER_RANK.get(m["tier"], 0))
            e_match = dict(e)
            e_match["matched_tier"] = best["tier"]
            matched.append(e_match)
        else:
            unmatched.append(e)

    matched_tier_mix = Counter(e["matched_tier"] for e in matched)
    matched_grade_mix = Counter(e["grade"] for e in matched)
    all_grade_mix = Counter(e["grade"] for e in on_marked_days)
    precision = len(matched) / len(on_marked_days) if on_marked_days else 0.0

    # all-signal (any grade) recall and signal status mix (true raw = every
    # captured signal, no dedupe — the honest mix and the true upper bound)
    S_a, A_a, X_a = tier_any["S"], tier_any["A"], tier_any["X"]
    S_r, A_r, X_r = tier_raw["S"], tier_raw["A"], tier_raw["X"]
    S_fr, A_fr, X_fr = tier_firedraw["S"], tier_firedraw["A"], tier_firedraw["X"]
    status_mix = Counter(s["status"] for s in raw_sigs)
    grade_mix_all = Counter(s["grade"] for s in raw_sigs)
    n_raw = len(raw_sigs)
    n_fired_raw = status_mix["fired"]

    # ---- write report ----
    S_tot, A_tot, X_tot = tier_total["S"], tier_total["A"], tier_total["X"]
    S_h, A_h, X_h = tier_hit["S"], tier_hit["A"], tier_hit["X"]
    lines = []
    lines.append("# engine_recall")
    lines.append("")
    lines.append("Detection: `signal_runner.SignalRunner.detect_signals` "
                 "(replayed bar-by-bar; see footer).")
    lines.append("")
    lines.append("## Recall by tier — fired entries (all marks; +/-2 bars)")
    lines.append(f"- **S: {S_h}/{S_tot}** detected")
    lines.append(f"- **A: {A_h}/{A_tot}** detected")
    lines.append(f"- **X: {X_h}/{X_tot}** detected")
    lines.append("")
    lines.append(f"Precision: **{len(matched)}/{len(on_marked_days)} = "
                 f"{precision:.1%}** of engine entries on marked days land on "
                 f"a marked bar.")
    lines.append("")
    lines.append("Denominators: join target `research/austin_marks_v2.jsonl` "
                 f"has {S_tot} S / {A_tot} A / {X_tot} X (159, post-dedup). The "
                 "spec's 78/60/24 are the pre-dedup `austin_verdicts.json` (162); "
                 "the 3 collapsed rows are exact symbol|day|entry_i twins, so the "
                 f"detected counts are identical vs that base: S {S_h}/78, "
                 f"A {A_h}/60, X {X_h}/24.")
    lines.append("")
    lines.append("## Verdict")
    lines.append(f"- Fired S recall is **{S_h}/{S_tot} = {S_h/S_tot:.0%}**. "
                 "The engine does not take the trades Austin grades S.")
    lines.append(f"- Even the generous upper bound — ANY captured signal, ANY "
                 f"grade (incl. D-skips), every bar — is only S {S_r}/{S_tot} = "
                 f"{S_r/S_tot:.0%}. The engine produces NO signal at ~"
                 f"{(S_tot-S_r)/S_tot:.0%} of S bars. (No-dedupe fired-only is "
                 f"also just S {S_fr}/{S_tot}.)")
    lines.append(f"- Of the {n_raw} signals the engine produces (raw, every bar), "
                 f"{status_mix['skipped_d']} are downgraded to D and only "
                 f"{n_fired_raw} fire — mostly tight-stop kills (e.g. an S at "
                 "the OR high with stop $0.22 on a $537 stock). A filter problem "
                 "sits on top, but it is secondary: even counting every fired "
                 f"bar, S recall is {S_fr}/{S_tot} = {S_fr/S_tot:.0%}.")
    lines.append("- This is a **detection problem, not a filter problem**. No "
                 "gate on the trades the engine already takes can recover "
                 "setups it never sees. The next version has to widen what "
                 "the engine detects (level vocabulary / break-and-retest "
                 "geometry), not tune what it filters.")
    lines.append("")
    lines.append("## Recall — any signal, any grade (detection vs filtering)")
    lines.append(f"- S: {S_a}/{S_tot}, A: {A_a}/{A_tot}, X: {X_a}/{X_tot} — "
                 "marks with ANY engine signal (incl. D/tight-stop skips, "
                 f"deduped) within +/-{TOL} bars.")
    lines.append(f"- S: {S_r}/{S_tot}, A: {A_r}/{A_tot}, X: {X_r}/{X_tot} — "
                 "same but counting EVERY captured signal bar (no dedupe; the "
                 "true upper bound on 'the engine produced a signal here').")
    lines.append(f"- No-dedupe FIRED only: S {S_fr}/{S_tot}, "
                 f"A {A_fr}/{A_tot}, X {X_fr}/{X_tot}.")
    lines.append(f"- Raw captured signal status mix: {dict(status_mix)}")
    lines.append(f"- Raw captured signal grade mix: {dict(grade_mix_all)}")
    lines.append("")
    lines.append("## Recall — testable marks only (archive present; isolates "
                 "detection/filter from the 54 no-archive misses)")
    lines.append(f"- Fired: S {testable_hit['S']}/{testable_total['S']}, "
                 f"A {testable_hit['A']}/{testable_total['A']}, "
                 f"X {testable_hit['X']}/{testable_total['X']}")
    lines.append(f"- Any signal (deduped): S {testable_any['S']}/{testable_total['S']}, "
                 f"A {testable_any['A']}/{testable_total['A']}, "
                 f"X {testable_any['X']}/{testable_total['X']}")
    lines.append(f"- Any signal (raw, upper bound): S {testable_raw['S']}/{testable_total['S']}, "
                 f"A {testable_raw['A']}/{testable_total['A']}, "
                 f"X {testable_raw['X']}/{testable_total['X']}")
    lines.append("")
    lines.append("## Precision detail")
    lines.append(f"- Engine entries on marked days: **{len(on_marked_days)}**")
    lines.append(f"- Landing on a marked bar: **{len(matched)}** "
                 f"(tier mix — matched mark's tier: "
                 f"S {matched_tier_mix['S']}, A {matched_tier_mix['A']}, "
                 f"X {matched_tier_mix['X']})")
    lines.append(f"- Matched engine-entry grade mix: "
                 f"{dict(matched_grade_mix)}")
    lines.append(f"- Engine entries on marked days Austin did NOT mark: "
                 f"**{len(unmatched)}**")
    lines.append("")
    lines.append("## Method")
    lines.append("- Marks: `research/austin_marks_v2.jsonl` "
                 f"({len(marks)} marks, {len(marked_days)} distinct symbol|day).")
    lines.append("- Bars: `data_archive/<SYMBOL>/<DAY>.csv` RTH 1-min; "
                 "54 marks have no archive (engine cannot run -> counted as "
                 "recall misses in the all-marks column; isolated in the "
                 "testable-only column).")
    no_archive_pairs = sum(1 for v in pair_has_archive.values() if not v)
    lines.append(f"- Marked days with no archived bars: {no_archive_pairs} "
                 f"(of {len(marked_days)}).")
    lines.append("- Replay: for each bar i in 5..N, `runner.candles = "
                 "candles[:i+1]`; `runner.detect_signals()`. *Fired* entries = "
                 "A+/A/B, or C with a viable stop (D and tight-stop-C are "
                 "skipped by `SignalRunner._route`, captured separately for the "
                 "any-signal column). One entry per setup idea per "
                 f"{DEDUPE_BARS}-bar window (backtest_week.DEDUPE_BARS); entry "
                 f"cutoff {ENTRY_CUTOFF} (all marks fall before it).")
    lines.append("- Level inputs reconstructed from the archive: PDH/PDL from "
                 "the prior archived day, PMH/PML from the same day's 04:00-09:29 "
                 "bars, HTF bias from prior days' close-vs-SMA20. 84% re-entries "
                 "are not armed (need a stopped prior trade's state).")
    lines.append("- A mark is *detected* if any engine entry bar is within "
                 f"+/-{TOL} of the mark's entry_i.")
    lines.append("")
    lines.append(f"Raw dumps: `research/engine_entries.jsonl` "
                 f"({len(all_entries)} fired entries, deduped) and "
                 f"`research/engine_signals.jsonl` ({len(all_sigs)} deduped "
                 "all-grade signals; the raw per-bar capture is recomputed "
                 "in-process for the mixes above) across all replayed days.")

    open(OUT_MD, "w").write("\n".join(lines) + "\n")

    # console summary
    print(f"fired   S {S_h}/{S_tot}  A {A_h}/{A_tot}  X {X_h}/{X_tot}")
    print(f"any-sig S {S_a}/{S_tot}  A {A_a}/{A_tot}  X {X_a}/{X_tot}")
    print(f"raw-sig S {S_r}/{S_tot}  A {A_r}/{A_tot}  X {X_r}/{X_tot}")
    print(f"firedraw S {S_fr}/{S_tot} A {A_fr}/{A_tot} X {X_fr}/{X_tot}")
    print(f"testable fired  S {testable_hit['S']}/{testable_total['S']} A {testable_hit['A']}/{testable_total['A']} X {testable_hit['X']}/{testable_total['X']}")
    print(f"testable raw    S {testable_raw['S']}/{testable_total['S']} A {testable_raw['A']}/{testable_total['A']} X {testable_raw['X']}/{testable_total['X']}")
    print(f"status mix {dict(status_mix)}  grade mix {dict(grade_mix_all)}")
    print(f"precision {len(matched)}/{len(on_marked_days)} = {precision:.1%}")
    print(f"unmarked engine entries: {len(unmatched)}")
    print(f"entries total: {len(all_entries)}; all_sigs(deduped): {len(all_sigs)}; "
          f"raw_sigs: {len(raw_sigs)}; on marked days: {len(on_marked_days)}")

    # ---- per-pool recall (omen-3.9 T7) ----
    pool_total = Counter()
    pool_hit = Counter()
    pool_any = Counter()
    pool_raw = Counter()
    pool_testable_total = Counter()
    pool_testable_hit = Counter()
    for m in marks:
        p = pool_for(m["symbol"])
        key = (m["symbol"], m["day"])
        ent_bars = [e["bar"] for e in all_entries
                    if e["symbol"] == m["symbol"] and e["day"] == m["day"]]
        sig_bars = [s["bar"] for s in sig_by_day.get(key, [])]
        hit = any(abs(b - m["entry_i"]) <= TOL for b in ent_bars)
        any_hit = any(abs(b - m["entry_i"]) <= TOL for b in sig_bars)
        raw_hit = any(abs(b - m["entry_i"]) <= TOL for b in raw_by_day.get(key, []))
        pool_total[p] += 1
        if pair_has_archive.get(key):
            pool_testable_total[p] += 1
            if hit:
                pool_testable_hit[p] += 1
        if hit:
            pool_hit[p] += 1
        if any_hit:
            pool_any[p] += 1
        if raw_hit:
            pool_raw[p] += 1

    # per-pool precision: split on_marked_days entries by pool
    pool_on_marked = Counter()
    pool_matched = Counter()
    for e in on_marked_days:
        p = pool_for(e["symbol"])
        pool_on_marked[p] += 1
    for e in matched:
        p = pool_for(e["symbol"])
        pool_matched[p] += 1

    print("")
    print("--- per-pool (omen-3.9 T7) ---")
    for p in ["index", "equity", "other"]:
        t = pool_total[p]
        h = pool_hit[p]
        a = pool_any[p]
        r = pool_raw[p]
        tt = pool_testable_total[p]
        th = pool_testable_hit[p]
        pom = pool_on_marked.get(p, 0)
        pm = pool_matched.get(p, 0)
        prec = pm / pom if pom else 0.0
        print(f"{p:7s} fired {h}/{t}  any-sig {a}/{t}  raw {r}/{t}  "
              f"testable-fired {th}/{tt}  precision {pm}/{pom}={prec:.0%}")


if __name__ == "__main__":
    main()
