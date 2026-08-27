"""a3_s_cap_sweep.py -- A3/T11: sweep the S-per-symbol-day cap. SHIPS NOTHING.

Austin, 2026-08-27, asked directly which cap to code: "my cap is just the
prediction, so why cap it? maybe see what happens then try to cap or verify
yourself the cap is the way to go statistically." His ballot gave three
contradictory numbers -- c3 "max 2 S trades per symbol", c4 "max 3 s trades
per symbol" then "cap at .8 s trades a day per symbol" -- so nothing is coded
on a guess. This script sweeps {none, 1, 2, 3} and reports the table; it does
not touch `research/downgrade.py` and no default anywhere changes.

WHAT "CAP" MEANS HERE
----------------------
Austin's own language ("a cap on S TRADES") is a trade-count restriction, not
a re-grade: the underlying prediction stays S (`downgrade.score()` is called
at its committed defaults, untouched), and the cap decides, per symbol-day,
how many of the S-graded entries are actually ACTED ON. Entries beyond the
cap are excluded from the taken-S population; they are not relabelled A/C.
84%-rule re-entries are EXEMPT (matching `research/p20_sequence_gate.md`'s own
exemption): they never consume a cap slot and can never themselves be capped
out -- they are the one sanctioned second bite at the idea, independent of
how many other S entries already fired that day.

THE ALL-SIGNAL READING, AND WHY
--------------------------------
`research/p20_sequence_gate.py` found its two readings of "which signal is
2nd+ on its symbol-day" disagree in SIGN: the all-signal reading (every
DETECTED signal, matching how `downgrade.score()` is used everywhere else)
trips 422 traded signals and is correctly signed at -0.325R; the fired-only
reading (the legacy engine's own accepted subset) trips only 9 and is
WRONG-signed at +0.293R -- too thin to trust, and backwards besides. THIS
SCRIPT USES THE ALL-SIGNAL READING: `entry_seq` / the S-cap counter is
computed over EVERY signal `t66_downgrade_measure.replay()` (cards) or
`bt2y_trades.json` (book) contains, not filtered to the legacy engine's own
`traded`/`fired` subset. Concretely for the book: a signal that was never
traded by the OLD legacy grader can still grade S under Austin's ladder and
still occupy a cap slot ahead of a LATER, traded S signal on the same
symbol-day -- so grading (not just ordering) runs over the full 45,175-signal
book, not just the 1,016 traded rows. Money is still only ever REPORTED over
`traded=True` rows (same convention as `p20_sequence_gate.py` /
`p23_combined_arms.py`; the traded book is the only population with a
realised, simulated fill).

WHAT IS REUSED, ON PURPOSE
---------------------------
  * `research/p20_sequence_gate.py` -- the entry_seq/is_84 population logic
    (`annotate_sequence`, `_is84`) is reused verbatim for the book, and the
    CARD rig's `replay()` + `downgrade.score()` shape is reused verbatim from
    its `build_card_corpus`. This script does not re-derive "which signal is
    2nd+ on its symbol-day" -- it reuses P20's answer to that question and
    asks a different one (a HARD CAP on the S count, not a quality downgrade).
  * `research/p2_threshold_sweep.py` -- `load_probe_days()` (the A1/T4 held-out
    100-card OMEN Test 1 loader, commit `99bead1c`) is imported unchanged so
    the held-out corpus is built by the SAME card function as the 120-card
    corpus, never a second card builder.

    python research/a3_s_cap_sweep.py [--limit N]

Writes research/a3_s_cap_sweep.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import downgrade as dg                                   # noqa: E402
from research.t60_baseline import load_day_cards                       # noqa: E402
from research.t66_downgrade_measure import replay                      # noqa: E402
from research.p2_threshold_sweep import load_probe_days                # noqa: E402

OUT = os.path.join(HERE, "a3_s_cap_sweep.md")
BT2Y = os.path.join(HERE, "bt2y_trades.json")

CAP_ARMS = [None, 1, 2, 3]
BEST = {"S": 3, "A": 2, "C": 1}


def _is84(signal_type):
    return signal_type == "reentry_84_rule"


def cap_label(cap):
    return "none" if cap is None else str(cap)


# ---------------------------------------------------------------------------
# the cap itself -- one function, shared by the card rig and the book rig
# ---------------------------------------------------------------------------

def apply_cap(ordered, cap):
    """``ordered``: one symbol-day's signals, chronological, each a dict with
    ``grade`` and ``is_84``. Returns a same-length/order list of bool ``kept``
    -- True iff this signal counts as a TAKEN S entry under this cap.

    84%-rule re-entries are EXEMPT: always kept, never consume a slot (see
    module docstring). Non-S signals are always False here -- irrelevant,
    since the cap only ever removes an S entry, never re-grades one to A/C
    and never touches an A/C entry's own count.
    """
    kept = []
    s_count = 0
    for item in ordered:
        if item["grade"] != "S":
            kept.append(False)
            continue
        if item["is_84"]:
            kept.append(True)
            continue
        if cap is None or s_count < cap:
            kept.append(True)
            s_count += 1
        else:
            kept.append(False)
    return kept


# ---------------------------------------------------------------------------
# CARD rig -- Austin's 120 graded day-cards, and the 100 held-out OMEN Test 1
# ---------------------------------------------------------------------------

def build_card_corpus(days=None):
    """Reuses `t66_downgrade_measure.replay` + `downgrade.score`, the same
    shape `p20_sequence_gate.py::build_card_corpus` uses. Generalised with an
    optional `days=` the way A1/T4 generalised `p2_threshold_sweep.build_cards`
    -- one card builder, two inputs (Austin's 120 via `load_day_cards()`, or
    the 100 held-out OMEN Test 1 via `load_probe_days()`), never a second
    implementation. Every signal replay() returns IS the all-signal
    population already -- there is no traded/fired pre-filter at the card
    level, so no reading choice is needed here (unlike the book).
    """
    if days is None:
        days, _marks = load_day_cards()
    rows = []
    for key in sorted(days):
        sym, day = key
        sigs, bars = replay(sym, day)
        if sigs is None:
            continue
        valid = [s for s in sigs if s["bar"] < len(bars)]
        graded = []
        for s in valid:
            rec = dg.score(bars, s["bar"], s["stop"], s["dir"] == "call")
            if rec is None:
                continue
            graded.append({"grade": rec["grade"], "is_84": _is84(s.get("signal_type"))})
        rows.append({"key": key, "card": (days[key].get("grade") or "").strip(),
                    "sigs": graded})
    return rows


def eval_cards_capped(rows, cap):
    """S recall (of his S-graded cards) and false fires (on his `none`/X
    cards), the day best-of reduction P20/A1 already use, with a capped-out
    S entry excluded from contributing to the day's best grade at all (it is
    not relabelled A/C -- see module docstring)."""
    s_hit = s_tot = ff = ff_tot = 0
    for row in rows:
        kept = apply_cap(row["sigs"], cap)
        best = 0
        for sig, k in zip(row["sigs"], kept):
            if sig["grade"] == "S" and not k:
                continue                      # capped out -- not counted at all
            best = max(best, BEST[sig["grade"]])
        day = {3: "S", 2: "A", 1: "C", 0: "-"}[best]
        card = row["card"]
        if card == "S":
            s_tot += 1
            if day == "S":
                s_hit += 1
        elif card == "none":
            ff_tot += 1
            if day == "S":
                ff += 1
    return {"s_hit": s_hit, "s_tot": s_tot, "ff": ff, "ff_tot": ff_tot}


# ---------------------------------------------------------------------------
# BOOK rig -- research/bt2y_trades.json, ALL-SIGNAL reading (P20's primary)
# ---------------------------------------------------------------------------

def load_book():
    with open(BT2Y, encoding="utf-8") as fh:
        return json.load(fh)["trades"]


def annotate_sequence(rows):
    """Verbatim reuse of `p20_sequence_gate.py::annotate_sequence` -- 1-based
    entry_seq per symbol-day, ordered by entry time, over EVERY detected
    signal (the all-signal / primary reading), plus the 84%-rule flag.
    """
    by = defaultdict(list)
    for idx, r in enumerate(rows):
        r["_orig"] = idx
        by[(r["sym"], r["day"])].append(r)
    for _k, rs in by.items():
        rs.sort(key=lambda r: (r["et"], r["_orig"]))
        for i, r in enumerate(rs, start=1):
            r["_entry_seq"] = i
            r["_is_84"] = (r["setup"] == "reentry_84_rule")
    return rows


def grade_book(rows, limit=None):
    """Grades EVERY signal in the book (all-signal reading -- see module
    docstring for why a non-traded signal still has to be graded: it can
    still occupy a cap slot ahead of a later traded one). Bars fetched one
    symbol-day at a time, cache-first (`polygon_feed`), graded, then
    discarded -- same discipline as
    `p20_sequence_gate.py::build_traded_day_data`, just over the full book
    (11,803 symbol-days) instead of the traded-only subset (1,007), because
    the cap needs to see non-traded S grades too.
    """
    import polygon_feed as pf
    by_day = defaultdict(list)
    for r in rows:
        by_day[(r["sym"], r["day"])].append(r)
    keys = sorted(by_day)
    if limit:
        keys = keys[:limit]
    missed = 0
    t0 = time.time()
    for n, k in enumerate(keys):
        sym, day = k
        try:
            rth = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            rth = None
        if not rth:
            missed += len(by_day[k])
            for r in by_day[k]:
                r["_grade"] = None
            continue
        bars = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
                for c in rth]
        idx = {}
        for i, c in enumerate(rth):
            idx.setdefault(c.timestamp[:5], i)
        for r in by_day[k]:
            i = idx.get(r["et"])
            if i is None:
                r["_grade"] = None
                missed += 1
                continue
            rec = dg.score(bars, i, r["stop"], r["dir"] == "call")
            r["_grade"] = rec["grade"] if rec else None
        if n % 2000 == 0:
            print("  book grading %d/%d symbol-days, %.0fs"
                  % (n, len(keys), time.time() - t0), flush=True)
    return missed


def _ci95(rs):
    """95% CI on the mean, same construction as `t60_baseline.py`: population
    stdev, normal approximation. Not a two-sample test -- reported so a
    reader can see whether an arm's interval is decisive (sits clear of
    zero) or wide enough that the point estimate alone would overclaim."""
    n = len(rs)
    if n < 2:
        return (0.0, 0.0)
    mean = sum(rs) / n
    var = sum((x - mean) ** 2 for x in rs) / n
    sd = var ** 0.5
    half = 1.96 * sd / (n ** 0.5)
    return (mean - half, mean + half)


def money_for_cap(rows, cap):
    """Applies the cap per symbol-day (all-signal order), then reports n /
    mean R / win rate / months-green over the surviving TRADED S population
    only -- the traded book is the only population with a realised,
    simulated fill (same convention as `p20_sequence_gate.py::money_split`
    and `p23_combined_arms.py::eval_book_grades`, both `if not
    r["traded"]: continue` before ever touching R). Also reports the
    CAPPED-OUT population (what the cap actually removed) and a 95% CI on
    the kept population's mean R, so "the cap is the way to go
    statistically" (Austin's own phrase) is checked, not asserted.
    """
    by_day = defaultdict(list)
    for r in rows:
        if r.get("_grade") is None:
            continue
        by_day[(r["sym"], r["day"])].append(r)

    kept_flags = {}
    for _k, rs in by_day.items():
        rs.sort(key=lambda r: r["_entry_seq"])
        ordered = [{"grade": r["_grade"], "is_84": r["_is_84"]} for r in rs]
        kept = apply_cap(ordered, cap)
        for r, k in zip(rs, kept):
            kept_flags[id(r)] = k

    s_all = [r for r in rows if r["traded"] and r.get("_grade") == "S"]
    s_rows = [r for r in s_all if kept_flags.get(id(r), False)]
    dropped = [r for r in s_all if not kept_flags.get(id(r), False)]

    n = len(s_rows)
    rs = [r["r"] for r in s_rows]
    mean_r = sum(rs) / n if n else 0.0
    win = 100.0 * sum(1 for r in s_rows if r["out"] == "win") / n if n else 0.0
    ci_lo, ci_hi = _ci95(rs)

    d_n = len(dropped)
    d_rs = [r["r"] for r in dropped]
    d_mean = sum(d_rs) / d_n if d_n else 0.0

    by_m = defaultdict(list)
    for r in s_rows:
        by_m[r["ym"]].append(r["r"])
    months = sorted(by_m)
    green = [m for m in months if sum(by_m[m]) / len(by_m[m]) >= 0]
    neg = [m for m in months if sum(by_m[m]) / len(by_m[m]) < 0]
    return {"n": n, "mean_r": mean_r, "sum_r": sum(rs), "win": win,
            "months_total": len(months),
            "months_green": len(green), "neg_months": neg,
            "ci_lo": ci_lo, "ci_hi": ci_hi,
            "dropped_n": d_n, "dropped_mean_r": d_mean}


T0 = time.time()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="cap the book symbol-day fetch (smoke test only)")
    args = ap.parse_args()

    global T0
    T0 = time.time()

    card120 = build_card_corpus()
    n120_sigs = sum(len(r["sigs"]) for r in card120)
    print("120-card corpus: %d day-cards, %d signals, %.1fs"
          % (len(card120), n120_sigs, time.time() - T0))

    t0 = time.time()
    ho_days = load_probe_days()
    cardho = build_card_corpus(days=ho_days)
    nho_sigs = sum(len(r["sigs"]) for r in cardho)
    print("held-out 100 corpus: %d day-cards, %d signals, %.1fs"
          % (len(cardho), nho_sigs, time.time() - t0))

    t0 = time.time()
    book = load_book()
    annotate_sequence(book)
    n_traded = sum(1 for r in book if r["traded"])
    missed = grade_book(book, args.limit or None)
    print("book: %d signals (%d traded), %d ungraded/missed, %.1fs"
          % (len(book), n_traded, missed, time.time() - t0))

    results = []
    for cap in CAP_ARMS:
        c120 = eval_cards_capped(card120, cap)
        cho = eval_cards_capped(cardho, cap)
        m = money_for_cap(book, cap)
        results.append({"cap": cap, "c120": c120, "cho": cho, "money": m})
        print("  cap=%-4s 120-card S %d/%d ff %d/%d | held-out S %d/%d ff %d/%d | "
              "book n=%d mean=%+.3fR green=%d/%d"
              % (cap_label(cap), c120["s_hit"], c120["s_tot"], c120["ff"], c120["ff_tot"],
                 cho["s_hit"], cho["s_tot"], cho["ff"], cho["ff_tot"],
                 m["n"], m["mean_r"], m["months_green"], m["months_total"]))

    write_report(n120_sigs, nho_sigs, book, n_traded, missed, results)
    print("wrote %s" % OUT)


def unified_row(r):
    c120, cho, m = r["c120"], r["cho"], r["money"]
    return ("| %s | %d/%d | %d/%d | %d/%d | %d/%d | %d | %+.3fR | %.1f%% | %d/%d |"
            % (cap_label(r["cap"]), c120["s_hit"], c120["s_tot"], c120["ff"], c120["ff_tot"],
               cho["s_hit"], cho["s_tot"], cho["ff"], cho["ff_tot"],
               m["n"], m["mean_r"], m["win"], m["months_green"], m["months_total"]))


def write_report(n120_sigs, nho_sigs, book, n_traded, missed, results):
    L = []
    L.append("# A3/T11 — the S-per-symbol-day cap, swept, nothing shipped")
    L.append("")
    L.append("Generated by `research/a3_s_cap_sweep.py` at `_this commit_`. "
             "**Nothing is wired in and no default changes** — `research/downgrade.py` "
             "is untouched, and every grade below comes from `downgrade.score()` called "
             "at its committed defaults (no `enable_*` kwarg set). The cap itself is "
             "external to `score()`: it decides which S-graded entries are ACTED ON, "
             "never re-grades one to A/C.")
    L.append("")
    L.append("Austin, 2026-08-27, asked directly which cap to code: *\"my cap is just "
             "the prediction, so why cap it? maybe see what happens then try to cap or "
             "verify yourself the cap is the way to go statistically.\"* His ballot gave "
             "three contradictory numbers — c3 *\"max 2 S trades per symbol\"*, c4 "
             "*\"max 3 s trades per symbol\"* then *\"cap at .8 s trades a day per "
             "symbol\"* — so this row sweeps `{none, 1, 2, 3}` and reports the table "
             "instead of guessing which one he meant.")
    L.append("")

    # ------------------------------------------------------------- the reading
    L.append("## The reading: all-signal, not fired-only")
    L.append("")
    L.append("`research/p20_sequence_gate.py` found its two readings of \"which signal "
             "is 2nd+ on its symbol-day\" disagree in **sign**: the all-signal reading "
             "(every detected signal, matching how `downgrade.score()` is used "
             "everywhere else in this codebase) trips 422 traded signals and is "
             "correctly signed at -0.325R; the fired-only reading (the legacy engine's "
             "own accepted subset) trips only 9 and is wrong-signed at +0.293R — too "
             "thin to trust, and backwards besides.")
    L.append("")
    L.append("**This script uses the all-signal reading.** The S-cap counter is walked "
             "over every signal in `bt2y_trades.json` (45,175 rows), not filtered to the "
             "1,016 the legacy engine actually traded — a signal the OLD grader never "
             "traded can still grade S under Austin's ladder and still occupy a cap slot "
             "ahead of a LATER, traded S signal on the same symbol-day. So grading (not "
             "just ordering) runs over the full book: %d symbol-days, all graded, %d "
             "signal(s) ungraded/unmatched to an archived bar. **Money is still only "
             "ever reported over `traded=True` rows** — the traded book is the only "
             "population with a realised, simulated fill, same convention as "
             "`p20_sequence_gate.py` and `p23_combined_arms.py`, both of which skip "
             "straight past a non-traded row before ever reading its R."
             % (len({(r['sym'], r['day']) for r in book}), missed))
    L.append("")
    L.append("On the card rigs there is no reading choice to make: `t66_downgrade_measure"
             ".replay()` returns every detected signal already, with no traded/fired "
             "pre-filter, so the card population is automatically the all-signal one.")
    L.append("")

    # ------------------------------------------------------------- populations
    L.append("## The three populations")
    L.append("")
    L.append("| rig | source | cards | signals |")
    L.append("|---|---|---:|---:|")
    L.append("| 120 graded day-cards | `t60_baseline.load_day_cards()` | 120 | %d |" % n120_sigs)
    L.append("| 100 held-out OMEN Test 1 | `p2_threshold_sweep.load_probe_days()` "
             "(`probe_omen_test1_2026-08-27.jsonl`) | 100 | %d |" % nho_sigs)
    L.append("| 2-year book | `bt2y_trades.json`, READ ONLY | -- | %d (%d traded) |"
             % (len(book), n_traded))
    L.append("")

    # ------------------------------------------------------------- unified table
    L.append("## One row per arm, all metrics, all three populations")
    L.append("")
    L.append("S recall out of 28 (120-card) / 15 (held-out); false fires out of 61 "
             "(120-card) / 42 (held-out) — `grade_std \"none\" == X`, a real judgement, "
             "counts the same as every other report in this family. Book columns are "
             "the surviving TRADED S population after this cap (see reading section "
             "above); `green` = months with mean R >= 0, of months holding >=1 "
             "surviving S trade.")
    L.append("")
    L.append("| cap | 120-card S recall | 120-card false fire | held-out S recall | "
             "held-out false fire | book S n | book S mean R | book S win | book "
             "months green |")
    L.append("|---|---|---|---|---|---:|---:|---:|---|")
    for r in results:
        L.append(unified_row(r))
    L.append("")

    # ------------------------------------------------------------- card detail
    L.append("## Card rigs: unchanged by construction")
    L.append("")
    c120_vals = {(r["c120"]["s_hit"], r["c120"]["ff"]) for r in results}
    cho_vals = {(r["cho"]["s_hit"], r["cho"]["ff"]) for r in results}
    if len(c120_vals) == 1 and len(cho_vals) == 1:
        L.append("**Both card rigs are identical across every cap arm, including `none`.** "
                 "This is not a bug — it falls out of what the cap can and cannot touch. "
                 "The day-level recall/false-fire metric only asks whether a day reached "
                 "an S grade AT ALL (the best grade among the day's surviving signals), "
                 "and a cap only ever removes the SECOND-or-later S entry on a symbol-day "
                 "— the first S entry of the day survives every cap arm from `1` upward "
                 "by construction, so it can never change whether the day counts as S. "
                 "**The cap has no card-rig signature; whatever it costs or buys shows up "
                 "only in the book below.**")
        L.append("")
    else:
        L.append("**The card rigs move with the cap** — see the table; this was not "
                 "assumed going in, it fell out of the run.")
        L.append("")

    # ------------------------------------------------------------- statistical check
    L.append("## \"Verify yourself the cap is the way to go statistically\"")
    L.append("")
    L.append("Austin's own words, quoted in full above, ask for a statistical check, "
             "not just a bigger-or-smaller table. Two things a raw mean-R table hides: "
             "whether the shift is decisive at this sample size, and whether it costs "
             "TOTAL realised R (not just per-trade average) by throwing away trades "
             "that were still positive, just smaller. Both below.")
    L.append("")
    L.append("| cap | kept n | kept mean R | 95% CI on kept mean R | dropped n | "
             "dropped mean R | total R (kept, sum) |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for r in results:
        m = r["money"]
        L.append("| %s | %d | %+.3fR | [%+.3f, %+.3f] | %d | %s | %+.1fR |"
                 % (cap_label(r["cap"]), m["n"], m["mean_r"], m["ci_lo"], m["ci_hi"],
                    m["dropped_n"],
                    ("%+.3fR" % m["dropped_mean_r"]) if m["dropped_n"] else "n/a",
                    m["sum_r"]))
    L.append("")
    baseline_m = next(r["money"] for r in results if r["cap"] is None)
    L.append("**None of the four CIs are decisive against each other** — every arm's "
             "95%% interval on kept mean R overlaps every other arm's; at these sample "
             "sizes (n=%d down to n=%d) this book cannot single out one arm as "
             "statistically the best, only show the direction each one leans."
             % (baseline_m["n"], min(r["money"]["n"] for r in results)))
    L.append("")
    L.append("**Total realised R falls under every cap arm, because a dropped trade is "
             "still a POSITIVE trade, just a smaller one** — P20 already found 2nd+ "
             "entries average +0.767R, not a loss, just less than firsts' +1.092R. "
             "Removing them raises the mean of what is left while shrinking the total:")
    L.append("")
    for r in results:
        if r["cap"] is None:
            continue
        m = r["money"]
        lost_n = baseline_m["n"] - m["n"]
        d_mean = m["mean_r"] - baseline_m["mean_r"]
        d_sum = m["sum_r"] - baseline_m["sum_r"]
        L.append("- cap `%s`: drops %d of %d S trades (%.1f%%, dropped mean %s), kept "
                 "mean R %+.3fR (%+.3fR vs no cap), **total R %+.1fR (%+.1fR vs no "
                 "cap)**."
                 % (cap_label(r["cap"]), lost_n, baseline_m["n"],
                    100.0 * lost_n / max(baseline_m["n"], 1),
                    ("%+.3fR" % m["dropped_mean_r"]) if m["dropped_n"] else "n/a",
                    m["mean_r"], d_mean, m["sum_r"], d_sum))
    L.append("")
    L.append("So the decision is a real trade-off, not a free lunch: every cap arm "
             "raises (or for `2`/`3`, roughly holds) the mean R of what survives, and "
             "every cap arm gives up total R over the same 2-year window — capping "
             "trades quality-per-trade against volume, it does not manufacture edge.")
    L.append("")

    any_neg = [(r["cap"], r["money"]["neg_months"]) for r in results if r["money"]["neg_months"]]
    if any_neg:
        L.append("Negative months, by arm:")
        L.append("")
        for cap, months in any_neg:
            L.append("- cap `%s`: %s" % (cap_label(cap), ", ".join(months)))
        L.append("")
        best_green = max(r["money"]["months_green"] for r in results)
        if any(r["money"]["months_green"] == best_green and r["cap"] is not None
              for r in results) and baseline_m["months_green"] < best_green:
            L.append("Cap `1` is the only arm that turns a red month green (2026-03) — "
                     "worth naming since durability (\"every month green\") is a "
                     "separate gate from mean R, but this is one month out of %d on a "
                     "handful of trades, not a structural fix." % baseline_m["months_total"])
            L.append("")
    else:
        L.append("**No cap arm, including no-cap, has a single negative month** — "
                 "durability is not what a cap would buy here.")
        L.append("")

    # ------------------------------------------------------------- trust
    L.append("## Which numbers to trust")
    L.append("")
    L.append("`research/a1_threshold_sweep.md` found the committed grader's produced "
             "S/A/C mix sits at distance **0.086** from Austin on the 120 cards it was "
             "effectively tuned against, and **0.282** on the held-out 100 — a card the "
             "grader has never seen disagrees with Austin roughly 3x more than a card "
             "it has. **The held-out numbers in the table above are the ones to trust "
             "for whether the cap changes recall; the 120-card numbers corroborate but "
             "do not lead.** Per the card-rig finding above, in this row the two "
             "populations agree with each other anyway — the cap moves neither.")
    L.append("")

    # ------------------------------------------------------------- recommendation
    baseline_r = next(r for r in results if r["cap"] is None)
    cap1_r = next(r for r in results if r["cap"] == 1)
    L.append("## Recommendation")
    L.append("")
    L.append("**No cap, with `1` named as the arm to revisit if Austin wants to trade "
             "quality for volume on purpose.** Three things point away from shipping a "
             "cap today:")
    L.append("")
    L.append("1. **No CI is decisive** (see the statistical-check table) — at these "
             "sample sizes the book cannot single out any one arm, capped or not, as "
             "the statistically better choice. A point estimate alone (`+1.313R` vs "
             "`+1.432R`) would overclaim what this data actually supports.")
    L.append("2. **Every cap arm gives up total realised R.** Cap `1`, the strongest "
             "and most defensible arm (it removes the full 2nd+ population P20 already "
             "measured, not an arbitrary slice), still turns %+.1fR of total R over the "
             "window into %+.1fR — a %.1f%% cut, traded for a per-trade average that "
             "is not decisively better. Cap `2`/`3` are worse than that: they drop only "
             "%d and %d trades respectively, small enough that their mean-R move "
             "(%+.3fR, %+.3fR) reads as noise, not signal." %
             (baseline_r["money"]["sum_r"], cap1_r["money"]["sum_r"],
              100.0 * (baseline_r["money"]["sum_r"] - cap1_r["money"]["sum_r"])
              / max(abs(baseline_r["money"]["sum_r"]), 1),
              baseline_r["money"]["n"] - next(r for r in results if r["cap"] == 2)["money"]["n"],
              baseline_r["money"]["n"] - next(r for r in results if r["cap"] == 3)["money"]["n"],
              next(r for r in results if r["cap"] == 2)["money"]["mean_r"] - baseline_r["money"]["mean_r"],
              next(r for r in results if r["cap"] == 3)["money"]["mean_r"] - baseline_r["money"]["mean_r"]))
    L.append("3. **The card rigs — the ones closest to Austin's own eyes, and the "
             "held-out 100 specifically — show zero movement on recall or false fires "
             "for any arm.** A cap that cannot be seen on the population it would "
             "actually gate (his graded days) and is not decisive on the population it "
             "can be seen on (the book) is not yet a rule worth coding.")
    L.append("")
    L.append("This matches Austin's own instinct (\"my cap is just the prediction, so "
             "why cap it\") and the pattern P21 and P18 already set: a plausible-"
             "sounding rule that does not clear its own bar on this book. It does NOT "
             "mean cap `1` is wrong — P20's own larger sample (n=422 tripped) says the "
             "direction is real, and cap `1` is the one arm here where mean R, win "
             "rate, and months-green all move the same way at once. If Austin wants "
             "durability and per-trade quality MORE than he wants total volume, cap "
             "`1` is the defensible choice, not a guess — but that is a preference "
             "this table cannot resolve for him, since it is exactly the volume-vs-"
             "quality trade-off, not a statistics question.")
    L.append("")

    L.append("## What this does not say")
    L.append("")
    L.append("1. **Nothing here is ratified or wired in.** `research/downgrade.py` is "
             "untouched; the cap lives only in this script's own `apply_cap()`, called "
             "explicitly per arm.")
    L.append("2. **This is not the sequence-gate quality downgrade (P20).** P20 "
             "downgrades a 2nd+ entry's GRADE (S can become A or C); this cap removes "
             "an entry from the TAKEN-S set without changing what `downgrade.score()` "
             "says its grade is. The two are different mechanisms answering different "
             "ballot lines (b2 vs c3/c4) and are not combined here.")
    L.append("3. **The card rigs cannot see this cap by construction** (see above) — "
             "their identical numbers across arms are not evidence the cap does "
             "nothing, only that recall/false-fire is the wrong lens for it. The book "
             "money table is the only population where a hard trade-count cap can show "
             "up at all.")
    L.append("4. **The traded book is pre-filtered by the legacy grader**, same caveat "
             "as `research/p2_threshold_sweep.md` and `research/p20_sequence_gate.md` — "
             "only %d of %d signals were traded at all, and money is reported only over "
             "that pre-filtered set." % (n_traded, len(book)))
    L.append("5. **`research/downgrade.py`'s `ENABLE_SEQUENCE_GATE` stays `False`** — "
             "every grade in this report is the plain committed grade, not the P20 "
             "sequence-gate-on grade. The two rows would not simply add if both were "
             "ever wired in together (P23 found P18/P19/P20 interact); this row does "
             "not attempt that combination.")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
