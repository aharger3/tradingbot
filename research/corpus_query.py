"""corpus_query.py -- CLI over research/corpus_index.jsonl.

Takes a question, ranks matching rows, and prints them GROUPED BY PROVENANCE
CLASS with the class shown on every line. Classes are never blended into one
undifferentiated answer -- TRADER_SAID is its own section, DOC_CLAIMS its own,
CODE_COMMENT its own, DERIVED its own. That separation is the whole point: a
naive blended answer is what would hand Austin his own engineering constant
back as though the corpus had said it (see research/t63_corpus_readiness.md).

Usage:
    python research/corpus_query.py "what is the one candle rule"
    python research/corpus_query.py "84 rule per day cap" --class TRADER_SAID
    python research/corpus_query.py "reclaim distance tolerance" --top 5

--class / --only restricts to one or more classes (comma-separated), e.g.
    --class TRADER_SAID            only the citable rows
    --class TRADER_SAID,DOC_CLAIMS drop CODE_COMMENT and DERIVED entirely

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = ROOT / "research" / "corpus_index.jsonl"

CLASS_ORDER = ["TRADER_SAID", "DOC_CLAIMS", "CODE_COMMENT", "DERIVED"]

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "does", "do", "did", "what",
    "how", "many", "times", "per", "may", "it", "can", "be", "on", "of", "to",
    "for", "and", "or", "in", "at", "this", "that", "with", "as", "by", "if",
    "you", "we", "i", "day", "trigger", "rule", "?", "question",
}


def load_index(path: Path) -> list:
    if not path.exists():
        raise SystemExit(f"index not found: {path} -- run corpus_index.py first")
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def tokenize(text: str) -> set:
    toks = re.findall(r"[a-z0-9%]+", text.lower())
    return {t for t in toks if t not in STOPWORDS and len(t) > 1}


def score_row(row: dict, query_tokens: set) -> int:
    text_tokens = tokenize(row["quote"])
    overlap = len(query_tokens & text_tokens)
    if overlap == 0:
        return 0
    score = overlap
    # topic-tag bonus: query token matches a topic name the row was tagged with
    topic_set = set(row.get("topics") or [])
    for qt in query_tokens:
        for tag in topic_set:
            if qt in tag or tag.replace("_", " ").find(qt) >= 0:
                score += 2
                break
    # exact phrase bonus (helps "84%" / "one candle rule" style queries)
    if "%" in query_tokens or any("%" in t for t in query_tokens):
        if "%" in row["quote"]:
            score += 2
    return score


def rank(rows: list, query: str, classes: set, top: int) -> dict:
    query_tokens = tokenize(query)
    if not query_tokens:
        raise SystemExit("query has no searchable terms after stripping stopwords")

    buckets = {c: [] for c in CLASS_ORDER}
    for row in rows:
        cls = row["class"]
        if classes and cls not in classes:
            continue
        s = score_row(row, query_tokens)
        if s > 0:
            buckets[cls].append((s, row))

    for cls in buckets:
        buckets[cls].sort(key=lambda sr: (-sr[0], sr[1]["source_file"], sr[1]["line"]))
        buckets[cls] = buckets[cls][:top]

    return buckets


def format_row(score: int, row: dict) -> str:
    speaker = row.get("speaker") or "?"
    cite = f" ({row['cite']})" if row.get("cite") else ""
    loc = f"{row['source_file']}:{row['line']}"
    q = row["quote"]
    if len(q) > 220:
        q = q[:217] + "..."
    return f"[{row['class']}] {loc} [{speaker}]{cite} score={score} -- {q}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="+", help="the question, free text")
    ap.add_argument("--index", default=str(DEFAULT_INDEX))
    ap.add_argument("--class", dest="classes", default="",
                     help="comma-separated provenance classes to restrict to "
                          "(TRADER_SAID,DOC_CLAIMS,CODE_COMMENT,DERIVED). Default: all, shown in separate sections.")
    ap.add_argument("--top", type=int, default=8, help="max rows per class (default 8)")
    args = ap.parse_args()

    query = " ".join(args.query)
    classes = {c.strip().upper() for c in args.classes.split(",") if c.strip()}
    bad = classes - set(CLASS_ORDER)
    if bad:
        raise SystemExit(f"unknown class(es): {bad}. Valid: {CLASS_ORDER}")

    rows = load_index(Path(args.index))
    buckets = rank(rows, query, classes, args.top)

    print(f'Q: "{query}"')
    if classes:
        print(f"(filtered to: {', '.join(sorted(classes))})")
    total = sum(len(v) for v in buckets.values())
    if total == 0:
        print("\nNo rows matched in any provenance class. UNMENTIONED in the indexed corpus --")
        print("do not synthesize an answer from other documents' interpretations.")
        return

    for cls in CLASS_ORDER:
        if classes and cls not in classes:
            continue
        section = buckets[cls]
        print(f"\n=== {cls} ({len(section)}) ===")
        if not section:
            print("  (no matches)")
            continue
        for score, row in section:
            print("  " + format_row(score, row))

    if "TRADER_SAID" not in classes and not buckets["TRADER_SAID"]:
        print("\nNOTE: zero TRADER_SAID rows matched. Any answer built from the sections above")
        print("is not a trader quote -- it is, at best, a document's claim or an engine comment.")


if __name__ == "__main__":
    main()
