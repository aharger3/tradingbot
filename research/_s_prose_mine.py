"""_s_prose_mine.py -- one-off, read-only. Mine the PROSE of Austin's 347 S
judgements (marks_pool.canonical_pool()) and count what recurs, against the
same prose on non-S days as a control. Ad hoc for the g99 lane; not imported
elsewhere.
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_deck as bd
import marks_pool as mp

pool = mp.canonical_pool()
grade_of = {k: e.grade for k, e in pool.items()}

# ---- collect every prose string attached to each row, keyed by its judgement key
prose_by_key = defaultdict(list)   # key -> [ (source, field, text) ]

def _walk_prose(obj, field_path, out):
    if isinstance(obj, str):
        t = obj.strip()
        if len(t) >= 3:
            out.append((field_path, t))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _walk_prose(v, field_path + "." + str(k), out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_prose(v, field_path, out)

for path in bd.mark_sources():
    name = os.path.relpath(path, HERE).replace("\\", "/")
    for row in bd._rows(path):
        key = bd._judgement_key(row)
        if not key:
            continue
        texts = []
        for field in ("note", "notes", "setup"):
            if field in row:
                _walk_prose(row[field], field, texts)
        # answers.* string values (excluding pure ladder/yesno tokens which
        # are handled by grade_read -- but include them here too, cheap and
        # harmless, dedup will collapse short tokens naturally since we
        # length-filter to >=3 chars and single-word tags like "chop" DO
        # matter for this analysis)
        if isinstance(row.get("answers"), dict):
            _walk_prose(row["answers"], "answers", texts)
        for field_path, text in texts:
            prose_by_key[key].append((name, field_path, text))

# ---- bucket by canonical grade
s_keys = {k for k, g in grade_of.items() if g == "S"}
nonS_keys = {k for k, g in grade_of.items() if g != "S"}

print("S days in pool: %d" % len(s_keys))
print("S days with >=1 prose string: %d" % sum(1 for k in s_keys if prose_by_key.get(k)))
print("non-S days in pool: %d" % len(nonS_keys))
print("non-S days with >=1 prose string: %d" % sum(1 for k in nonS_keys if prose_by_key.get(k)))

def all_text_for(key):
    return " || ".join(t for _s, _f, t in prose_by_key.get(key, []))

s_corpus = {k: all_text_for(k) for k in s_keys if prose_by_key.get(k)}
nonS_corpus = {k: all_text_for(k) for k in nonS_keys if prose_by_key.get(k)}

print("S days -> total prose strings: %d" % sum(len(v) for k,v in prose_by_key.items() if k in s_keys))
print("non-S days -> total prose strings: %d" % sum(len(v) for k,v in prose_by_key.items() if k in nonS_keys))

OUT = {}
OUT["n_S_days_pool"] = len(s_keys)
OUT["n_S_days_with_prose"] = len(s_corpus)
OUT["n_nonS_days_pool"] = len(nonS_keys)
OUT["n_nonS_days_with_prose"] = len(nonS_corpus)

# ---------------------------------------------------------------- term rules
# Each rule: name -> compiled regex (case-insensitive). A day "carries" the
# term if the regex matches ANYWHERE in that day's concatenated prose (any
# row, any field, any source -- a day can be graded S in one place and carry
# a note in another).
TERMS = {
    "displacement":        r"\bdisplac\w*",
    "chop":                 r"\bchop\w*",
    "as candle forming":    r"as (the )?candle (was |is )?forming|candle forming",
    "too many candles":     r"too many candles|many candles (later|after)|\d+ candles (later|after|away)",
    "br+ocr / confluence":  r"\bconfluence\b|\bbr\s*\+\s*ocr\b|\bocr\b.*\bbr\b|\bbr\b.*\bocr\b",
    "one candle rule (ocr)":r"\bocr\b|one candle rule",
    "break and retest (br)":r"\bbr\b|break and retest|break-and-retest",
    "whole dollar level":   r"whole dollar|round number|\$\d+\.00\b|whole number",
    "hod/lod":              r"\bhod\b|\blod\b|high of (the )?day|low of (the )?day",
    "stop wording -- wick": r"\bwick\w*",
    "stop wording -- close":r"\bclose\b.*\bstop\b|\bstop\b.*\bclose\b|closes? (below|above|through)",
    "late / entry timing":  r"\blate\b|too late|entry (is |was )?\d+ candles? (earlier|later|behind)|behind",
    "exhausted / extended":  r"\bexhaust\w*|overextend\w*|too far (extended|away)",
    "level not respected":  r"level not respected|didn'?t (actually )?touch|didnt (actually )?touch|close enough|within a few cents",
    "no clear entry":       r"no clear entr\w*|no entries|no entry",
    "retest tolerance / touch": r"\btouch\w*|\bretest\w*",
    "psychological level":  r"psychological",
    "vwap":                 r"\bvwap\b",
    "pdh/pdl/pml":          r"\bpdh\b|\bpdl\b|\bpml\b|\bpmh\b|prior day high|prior day low",
    "gap":                  r"\bgap\w*",
    "trend / htf":          r"\btrend\b|\bhtf\b|higher time ?frame",
    "volume":               r"\bvolume\b",
    "reject / rejection":   r"reject\w*",
    "size of move / rr":    r"\brr\b|risk[- ]?reward|good rr|rr sucks|bad rr",
}

compiled = {name: re.compile(pat, re.IGNORECASE) for name, pat in TERMS.items()}

def day_hits(corpus):
    """key -> set(term names matched anywhere in that day's prose)."""
    out = {}
    for k, text in corpus.items():
        hits = {name for name, rx in compiled.items() if rx.search(text)}
        out[k] = hits
    return out

s_hits = day_hits(s_corpus)
nonS_hits = day_hits(nonS_corpus)

term_counts_S = Counter()
term_counts_nonS = Counter()
for hits in s_hits.values():
    term_counts_S.update(hits)
for hits in nonS_hits.values():
    term_counts_nonS.update(hits)

n_S = len(s_corpus)
n_nonS = len(nonS_corpus)

rows = []
for name in TERMS:
    s_n = term_counts_S.get(name, 0)
    ns_n = term_counts_nonS.get(name, 0)
    s_rate = s_n / n_S if n_S else 0.0
    ns_rate = ns_n / n_nonS if n_nonS else 0.0
    rows.append({
        "term": name,
        "n_S": s_n, "n_S_total": n_S, "rate_S": round(s_rate, 4),
        "n_nonS": ns_n, "n_nonS_total": n_nonS, "rate_nonS": round(ns_rate, 4),
        "lift_S_over_nonS": round((s_rate / ns_rate), 3) if ns_rate > 0 else (
            "inf" if s_rate > 0 else 0),
    })

rows.sort(key=lambda r: -r["n_S"])

print("\n%-28s %6s %8s   %6s %8s   %s" % ("term", "n_S", "rate_S", "n_nS", "rate_nS", "lift"))
for r in rows:
    print("%-28s %6d %7.1f%%   %6d %7.1f%%   %s" % (
        r["term"], r["n_S"], 100*r["rate_S"], r["n_nonS"], 100*r["rate_nonS"], r["lift_S_over_nonS"]))

OUT["terms"] = rows

# ---- sample raw quotes per term (S-only), for the writeup
SAMPLES = {}
for name, rx in compiled.items():
    samples = []
    for k, text in s_corpus.items():
        m = rx.search(text)
        if m:
            # grab a short window around the match from the ORIGINAL row text
            # (use the shortest matching field-level string, not full concat)
            for src, field, t in prose_by_key[k]:
                if rx.search(t):
                    samples.append({"key": k, "source": src, "field": field, "text": t})
                    break
        if len(samples) >= 6:
            break
    SAMPLES[name] = samples

OUT["samples"] = SAMPLES

with open(os.path.join(HERE, "_s_prose_mine_out.json"), "w", encoding="utf-8") as fh:
    json.dump(OUT, fh, indent=2, sort_keys=False)

print("\nwrote research/_s_prose_mine_out.json")
