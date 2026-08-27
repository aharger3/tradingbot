"""p23_combined_arms.py -- P23/Block 6: P18+P19+P20 measured TOGETHER, not alone.

Ballot batch 02 added three flags to `research/downgrade.py`, all OFF by
default, each measured ALONE against the committed grader:

    P19  ENABLE_MULTI_LEVEL_CONFLUENCE   +0.250R, right-signed, trips 23.9%
    P20  ENABLE_SEQUENCE_GATE            -0.325R, right-signed, recall 12/28->8/28
    P18  ENABLE_LARGE_COUNTER_BODY       +0.029R, wrong-signed, trips 57.2%

Nobody has run them TOGETHER, and they interact by construction: P19 hands
out a +1, P20 takes one away, on overlapping populations. This script scores
five arms -- baseline, P19 alone, P20 alone, P19+P20, and P19+P20+P18 -- over
ONE pass over the bars (bars/levels/entry_seq computed once, `downgrade.score`
re-called per arm on the same in-memory data, no re-fetch).

**Change no defaults.** Every ENABLE_* flag in `downgrade.py` stays `False`.
This is measurement; wiring is R3/P4, gated on Austin ratifying (R2). Every
row below comes from an explicit `enable_*` kwarg on this script's own calls
to `downgrade.score`, exactly as P18/P19/P20's own scripts already do.

THE HOLD-OUT
------------
Reuses `research/p2_threshold_sweep.py`'s own `build_cards()` + `split_cards()`
to get the identical 50/50, stratified-by-Austin's-own-grade partition of the
120 day-cards (same seed, deterministic, re-running reproduces it) -- this
script does not reimplement the split, it imports it. The headline is
reported on HOLD, per `research/p2_threshold_sweep.md`'s own finding that the
committed grader looks better on TUNE (+0.033 gate) than HOLD (-0.159); an
arm that only wins on TUNE has not won. The 2-year book (`bt2y_trades.json`)
is NOT split -- consistent with `p2_threshold_sweep.py`, which only holds out
the 120-card corpus (the thing a threshold could be fit against); the book is
an independent read-only check either way.

    python research/p23_combined_arms.py [--limit N]

Writes research/p23_combined_arms.md.
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
from research.p2_threshold_sweep import (build_cards as sweep_build_cards,  # noqa: E402
                                         split_cards)

OUT = os.path.join(HERE, "p23_combined_arms.md")
BT2Y = os.path.join(HERE, "bt2y_trades.json")

SIX = dg.CONFLUENCE_LEVELS                       # ("PDH","PDL","PMH","PML","ORH","ORL")
BEST = {"S": 3, "A": 2, "C": 1}
AUSTIN_MIX = {"S": 28, "A": 27, "C": 3}

ARMS = [
    ("baseline", {}),
    ("P19 only", {"enable_multi_level_confluence": True}),
    ("P20 only", {"enable_sequence_gate": True}),
    ("P19 + P20", {"enable_multi_level_confluence": True, "enable_sequence_gate": True}),
    ("P19 + P20 + P18", {"enable_multi_level_confluence": True,
                         "enable_sequence_gate": True,
                         "enable_large_counter_body": True}),
]


def _is84(signal_type):
    return signal_type == "reentry_84_rule"


# ---------------------------------------------------------------------------
# CARD rig -- Austin's 120 graded day-cards, split TUNE/HOLD via p2's own split
# ---------------------------------------------------------------------------

def card_levels(sym, day, bars):
    pdh, pdl, _po, _pc = prior_day_levels(sym, day)
    pmh, pml = premarket_extremes(sym, day)
    orh = max(b["h"] for b in bars[:5]) if len(bars) >= 5 else None
    orl = min(b["l"] for b in bars[:5]) if len(bars) >= 5 else None
    return {"PDH": pdh, "PDL": pdl, "PMH": pmh, "PML": pml, "ORH": orh, "ORL": orl}


def build_card_corpus():
    """Bars + levels + entry_seq/is_84 for every card signal, keyed the same
    way `p2_threshold_sweep.build_cards()` keys its own corpus."""
    days, _trades = load_day_cards()
    rows = {}
    for key in sorted(days):
        sym, day = key
        sigs, bars = replay(sym, day)
        if sigs is None:
            continue
        levels = card_levels(sym, day, bars)
        valid = [s for s in sigs if s["bar"] < len(bars)]
        sigs_out = [{"i": s["bar"], "stop": s["stop"], "is_long": s["dir"] == "call",
                    "entry_seq": idx, "is_84": _is84(s.get("signal_type"))}
                   for idx, s in enumerate(valid, start=1)]
        rows[key] = {"key": key, "card": (days[key].get("grade") or "").strip(),
                    "bars": bars, "levels": levels, "sigs": sigs_out}
    return rows


def split_card_rows(rows):
    """Reuses `p2_threshold_sweep.py`'s own build_cards()+split_cards() to get
    the identical 50/50, stratified, seed-6 partition -- imported, not
    reimplemented. Returns (tune_rows, hold_rows, all_rows), each a list of
    this script's own row dicts (bars/levels/sigs), keyed by the same
    (symbol, day) split p2 uses."""
    sweep_corpus = sweep_build_cards()          # [(key, grade, feats), ...]
    tune_pairs, hold_pairs = split_cards(sweep_corpus)
    tune_keys = {r[0] for r in tune_pairs}
    hold_keys = {r[0] for r in hold_pairs}
    tune_rows = [rows[k] for k in tune_keys if k in rows]
    hold_rows = [rows[k] for k in hold_keys if k in rows]
    all_rows = tune_rows + hold_rows
    return tune_rows, hold_rows, all_rows


def eval_cards_direct(rows, **score_kw):
    day_mix = Counter()
    grades = Counter()
    s_hit = s_tot = ff = ff_tot = agree = agree_tot = n_sigs = 0
    for row in rows:
        best = 0
        for sig in row["sigs"]:
            rec = dg.score(row["bars"], sig["i"], sig["stop"], sig["is_long"],
                          levels=row["levels"], entry_seq=sig["entry_seq"],
                          is_84_reentry=sig["is_84"], **score_kw)
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
            "n_sigs": n_sigs, "grades": grades,
            "s_recall": s_hit / max(s_tot, 1), "false_fire": ff / max(ff_tot, 1)}


def gate(r):
    return r["s_recall"] - r["false_fire"]


# ---------------------------------------------------------------------------
# BOOK rig -- research/bt2y_trades.json, read only, NOT split (see docstring)
# ---------------------------------------------------------------------------

def build_book(limit=None):
    import polygon_feed as pf
    with open(BT2Y, encoding="utf-8") as fh:
        rows = json.load(fh)["trades"]

    # entry_seq / is_84, all-signal reading (P20's primary reading -- the one
    # that separates money; see research/p20_sequence_gate.md).
    by_seq = defaultdict(list)
    for idx, r in enumerate(rows):
        r["_orig"] = idx
        by_seq[(r["sym"], r["day"])].append(r)
    for _k, rs in by_seq.items():
        rs.sort(key=lambda r: (r["et"], r["_orig"]))
        for i, r in enumerate(rs, start=1):
            r["_entry_seq"] = i
            r["_is_84"] = (r["setup"] == "reentry_84_rule")

    by_day = defaultdict(list)
    for r in rows:
        by_day[(r["sym"], r["day"])].append(r)
    keys = sorted(by_day)
    if limit:
        keys = keys[:limit]
    book, missed = [], 0
    t0 = time.time()
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
        levels_full = p21.levels_for_entry(sym, day, len(rth) - 1)
        levels = {k6: levels_full.get(k6) for k6 in SIX}
        for r in by_day[k]:
            i = idx.get(r["et"])
            if i is None:
                missed += 1
                continue
            book.append({"bars": bars, "i": i, "stop": r["stop"],
                        "is_long": r["dir"] == "call", "levels": levels,
                        "entry_seq": r["_entry_seq"], "is_84": r["_is_84"],
                        "traded": bool(r["traded"]), "win": r["out"] == "win",
                        "r": float(r["r"])})
        if n % 2000 == 0:
            print("  book %d/%d symbol-days, %.0fs" % (n, len(keys), time.time() - t0),
                  flush=True)
    return book, missed


def eval_book_grades(book, **score_kw):
    tr = {g: [0, 0, 0.0] for g in ("S", "A", "C")}
    for rec in book:
        if not rec["traded"]:
            continue
        d = dg.score(rec["bars"], rec["i"], rec["stop"], rec["is_long"],
                    levels=rec["levels"], entry_seq=rec["entry_seq"],
                    is_84_reentry=rec["is_84"], **score_kw)
        t = tr[d["grade"]]
        t[0] += 1
        t[1] += 1 if rec["win"] else 0
        t[2] += rec["r"]
    out = {}
    for g, (n, w, s) in tr.items():
        out[g] = {"n": n, "win": (100.0 * w / n if n else 0.0), "r": (s / n if n else 0.0)}
    mono_r = out["S"]["r"] > out["A"]["r"] > out["C"]["r"]
    mono_w = out["S"]["win"] > out["A"]["win"] > out["C"]["win"]
    return out, (mono_r and mono_w)


T0 = time.time()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="cap the book to N symbol-days (smoke test only)")
    args = ap.parse_args()

    global T0
    T0 = time.time()
    card_rows_by_key = build_card_corpus()
    tune_rows, hold_rows, all_rows = split_card_rows(card_rows_by_key)
    n_card_sigs = sum(len(r["sigs"]) for r in all_rows)
    print("cards: %d day-cards (%d TUNE / %d HOLD), %d signals, %.1fs"
          % (len(all_rows), len(tune_rows), len(hold_rows), n_card_sigs, time.time() - T0))

    t0 = time.time()
    book, missed = build_book(args.limit or None)
    n_traded = sum(1 for r in book if r["traded"])
    print("book: %d signals (%d unmatched), %d traded, %.1fs"
          % (len(book), missed, n_traded, time.time() - t0))

    results = []
    for label, kw in ARMS:
        tune = eval_cards_direct(tune_rows, **kw)
        hold = eval_cards_direct(hold_rows, **kw)
        allc = eval_cards_direct(all_rows, **kw)
        book_out, mono = eval_book_grades(book, **kw)
        results.append({"label": label, "kw": kw, "tune": tune, "hold": hold,
                        "all": allc, "book": book_out, "mono": mono})
        print("  %-18s TUNE gate %+.3f  HOLD gate %+.3f  S(hold n=%d win=%.1f%% r=%+.3f)"
              % (label, gate(tune), gate(hold),
                 book_out["S"]["n"], book_out["S"]["win"], book_out["S"]["r"]))

    write_report(all_rows, n_card_sigs, len(tune_rows), len(hold_rows),
                book, n_traded, missed, results)
    print("wrote %s" % OUT)


def card_row(r, label):
    return ("| %s | %d/%d | %d/%d | %d/%d | %d/%d/%d |"
            % (label, r["s_hit"], r["s_tot"], r["ff"], r["ff_tot"],
               r["agree"], r["agree_tot"], r["dS"], r["dA"], r["dC"]))


def book_row(out, mono, label):
    return ("| %s | %d | %.1f%% | %+.3fR | %d | %.1f%% | %+.3fR | %d | %.1f%% | %+.3fR | %s |"
            % (label, out["S"]["n"], out["S"]["win"], out["S"]["r"],
               out["A"]["n"], out["A"]["win"], out["A"]["r"],
               out["C"]["n"], out["C"]["win"], out["C"]["r"],
               "yes" if mono else "**NO**"))


def write_report(all_rows, n_card_sigs, n_tune, n_hold, book, n_traded, missed, results):
    L = []
    L.append("# P23 — the combination nobody ran: P18 + P19 + P20 together")
    L.append("")
    L.append("Generated by `research/p23_combined_arms.py`. Every `ENABLE_*` flag in "
             "`research/downgrade.py` stays **`False`** — every number below came from "
             "an explicit `enable_*` kwarg on this script's own calls to "
             "`downgrade.score`, which does not touch the module defaults any other "
             "caller sees. Nothing here is wired into detection; ratifying or rejecting "
             "any arm is R2, Austin's call.")
    L.append("")
    L.append("P19 (`multi_level_confluence`, +0.250R alone), P20 (`sequence_gate`, "
             "-0.325R alone) and P18 (`large_counter_body`, +0.029R alone, wrong-signed) "
             "were each measured **alone**, against the committed grader "
             "(`research/p18_p19_new_variables.md`, `research/p20_sequence_gate.md`). "
             "They interact by construction — P19 hands out a +1, P20 takes one away, "
             "on overlapping populations — so the net cannot be read off the three solo "
             "numbers. Note P15 landed nothing (`research/p15_level_respect.md`): "
             "\"the corrected grader\" below means P19+P20(+P18), not a fixed "
             "`level_not_respected`.")
    L.append("")
    L.append("Two rigs, same as `research/p2_threshold_sweep.md`: Austin's %d graded "
             "day-cards (%d signals, split 50/50 TUNE/HOLD — %d/%d — via that script's "
             "own `build_cards()`+`split_cards()`, imported not reimplemented) and "
             "`research/bt2y_trades.json` (%d signals / %d traded, not split — same "
             "convention as `p2_threshold_sweep.py`, which only holds out the "
             "card corpus)." % (len(all_rows), n_card_sigs, n_tune, n_hold,
                                len(book), n_traded))
    if missed:
        L.append("")
        L.append("%d book signals could not be matched to an archived bar and are "
                 "excluded." % missed)
    L.append("")

    L.append("## Hold-out discipline")
    L.append("")
    L.append("`research/p2_threshold_sweep.md` already found the committed grader looks "
             "materially better on TUNE (gate +0.033) than HOLD (gate -0.159). None of "
             "the five arms below is fit to either half — the flags carry Austin's own "
             "numbers (5/6 levels, the sequence rule, 75% body), not a threshold swept "
             "against this data — but the headline is still reported on **HOLD**, not "
             "TUNE, so an arm that only looks good on the half it happens to agree with "
             "is not mistaken for a winner.")
    L.append("")

    # ------------------------------------------------------------- card table
    L.append("## Card rig — S recall, false fires, day agreement, S/A/C mix")
    L.append("")
    L.append("`gate` = S recall − false-fire rate, the same ranking Austin asked for "
             "first. Austin's own day mix is 28/27/3 (S/A/C) over the full 58 graded "
             "day-cards.")
    L.append("")
    for half_key, half_label in (("tune", "TUNE"), ("hold", "HOLD"), ("all", "ALL")):
        L.append("### %s" % half_label)
        L.append("")
        L.append("| arm | S recall | false fire | gate | agree | day S/A/C |")
        L.append("|---|---|---|---:|---|---|")
        for r in results:
            half = r[half_key]
            L.append("| %s | %d/%d | %d/%d | **%+.3f** | %d/%d | %d/%d/%d |"
                     % (r["label"], half["s_hit"], half["s_tot"], half["ff"], half["ff_tot"],
                        gate(half), half["agree"], half["agree_tot"],
                        half["dS"], half["dA"], half["dC"]))
        L.append("")

    # ------------------------------------------------------------- money table
    L.append("## Money rig — traded book, per grade")
    L.append("")
    L.append("| arm | S n | S win | S mean R | A n | A win | A mean R | C n | C win | "
             "C mean R | S>A>C |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for r in results:
        L.append(book_row(r["book"], r["mono"], r["label"]))
    L.append("")

    # ------------------------------------------------------------- the read
    hold_gates = {r["label"]: gate(r["hold"]) for r in results}
    tune_gates = {r["label"]: gate(r["tune"]) for r in results}
    hold_ff = {r["label"]: r["hold"]["ff"] for r in results}
    hold_recall = {r["label"]: r["hold"]["s_hit"] for r in results}
    best_hold = max(hold_gates, key=lambda k: hold_gates[k])
    best_tune = max(tune_gates, key=lambda k: tune_gates[k])
    best_money = max(results, key=lambda r: r["book"]["S"]["r"])["label"]
    baseline_hold_gate = hold_gates["baseline"]

    L.append("## The read")
    L.append("")
    L.append("Recall and false fires move together, so no arm is ranked on recall "
             "alone — `gate` (recall minus false-fire rate) is the number that "
             "separates a real improvement from an arm that simply fires more (or "
             "less) often.")
    L.append("")
    L.append("**Best HOLD gate: `%s`** (%+.3f vs baseline %+.3f)." % (best_hold, hold_gates[best_hold], baseline_hold_gate))
    L.append("")
    L.append("**Best TUNE gate: `%s`** (%+.3f)." % (best_tune, tune_gates[best_tune]))
    if best_hold != best_tune:
        L.append("")
        L.append("**TUNE and HOLD disagree on which arm is best — reported, not "
                 "averaged away.**")
    L.append("")
    L.append("**Best money-rig S mean R: `%s`.**" % best_money)
    if best_money != best_hold:
        L.append("")
        L.append("**The cards rig and the money rig do not agree on the best arm** — "
                 "the cards rig prefers `%s` on HOLD, the money rig prefers `%s` on S "
                 "mean R. That disagreement is itself the finding, not something to "
                 "average over: a card-gate winner is not automatically a money-rig "
                 "winner, and vice versa." % (best_hold, best_money))
    else:
        L.append("")
        L.append("**The cards rig and the money rig agree**: `%s` is best on both HOLD "
                 "gate and S mean R." % best_hold)
    L.append("")

    L.append("## What this does not say")
    L.append("")
    L.append("1. **Nothing here is ratified or wired in.** Every `ENABLE_*` flag in "
             "`research/downgrade.py` stays `False`; every row above came from an "
             "explicit `enable_*` kwarg on this script's own calls to `downgrade.score`.")
    L.append("2. **This is not a threshold sweep.** No knob is fit against TUNE or "
             "HOLD; the flags carry Austin's own ballot numbers unchanged. The TUNE/HOLD "
             "split still matters here because it is the same 120-card corpus used to "
             "justify P19/P20/P18 individually, and reporting only the half that looks "
             "best would repeat the mistake `p2_threshold_sweep.md` was written to avoid.")
    L.append("3. **The upgrade cap (P19) is unchanged from its own report** — "
             "`multi_level_confluence` and `has_confluence` (BR+OCR) are capped together "
             "at one point, per `research/p18_p19_new_variables.md`; that design choice "
             "is not re-litigated here.")
    L.append("4. **`level_not_respected` is unfixed.** P15 landed nothing "
             "(`research/p15_level_respect.md`); \"the corrected grader\" in this report "
             "means P19+P20(+P18), and `level_not_respected` stays in its committed, "
             "wrong-signed form in every arm, baseline included.")
    L.append("5. **The traded book is pre-filtered by the legacy grader**, same caveat "
             "as `research/p2_threshold_sweep.md` — only %d of %d signals were traded "
             "at all." % (n_traded, len(book)))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
