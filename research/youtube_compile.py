"""Compile 558 YouTube transcript extractions into organized rulebook.

Reads youtube-checkpoint.json, batches extractions, calls DeepSeek per
batch for topic-organized summaries, then merges into final document.
"""
import os, json, glob, time, re, math
import openai

API_KEY = "sk-516a62fdf01b4c19af470990babd63d8"
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"
CHECKPOINT = r"C:\Users\aharg\tradingbot\research\youtube-checkpoint.json"
BATCH_DIR = r"C:\Users\aharg\tradingbot\research\youtube_batches"
OUTPUT_FILE = r"C:\Users\aharg\tradingbot\research\scarface-rules-youtube.md"
BATCH_SIZE = 30  # files per compilation call
MAX_WORKERS = 5

client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)

BATCH_PROMPT = """You are compiling Scarface/J-Dub trading rules from YouTube trading transcripts.

You will receive extractions from {count} YouTube trading session transcripts. Each extraction has verbatim quotes organized by 12 topics (NOT COVERED = topic didn't appear in that transcript).

Your job: compile these extractions into a consolidated summary for ALL {count} transcripts. For each topic:
1. List the key rules/concepts found, with the BEST (most specific/unique) verbatim quote for each
2. Always cite (filename, [timestamp]) with each quote
3. Note any patterns, contradictions, or unique insights across transcripts
4. If zero transcripts covered a topic in this batch, write "NOT COVERED IN THIS BATCH"

Output EXACT format — one section per topic, with bullet points:

### Extractions {batch_label}
**1. Break-and-retest:**
- <key finding>. "<verbatim quote>" (filename, [timestamp])
- <another key finding>...
**2. One candle rule / opening candle retest:**
...
**12. Long vs Short Playbooks:**

RULES:
- Quote VERBATIM — exact words
- Always cite (filename, [timestamp])
- Capture specific trade-review commentary (good/bad trade judgments)
- Distill, don't dump — pick the most instructive quotes, not all of them
- Do NOT fill gaps from trading knowledge"""


MERGE_PROMPT = """You are merging {count} batch summaries of Scarface/J-Dub trading rules from YouTube trading transcripts.

Each batch summary covers a subset of the ~558 YouTube transcripts. All 12 topics may appear across multiple batches with overlapping findings.

Your job: produce a single consolidated rulebook document.

Structure:
1. ## HEADLINE FINDINGS — the 5-12 most important discoveries across ALL YouTube transcripts that either:
   - CONFIRM rules from accelerator/mastermind/coaching sources (with citations)
   - CONTRADICT prior sources (label as CONTRADICTION)
   - Are NEW rules not found in prior extractions

2. For each of the 12 topics, provide a consolidated section with:
   - The key rules with best verbatim quotes
   - Cite (filename, [timestamp]) for every quote
   - Note contradictions or patterns

3. ## AMBIGUITIES — rules that are unclear, contradictory, or need clarification

Format EXACTLY like accelerater output (scarface-rules-accelerator.md). Same tone, same structure.

RULES:
- Quote VERBATIM
- Always cite (filename, [timestamp])
- Every rule backed by source
- "NOT COVERED" when absent
- Kill hallucinated rules — if no source supports it, don't write it"""


def load_extractions():
    """Load checkpoint JSON, return dict of filename -> extraction text."""
    with open(CHECKPOINT, 'r', encoding='utf-8') as f:
        state = json.load(f)
    return state["completed"]


def batch_extractions(extractions):
    """Group extractions into sequential batches."""
    items = sorted(extractions.items())  # sort by filename
    batches = []
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i:i+BATCH_SIZE]
        batches.append((i+1, min(i+BATCH_SIZE, len(items)), batch))
    return batches


def call_llm(prompt, system, max_tokens=8192):
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=max_tokens,
                timeout=180,
            )
            return r.choices[0].message.content.strip()
        except Exception as e:
            wait = 2 ** attempt
            print(f"  LLM call failed: {e}, retry in {wait}s...")
            time.sleep(wait)
    return "ERROR: LLM call failed after 3 retries"


def process_batch(batch_start, batch_end, items):
    """Process one batch of extractions through LLM."""
    # Build input: concatenate all extractions in this batch
    sections = []
    for fname, text in items:
        # Keep only the extraction body (skip heading)
        sections.append(f"--- {fname} ---\n{text}")

    chunk = "\n\n".join(sections)
    count = len(items)

    # Truncate if needed (DeepSeek has 128K context; prompt + chunks should be under)
    max_chars = 110000  # leave room for prompt
    if len(chunk) > max_chars:
        chunk = chunk[:max_chars] + "\n\n[...TRUNCATED...]"

    prompt_text = f"Extractions from transcripts {batch_start} to {batch_end} ({count} files):\n\n{chunk}"
    system = BATCH_PROMPT.format(count=count, batch_label=f"{batch_start}-{batch_end}")

    print(f"  Processing batch {batch_start}-{batch_end} ({count} files, {len(chunk)} chars)...")
    result = call_llm(prompt_text, system)
    return result


def save_batch_result(batch_idx, result):
    """Save batch result to file (for resume)."""
    os.makedirs(BATCH_DIR, exist_ok=True)
    path = os.path.join(BATCH_DIR, f"batch_{batch_idx:03d}.md")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(result)
    return path


def load_all_batch_results():
    """Load all saved batch results, return list sorted by batch index."""
    pattern = os.path.join(BATCH_DIR, "batch_*.md")
    files = sorted(glob.glob(pattern))
    results = []
    for fp in files:
        with open(fp, 'r', encoding='utf-8') as f:
            results.append(f.read())
    return results


def merge_batches(batch_results):
    """Merge all batch summaries into final document."""
    count = len(batch_results)
    combined = "\n\n---\n\n".join(batch_results)

    print(f"Merging {count} batch summaries into final document...")
    system = MERGE_PROMPT.format(count=count)
    result = call_llm(
        f"Here are {count} batch summaries from YouTube trading transcript extractions. Merge them into one consolidated rulebook document:\n\n{combined}",
        system,
        max_tokens=16384
    )
    return result


def main():
    print("Loading extractions...")
    extractions = load_extractions()
    print(f"Loaded {len(extractions)} extractions")

    # Check if batch results already exist
    existing = glob.glob(os.path.join(BATCH_DIR, "batch_*.md"))
    if existing:
        print(f"Found {len(existing)} existing batch results, skipping extraction phase")
        batch_results = load_all_batch_results()
    else:
        batches = batch_extractions(extractions)
        print(f"Processing {len(batches)} batches of ~{BATCH_SIZE} files each")

        batch_results = []
        for idx, (start, end, items) in enumerate(batches, 1):
            result = process_batch(start, end, items)
            path = save_batch_result(idx, result)
            print(f"  Batch {idx} ({start}-{end}) saved to {path}")
            batch_results.append(result)

            # Short pause between batches
            if idx < len(batches):
                time.sleep(2)

    # Merge into final document
    final = merge_batches(batch_results)

    # Add header
    header = f"""# Scarface / J-Dub Rules — YouTube Transcripts (all {len(extractions)} files, compiled 2026-07-11)

Source: `youtube_data/*_transcript.txt` — {len(extractions)} files.
Extracted via DeepSeek API (deepseek-chat), compiled from {len(batch_results)} batch summaries.
Every rule backed by verbatim quote + (filename, [timestamp]).
"NOT COVERED IN THIS SOURCE" = topic never appeared.

"""
    final = header + final

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(final)

    print(f"\n=== Done ===")
    print(f"Final output: {OUTPUT_FILE}")
    print(f"Size: {len(final)} chars, {len(final.splitlines())} lines")


if __name__ == "__main__":
    main()
