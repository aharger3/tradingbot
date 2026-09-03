"""G7.1 / track `smeasure` (part 3) -- THE definitive S-accuracy test.

Austin, 2026-08-29:
  "until we have the best test to determine s trade acuracy, and pooling those
   together, then we can determine if the whole system is meeting my eye"
  "understanding my system from 25 card samples is not enough."

WHAT IS WRONG WITH THE TEST WE HAVE
-----------------------------------
`research/t0_heldout_recall.py:86` scores S recall on ONE corpus -- the 34 S
cards inside `research/marks/probe_s_sweep_2026-08-28.jsonl` -- through
`research/t4_engine_recall.run_day`, and calls a card a hit if the engine takes
ANY entry that day (`t0_heldout_recall.py:92-97`). Three defects, all fatal to
the 90% gate:

  1. n = 34.  The 95% Wilson interval on 23/34 is +/-15 points wide.  You
     cannot see a 90% gate through a +/-15 point window, and n=25 (the `sr_`
     lane of `probe_master_homework_2026-08-26.jsonl`) is worse.
  2. It is scored on the WRONG ROUTER.  `t4_engine_recall.CaptureRunner._route`
     is a hand-rolled copy of `SignalRunner._route` that never calls `super()`,
     so every gate the base grew after it was written is INERT in the one rig
     that scores the governing metric (`research/t23_stack.md` section 4b).
     On the traded book the same 34 cards score 1/34, not 23/34.
  3. It ignores 254 of the 288 S symbol-days on record.  `answers.s` /
     `answers.s_call` / `austin_tier` / `verdict` / `grade` all mean "S" in
     different corpora and no reader takes all five (`g71_smeasure_pools.py`).

THE TEST
--------
Same pooled population, FOUR nested hit definitions scored side by side, each
with a 95% Wilson interval, and an explicit eligibility funnel so a miss caused
by "the book never trades that symbol" is never mistaken for a miss caused by
the grader:

    saw     the two-year book emitted ANY signal on that symbol-day
    routed  at least one of those signals cleared `_route` (status == "fired")
    traded  at least one survived into the book (`traded == true`)
    harness `t4_engine_recall.run_day` takes an entry -- the metric published
            today, kept only so the new numbers can be reconciled to it

`traded` is the one that answers his question.  `harness` is the one the repo
has been steering by.  Reporting them together is the point.

Held-out discipline is declared per corpus, not assumed (see `PROVENANCE`).
No corpus in this repo is a clean hold-out today and the script says so.

Precision is scored on the SAME days from the negative side: of the days he
looked at and refused, how often does the engine trade anyway.  A recall number
with no precision number can be bought by firing on everything.

Reads only.  No mark file, no engine file, no published artifact is written.

Usage:
  python research/g71_smeasure_test.py                    # full test
  python research/g71_smeasure_test.py --no-harness       # skip the replay (fast)
  python research/g71_smeasure_test.py --out research/g71_smeasure_test.json
"""
from __future__ import annotations
import argparse, json, math, os, sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import research.build_deck as bd                     # noqa: E402
import research.g71_smeasure_pools as pools_mod      # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades.json")

# Corpus -> (graded_on, how it has already been used).  "held-out" is a claim
# about USE, not about date: a set the arms were selected on is not held out
# however fresh it is.
#   fit         its labels chose a threshold
#   selection   arms were ranked by their score on it
#   in_sample   it predates the engine that is being scored
#   clean       never fit, never selected on  -- currently EMPTY, and that is
#               the finding
PROVENANCE = {
    "marks/probe_s_sweep_2026-08-28.jsonl":        ("2026-08-28", "selection"),
    "marks/probe_master_2026-08-29.jsonl":         ("2026-08-29", "fit"),
    "marks/probe_master_homework_2026-08-26.jsonl": ("2026-08-26", "selection"),
    "marks/probe_omen_test1_2026-08-27.jsonl":     ("2026-08-27", "selection"),
    "marks/deck_marks_h2_3lane_2026-08-28.jsonl":  ("2026-08-28", "fit"),
    "marks/probe_autopsy_2026-08-23.jsonl":        ("2026-08-23", "in_sample"),
    "marks/probe_head2head_2026-08-24.jsonl":      ("2026-08-24", "in_sample"),
    "marks/deck_marks_index_2026-08-19.jsonl":     ("2026-08-19", "in_sample"),
    "marks/deck_marks_tsla_2026-08-20.jsonl":      ("2026-08-20", "in_sample"),
    "austin_marks_v7.jsonl":                       ("2026-08-11", "in_sample"),
    "blind_marks_all.jsonl":                       ("2026-08-05", "in_sample"),
    "marks_clean.jsonl":                           ("2026-08-05", "in_sample"),
    "mark_batch_02_grades.jsonl":                  ("2026-08-09", "in_sample"),
    "mark_batch_03_regrades.jsonl":                ("2026-08-10", "in_sample"),
    "mark_batch_04_grades.jsonl":                  ("2026-08-10", "in_sample"),
    "derived_marks_v1.jsonl":                      ("2026-08-10", "in_sample"),
    "derived_marks_v2.jsonl":                      ("2026-08-11", "in_sample"),
    "recovered_reviews.jsonl":                     ("2026-08-11", "in_sample"),
    "austin_verdicts.json":                        ("2026-08-06", "in_sample"),
}


# ------------------------------------------------------------------ statistics

def wilson(k, n, z=1.959963985):
    """95% Wilson score interval for k successes in n.  Wilson, not
    Wald: at n=34 and p near 0.9 the Wald interval runs past 1.0."""
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def n_for_halfwidth(p, target_hw, z=1.959963985, nmax=20000):
    """Smallest n whose 95% Wilson half-width at recall p is <= target_hw."""
    for n in range(5, nmax):
        k = round(p * n)
        _, lo, hi = wilson(k, n, z)
        if (hi - lo) / 2 <= target_hw:
            return n
    return None


def n_to_demonstrate(p_true, gate=0.90, z=1.959963985, nmax=20000):
    """Smallest n at which, if true recall is p_true, the 95% Wilson LOWER
    bound clears `gate`.  This is the honest form of the gate: 'recall >= 90%'
    is a claim, and a claim needs a lower bound above 0.90, not a point
    estimate above it."""
    if p_true <= gate:
        return None
    for n in range(5, nmax):
        k = round(p_true * n)
        _, lo, _ = wilson(k, n, z)
        if lo >= gate:
            return n
    return None


def two_prop_z(k1, n1, k2, n2):
    """Unpaired two-proportion z test -- does the engine treat his S days
    differently from the days he refused?  This is the whole question: an arm
    whose S rate equals its refused rate has learned nothing about his eye,
    however high the recall number is."""
    if n1 == 0 or n2 == 0:
        return {"diff_pts": 0.0, "z": 0.0, "p_two_sided": 1.0}
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    z = 0.0 if se == 0 else (p1 - p2) / se
    # two-sided normal tail
    pv = math.erfc(abs(z) / math.sqrt(2))
    return {"diff_pts": round((p1 - p2) * 100, 1), "z": round(z, 3),
            "p_two_sided": round(pv, 4)}


def mcnemar_exact_one_sided(b, c):
    """One-sided exact McNemar on discordant pairs (b gained, c lost)."""
    n = b + c
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(b, n + 1)) / (2 ** n)


# ------------------------------------------------------------------- the pool

def s_pool():
    """{key: {'corpora': [...], 'uses': set(), 'contested': bool}} for every
    symbol-day at least one corpus calls S.  Enumerated through
    build_deck._judgement_key so it can never drift from the no-repeat guard."""
    pools, per_source, _ = pools_mod.collect()
    out = {}
    for key, by_corpus in pools.items():
        says_s = sorted(c for c, t in by_corpus.items() if t[True])
        if not says_s:
            continue
        says_no = sorted(set(c for c, t in by_corpus.items() if t[False]) - set(says_s))
        out[key] = {"S_in": says_s, "notS_in": says_no,
                    "contested": bool(says_no),
                    "uses": sorted({PROVENANCE.get(c, ("", "unknown"))[1]
                                    for c in says_s})}
    return out, per_source, pools


def neg_pool(pools):
    """Days he judged and did NOT call S, in any corpus -- the negative sample
    precision is scored on."""
    out = {}
    for key, by_corpus in pools.items():
        says_s = {c for c, t in by_corpus.items() if t[True]}
        if says_s:
            continue
        says_no = sorted(c for c, t in by_corpus.items() if t[False])
        if says_no:
            out[key] = {"notS_in": says_no}
    return out


# -------------------------------------------------------------------- the book

def book_index():
    """(by_day, meta).  by_day[(sym, day)] = {'sigs','routed','traded'}."""
    d = json.load(open(BOOK, encoding="utf-8"))
    meta = d["meta"]
    by_day = defaultdict(lambda: {"sigs": 0, "routed": 0, "traded": 0})
    for t in d["trades"]:
        e = by_day[(t["sym"], t["day"])]
        e["sigs"] += 1
        if t.get("status") == "fired":
            e["routed"] += 1
        if t.get("traded"):
            e["traded"] += 1
    return by_day, meta


# ------------------------------------------------------------------ the harness

def harness_fired(pairs):
    from research.t4_engine_recall import run_day
    out = {}
    for sym, day in sorted(pairs):
        try:
            entries, _sigs, _raw = run_day(sym, day)
        except Exception as e:                       # noqa: BLE001
            out[(sym, day)] = None
            continue
        out[(sym, day)] = None if entries is None else len(entries)
    return out


# ------------------------------------------------------------------------ main

def split(key):
    sym, day = key.rsplit("_", 1)
    return sym, day


def score(days, hits, label):
    n = len(days)
    k = sum(1 for d in days if hits.get(d))
    p, lo, hi = wilson(k, n)
    return {"arm": label, "n": n, "hits": k,
            "rate_pct": round(p * 100, 1),
            "ci95_pct": [round(lo * 100, 1), round(hi * 100, 1)],
            "halfwidth_pts": round((hi - lo) / 2 * 100, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "g71_smeasure_test.json"))
    ap.add_argument("--no-harness", action="store_true")
    a = ap.parse_args()

    spool, per_source, pools = s_pool()
    npool = neg_pool(pools)
    by_day, meta = book_index()
    win_lo, win_hi = meta["first"], meta["last"]
    book_syms = set(meta["symbols"])

    # ---- eligibility funnel ------------------------------------------------
    def eligible(key):
        sym, day = split(key)
        return (sym in book_syms) and (win_lo <= day <= win_hi)

    all_s = sorted(spool)
    elig_s = [k for k in all_s if eligible(k)]
    all_n = sorted(npool)
    elig_n = [k for k in all_n if eligible(k)]

    funnel = {
        "S_days_pooled": len(all_s),
        "S_days_symbol_in_book_universe": sum(
            1 for k in all_s if split(k)[0] in book_syms),
        "S_days_inside_book_window_%s_%s" % (win_lo, win_hi): sum(
            1 for k in all_s if win_lo <= split(k)[1] <= win_hi),
        "S_days_eligible_for_the_book": len(elig_s),
        "negative_days_pooled": len(all_n),
        "negative_days_eligible": len(elig_n),
    }

    # ---- the four arms -----------------------------------------------------
    saw = {k: by_day.get(split(k), {}).get("sigs", 0) for k in elig_s}
    routed = {k: by_day.get(split(k), {}).get("routed", 0) for k in elig_s}
    traded = {k: by_day.get(split(k), {}).get("traded", 0) for k in elig_s}

    arms = [score(elig_s, saw, "saw (engine emitted any signal)"),
            score(elig_s, routed, "routed (cleared _route)"),
            score(elig_s, traded, "traded (survived into the book)")]

    harness = None
    if not a.no_harness:
        hf = harness_fired({split(k) for k in elig_s})
        harness = {k: (hf.get(split(k)) or 0) for k in elig_s}
        arms.append(score(elig_s, harness, "harness (t4_engine_recall.run_day)"))

    # ---- precision, on the negative pool -----------------------------------
    n_saw = {k: by_day.get(split(k), {}).get("sigs", 0) for k in elig_n}
    n_routed = {k: by_day.get(split(k), {}).get("routed", 0) for k in elig_n}
    n_traded = {k: by_day.get(split(k), {}).get("traded", 0) for k in elig_n}
    neg = score(elig_n, n_traded, "false-fire on days he refused (traded)")

    # ---- DISCRIMINATION: does the arm separate his S days from his refusals?
    disc = []
    disc_pairs = [("saw", saw, n_saw), ("routed", routed, n_routed),
                  ("traded", traded, n_traded)]
    n_harness = None
    if not a.no_harness:
        hfn = harness_fired({split(k) for k in elig_n})
        n_harness = {k: (hfn.get(split(k)) or 0) for k in elig_n}
        disc_pairs.append(("harness", harness, n_harness))
    for label, pos, negm in disc_pairs:
        kp = sum(1 for k in elig_s if pos[k])
        kn = sum(1 for k in elig_n if negm[k])
        d = two_prop_z(kp, len(elig_s), kn, len(elig_n))
        d["arm"] = label
        d["S_rate_pct"] = round(kp / len(elig_s) * 100, 1)
        d["refused_rate_pct"] = round(kn / len(elig_n) * 100, 1)
        disc.append(d)
    tp = sum(1 for k in elig_s if traded[k])
    fp = sum(1 for k in elig_n if n_traded[k])
    prec_p, prec_lo, prec_hi = wilson(tp, tp + fp) if (tp + fp) else (0, 0, 0)

    # ---- SENSITIVITY: does a precedence rule move the answer? ---------------
    # "any corpus says S" is one defensible pooling rule. The other is "the
    # LATEST grading session wins" -- which is what LEDGER.md already asserts
    # for austin_verdicts -> v7, and what a regrade batch means by definition.
    # If the two rules give the same recall, the 35 conflicts do not matter to
    # the gate and can be left alone; if they diverge, they must be settled
    # before any recall number is published.
    prec_pool = []
    for key in elig_s + elig_n:
        by_corpus = pools[key]
        best_date, best_v = "", None
        for c, t in by_corpus.items():
            d = PROVENANCE.get(c, ("0000-00-00", ""))[0]
            if d >= best_date:
                # within one corpus, any S on the day wins (day-level grain)
                best_date, best_v = d, bool(t[True])
        if best_v:
            prec_pool.append(key)
    prec_traded = {k: by_day.get(split(k), {}).get("traded", 0) for k in prec_pool}
    prec_neg = [k for k in elig_s + elig_n if k not in set(prec_pool)]
    prec_neg_traded = {k: by_day.get(split(k), {}).get("traded", 0) for k in prec_neg}
    sens = {
        "rule_any_corpus_says_S": score(elig_s, traded, "traded | any-corpus-S"),
        "rule_latest_session_wins": score(prec_pool, prec_traded,
                                          "traded | latest-session-wins"),
        "S_days_moved": len(set(elig_s) ^ set(prec_pool)),
        "discrimination_under_precedence": {
            **two_prop_z(sum(1 for k in prec_pool if prec_traded[k]), len(prec_pool),
                         sum(1 for k in prec_neg if prec_neg_traded[k]), len(prec_neg)),
            "n_S": len(prec_pool), "n_refused": len(prec_neg)},
    }

    # ---- what today's rig reports, for reconciliation ----------------------
    sweep = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
    sweep_s = []
    for line in open(sweep, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("answers", {}).get("s") == ["s"]:
            sweep_s.append("%s_%s" % (r["symbol"], r["date"]))
    t0_like = {k: by_day.get(split(k), {}).get("traded", 0) for k in sweep_s}
    t0_traded = score(sweep_s, t0_like, "t0 34-card sample, traded arm")

    # ---- sample-size table -------------------------------------------------
    sizing = {
        "today_n34_halfwidth_pts_at_23_34": round(
            (wilson(23, 34)[2] - wilson(23, 34)[1]) / 2 * 100, 1),
        "today_n25_halfwidth_pts_at_5_25": round(
            (wilson(5, 25)[2] - wilson(5, 25)[1]) / 2 * 100, 1),
        "n_for_plus_minus_10pts_at_p90": n_for_halfwidth(0.90, 0.10),
        "n_for_plus_minus_5pts_at_p90": n_for_halfwidth(0.90, 0.05),
        "n_for_plus_minus_3pts_at_p90": n_for_halfwidth(0.90, 0.03),
        "n_to_DEMONSTRATE_gate_if_true_recall_is_95pct": n_to_demonstrate(0.95),
        "n_to_DEMONSTRATE_gate_if_true_recall_is_93pct": n_to_demonstrate(0.93),
        "n_to_DEMONSTRATE_gate_if_true_recall_is_92pct": n_to_demonstrate(0.92),
        "note": ("The gate is a CLAIM (fires on >=90 pct of his S days), so it "
                 "needs a 95 pct lower bound above 0.90, not a point estimate "
                 "above it. A perfect engine (true recall 100 pct) clears it "
                 "at n=" + str(n_to_demonstrate(1.0)) + "."),
    }

    # ---- provenance of the pool -------------------------------------------
    by_use = Counter()
    for k in elig_s:
        for u in spool[k]["uses"]:
            by_use[u] += 1
    prov = {"eligible_S_days_by_how_the_corpus_was_used": dict(by_use),
            "clean_holdout_S_days": by_use.get("clean", 0)}

    res = {
        "book": {"file": "research/bt2y_trades.json", "generated": meta["generated"],
                 "window": [win_lo, win_hi], "sessions": meta["sessions"],
                 "signals": meta["signals"], "traded": meta["traded"],
                 "symbols": len(book_syms)},
        "funnel": funnel,
        "arms": arms,
        "false_fire_on_refused_days": neg,
        "discrimination_S_vs_refused": disc,
        "precision_traded_pct": round(prec_p * 100, 1),
        "precision_ci95_pct": [round(prec_lo * 100, 1), round(prec_hi * 100, 1)],
        "reconciliation_to_t0_sample": t0_traded,
        "pooling_rule_sensitivity": sens,
        "sizing": sizing,
        "provenance": prov,
        "contested_S_days_in_pool": sum(1 for k in elig_s if spool[k]["contested"]),
        "per_source": per_source,
        "eligible_S_days": elig_s,
        "misses_traded_arm": sorted(k for k in elig_s if not traded[k]),
    }
    if harness is not None:
        b = sum(1 for k in elig_s if harness[k] and not traded[k])
        c = sum(1 for k in elig_s if traded[k] and not harness[k])
        res["harness_vs_book"] = {
            "harness_only": b, "book_only": c,
            "mcnemar_exact_one_sided_p": round(mcnemar_exact_one_sided(b, c), 6)}

    # ---------------------------------------------------------------- report
    P = print
    P("BOOK  %s  %s..%s  %d sessions  %d signals  %d traded"
      % (os.path.basename(BOOK), win_lo, win_hi, meta["sessions"],
         meta["signals"], meta["traded"]))
    P("\nELIGIBILITY FUNNEL")
    for k, v in funnel.items():
        P("  %-52s %5d" % (k, v))
    P("\nS RECALL on the %d eligible pooled S symbol-days" % len(elig_s))
    P("  %-42s %5s %5s %8s  %s" % ("arm", "hits", "n", "rate", "95% CI"))
    for r in arms:
        P("  %-42s %5d %5d %7.1f%%  [%.1f, %.1f]  +/-%.1f pts"
          % (r["arm"], r["hits"], r["n"], r["rate_pct"],
             r["ci95_pct"][0], r["ci95_pct"][1], r["halfwidth_pts"]))
    P("\nDISCRIMINATION -- his %d S days vs his %d refused days, same arm"
      % (len(elig_s), len(elig_n)))
    P("  %-10s %9s %9s %11s %8s %9s"
      % ("arm", "S rate", "refused", "diff", "z", "p"))
    for d in disc:
        P("  %-10s %8.1f%% %8.1f%% %7.1f pts %8.2f %9.4f"
          % (d["arm"], d["S_rate_pct"], d["refused_rate_pct"],
             d["diff_pts"], d["z"], d["p_two_sided"]))
    P("\nPRECISION")
    P("  false fire on his %d refused days (traded): %d = %.1f%%  [%.1f, %.1f]"
      % (neg["n"], neg["hits"], neg["rate_pct"],
         neg["ci95_pct"][0], neg["ci95_pct"][1]))
    P("  precision of the traded book against his ladder: %.1f%%  [%.1f, %.1f]"
      % (res["precision_traded_pct"], prec_lo * 100, prec_hi * 100))
    P("\nRECONCILIATION -- the 34-card sample t0_heldout_recall.py publishes")
    P("  %d/%d = %.1f%%  [%.1f, %.1f]  +/-%.1f pts"
      % (t0_traded["hits"], t0_traded["n"], t0_traded["rate_pct"],
         t0_traded["ci95_pct"][0], t0_traded["ci95_pct"][1],
         t0_traded["halfwidth_pts"]))
    P("\nPOOLING-RULE SENSITIVITY (traded arm)")
    for rk in ("rule_any_corpus_says_S", "rule_latest_session_wins"):
        r = sens[rk]
        P("  %-26s %4d/%4d = %5.1f%%  [%.1f, %.1f]"
          % (rk, r["hits"], r["n"], r["rate_pct"],
             r["ci95_pct"][0], r["ci95_pct"][1]))
    dsp = sens["discrimination_under_precedence"]
    P("  S days that move between the rules: %d" % sens["S_days_moved"])
    P("  discrimination under precedence: %.1f pts  z=%.2f  p=%.4f  (n_S=%d, n_ref=%d)"
      % (dsp["diff_pts"], dsp["z"], dsp["p_two_sided"],
         dsp["n_S"], dsp["n_refused"]))
    P("\nSAMPLE SIZE")
    for k, v in sizing.items():
        P("  %-52s %s" % (k, v))
    P("\nPROVENANCE of the eligible S pool")
    for k, v in sorted(by_use.items()):
        P("  %-20s %d" % (k, v))
    P("  contested (S in one corpus, not-S in another): %d"
      % res["contested_S_days_in_pool"])
    if harness is not None:
        P("\nHARNESS vs BOOK  harness-only %d  book-only %d  exact one-sided p=%.4g"
          % (res["harness_vs_book"]["harness_only"],
             res["harness_vs_book"]["book_only"],
             res["harness_vs_book"]["mcnemar_exact_one_sided_p"]))

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    P("\nwrote " + a.out)


if __name__ == "__main__":
    main()
