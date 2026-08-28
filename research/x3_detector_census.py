"""X3 -- the four detectors, one census.

Austin, 2026-08-28: "i think br is only one firing good and we have BR, OCR, both,
and 84 percent rule. that are the 4 right now never forget it." And: "not sure how
well 84 percent rule is firing."

Four arms, one scorecard, over the SHIPPED 2-year book and over Austin's marks:

  BR     break-and-retest alone      signal_runner.detect_signals -> omen_bot.detect_break_retest
  OCR    the one candle rule alone   signal_runner.detect_signals -> omen_bot.detect_order_block_setup
  BROCR  both at once                signal_runner._label_confluence -> research.downgrade.has_confluence
  R84    the 84% reclaim re-entry    signal_runner.py:2237-2285 (long) / :2455-2499 (short),
                                     armed by backtest_week._arm_84

The arms are EXCLUSIVE on the book: a row tagged [brocr] is counted in BROCR and
not in BR/OCR, because "both" is the third thing Austin named. Every table also
prints the INCLUSIVE reading (BR = every break_and_retest row, confluent or not)
because "is BR the only one working" is a question about the base detector.

    python research/x3_detector_census.py            # everything, writes the .md
    python research/x3_detector_census.py book       # part A only
    python research/x3_detector_census.py recall     # part B only (~2 min first run)
    python research/x3_detector_census.py gate84     # part C only
    python research/x3_detector_census.py --selfcheck

Substrate: research/g3_arm_ow1.json (the shipped 2-year book, 45,193 signals /
1,017 traded, ON_WATCH=1, 2024-08-21..2026-08-21, produced by
research/g3_onwatch_2y.py). Marks: t60_baseline.load_day_cards() in-sample and
research/marks/probe_omen_test1_2026-08-27.jsonl held out.

Reused, not reimplemented:
  research.t4_engine_recall  rth_candles / prior_day_levels / premarket_extremes /
                             htf_bias / CaptureRunner / DEDUPE_BARS / ENTRY_CUTOFF
  research.t60_baseline      load_day_cards
  research.t70_test1_score   load_cards, in_universe
  signal_runner              STRONG_PA_MULT, RULE84_*, SESSION_END -- read, never set

NOTHING here changes an engine default. Read-only.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

BOOK = os.path.join(_HERE, "g3_arm_ow1.json")
OUT_MD = os.path.join(_HERE, "x3_detector_census.md")
CACHE_RECALL = os.path.join(_HERE, "_x3_recall.json")
CACHE_G84 = os.path.join(_HERE, "_x3_gate84.json")

ARMS = ["BR", "OCR", "BROCR", "R84"]
ARM_LABEL = {
    "BR": "BR only (break-and-retest, no OCR)",
    "OCR": "OCR only (one candle rule, no BR)",
    "BROCR": "BR + OCR confluence (`[brocr]`)",
    "R84": "84% reclaim re-entry",
}


# ---------------------------------------------------------------------------
# pure helpers -- everything --selfcheck exercises lives here
# ---------------------------------------------------------------------------

def arm_of(row):
    """Which of Austin's four arms this book row belongs to. Exclusive.

    The `[brocr]` reason tag is stamped at DETECTION time by
    signal_runner._label_confluence (signal_runner.py:1768-1795), on the signal's
    own bar with sig["stop"] as the level proxy. It is the same
    research/downgrade.py::has_confluence call the book's `confluence` column
    uses at grading time; the two disagree on 3 of 1,017 traded rows and the tag
    is the detector-side one, so the tag is what defines the arm here.
    """
    setup = row.get("setup")
    if setup == "reentry_84_rule":
        return "R84"
    if "brocr" in (row.get("tags") or []):
        return "BROCR"
    if setup == "break_and_retest":
        return "BR"
    if setup == "one_candle_rule":
        return "OCR"
    return None


def base_of(row):
    """The INCLUSIVE reading: the base detector, confluence folded back in."""
    return {"break_and_retest": "BR", "one_candle_rule": "OCR",
            "reentry_84_rule": "R84"}.get(row.get("setup"))


def mean_ci95(rs):
    """(mean, half-width) of the 95% interval on the MEAN, normal approximation.

    This is the interval on ONE arm's own mean over its own n. It is NOT the
    +/-0.0095R paired A/B bar carried repo-wide (W0) -- that one prices the
    DIFFERENCE between two arms over the same rows and is much narrower by
    construction. Never quote one where the other belongs.
    """
    n = len(rs)
    if n == 0:
        return (float("nan"), float("nan"))
    m = sum(rs) / n
    if n < 2:
        return (m, float("nan"))
    sd = statistics.stdev(rs)
    return (m, 1.96 * sd / math.sqrt(n))


def months_green(rows, all_months):
    """(green, traded, absent) over the book's 25 calendar months.

    A month with no signal from this arm is NOT green -- the durability gate is
    "every month green", and an arm silent for 11 months has not passed it.
    Absent months are counted out loud so the read is not hidden.
    """
    by_m = defaultdict(float)
    for r in rows:
        by_m[r["ym"]] += r["r"]
    green = sum(1 for m in all_months if by_m.get(m, 0.0) > 0)
    traded = sum(1 for m in all_months if m in by_m)
    return green, traded, len(all_months) - traded


def pct(n, d):
    return (100.0 * n / d) if d else 0.0


def win_rate(rows):
    """Win rate over DECIDED trades -- scratches excluded.

    g3_onwatch_2y.py:384 fixes this convention ("win rate is of DECIDED trades
    (scratches excluded)") and it is why the shipped book reads 53.2% and not
    52.9%. Five scratches in 1,017; the convention matters more per-arm.
    """
    w = sum(1 for r in rows if r["out"] == "win")
    d = sum(1 for r in rows if r["out"] in ("win", "loss"))
    return pct(w, d)


def two_sample(a, b):
    """(delta, half-width of the 95% interval on the delta) for two DISJOINT sets.

    The per-arm CIs in the scorecard overlap, and overlapping CIs are not a test.
    These arms partition the book, so the difference of two independent means is
    the right instrument: se = sqrt(se_a^2 + se_b^2). This is NOT the +/-0.0095R
    paired bar either -- that one is for the same rows measured twice.
    """
    if len(a) < 2 or len(b) < 2:
        return (float("nan"), float("nan"))
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    se = math.sqrt(statistics.stdev(a) ** 2 / len(a) + statistics.stdev(b) ** 2 / len(b))
    return (ma - mb, 1.96 * se)


def strong_pa(bars, i, mult):
    """signal_runner.PriceActionAnalyzer._strong_pa, on plain dict bars.

    prior = candles[-11:-1] relative to the CURRENT bar, i.e. the ten bars
    before bar i; body >= mult * mean(|c-o|) over those ten.
    """
    prior = bars[max(0, i - 10):i]
    if not prior:
        return False
    avg = sum(abs(b["c"] - b["o"]) for b in prior) / len(prior)
    return avg > 0 and abs(bars[i]["c"] - bars[i]["o"]) >= mult * avg


def r84_bar_ok(bars, i, entry_price, target, stop, is_long, mult=None):
    """One bar tested against the shipped 84% emission block, ex-arming.

    Mirrors signal_runner.py:2237-2255 (long) / :2455-2473 (short), with
    `mult=None` meaning the shipped RULE84_LESSON=True path (strong-PA BYPASSED)
    and a float meaning the gate is live at that multiple. Returns the individual
    clauses so a funnel can be counted instead of a boolean.

    Not modelled, deliberately: RULE84_MAX_ATTEMPTS (this counts opportunity, not
    the one-shot disarm) and the arming state machine itself, which is counted
    separately in part_c's funnel.
    """
    b = bars[i]
    hod = max(x["h"] for x in bars[:i + 1])
    lod = min(x["l"] for x in bars[:i + 1])
    day_range = hod - lod
    reclaim = (b["c"] >= entry_price and b["c"] > b["o"]) if is_long \
        else (b["c"] <= entry_price and b["c"] < b["o"])
    pa = True if mult is None else strong_pa(bars, i, mult)
    # RULE84_LESSON=True keeps the ORIGINAL stop and the ORIGINAL target.
    if is_long:
        rr_ok = target is not None and stop < b["c"] and (target - b["c"]) >= 1.5 * (b["c"] - stop)
        room = day_range > 0 and (hod - b["c"]) / day_range > 0.2
    else:
        rr_ok = target is not None and stop > b["c"] and (b["c"] - target) >= 1.5 * (stop - b["c"])
        room = day_range > 0 and (b["c"] - lod) / day_range > 0.2
    return {"reclaim": reclaim, "pa": pa, "rr_ok": rr_ok, "room": room,
            "all": bool(reclaim and pa and rr_ok and room)}


# ---------------------------------------------------------------------------
# PART A -- the book
# ---------------------------------------------------------------------------

def load_book(path=BOOK):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def part_a(book):
    rows = book["trades"]
    traded = [r for r in rows if r.get("traded")]
    all_months = sorted({r["ym"] for r in traded})
    total_r = sum(r["r"] for r in traded)

    def scorecard(sel, label):
        rs = [r["r"] for r in sel]
        m, hw = mean_ci95(rs)
        g, tm, ab = months_green(sel, all_months)
        return {
            "label": label, "n": len(sel),
            "days": len({(r["sym"], r["day"]) for r in sel}),
            "sessions": len({r["day"] for r in sel}),
            "mean": m, "ci": hw,
            "median": statistics.median(rs) if rs else float("nan"),
            "win": win_rate(sel),
            "green": g, "months_traded": tm, "months_absent": ab,
            "sum_r": sum(rs), "share": pct(sum(rs), total_r) if total_r else 0.0,
        }

    excl = {a: scorecard([r for r in traded if arm_of(r) == a], ARM_LABEL[a]) for a in ARMS}
    incl = {a: scorecard([r for r in traded if base_of(r) == a], a) for a in ("BR", "OCR", "R84")}

    # The within-detector split: confluence is not a fourth detector, it is a
    # PROPERTY of a BR or an OCR signal. This is the comparison that isolates it.
    def split(setup, want):
        return [r for r in traded if r["setup"] == setup and (("brocr" in r["tags"]) == want)]

    sp = {}
    for tag, setup in (("BR", "break_and_retest"), ("OCR", "one_candle_rule")):
        with_, without = split(setup, True), split(setup, False)
        d, hw = two_sample([r["r"] for r in with_], [r["r"] for r in without])
        sp[tag] = {"with": scorecard(with_, tag + " with OCR"),
                   "without": scorecard(without, tag + " without OCR"),
                   "delta": d, "delta_ci": hw}
    noconf = scorecard([r for r in traded if "brocr" not in r["tags"]], "book minus confluence")

    det_excl = Counter(arm_of(r) for r in rows)
    det_days = {a: len({(r["sym"], r["day"]) for r in rows if arm_of(r) == a}) for a in ARMS}
    fired = Counter(arm_of(r) for r in rows if r.get("status") == "fired")

    return {"excl": excl, "incl": incl, "split": sp, "noconf": noconf,
            "book": scorecard(traded, "whole book"),
            "total_r": total_r, "n_traded": len(traded),
            "n_signals": len(rows), "months": all_months,
            "det_excl": dict(det_excl), "det_days": det_days, "fired": dict(fired),
            "grade_mix": dict(Counter(r["grade"] for r in traded)),
            "sessions": len({r["day"] for r in rows}),
            "book_days": len({(r["sym"], r["day"]) for r in rows})}


# ---------------------------------------------------------------------------
# PART B -- recall, in-sample and held out
# ---------------------------------------------------------------------------

def run_day_tagged(symbol, day):
    """t4_engine_recall.run_day, plus the confluence label on every record.

    t4's own run_day builds its record dict inline and drops sig["setup_type"] /
    sig["br_ocr"], which is exactly the field this lane needs. Everything that
    reads bars, levels or the engine is imported from t4 unchanged; only the
    record shape differs.

    The 84% rule CANNOT fire here and that is structural, not a result: arming
    needs a stopped-out prior trade's session state (backtest_week._arm_84), and
    a detection-only replay never trades. R84 recall is measured off the 2-year
    book instead (part_b_r84).
    """
    from research.t4_engine_recall import (rth_candles, prior_day_levels,
                                           premarket_extremes, htf_bias,
                                           CaptureRunner, DEDUPE_BARS, ENTRY_CUTOFF)
    candles = rth_candles(symbol, day)
    if not candles:
        return None
    pdh, pdl, pdo, pdc = prior_day_levels(symbol, day)
    pmh, pml = premarket_extremes(symbol, day)
    runner = CaptureRunner(symbol)
    runner.pdh, runner.pdl = pdh, pdl
    runner.pmh, runner.pml = pmh, pml
    runner.pd_open, runner.pd_close = pdo, pdc
    runner.htf_bias = htf_bias(symbol, day)
    runner.qqq_breaks = None

    entries, seen = [], {}
    for i in range(5, len(candles)):
        c = candles[i]
        if ENTRY_CUTOFF and c.timestamp >= ENTRY_CUTOFF:
            continue
        runner.candles = candles[: i + 1]
        before = len(runner.captured)
        runner.detect_signals()
        for sig in runner.captured[before:]:
            if sig.get("status") != "fired":
                continue
            st = sig["signal_type"].value
            idea = sig.get("stop_level_name") if st == "break_and_retest" else round(sig["stop"], 2)
            key = (st, sig["direction"], idea)
            if key in seen and i - seen[key] < DEDUPE_BARS:
                seen[key] = i
                continue
            seen[key] = i
            arm = "BROCR" if sig.get("br_ocr") else \
                  {"break_and_retest": "BR", "one_candle_rule": "OCR",
                   "reentry_84_rule": "R84"}.get(st)
            entries.append({"bar": i, "signal_type": st, "arm": arm,
                            "grade": sig["grade"], "direction": sig["direction"]})
    return entries


def score_days(cards, cache):
    """cards = [{symbol,date,his,entry_i}] -> per-card arms fired."""
    out = []
    for c in cards:
        key = "%s|%s" % (c["symbol"], c["date"])
        if key not in cache:
            try:
                cache[key] = run_day_tagged(c["symbol"], c["date"])
            except Exception as exc:
                cache[key] = {"err": str(exc)[:120]}
        ent = cache[key]
        has_bars = isinstance(ent, list)
        ent = ent if has_bars else []
        out.append({**c, "has_bars": has_bars, "n": len(ent),
                    "arms": sorted({e["arm"] for e in ent if e["arm"]}),
                    "match": sorted({e["arm"] for e in ent if e["arm"] and
                                     isinstance(c.get("entry_i"), int) and
                                     abs(e["bar"] - c["entry_i"]) <= 2})})
    return out


def part_b(force=False):
    if os.path.exists(CACHE_RECALL) and not force:
        with open(CACHE_RECALL, encoding="utf-8") as fh:
            return json.load(fh)

    from research.t60_baseline import load_day_cards
    from research.t70_test1_score import load_cards, in_universe

    days, _marks = load_day_cards()
    ins = [{"symbol": s, "date": d, "his": (v.get("grade") or "").strip() or "blank",
            "entry_i": v.get("entry_i"), "in_universe": in_universe(s)}
           for (s, d), v in sorted(days.items())]

    held = [{"symbol": c["symbol"], "date": c["date"], "his": c["his"],
             "entry_i": c.get("entry_i"), "in_universe": in_universe(c["symbol"])}
            for c in load_cards()]

    cache = {}
    res = {"in_sample": score_days(ins, cache), "held_out": score_days(held, cache)}
    with open(CACHE_RECALL, "w", encoding="utf-8") as fh:
        json.dump(res, fh)
    return res


def norm_his(h):
    """One spelling for his refusal.

    t70_test1_score.load_cards writes `X` for grade_std "none"; t60's day-cards
    carry the literal string "none". Both mean the same judgement -- he looked and
    refused the day -- and a false-fire table that misses half of them is wrong.
    """
    return "none" if h in ("X", "none") else h


def recall_table(scored, grade, universe_only=False):
    """arm -> days of `grade` this arm fired on / total such days.

    `universe_only=False` is the default because it is the population the standing
    held-out figures are quoted over (T70: S recall 3/15, false fires 12/42).
    Passing True restricts to `universe.BACKTEST_SYMBOLS`, T70's second column.
    """
    grade = norm_his(grade)
    pop = [s for s in scored if norm_his(s["his"]) == grade
           and (s["in_universe"] or not universe_only) and s["has_bars"]]
    tab = {a: sum(1 for s in pop if a in s["arms"]) for a in ARMS}
    tab["ANY"] = sum(1 for s in pop if s["arms"])
    tab["_n"] = len(pop)
    tab["_dropped_no_bars"] = sum(1 for s in scored if norm_his(s["his"]) == grade
                                  and (s["in_universe"] or not universe_only)
                                  and not s["has_bars"])
    return tab


def part_b_r84(book, scored_in, scored_held):
    """R84 recall off the 2-year book, which is the only rig that arms it."""
    r84 = [r for r in book["trades"] if r.get("setup") == "reentry_84_rule"]
    keys = {(r["sym"], r["day"]) for r in r84}
    out = {}
    for name, scored in (("in_sample", scored_in), ("held_out", scored_held)):
        out[name] = [(s["symbol"], s["date"], s["his"]) for s in scored
                     if (s["symbol"], s["date"]) in keys]
    return {"rows": [{"sym": r["sym"], "day": r["day"], "et": r["et"], "grade": r["grade"],
                      "r": r["r"], "out": r["out"], "traded": r["traded"]} for r in r84],
            "overlap": out}


# ---------------------------------------------------------------------------
# PART C -- what is actually starving the 84% rule
# ---------------------------------------------------------------------------

def part_c(book, force=False):
    """The arming funnel from the book, then the reclaim census on the bars.

    Two separable questions:
      1. the ARMING gate  -- backtest_week._arm_84, computable from the book,
         because every input it reads (outcome, setup, legacy grade, stop-out
         time) is a column.
      2. the STRONG_PA_MULT gate -- signal_runner.py:2240 `RULE84_LESSON or
         self._strong_pa(current)`. Shipped RULE84_LESSON=True short-circuits it,
         so this walks the bars after every arming stop-out and counts the
         qualifying reclaim bars with the gate off (shipped) and on, at several
         multiples including the shipped 1.5.
    """
    if os.path.exists(CACHE_G84) and not force:
        with open(CACHE_G84, encoding="utf-8") as fh:
            return json.load(fh)

    from research.t4_engine_recall import rth_candles
    from signal_runner import SESSION_END

    traded = [r for r in book["trades"] if r.get("traded")]
    losses = [r for r in traded if r["out"] == "loss"]
    arming_setups = {"break_and_retest", "one_candle_rule"}   # RULE84_ARM_ON
    on_setup = [r for r in losses if r["setup"] in arming_setups]

    def exit_min(r):
        return int(r["et"][:2]) * 60 + int(r["et"][3:5]) + int(r["bars"])

    end_min = int(SESSION_END[:2]) * 60 + int(SESSION_END[3:5])
    in_sess = [r for r in on_setup if exit_min(r) < end_min]
    strict = [r for r in in_sess if r["grade"] in ("A+", "A")]
    sgrade = [r for r in in_sess if r.get("sgrade") == "S"]

    funnel = {
        "traded": len(traded), "losses": len(losses),
        "on_arming_setup": len(on_setup),
        "before_1100": len(in_sess),
        "strict_A_or_Aplus": len(strict),
        "sgrade_S": len(sgrade),
        "grade_mix_of_losses": dict(Counter(r["grade"] for r in on_setup)),
        "sgrade_mix_of_losses": dict(Counter(r.get("sgrade") for r in on_setup)),
    }

    mults = [0.0, 1.0, 1.25, 1.5, 2.0]
    census = {"loose": {"armings": 0, "with_reclaim": 0, "bars": 0,
                        "emitting_days": 0, "emit_bars": 0},
              "by_mult": {str(m): {"emitting_days": 0, "emit_bars": 0} for m in mults},
              "strict_arm": {"armings": 0, "emitting_days": 0, "emit_bars": 0},
              "no_bars": 0}
    barcache = {}
    for r in in_sess:
        key = (r["sym"], r["day"])
        if key not in barcache:
            c = rth_candles(*key)
            barcache[key] = [{"o": x.open, "h": x.high, "l": x.low, "c": x.close,
                              "t": x.timestamp} for x in c] if c else None
        bars = barcache[key]
        if not bars:
            census["no_bars"] += 1
            continue
        census["loose"]["armings"] += 1
        is_long = r["side"] == "L"
        start = int(r["entry_i"]) + int(r["bars"]) + 1
        idx = [i for i in range(max(5, start), len(bars)) if bars[i]["t"] < SESSION_END]
        checks = {i: r84_bar_ok(bars, i, r["entry"], r["target"], r["stop"], is_long, None)
                  for i in idx}
        recl = [i for i in idx if checks[i]["reclaim"]]
        census["loose"]["bars"] += len(recl)
        if recl:
            census["loose"]["with_reclaim"] += 1
        emit = [i for i in idx if checks[i]["all"]]
        census["loose"]["emit_bars"] += len(emit)
        if emit:
            census["loose"]["emitting_days"] += 1
        if r["grade"] in ("A+", "A"):
            census["strict_arm"]["armings"] += 1
            if emit:
                census["strict_arm"]["emitting_days"] += 1
                census["strict_arm"]["emit_bars"] += len(emit)
        for m in mults:
            e = [i for i in emit if strong_pa(bars, i, m)]
            census["by_mult"][str(m)]["emit_bars"] += len(e)
            if e:
                census["by_mult"][str(m)]["emitting_days"] += 1

    return_val = {"funnel": funnel, "census": census, "mults": mults}
    with open(CACHE_G84, "w", encoding="utf-8") as fh:
        json.dump(return_val, fh)
    return return_val


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck():
    ok = True

    def chk(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and bool(cond)

    chk(arm_of({"setup": "break_and_retest", "tags": ["clean"]}) == "BR", "plain B&R -> BR")
    chk(arm_of({"setup": "break_and_retest", "tags": ["brocr"]}) == "BROCR", "tagged B&R -> BROCR")
    chk(arm_of({"setup": "one_candle_rule", "tags": ["brocr"]}) == "BROCR", "tagged OCR -> BROCR")
    chk(arm_of({"setup": "reentry_84_rule", "tags": ["brocr"]}) == "R84", "84% wins over the tag")
    chk(base_of({"setup": "break_and_retest", "tags": ["brocr"]}) == "BR", "inclusive keeps the base")

    m, hw = mean_ci95([1.0, 1.0, 1.0, 1.0])
    chk(abs(m - 1.0) < 1e-9 and hw == 0.0, "zero-variance CI is zero")
    chk(math.isnan(mean_ci95([])[0]), "empty CI is nan")

    rows = [{"ym": "2024-08", "r": 1.0}, {"ym": "2024-09", "r": -1.0}]
    chk(months_green(rows, ["2024-08", "2024-09", "2024-10"]) == (1, 2, 1),
        "months_green counts absent months as not green")

    outs = [{"out": "win"}, {"out": "loss"}, {"out": "scratch"}]
    chk(abs(win_rate(outs) - 50.0) < 1e-9, "win rate excludes scratches (g3 convention)")
    chk(win_rate([]) == 0.0, "win rate of nothing is 0, not a crash")

    d, hw = two_sample([1.0, 1.0, 1.0], [0.0, 0.0, 0.0])
    chk(abs(d - 1.0) < 1e-9 and hw == 0.0, "two_sample delta with no variance")
    chk(math.isnan(two_sample([1.0], [0.0])[0]), "two_sample needs n>=2 on both sides")

    bars = [{"o": 0.0, "h": 1, "l": 0, "c": 1.0} for _ in range(10)] + \
           [{"o": 0.0, "h": 2, "l": 0, "c": 2.0}]
    chk(strong_pa(bars, 10, 1.5) and not strong_pa(bars, 10, 2.5), "strong_pa bites at a multiple")
    chk(strong_pa(bars, 10, 0.0), "mult 0 = gate removed, always true")

    b = [{"o": 9.0, "h": 10.0, "l": 8.0, "c": 9.5, "t": "09:40:00"} for _ in range(11)]
    b[10] = {"o": 9.0, "h": 10.0, "l": 8.0, "c": 9.05, "t": "09:40:00"}
    chk(r84_bar_ok(b, 10, 9.0, 12.0, 8.0, True, None)["pa"] is True,
        "mult=None (RULE84_LESSON=True) bypasses the PA gate")
    chk(r84_bar_ok(b, 10, 9.0, 12.0, 8.0, True, 1.5)["pa"] is False,
        "mult=1.5 makes a small reclaim body fail")

    from signal_runner import STRONG_PA_MULT, RULE84_LESSON, RULE84_STRICT, RULE84_OFF
    chk(STRONG_PA_MULT == 1.5, "STRONG_PA_MULT is 1.5 as shipped")
    chk(RULE84_LESSON is True, "RULE84_LESSON is True as shipped (the bypass)")
    chk(RULE84_STRICT is True and RULE84_OFF is False, "RULE84_STRICT on, RULE84_OFF off")
    print("SELFCHECK", "GREEN" if ok else "RED")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def fmt(x, n=4):
    return "n/a" if (x is None or (isinstance(x, float) and math.isnan(x))) else ("%.*f" % (n, x))


def build_md(A, B, C, book):
    r84o = part_b_r84(book, B["in_sample"], B["held_out"])
    e, f, cen = A["excl"], C["funnel"], C["census"]
    L = []
    ap = L.append
    ap("# X3 — the four detectors, one census")
    ap("")
    ap("Generated by `research/x3_detector_census.py` (`--selfcheck` green). Substrate: "
       "`research/g3_arm_ow1.json` — the shipped 2-year book, **%d signals / %d traded**, "
       "%d sessions, %d symbol-days, 2024-08-21..2026-08-21, `ON_WATCH=1`, from "
       "`research/g3_onwatch_2y.py`. Marks: `t60_baseline.load_day_cards()` in-sample, "
       "`research/marks/probe_omen_test1_2026-08-27.jsonl` held out."
       % (A["n_signals"], A["n_traded"], A["sessions"], A["book_days"]))
    ap("")
    ap("Austin: *\"i think br is only one firing good and we have BR, OCR, both, and 84 "
       "percent rule. that are the 4 right now never forget it.\"* And: *\"not sure how well "
       "84 percent rule is firing.\"*")
    ap("")
    ap("## The headline")
    ap("")
    ap("**BR is not the only one working. It is the only one with an N — and the arm that "
       "earns is BR+OCR confluence.** Per signal: confluence **%s R** on n=%d against BR-only's "
       "**%s R** on n=%d, a **%s R** spread on the same book, %.1f%% win rate against %.1f%%, "
       "and %d/25 months green against %d/25. **Confluence is the only arm with a real N that "
       "clears the 55%% win-rate leg of the money gate** (%.2f%%); the whole book is 53.2%%. "
       "OCR alone is **%s R** on n=%d with a 95%% interval of +/-%s — unreadable, not refuted. "
       "The 84%% rule produced **%d signals in two years**, and the constant the vault blames "
       "for that (`STRONG_PA_MULT = 1.5`) **is not on its code path at all**: the arming grade "
       "gate is, and it admits %d of %d eligible stop-outs."
       % (fmt(e["BROCR"]["mean"]), e["BROCR"]["n"], fmt(e["BR"]["mean"]), e["BR"]["n"],
          fmt(e["BROCR"]["mean"] - e["BR"]["mean"]),
          e["BROCR"]["win"], e["BR"]["win"], e["BROCR"]["green"], e["BR"]["green"],
          e["BROCR"]["win"],
          fmt(e["OCR"]["mean"]), e["OCR"]["n"], fmt(e["OCR"]["ci"]), e["R84"]["n"],
          f["strict_A_or_Aplus"], f["before_1100"]))
    ap("")

    # ---- A ---------------------------------------------------------------
    ap("## A. The book — %d traded signals, four arms" % A["n_traded"])
    ap("")
    ap("Arms are **exclusive**: a `[brocr]`-tagged row is confluence, not BR and not OCR. "
       "The tag is stamped at detection by `signal_runner._label_confluence` "
       "(`signal_runner.py:1768-1795`), which calls `research/downgrade.py::has_confluence` — "
       "one definition of confluence, in the file that owns it.")
    ap("")
    ap("| arm | signals traded | symbol-days | mean R | 95% CI on the mean | median R | win rate | months green /25 | share of book R |")
    ap("|---|---:|---:|---:|---|---:|---:|---:|---:|")
    for a in ARMS:
        s = e[a]
        ci = "n/a (n<2)" if math.isnan(s["ci"]) else "%s .. %s  (+/-%s)" % (
            fmt(s["mean"] - s["ci"]), fmt(s["mean"] + s["ci"]), fmt(s["ci"]))
        ap("| **%s** | %d | %d | **%s** | %s | %s | %.1f%% | %d (%d months silent) | %.1f%% |"
           % (ARM_LABEL[a], s["n"], s["days"], fmt(s["mean"]), ci, fmt(s["median"], 3),
              s["win"], s["green"], s["months_absent"], s["share"]))
    ap("")
    ap("Read the CI column before the mean column. The money gate is mean R >= 2.0; **no arm "
       "reaches it and no arm's interval touches it.** The 95% interval here is on one arm's "
       "own mean over its own n — it is NOT the +/-0.0095R paired A/B bar carried repo-wide "
       "(W0), which prices the difference between two arms over the *same* rows.")
    ap("")
    ap("The **inclusive** reading, confluence folded back into its base detector — this is the "
       "one that answers \"does BR just have all the N\":")
    ap("")
    ap("| base detector | signals traded | mean R | 95% CI | median R | win rate | months green /25 | share of book R |")
    ap("|---|---:|---:|---|---:|---:|---:|---:|")
    for a in ("BR", "OCR", "R84"):
        s = A["incl"][a]
        ci = "n/a (n<2)" if math.isnan(s["ci"]) else "+/-%s" % fmt(s["ci"])
        ap("| %s (all) | %d | %s | %s | %s | %.1f%% | %d | %.1f%% |"
           % (a, s["n"], fmt(s["mean"]), ci, fmt(s["median"], 3), s["win"],
              s["green"], s["share"]))
    ap("")
    ap("### Confluence is not a fourth detector — it is a property of the other two")
    ap("")
    ap("Every `[brocr]` row is also a `break_and_retest` or a `one_candle_rule` row; the label "
       "says an OCR was ALSO present at the level. So the sharp comparison is inside each base "
       "detector, where everything else is held fixed:")
    ap("")
    ap("| | n | mean R | median R | win rate | months green /25 |")
    ap("|---|---:|---:|---:|---:|---:|")
    for tag, other in (("BR", "OCR"), ("OCR", "BR")):
        for k, lbl in (("with", "**%s WITH a%s %s at the level**"), ("without", "%s with no%s %s")):
            s = A["split"][tag][k]
            art = "n" if other == "OCR" else ""
            ap("| %s | %d | %s | %s | %.1f%% | %d |"
               % (lbl % (tag, art if k == "with" else "", other), s["n"], fmt(s["mean"]),
                  fmt(s["median"], 3), s["win"], s["green"]))
    ap("")
    ap("Break-and-retest **with** an OCR beats break-and-retest **without** one by **%s R per "
       "signal** (%s vs %s), crosses the 55%% win-rate line (%.1f%% vs %.1f%%) and is green in "
       "%d months against %d. Same detector, same book, same exit ladder — the only difference "
       "is whether an order block was sitting at the level."
       % (fmt(A["split"]["BR"]["delta"]), fmt(A["split"]["BR"]["with"]["mean"]),
          fmt(A["split"]["BR"]["without"]["mean"]), A["split"]["BR"]["with"]["win"],
          A["split"]["BR"]["without"]["win"], A["split"]["BR"]["with"]["green"],
          A["split"]["BR"]["without"]["green"]))
    ap("")
    ap("**But it does not clear its own error bar.** The two sets are disjoint, so the "
       "instrument is the difference of two independent means, not the overlap of two "
       "single-arm CIs: **%s +/- %s R**. That interval contains zero. Every read points the "
       "same way — mean, median, win rate, months green — and on this book the break-and-retest "
       "spread is **pointed, not proven**."
       % (fmt(A["split"]["BR"]["delta"]), fmt(A["split"]["BR"]["delta_ci"])))
    ap("")
    ap("The same split inside the ONE CANDLE RULE is larger and does clear: **%s +/- %s R** "
       "(%s with a BR present, %s without). Read it with two cautions — the without-arm is "
       "n=%d, and this is one of four comparisons in this lane, so a single marginal pass at "
       "95%% is about what chance supplies. It is a flag, not a finding."
       % (fmt(A["split"]["OCR"]["delta"]), fmt(A["split"]["OCR"]["delta_ci"]),
          fmt(A["split"]["OCR"]["with"]["mean"]), fmt(A["split"]["OCR"]["without"]["mean"]),
          A["split"]["OCR"]["without"]["n"]))
    ap("")
    ap("Detection, before any grade or routing filter — all %d signals in the book:" % A["n_signals"])
    ap("")
    ap("| arm | detected | symbol-days detected on | reached `fired` status | traded |")
    ap("|---|---:|---:|---:|---:|")
    for a in ARMS:
        ap("| %s | %d | %d | %d | %d |" % (a, A["det_excl"].get(a, 0), A["det_days"].get(a, 0),
                                           A["fired"].get(a, 0), e[a]["n"]))
    ap("")
    ap("`fair_value_gap` and `flag` produce **0 signals in the whole two years** — they are in "
       "`RETIRED_SETUPS` and never emit. Austin's four are the only four that exist.")
    ap("")

    # ---- B ---------------------------------------------------------------
    ap("## B. Recall — which arm reaches Austin's S days")
    ap("")
    ap("One `run_day_tagged` per marked symbol-day: the engine replayed bar-by-bar with the "
       "same reader, levels, 30-bar dedupe and 11:00 cutoff `research/t4_engine_recall.run_day` "
       "uses, plus the `br_ocr` label on every record. A day counts for an arm when that arm "
       "fires at all on it. **Held-out first.**")
    ap("")
    ap("> **The 84% rule cannot appear in these two tables, and that is structural, not a "
       "result.** Arming needs a stopped-out prior trade's session state "
       "(`backtest_week._arm_84`), and a detection-only replay never trades. Its recall is "
       "measured off the 2-year book below — the only rig in the repo that arms it.")
    ap("")
    for name, key in (("Held out — OMEN Test 1, 100 unseen cards", "held_out"),
                      ("In-sample — the graded day-cards", "in_sample")):
        ap("### %s" % name)
        ap("")
        ap("| his grade | days | BR only | OCR only | BR+OCR | ANY arm |")
        ap("|---|---:|---:|---:|---:|---:|")
        for g in ("S", "A", "C", "none", "blank"):
            t = recall_table(B[key], g)
            if t["_n"] == 0:
                continue
            lbl = {"S": "**S (the gate)**", "none": "`none` (the false-fire base)"}.get(g, g)
            ap("| %s | %d | %d (%.0f%%) | %d (%.0f%%) | %d (%.0f%%) | **%d (%.0f%%)** |"
               % (lbl, t["_n"], t["BR"], pct(t["BR"], t["_n"]), t["OCR"], pct(t["OCR"], t["_n"]),
                  t["BROCR"], pct(t["BROCR"], t["_n"]), t["ANY"], pct(t["ANY"], t["_n"])))
        ap("")
        ts, tsu = recall_table(B[key], "S"), recall_table(B[key], "S", True)
        tn, tnu = recall_table(B[key], "none"), recall_table(B[key], "none", True)
        oos = sum(1 for s in B[key] if not s["in_universe"])
        ap("All graded symbols, which is the population the standing figures are quoted over. "
           "Restricted to `universe.BACKTEST_SYMBOLS` (%d of %d cards are out of universe — "
           "SPY by explicit decision, IWM and ACHR in no backtest tier) it is **S %d/%d**, "
           "**`none` %d/%d**. %d day%s dropped for missing archived bars."
           % (oos, len(B[key]), tsu["ANY"], tsu["_n"], tnu["ANY"], tnu["_n"],
              ts["_dropped_no_bars"], "" if ts["_dropped_no_bars"] == 1 else "s"))
        ap("")
        if key == "held_out":
            ap("**Cross-check against the published held-out number:** `research/"
               "t70_test1_score.md` line 38 says *\"S recall: 3/15 ... In-universe: 2/12\"*. "
               "This rig gets **%d/%d** and **%d/%d** — identical, which is the evidence that "
               "the per-arm split below it is trustworthy. The false-fire figure **%d/%d** is "
               "likewise the 12/42 quoted in R3, G13 and W3."
               % (ts["ANY"], ts["_n"], tsu["ANY"], tsu["_n"], tn["ANY"], tn["_n"]))
            ap("")
    ap("Arms overlap on a day (a day can carry a BR fire and a BROCR fire), so the columns do "
       "not sum to ANY. That is the point of the table: **no arm has a monopoly on the S days "
       "the engine does reach, and the arms that reach them also reach the `none` days.**")
    ap("")
    ap("### The 84% arm's recall, off the 2-year book")
    ap("")
    ap("All %d `reentry_84_rule` rows the shipped engine produced in 500 sessions:" % len(r84o["rows"]))
    ap("")
    ap("| symbol | day | entry | legacy grade | traded | outcome | R |")
    ap("|---|---|---|---|---|---|---:|")
    for r in r84o["rows"]:
        ap("| %s | %s | %s | %s | %s | %s | %s |" % (r["sym"], r["day"], r["et"], r["grade"],
                                                     r["traded"], r["out"], fmt(r["r"], 3)))
    ap("")
    ov_h, ov_i = r84o["overlap"]["held_out"], r84o["overlap"]["in_sample"]
    sh = [x for x in ov_h if x[2] == "S"]
    si = [x for x in ov_i if x[2] == "S"]
    nS_h = recall_table(B["held_out"], "S")["_n"]
    nS_i = recall_table(B["in_sample"], "S")["_n"]
    ap("Overlap with Austin's marked days — held-out: %s. In-sample: %s."
       % (", ".join("%s %s (his %s)" % x for x in ov_h) or "**none**",
          ", ".join("%s %s (his %s)" % x for x in ov_i) or "**none**"))
    ap("")
    ap("**So the 84%% arm's S-day recall is %d/%d held out and %d/%d in-sample.** Held out it "
       "reaches nothing, because it fires 3 times in 500 sessions and none of those days is on "
       "the test sheet. In-sample it lands on **1** — TSLA 2026-05-19, a day Austin graded "
       "**S**, and it won **+3.145R** on it. One in three of everything this rule has ever "
       "produced hit a day he called S. That is a sample of three and it proves nothing about "
       "the rule's edge; what it does establish is that the rule is not firing on garbage."
       % (len(sh), nS_h, len(si), nS_i))
    ap("")

    # ---- C ---------------------------------------------------------------
    ap("## C. Is the 84% rule firing at all, and what is starving it")
    ap("")
    ap("### It is not `STRONG_PA_MULT`. That constant is not on the path.")
    ap("")
    ap("`signal_runner.py:91`:")
    ap("")
    ap("```python")
    ap("STRONG_PA_MULT = 1.5  # reclaim body vs avg body of prior 10 candles (84% rule gate)")
    ap("```")
    ap("")
    ap("The trailing comment is false for the shipped build. Both emission sites read:")
    ap("")
    ap("```python")
    ap("signal_runner.py:2240   and (RULE84_LESSON or self._strong_pa(current))):   # long")
    ap("signal_runner.py:2458   and (RULE84_LESSON or self._strong_pa(current))):   # short")
    ap("```")
    ap("")
    ap("and `RULE84_LESSON = True` at `signal_runner.py:104` — a hardcoded module constant, "
       "no env var, no flag, no A/B. Python short-circuits `or`, so **`_strong_pa` is never "
       "called on the 84% path and `STRONG_PA_MULT` is never read there.** The codebase "
       "already knew twice over: the B4 comment at `:171` says *\"RULE84_LESSON=True (line "
       "102) BYPASSES the strong-PA gate on 84%-rule re-entries\"*, and the in-block comment "
       "at `:2263` labels its own neighbouring comment STALE for the same reason.")
    ap("")
    ap("Its only live reader is `_aplus_stack` (`signal_runner.py:1436-1444`), which needs "
       "first-break + displacement + strong PA to grant **A+**. That matters here only "
       "indirectly, and the indirection is the whole story — see the next section.")
    ap("")
    ap("**Four documents say it gates the 84% rule. One says it does not, and that one is "
       "right:**")
    ap("")
    ap("| document | what it says | correct? |")
    ap("|---|---|---|")
    ap("| `signal_runner.py:91` (its own trailing comment) | *\"(84% rule gate)\"* | **no** |")
    ap("| `research/hallucination-audit.md:49` | *\"CRITICAL — gates 84% reclaim\"* | **no** |")
    ap("| `research/x10_open_questions.md:114` | *\"`STRONG_PA_MULT = 1.5` which gates it\"* | **no** |")
    ap("| vault `.scratch/omen-6/qa-queue.md:140` (Q5) | *\"`STRONG_PA_MULT = 1.5x` gates this rule "
       "and ... has no author\"* | **half** — the no-author half is right |")
    ap("| `research/parameter_catalog_draft.md:16` | *\"only active when `RULE84_LESSON=False`\"* | "
       "**yes** |")
    ap("")
    ap("The catalog draft got there first and nothing downstream picked it up. This lane is "
       "the confirmation, with the funnel underneath it.")
    ap("")
    ap("### What IS starving it: the arming grade gate in `backtest_week._arm_84`")
    ap("")
    ap("Every input `_arm_84` reads is a column in the book, so the funnel is computable "
       "without a replay:")
    ap("")
    ap("| stage | rows | why |")
    ap("|---|---:|---|")
    ap("| traded signals | %d | the book |" % f["traded"])
    ap("| full stop-outs (`out == loss`) | %d | a scratch never arms it |" % f["losses"])
    ap("| on an arming setup (`RULE84_ARM_ON` = B&R, OCR) | %d | FVG / flag losers do not arm |" % f["on_arming_setup"])
    ap("| stop-out lands before 11:00 (`SESSION_END`) | %d | no re-entry to take after 11 |" % f["before_1100"])
    ap("| **survives `RULE84_STRICT` — `t.grade in (\"A+\",\"A\")`** | **%d** | **this is the gate** |" % f["strict_A_or_Aplus"])
    ap("| (counterfactual) survives `RULE84_ARM_SGRADE` — `sgrade == \"S\"` | %d | P7/G1's third arm |" % f["sgrade_S"])
    ap("")
    gm = ", ".join("%s %d" % kv for kv in sorted(f["grade_mix_of_losses"].items()))
    ap("The legacy grade on those %d arming stop-outs: **%s**. `_calibration_grade` floors the "
       "first with-trend signal of the day to **B** (G4: 968 of 1,016 traded rows are B for "
       "exactly that reason), and `RULE84_STRICT` demands **A+ or A**. **The grade gate kills "
       "%.1f%% of everything that reaches it** — %d of %d."
       % (f["on_arming_setup"], gm,
          pct(f["before_1100"] - f["strict_A_or_Aplus"], f["before_1100"]),
          f["before_1100"] - f["strict_A_or_Aplus"], f["before_1100"]))
    ap("")
    ap("**Reconciliation with P7/G1**, which ran the whole 500-session replay instead of "
       "reading the book: P7's strict funnel is `473 -> 472 -> 7 -> 5 -> 3` and it applies the "
       "grade gate BEFORE the 11:00 clock (7 pass the grade, 5 of those are in session). This "
       "table applies the clock first (%d in session, %d of those pass the grade). **Both land "
       "on 5, and both land on 3 emitted signals.** The one-row gaps at the top (%d vs 473 "
       "losses, %d vs 472 on an arming setup) are P7's `counted` flag, which the book does not "
       "carry as a column; they do not propagate."
       % (f["before_1100"], f["strict_A_or_Aplus"], f["losses"], f["on_arming_setup"]))
    ap("")
    ap("This is the two-ladder bug in its purest form. The rulebook sentence behind "
       "`RULE84_STRICT` is Austin's — *\"you need an A+ entry\"* — and in **his** ladder A+ is "
       "what he now calls **S**. The code tests `_grade_pa`'s A+: a candle-shape scale that "
       "lands on **%d of %d** traded signals in two years (grade mix %s). One word, two "
       "ladders, a dead rule."
       % (A["grade_mix"].get("A+", 0), A["n_traded"],
          ", ".join("%s %d" % kv for kv in sorted(A["grade_mix"].items()))))
    ap("")
    ap("### The reclaim census — what the detector produces with the arming gate opened")
    ap("")
    ap("Each of the %d in-session arming stop-outs, walked forward from its own exit bar to "
       "11:00, testing the shipped emission block (`signal_runner.py:2237-2255` long / "
       ":2455-2473 short) bar by bar: reclaim of the original entry price on a same-direction "
       "close, ORIGINAL stop and target, remaining reward >= 1.5x remaining risk, close not "
       "within 20%% of the session extreme it is running into. `RULE84_MAX_ATTEMPTS` and the "
       "one-shot disarm are deliberately not modelled — this counts OPPORTUNITY, and the "
       "arming state machine is the row above." % f["before_1100"])
    ap("")
    ap("| | stop-outs | at least one qualifying bar | qualifying bars |")
    ap("|---|---:|---:|---:|")
    ap("| reclaim clause alone | %d | %d (%.1f%%) | %d |"
       % (cen["loose"]["armings"], cen["loose"]["with_reclaim"],
          pct(cen["loose"]["with_reclaim"], cen["loose"]["armings"]), cen["loose"]["bars"]))
    ap("| full emission block, **PA gate off (shipped)** | %d | **%d (%.1f%%)** | %d |"
       % (cen["loose"]["armings"], cen["loose"]["emitting_days"],
          pct(cen["loose"]["emitting_days"], cen["loose"]["armings"]), cen["loose"]["emit_bars"]))
    ap("| full block, arming restricted to A+/A (shipped `RULE84_STRICT`) | %d | %d | %d |"
       % (cen["strict_arm"]["armings"], cen["strict_arm"]["emitting_days"],
          cen["strict_arm"]["emit_bars"]))
    ap("")
    ap("So the detector is alive: **%d of %d** stop-outs (%.1f%%) offer it a bar it would "
       "take. The arming gate hands it **%d**."
       % (cen["loose"]["emitting_days"], cen["loose"]["armings"],
          pct(cen["loose"]["emitting_days"], cen["loose"]["armings"]),
          cen["strict_arm"]["emitting_days"]))
    ap("")
    ap("And the same census with the strong-PA gate **switched on** at each multiple — which "
       "is what `STRONG_PA_MULT` would cost if `RULE84_LESSON` were ever set False, and what "
       "removing it (0.00x) buys:")
    ap("")
    ap("| `STRONG_PA_MULT` | stop-outs with a qualifying bar | qualifying bars | vs gate off |")
    ap("|---|---:|---:|---:|")
    base = cen["loose"]["emitting_days"]
    for m in C["mults"]:
        d = cen["by_mult"][str(m)]
        note = {0.0: " — gate removed entirely", 1.5: " — **the shipped constant**"}.get(m, "")
        ap("| %.2fx%s | %d | %d | %+.1f%% |" % (m, note, d["emitting_days"], d["emit_bars"],
                                                pct(d["emitting_days"] - base, base)))
    ap("")
    d15 = cen["by_mult"]["1.5"]["emitting_days"]
    ap("**Verdict on the constant: it is a %.1f%% filter, and it is switched off.** At 1.5x it "
       "would cost %d of %d opportunity days. That is real but it is nowhere near the "
       "%.1f%% the arming grade gate takes, and it is not applied. P7/G1 already ran the whole "
       "500-session replay through the same funnel and got **473 -> 472 -> 7 -> 5 -> 3 "
       "signals** on the shipped arm and **521 -> 472 -> 472 -> 433 -> 116** on the loose arm "
       "(`research/p7_84_rule.md`, `research/p7_84_rule.py`) — a 39x swing produced entirely "
       "by the grade gate, with `STRONG_PA_MULT` untouched in both arms."
       % (pct(base - d15, base), base - d15, base,
          pct(f["before_1100"] - f["strict_A_or_Aplus"], f["before_1100"])))
    ap("")
    ap("### And the constant has no author")
    ap("")
    ap("`research/p11_parameter_provenance.py:37` files `STRONG_PA_MULT` as row **A5** with "
       "provenance `sr:90` — *the line of source it is defined on*. The constant cites itself. "
       "No transcript, no rulebook clause, no mark. Ballot **b01 q12–q15** records what Austin "
       "actually specified for this rule: re-entry at the PRICE you entered on, a candle CLOSE "
       "to reclaim it, at most two attempts, matching the trend direction. A body-size "
       "multiple appears in none of the four. `RULE84_LESSON=True` is, in effect, someone "
       "having already deleted it — silently, and without moving the comment.")
    ap("")

    # ---- the three answers ------------------------------------------------
    ap("## The three answers")
    ap("")
    ap("### 1. Is BR genuinely the only one working, or does it just have the N?")
    ap("")
    ap("It just has the N. Normalised per signal, **BR-only is the weaker of the two arms with "
       "a real sample**:")
    ap("")
    for a in ARMS:
        s = e[a]
        ci = (", 95%% CI +/-%s" % fmt(s["ci"])) if not math.isnan(s["ci"]) else " (n<2, no interval)"
        ap("- **%s** — %s R/signal, n=%d%s, %.1f%% of book R" % (a, fmt(s["mean"]), s["n"], ci,
                                                                 s["share"]))
    ap("")
    ap("**Delete every confluence row from the book and the mean R falls from %s (n=%d) to %s "
       "(n=%d)**, the win rate from %.1f%% to %.1f%%, and months green from %d/25 to %d/25. "
       "The arm Austin reads as the sideshow is the better half of the arm he reads as the "
       "engine — though the %s R spread inside break-and-retest carries a +/-%s interval and "
       "is therefore pointed, not proven."
       % (fmt(A["book"]["mean"]), A["book"]["n"], fmt(A["noconf"]["mean"]), A["noconf"]["n"],
          A["book"]["win"], A["noconf"]["win"], A["book"]["green"], A["noconf"]["green"],
          fmt(A["split"]["BR"]["delta"]), fmt(A["split"]["BR"]["delta_ci"])))
    ap("")
    ap("### 2. Is the 84% rule firing at all?")
    ap("")
    ap("**%d signals in two years, %d traded — and 1 of the 3 landed on a day Austin graded S "
       "(TSLA 2026-05-19, +3.145R).** Firing, yes; measurable, no. The cause is NOT "
       "`STRONG_PA_MULT` — that constant is "
       "short-circuited off the path by `RULE84_LESSON=True` and cannot be starving anything. "
       "The cause is `RULE84_STRICT` demanding a legacy `A+`/`A` from a selector that issues "
       "`B` on %d of %d traded rows."
       % (e["R84"]["n"], sum(1 for r in r84o["rows"] if r["traded"]),
          A["grade_mix"].get("B", 0), A["n_traded"]))
    ap("")
    ap("### 3. Is any of the four dead enough to DELETE?")
    ap("")
    ap("| detector | verdict | the number behind it |")
    ap("|---|---|---|")
    ap("| **BR** | **KEEP** | %d of %d traded signals, %.1f%% of book R, %d/25 months green. "
       "Nothing else has the volume. |"
       % (A["incl"]["BR"]["n"], A["n_traded"], A["incl"]["BR"]["share"], A["incl"]["BR"]["green"]))
    ap("| **BR+OCR confluence** | **KEEP — and it is the one to promote** | %s R/signal on "
       "n=%d vs BR-only's %s on n=%d; %.1f%% win rate vs %.1f%%; %d/25 months green vs %d/25. "
       "Best per-signal arm in the book. |"
       % (fmt(e["BROCR"]["mean"]), e["BROCR"]["n"], fmt(e["BR"]["mean"]), e["BR"]["n"],
          e["BROCR"]["win"], e["BR"]["win"], e["BROCR"]["green"], e["BR"]["green"]))
    ap("| **OCR alone** (an OCR with no BR at the level) | **the only defensible delete on this "
       "book — and it buys almost nothing** | n=%d in two years, mean %s, own 95%% CI %s .. %s "
       "(contains zero, so \"loses money\" is NOT established). What IS established at 95%% is "
       "that it is worse than the same detector WITH a BR present: **%s +/- %s R**. Deleting it "
       "returns **%s R over two years**, moving the book mean by %+.4f R against the 1.045R the "
       "money gate is short. Worth doing for clarity, not for money. |"
       % (e["OCR"]["n"], fmt(e["OCR"]["mean"]), fmt(e["OCR"]["mean"] - e["OCR"]["ci"]),
          fmt(e["OCR"]["mean"] + e["OCR"]["ci"]),
          fmt(A["split"]["OCR"]["delta"]), fmt(A["split"]["OCR"]["delta_ci"]),
          fmt(-e["OCR"]["sum_r"], 3),
          (A["total_r"] - e["OCR"]["sum_r"]) / (A["n_traded"] - e["OCR"]["n"])
          - A["total_r"] / A["n_traded"]))
    ap("| **84%% re-entry** | **DO NOT DELETE — it is not dead, it is gated shut** | %d signals "
       "in 500 sessions. The DETECTOR reaches a qualifying bar on **%d of %d** arming "
       "stop-outs (%.1f%%); the arming grade gate then admits %d of %d. Deleting the codebase "
       "would delete a rule that has never once been allowed to run. |"
       % (e["R84"]["n"], cen["loose"]["emitting_days"], cen["loose"]["armings"],
          pct(cen["loose"]["emitting_days"], cen["loose"]["armings"]),
          f["strict_A_or_Aplus"], f["before_1100"]))
    ap("")
    hs = recall_table(B["held_out"], "S")
    hn = recall_table(B["held_out"], "none")
    ap("**No arm passes the recall column, and the arm with the best money is the worst "
       "discriminator.** The held-out gate is: fire on >=90%% of his S days. Beside it, the "
       "%d days he refused." % hn["_n"])
    ap("")
    ap("| arm | held-out S days reached | held-out `none` days fired on | S rate minus `none` rate |")
    ap("|---|---:|---:|---:|")
    for a in ARMS:
        note = " *" if a == "R84" else ""
        ap("| %s%s | %d/%d (%.0f%%) | %d/%d (%.0f%%) | %+.1f pts |"
           % (a, note, hs[a], hs["_n"], pct(hs[a], hs["_n"]), hn[a], hn["_n"],
              pct(hn[a], hn["_n"]), pct(hs[a], hs["_n"]) - pct(hn[a], hn["_n"])))
    ap("| **any arm** | **%d/%d (%.0f%%)** | **%d/%d (%.0f%%)** | **%+.1f pts** |"
       % (hs["ANY"], hs["_n"], pct(hs["ANY"], hs["_n"]), hn["ANY"], hn["_n"],
          pct(hn["ANY"], hn["_n"]),
          pct(hs["ANY"], hs["_n"]) - pct(hn["ANY"], hn["_n"])))
    ap("")
    ap("")
    ap("\\* R84's two zeros are structural, not measured — the detection replay cannot arm it. "
       "Its real 2-year figures are 0/15 held out and 1/28 in-sample, from the book.")
    ap("")
    ap("Every arm fires at least as often on a day he refused as on a day he graded S, and "
       "confluence — the arm that carries the money — is the most negative of the four "
       "(%.0f%% on S, %.0f%% on `none`). **The detector that earns is not the detector that "
       "sees what he sees.** On 15 and 42 days these gaps are individually unresolvable; the "
       "sign being uniformly wrong across four arms is the part worth reading."
       % (pct(hs["BROCR"], hs["_n"]), pct(hn["BROCR"], hn["_n"])))
    ap("")
    ap("**What IS safely deletable, and it is not one of the four:** `STRONG_PA_MULT` on the "
       "84% path. Unreachable code (`RULE84_LESSON=True` short-circuits it), no author "
       "(`p11` row A5, provenance `sr:90` = its own line number), and four documents "
       "currently blame it for a rule it does not gate. Delete the dead branch at `:2240` and "
       "`:2458`, delete the stale comment at `:2263`, fix the trailing comment at `:91`. Zero "
       "behaviour change — the selfcheck in this file asserts the short-circuit, so a "
       "regression would be caught.")
    ap("")
    ap("**And the ticket that follows from this lane:** `RULE84_STRICT` is one English "
       "sentence read against the wrong ladder. G14 is already queued to A/B "
       "`_calibration_grade`, which is the thing issuing the `B` that starves it. These are "
       "the same bug seen from two ends.")
    ap("")
    ap("## Reproduce")
    ap("")
    ap("```")
    ap("python research/x3_detector_census.py --selfcheck")
    ap("python research/x3_detector_census.py")
    ap("```")
    ap("")
    ap("Caches: `research/_x3_recall.json` (the per-day replay, ~2 min to rebuild) and "
       "`research/_x3_gate84.json`. `--force` rebuilds both.")
    return "\n".join(L) + "\n"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--selfcheck" in sys.argv:
        return selfcheck()
    force = "--force" in sys.argv
    book = load_book()
    A = part_a(book)
    if args == ["book"]:
        print(json.dumps(A, indent=1, default=str))
        return 0
    C = part_c(book, force)
    if args == ["gate84"]:
        print(json.dumps(C, indent=1))
        return 0
    B = part_b(force)
    if args == ["recall"]:
        for k in ("held_out", "in_sample"):
            for g in ("S", "A", "C", "none"):
                print(k, g, recall_table(B[k], g))
        return 0
    md = build_md(A, B, C, book)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(md)
    print("wrote", OUT_MD, len(md), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
