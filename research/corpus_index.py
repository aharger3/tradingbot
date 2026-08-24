"""corpus_index.py -- provenance-tagged index over the OMEN rule-extraction corpus.

Built in response to research/t63_corpus_readiness.md: retrieval today is grep over
flat files, and nothing separates "a trader said this" from "engine code claims a
trader said this" -- the exact gap that would have handed Austin his own 25%
BAR_EXTREME_FRAC constant back to him as though the corpus had said it.

Stdlib only. No embeddings, no external service. Walks the rule-extraction docs named
in t63 (EXTRACTED_TRADING_RULES.md, scarface-rules-*.md, 84rule-sizing-dossier.md,
hallucination-audit.md, parameter_catalog_draft.md) plus signal_runner.py -- the engine
source that is itself a provenance class -- and emits one row per identifiable
quote/claim with:

    quote            the text
    source_file      relative path
    line             1-based line number
    speaker          trader/person if identifiable, else None
    cite             freeform timestamp/file citation from the source doc, else None
    topics           list of matched topic tags
    class            exactly one of TRADER_SAID / DOC_CLAIMS / CODE_COMMENT / DERIVED

Provenance classes:
    TRADER_SAID   a direct quote from a transcript, or Austin's own words
    DOC_CLAIMS    a rules/summary document asserting a trader said something,
                  without reproducing the quote
    CODE_COMMENT  a claim living in engine source (signal_runner.py) -- the class
                  that fooled the last reader. A literal Austin quote embedded in a
                  code docstring is TRADER_SAID; a paraphrase/attribution in a code
                  comment (no quote marks) is CODE_COMMENT.
    DERIVED       something inferred by an earlier extraction/audit pass
                  (hallucination-audit.md's MATCHES/DIVERGES verdicts: t63 showed
                  one of these -- "ONE re-entry" -- was an interpretive leap, not a
                  verbatim rule, so the whole file is treated as an inferred layer)

Run: python research/corpus_index.py [--out research/corpus_index.jsonl]
Writes the index and prints a one-line class breakdown to stdout.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"

# ---------------------------------------------------------------------------
# Sources named in t63_corpus_readiness.md as the rule-extraction corpus, plus
# the engine source file that is its own provenance class.
# ---------------------------------------------------------------------------
RULE_DOCS = [
    "EXTRACTED_TRADING_RULES.md",
    "scarface-rules-videos.md",
    "scarface-rules-mastermind.md",
    "scarface-rules-accelerator.md",
    "scarface-rules-coaching-bonus.md",
    "scarface-rules-youtube.md",
    "scarface-rules-discord.md",
    "84rule-sizing-dossier.md",
    "hallucination-audit.md",
    "parameter_catalog_draft.md",
]
CODE_SOURCES = ["signal_runner.py"]

DERIVED_FILES = {"hallucination-audit.md"}  # an earlier audit/extraction pass, not raw quotes

KNOWN_NAMES = [
    "Scarface", "jdub", "J-Dub", "Jack", "Hayden", "Neto", "Tony",
    "Das Wookie", "Kam", "demchy19", "Markellwhite16", "305 Trader",
    "dane", "Jay_aye11", "Joebag009", "Royal191", "Mar",
]

# ---------------------------------------------------------------------------
# Topic vocabulary -- substring match against lowercased quote text.
# ---------------------------------------------------------------------------
TOPICS = {
    "one_candle_rule": ["one candle rule", "1 candle rule", "1kind of rule", "order block"],
    "84_rule": ["84%", "84 percent", "84-percent", "re-entry", "reentry"],
    "break_retest": ["break and retest", "break-and-retest", "b&r", "breakout", "retest"],
    "reclaim": ["reclaim"],
    "displacement": ["displacement"],
    "stop": ["stop loss", "stop-loss", "stop loss", "risk level", " stop "],
    "target": ["target", "profit target", "scale", "hod", "lod", "high of day", "low of day"],
    "grading": ["a+", "a plus", "a-plus", "grade", "grading"],
    "qqq_alignment": ["qqq", "spy", "relative strength", "higher time frame", "htf"],
    "gap": ["gap"],
    "opening_play": ["opening play", "opening candle", "opening range"],
    "hammer": ["hammer"],
    "discipline": ["revenge", "max trades", "overtrad", "discipline", "stop after"],
    "choppy": ["choppy", "chop"],
    "friday": ["friday"],
    "news_day": ["news", "fomc", "cpi", "powell"],
    "size": ["size up", "sizing", "risk $", "risk a thousand", "same size"],
    "distance_tolerance": ["how far", "too far", "tolerance", "bar_extreme_frac", "0.25"],
}


def topics_for(text: str) -> list:
    low = text.lower()
    hits = []
    for tag, keywords in TOPICS.items():
        if any(kw in low for kw in keywords):
            hits.append(tag)
    return hits


def guess_speaker(citation: str, default: str = None):
    if not citation:
        return default
    # discord/dossier form: "(Person, file.json, date)" or "(Person, file.json, date -- note)"
    first = citation.split(",")[0].strip()
    for name in KNOWN_NAMES:
        if name.lower() == first.lower() or name.lower() in citation.lower():
            return name
    # first token that isn't a filename / timestamp / bare id
    if first and not re.search(r"\.(txt|json|vtt)$|^\d|^\[|^group_|^mastermind|^bonus_|^boot-camp", first, re.I):
        # looks like a plausible name (letters, short)
        if re.match(r"^[A-Za-z][A-Za-z0-9_ '.-]{1,24}$", first):
            return first
    return default


QUOTE_CITE_RE = re.compile(r'"([^"]{10,500})"\s*\(([^)]{3,200})\)')
RULE_LINE_RE = re.compile(r'^\s*-\s*Rule:\s*"(.+)"\s*$')
TIMESTAMP_LINE_RE = re.compile(r'^\s*-\s*Timestamp:\s*(.+)$')
FILE_LINE_RE = re.compile(r'^\s*-\s*File:\s*(.+)$')

CLAIM_TRIGGERS = re.compile(
    r'^(#{1,4}\s*\d*\.?\s*)?(CONFIRMED|NEW|SPLIT|DIVERGES|MATCHES|INVENTED|Implication|'
    r'Course materials|Community|Discord adds|Community-Derived|Headline)',
    re.I,
)


def rows_from_quote_citation(rel_path: str, lines: list, default_speaker: str, doc_class_override=None):
    out = []
    for i, line in enumerate(lines, start=1):
        for m in QUOTE_CITE_RE.finditer(line):
            quote, cite = m.group(1).strip(), m.group(2).strip()
            cls = doc_class_override or "TRADER_SAID"
            speaker = guess_speaker(cite, default_speaker)
            out.append({
                "quote": quote,
                "source_file": rel_path,
                "line": i,
                "speaker": speaker,
                "cite": cite,
                "topics": topics_for(quote),
                "class": cls,
            })
    return out


def rows_from_rule_blocks(rel_path: str, lines: list, default_speaker: str, doc_class_override=None):
    """EXTRACTED_TRADING_RULES.md-style block: '- Rule: "..."' followed within a
    few lines by '- Timestamp: ...' and '- File: ...'."""
    out = []
    n = len(lines)
    for i, line in enumerate(lines):
        m = RULE_LINE_RE.match(line)
        if not m:
            continue
        quote = m.group(1).strip()
        ts, fl = None, None
        for j in range(i + 1, min(i + 6, n)):
            tm = TIMESTAMP_LINE_RE.match(lines[j])
            fm = FILE_LINE_RE.match(lines[j])
            if tm and ts is None:
                ts = tm.group(1).strip()
            if fm and fl is None:
                fl = fm.group(1).strip()
            if lines[j].strip() == "" and ts and fl:
                break
        cite = " / ".join(x for x in (fl, ts) if x) or None
        cls = doc_class_override or "TRADER_SAID"
        out.append({
            "quote": quote,
            "source_file": rel_path,
            "line": i + 1,
            "speaker": default_speaker,
            "cite": cite,
            "topics": topics_for(quote),
            "class": cls,
        })
    return out


QUOTE_HEADER_RE = re.compile(r'^\*\*Quote\s+\d+\*\*\s*\(([^)]+)\):\s*$')
EM_DASH_ATTRIB_RE = re.compile(r'[—-]{1,2}\s*([A-Z][A-Za-z0-9_. ]{1,30})\s*\(')


def rows_from_quote_header_blockquote(rel_path: str, lines: list, default_speaker: str, doc_class_override=None):
    """84rule-sizing-dossier.md-style: '**Quote N** (cite):' header line followed
    by a '> ...' blockquote line holding the content (quoted or paraphrased)."""
    out = []
    n = len(lines)
    for i, line in enumerate(lines):
        hm = QUOTE_HEADER_RE.match(line.strip())
        if not hm:
            continue
        cite = hm.group(1).strip()
        j = i + 1
        while j < n and lines[j].strip() == "":
            j += 1
        if j >= n or not lines[j].strip().startswith(">"):
            continue
        content = lines[j].strip().lstrip(">").strip()
        em = EM_DASH_ATTRIB_RE.search(content)
        speaker = em.group(1).strip() if em else guess_speaker(cite, default_speaker)
        inner_quotes = re.findall(r'"([^"]{5,500})"', content)
        if inner_quotes:
            for q in inner_quotes:
                cls = doc_class_override or "TRADER_SAID"
                out.append({
                    "quote": q.strip(),
                    "source_file": rel_path,
                    "line": j + 1,
                    "speaker": speaker,
                    "cite": cite,
                    "topics": topics_for(q),
                    "class": cls,
                })
        else:
            text = re.sub(r'\*\*', '', content).strip()
            cls = doc_class_override or "DOC_CLAIMS"
            out.append({
                "quote": text[:500],
                "source_file": rel_path,
                "line": j + 1,
                "speaker": speaker,
                "cite": cite,
                "topics": topics_for(text),
                "class": cls,
            })
    return out


def rows_from_claims(rel_path: str, lines: list, already_quoted_lines: set, doc_class_override=None):
    """Narrative / table assertions with no reproduced quote -- DOC_CLAIMS unless
    the file is itself a derived-audit doc."""
    out = []
    for i, line in enumerate(lines, start=1):
        if i in already_quoted_lines:
            continue
        stripped = line.strip()
        if not stripped or '"' in stripped:
            continue
        if CLAIM_TRIGGERS.match(stripped):
            text = re.sub(r'^#{1,4}\s*', '', stripped)
            cls = doc_class_override or "DOC_CLAIMS"
            out.append({
                "quote": text[:500],
                "source_file": rel_path,
                "line": i,
                "speaker": guess_speaker(stripped, None),
                "cite": None,
                "topics": topics_for(text),
                "class": cls,
            })
    return out


def index_rule_doc(path: Path) -> list:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    override = "DERIVED" if path.name in DERIVED_FILES else None
    default_speaker = None if path.name in DERIVED_FILES else "Scarface/jdub"

    rows = []
    quoted_lines = set()

    rows_a = rows_from_rule_blocks(rel, lines, default_speaker, override)
    quoted_lines.update(r["line"] for r in rows_a)
    rows += rows_a

    rows_b = rows_from_quote_citation(rel, lines, default_speaker, override)
    quoted_lines.update(r["line"] for r in rows_b)
    rows += rows_b

    rows_d = rows_from_quote_header_blockquote(rel, lines, default_speaker, override)
    quoted_lines.update(r["line"] for r in rows_d)
    rows += rows_d

    rows_c = rows_from_claims(rel, lines, quoted_lines, override)
    rows += rows_c

    return rows


# ---------------------------------------------------------------------------
# signal_runner.py: engine source. Default class CODE_COMMENT for any
# Scarface/jdub/Austin-attributed claim without a literal quote. An Austin
# quote (either same-line "..." or an indented blockquote following an
# "Austin, YYYY-MM-DD ...:" trigger line) is TRADER_SAID -- Austin's own words,
# regardless of which file they're recorded in.
# ---------------------------------------------------------------------------
AUSTIN_TRIGGER_RE = re.compile(r'Austin,\s*\d{4}-\d{2}-\d{2}[^:]*:\s*$')
AUSTIN_INLINE_RE = re.compile(r'Austin,\s*\d{4}-\d{2}-\d{2}')
ATTRIB_RE = re.compile(
    r'\b(Scarface|jdub|J-Dub|Austin|trader|'
    r'BAR_EXTREME_FRAC|RULE84_MAX_ATTEMPTS|RULE84_LESSON|RULE84_ARM_BNR_ONLY|'
    r'STRONG_PA_MULT|SESSION_EXTREME_FRAC|tolerance unit)\b',
    re.I,
)


def index_signal_runner(path: Path) -> list:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    rows = []
    consumed = set()

    # Pass 1: Austin blockquote -- trigger line followed by an indented quote block.
    for i, line in enumerate(raw_lines):
        if not AUSTIN_TRIGGER_RE.search(line):
            continue
        trigger_indent = len(line) - len(line.lstrip())
        block = []
        j = i + 1
        while j < len(raw_lines):
            nxt = raw_lines[j]
            if nxt.strip() == "":
                if block:
                    break
                j += 1
                continue
            indent = len(nxt) - len(nxt.lstrip())
            if indent <= trigger_indent:
                break
            block.append(nxt.strip())
            consumed.add(j + 1)
            j += 1
        if block:
            quote = " ".join(block).replace("**", "").strip()
            rows.append({
                "quote": quote,
                "source_file": rel,
                "line": i + 2,
                "speaker": "Austin",
                "cite": line.strip().rstrip(":"),
                "topics": topics_for(quote),
                "class": "TRADER_SAID",
            })
            consumed.add(i + 1)

    # Pass 2: same-line quoted text with an inline Austin+date citation.
    for i, line in enumerate(raw_lines, start=1):
        if i in consumed:
            continue
        for m in re.finditer(r'"([^"]{8,300})"', line):
            quote = m.group(1).strip()
            if AUSTIN_INLINE_RE.search(line):
                rows.append({
                    "quote": quote,
                    "source_file": rel,
                    "line": i,
                    "speaker": "Austin",
                    "cite": line.strip(),
                    "topics": topics_for(quote),
                    "class": "TRADER_SAID",
                })
                consumed.add(i)

    # Pass 3: any remaining Scarface/jdub/Austin/trader-attributed comment line
    # (no literal quote captured above) -- CODE_COMMENT, the class t63 flagged.
    for i, line in enumerate(raw_lines, start=1):
        if i in consumed:
            continue
        stripped = line.strip()
        if not (stripped.startswith("#") or '"""' in stripped or stripped.startswith('"')):
            # still allow docstring body lines to qualify below via ATTRIB_RE match
            pass
        if ATTRIB_RE.search(stripped) and len(stripped) > 3:
            rows.append({
                "quote": stripped.lstrip("#").strip()[:400],
                "source_file": rel,
                "line": i,
                "speaker": None,
                "cite": None,
                "topics": topics_for(stripped),
                "class": "CODE_COMMENT",
            })

    return rows


def build(out_path: Path) -> list:
    rows = []
    for name in RULE_DOCS:
        p = RESEARCH / name
        if p.exists():
            rows.extend(index_rule_doc(p))
    for name in CODE_SOURCES:
        p = ROOT / name
        if p.exists():
            rows.extend(index_signal_runner(p))

    for idx, row in enumerate(rows):
        row["id"] = idx

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(RESEARCH / "corpus_index.jsonl"))
    args = ap.parse_args()

    rows = build(Path(args.out))

    from collections import Counter
    breakdown = Counter(r["class"] for r in rows)
    print(f"indexed {len(rows)} rows -> {args.out}")
    for cls in ("TRADER_SAID", "DOC_CLAIMS", "CODE_COMMENT", "DERIVED"):
        print(f"  {cls}: {breakdown.get(cls, 0)}")


if __name__ == "__main__":
    main()
