"""G7.1 mediarepoint fix: mine the 107 course transcripts that were transcribed and never
run through the rule-extraction pass.

Ground truth for "unmined": build the official 195-lesson transcript list from each space's
videos.json (research/g71_media_inventory.py's own slug logic), then drop any lesson whose
normalized name already appears among the 89 files cited in research/scarface-rules-videos.md
(the corpus `_extract_video_rules.py` / `_compile_video_extraction.py` already mined, from
research/video_transcripts/). This reproduces the board's research/g71_media.md breakdown
(performance-coaching 45, accelerator 27, tony-s-q-a 20, psychology-coaching 9,
technical-analysis 6 = 107; board rounded tony-s-q-a to 18 for 105 -- 2-file difference,
immaterial to the mining pass).

Output is a RULE BALLOT, not a mark file: research/corpus_sf/course_rules.jsonl (one row per
extracted rule, source-cited) and research/corpus_sf/course_rules.md (the write-up). Nothing
here is Austin's judgement and nothing is wired into detection -- same discipline as
research/corpus_sf/mentor_rules.md.

Uses DEEPSEEK_API_KEY (same vendor/model as the original 89-file pass) via raw HTTP, no new
dependency. No mark file is read or written.
"""
import json, os, re, sys, time
from pathlib import Path
from collections import Counter

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CIRCLE_DATA = ROOT / "circle_data"
TRANSCRIPTS_TEXT = CIRCLE_DATA / "transcripts_text"
MINED_CORPUS = ROOT / "research" / "video_transcripts"
CORPUS_SF = ROOT / "research" / "corpus_sf"
CHECKPOINT_DIR = CORPUS_SF / "_course_extract_checkpoints"
OUT_JSONL = CORPUS_SF / "course_rules.jsonl"
OUT_MD = CORPUS_SF / "course_rules.md"

MAX_CHUNK_CHARS = 60000
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

SYSTEM_PROMPT = """You are mining Scarface/J-Dub course transcripts for candidate trading
rules. These are BALLOT CANDIDATES, not verified truth -- extract only what the speaker
literally teaches, backed by a verbatim quote. NEVER fill gaps from your own trading
knowledge, and never invent a rule the transcript does not state.

## HARD RULES
1. Every rule MUST cite a verbatim quote + the source filename.
2. Topic absent from this transcript -> "NOT COVERED" -- never guess.
3. Extraction only -- no commentary, no grading, no opinion on whether the rule is correct.
4. If a rule contradicts common OMEN rulebook framing, extract it anyway and say so plainly
   -- contradictions are exactly what a ballot is for.

## TOPICS
1. Break-and-retest: valid break, valid retest, entry trigger, stop placement, targets
2. One-candle-rule / opening-candle-retest
3. 84% rule / re-entries: conditions, sizing, disqualifiers
4. Order blocks: definition, validity, confluence
5. Key levels: PDH/PDL/PMH/PML/opening range/HOD/LOD, hierarchy
6. Time-of-day: trade window, best days, news days
7. Exits: scaling, breakeven, trailing
8. Trade selection / grading: A/A+/B/C criteria, confluence, max trades/day, stop-when-green
9. Psychology / performance: only if it states a concrete rule of conduct, not general morale
10. Concrete numbers: win rates, R:R, risk %, drawdown stats

## OUTPUT FORMAT (markdown)
### [Topic Name]
- **[Sub-topic]** "Verbatim quote" (source_file.txt)

After topics:
### NOT COVERED IN THIS SOURCE
[list topics 1-10 absent from this transcript group]"""


def slug(n):
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")[:60]


def norm_mined_name(name):
    s = name.lower()
    s = re.sub(r"\.txt$", "", s)
    s = re.sub(r"_?transcript$", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def build_unmined_list():
    """Official lesson transcripts (from videos.json) minus the 89 already mined."""
    mined = {
        norm_mined_name(p.name) for p in MINED_CORPUS.glob("*_transcript.txt")
    }
    unmined = []
    for f in sorted(CIRCLE_DATA.glob("*/videos.json")):
        space = f.parent.name
        data = json.loads(f.read_text(encoding="utf-8"))
        for v in data:
            fn = f"{space}_{slug(v['name'])}_transcript.txt"
            p = TRANSCRIPTS_TEXT / fn
            if p.exists() and norm_mined_name(fn) not in mined:
                unmined.append((space, fn))
    return unmined


def call_deepseek(messages, api_key, max_retries=3):
    import urllib.request

    payload = json.dumps(
        {"model": "deepseek-chat", "messages": messages, "temperature": 0, "max_tokens": 8192}
    ).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(DEEPSEEK_API_URL, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})
            print(f"    tokens: {usage.get('prompt_tokens','?')}->{usage.get('completion_tokens','?')}")
            return content
        except Exception as e:
            print(f"    attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(10 * (attempt + 1))
    return None


def chunk_by_space(unmined):
    by_space = {}
    for space, fn in unmined:
        by_space.setdefault(space, []).append(fn)

    chunks = []  # list of (space, [filenames])
    for space, fnames in by_space.items():
        cur, cur_size = [], 0
        for fn in fnames:
            p = TRANSCRIPTS_TEXT / fn
            size = p.stat().st_size
            if cur and cur_size + size > MAX_CHUNK_CHARS:
                chunks.append((space, cur))
                cur, cur_size = [], 0
            cur.append(fn)
            cur_size += size
        if cur:
            chunks.append((space, cur))
    return chunks


def run_extraction(unmined, api_key, limit=None):
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    chunks = chunk_by_space(unmined)
    if limit:
        chunks = chunks[:limit]
    print(f"{len(unmined)} unmined transcripts -> {len(chunks)} chunks")

    outputs = []
    for i, (space, fnames) in enumerate(chunks):
        ckpt = CHECKPOINT_DIR / f"{space}_chunk{i:03d}.md"
        if ckpt.exists():
            outputs.append((space, fnames, ckpt.read_text(encoding="utf-8")))
            print(f"[{i+1}/{len(chunks)}] {space} ({len(fnames)} files) -- cached")
            continue

        print(f"[{i+1}/{len(chunks)}] {space} ({len(fnames)} files)")
        parts = []
        for fn in fnames:
            content = (TRANSCRIPTS_TEXT / fn).read_text(encoding="utf-8", errors="replace")
            parts.append(f"=== {fn} ===\n{content}")
        user_text = "Extract candidate rules from these course transcripts.\n\n" + "\n\n".join(parts)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]
        result = call_deepseek(messages, api_key)
        if not result:
            print(f"    FAILED, skipping")
            continue
        ckpt.write_text(f"# {space} chunk {i:03d}: {fnames}\n\n{result}", encoding="utf-8")
        outputs.append((space, fnames, result))
        time.sleep(2)
    return outputs


def rules_to_jsonl(outputs):
    rows = []
    rule_re = re.compile(r'^-\s+\*\*(.+?)\*\*\s+"(.+?)"\s*\(([^)]+)\)\s*$')
    topic_re = re.compile(r'^###\s+(.+)$')
    for space, fnames, text in outputs:
        topic = None
        for line in text.splitlines():
            line = line.strip()
            tm = topic_re.match(line)
            if tm:
                topic = tm.group(1).strip()
                continue
            rm = rule_re.match(line)
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
    return rows


def write_md(rows, unmined, chunks_done, chunks_total):
    by_topic = Counter(r["topic"] for r in rows)
    by_space = Counter(sp for sp, _ in unmined)
    lines = []
    lines.append("# Course-transcript rule ballot (G7.1 fix pass, key: mediarepoint)\n")
    lines.append(
        f"Mined {chunks_done} of {chunks_total} chunks covering the 107 course transcripts "
        "that were transcribed but never run through the rule-extraction pass "
        "(`research/g71_media.md`, section \"Rule mining\"). These are Scarface/J-Dub course "
        "statements, not Austin's marks -- ballot candidates only, same as "
        "`research/corpus_sf/mentor_rules.md`. Nothing here is wired into detection.\n"
    )
    lines.append(f"**{len(rows)} candidate rules extracted** across these spaces:\n")
    lines.append("| space | unmined transcripts | rules extracted |")
    lines.append("|---|---:|---:|")
    for space in sorted(by_space):
        lines.append(f"| {space} | {by_space[space]} | {sum(1 for r in rows if r['space']==space)} |")
    lines.append("")
    lines.append("## By topic\n")
    for topic, n in by_topic.most_common():
        lines.append(f"- **{topic}**: {n}")
    lines.append("\n## All candidates\n")
    for r in rows:
        lines.append(f"- **[{r['space']}] {r['subtopic']}** \"{r['quote']}\" ({r['source']})")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-chunks", type=int, default=None, help="cap number of chunks (for a dry run)")
    ap.add_argument("--list-only", action="store_true", help="print the unmined list and exit, no API calls")
    args = ap.parse_args()

    unmined = build_unmined_list()
    by_space = Counter(sp for sp, _ in unmined)
    print(f"unmined course transcripts: {len(unmined)}")
    for sp, n in sorted(by_space.items()):
        print(f"  {sp}: {n}")

    if args.list_only:
        sys.exit(0)

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("DEEPSEEK_API_KEY not set")
        sys.exit(1)

    all_chunks = chunk_by_space(unmined)
    outputs = run_extraction(unmined, api_key, limit=args.limit_chunks)
    rows = rules_to_jsonl(outputs)
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    write_md(rows, unmined, len(outputs), len(all_chunks))
    print(f"\nwrote {len(rows)} candidate rules -> {OUT_JSONL}")
    print(f"wrote ballot write-up -> {OUT_MD}")
