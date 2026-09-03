"""g112_refusal_taxonomy.py -- every refusal in the mark corpus, clustered and
ranked, then priced against the honest book.

Austin, 2026-09-03: "REALLY ANALYZE MY S MARKS." This is the refusal half of
that instruction: grade "none", answers.take == "no", every why_not/why
checkbox, and the prose reason fields, counted with their denominators. Then
the precision question -- on the symbol-days he refused, what did the engine
do, and was it worth taking? A refusal he was RIGHT about is the precision
prize `research/omen_metrics.py` (2026-09-03) exists to price: this module
prices it.

Read-only. No mark file, no engine file, is opened for writing.

    python research/g112_refusal_taxonomy.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd            # noqa: E402
import grade_read as gr            # noqa: E402
import marks_pool as mp            # noqa: E402
from omen_metrics import ev_r_scoreboard, first_of_day_arm  # noqa: E402

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")

# --------------------------------------------------------------------------
# 1. THE TAXONOMY -- every structured refusal signal, clustered
# --------------------------------------------------------------------------

# Literal value -> normalized bucket. Built from grepping every mark corpus
# for reason_none / answers.why_not / answers.why (see grade_read.py's own
# field-count report run 2026-09-03: reason_none n=20, answers.why_not n=65,
# answers.why n=43). "chop" and "chop / no structure" are the same reason
# spelled by two different page builds; kept as one bucket. "no_level" /
# "no level" likewise. Everything else is its own bucket -- no bucket is
# invented for an n<3 literal, they fall into OTHER_LITERAL so nothing is
# silently merged past what the data says.
_BUCKET = {
    "chop": "chop / no structure",
    "chop / no structure": "chop / no structure",
    "no_setup": "chop / no structure",     # "no_setup" only ever co-occurs
                                            # with chop in answers.why rows
    "level_not_respected": "level not respected",
    "no_level": "no level present",
    "no level": "no level present",
    "no_displacement": "no displacement",
    "late": "late / missed it",
    "missed it": "late / missed it",
    "exhausted": "exhausted move",
    "too_extended": "exhausted move",
    "no_retest": "no retest",
    "range too tight": "range too tight",
    "other": "other (unspecified)",
}


def taxonomy_report():
    """Every refusal REASON in the corpus (not yet joined to a canonical
    day) -- one row's why_not list can carry more than one checkbox, so this
    counts checkbox instances, denominator = rows carrying that field."""
    reason_none_vals = Counter()
    why_not_vals = Counter()
    why_vals = Counter()
    take_no_rows = 0
    take_yes_rows = 0
    n_rows_any_refusal_field = 0
    n_rows_total = 0

    def _listify(v):
        if v is None:
            return []
        if isinstance(v, (list, tuple)):
            return [str(x).strip() for x in v if str(x).strip()]
        s = str(v).strip()
        return [s] if s else []

    for path in bd.mark_sources():
        for row in bd._rows(path):
            n_rows_total += 1
            hit = False
            for v in _listify(row.get("reason_none")):
                reason_none_vals[v] += 1
                hit = True
            ans = row.get("answers")
            if isinstance(ans, dict):
                for v in _listify(ans.get("why_not")):
                    why_not_vals[v] += 1
                    hit = True
                for v in _listify(ans.get("why")):
                    why_vals[v] += 1
                    hit = True
                tk = ans.get("take")
                tk = tk[0] if isinstance(tk, list) and tk else tk
                if tk is not None:
                    t = str(tk).strip().lower()
                    if t in ("no", "n", "false"):
                        take_no_rows += 1
                        hit = True
                    elif t in ("yes", "y", "true"):
                        take_yes_rows += 1
            if hit:
                n_rows_any_refusal_field += 1

    # cluster into normalized buckets
    clustered = Counter()
    literal_detail = defaultdict(Counter)
    for src_name, vals in (("reason_none", reason_none_vals),
                            ("answers.why_not", why_not_vals),
                            ("answers.why", why_vals)):
        for lit, c in vals.items():
            bucket = _BUCKET.get(lit.strip().lower(), "other (unspecified)")
            clustered[bucket] += c
            literal_detail[bucket][(src_name, lit)] += c

    clustered["take:no (no reason given)"] = take_no_rows

    return {
        "n_rows_total_corpus": n_rows_total,
        "n_rows_with_any_structured_refusal_field": n_rows_any_refusal_field,
        "raw_field_counts": {
            "reason_none": dict(reason_none_vals),
            "answers.why_not": dict(why_not_vals),
            "answers.why": dict(why_vals),
            "answers.take==no": take_no_rows,
            "answers.take==yes (NOT a refusal, excluded)": take_yes_rows,
        },
        "clustered_ranked": clustered.most_common(),
        "literal_detail": {
            b: {"%s:%s" % (src, lit): n for (src, lit), n in c.items()}
            for b, c in literal_detail.items()
        },
    }


def prose_scan():
    """Free-text note/notes fields on rows whose OWN grade resolved to
    'none' -- a keyword sweep, not a parse. Reported as a supplementary
    count only: labelled a hint, never merged into the structured counts
    above, per CLAUDE.md ('a claim on n cards is a hint and must be
    labelled one')."""
    KEYWORDS = {
        "chop": ["chop", "choppy"],
        "late": ["late", "missed"],
        "no level": ["no level", "no clean level"],
        "extended": ["extended", "exhaust"],
        "displacement": ["no disp", "no displacement", "nodisp"],
        "small/tight": ["too tight", "too small", "tiny"],
        "news/gap": ["news", "gap up", "gap down", "halted", "halt"],
        "counter-trend": ["counter trend", "counter-trend", "against trend"],
    }
    hits = Counter()
    n_none_rows_with_note = 0
    n_none_rows = 0
    for path in bd.mark_sources():
        for row in bd._rows(path):
            if gr.read_grade(row) != "none":
                continue
            n_none_rows += 1
            note = str(row.get("note") or row.get("notes") or "").lower()
            if not note:
                continue
            n_none_rows_with_note += 1
            for label, kws in KEYWORDS.items():
                if any(kw in note for kw in kws):
                    hits[label] += 1
    return {
        "n_none_rows": n_none_rows,
        "n_none_rows_with_free_text_note": n_none_rows_with_note,
        "keyword_hits_ranked": hits.most_common(),
        "caveat": "keyword sweep over free text, not a parse; a note can "
                   "match zero or multiple keywords; counts are a hint, "
                   "n_relevant = n_none_rows_with_free_text_note.",
    }


# --------------------------------------------------------------------------
# 2. THE PRECISION PRIZE -- refused symbol-days priced against the book
# --------------------------------------------------------------------------

def load_book():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    return blob["meta"], blob["trades"]


def precision_prize():
    pool = mp.canonical_pool()
    refused = {k: e for k, e in pool.items() if e.grade == "none"}
    x_only_keys = mp.x_only_days(pool)
    explicit_keys = set(refused) - x_only_keys

    meta, rows = load_book()
    sessions = meta.get("sessions") or len({r["day"] for r in rows})

    by_symday = defaultdict(list)
    for r in rows:
        by_symday[(r["sym"], r["day"])].append(r)

    def key_to_symday(k):
        sym, date = k.split("_", 1)
        return (sym, date)

    refused_symdays = {key_to_symday(k) for k in refused}
    explicit_symdays = {key_to_symday(k) for k in explicit_keys}
    x_only_symdays = {key_to_symday(k) for k in x_only_keys}

    # does the book even cover this symbol-day at all (any row, fired or not)?
    covered = {sd for sd in refused_symdays if sd in by_symday}

    # trades the engine actually TOOK on a refused symbol-day
    traded_on_refused = []
    fired_but_skipped_on_refused = 0
    for sd in refused_symdays:
        for r in by_symday.get(sd, ()):
            if r.get("status") == "fired" and r.get("traded"):
                traded_on_refused.append(r)
            elif r.get("status") == "fired":
                fired_but_skipped_on_refused += 1

    # same, restricted to EXPLICIT day-level refusals only (excludes X-only
    # "this specific detection was wrong" rows, per marks_pool's own
    # separation rule -- an X-only day is not "he refused the day")
    traded_on_explicit_refused = []
    for sd in explicit_symdays:
        for r in by_symday.get(sd, ()):
            if r.get("status") == "fired" and r.get("traded"):
                traded_on_explicit_refused.append(r)

    # the cleanest cut: the FIRST-OF-DAY arm (the actual one-trade-a-day
    # candidate stream) restricted to sessions that fall on a refused day --
    # this is literally "the trade the day-policy would have taken on a day
    # Austin said no to"
    firsts = first_of_day_arm(rows)
    firsts_on_refused = [f for f in firsts if (f["sym"], f["day"]) in refused_symdays]
    firsts_on_explicit_refused = [f for f in firsts if (f["sym"], f["day"]) in explicit_symdays]
    firsts_not_refused = [f for f in firsts if (f["sym"], f["day"]) not in refused_symdays]

    sb_all_firsts = ev_r_scoreboard(firsts, sessions=sessions)
    sb_refused_firsts = ev_r_scoreboard(firsts_on_refused, sessions=len(firsts_on_refused) or None)
    sb_explicit_refused_firsts = ev_r_scoreboard(firsts_on_explicit_refused, sessions=len(firsts_on_explicit_refused) or None)
    sb_not_refused_firsts = ev_r_scoreboard(firsts_not_refused, sessions=len(firsts_not_refused) or None)

    sb_traded_on_refused = ev_r_scoreboard(traded_on_refused, sessions=len(traded_on_refused) or None)
    sb_traded_on_explicit_refused = ev_r_scoreboard(traded_on_explicit_refused, sessions=len(traded_on_explicit_refused) or None)

    return {
        "n_refused_symbol_days_canonical": len(refused),
        "n_refused_symbol_days_explicit_none": len(explicit_symdays),
        "n_refused_symbol_days_X_only_engine_refusal": len(x_only_symdays),
        "n_refused_symbol_days_covered_by_book": len(covered),
        "n_refused_symbol_days_NOT_in_book_window": len(refused_symdays) - len(covered),
        "engine_fired_but_skipped_on_refused_days": fired_but_skipped_on_refused,
        "engine_TRADED_on_refused_days": {
            "n_trades": len(traded_on_refused),
            "n_distinct_symbol_days": len({(r["sym"], r["day"]) for r in traded_on_refused}),
            "scoreboard": sb_traded_on_refused,
        },
        "engine_TRADED_on_EXPLICIT_refused_days_only": {
            "n_trades": len(traded_on_explicit_refused),
            "scoreboard": sb_traded_on_explicit_refused,
        },
        "first_of_day_arm": {
            "all_sessions": {"n": len(firsts), "scoreboard": sb_all_firsts},
            "on_refused_days": {"n": len(firsts_on_refused), "scoreboard": sb_refused_firsts},
            "on_explicit_refused_days_only": {"n": len(firsts_on_explicit_refused), "scoreboard": sb_explicit_refused_firsts},
            "on_NOT_refused_days": {"n": len(firsts_not_refused), "scoreboard": sb_not_refused_firsts},
        },
    }


def main():
    tax = taxonomy_report()
    print("=== TAXONOMY -- refusal reasons, clustered and ranked ===")
    print("rows in corpus: %d, rows carrying a structured refusal field: %d"
          % (tax["n_rows_total_corpus"], tax["n_rows_with_any_structured_refusal_field"]))
    for bucket, c in tax["clustered_ranked"]:
        print("  %-32s %d" % (bucket, c))

    prose = prose_scan()
    print("\n=== PROSE SCAN (hint only, n_relevant=%d) ===" % prose["n_none_rows_with_free_text_note"])
    for label, c in prose["keyword_hits_ranked"]:
        print("  %-16s %d" % (label, c))

    prize = precision_prize()
    print("\n=== PRECISION PRIZE ===")
    print(json.dumps(prize, indent=2, sort_keys=False, default=str))

    out = {
        "taxonomy": tax,
        "prose_scan": prose,
        "precision_prize": prize,
    }
    outpath = os.path.join(HERE, "g112_refusal_taxonomy.json")
    with open(outpath, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    print("\nwrote", outpath)


if __name__ == "__main__":
    main()
