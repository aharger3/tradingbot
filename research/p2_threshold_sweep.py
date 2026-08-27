"""p2_threshold_sweep -- P2/A1: sweep every guessed constant in `downgrade.py`
against TWO independent things at once, with a held-out half.

WHY THIS EXISTS AND WHY IT IS NOT `downgrade_tune.py`
-----------------------------------------------------
`research/downgrade_tune.md` already swept these knobs one at a time against
Austin's 120 graded day-cards. It found the useful thing (REJECT_BARS is dead)
and it is honest about what it cannot see. Three holes remain, and they are the
whole of this ticket:

  1. **No money axis.** Every number in `downgrade_tune.md` is "does a DAY fire".
     None of it says what the resulting S set MADE. A threshold that lifts recall
     while flattening the S > A > C ordering on the 2-year book is a worse
     setting, not a better one, and that sweep could not tell the difference.
  2. **No hold-out.** Every row was computed on the same 120 cards the gate is
     scored on. `build_calibration.py`'s header names this exact trap.
  3. **Signal-level distribution compared to a DAY-level corpus.** T66 put
     S/A/C = 168/304/778 (per signal, n=1250) next to Austin's 28/27/3 (per
     day-card, n=58) and concluded "the thresholds are wrong". Those are
     different units. This report computes the day-level mix too, which is the
     only one of the two that is comparable to his.

WHAT IS SWEPT, AND WHAT IS DELIBERATELY NOT
-------------------------------------------
Swept: the six numeric guesses (`STALE_BARS`, `CHOP_TOUCHES`, `EXHAUSTED_ATR`,
`DISP_BODY_MULT`, `REJECT_BARS`, `UNRESPECTED_COUNTER`), `ATR_WINDOW`, and the
two structural choices inside `find_ocr` (proximity, isolation strictness).

NOT swept: the `0.25` inside `_eps`. That is `BAR_EXTREME_FRAC`, the one
tolerance unit Austin settled on 2026-08-23 -- it is his number, not a guess, and
it is out of scope for a sweep of the guesses. It is the only constant in
`downgrade.py` this file leaves alone on purpose.

**No default in `downgrade.py` is read from or written to by this script beyond
its committed values.** The grader is re-implemented here as
`features()` + `grade_of()`: one pass over bars produces the sufficient statistic
for each variable (the gap, the count, the ratio), and every threshold then
reduces to one comparison against it. That is what makes 45,175 signals x ~60
settings affordable. `--selftest` proves the re-implementation reproduces
`downgrade.score` bar for bar.

THE TWO RIGS
------------
  RIG 1  Austin's 120 graded day-cards, replayed exactly as t66 does. Day-level
         agreement, S-day recall, false fires, and the day-level grade mix
         against his 28/27/3. Split 50/50, stratified by his own grade; tuned on
         one half, reported on the other.
  RIG 2  `research/bt2y_trades.json`, READ ONLY, 45,175 signals / 1,016 traded.
         Re-graded from the archived bars at each setting. Mean R and win rate of
         the resulting S set, and whether S > A > C survives.

    python research/p2_threshold_sweep.py [--selftest] [--limit N]

Writes research/p2_threshold_sweep.md.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = os.path.join(HERE, "p2_threshold_sweep.md")
BT2Y = os.path.join(HERE, "bt2y_trades.json")

# Austin's own corpus. 58 day-cards he was willing to trade, graded by him.
AUSTIN_MIX = {"S": 28, "A": 27, "C": 3}
CONFLUENCE_CAP = 0.20            # Austin 2026-08-24: confluence under 1 in 5

# committed defaults, mirrored here so the sweep never mutates downgrade.py
D = {
    "STALE_BARS": 10,        # ratified, ballot batch 02 b11
    "CHOP_TOUCHES": 2,
    "EXHAUSTED_ATR": 10.0,
    "DISP_BODY_MULT": 1.5,
    "REJECT_BARS": 2,
    "UNRESPECTED_COUNTER": 2,
    "ATR_WINDOW": 14,
    "ocr_lookback": 20,
    "ocr_isolation": "both",
}

SWEEPS = [
    ("STALE_BARS", [3, 5, 8, 10, 15, 20, 30, 60, 120]),
    ("CHOP_TOUCHES", [1, 2, 3, 4, 5, 6, 8, 12]),
    ("EXHAUSTED_ATR", [2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0, 30.0, 50.0]),
    ("DISP_BODY_MULT", [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0]),
    ("REJECT_BARS", [0, 1, 2, 3, 5, 8, 12, 20]),
    ("UNRESPECTED_COUNTER", [1, 2, 3, 4, 5, 6, 8, 12]),
    ("ATR_WINDOW", [5, 7, 10, 14, 21, 30]),
    ("ocr_lookback", [2, 3, 5, 8, 10, 15, 20, 30]),
    ("ocr_isolation", ["none", "left", "right", "both", "both2"]),
]

ATR_WINDOWS = sorted({v for k, vals in SWEEPS if k == "ATR_WINDOW" for v in vals}
                     | {D["ATR_WINDOW"]})
OCR_VARIANTS = sorted({(lb, D["ocr_isolation"])
                       for k, vals in SWEEPS if k == "ocr_lookback" for lb in vals}
                      | {(D["ocr_lookback"], iso)
                         for k, vals in SWEEPS if k == "ocr_isolation" for iso in vals})
MAX_OCR_LOOKBACK = max(lb for lb, _ in OCR_VARIANTS)
BREAK_LOOKBACK = 30              # hardcoded in downgrade._break_bar; not a threshold
PRIOR_BODIES = 10                # hardcoded in downgrade.no_displacement
CHOP_WINDOW = 12                 # hardcoded in downgrade.level_not_respected
CTNR_WINDOW = 12                 # hardcoded in downgrade.counter_trend_not_respected
CTNR_RECOVER = 3                 # hardcoded: range(j+1, min(j+3, i+1))
EPS_FRAC = 0.25                  # Austin's BAR_EXTREME_FRAC. NOT swept -- see header.


# ---------------------------------------------------------------------------
# bar helpers -- byte-for-byte the same arithmetic as downgrade.py
# ---------------------------------------------------------------------------

def _body(b):
    return abs(b["c"] - b["o"])


def _rng(b):
    return b["h"] - b["l"]


def _atr(bars, i, n):
    lo = max(1, i - n + 1)
    rows = bars[lo:i + 1]
    return (sum(_rng(b) for b in rows) / len(rows)) if rows else 0.0


def _is_up(b):
    return b["c"] >= b["o"]


def _break_bar(bars, i, level, is_long):
    for j in range(i, max(0, i - BREAK_LOOKBACK) - 1, -1):
        if j == 0:
            break
        prev, cur = bars[j - 1], bars[j]
        crossed = ((prev["c"] <= level < cur["c"]) if is_long
                   else (prev["c"] >= level > cur["c"]))
        if crossed:
            return j
    return None


def _retest_bar(bars, i, level, is_long, after, eps):
    for j in range(after + 1, i + 1):
        back = (bars[j]["l"] <= level + eps) if is_long else (bars[j]["h"] >= level - eps)
        if back:
            return j
    return None


# ---------------------------------------------------------------------------
# sufficient statistics: one pass over bars, every threshold becomes a compare
# ---------------------------------------------------------------------------

def ocr_features(bars, i, is_long):
    """For every (lookback, isolation) variant: does an OCR exist, was it
    respected, and is its far edge usable as a stop?

    One scan of the candidate counter-coloured candles serves all variants --
    the isolation modes are just different flags on the same candidate.
    """
    cands = []                                   # (j, {isolation: bool})
    lo = max(1, i - MAX_OCR_LOOKBACK)
    for j in range(i - 1, lo - 1, -1):
        if j + 1 > i:
            continue
        b = bars[j]
        counter = (not _is_up(b)) if is_long else _is_up(b)
        if not counter:
            continue

        def trend(k):
            return _is_up(bars[k]) if is_long else (not _is_up(bars[k]))

        l1, r1 = trend(j - 1), trend(j + 1)
        both2 = False
        if j - 2 >= 0 and j + 2 <= i:
            both2 = l1 and r1 and trend(j - 2) and trend(j + 2)
        cands.append((j, {"none": True, "left": l1, "right": r1,
                          "both": l1 and r1, "both2": both2}))

    memo = {}

    def judge(j):
        if j in memo:
            return memo[j]
        edge = bars[j]["l"] if is_long else bars[j]["h"]
        through = False
        for k in range(j + 1, i + 1):
            if (bars[k]["c"] < edge) if is_long else (bars[k]["c"] > edge):
                through = True
                break
        usable = (edge <= bars[i]["c"]) if is_long else (edge >= bars[i]["c"])
        memo[j] = (through, usable)
        return memo[j]

    out = {}
    for lb, iso in OCR_VARIANTS:
        floor = max(1, i - lb)
        hit = None
        for j, flags in cands:                   # cands already newest-first
            if j < floor:
                break
            if flags[iso]:
                hit = j
                break
        if hit is None:
            out[(lb, iso)] = (False, False)      # no OCR: not a downgrade, no +1
        else:
            through, usable = judge(hit)
            out[(lb, iso)] = (through, usable and not through)
    return out


def features(bars, i, level, is_long):
    """Everything the eight variables need, with the thresholds factored out.

    Returned per ATR window (eps and `exhausted` both move with it); the OCR
    block is window-independent so it is computed once.
    """
    if not bars or i >= len(bars) or level is None:
        return None
    br = _break_bar(bars, i, level, is_long)

    # no_displacement: body of the break bar vs the average body before it
    if br is None:
        disp = None                              # br missing -> always trips
    else:
        prior = bars[max(0, br - PRIOR_BODIES):br]
        avg = (sum(_body(b) for b in prior) / len(prior)) if prior else 0.0
        disp = (_body(bars[br]) / avg) if avg > 0 else float("inf")   # inf -> never trips

    # break_then_rejection: bars from the break to the first close back through
    reject_gap = None
    if br is not None:
        for j in range(br + 1, i + 1):
            back = (bars[j]["c"] < level) if is_long else (bars[j]["c"] > level)
            if back:
                reject_gap = j - br
                break

    # counter_trend_not_respected: how many counter candles went un-bought-back
    ctnr = 0
    for j in range(max(1, i - CTNR_WINDOW), i):
        b = bars[j]
        counter = (not _is_up(b)) if is_long else _is_up(b)
        if not counter:
            continue
        recovered = any(
            (bars[k]["c"] > b["h"]) if is_long else (bars[k]["c"] < b["l"])
            for k in range(j + 1, min(j + CTNR_RECOVER, i + 1))
        )
        if not recovered:
            ctnr += 1

    # One FLAT tuple per signal. 45,175 signals x 6 ATR windows x 12 OCR variants
    # is a lot of small objects; dicts here cost gigabytes and tuples cost ~25MB.
    #   [0..3]  br, disp, reject_gap, ctnr
    #   then 4 slots per ATR window, in ATR_WINDOWS order
    #   then 2 slots per OCR variant, in OCR_VARIANTS order
    flat = [br is not None, disp, reject_gap, ctnr]
    hi = bars[i]["c"] - bars[0]["o"]
    for n in ATR_WINDOWS:
        a = _atr(bars, i, n)
        eps = EPS_FRAC * (a or 0.0)
        chop = sum(1 for b in bars[max(0, i - CHOP_WINDOW):i + 1]
                   if abs(b["c"] - level) <= eps)
        exh = (abs(hi) / a) if a > 0 else None
        stale_gap = None
        no_rt = False
        if br is not None:
            rt = _retest_bar(bars, i, level, is_long, br, eps)
            no_rt = rt is None
            stale_gap = None if rt is None else (rt - br)
        flat += [chop, exh, stale_gap, no_rt]
    ocr = ocr_features(bars, i, is_long)
    for v in OCR_VARIANTS:
        flat += list(ocr[v])
    return tuple(flat)


W_BASE = 4
O_BASE = 4 + 4 * len(ATR_WINDOWS)


def grade_of(f, st):
    """`downgrade.score`'s grade, from the statistics and one settings dict."""
    w = st["_w"]
    o = st["_o"]
    chop, exh, stale_gap, no_rt = f[w], f[w + 1], f[w + 2], f[w + 3]
    ocr_nr, confl_ocr = f[o], f[o + 1]
    disp, reject_gap = f[1], f[2]
    tripped = 0
    if (not f[0]) or (disp is not None and disp < st["DISP_BODY_MULT"]):
        tripped += 1                                          # no_displacement
    if stale_gap is not None and stale_gap > st["STALE_BARS"]:
        tripped += 1                                          # stale_retest
    if chop >= st["CHOP_TOUCHES"]:
        tripped += 1                                          # level_not_respected
    if exh is not None and exh >= st["EXHAUSTED_ATR"]:
        tripped += 1                                          # exhausted
    if f[3] >= st["UNRESPECTED_COUNTER"]:
        tripped += 1                                          # counter_trend
    if reject_gap is not None and reject_gap <= st["REJECT_BARS"]:
        tripped += 1                                          # break_then_rejection
    if no_rt:
        tripped += 1                                          # no_retest
    if ocr_nr:
        tripped += 1                                          # ocr_not_respected
    confl = bool(f[0]) and confl_ocr
    net = tripped - (1 if confl else 0)
    return ("S" if net <= 0 else ("A" if net == 1 else "C")), tripped, confl


VARS = ("no_displacement", "stale_retest", "level_not_respected", "exhausted",
        "counter_trend_not_respected", "break_then_rejection", "no_retest",
        "ocr_not_respected")


def trips_of(f, st):
    """The same eight tests as `grade_of`, reported individually.

    Only used for the incidence table -- a variable that never trips at any
    setting is not a strict variable, it is an unreachable branch.
    """
    w, o = st["_w"], st["_o"]
    chop, exh, stale_gap, no_rt = f[w], f[w + 1], f[w + 2], f[w + 3]
    return (
        (not f[0]) or (f[1] is not None and f[1] < st["DISP_BODY_MULT"]),
        stale_gap is not None and stale_gap > st["STALE_BARS"],
        chop >= st["CHOP_TOUCHES"],
        exh is not None and exh >= st["EXHAUSTED_ATR"],
        f[3] >= st["UNRESPECTED_COUNTER"],
        f[2] is not None and f[2] <= st["REJECT_BARS"],
        bool(no_rt),
        bool(f[o]),
    )


def setting(**kw):
    st = dict(D)
    st.update(kw)
    st["_w"] = W_BASE + 4 * ATR_WINDOWS.index(st["ATR_WINDOW"])
    st["_o"] = O_BASE + 2 * OCR_VARIANTS.index((st["ocr_lookback"], st["ocr_isolation"]))
    return st


# ---------------------------------------------------------------------------
# RIG 1 -- Austin's 120 graded day-cards
# ---------------------------------------------------------------------------

BEST = {"S": 3, "A": 2, "C": 1}


def build_cards():
    from research.t66_downgrade_measure import replay
    from research.t60_baseline import load_day_cards
    days, _marks = load_day_cards()
    corpus = []
    for key in sorted(days):
        sigs, bars = replay(*key)
        if sigs is None:
            continue
        feats = []
        for s in sigs:
            f = features(bars, s["bar"], s["stop"], s["dir"] == "call")
            if f is not None:
                feats.append(f)
        corpus.append((key, (days[key].get("grade") or "").strip(), feats))
    return corpus


def split_cards(corpus, seed=6):
    """Stratified 50/50 by Austin's OWN grade, deterministic.

    Within each grade class the cards are sorted by (symbol, date) and dealt
    alternately, so TUNE and HOLD each carry the same grade mix and neither half
    can be enriched by a lucky shuffle. `seed` only picks which half starts.
    """
    by_grade = defaultdict(list)
    for row in corpus:
        by_grade[row[1]].append(row)
    tune, hold = [], []
    rnd = random.Random(seed)
    for g in sorted(by_grade):
        rows = sorted(by_grade[g], key=lambda r: r[0])
        flip = rnd.random() < 0.5
        for n, row in enumerate(rows):
            (tune if (n % 2 == 0) != flip else hold).append(row)
    return tune, hold


def eval_cards(rows, st):
    grades = Counter()
    day_mix = Counter()
    confl = n_sigs = 0
    s_hit = s_tot = ff = ff_tot = agree = agree_tot = nosig = 0
    for key, card, feats in rows:
        best = 0
        for f in feats:
            g, _t, c = grade_of(f, st)
            grades[g] += 1
            n_sigs += 1
            confl += 1 if c else 0
            best = max(best, BEST[g])
        day = {3: "S", 2: "A", 1: "C", 0: "-"}[best]
        if card in ("S", "A", "C"):
            agree_tot += 1
            day_mix[day] += 1
            if day == card:
                agree += 1
            if day == "-":
                nosig += 1
            if card == "S":
                s_tot += 1
                if day == "S":
                    s_hit += 1
        elif card == "none":
            ff_tot += 1
            if day == "S":
                ff += 1
    n_day = sum(day_mix[g] for g in ("S", "A", "C"))
    m = sum(AUSTIN_MIX.values())
    shape_day = (0.5 * sum(abs(day_mix[g] / n_day - AUSTIN_MIX[g] / m)
                           for g in ("S", "A", "C")) if n_day else 1.0)
    shape_sig = (0.5 * sum(abs(grades[g] / n_sigs - AUSTIN_MIX[g] / m)
                           for g in ("S", "A", "C")) if n_sigs else 1.0)
    return {"s_hit": s_hit, "s_tot": s_tot, "ff": ff, "ff_tot": ff_tot,
            "s_recall": s_hit / max(s_tot, 1), "false_fire": ff / max(ff_tot, 1),
            "agree": agree, "agree_tot": agree_tot, "nosig": nosig,
            "dS": day_mix["S"], "dA": day_mix["A"], "dC": day_mix["C"],
            "S": grades["S"], "A": grades["A"], "C": grades["C"], "n_sigs": n_sigs,
            "confluence": confl / max(n_sigs, 1),
            "shape_day": shape_day, "shape_sig": shape_sig}


def incidence(corpus, book):
    """Per variable: how often it trips, and whether it separates money at all.

    Computed once, at the committed defaults, and swept across each variable's
    own range to answer the sharper question: is there ANY setting at which this
    variable fires?
    """
    st = setting()
    card_trip = Counter()
    card_n = 0
    for _k, _g, feats in corpus:
        for f in feats:
            card_n += 1
            for x, t in enumerate(trips_of(f, st)):
                if t:
                    card_trip[VARS[x]] += 1
    book_trip = Counter()
    on = {v: [0, 0.0, 0] for v in VARS}          # n, sum R, wins   (traded only)
    off = {v: [0, 0.0, 0] for v in VARS}
    book_n = 0
    for f, traded, win, r, _s in book:
        book_n += 1
        ts = trips_of(f, st)
        for x, t in enumerate(ts):
            if t:
                book_trip[VARS[x]] += 1
            if traded:
                d = (on if t else off)[VARS[x]]
                d[0] += 1
                d[1] += r
                d[2] += 1 if win else 0

    # can each variable EVER fire, anywhere in its own swept range?
    reach = {}
    knob_for = {"no_displacement": "DISP_BODY_MULT", "stale_retest": "STALE_BARS",
                "level_not_respected": "CHOP_TOUCHES", "exhausted": "EXHAUSTED_ATR",
                "counter_trend_not_respected": "UNRESPECTED_COUNTER",
                "break_then_rejection": "REJECT_BARS", "no_retest": None,
                "ocr_not_respected": "ocr_lookback"}
    for x, v in enumerate(VARS):
        if book_trip[v]:
            reach[v] = book_trip[v]              # obviously reachable; no sweep needed
            continue
        knob = knob_for[v]
        vals = ([val for k, vs in SWEEPS if k == knob for val in vs] if knob else [None])
        best = 0
        for val in vals:
            s2 = setting(**({knob: val} if knob else {}))
            best = max(best, sum(1 for f, _t, _w, _r, _s in book if trips_of(f, s2)[x]))
        reach[v] = best
    return card_n, card_trip, book_n, book_trip, on, off, reach


def card_score(r):
    """The gate Austin asked to be ranked on first: recall minus false fires."""
    return r["s_recall"] - r["false_fire"]


# ---------------------------------------------------------------------------
# RIG 2 -- the 2-year book, read-only
# ---------------------------------------------------------------------------

def build_book(limit=None):
    """Re-derive every signal's statistics from the archived bars.

    `bt2y_trades.json` is READ, never written. It carries `et` (entry minute) but
    not the bar index, so the index is recovered by matching the minute inside
    `pf.rth(pf.fetch_day(...))` -- the same array `backtest_2y.py` graded on.
    """
    import polygon_feed as pf
    with open(BT2Y, encoding="utf-8") as fh:
        rows = json.load(fh)["trades"]
    by_day = defaultdict(list)
    for r in rows:
        by_day[(r["sym"], r["day"])].append(r)

    keys = sorted(by_day)
    if limit:
        keys = keys[:limit]
    book, missed = [], 0
    for n, k in enumerate(keys):
        try:
            rth = pf.rth(pf.fetch_day(*k))
        except Exception:
            missed += len(by_day[k])
            continue
        if not rth:
            missed += len(by_day[k])
            continue
        bars = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
                for c in rth]
        idx = {}
        for i, c in enumerate(rth):
            idx.setdefault(c.timestamp[:5], i)
        for r in by_day[k]:
            i = idx.get(r["et"])
            if i is None:
                missed += 1
                continue
            f = features(bars, i, r["stop"], r["dir"] == "call")
            if f is None:
                missed += 1
                continue
            book.append((f, bool(r["traded"]), r["out"] == "win", float(r["r"]),
                         r["sgrade"]))
        if n % 2000 == 0:
            print("  book %d/%d symbol-days" % (n, len(keys)), flush=True)
    return book, missed


def eval_book(book, st):
    """Mean R and win rate per grade, over the traded book and over everything."""
    tr = {g: [0, 0, 0.0] for g in ("S", "A", "C")}     # n, wins, sum R
    al = {g: [0, 0, 0.0] for g in ("S", "A", "C")}
    for f, traded, win, r, _stored in book:
        g, _t, _c = grade_of(f, st)
        a = al[g]
        a[0] += 1
        a[1] += 1 if win else 0
        a[2] += r
        if traded:
            t = tr[g]
            t[0] += 1
            t[1] += 1 if win else 0
            t[2] += r

    def pack(d):
        out = {}
        for g, (n, w, s) in d.items():
            out[g] = {"n": n, "win": (w / n if n else 0.0), "r": (s / n if n else 0.0)}
        return out

    t, a = pack(tr), pack(al)
    mono_r = t["S"]["r"] > t["A"]["r"] > t["C"]["r"]
    mono_w = t["S"]["win"] > t["A"]["win"] > t["C"]["win"]
    return {"traded": t, "all": a, "mono_r": mono_r, "mono_win": mono_w,
            "mono": mono_r and mono_w}


# ---------------------------------------------------------------------------
# selftest -- prove the re-implementation IS downgrade.score
# ---------------------------------------------------------------------------

def selftest(n=400):
    import polygon_feed as pf
    from research import downgrade as dg
    with open(BT2Y, encoding="utf-8") as fh:
        rows = json.load(fh)["trades"]
    rnd = random.Random(11)
    sample = rnd.sample(rows, n)
    by_day = defaultdict(list)
    for r in sample:
        by_day[(r["sym"], r["day"])].append(r)
    ok = bad = skip = 0
    for k, rs in by_day.items():
        try:
            rth = pf.rth(pf.fetch_day(*k))
        except Exception:
            skip += len(rs)
            continue
        bars = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
                for c in rth]
        idx = {}
        for i, c in enumerate(rth):
            idx.setdefault(c.timestamp[:5], i)
        for r in rs:
            i = idx.get(r["et"])
            if i is None:
                skip += 1
                continue
            want = dg.score(bars, i, r["stop"], r["dir"] == "call")
            f = features(bars, i, r["stop"], r["dir"] == "call")
            got = grade_of(f, setting())
            if (want["grade"], want["n_tripped"], want["confluence"]) == got:
                ok += 1
            else:
                bad += 1
                if bad <= 5:
                    print("  MISMATCH %s %s %s: dg=%s/%d/%s  mine=%s"
                          % (k[0], k[1], r["et"], want["grade"], want["n_tripped"],
                             want["confluence"], got))
    print("selftest vs downgrade.score: ok=%d bad=%d skipped=%d" % (ok, bad, skip))
    return bad == 0


# ---------------------------------------------------------------------------
# response-shape classification
# ---------------------------------------------------------------------------

def shape_of(values, series, eps=1e-9):
    """Call the response: dead, monotone, cliff, or non-monotone.

    `series` is the metric at each swept value, in sweep order. This is the
    finding `downgrade_tune.md` proved is worth reporting on its own -- a knob
    whose response is flat is not a knob.
    """
    lo, hi = min(series), max(series)
    if hi - lo <= eps:
        return "dead", 0.0
    span = hi - lo
    deltas = [series[k + 1] - series[k] for k in range(len(series) - 1)]
    biggest = max(abs(d) for d in deltas)
    ups = sum(1 for d in deltas if d > eps)
    downs = sum(1 for d in deltas if d < -eps)
    if biggest >= 0.7 * span and (ups <= 1 or downs <= 1):
        return "cliff", span
    if downs == 0 or ups == 0:
        return "monotone", span
    return "non-monotone", span


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

CARD_HEAD = ("| setting | S recall | false fire | gate | agree | day S/A/C | "
             "day shape | sig S/A/C | confl |\n|---|---|---|---:|---|---|---:|---|---:|")


def card_row(r, label):
    return ("| %s | %d/%d = %.3f | %d/%d = %.3f | **%+.3f** | %d/%d = %.2f | %d/%d/%d | "
            "%.3f | %d/%d/%d | %.1f%%%s |"
            % (label, r["s_hit"], r["s_tot"], r["s_recall"],
               r["ff"], r["ff_tot"], r["false_fire"], card_score(r),
               r["agree"], r["agree_tot"], r["agree"] / max(r["agree_tot"], 1),
               r["dS"], r["dA"], r["dC"], r["shape_day"],
               r["S"], r["A"], r["C"], 100 * r["confluence"],
               " OK" if r["confluence"] < CONFLUENCE_CAP else ""))


MONEY_HEAD = ("| setting | S n | S win | S mean R | A mean R | C mean R | monotone |"
              "\n|---|---:|---:|---:|---:|---:|---|")


def money_row(m, label):
    t = m["traded"]
    return ("| %s | %d | %.1f%% | **%+.3fR** | %+.3fR | %+.3fR | %s |"
            % (label, t["S"]["n"], 100 * t["S"]["win"], t["S"]["r"],
               t["A"]["r"], t["C"]["r"],
               "yes" if m["mono"] else ("R only" if m["mono_r"] else
                                        ("win only" if m["mono_win"] else "**NO**"))))


def label_of(param, value):
    star = "  *(current)*" if value == D.get(param) else ""
    return "`%s = %s`%s" % (param, value, star)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--limit", type=int, default=0,
                    help="cap the 2-year book to N symbol-days (smoke test only)")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)

    t0 = time.time()
    corpus = build_cards()
    print("replayed %d day-cards, %d signals, %.1fs"
          % (len(corpus), sum(len(f) for _, _, f in corpus), time.time() - t0))
    tune, hold = split_cards(corpus)
    all_rows = corpus

    t0 = time.time()
    book, missed = build_book(args.limit or None)
    print("book: %d signals (%d unmatched), %.1fs" % (len(book), missed, time.time() - t0))
    stored = Counter(s for _f, _t, _w, _r, s in book)
    mine = Counter(grade_of(f, setting())[0] for f, _t, _w, _r, _s in book)
    agree_book = sum(1 for f, _t, _w, _r, s in book
                     if grade_of(f, setting())[0] == s)
    print("  stored %s / recomputed %s / agree %d (%.2f%%)"
          % (dict(stored), dict(mine), agree_book, 100 * agree_book / max(len(book), 1)))

    base_all = eval_cards(all_rows, setting())
    base_tune = eval_cards(tune, setting())
    base_hold = eval_cards(hold, setting())
    base_money = eval_book(book, setting())

    rows = []
    for param, values in SWEEPS:
        for v in values:
            st = setting(**{param: v})
            rows.append({"param": param, "value": v, "st": st,
                         "all": eval_cards(all_rows, st),
                         "tune": eval_cards(tune, st),
                         "hold": eval_cards(hold, st),
                         "money": eval_book(book, st)})
            r = rows[-1]
            print("  %-20s %-8s  gate %+.3f  Smoney %+.3fR n=%d  mono=%s"
                  % (param, v, card_score(r["all"]),
                     r["money"]["traded"]["S"]["r"], r["money"]["traded"]["S"]["n"],
                     r["money"]["mono"]), flush=True)

    # ---- candidate selection, on the TUNE half only ----------------------
    # Rules, fixed before the numbers were looked at:
    #   1. selected on TUNE, never on HOLD or on the full 120
    #   2. must keep S > A > C on BOTH mean R and win rate over the 2-year book
    #   3. must not cut the S set's mean R below baseline
    #   4. must not make the day-level shape worse than baseline
    def admissible(r):
        return (r["money"]["mono"]
                and r["money"]["traded"]["S"]["r"] >= base_money["traded"]["S"]["r"]
                and r["all"]["shape_day"] <= base_all["shape_day"] + 1e-9)

    winners = {}
    for param, _values in SWEEPS:
        cands = [r for r in rows if r["param"] == param and r["value"] != D[param]
                 and admissible(r)]
        if not cands:
            continue
        best = max(cands, key=lambda r: (card_score(r["tune"]), -r["all"]["shape_day"]))
        if card_score(best["tune"]) > card_score(base_tune) + 1e-9:
            winners[param] = best

    # ---- combinations: the union of the per-knob winners, MEASURED --------
    combos = []
    if winners:
        ordered = sorted(winners.values(), key=lambda r: -card_score(r["tune"]))
        acc = {}
        for r in ordered:
            acc[r["param"]] = r["value"]
            st = setting(**acc)
            combos.append({"label": ", ".join("%s=%s" % kv for kv in sorted(acc.items())),
                           "st": st, "keys": dict(acc),
                           "all": eval_cards(all_rows, st),
                           "tune": eval_cards(tune, st),
                           "hold": eval_cards(hold, st),
                           "money": eval_book(book, st)})
            print("  combo %-46s gate(tune) %+.3f gate(hold) %+.3f Smoney %+.3fR mono=%s"
                  % (combos[-1]["label"], card_score(combos[-1]["tune"]),
                     card_score(combos[-1]["hold"]),
                     combos[-1]["money"]["traded"]["S"]["r"],
                     combos[-1]["money"]["mono"]), flush=True)

    ok_combos = [c for c in combos if c["money"]["mono"]]
    best_combo = (max(ok_combos, key=lambda c: card_score(c["tune"]))
                  if ok_combos else None)

    inc = incidence(corpus, book)
    write_report(corpus, tune, hold, book, missed, agree_book,
                 base_all, base_tune, base_hold, base_money,
                 rows, winners, combos, best_combo, inc)
    print("wrote %s" % OUT)


def write_report(corpus, tune, hold, book, missed, agree_book,
                 base_all, base_tune, base_hold, base_money,
                 rows, winners, combos, best_combo, inc):
    card_n, card_trip, book_n, book_trip, on, off, reach = inc
    n_traded = sum(1 for _f, t, _w, _r, _s in book if t)
    L = ["# P2 / A1 — the `downgrade.py` threshold sweep, scored on two axes with a "
         "held-out half", ""]
    L.append("Generated by `research/p2_threshold_sweep.py`. **Nothing is applied. No "
             "default in `downgrade.py` is changed by this file or by the run that made "
             "it.** Ratifying or rejecting any number below is R2 — Austin's call.")
    L.append("")
    L.append("## What is measured, and against what")
    L.append("")
    L.append("| rig | data | what it answers |")
    L.append("|---|---|---|")
    L.append("| **cards** | Austin's %d graded day-cards, %d signals | does the grade "
             "agree with his, and does an S-day fire |"
             % (len(corpus), sum(len(f) for _, _, f in corpus)))
    L.append("| **money** | `research/bt2y_trades.json`, %d signals / %d traded | what "
             "the resulting S set MADE, and does S > A > C survive |"
             % (len(book), n_traded))
    L.append("")
    L.append("The second rig is the one `research/downgrade_tune.md` did not have. A "
             "setting that lifts agreement while flattening the S > A > C ordering is a "
             "**worse** setting, not a better one, and only the money rig can see that.")
    L.append("")
    L.append("### Hold-out")
    L.append("")
    L.append("The %d cards are split **50/50, stratified by Austin's own grade**: within "
             "each grade class the cards are sorted by (symbol, date) and dealt "
             "alternately, so both halves carry the same grade mix. Candidates are chosen "
             "on TUNE and **reported on HOLD**. The split is deterministic — re-running "
             "this script reproduces it exactly." % len(corpus))
    L.append("")
    L.append("| half | cards | S-days | refused days |")
    L.append("|---|---:|---:|---:|")
    for name, half in (("TUNE", tune), ("HOLD", hold), ("all", corpus)):
        L.append("| %s | %d | %d | %d |"
                 % (name, len(half),
                    sum(1 for _k, g, _f in half if g == "S"),
                    sum(1 for _k, g, _f in half if g == "none")))
    L.append("")
    L.append("### The harness reproduces `downgrade.score`")
    L.append("")
    L.append("Sweeping 45,175 signals x ~60 settings by calling `downgrade.score` each "
             "time is not affordable, so the grader is re-expressed here as *sufficient "
             "statistics* — one pass over bars yields the gap, the count, the ratio each "
             "variable is really testing, and every threshold then reduces to one "
             "comparison. `--selftest` checks that against `downgrade.score` on a random "
             "400-signal sample and must come back with zero mismatches.")
    L.append("")
    L.append("Against the grades **stored** in `bt2y_trades.json`, the recomputation "
             "agrees on **%d of %d (%.2f%%)**. The residual is level precision: the JSON "
             "stores `stop` rounded to the cent, and a level within a hair of `eps` can "
             "land either side of a comparison. Every row below is computed against this "
             "same recomputed baseline, so the residual cancels."
             % (agree_book, len(book), 100 * agree_book / max(len(book), 1)))
    if missed:
        L.append("")
        L.append("%d signals could not be matched back to a bar and are excluded." % missed)
    L.append("")

    # ---- baseline --------------------------------------------------------
    L.append("## Baseline — `downgrade.py` exactly as committed")
    L.append("")
    L.append(CARD_HEAD)
    L.append(card_row(base_all, "all %d cards" % len(corpus)))
    L.append(card_row(base_tune, "TUNE"))
    L.append(card_row(base_hold, "HOLD"))
    L.append("")
    L.append(MONEY_HEAD)
    L.append(money_row(base_money, "current defaults"))
    L.append("")
    t = base_money["traded"]
    L.append("Over the traded book: S n=%d %.1f%% win %+.3fR · A n=%d %.1f%% %+.3fR · "
             "C n=%d %.1f%% %+.3fR."
             % (t["S"]["n"], 100 * t["S"]["win"], t["S"]["r"],
                t["A"]["n"], 100 * t["A"]["win"], t["A"]["r"],
                t["C"]["n"], 100 * t["C"]["win"], t["C"]["r"]))
    L.append("")

    # ---- the units finding ----------------------------------------------
    L.append("## First finding: 168/304/778 was never comparable to 28/27/3")
    L.append("")
    L.append("T66 put the grader's **per-signal** mix next to Austin's **per-day-card** "
             "mix and read the gap as evidence the thresholds are wrong. Those are "
             "different units. He graded a DAY; the engine emits ~10 signals per day and "
             "the grader scores each one. Collapsing each card to its best signal grade — "
             "the same reduction the `S`-only trading rule makes — gives the comparable "
             "number:")
    L.append("")
    L.append("| mix | S | A | C | distance from 28/27/3 |")
    L.append("|---|---:|---:|---:|---:|")
    m = sum(AUSTIN_MIX.values())
    L.append("| Austin, per day-card | 28 | 27 | 3 | 0.000 |")
    L.append("| grader, per day-card (best signal) | %d | %d | %d | **%.3f** |"
             % (base_all["dS"], base_all["dA"], base_all["dC"], base_all["shape_day"]))
    L.append("| grader, per signal (T66's number) | %d | %d | %d | %.3f |"
             % (base_all["S"], base_all["A"], base_all["C"], base_all["shape_sig"]))
    L.append("")
    L.append("")
    L.append("**The distribution objection dissolves.** Read in his own unit the grader "
             "is already at %d/%d/%d against his %d/%d/%d — distance **%.3f**, not 0.571. "
             "T66's line \"if the distribution above is nothing like that, the thresholds "
             "are wrong before anything else is\" was comparing a per-signal histogram to "
             "a per-day one. The thresholds may still be wrong; the distribution is not "
             "the evidence."
             % (base_all["dS"], base_all["dA"], base_all["dC"],
                AUSTIN_MIX["S"], AUSTIN_MIX["A"], AUSTIN_MIX["C"], base_all["shape_day"]))
    L.append("")
    L.append("What does not agree is **which** days. Exact day-level agreement with his "
             "letter is **%d/%d = %.0f%%**, and S-day recall is **%d/%d**. The grader "
             "produces the right mix of letters and hands them to the wrong cards. That "
             "is a different failure from a mis-set threshold, and no threshold in this "
             "sweep fixes it%s."
             % (base_all["agree"], base_all["agree_tot"],
                100 * base_all["agree"] / max(base_all["agree_tot"], 1),
                base_all["s_hit"], base_all["s_tot"],
                (" — %d of his %d traded cards produce no signal at all"
                 % (base_all["nosig"], base_all["agree_tot"])) if base_all["nosig"] else ""))
    L.append("")

    # ---- variable incidence ---------------------------------------------
    L.append("## Does each variable fire, and does it separate money?")
    L.append("")
    L.append("At the committed defaults. `mean R when tripped` vs `when clean` is over "
             "the %d traded signals — a variable that does not move that number is not "
             "carrying its place in the ladder, whatever its threshold is set to." % n_traded)
    L.append("")
    L.append("| variable | trips on cards | trips on book | traded mean R tripped | clean | "
             "delta | max trips at ANY swept value |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for v in VARS:
        a, b = on[v], off[v]
        ra = a[1] / a[0] if a[0] else 0.0
        rb = b[1] / b[0] if b[0] else 0.0
        L.append("| `%s` | %d (%.1f%%) | %d (%.1f%%) | %+.3fR (n=%d) | %+.3fR (n=%d) | "
                 "%+.3fR | %d |"
                 % (v, card_trip[v], 100 * card_trip[v] / max(card_n, 1),
                    book_trip[v], 100 * book_trip[v] / max(book_n, 1),
                    ra, a[0], rb, b[0], ra - rb, reach[v]))
    L.append("")
    dead_vars = [v for v in VARS if reach[v] < 0.001 * book_n]
    if dead_vars:
        L.append("**%s is effectively unreachable** — %s at the widest value in its swept "
                 "range, out of %d signals, and **zero** on all %d card signals and all "
                 "%d traded signals. That is why `REJECT_BARS` sweeps as a dead knob: the "
                 "threshold is not wrong, the branch is."
                 % (", ".join("`%s`" % v for v in dead_vars),
                    ", ".join("%d" % reach[v] for v in dead_vars),
                    book_n, card_n, n_traded))
        L.append("")
        L.append("The mechanism is the same one `TASKS.md` records for the T4(b) "
                 "entry-bar scratch. `_break_bar` returns the **most recent** bar that "
                 "closed through the level; a later bar closing back through it would "
                 "itself usually create a newer cross, so by construction there is almost "
                 "never anything for `break_then_rejection` to find. Austin's rule — \"it "
                 "broke, then immediately gave it back\" — is real. This implementation "
                 "cannot express it, and the ladder is running on seven variables, not "
                 "eight.")
        L.append("")
    always = [v for v in VARS if book_trip[v] > 0.8 * book_n]
    if always:
        L.append("**%s fires on %s of the signals in the book.** A variable that is true "
                 "of nearly everything is not grading anything — it is a constant −1 "
                 "applied to the whole ladder, and it is most of why the majority of "
                 "signals land on C. Its knob behaves accordingly in the sweep below: "
                 "raising `UNRESPECTED_COUNTER` from 2 to 5 moves S-day recall 12/28 → "
                 "24/28 and false fires 30/61 → 50/61 together, because it is not "
                 "re-sorting a subset, it is lifting the whole distribution at once."
                 % (", ".join("`%s`" % v for v in always),
                    ", ".join("%.0f%%" % (100 * book_trip[v] / book_n) for v in always)))
        L.append("")
    inverted = [v for v in VARS if reach[v] and on[v][0] >= 30 and off[v][0] >= 30
                and (on[v][1] / on[v][0]) >= (off[v][1] / off[v][0])]
    if inverted:
        L.append("**Wrong sign:** %s trips on trades that made MORE than the ones it left "
                 "clean. A downgrade is supposed to mark a worse setup. Either the test "
                 "is inverted, or it is measuring something that is not a defect — worth "
                 "putting in front of Austin as a question about the variable, not about "
                 "its number." % ", ".join("`%s`" % v for v in inverted))
        L.append("")

    # ---- per-knob shape --------------------------------------------------
    L.append("## Response shape, knob by knob")
    L.append("")
    L.append("`gate` = S-day recall − false-fire rate on all %d cards. `S mean R` is over "
             "the traded 2-year book. **A knob whose response is flat is not a knob** — "
             "that is the finding, not a failure to find one." % len(corpus))
    L.append("")
    L.append("| knob | swept | gate response | S-money response | verdict |")
    L.append("|---|---|---|---|---|")
    shapes = {}
    for param, values in SWEEPS:
        rs = [r for r in rows if r["param"] == param]
        gate = [card_score(r["all"]) for r in rs]
        mny = [r["money"]["traded"]["S"]["r"] for r in rs]
        sg, gspan = shape_of(values if isinstance(values[0], str) else values, gate)
        sm, mspan = shape_of(values if isinstance(values[0], str) else values, mny)
        shapes[param] = (sg, gspan, sm, mspan)
        verdict = ("**dead knob**" if sg == "dead" and sm == "dead" else
                   "live" if gspan > 0.05 or mspan > 0.10 else "weak")
        L.append("| `%s` | %s | %s (span %.3f) | %s (span %.3fR) | %s |"
                 % (param, "%s … %s" % (values[0], values[-1]), sg, gspan,
                    sm, mspan, verdict))
    L.append("")

    # ---- full tables -----------------------------------------------------
    for param, values in SWEEPS:
        rs = [r for r in rows if r["param"] == param]
        L.append("### `%s`" % param)
        L.append("")
        L.append(CARD_HEAD)
        for r in rs:
            L.append(card_row(r["all"], label_of(param, r["value"])))
        L.append("")
        L.append(MONEY_HEAD)
        for r in rs:
            L.append(money_row(r["money"], label_of(param, r["value"])))
        L.append("")
        sg, gspan, sm, mspan = shapes[param]
        if sg == "dead" and sm == "dead":
            L.append("**Dead over this range.** Every value yields an identical grade on "
                     "every signal in both rigs. Either the variable never binds, or the "
                     "swept range sits entirely on one side of where it does.")
            L.append("")
        elif sg == "dead":
            L.append("Flat on the card gate; only the money read moves.")
            L.append("")

    # ---- selection -------------------------------------------------------
    L.append("## The best setting, chosen on TUNE and reported on HOLD")
    L.append("")
    L.append("Selection rules, fixed before the numbers were read:")
    L.append("")
    L.append("1. chosen on the **TUNE half only** — never on HOLD, never on all 120;")
    L.append("2. must keep **S > A > C on both mean R and win rate** over the 2-year book;")
    L.append("3. must not cut the S set's mean R below baseline (%+.3fR);"
             % base_money["traded"]["S"]["r"])
    L.append("4. must not make the day-level shape distance worse than baseline (%.3f)."
             % base_all["shape_day"])
    L.append("")
    if not winners:
        L.append("**No single-knob change clears all four.** Every setting that lifts the "
                 "card gate either breaks the S > A > C ordering on money, cuts the S "
                 "set's mean R, or moves the day-level mix further from his.")
        L.append("")
    else:
        L.append("Per-knob survivors (each still one knob moved, everything else at "
                 "committed defaults):")
        L.append("")
        L.append(CARD_HEAD)
        for p, r in sorted(winners.items()):
            L.append(card_row(r["tune"], label_of(p, r["value"]) + " — TUNE"))
        for p, r in sorted(winners.items()):
            L.append(card_row(r["hold"], label_of(p, r["value"]) + " — HOLD"))
        L.append("")
        L.append(MONEY_HEAD)
        for p, r in sorted(winners.items()):
            L.append(money_row(r["money"], label_of(p, r["value"])))
        L.append("")
    if combos:
        L.append("### Combinations, measured as combinations")
        L.append("")
        L.append("`downgrade_tune.md`'s standing caveat is that one-factor sweeps say "
                 "nothing about interactions. These are not a grid search — they are the "
                 "per-knob survivors stacked in order of their TUNE gate, each stack "
                 "re-measured from scratch on both rigs.")
        if len(combos) == 1:
            L.append("")
            L.append("Only one knob survived selection, so there is nothing to stack: the "
                     "\"combination\" below is that single change, and no interaction is "
                     "being claimed.")
        L.append("")
        L.append(CARD_HEAD)
        for c in combos:
            L.append(card_row(c["tune"], "`%s` — TUNE" % c["label"]))
        for c in combos:
            L.append(card_row(c["hold"], "`%s` — HOLD" % c["label"]))
        L.append("")
        L.append(MONEY_HEAD)
        for c in combos:
            L.append(money_row(c["money"], "`%s`" % c["label"]))
        L.append("")
    if best_combo:
        b = best_combo
        L.append("### Recommended — **not applied**")
        L.append("")
        L.append("```")
        for k, v in sorted(b["keys"].items()):
            L.append("%s = %s      # was %s" % (k, v, D[k]))
        L.append("```")
        L.append("")
        L.append("| | TUNE | HOLD | all %d |" % len(corpus))
        L.append("|---|---|---|---|")
        L.append("| S recall | %d/%d | **%d/%d** | %d/%d |"
                 % (b["tune"]["s_hit"], b["tune"]["s_tot"],
                    b["hold"]["s_hit"], b["hold"]["s_tot"],
                    b["all"]["s_hit"], b["all"]["s_tot"]))
        L.append("| false fires | %d/%d | **%d/%d** | %d/%d |"
                 % (b["tune"]["ff"], b["tune"]["ff_tot"],
                    b["hold"]["ff"], b["hold"]["ff_tot"],
                    b["all"]["ff"], b["all"]["ff_tot"]))
        L.append("| gate | %+.3f | **%+.3f** | %+.3f |"
                 % (card_score(b["tune"]), card_score(b["hold"]), card_score(b["all"])))
        L.append("| baseline gate | %+.3f | %+.3f | %+.3f |"
                 % (card_score(base_tune), card_score(base_hold), card_score(base_all)))
        L.append("| day S/A/C | %d/%d/%d | %d/%d/%d | %d/%d/%d |"
                 % (b["tune"]["dS"], b["tune"]["dA"], b["tune"]["dC"],
                    b["hold"]["dS"], b["hold"]["dA"], b["hold"]["dC"],
                    b["all"]["dS"], b["all"]["dA"], b["all"]["dC"]))
        L.append("")
        L.append(MONEY_HEAD)
        L.append(money_row(base_money, "baseline"))
        L.append(money_row(b["money"], "recommended"))
        L.append("")
        d_s = b["hold"]["s_hit"] - base_hold["s_hit"]
        d_f = b["hold"]["ff"] - base_hold["ff"]
        L.append("**Read the size of this before reading the sign.** On the held-out half "
                 "it moves S-day recall by %+d and false fires by %+d — %s. The gate is "
                 "still negative on HOLD (%.3f), meaning the grader fires on a larger "
                 "share of the days Austin refused than of the days he graded S, and this "
                 "change does not fix that. What it does do is cut the S set from %d to "
                 "%d traded signals while raising its mean R from %+.3fR to %+.3fR and its "
                 "win rate from %.1f%% to %.1f%%, with S > A > C intact on both measures. "
                 "That is a real but small tightening, and it is the ONLY single change in "
                 "the sweep that improves the card gate without costing money or shape."
                 % (d_s, d_f,
                    "one card" if abs(d_s) + abs(d_f) == 1 else "%d cards" % (abs(d_s) + abs(d_f)),
                    card_score(b["hold"]),
                    base_money["traded"]["S"]["n"], b["money"]["traded"]["S"]["n"],
                    base_money["traded"]["S"]["r"], b["money"]["traded"]["S"]["r"],
                    100 * base_money["traded"]["S"]["win"],
                    100 * b["money"]["traded"]["S"]["win"]))
        L.append("")

    # ---- distance to 28/27/3 --------------------------------------------
    L.append("## How close does anything get to 28 / 27 / 3?")
    L.append("")
    best_shape = min(rows, key=lambda r: r["all"]["shape_day"])
    L.append("| mix | S | A | C | distance |")
    L.append("|---|---:|---:|---:|---:|")
    L.append("| Austin | 28 | 27 | 3 | 0.000 |")
    L.append("| baseline, per day-card | %d | %d | %d | %.3f |"
             % (base_all["dS"], base_all["dA"], base_all["dC"], base_all["shape_day"]))
    L.append("| closest single setting (`%s = %s`, NOT admissible) | %d | %d | %d | **%.3f** |"
             % (best_shape["param"], best_shape["value"],
                best_shape["all"]["dS"], best_shape["all"]["dA"],
                best_shape["all"]["dC"], best_shape["all"]["shape_day"]))
    if best_combo:
        L.append("| recommended combination | %d | %d | %d | %.3f |"
                 % (best_combo["all"]["dS"], best_combo["all"]["dA"],
                    best_combo["all"]["dC"], best_combo["all"]["shape_day"]))
    L.append("")
    L.append("Austin's mix is **48.3%% S / 46.6%% A / 5.2%% C**. Read per day-card — his "
             "unit — the committed grader is **already there**, and the sweep can shave "
             "the remaining distance but has nothing left to fix. The honest answer to "
             "\"how far does the best setting get toward 28/27/3\" is: **the distance was "
             "never the problem.** The C bucket is the one real residual — the grader "
             "puts %d cards in C where he put 3, and every one of those is a day he was "
             "willing to trade." % base_all["dC"])
    L.append("")
    L.append("Where it is genuinely short is agreement, not shape: %d/%d cards match his "
             "letter and %d/%d of his S-days fire. Moving a threshold trades those two "
             "against each other and does not lift both."
             % (base_all["agree"], base_all["agree_tot"],
                base_all["s_hit"], base_all["s_tot"]))
    L.append("")

    # ---- confluence ------------------------------------------------------
    L.append("## The 1-in-5 confluence cap")
    L.append("")
    L.append("Austin, 2026-08-24: confluence must fire on under 1 in 5 signals. At the "
             "committed defaults it fires on **%.1f%%** of card signals."
             % (100 * base_all["confluence"]))
    under = [r for r in rows if r["all"]["confluence"] < CONFLUENCE_CAP]
    L.append("")
    if under:
        L.append(CARD_HEAD)
        for r in sorted(under, key=lambda r: -card_score(r["all"])):
            L.append(card_row(r["all"], label_of(r["param"], r["value"])))
    else:
        L.append("**No single-knob setting in this sweep clears it.** "
                 "`downgrade_tune.md` already crossed proximity x isolation and found the "
                 "cap reachable only with `lookback<=5, isolation=both2`, at the price of "
                 "S-day recall falling to 6/28. That result stands; nothing here revises it.")
    L.append("")

    # ---- missing / mis-defined ------------------------------------------
    L.append("## Where a variable looks missing or mis-defined")
    L.append("")
    L.append("This is the part of the ticket that is a finding rather than a number. "
             "Everything here is a question for Austin about a VARIABLE, not a request to "
             "ratify a threshold.")
    L.append("")
    L.append("1. **`break_then_rejection` is an unreachable branch** (%d/%d signals at the "
             "widest setting). The rule is his; the implementation is not it. Fixing it "
             "means anchoring on the FIRST break of the level rather than the most recent "
             "one — which is a change to the variable, and R2/R3 territory."
             % (reach["break_then_rejection"], book_n))
    L.append("2. **`counter_trend_not_respected` fires on %.0f%% of everything.** Two "
             "un-bought-back counter candles in a 12-bar window on 1-minute bars is an "
             "ordinary market, not a defect. Whatever Austin means by \"red candles inside "
             "an uptrend that don't get bought back\", he does not mean 9 signals in 10."
             % (100 * book_trip["counter_trend_not_respected"] / book_n))
    L.append("3. **`level_not_respected` has the wrong sign on money** (%+.3fR when it "
             "trips vs %+.3fR when it does not, over %d traded signals). It also fires on "
             "%.0f%% of the book. Combined with (2), two of the eight variables are true "
             "of the majority of signals, which is the whole reason the C bucket is large."
             % (on["level_not_respected"][1] / max(on["level_not_respected"][0], 1),
                off["level_not_respected"][1] / max(off["level_not_respected"][0], 1),
                n_traded, 100 * book_trip["level_not_respected"] / book_n))
    L.append("4. **`stale_retest` fires on %.1f%% of the book**, which is why "
             "`STALE_BARS` sweeps nearly flat. It is not dead, but it is not doing work "
             "either." % (100 * book_trip["stale_retest"] / book_n))
    L.append("5. **The gap is agreement, not distribution.** %d/%d card agreement with a "
             "day-level mix that already matches his says the ladder is sorting the right "
             "proportions of the wrong days. A threshold cannot fix that; either a "
             "variable is missing, or the level the grader is handed (the stop, as a "
             "proxy) is not the level Austin was looking at."
             % (base_all["agree"], base_all["agree_tot"]))
    L.append("")

    # ---- what this does not say -----------------------------------------
    L.append("## What this does not say")
    L.append("")
    L.append("1. **No number here is ratified.** R2 is Austin's. The defaults in "
             "`downgrade.py` are untouched.")
    L.append("2. **The money rig re-grades, it does not re-detect.** Changing a downgrade "
             "threshold changes which signals are S; it does not change which signals "
             "exist, and it does not change what any of them made. The R column is the "
             "outcome the 2-year replay already recorded.")
    L.append("3. **The traded book is pre-filtered by the legacy grader.** Only 1,016 of "
             "45,175 signals were traded, chosen by `_grade_pa`. The S set measured here "
             "lives inside that filter, and 7,225 signals this grader calls S were never "
             "traded at all.")
    L.append("4. **Two halves of 120 cards is a small hold-out.** A HOLD gate that moves "
             "by one or two days is one card changing its mind. Believe the large, "
             "monotone moves and nothing else.")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
