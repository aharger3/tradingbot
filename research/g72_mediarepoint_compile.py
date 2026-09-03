"""Compile whatever course-rule checkpoints exist right now into course_rules.jsonl/.md.
Safe to re-run at any time -- picks up new checkpoints as g72_mediarepoint_course_extract.py
writes them.
"""
import re, json
from pathlib import Path
from collections import Counter

CORPUS_SF = Path(__file__).resolve().parent / "corpus_sf"
CKPT = CORPUS_SF / "_course_extract_checkpoints"
OUT_JSONL = CORPUS_SF / "course_rules.jsonl"
OUT_MD = CORPUS_SF / "course_rules.md"

RULE_RE = re.compile(r'^-\s+\*\*(.+?)\*\*\s+"(.+?)"\s*\(([^)]+)\)\s*$')
TOPIC_RE = re.compile(r'^###\s+(.+)$')

files = sorted(CKPT.glob("*.md"))
rows = []
for f in files:
    text = f.read_text(encoding="utf-8")
    m = re.match(r"#\s+([a-z0-9-]+)_chunk", text)
    space = m.group(1) if m else f.name.split("_chunk")[0]
    topic = None
    for line in text.splitlines():
        line = line.strip()
        tm = TOPIC_RE.match(line)
        if tm:
            topic = tm.group(1).strip()
            continue
        rm = RULE_RE.match(line)
        if rm and topic and "NOT COVERED" not in topic.upper():
            rows.append(
                {
                    "space": space,
                    "topic": topic,
                    "subtopic": rm.group(1).strip(),
                    "quote": rm.group(2).strip(),
                    "source": rm.group(3).strip(),
                    "status": "candidate",
                }
            )

with open(OUT_JSONL, "w", encoding="utf-8") as fo:
    for r in rows:
        fo.write(json.dumps(r) + "\n")

by_topic = Counter(r["topic"] for r in rows)
by_space = Counter(r["space"] for r in rows)

lines = [
    "# Course-transcript rule ballot (G7.1 fix pass, key: mediarepoint)",
    "",
    f"Compiled from {len(files)} of 99 chunks covering the 107 course transcripts that were "
    "transcribed but never run through rule extraction (`research/g71_media.md`). Re-run "
    "`python research/g72_mediarepoint_course_extract.py` to pick up any remaining chunks, "
    "then `python research/g72_mediarepoint_compile.py` again -- both are idempotent and cache "
    "finished work.",
    "",
    "These are Scarface/J-Dub course statements, not Austin's marks -- ballot candidates only, "
    "same discipline as `research/corpus_sf/mentor_rules.md`. Nothing here is wired into "
    "detection.",
    "",
    f"**{len(rows)} candidate rules extracted so far** across these spaces:",
    "",
    "| space | rules |",
    "|---|---:|",
]
for sp, n in sorted(by_space.items()):
    lines.append(f"| {sp} | {n} |")
lines += ["", "## By topic", ""]
for t, n in by_topic.most_common():
    lines.append(f"- **{t}**: {n}")
lines += ["", "## All candidates", ""]
for r in rows:
    lines.append(f"- **[{r['space']}] {r['subtopic']}** \"{r['quote']}\" ({r['source']})")

OUT_MD.write_text("\n".join(lines), encoding="utf-8")
print(f"chunks compiled: {len(files)} of 99")
print(f"rules: {len(rows)}")
print(f"wrote {OUT_JSONL}")
print(f"wrote {OUT_MD}")
