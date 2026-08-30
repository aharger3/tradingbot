"""g81_displacement.py -- is the SHIPPED displacement check the thing Austin means?

Austin refused 9 of the 30 g71 homework cards on 2026-08-29 and named displacement
in four of them, unprompted. Displacement is NOT a new rule and must not be built as
one: `research/downgrade.py::no_displacement` is variable #1 of the eight, ratified
in rule ballot batch 01, q18 ("br-needs-displacement", answer "tweak"). So the
question this script answers is not "should displacement be a variable" -- it is
already one -- but:

    does the shipped implementation measure what he means by the word?

WHAT THE SHIPPED CHECK DOES
---------------------------
    no_displacement(bars, i, level, is_long):
        br = _break_bar(...)            # most recent close through the level, 30 back
        if br is None: return True      # "never broke with conviction"
        avg = mean body of the 10 bars before the break
        return body(bars[br]) < 1.5 * avg

That is a BODY-SIZE comparison: is the breaking candle fatter than the candles just
before it. It never looks at the level again after finding the break bar.

WHAT HE AND THE MENTORS SAY
---------------------------
Austin, all six displacement sentences in the 2026-08-29 homework file (read-only):

  AMD  2025-09-08 (no):  "10:37 but really no displacement from the original candles
                          so i have to downgrade"
  NVDA 2025-06-24 (no):  "really good a trade i wish it was an S but it didnt displace
                          from that wick, but technically it is an OCR and BR just
                          neither of the parts have displacement"
  QQQ  2025-12-22 (no):  why_not = [no_displacement, chop]
  MSFT 2025-08-29 (YES): "BR OCB confluence, not perfect because no displacement but
                          you get a +1 9:38 is the entry"
  SPY  2026-06-17 (YES): "your s is good too but its tight on if theres displacement"
  QQQ  2024-08-26 (YES): "a break retest with no dispacement happens at 9:45, its not
                          of the level just the wicks at the beginning of the day"

The mentor corpus (research/corpus_sf/mentor_rules.jsonl) gives the definition in one
sentence, and it is a DISTANCE, not a candle size -- Neto, cluster SF063:

  "We usually are looking for a break of a key level, some displacement (ACTUAL
   SEPARATION FROM THE CANDLES TO THE KEY LEVEL), then the retest and lastly strong
   reaction on the key level"

  SF055, Neto: "I'm not a big fan of immediate retest because I like to have
   displacement and then the retest of my key level"
  SF050, Lauren: "I only took the trades when there was strong displacement and strong
   price action above/below the range"  (xref_verdict AGREES, anchored to ballot q18)

Austin's own three references are all to the STRUCTURE, never to a body: "from the
original candles", "from that wick", "not of the level just the wicks". Separation is
what he is looking at. The shipped check cannot see it.

THE FOUR VARIANTS MEASURED HERE
-------------------------------
  A   shipped            body(break bar) < 1.5 x avg body of the prior 10
  A0  shipped, decomposed  same, but the "no break bar found" branch counted separately
  B   separation         max excursion past the level, break bar -> entry bar, in ATR;
                         trips below DISP_SEP_ATR.  Neto's definition.
  B0  separation, no-break-neutral   same, but "no break found" does not trip
  D   both parts         "neither of the parts have displacement": B on the BR leg AND
                         B on the OCR leg (separation of the OCR candle's own edge).
                         Trips if EITHER part lacks separation.

NOTHING IS APPLIED. This workflow measures. `downgrade.py` is untouched; the diffs are
proposed in research/g81_displacement.md and left there.

THE THRESHOLD IS A GUESS AND IS SWEPT, NOT FITTED
-------------------------------------------------
DISP_SEP_ATR is chosen a priori, not fitted to the mark pool: the project's one
tolerance unit is 0.25 x ATR (BAR_EXTREME_FRAC), so "actual separation" has to clear
the noise unit by a clear margin. 1.0 ATR -- one average candle of clear air between
price and the level -- is the a-priori pick. Every number is also reported across a
0.25..3.0 sweep so the sensitivity is visible and nothing is silently tuned.

Read-only over every mark corpus (via research/marks_pool.py). No mark file is opened
for writing.

Usage:  python research/g81_displacement.py [--out research/g81_displacement.json]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import polygon_feed as pf            # noqa: E402
import downgrade as dg               # noqa: E402  (research/ is on the path)
import marks_pool                    # noqa: E402  the canonical S/A/C/none pool

BOOK = os.path.join(HERE, "bt2y_trades.json")
HOMEWORK = os.path.join(HERE, "marks", "probe_g71_homework_s3_2026-08-29_complete.jsonl")

# The standing error bar on this project (DIRECTION.md). Two arms inside it is a TIE.
ERROR_BAR_R = 1.5799

# --- thresholds. AUSTIN HAS NOT SET ANY OF THESE, same as every constant in
# --- downgrade.py. Chosen a priori, swept below, never fitted.
DISP_SEP_ATR = 1.0        # separation past the level, in ATR at the entry bar
SWEEP = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)

# Trip-rate red flags. This project has killed variables at both ends: a branch that
# can never be true (level_not_respected once tripped 13 of 45,175) and a branch that
# trips on everything (counter_trend_not_respected trips 89.8% of the current book).
RATE_FLOOR, RATE_CEIL = 0.02, 0.60


# ---------------------------------------------------------------------------
# the variants
# ---------------------------------------------------------------------------

def separation_atr(bars, i, level, is_long, br=None):
    """Max excursion PAST the level between the break bar and bar i, in ATR.

    Neto's "actual separation from the candles to the key level". Causal: reads
    only bars <= i, and only bars at or after the break.

    Returns (sep_in_atr, break_index) or (None, None) when nothing broke.
    """
    if br is None:
        br = dg._break_bar(bars, i, level, is_long)
    if br is None:
        return None, None
    a = dg._atr(bars, i)
    if a <= 0:
        return None, br
    if is_long:
        far = max(b["h"] for b in bars[br:i + 1])
        d = far - level
    else:
        far = min(b["l"] for b in bars[br:i + 1])
        d = level - far
    return (d / a), br


def no_displacement_separation(bars, i, level, is_long, thr=DISP_SEP_ATR,
                               nobreak_trips=True):
    """Variant B. Trips when the break never put clear air between price and the
    level. `nobreak_trips` mirrors the shipped convention (no break -> trip);
    B0 sets it False so "cannot judge" is not counted as a failure."""
    sep, br = separation_atr(bars, i, level, is_long)
    if br is None:
        return bool(nobreak_trips)
    if sep is None:
        return False                     # cannot judge; do not invent a downgrade
    return sep < thr


def ocr_separation_atr(bars, i, is_long):
    """The second half of variant D. "neither of the PARTS have displacement" --
    the OCR candle's own edge is a level too, and price has to have separated from
    it. Returns separation in ATR, or None when there is no OCR in range (absence
    of the setup is not a failure of it -- same convention as ocr_not_respected)."""
    j = dg.find_ocr(bars, i, is_long)
    if j is None:
        return None
    a = dg._atr(bars, i)
    if a <= 0:
        return None
    edge = bars[j]["l"] if is_long else bars[j]["h"]
    if is_long:
        d = max(b["h"] for b in bars[j:i + 1]) - edge
    else:
        d = edge - min(b["l"] for b in bars[j:i + 1])
    return d / a


def _trips_from(sep, no_break, ocr_sep, thr, nobreak_trips=True, both_parts=False):
    """Every variant is a comparison against ONE pair of pre-computed separations,
    so the whole 0.25..3.0 sweep costs no extra bar walking."""
    if no_break:
        br_bad = bool(nobreak_trips)
    elif sep is None:
        br_bad = False
    else:
        br_bad = sep < thr
    if not both_parts or br_bad:
        return br_bad
    if ocr_sep is None:
        return False
    return ocr_sep < thr


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, (c - h) / d, (c + h) / d


def _lchoose(n, k):
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1))


def fisher_two_sided(a, b, c, d):
    """2x2 [[a,b],[c,d]] two-sided Fisher exact p."""
    n = a + b + c + d
    r1, c1 = a + b, a + c
    def pr(x):
        return math.exp(_lchoose(r1, x) + _lchoose(n - r1, c1 - x) - _lchoose(n, c1))
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    p0 = pr(a)
    tot = 0.0
    for x in range(lo, hi + 1):
        p = pr(x)
        if p <= p0 * (1 + 1e-9):
            tot += p
    return min(1.0, tot)


def boot_diff(xs, ys, n=4000, seed=17):
    """Bootstrap 95% CI on mean(xs) - mean(ys)."""
    if not xs or not ys:
        return (0.0, 0.0, 0.0)
    rnd = random.Random(seed)
    obs = sum(xs) / len(xs) - sum(ys) / len(ys)
    ds = []
    for _ in range(n):
        a = sum(rnd.choice(xs) for _ in xs) / len(xs)
        b = sum(rnd.choice(ys) for _ in ys) / len(ys)
        ds.append(a - b)
    ds.sort()
    return obs, ds[int(0.025 * n)], ds[int(0.975 * n) - 1]


def boot_prop_diff(k1, n1, k2, n2, n=4000, seed=23):
    if not n1 or not n2:
        return (0.0, 0.0, 0.0)
    xs = [1.0] * k1 + [0.0] * (n1 - k1)
    ys = [1.0] * k2 + [0.0] * (n2 - k2)
    return boot_diff(xs, ys, n=n, seed=seed)


# ---------------------------------------------------------------------------
# bars
# ---------------------------------------------------------------------------

_BARCACHE = {}


def dbars_for(sym, day):
    key = (sym, day)
    if key in _BARCACHE:
        return _BARCACHE[key]
    try:
        r = pf.rth(pf.fetch_day(sym, day))
    except Exception:
        r = []
    out = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
           for c in r] if r else []
    if len(_BARCACHE) > 400:
        _BARCACHE.clear()
    _BARCACHE[key] = out
    return out


# ---------------------------------------------------------------------------
# pass 1 -- the whole book
# ---------------------------------------------------------------------------

def scan_book(rows, verbose=True):
    """Recompute every variant at each signal's own entry bar.

    Returns per-row records. Also validates the rig: variant A must reproduce the
    `no_displacement` already stored in each book row's `downgrades` list. If it
    does not reproduce, every number downstream is measuring a different bar and
    the run aborts."""
    by_day = defaultdict(list)
    for idx, r in enumerate(rows):
        by_day[(r["sym"], r["day"])].append(idx)

    recs = [None] * len(rows)
    agree = disagree = skipped = 0
    dis_dir = Counter()
    dis_sample = []
    days = sorted(by_day)
    for n, key in enumerate(days):
        if verbose and n % 1000 == 0:
            print("  %5d / %d symbol-days" % (n, len(days)), flush=True)
        sym, day = key
        bars = dbars_for(sym, day)
        if not bars:
            skipped += len(by_day[key])
            continue
        for idx in by_day[key]:
            r = rows[idx]
            i, level = r.get("entry_i"), r.get("stop")
            if i is None or level is None or i >= len(bars):
                skipped += 1
                continue
            is_long = (r["dir"] == "call")
            br = dg._break_bar(bars, i, level, is_long)
            a_ship = dg.no_displacement(bars, i, level, is_long)
            sep, _ = separation_atr(bars, i, level, is_long, br=br)
            ocr_sep = ocr_separation_atr(bars, i, is_long)
            nb = br is None

            book_says = "no_displacement" in (r.get("downgrades") or [])
            if a_ship == book_says:
                agree += 1
            else:
                disagree += 1
                dis_dir["rig_trips_book_did_not" if a_ship
                        else "book_tripped_rig_did_not"] += 1
                if len(dis_sample) < 12:
                    dis_sample.append({"sym": sym, "day": day, "et": r["et"],
                                       "rig": a_ship, "book": book_says})

            recs[idx] = {
                "A": a_ship,
                "no_break": nb,
                "sep": sep,
                "conf": dg.has_confluence(bars, i, level, is_long),
                # every OTHER downgrade the book already recorded, so a variant can
                # be swapped in for no_displacement and the grade recomputed without
                # re-running the other seven checks
                "others": len([d for d in (r.get("downgrades") or [])
                               if d != "no_displacement"]),
                "B": {t: _trips_from(sep, nb, ocr_sep, t, True, False) for t in SWEEP},
                "B0": {t: _trips_from(sep, nb, ocr_sep, t, False, False) for t in SWEEP},
                "D": {t: _trips_from(sep, nb, ocr_sep, t, True, True) for t in SWEEP},
            }
    return recs, {"agree": agree, "disagree": disagree, "skipped": skipped,
                   "direction": dict(dis_dir), "sample": dis_sample}


def regrade(rows, recs, thr):
    """Swap each variant in for `no_displacement` and recompute Austin's ladder.

    score = (other downgrades) + (1 if this variant trips) - (1 if confluence),
    floored at C -- exactly `downgrade.score()`'s arithmetic, with the seven other
    checks read off the book rather than recomputed. Reports the S/A/C shift and
    what the traded S bucket earns under each."""
    out = {}
    for v in ("A", "B", "B0", "D", "OFF"):
        dist = Counter()
        s_r, s_win, s_n = 0.0, 0, 0
        for idx, r in enumerate(rows):
            rec = recs[idx]
            if rec is None:
                continue
            if v == "OFF":
                trip = False
            elif v == "A":
                trip = rec["A"]
            else:
                trip = rec[v][thr]
            net = rec["others"] + (1 if trip else 0) - (1 if rec["conf"] else 0)
            g = "S" if net <= 0 else ("A" if net == 1 else "C")
            dist[g] += 1
            if g == "S" and r.get("traded") and r.get("r") is not None:
                s_r += float(r["r"])
                s_win += 1 if float(r["r"]) > 0 else 0
                s_n += 1
        out[v] = {"dist": dict(dist),
                  "S_rate": dist["S"] / max(1, sum(dist.values())),
                  "traded_S_n": s_n,
                  "traded_S_meanR": (s_r / s_n) if s_n else 0.0,
                  "traded_S_win": (s_win / s_n) if s_n else 0.0}
    return out


# ---------------------------------------------------------------------------
# pass 2 -- score against the canonical mark pool
# ---------------------------------------------------------------------------

def score_against_pool(rows, recs, pool, thr):
    """Does the variable separate Austin's S days from his `none` days?

    Two readings, both day-level (he judged DAYS, the variable judges SIGNALS):

      signal-level : trip rate over every book signal that falls on a judged day
      day-level    : does the day contain AT LEAST ONE signal with displacement
                     PRESENT (the variable not tripping)

    Restricted to judged symbol-days the book actually has signals for."""
    sig = {"S": defaultdict(lambda: [0, 0]), "none": defaultdict(lambda: [0, 0])}
    day_any = {"S": defaultdict(lambda: [0, 0]), "none": defaultdict(lambda: [0, 0])}
    day_present = {"S": defaultdict(list), "none": defaultdict(list)}

    variants = ("A", "B", "B0", "D")
    by_day = defaultdict(list)
    for idx, r in enumerate(rows):
        if recs[idx] is None:
            continue
        by_day[(r["sym"], r["day"])].append(idx)

    n_days = {"S": 0, "none": 0}
    for key, idxs in by_day.items():
        pk = "%s_%s" % key
        e = pool.get(pk)
        if e is None or e.grade not in ("S", "none"):
            continue
        g = e.grade
        n_days[g] += 1
        for v in variants:
            trips = [(recs[i]["A"] if v == "A" else recs[i][v][thr]) for i in idxs]
            sig[g][v][0] += sum(1 for t in trips if t)
            sig[g][v][1] += len(trips)
            present = any(not t for t in trips)
            day_any[g][v][0] += 1 if present else 0
            day_any[g][v][1] += 1
            day_present[g][v].append(1.0 if present else 0.0)

    out = {"n_days": dict(n_days), "variants": {}}
    for v in variants:
        ks, ns = sig["S"][v]
        kn, nn = sig["none"][v]
        ps, plo, phi = wilson(ks, ns)
        pn, nlo, nhi = wilson(kn, nn)
        ds, dslo, dshi = day_any["S"][v][0], 0, 0
        aS, tS = day_any["S"][v]
        aN, tN = day_any["none"][v]
        obs, lo, hi = boot_prop_diff(aS, tS, aN, tN)
        out["variants"][v] = {
            "signal_trip_S": {"k": ks, "n": ns, "rate": ps, "lo": plo, "hi": phi},
            "signal_trip_none": {"k": kn, "n": nn, "rate": pn, "lo": nlo, "hi": nhi},
            "signal_trip_gap_pp": (pn - ps) * 100,
            "day_has_displaced_S": {"k": aS, "n": tS,
                                    "rate": (aS / tS if tS else 0.0)},
            "day_has_displaced_none": {"k": aN, "n": tN,
                                       "rate": (aN / tN if tN else 0.0)},
            "day_gap_pp": obs * 100,
            "day_gap_ci_pp": [lo * 100, hi * 100],
            "day_fisher_p": fisher_two_sided(aS, tS - aS, aN, tN - aN),
        }
    return out


def grade_separation(rows, recs, pool, thr):
    """The separation question one level up, where it actually matters.

    The variable is not the product -- the GRADE is. So: under each definition of
    displacement, on what share of Austin's S days does the book contain at least
    one signal his ladder grades S, and on what share of his refusals does it do
    the same? A useful variable widens that gap. This is the held-out-recall shape
    DIRECTION.md says to gate on, computed on his own ladder rather than on mean R.
    """
    by_day = defaultdict(list)
    for idx, r in enumerate(rows):
        if recs[idx] is not None:
            by_day[(r["sym"], r["day"])].append(idx)
    out = {}
    for v in ("OFF", "A", "B", "B0", "D"):
        hit = {"S": [0, 0], "none": [0, 0]}
        for key, idxs in by_day.items():
            e = pool.get("%s_%s" % key)
            if e is None or e.grade not in ("S", "none"):
                continue
            any_s = False
            for i in idxs:
                rec = recs[i]
                trip = (False if v == "OFF" else
                        rec["A"] if v == "A" else rec[v][thr])
                net = rec["others"] + (1 if trip else 0) - (1 if rec["conf"] else 0)
                if net <= 0:
                    any_s = True
                    break
            hit[e.grade][0] += 1 if any_s else 0
            hit[e.grade][1] += 1
        kS, nS = hit["S"]
        kN, nN = hit["none"]
        obs, lo, hi = boot_prop_diff(kS, nS, kN, nN)
        out[v] = {"S_hit": kS, "S_n": nS, "S_rate": kS / nS if nS else 0.0,
                  "none_hit": kN, "none_n": nN,
                  "none_rate": kN / nN if nN else 0.0,
                  "gap_pp": obs * 100, "ci_pp": [lo * 100, hi * 100],
                  "fisher_p": fisher_two_sided(kS, nS - kS, kN, nN - kN)}
    return out


# ---------------------------------------------------------------------------
# pass 3 -- money
# ---------------------------------------------------------------------------

def money(rows, recs, thr):
    """Mean R of traded signals where displacement is PRESENT vs where it TRIPS,
    and the delta against the standing +/-1.5799R error bar."""
    out = {}
    for v in ("A", "B", "B0", "D"):
        keep, drop = [], []
        for idx, r in enumerate(rows):
            if recs[idx] is None or not r.get("traded"):
                continue
            rr = r.get("r")
            if rr is None:
                continue
            t = recs[idx]["A"] if v == "A" else recs[idx][v][thr]
            (drop if t else keep).append(float(rr))
        obs, lo, hi = boot_diff(keep, drop)
        book = keep + drop
        out[v] = {
            "n_present": len(keep), "n_tripped": len(drop),
            "meanR_present": (sum(keep) / len(keep)) if keep else 0.0,
            "meanR_tripped": (sum(drop) / len(drop)) if drop else 0.0,
            "delta": obs, "ci": [lo, hi],
            "inside_error_bar": abs(obs) < ERROR_BAR_R,
            "book_meanR": (sum(book) / len(book)) if book else 0.0,
            "win_present": (sum(1 for x in keep if x > 0) / len(keep)) if keep else 0.0,
            "win_tripped": (sum(1 for x in drop if x > 0) / len(drop)) if drop else 0.0,
        }
    return out


# ---------------------------------------------------------------------------
# pass 4 -- his six displacement sentences, card by card
# ---------------------------------------------------------------------------

# The six cards in the 2026-08-29 homework where he used the word, or filed
# no_displacement as the reason. Quoted verbatim from the file (read-only).
DISP_CARDS = {
    "AMD_2025-09-08":  ("no",  "10:37", "no displacement from the original candles so i have to downgrade"),
    "NVDA_2025-06-24": ("no",  None,    "it didnt displace from that wick ... neither of the parts have displacement"),
    "QQQ_2025-12-22":  ("no",  None,    "why_not = [no_displacement, chop]"),
    "MSFT_2025-08-29": ("yes", "9:38",  "BR OCR confluence, not perfect because no displacement but you get a +1"),
    "SPY_2026-06-17":  ("yes", "9:48",  "your s is good too but its tight on if theres displacement"),
    "QQQ_2024-08-26":  ("yes", "9:56",  "a break retest with no dispacement happens at 9:45, its not of the level just the wicks"),
}


def _mins(et):
    try:
        h, m = et.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def his_cards(rows, recs, thr):
    """For each of the six cards: what every variant says on the engine signal
    nearest the minute he named (or the day's first signal when he named none)."""
    by_day = defaultdict(list)
    for idx, r in enumerate(rows):
        by_day["%s_%s" % (r["sym"], r["day"])].append(idx)
    out = []
    for card, (verdict, minute, quote) in sorted(DISP_CARDS.items()):
        idxs = [i for i in by_day.get(card, []) if recs[i] is not None]
        if not idxs:
            out.append({"card": card, "verdict": verdict, "quote": quote,
                        "n_signals": 0, "note": "no book signal with bars"})
            continue
        tgt = _mins(minute) if minute else None
        if tgt is not None:
            pick = min(idxs, key=lambda i: abs((_mins(rows[i]["et"]) or 0) - tgt))
        else:
            pick = min(idxs, key=lambda i: (_mins(rows[i]["et"]) or 0))
        rec, r = recs[pick], rows[pick]
        row = {
            "card": card, "verdict": verdict, "his_minute": minute, "quote": quote,
            "n_signals": len(idxs), "picked_et": r["et"],
            "sep_atr": (round(rec["sep"], 2) if rec["sep"] is not None else None),
            "no_break": rec["no_break"], "confluence": rec["conf"],
            "A_shipped_trips": rec["A"],
            "B_separation_trips": rec["B"][thr],
            "D_both_parts_trips": rec["D"][thr],
            "sgrade_in_book": r.get("sgrade"),
            "book_downgrades": r.get("downgrades"),
        }
        # what each variant would have to say to agree with him: he refused three
        # cards FOR displacement (variable should trip) and named it as a flaw --
        # not an absolute veto -- on three he took (may trip, carried by the +1).
        row["A_agrees"] = (rec["A"] if verdict == "no" else True)
        out.append(row)
    return out


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "g81_displacement.json"))
    ap.add_argument("--thr", type=float, default=DISP_SEP_ATR)
    a = ap.parse_args()
    thr = a.thr

    book = json.load(open(BOOK, encoding="utf-8"))
    rows = book["trades"]
    print("book: %d signals, %d traded, %s..%s"
          % (len(rows), book["meta"]["traded"], book["meta"]["first"], book["meta"]["last"]))

    print("scanning the book (recomputing every variant at each signal's entry bar)...")
    recs, val = scan_book(rows, verbose=True)
    n_scored = sum(1 for x in recs if x is not None)
    print("scored %d of %d signals (%d skipped: no bars / no entry index)"
          % (n_scored, len(rows), val["skipped"]))
    print("rig validation vs the book's own stored `downgrades`: "
          "%d agree, %d disagree" % (val["agree"], val["disagree"]))
    if val["agree"] and val["disagree"] / max(1, val["agree"] + val["disagree"]) > 0.01:
        raise SystemExit("ABORT: variant A does not reproduce the shipped variable "
                         "-- the rig is grading a different bar than the book did.")

    # --- trip rates, the FIRST number reported ----------------------------
    rates = {}
    scored = [x for x in recs if x is not None]
    rates["A_shipped"] = sum(1 for x in scored if x["A"]) / n_scored
    rates["A_nobreak_branch"] = sum(1 for x in scored if x["no_break"]) / n_scored
    rates["A_weak_body_only"] = sum(1 for x in scored
                                    if x["A"] and not x["no_break"]) / n_scored
    for v in ("B", "B0", "D"):
        rates[v] = {t: sum(1 for x in scored if x[v][t]) / n_scored for t in SWEEP}

    print("\nTRIP RATES over %d scored signals" % n_scored)
    print("  A  shipped (body-size)          %5.1f%%" % (100 * rates["A_shipped"]))
    print("     of which: no break bar found %5.1f%%" % (100 * rates["A_nobreak_branch"]))
    print("     of which: weak body          %5.1f%%" % (100 * rates["A_weak_body_only"]))
    print("  sweep, separation in ATR:")
    print("      thr     B(no-break trips)   B0(neutral)   D(both parts)")
    for t in SWEEP:
        print("     %4.2f      %6.1f%%            %6.1f%%       %6.1f%%"
              % (t, 100 * rates["B"][t], 100 * rates["B0"][t], 100 * rates["D"][t]))

    flags = []
    for name, r in (("A shipped", rates["A_shipped"]), ("B @%.2f" % thr, rates["B"][thr]),
                    ("B0 @%.2f" % thr, rates["B0"][thr]), ("D @%.2f" % thr, rates["D"][thr])):
        if r < RATE_FLOOR:
            flags.append("%s trips %.2f%% -- BELOW the 2%% floor, red flag" % (name, 100 * r))
        elif r > RATE_CEIL:
            flags.append("%s trips %.1f%% -- ABOVE the 60%% ceiling, red flag" % (name, 100 * r))
    for f in flags:
        print("  FLAG: " + f)

    # --- the mark pool ----------------------------------------------------
    print("\nbuilding the canonical mark pool (read-only)...")
    pool = marks_pool.canonical_pool()
    gc = Counter(e.grade for e in pool.values())
    print("  pool: %d judged symbol-days, S=%d none=%d" % (len(pool), gc["S"], gc["none"]))
    sep = score_against_pool(rows, recs, pool, thr)
    print("  judged days the book has signals on: S=%d none=%d"
          % (sep["n_days"]["S"], sep["n_days"]["none"]))
    print("\nSEPARATION (does it tell his S days from his refusals?) @ thr=%.2f" % thr)
    for v, d in sep["variants"].items():
        print("  %-3s signal trip rate  S %5.1f%%  none %5.1f%%   gap %+5.1f pp"
              % (v, 100 * d["signal_trip_S"]["rate"], 100 * d["signal_trip_none"]["rate"],
                 d["signal_trip_gap_pp"]))
        print("      day has a displaced signal  S %5.1f%% (%d/%d)  none %5.1f%% (%d/%d)"
              % (100 * d["day_has_displaced_S"]["rate"], d["day_has_displaced_S"]["k"],
                 d["day_has_displaced_S"]["n"], 100 * d["day_has_displaced_none"]["rate"],
                 d["day_has_displaced_none"]["k"], d["day_has_displaced_none"]["n"]))
        print("      gap %+.1f pp, 95%% CI [%+.1f, %+.1f], Fisher p = %.3f"
              % (d["day_gap_pp"], d["day_gap_ci_pp"][0], d["day_gap_ci_pp"][1],
                 d["day_fisher_p"]))

    # sweep the separation gap so the threshold choice is visible
    sweep_sep = {}
    for t in SWEEP:
        s = score_against_pool(rows, recs, pool, t)
        sweep_sep[t] = {v: {"gap_pp": s["variants"][v]["day_gap_pp"],
                            "p": s["variants"][v]["day_fisher_p"],
                            "trip": rates[v][t] if v in ("B", "B0", "D") else rates["A_shipped"]}
                        for v in ("A", "B", "B0", "D")}
    print("\nSEPARATION SWEEP (day-level gap in points, S minus none, + = good)")
    print("      thr    B gap (p)          B0 gap (p)         D gap (p)")
    for t in SWEEP:
        s = sweep_sep[t]
        print("     %4.2f   %+5.1f (p=%.3f)   %+5.1f (p=%.3f)   %+5.1f (p=%.3f)"
              % (t, s["B"]["gap_pp"], s["B"]["p"], s["B0"]["gap_pp"], s["B0"]["p"],
                 s["D"]["gap_pp"], s["D"]["p"]))

    # --- money ------------------------------------------------------------
    mny = money(rows, recs, thr)
    print("\nMONEY over traded signals @ thr=%.2f   (error bar +/-%.4fR)" % (thr, ERROR_BAR_R))
    for v, d in mny.items():
        print("  %-3s present n=%4d meanR %+.4f (%4.1f%% win) | tripped n=%4d meanR %+.4f (%4.1f%% win)"
              % (v, d["n_present"], d["meanR_present"], 100 * d["win_present"],
                 d["n_tripped"], d["meanR_tripped"], 100 * d["win_tripped"]))
        print("      delta %+.4fR, 95%% CI [%+.4f, %+.4f] -- %s"
              % (d["delta"], d["ci"][0], d["ci"][1],
                 "INSIDE the error bar, a TIE" if d["inside_error_bar"] else "outside the error bar"))

    # --- his six sentences ------------------------------------------------
    cards = his_cards(rows, recs, thr)
    print("\nHIS SIX DISPLACEMENT CARDS @ thr=%.2f" % thr)
    for c in cards:
        if c["n_signals"] == 0:
            print("  %-16s %-3s  (%s)" % (c["card"], c["verdict"], c["note"]))
            continue
        print("  %-16s he=%-3s  sep=%s ATR  nobreak=%-5s confl=%-5s | A=%-5s B=%-5s D=%-5s"
              % (c["card"], c["verdict"],
                 ("%5.2f" % c["sep_atr"]) if c["sep_atr"] is not None else " none",
                 c["no_break"], c["confluence"],
                 c["A_shipped_trips"], c["B_separation_trips"], c["D_both_parts_trips"]))

    agree_no = sum(1 for c in cards if c["verdict"] == "no" and c.get("A_shipped_trips"))
    n_no = sum(1 for c in cards if c["verdict"] == "no" and c["n_signals"])
    agree_no_B = sum(1 for c in cards if c["verdict"] == "no" and c.get("B_separation_trips"))
    print("  on his three displacement REFUSALS: shipped A trips %d/%d, "
          "separation B trips %d/%d" % (agree_no, n_no, agree_no_B, n_no))

    # --- what swapping the definition does to his ladder ------------------
    rg = regrade(rows, recs, thr)
    print("\nSWAPPING THE DEFINITION INTO HIS LADDER @ thr=%.2f" % thr)
    print("   variant   S%%     S      A      C   | traded-S n  meanR   win")
    for v in ("OFF", "A", "B", "B0", "D"):
        d = rg[v]
        print("   %-7s %5.1f%% %6d %6d %6d | %6d  %+.4f  %4.1f%%"
              % (v, 100 * d["S_rate"], d["dist"].get("S", 0), d["dist"].get("A", 0),
                 d["dist"].get("C", 0), d["traded_S_n"], d["traded_S_meanR"],
                 100 * d["traded_S_win"]))

    gsep = grade_separation(rows, recs, pool, thr)
    print("\nGRADE-LEVEL SEPARATION -- day has an S-graded signal, his ladder @ thr=%.2f" % thr)
    print("   variant   his S days      his refusals    gap        Fisher p")
    for v in ("OFF", "A", "B", "B0", "D"):
        d = gsep[v]
        print("   %-7s %5.1f%% (%3d/%3d)  %5.1f%% (%3d/%3d)  %+5.1f pp   %.3f"
              % (v, 100 * d["S_rate"], d["S_hit"], d["S_n"],
                 100 * d["none_rate"], d["none_hit"], d["none_n"],
                 d["gap_pp"], d["fisher_p"]))

    report = {
        "grade_separation": gsep,
        "regrade": rg,
        "book": {"signals": len(rows), "scored": n_scored,
                 "traded": book["meta"]["traded"],
                 "first": book["meta"]["first"], "last": book["meta"]["last"]},
        "rig_validation": val,
        "threshold_used": thr,
        "trip_rates": rates,
        "rate_flags": flags,
        "separation": sep,
        "separation_sweep": {str(k): v for k, v in sweep_sep.items()},
        "money": mny,
        "his_cards": cards,
        "error_bar_R": ERROR_BAR_R,
    }
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True, default=str)
    print("\nwrote %s" % a.out)


if __name__ == "__main__":
    main()
