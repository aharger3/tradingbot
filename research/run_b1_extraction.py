#!/usr/bin/env python3
"""B1: Extract trading rules from 89 video transcripts (36 groups) via DeepSeek API.
Output: research/scarface-rules-videos.md"""

import json, os, sys, time, re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    os.system(f'"{sys.executable}" -m pip install requests -q')
    import requests

BASE = Path(r"C:\Users\aharg\tradingbot\research")
TRANSCRIPTS = BASE / "video_transcripts"
GROUPS_FILE = TRANSCRIPTS / "_extract_groups.json"
EXISTING_EXTRACT = BASE / "EXTRACTED_TRADING_RULES.md"
OUTPUT = BASE / "scarface-rules-videos.md"

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-516a62fdf01b4c19af470990babd63d8")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

# Progressive save
INTERIM_DIR = BASE / "_b1_interim"
INTERIM_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = """You are a trading-rule extraction engine. Extract every concrete trading rule, setup criterion, and methodology statement from the provided transcript excerpts. Hard rules:

1. **Quote verbatim** — every rule must have an exact quote + file name + timestamp marker (e.g. [Ns] from transcript). If a topic never appears: "NOT COVERED IN THIS SOURCE".
2. **NEVER fill gaps** from general trading knowledge. This is the cardinal sin — we are auditing what was actually taught vs what the bot coded. If uncertain, leave blank.
3. **Trade-review commentary** is gold: "this trade was bad because X" — always capture the criteria used to judge.
4. **Be exhaustive** for new material (topics not in existing rulebooks). For confirmation of known rules, one line + citation is enough.

Extract these topics (use headings as in the template):

## 1. Break-and-retest (core setup)
Break validity (bodies vs wicks, displacement size), retest (touch? zone? max wait?), entry trigger candle (hammer/shooting star), stop placement, targets, invalidation, first-break-of-day vs later breaks.

## 2. "One candle rule" / opening candle retest
Find any use of "one candle rule" naming and its exact spec. Opening candle retest definition.

## 3. 84% rule / re-entries
Conditions, sizing (same or larger?), disqualifiers (multiple touches? broke structure?).

## 4. Order blocks
Definition, drawing method (wick-to-body etc), entry/stop use, "isolated" quality criteria.

## 5. Key levels
PDH/PDL, PMH/PML, opening range, HOD/LOD, gap fill — hierarchy, when each matters.

## 6. Time-of-day + day-of-week rules; news days.

## 7. Exits
Scaling %, breakeven rules, trailing, hold-to-target, runners.

## 8. Higher-timeframe / swing / long-term B&R
Daily/weekly levels, inside bars, multi-day holds.

## 9. Trade selection
A+ criteria, confluence lists, max trades/day, stop-when-green, market-regime awareness (melt-ups, chop, VIX).

## 10. Concrete numbers
Win rates, R:R, risk %, drawdown norms.

## PLUS — Flagged audit topics:
- **A/A+ grading criteria** — every quote defining A vs B setup quality (backtest shows A/A+ inverted vs B)
- **QQQ alignment** — index correlation for entries
- **Displacement / FVG** — exact size/definition
- **Stop-after-win / max trades/day** — tier rules (S≥4+[hammer], max 2, stop-green)
- **Contract selection** — options strike, expiry, 0DTE vs weekly

Output format per source section: "Rule: [verbatim quote] ([File], [Timestamp])". Group by topic."""

def read_transcript(path):
    """Read transcript file, return text. Files exist or warn."""
    if not path.exists():
        print(f"  WARN: missing {path.name}")
        return f"[FILE NOT FOUND: {path.name}]"
    return path.read_text(encoding="utf-8", errors="replace")

def build_group_prompt(files_in_group):
    """Build prompt for one group of transcript files."""
    parts = []
    for fname in files_in_group:
        fpath = TRANSCRIPTS / fname
        text = read_transcript(fpath)
        # Truncate if >80K chars to avoid context limits
        if len(text) > 80000:
            text = text[:80000] + "\n\n[...TRUNCATED - file too large]"
        parts.append(f"=== FILE: {fname} ===\n{text}")

    combined = "\n\n".join(parts)
    # If whole group exceeds ~120K chars, truncate further
    if len(combined) > 120000:
        # Keep file headers but trim each file body
        print(f"  WARN: group too large ({len(combined)} chars), truncating")
        new_parts = []
        for fname in files_in_group:
            fpath = TRANSCRIPTS / fname
            text = read_transcript(fpath)
            header = f"=== FILE: {fname} ===\n"
            if len(text) > 40000:
                text = text[:40000] + f"\n\n[...TRUNCATED at 40K chars - {fname}]"
            new_parts.append(header + text)
        combined = "\n\n".join(new_parts)
        if len(combined) > 120000:
            combined = combined[:120000] + "\n\n[...FINAL TRUNCATION - group still too large]"

    return f"""Extract ALL trading rules from the following transcript file(s). Follow the extraction template topics 1-10 plus the flagged audit topics.

Transcripts:
{combined}"""

def call_deepseek(messages, max_retries=3):
    """Call DeepSeek API with messages, return content string."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 8192
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(API_URL, headers=headers, json=data, timeout=300)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            elif resp.status_code == 429:
                wait = min(30 * (attempt + 1), 120)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            else:
                print(f"  API error {resp.status_code}: {resp.text[:200]}")
                if attempt < max_retries - 1:
                    time.sleep(10)
                else:
                    return f"[EXTRACTION FAILED: HTTP {resp.status_code}]"
        except Exception as e:
            print(f"  Exception: {e}")
            if attempt < max_retries - 1:
                time.sleep(15)
            else:
                return f"[EXTRACTION FAILED: {e}]"
    return "[EXTRACTION FAILED: max retries]"

def process_group(i, files):
    """Process one group, return (group_id, markdown_section)."""
    group_id = f"g{i+1:02d}"
    group_file = INTERIM_DIR / f"{group_id}.md"

    # Check if already processed
    if group_file.exists():
        print(f"  [{group_id}] Using cached result ({len(files)} files)")
        return group_id, group_file.read_text(encoding="utf-8")

    fnames_str = ", ".join(f.name if hasattr(f, 'name') else f for f in files)
    print(f"\n[{group_id}] Processing {len(files)} files: {fnames_str[:100]}...")

    # Build messages
    user_prompt = build_group_prompt(files)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    total_chars = sum(len(read_transcript(TRANSCRIPTS / f)) for f in files)
    print(f"  Total transcript size: ~{total_chars//1000}KB")

    content = call_deepseek(messages)

    # Save interim
    group_file.write_text(content, encoding="utf-8")
    print(f"  [{group_id}] Saved ({len(content)} chars)")

    return group_id, content

def fold_existing_extraction():
    """Read the already-extracted Day 5+6 rules, return as markdown section."""
    if not EXISTING_EXTRACT.exists():
        return "## Already extracted (sources: Day 5, Day 6)\n\n[File not found]"
    text = EXISTING_EXTRACT.read_text(encoding="utf-8")
    # Reformatted section header
    return f"""## Already extracted (sources: boot-camp Day 5, Day 6)

These rules were extracted in a prior pass. Folded in unchanged.

{text}
"""

def sort_groups_by_priority(groups):
    """Sort groups per priority in deepseek-spec-4.md."""
    def priority_key(group):
        fnames = " ".join(f.lower() for f in group)
        # Priority 1: building-your-profitable-system, hayden-s-coaching, boot-camp
        if "building-your-profitable-system" in fnames: return 0
        if "hayden-s-coaching" in fnames: return 0
        if "boot-camp" in fnames: return 0
        # Priority 2: mastermind, accelerator, bonus
        if "mastermind" in fnames: return 1
        if "the-accelerator" in fnames: return 1
        if "bonus_" in fnames: return 1
        # Priority 3: performance-coaching
        if "performance-coaching" in fnames: return 2
        return 3
    return sorted(groups, key=priority_key)

def classify_source_priority(files):
    """Classify source group for labeling."""
    fnames = " ".join(f.lower() for f in files)
    if "building-your-profitable-system" in fnames: return "building-your-profitable-system"
    if "hayden-s-coaching" in fnames: return "hayden-s-coaching"
    if "boot-camp" in fnames: return "boot-camp-recordings"
    if "mastermind" in fnames: return "mastermind"
    if "the-accelerator" in fnames: return "accelerator"
    if "bonus_" in fnames: return "bonus"
    if "performance-coaching" in fnames: return "performance-coaching"
    return "other"

def main():
    print("=" * 60)
    print("B1 Extraction: 89 transcripts × 36 groups -> scarface-rules-videos.md")
    print("=" * 60)

    # Load groups
    with open(GROUPS_FILE, "r") as f:
        groups = json.load(f)
    print(f"Loaded {len(groups)} groups ({sum(len(g) for g in groups)} files)")

    # Verify files exist
    missing = []
    for group in groups:
        for fname in group:
            fpath = TRANSCRIPTS / fname
            if not fpath.exists():
                missing.append(fname)
    if missing:
        print(f"WARN: {len(missing)} files missing:")
        for m in missing[:5]:
            print(f"  - {m}")

    # Sort by priority (new material first)
    groups_sorted = sort_groups_by_priority(groups)

    # Process groups in parallel (up to 6 concurrent)
    results = []
    processed_count = 0
    cached_count = 0
    for group in groups_sorted:
        group_id = f"g{groups_sorted.index(group)+1:02d}"
        if (INTERIM_DIR / f"{group_id}.md").exists():
            cached_count += sum(1 for _ in group)

    remaining = [g for i, g in enumerate(groups_sorted) if not (INTERIM_DIR / f"g{i+1:02d}.md").exists()]
    cached_groups = [g for i, g in enumerate(groups_sorted) if (INTERIM_DIR / f"g{i+1:02d}.md").exists()]

    print(f"\nCached: {len(cached_groups)} groups, Remaining: {len(remaining)} groups")

    # Load cached results
    for i, group in enumerate(groups_sorted):
        gid = f"g{i+1:02d}"
        if group in cached_groups:
            content = (INTERIM_DIR / f"{gid}.md").read_text(encoding="utf-8")
            priority = classify_source_priority(group)
            results.append((gid, priority, group, content))

    # Process remaining in parallel
    if remaining:
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_group = {}
            for i, group in enumerate(groups_sorted):
                if group in remaining:
                    future = executor.submit(process_group, i, group)
                    future_to_group[future] = group

            for future in as_completed(future_to_group):
                group = future_to_group[future]
                try:
                    gid, content = future.result()
                    priority = classify_source_priority(group)
                    results.append((gid, priority, group, content))
                except Exception as e:
                    print(f"  FAILED group: {e}")

    # Sort results back to priority order
    def sort_key(item):
        gid, priority, group, _ = item
        idx = 0
        for j, g in enumerate(groups_sorted):
            if g is group:
                idx = j
                break
        return idx
    results.sort(key=sort_key)

    # Assemble final document
    sections = []

    # Header
    sections.append("""# Scarface / J-Dub Trading Rules — Video Transcripts (89 files, extracted 2026-07-13)

Source: `research/video_transcripts/*_transcript.txt` (89 Whisper-transcribed files across 36 batches).
Every rule is backed by a verbatim quote + (filename, timestamp marker). "NOT COVERED IN THIS SOURCE" = never taught.
Boot-camp Day 5 + Day 6 pre-extracted and folded in.

---
""")

    # HEADLINE FINDINGS — will be synthesized from all results
    sections.append("""## HEADLINE FINDINGS (for the hallucination audit)

### (a) Rules found NOWHERE in prior rulebooks

[To be determined after cross-referencing with scarface-rules-accelerator.md and other rulebooks]

### (b) Contradictions with prior rulebooks

[To be determined — attribute WHO says WHAT]

### (c) Bearing on A/A+ inversion

[To be determined — backtest shows A/A+ 30.9%W vs B 36.6%W]

---
""")

    # Main extraction sections, organized by source priority
    sections.append("""---

## PRIORITY GROUP 1: Building Your Profitable System + Hayden's Coaching + Boot Camp Recordings

These sources had NO existing rulebook coverage. Highest value — exhaustive extraction.
""")

    for gid, priority, group, content in results:
        if priority not in ("building-your-profitable-system", "hayden-s-coaching", "boot-camp-recordings"):
            continue
        fnames = ", ".join(group)
        sections.append(f"""### Group {gid}: {fnames}

{content}
""")

    sections.append("""---

## PRIORITY GROUP 2: Mastermind + Accelerator + Bonus

These are DIFFERENT recordings from the VTT-derived rulebooks. Extract fully; where a rule confirms existing rulebook entry, one line + citation is enough.
""")

    for gid, priority, group, content in results:
        if priority not in ("mastermind", "accelerator", "bonus"):
            continue
        fnames = ", ".join(group)
        sections.append(f"""### Group {gid}: {fnames}

{content}
""")

    sections.append("""---

## PRIORITY GROUP 3: Performance Coaching

SKIM — concrete methodology + trade-review judgments only.
""")

    for gid, priority, group, content in results:
        if priority != "performance-coaching":
            continue
        fnames = ", ".join(group)
        sections.append(f"""### Group {gid}: {fnames}

{content}
""")

    # Fold in existing extraction
    sections.append("\n---\n\n")
    sections.append(fold_existing_extraction())

    # Ambiguities / gaps
    sections.append("""---

## Ambiguities / gaps (remaining open questions)

[To be determined — populates after all extractions are cross-referenced with coding audit]

---
""")

    # Write output
    final_text = "\n".join(sections)
    OUTPUT.write_text(final_text, encoding="utf-8")
    print(f"\n{'=' * 60}")
    print(f"OUTPUT: {OUTPUT}")
    print(f"Total size: {len(final_text)} chars")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
