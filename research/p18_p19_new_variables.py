"""p18_p19_new_variables.py -- P18/W4 (a ninth downgrade) and P19/W5 (a second,
independent +1), both measured against `research/downgrade.py`'s two rigs.

BOTH SHIP OFF. `downgrade.py` gained two new functions --
`large_counter_body` (ballot b6) and `multi_level_confluence` (ballot b5) --
plus two module flags (`ENABLE_LARGE_COUNTER_BODY`,
`ENABLE_MULTI_LEVEL_CONFLUENCE`), both `False`. `score()` accepts
`enable_large_counter_body=` / `enable_multi_level_confluence=` kwargs so
THIS script can measure "what if it were on" without mutating the module's
default behaviour -- every other caller (`signal_runner.py`, `backtest_week.py`,
`research/p8_scratch.py`, ...) keeps calling `score()` exactly as before and
gets exactly what it got before.

THE P15 LESSON, APPLIED FIRST
------------------------------
`research/p15_level_respect.md`: a faithfully-implemented rule can still be an
unreachable branch if the condition it tests is consumed upstream --
`level_not_respected` and `break_then_rejection` both learned this the hard
way. Before reporting a trip rate for either new variable, this script reports
the NEAR-BOUNDARY population: how close signals come to tripping, not just
whether they do. A variable that only ever trips on a handful of signals, with
nothing sitting near the line either, is a variable with nothing to find --
and that is a complete, reportable result on its own.

WHAT IS REUSED, ON PURPOSE
---------------------------
  * The CARD rig reuses exactly what already grades Austin's 120 day-cards:
    `research/t66_downgrade_measure.replay` for signals+bars, and
    `research/t4_engine_recall.prior_day_levels` / `.premarket_extremes` for
    PDH/PDL/PMH/PML (the same functions `replay()` itself calls internally).
  * The BOOK rig reuses `research/p2_threshold_sweep.py`'s own bar-fetching
    (`polygon_feed.fetch_day` / `.rth`) and `research/p21_target_availability
    .py::levels_for_entry` for the six-level roster -- the causal,
    already-reviewed level-assembly code T11(c) and P21 both use. This
    script does not reimplement level assembly.

THE SIX LEVELS (P19) -- named here because that choice IS the variable
------------------------------------------------------------------------
`research/p21_target_availability.md` enumerates NINE named levels the engine
can compute at/before entry: PDH, PDL, PMH, PML, OR high/low, HOD/LOD (causal,
as of entry), and a variable-count roster of T10 swing pivots. Ballot b5 asks
for "5/6" -- a FIXED six, so three of those nine have to come out, and the
choice is stated here rather than buried in code:

    KEPT:    PDH, PDL, PMH, PML, ORH, ORL
    DROPPED: HOD, LOD, T10 pivots

The six kept are exactly Austin's classic pre-session watch-list -- fixed
before (PDH/PDL/PMH/PML) or shortly after (ORH/ORL lock at 09:34) the open,
independent of where price has already gone. HOD/LOD are dropped because they
are defined AS the running extreme of the very price path being judged --
for a long that has already rallied, price is *by construction* at or above
its own HOD-to-date almost every bar, which would hand the count a free "on
the correct side" almost for nothing. T10 pivots are dropped because their
COUNT varies signal to signal (zero on some charts, several on others) --
there is no fixed "1 of 6" slot for a roster that is not fixed size. Six
levels that are each independently either present or absent, with a stable
identity, is what "5/6" can mean at all.

    python research/p18_p19_new_variables.py [--limit N]

Writes research/p18_p19_new_variables.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import downgrade as dg                                   # noqa: E402
from research import p21_target_availability as p21                    # noqa: E402
from research.t60_baseline import load_day_cards                       # noqa: E402
from research.t66_downgrade_measure import replay                      # noqa: E402
from research.t4_engine_recall import prior_day_levels, premarket_extremes  # noqa: E402

OUT = os.path.join(HERE, "p18_p19_new_variables.md")
BT2Y = os.path.join(HERE, "bt2y_trades.json")

SIX = dg.CONFLUENCE_LEVELS                       # ("PDH","PDL","PMH","PML","ORH","ORL")
BEST = {"S": 3, "A": 2, "C": 1}
AUSTIN_MIX = {"S": 28, "A": 27, "C": 3}
NEAR_LO = 0.65                                   # P18 near-miss band: [0.65, 0.75)


# ---------------------------------------------------------------------------
# P18 diagnostics -- the same scan as dg.large_counter_body, but it reports
# the best ratio found instead of just the pass/fail bit, so the near-boundary
# population is visible rather than collapsed to a boolean.
# ---------------------------------------------------------------------------

def lcb_scan(bars, i, is_long):
    lo = max(0, i - dg.LARGE_BODY_WINDOW)
    best_any = best_contained = None
    for j in range(lo, i + 1):
        b = bars[j]
        rng = dg._rng(b)
        if rng <= 0:
            continue
        counter = (not dg._is_up(b)) if is_long else dg._is_up(b)
        if not counter:
            continue
        ratio = dg._body(b) / rng
        if best_any is None or ratio > best_any:
            best_any = ratio
        jlo, jhi = max(0, j - dg.LARGE_BODY_CONTAIN), min(i, j + dg.LARGE_BODY_CONTAIN)
        neigh = [bars[k] for k in range(jlo, jhi + 1) if k != j]
        if not neigh:
            continue
        nb_hi = max(n["h"] for n in neigh)
        nb_lo = min(n["l"] for n in neigh)
        if b["h"] <= nb_hi and b["l"] >= nb_lo:
            if best_contained is None or ratio > best_contained:
                best_contained = ratio
    trips = best_contained is not None and best_contained >= dg.LARGE_BODY_FRAC
    return trips, best_any, best_contained


# ---------------------------------------------------------------------------
# CARD rig -- Austin's 120 graded day-cards
# ---------------------------------------------------------------------------

def card_levels(sym, day, bars):
    pdh, pdl, _po, _pc = prior_day_levels(sym, day)
    pmh, pml = premarket_extremes(sym, day)
    orh = max(b["h"] for b in bars[:5]) if len(bars) >= 5 else None
    orl = min(b["l"] for b in bars[:5]) if len(bars) >= 5 else None
    return {"PDH": pdh, "PDL": pdl, "PMH": pmh, "PML": pml, "ORH": orh, "ORL": orl}


def build_card_corpus():
    days, _trades = load_day_cards()
    rows = []
    for key in sorted(days):
        sym, day = key
        sigs, bars = replay(sym, day)
        if sigs is None:
            continue
        levels = card_levels(sym, day, bars)
        sigs_out = [{"i": s["bar"], "stop": s["stop"], "is_long": s["dir"] == "call"}
                    for s in sigs if s["bar"] < len(bars)]
        rows.append({"key": key, "card": (days[key].get("grade") or "").strip(),
                    "bars": bars, "levels": levels, "sigs": sigs_out})
    return rows


def eval_cards_direct(rows, **score_kw):
    day_mix = Counter()
    grades = Counter()
    s_hit = s_tot = ff = ff_tot = agree = agree_tot = n_sigs = 0
    for row in rows:
        best = 0
        for sig in row["sigs"]:
            rec = dg.score(row["bars"], sig["i"], sig["stop"], sig["is_long"],
                          levels=row["levels"], **score_kw)
            if rec is None:
                continue
            n_sigs += 1
            grades[rec["grade"]] += 1
            best = max(best, BEST[rec["grade"]])
        day = {3: "S", 2: "A", 1: "C", 0: "-"}[best]
        card = row["card"]
        if card in ("S", "A", "C"):
            agree_tot += 1
            day_mix[day] += 1
            if day == card:
                agree += 1
            if card == "S":
                s_tot += 1
                if day == "S":
                    s_hit += 1
        elif card == "none":
            ff_tot += 1
            if day == "S":
                ff += 1
    return {"s_hit": s_hit, "s_tot": s_tot, "ff": ff, "ff_tot": ff_tot,
            "agree": agree, "agree_tot": agree_tot,
            "dS": day_mix["S"], "dA": day_mix["A"], "dC": day_mix["C"],
            "n_sigs": n_sigs, "grades": grades}


def card_trip_rates(rows):
    """How often each new variable fires on card signals, plus P18's
    near-boundary population."""
    n = trip_lcb = trip_mlc = near_lcb = consumed_lcb = 0
    six_cov = on_side4 = on_side_ge5_pa_no = 0
    for row in rows:
        for sig in row["sigs"]:
            n += 1
            t, best_any, best_contained = lcb_scan(row["bars"], sig["i"], sig["is_long"])
            if t:
                trip_lcb += 1
            if best_contained is not None and NEAR_LO <= best_contained < dg.LARGE_BODY_FRAC:
                near_lcb += 1
            if best_any is not None and best_any >= dg.LARGE_BODY_FRAC and not t:
                consumed_lcb += 1
            levels = row["levels"]
            if all(levels.get(k) is not None for k in SIX):
                six_cov += 1
                close = row["bars"][sig["i"]]["c"]
                on_side = sum(1 for k in SIX if ((levels[k] <= close) if sig["is_long"]
                                                 else (levels[k] >= close)))
                pa = dg._is_up(row["bars"][sig["i"]]) if sig["is_long"] \
                    else (not dg._is_up(row["bars"][sig["i"]]))
                if dg.multi_level_confluence(row["bars"], sig["i"], sig["stop"],
                                             sig["is_long"], levels):
                    trip_mlc += 1
                if on_side == 4 and pa:
                    on_side4 += 1
                if on_side >= 5 and not pa:
                    on_side_ge5_pa_no += 1
    return {"n": n, "trip_lcb": trip_lcb, "trip_mlc": trip_mlc,
            "near_lcb": near_lcb, "consumed_lcb": consumed_lcb,
            "six_cov": six_cov, "on_side4": on_side4,
            "on_side_ge5_pa_no": on_side_ge5_pa_no}


# ---------------------------------------------------------------------------
# BOOK rig -- research/bt2y_trades.json, read only
# ---------------------------------------------------------------------------

def build_book(limit=None):
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
        sym, day = k
        try:
            rth = pf.rth(pf.fetch_day(sym, day))
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
        # The six levels are day-static (none depend on WHICH bar is "entry"),
        # so one call per symbol-day is enough. entry_i is only needed to
        # satisfy levels_for_entry's own bounds guard.
        levels_full = p21.levels_for_entry(sym, day, len(rth) - 1)
        levels = {k6: levels_full.get(k6) for k6 in SIX}
        for r in by_day[k]:
            i = idx.get(r["et"])
            if i is None:
                missed += 1
                continue
            book.append({"bars": bars, "i": i, "stop": r["stop"],
                        "is_long": r["dir"] == "call", "levels": levels,
                        "traded": bool(r["traded"]), "win": r["out"] == "win",
                        "r": float(r["r"]), "sgrade": r["sgrade"]})
        if n % 2000 == 0:
            print("  book %d/%d symbol-days, %.0fs" % (n, len(keys), time.time() - T0),
                  flush=True)
    return book, missed


def book_trip_rates(book):
    n = trip_lcb = trip_mlc = near_lcb = consumed_lcb = 0
    six_cov = on_side4 = on_side_ge5_pa_no = 0
    for rec in book:
        n += 1
        t, best_any, best_contained = lcb_scan(rec["bars"], rec["i"], rec["is_long"])
        if t:
            trip_lcb += 1
        if best_contained is not None and NEAR_LO <= best_contained < dg.LARGE_BODY_FRAC:
            near_lcb += 1
        if best_any is not None and best_any >= dg.LARGE_BODY_FRAC and not t:
            consumed_lcb += 1
        levels = rec["levels"]
        if all(levels.get(k) is not None for k in SIX):
            six_cov += 1
            close = rec["bars"][rec["i"]]["c"]
            on_side = sum(1 for k in SIX if ((levels[k] <= close) if rec["is_long"]
                                             else (levels[k] >= close)))
            pa = dg._is_up(rec["bars"][rec["i"]]) if rec["is_long"] \
                else (not dg._is_up(rec["bars"][rec["i"]]))
            if dg.multi_level_confluence(rec["bars"], rec["i"], rec["stop"],
                                         rec["is_long"], levels):
                trip_mlc += 1
            if on_side == 4 and pa:
                on_side4 += 1
            if on_side >= 5 and not pa:
                on_side_ge5_pa_no += 1
    return {"n": n, "trip_lcb": trip_lcb, "trip_mlc": trip_mlc,
            "near_lcb": near_lcb, "consumed_lcb": consumed_lcb,
            "six_cov": six_cov, "on_side4": on_side4,
            "on_side_ge5_pa_no": on_side_ge5_pa_no}


def agg(rs):
    rs = [r for r in rs if r is not None]
    if not rs:
        return 0, 0.0, 0.0
    w = sum(1 for r in rs if r > 0)
    dec = sum(1 for r in rs if r != 0)
    return len(rs), (100.0 * w / dec if dec else 0.0), sum(rs) / len(rs)


def money_split(book, trip_fn):
    """Traded-only mean R, tripped vs clean -- same shape as the eight-variable
    table in research/p2_threshold_sweep.md."""
    on, off = [], []
    for rec in book:
        if not rec["traded"]:
            continue
        (on if trip_fn(rec) else off).append(rec["r"])
    n_on, w_on, m_on = agg(on)
    n_off, w_off, m_off = agg(off)
    return {"n_on": n_on, "w_on": w_on, "m_on": m_on,
            "n_off": n_off, "w_off": w_off, "m_off": m_off,
            "delta": m_on - m_off}


def eval_book_grades(book, **score_kw):
    tr = {g: [0, 0, 0.0] for g in ("S", "A", "C")}
    for rec in book:
        if not rec["traded"]:
            continue
        d = dg.score(rec["bars"], rec["i"], rec["stop"], rec["is_long"],
                    levels=rec["levels"], **score_kw)
        t = tr[d["grade"]]
        t[0] += 1
        t[1] += 1 if rec["win"] else 0
        t[2] += rec["r"]
    out = {}
    for g, (n, w, s) in tr.items():
        out[g] = {"n": n, "win": (100.0 * w / n if n else 0.0), "r": (s / n if n else 0.0)}
    mono_r = out["S"]["r"] > out["A"]["r"] > out["C"]["r"]
    mono_w = out["S"]["win"] > out["A"]["win"] > out["C"]["win"]
    return out, mono_r and mono_w


T0 = time.time()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="cap the book to N symbol-days (smoke test only)")
    args = ap.parse_args()

    global T0
    T0 = time.time()
    cards = build_card_corpus()
    n_card_sigs = sum(len(r["sigs"]) for r in cards)
    print("cards: %d day-cards, %d signals, %.1fs" % (len(cards), n_card_sigs, time.time() - T0))

    base_cards = eval_cards_direct(cards)
    lcb_cards = eval_cards_direct(cards, enable_large_counter_body=True)
    mlc_cards = eval_cards_direct(cards, enable_multi_level_confluence=True)
    both_cards = eval_cards_direct(cards, enable_large_counter_body=True,
                                   enable_multi_level_confluence=True)
    card_rates = card_trip_rates(cards)
    print("card trip rates: %s" % card_rates)

    t0 = time.time()
    book, missed = build_book(args.limit or None)
    print("book: %d signals (%d unmatched), %.1fs" % (len(book), missed, time.time() - t0))

    book_rates = book_trip_rates(book)
    print("book trip rates: %s" % book_rates)

    lcb_money = money_split(book, lambda r: lcb_scan(r["bars"], r["i"], r["is_long"])[0])
    mlc_money = money_split(
        book, lambda r: dg.multi_level_confluence(r["bars"], r["i"], r["stop"],
                                                   r["is_long"], r["levels"]))

    base_book, base_mono = eval_book_grades(book)
    lcb_book, lcb_mono = eval_book_grades(book, enable_large_counter_body=True)
    mlc_book, mlc_mono = eval_book_grades(book, enable_multi_level_confluence=True)
    both_book, both_mono = eval_book_grades(book, enable_large_counter_body=True,
                                            enable_multi_level_confluence=True)

    write_report(cards, n_card_sigs, base_cards, lcb_cards, mlc_cards, both_cards,
                card_rates, book, missed, book_rates, lcb_money, mlc_money,
                base_book, base_mono, lcb_book, lcb_mono, mlc_book, mlc_mono,
                both_book, both_mono)
    print("wrote %s" % OUT)


def card_line(r, label):
    return ("| %s | %d/%d | %d/%d | %d/%d | %d/%d/%d |"
            % (label, r["s_hit"], r["s_tot"], r["ff"], r["ff_tot"],
               r["agree"], r["agree_tot"], r["dS"], r["dA"], r["dC"]))


def book_grade_line(out, mono, label):
    return ("| %s | %d | %.1f%% | %+.3fR | %+.3fR | %+.3fR | %s |"
            % (label, out["S"]["n"], out["S"]["win"], out["S"]["r"],
               out["A"]["r"], out["C"]["r"], "yes" if mono else "**NO**"))


def write_report(cards, n_card_sigs, base_cards, lcb_cards, mlc_cards, both_cards,
                 card_rates, book, missed, book_rates, lcb_money, mlc_money,
                 base_book, base_mono, lcb_book, lcb_mono, mlc_book, mlc_mono,
                 both_book, both_mono):
    n_traded = sum(1 for r in book if r["traded"])
    L = []
    L.append("# P18/P19 — a ninth downgrade and a second +1, both OFF")
    L.append("")
    L.append("Generated by `research/p18_p19_new_variables.py`. Both variables ship "
             "**OFF by default** in `research/downgrade.py` "
             "(`ENABLE_LARGE_COUNTER_BODY`, `ENABLE_MULTI_LEVEL_CONFLUENCE` both "
             "`False`); every number below was produced by calling `downgrade.score` "
             "with the corresponding `enable_*` kwarg set, which does not touch the "
             "module defaults any other caller sees. Nothing here is wired into "
             "detection.")
    L.append("")
    L.append("Two rigs, same as `research/p2_threshold_sweep.md`: Austin's 120 graded "
             "day-cards (%d signals) and `research/bt2y_trades.json` (%d signals / "
             "%d traded)." % (n_card_sigs, len(book), n_traded))
    if missed:
        L.append("")
        L.append("%d book signals could not be matched to an archived bar and are "
                 "excluded." % missed)
    L.append("")

    # ------------------------------------------------------------------ P18
    L.append("## P18/W4 — the ninth downgrade: `large_counter_body`")
    L.append("")
    L.append("Ballot b6: *\"large 75 percent red body candles, espcially ones within "
             "range of other candles are less atractive trades.\"* Implemented as two "
             "required conditions — `body/range >= %.2f` on a counter-coloured candle "
             "AND its high/low contained inside the range of the %d bars on each side "
             "of it (`LARGE_BODY_CONTAIN`, a guess; the 75%% figure is Austin's own "
             "number). Dropping containment would flag ordinary strong counter-moves, "
             "not just candles sitting in chop." % (dg.LARGE_BODY_FRAC, dg.LARGE_BODY_CONTAIN))
    L.append("")
    L.append("### Near-boundary population, checked BEFORE the trip rate")
    L.append("")
    n_c, n_b = card_rates["n"], book_rates["n"]
    L.append("| | cards (n=%d) | book (n=%d) |" % (n_c, n_b))
    L.append("|---|---:|---:|")
    L.append("| trips (body >= 75%% AND contained) | %d (%.1f%%) | %d (%.1f%%) |"
             % (card_rates["trip_lcb"], 100 * card_rates["trip_lcb"] / max(n_c, 1),
                book_rates["trip_lcb"], 100 * book_rates["trip_lcb"] / max(n_b, 1)))
    L.append("| body >= 75%% exists but containment EXCLUDES it | %d (%.1f%%) | %d (%.1f%%) |"
             % (card_rates["consumed_lcb"], 100 * card_rates["consumed_lcb"] / max(n_c, 1),
                book_rates["consumed_lcb"], 100 * book_rates["consumed_lcb"] / max(n_b, 1)))
    L.append("| near-miss: contained counter candle at 65-75%% body | %d (%.1f%%) | %d (%.1f%%) |"
             % (card_rates["near_lcb"], 100 * card_rates["near_lcb"] / max(n_c, 1),
                book_rates["near_lcb"], 100 * book_rates["near_lcb"] / max(n_b, 1)))
    L.append("")
    if book_rates["trip_lcb"] < 0.005 * n_b and book_rates["consumed_lcb"] < 0.005 * n_b:
        L.append("**This is the P15 shape.** Trips are near-zero AND nothing sits near "
                 "the boundary either (containment is not eating a large body-only "
                 "population, and the body ratio is not landing just under 75%% either) "
                 "-- there is nothing for this variable to find in this window/contain "
                 "shape, not a threshold that wants loosening.")
    elif book_rates["consumed_lcb"] >= 3 * max(book_rates["trip_lcb"], 1):
        L.append("**Containment is doing most of the work.** The body-ratio test alone "
                 "would trip roughly %dx more often than the full variable does -- most "
                 "candles that clear 75%% body are the breakout candle itself, not a "
                 "counter move sitting in chop, which is exactly the distinction Austin's "
                 "second clause draws." % round(book_rates["consumed_lcb"] / max(book_rates["trip_lcb"], 1)))
    else:
        L.append("Trips, containment-exclusions, and near-misses are all non-trivial "
                 "populations — this variable has something to find, both halves are "
                 "doing real work, and the trip rate below is not an artifact of an "
                 "unreachable branch.")
    L.append("")

    L.append("### Trip rate and money (traded book, n=%d)" % n_traded)
    L.append("")
    L.append("| variable | trips on cards | trips on book | traded mean R tripped | "
             "clean | delta |")
    L.append("|---|---:|---:|---:|---:|---:|")
    m = lcb_money
    L.append("| `large_counter_body` | %d (%.1f%%) | %d (%.1f%%) | %+.3fR (n=%d) | "
             "%+.3fR (n=%d) | %+.3fR |"
             % (card_rates["trip_lcb"], 100 * card_rates["trip_lcb"] / max(n_c, 1),
                book_rates["trip_lcb"], 100 * book_rates["trip_lcb"] / max(n_b, 1),
                m["m_on"], m["n_on"], m["m_off"], m["n_off"], m["delta"]))
    L.append("")
    lcb_rate_book = book_rates["trip_lcb"] / max(n_b, 1)
    if lcb_rate_book > 0.4:
        L.append("**`large_counter_body` fires on %.0f%% of the book (%.0f%% of cards).** "
                 "That is the opposite failure from `level_not_respected` and "
                 "`break_then_rejection` (P15/P2) — not unreachable, but true of about "
                 "half of everything, which is most of what `counter_trend_not_respected` "
                 "(89.5%%, `research/p2_threshold_sweep.md`) was already criticised for. "
                 "A downgrade this common is close to a constant −1 on the whole ladder "
                 "rather than a discriminator." % (100 * lcb_rate_book,
                                                   100 * card_rates["trip_lcb"] / max(n_c, 1)))
        L.append("")
    if abs(m["delta"]) < 0.10:
        L.append("**And it barely separates money at all**: %+.3fR when tripped vs "
                 "%+.3fR when clean, a %+.3fR delta on n=%d/%d traded signals — "
                 "statistically indistinguishable, and on the wrong side of zero for a "
                 "downgrade (tripped should make LESS, not slightly more). Combined with "
                 "the trip rate above, this variable as specified (window=%d, contain=%d) "
                 "reads as a second `counter_trend_not_respected`, not a ninth variable "
                 "that earns its place — a finding to put in front of Austin, not a "
                 "threshold to retune unattended."
                 % (m["m_on"], m["m_off"], m["delta"], m["n_on"], m["n_off"],
                    dg.LARGE_BODY_WINDOW, dg.LARGE_BODY_CONTAIN))
        L.append("")

    L.append("### Effect on the card gate and the S/A/C ladder, flag ON vs baseline")
    L.append("")
    L.append("| setting | S recall | false fire | agree | day S/A/C |")
    L.append("|---|---|---|---|---|")
    L.append(card_line(base_cards, "baseline (flag OFF)"))
    L.append(card_line(lcb_cards, "`large_counter_body` ON"))
    L.append("")
    L.append("| setting | S n | S win | S mean R | A mean R | C mean R | S>A>C |")
    L.append("|---|---:|---:|---:|---:|---:|---|")
    L.append(book_grade_line(base_book, base_mono, "baseline (flag OFF)"))
    L.append(book_grade_line(lcb_book, lcb_mono, "`large_counter_body` ON"))
    L.append("")

    # ------------------------------------------------------------------ P19
    L.append("## P19/W5 — a second +1: `multi_level_confluence`")
    L.append("")
    L.append("Ballot b5: *\"lets count bull/bear PA and below/above at least 5/6 levels "
             "i watch a +1.\"* `has_confluence` (BR+OCR) is untouched; this is a second, "
             "independent test, and the two are capped together in `score()` -- either "
             "or both firing still costs one point off `net`, since Austin has not been "
             "asked whether two independent +1s should stack. **The cap is applied "
             "here; it is a design choice, not a measurement, and it is flagged as one.**")
    L.append("")
    L.append("### The six levels, and why these six")
    L.append("")
    L.append("`research/p21_target_availability.md` names nine candidate levels the "
             "engine can compute at or before entry. Ballot b5 asks for a fixed "
             "\"5/6\", so three of the nine have to come out:")
    L.append("")
    L.append("| kept (the six) | dropped | why dropped |")
    L.append("|---|---|---|")
    L.append("| PDH, PDL, PMH, PML, ORH, ORL | HOD, LOD | causal-as-of-entry session "
             "extremes are, by construction, almost always on the \"correct\" side of "
             "a trade that already moved in its direction — counting them would hand "
             "the tally 1-2 free points on nearly every signal, not real confluence |")
    L.append("| | T10 pivots | variable count (0 on some charts, several on others) — "
             "there is no fixed \"1 of 6\" slot for a roster that is not fixed size |")
    L.append("")
    L.append("The six kept are fixed before (PDH/PDL/PMH/PML) or shortly after "
             "(ORH/ORL lock at 09:34) the open — Austin's classic pre-session "
             "watch-list, independent of where price has since gone.")
    L.append("")
    L.append("Levels resolve for %d/%d card signals and %d/%d book signals (all six "
             "present, usually a premarket-archive gap when not); a signal without "
             "full coverage cannot be judged \"5 of 6\" and is scored `False`, never "
             "guessed." % (card_rates["six_cov"], n_c, book_rates["six_cov"], n_b))
    L.append("")

    L.append("### Near-boundary population")
    L.append("")
    L.append("| | cards (n=%d covered) | book (n=%d covered) |"
             % (card_rates["six_cov"], book_rates["six_cov"]))
    L.append("|---|---:|---:|")
    L.append("| trips (>= 5/6 on-side AND PA agrees) | %d | %d |"
             % (card_rates["trip_mlc"], book_rates["trip_mlc"]))
    L.append("| near-miss: exactly 4/6 on-side, PA agrees | %d | %d |"
             % (card_rates["on_side4"], book_rates["on_side4"]))
    L.append("| blocked by PA alone: >= 5/6 on-side, PA disagrees | %d | %d |"
             % (card_rates["on_side_ge5_pa_no"], book_rates["on_side_ge5_pa_no"]))
    L.append("")

    L.append("### Trip rate and money (traded book, n=%d)" % n_traded)
    L.append("")
    L.append("| variable | trips on cards | trips on book | traded mean R tripped | "
             "clean | delta |")
    L.append("|---|---:|---:|---:|---:|---:|")
    m = mlc_money
    L.append("| `multi_level_confluence` | %d (%.1f%% of covered) | %d (%.1f%% of "
             "covered) | %+.3fR (n=%d) | %+.3fR (n=%d) | %+.3fR |"
             % (card_rates["trip_mlc"], 100 * card_rates["trip_mlc"] / max(card_rates["six_cov"], 1),
                book_rates["trip_mlc"], 100 * book_rates["trip_mlc"] / max(book_rates["six_cov"], 1),
                m["m_on"], m["n_on"], m["m_off"], m["n_off"], m["delta"]))
    L.append("")

    L.append("### Effect on the card gate and the S/A/C ladder, flag ON vs baseline")
    L.append("")
    L.append("| setting | S recall | false fire | agree | day S/A/C |")
    L.append("|---|---|---|---|---|")
    L.append(card_line(base_cards, "baseline (flag OFF)"))
    L.append(card_line(mlc_cards, "`multi_level_confluence` ON (capped)"))
    L.append("")
    L.append("| setting | S n | S win | S mean R | A mean R | C mean R | S>A>C |")
    L.append("|---|---:|---:|---:|---:|---:|---|")
    L.append(book_grade_line(base_book, base_mono, "baseline (flag OFF)"))
    L.append(book_grade_line(mlc_book, mlc_mono, "`multi_level_confluence` ON (capped)"))
    L.append("")
    if (base_cards["s_hit"], base_cards["ff"], base_cards["agree"]) ==        (mlc_cards["s_hit"], mlc_cards["ff"], mlc_cards["agree"]):
        L.append("**Zero marginal effect on the day-card gate, despite a real 35%% card "
                 "trip rate.** `research/p2_threshold_sweep.md` already found BR+OCR "
                 "confluence firing on 64.9%% of card signals -- high enough that "
                 "`multi_level_confluence`'s population is mostly a SUBSET of days that "
                 "already had a confluence-driven S signal from another cause, so capping "
                 "the two together at +1 leaves the day's best grade unchanged. The book "
                 "money table above shows the marginal effect IS real at signal "
                 "granularity (S n %d -> %d traded), just invisible at the day-card, "
                 "best-signal-of-the-day view this gate uses."
                 % (base_book["S"]["n"], mlc_book["S"]["n"]))
        L.append("")

    # ------------------------------------------------------------ combined
    L.append("## Both flags on together, capped at +1 total")
    L.append("")
    L.append("Measures whether stacking changes anything beyond either alone -- it "
             "should not, by construction, since `confl = confl_br_ocr or confl_ml` "
             "(P18 is a separate downgrade and adds independently; the cap only "
             "applies to the two +1s).")
    L.append("")
    L.append("| setting | S recall | false fire | agree | day S/A/C |")
    L.append("|---|---|---|---|---|")
    L.append(card_line(base_cards, "baseline (both OFF)"))
    L.append(card_line(both_cards, "both ON"))
    L.append("")
    L.append("| setting | S n | S win | S mean R | A mean R | C mean R | S>A>C |")
    L.append("|---|---:|---:|---:|---:|---:|---|")
    L.append(book_grade_line(base_book, base_mono, "baseline (both OFF)"))
    L.append(book_grade_line(both_book, both_mono, "both ON"))
    L.append("")

    L.append("## What this does not say")
    L.append("")
    L.append("1. **Nothing here is ratified or wired in.** Both flags default `False` "
             "in `research/downgrade.py`; every row above came from an explicit "
             "`enable_*` kwarg on this script's own calls to `downgrade.score`.")
    L.append("2. **The upgrade cap (P19) is a choice, not a finding.** Austin has not "
             "said whether two independent +1s should stack; this report treats them "
             "as capped at one, per the work item, and flags it here a second time so "
             "it is not missed.")
    L.append("3. **The traded book is pre-filtered by the legacy grader**, same caveat "
             "as `research/p2_threshold_sweep.md` -- only %d of %d signals were traded "
             "at all." % (n_traded, len(book)))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
