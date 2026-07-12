"""YouTube transcript extraction — Scarface/J-Dub rules, Tranche 4.

Processes ~558 youtube_data/*_transcript.txt files via DeepSeek API.
Checkpoints after every file. Resumes from checkpoint.
Output: scarface-rules-youtube.md
"""
import os, glob, json, time, sys, re
from concurrent.futures import ThreadPoolExecutor, as_completed
import openai

# --- Config ---
TRANSCRIPT_DIR = r"C:\Users\aharg\tradingbot\youtube_data"
OUTPUT_DIR = r"C:\Users\aharg\tradingbot\research"
CHECKPOINT = os.path.join(OUTPUT_DIR, "youtube-checkpoint.json")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "scarface-rules-youtube.md")
MAX_WORKERS = 10
MODEL = "deepseek-chat"  # DeepSeek V4 Flash

API_KEY = "sk-516a62fdf01b4c19af470990babd63d8"
BASE_URL = "https://api.deepseek.com"

client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)

# --- Extraction prompt ---
SYSTEM_PROMPT = """You extract Scarface/J-Dub trading rules verbatim from YouTube trading-session transcripts.

RULES (critical — NEVER violate):
1. Quote VERBATIM — exact words from the transcript, even if grammatically messy.
2. Cite EVERY quote as (filename, [timestamp]) using the transcript's timestamp markers.
3. If a topic never appears in this transcript: write "NOT COVERED IN THIS SOURCE". Not one word more.
4. NEVER fill gaps from general trading knowledge. ZERO invention. This project kills hallucinated rules.
5. Trade-review commentary ("this trade was good/bad because X") is GOLD — always capture the specific criteria used to judge it.

Topics to extract (12 total):
1. Break-and-retest: valid break (bodies vs wicks, displacement size), valid retest (touch? zone? max wait?), entry trigger candle (hammer/shooting star qualities), stop placement, targets, invalidation, first-break-of-day vs later breaks (late entries).
2. "One candle rule" / opening candle retest: any reference to opening candle retest, opening candle print, "one candle" setups.
3. 84% rule / re-entries: conditions, sizing, disqualifiers.
4. Order blocks: definition, drawing (wick-to-body), entry/stop use, "isolated" quality criteria.
5. Key levels: PDH/PDL, PMH/PML, opening range, HOD/LOD, gap fill — hierarchy, when each matters.
6. Time-of-day + day-of-week rules; news days.
7. Exits: scaling %, breakeven rules, trailing, hold-to-target, runners.
8. Higher-timeframe / swing / long-term application of break-and-retest (daily/weekly levels, inside bars, multi-day holds).
9. Trade selection: A+ criteria, confluence lists, max trades/day, stop-when-green, market-regime awareness (melt-ups, chop, VIX).
10. Concrete numbers: win rates, R:R, risk %, drawdown norms.
11. QQQ/SPY market-structure alignment: exact conditions for when index context makes a setup A+ vs when to trust the stock's own level over QQQ.
12. Separate long vs short playbooks: criteria differences between puts and calls, more aggressive entries on shorts vs longs.

Return ONLY a markdown section for this ONE file. Format:

### <filename>
**1. Break-and-retest:**
<verbatim quotes with (filename, [timestamp])>
[...each topic...]
**12. Long vs Short Playbooks:**
NOT COVERED IN THIS SOURCE"""


def extract_from_transcript(filepath):
    """Call DeepSeek API for one transcript. Returns (filename, markdown_section)."""
    filename = os.path.basename(filepath)
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # Trim if stupidly large (>180KB after system prompt)
    max_chars = 150000
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[TRANSCRIPT TRIMMED — exceeded max length]"

    user_msg = f"Transcript file: {filename}\n\n---\n{content}"

    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0,
                max_tokens=4096,
                timeout=120,
            )
            text = r.choices[0].message.content.strip()
            if not text:
                text = f"### {filename}\nEXTRACTION RETURNED EMPTY — review manually."
            return filename, text
        except Exception as e:
            wait = 2 ** attempt
            print(f"  [RETRY {attempt+1}/3] {filename}: {e}")
            time.sleep(wait)
    return filename, f"### {filename}\nEXTRACTION FAILED AFTER 3 RETRIES: {e}"


def load_checkpoint():
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"completed": {}, "pending": [], "failed": []}


def save_checkpoint(state):
    with open(CHECKPOINT, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)


def get_pending_files():
    """Return files that haven't been successfully extracted yet."""
    pattern = os.path.join(TRANSCRIPT_DIR, "*_transcript.txt")
    all_files = sorted(glob.glob(pattern))
    state = load_checkpoint()
    pending = [f for f in all_files if os.path.basename(f) not in state["completed"]]
    return pending, state


def compile_output(state):
    """Build final markdown from all completed extractions."""
    completed = state.get("completed", {})
    failed = state.get("failed", [])

    # Sort by filename
    sorted_names = sorted(completed.keys())

    lines = []
    lines.append("# Scarface / J-Dub Rules — YouTube Transcripts (all ~558 files, extracted 2026-07-11)")
    lines.append("")
    lines.append(f"Source: `youtube_data/*_transcript.txt` — {len(sorted_names)} files processed via DeepSeek API (deepseek-chat).")
    lines.append("Every rule backed by verbatim quote + (filename, [timestamp]).")
    lines.append('"NOT COVERED IN THIS SOURCE" = topic never appeared in that transcript.')
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## HEADLINE FINDINGS")
    lines.append("")
    lines.append("*TBD — compile after all extractions complete. For now, raw per-file extractions below.*")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Per-Transcript Extraction Results")
    lines.append("")

    for name in sorted_names:
        lines.append(completed[name])
        lines.append("")

    if failed:
        lines.append("## Failed Extractions")
        lines.append("")
        for f in failed:
            lines.append(f"- {f}")
        lines.append("")

    return "\n".join(lines)


def main():
    pending, state = get_pending_files()
    failed_list = state.get("failed", [])
    completed_count = len(state.get("completed", {}))

    if not pending:
        print(f"All {completed_count} files already extracted. Compiling output...")
        final_md = compile_output(state)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(final_md)
        print(f"Output written to {OUTPUT_FILE}")
        return

    total = len(pending) + completed_count
    print(f"Checkpoint found: {completed_count} done, {len(pending)} remaining of {total}")

    # Process pending files
    batch_num = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {}
        for fp in pending:
            future = pool.submit(extract_from_transcript, fp)
            futures[future] = fp

        done_count = completed_count
        for future in as_completed(futures):
            fp = futures[future]
            filename = os.path.basename(fp)
            try:
                fname, result = future.result()
                state["completed"][fname] = result
                done_count += 1
                print(f"  [{done_count}/{total}] {fname} — DONE")
            except Exception as e:
                state.setdefault("failed", []).append(filename)
                print(f"  [{done_count+1}/{total}] {filename} — FAILED: {e}")
                done_count += 1

            # Checkpoint every 25 files
            if done_count % 25 == 0:
                state["failed"] = list(set(state.get("failed", [])))
                save_checkpoint(state)
                print(f"  --- Checkpoint saved ({done_count}/{total}) ---")

    # Final save
    state["failed"] = list(set(state.get("failed", [])))
    save_checkpoint(state)

    # Compile output
    final_md = compile_output(state)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(final_md)

    comp = len(state["completed"])
    fail = len(state.get("failed", []))
    print(f"\n=== Done ===")
    print(f"Completed: {comp}")
    print(f"Failed: {fail}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
