"""Extract trading rules from 89 video transcripts via DeepSeek API.

Follows deepseek-spec-4.md and deepseek-extraction-spec.md.
Processes 36 pre-batched groups with chunking for large groups.
"""
import json, os, sys, time, re
from pathlib import Path

# Force UTF-8 for stdout/stderr (avoids cp1252 on Windows)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stderr.reconfigure(encoding='utf-8')

TRANSCRIPT_DIR = Path(r"C:\Users\aharg\tradingbot\research\video_transcripts")
OUTPUT_FILE = Path(r"C:\Users\aharg\tradingbot\research\scarface-rules-videos.md")
EXTRACTED_RULES = Path(r"C:\Users\aharg\tradingbot\research\EXTRACTED_TRADING_RULES.md")
ACCELERATOR_RULES = Path(r"C:\Users\aharg\tradingbot\research\scarface-rules-accelerator.md")
GROUPS_FILE = TRANSCRIPT_DIR / "_extract_groups.json"
CHECKPOINT_DIR = TRANSCRIPT_DIR / "_extract_checkpoints"
NOTES_DIR = CHECKPOINT_DIR / "_running_notes"

DEEPSEEK_API_KEY = "sk-516a62fdf01b4c19af470990babd63d8"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Max chars of transcript text per chunk (leaves room for system prompt + output)
MAX_CHUNK_CHARS = 60000

SYSTEM_PROMPT = """You are an expert trading analyst extracting canonical rules from Scarface/J-Dub video course transcripts. Extract ONLY what the speaker teaches, backed by verbatim quotes. NEVER fill gaps from your own trading knowledge.

## HARD RULES
1. Every rule MUST cite a verbatim quote + (filename, timestamp) e.g. (boot-camp_day5.txt [443s])
2. Topic absent from transcript -> "NOT COVERED IN THIS SOURCE" — never guess
3. Never fill from general trading knowledge
4. Extraction only — no commentary or analysis
5. Trade-review commentary with specific judgment + WHY is GOLD
6. Timestamps are [Ns-Ms] format in transcripts

## EXTRACTION TOPICS
For each topic present, extract rules with citations. Topics not covered -> "NOT COVERED":

1. Break-and-retest: valid break (bodies vs wicks, displacement), valid retest (touch/zone, max wait), entry trigger (hammer/shooting star), stop placement, targets (HOD/LOD -> liquidity), first-break vs late breaks
2. One-candle-rule / opening-candle-retest: named "one candle rule" or "opening candle retest"? Exact spec. NOTE: prior accelerator extraction found NOT named OCR.
3. 84% rule / re-entries: conditions, sizing (same/bigger/smaller), disqualifiers, psychology
4. Order blocks: definition, drawing (wick-to-body), probability hierarchy, validity, confluence, entry/stop/target
5. Key levels: PDH/PDL, PMH/PML, opening range, HOD/LOD, gap fill, hierarchy, zones vs ticks, liquidity
6. Time-of-day: trade window, best days, news days (FOMC/CPI/red-folder), chart timeframe rules
7. Exits: scaling %, breakeven (when), trailing, position management
8. HTF application: weekly/daily levels, multi-day holds, HTF overriding intraday
9. Trade selection: A/A+/B/C grading criteria, confluence, max trades/day, stop-when-green, market regime
10. Concrete numbers: win rates, R:R, risk %, drawdown, gap fill stats

## SPECIAL AUDIT QUESTIONS (flag any material)
- A/A+ grading: verbatim criteria distinguishing A from A+ from B
- QQQ alignment: index confirmation rules
- Displacement/FVG: exact size definitions
- Stop-after-win / max trades/day: tier rules
- Reclaim setup: full definition + 84% mechanics

## PRIORITY
- building-your-profitable-system + hayden-s-coaching + boot-camp -> extract FULLY, be verbose (NEW material)
- mastermind-* + accelerator + bonus -> extract fully; where rule CONFIRMS existing rulebook, one line + cite is enough; spend words on NEW or CONTRADICTING
- performance-coaching -> SKIM psych, capture only methodology + trade-review judgments

## OUTPUT FORMAT
### [Topic Name]
- **[Sub-topic]** "Verbatim quote" (file.txt [Ns])
- **[Sub-topic]** "Verbatim quote" (file.txt [Ns])

After topics:
### NOT COVERED IN THIS SOURCE
[List topics 1-10 absent from this batch]"""


def load_groups():
    with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def read_transcript(filename):
    path = TRANSCRIPT_DIR / filename
    if not path.exists():
        print(f"  WARN: {filename} not found")
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def chunk_transcripts(filenames, max_chars=MAX_CHUNK_CHARS):
    """Split transcript files into chunks of ≤ max_chars each."""
    # Read all files, track sizes
    file_data = []
    for fn in filenames:
        content = read_transcript(fn)
        if content:
            file_data.append((fn, content))
        else:
            print(f"  SKIP: {fn} (not found)")

    chunks = []
    current_chunk = []
    current_size = 0

    for fn, content in file_data:
        size = len(content)
        if current_size + size > max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_size = 0
        current_chunk.append((fn, content))
        current_size += size

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def build_chunk_prompt(chunk_data, running_notes=None):
    """Build user prompt for one transcript chunk."""
    parts = []
    for fn, content in chunk_data:
        short = fn.replace('_transcript.txt', '')
        parts.append(f"=== {fn} ({short}) ===\n{content}")

    combined = "\n\n".join(parts)

    if running_notes:
        preface = f"""PREVIOUS EXTRACTION NOTES (transcripts already processed in this group):
{running_notes}

CONTINUE extraction. Add rules from these NEW transcripts. Do NOT repeat rules already in notes above. Add new topics, confirmations, or contradictions only.
"""
    else:
        preface = "Extract trading rules from these transcripts following the extraction template.\n"

    return preface + combined


def call_deepseek(messages, max_retries=3):
    """Call DeepSeek chat API with retries."""
    import urllib.request, urllib.error

    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 8192,
    }).encode('utf-8')

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    }

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                DEEPSEEK_API_URL, data=payload, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            if "choices" not in result or not result["choices"]:
                raise ValueError(f"Empty response: {result}")

            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})
            print(f"  Tokens: {usage.get('prompt_tokens','?')}->{usage.get('completion_tokens','?')}")
            return content

        except Exception as e:
            print(f"  Attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                wait = 10 * (attempt + 1)
                print(f"  Retry in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  ALL RETRIES EXHAUSTED")
                return None


def process_group(group_idx, filenames):
    """Process one group with chunking. Returns (group_idx, merged_output)."""
    print(f"\n{'='*50}")
    print(f"Group {group_idx+1}/36: {len(filenames)} files")
    for f in filenames:
        print(f"  - {f}")

    chunks = chunk_transcripts(filenames)
    print(f"  Chunks: {len(chunks)}")

    if not chunks:
        print(f"  SKIP: no readable files")
        return None

    all_outputs = []
    running_notes = None

    for ci, chunk in enumerate(chunks):
        print(f"  --- Chunk {ci+1}/{len(chunks)} ({len(chunk)} files) ---")

        user_text = build_chunk_prompt(chunk, running_notes)
        total_chars = len(SYSTEM_PROMPT) + len(user_text)
        print(f"  Total prompt size: {total_chars} chars (~{total_chars//4} tokens)")

        if total_chars > 200000:
            print(f"  WARNING: very large prompt, may exceed context")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ]

        result = call_deepseek(messages)
        if not result:
            print(f"  FAILED chunk {ci+1}")
            continue

        all_outputs.append(result)

        # Build running notes from extraction so far (extract topic headers + key findings)
        # Keep it short — just topic-level summaries
        topic_lines = []
        for line in result.split('\n'):
            line_s = line.strip()
            if line_s.startswith('### ') or line_s.startswith('## '):
                topic_lines.append(line_s[:200])
            elif line_s.startswith('- **[') or line_s.startswith('- **'):
                topic_lines.append(line_s[:200])
        running_notes = "EXTRACTED SO FAR:\n" + "\n".join(topic_lines[-30:])  # keep last 30 lines
        running_notes += f"\n\nFiles processed this group: {[f for f,_ in chunk]}"

        # Save individual chunk checkpoint
        ckpt_name = f"group_{group_idx+1:02d}_chunk{ci+1}.md"
        (CHECKPOINT_DIR / ckpt_name).write_text(
            f"# Group {group_idx+1} Chunk {ci+1}: {[f for f,_ in chunk]}\n\n{result}",
            encoding='utf-8'
        )

        time.sleep(3)  # rate limit buffer

    if not all_outputs:
        return None

    # Merge: for single chunk, return as-is; for multiple, merge unique topics
    if len(all_outputs) == 1:
        merged = all_outputs[0]
    else:
        merged_parts = []
        merged_parts.append(f"# Group {group_idx+1} — Merged from {len(all_outputs)} chunks\n")
        for oi, out in enumerate(all_outputs):
            merged_parts.append(f"\n--- Chunk {oi+1} ---\n{out}")
        merged = "\n".join(merged_parts)

    # Save full group checkpoint
    group_cp = CHECKPOINT_DIR / f"group_{group_idx+1:02d}.md"
    group_cp.write_text(
        f"# Group {group_idx+1}: {', '.join(filenames)}\n\n{merged}",
        encoding='utf-8'
    )
    print(f"  ✓ Saved group {group_idx+1} checkpoint")

    return merged


def compile_final(results, group_files):
    """Compile all group results into scarface-rules-videos.md."""
    import time as t
    print(f"\n{'='*50}")
    print("Compiling final output...")

    boot_camp_d5d6 = ""
    if EXTRACTED_RULES.exists():
        boot_camp_d5d6 = EXTRACTED_RULES.read_text(encoding='utf-8')

    # Build body — only successful groups
    body_parts = []
    for i, (result, filenames) in enumerate(zip(results, group_files)):
        if not result:
            continue
        body_parts.append(f"\n\n---\n\n### GROUP {i+1}\n"
                        f"Files: {', '.join(f for f in filenames)}\n\n{result}")

    body = "\n".join(body_parts)

    output = f"""# Scarface / J-Dub Canonical Rules — Video Course Extraction
## Extracted {t.strftime('%Y-%m-%d')} from {sum(1 for r in results if r)} groups ({sum(len(g) for g in group_files)} total files)

Source: `video_transcripts/*_transcript.txt` — whisper-transcribed WAV recordings.
Every rule backed by verbatim quote + (filename, timestamp).
Boot camp Day 5+6 pre-extracted content folded in from `EXTRACTED_TRADING_RULES.md`.

---

## HEADLINE FINDINGS

> **Post-extraction pass pending.** Headline findings (new rules, contradictions with existing rulebooks,
> A/A+ grading evidence) will be compiled by Claude Code after this raw extraction completes.
>
> For now: this is the raw, group-by-group extraction output ready for analysis.

---

# EXTRACTION RESULTS

{body}

---

# PRE-EXTRACTED (Day 5 + Day 6 Boot Camp)

{'' if 'NOT FOUND' in boot_camp_d5d6 else boot_camp_d5d6}

---

# SOURCE FILE INDEX

| Group | Files |
|-------|-------|
"""
    for i, filenames in enumerate(group_files):
        if results[i]:
            f_list = ", ".join(f.replace('_transcript.txt','') for f in filenames)
            output += f"| {i+1} | {f_list} |\n"
        else:
            output += f"| {i+1} | **FAILED** |\n"

    return output


def main():
    print("=" * 60)
    print("VIDEO TRANSCRIPT RULE EXTRACTION")
    print(f"Checkpoints: {CHECKPOINT_DIR}")
    print(f"Output: {OUTPUT_FILE}")
    print("=" * 60)

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    groups = load_groups()
    print(f"Groups: {len(groups)}, files: {sum(len(g) for g in groups)}")

    # Resume from last group checkpoint
    existing = sorted(CHECKPOINT_DIR.glob("group_??.md"))
    resume_from = 0
    if existing:
        last = existing[-1]
        m = re.search(r'group_(\d+)', last.name)
        if m:
            resume_from = int(m.group(1))
            print(f"Resume from group {resume_from+1} ({len(existing)} checkpoints exist)")

    results = []
    for i, filenames in enumerate(groups):
        if i < resume_from:
            # Load from checkpoint
            cp = CHECKPOINT_DIR / f"group_{i+1:02d}.md"
            if cp.exists():
                content = cp.read_text(encoding='utf-8')
                # Remove the header line we added
                body = re.sub(r'^# Group \d+:.*?\n\n', '', content, count=1)
                results.append(body)
                print(f"  Loaded group {i+1} from checkpoint")
            else:
                results.append(None)
            continue

        result = process_group(i, filenames)
        results.append(result)

        if i < len(groups) - 1:
            print(f"  Pause 3s...")
            time.sleep(3)

    # Compile
    success = sum(1 for r in results if r)
    fail = sum(1 for r in results if r is None)
    print(f"\n{'='*60}")
    print(f"RESULTS: {success} succeeded, {fail} failed / {len(groups)} total")

    if success > 0:
        output = compile_final(results, list(groups))
        OUTPUT_FILE.write_text(output, encoding='utf-8')
        print(f"OUTPUT: {OUTPUT_FILE} ({len(output)} chars)")
    else:
        print("NOTHING TO COMPILE — all groups failed")
        sys.exit(1)

    print("DONE — post-extraction analysis pass (headlines, audit diff) follows.")


if __name__ == "__main__":
    main()
