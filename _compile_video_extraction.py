"""Compile all group checkpoints into scarface-rules-videos.md."""
import json, re, time
from pathlib import Path

CKPT = Path(r"C:\Users\aharg\tradingbot\research\video_transcripts\_extract_checkpoints")
OUT = Path(r"C:\Users\aharg\tradingbot\research\scarface-rules-videos.md")
EXTRACTED = Path(r"C:\Users\aharg\tradingbot\research\EXTRACTED_TRADING_RULES.md")
GROUPS = Path(r"C:\Users\aharg\tradingbot\research\video_transcripts\_extract_groups.json")

with open(GROUPS, "r", encoding="utf-8") as f:
    groups = json.load(f)

# Load all group checkpoints
results = []
for i in range(36):
    cp = CKPT / f"group_{i+1:02d}.md"
    if cp.exists():
        content = cp.read_text(encoding="utf-8")
        body = re.sub(r"^# Group \d+:.*?\n\n", "", content, count=1)
        results.append(body)
    else:
        results.append(None)
        print(f"Missing: group_{i+1:02d}.md")

# Load pre-extracted boot camp D5+D6
boot = ""
if EXTRACTED.exists():
    boot = EXTRACTED.read_text(encoding="utf-8")

# Build body
body_parts = []
for i, (r, g) in enumerate(zip(results, groups)):
    if not r:
        body_parts.append(f'\n\n---\n\n{"#"*3} GROUP {i+1}\n\n**EXTRACTION FAILED**\n')
        continue
    body_parts.append(f'\n\n---\n\n{"#"*3} GROUP {i+1}\nFiles: {", ".join(f for f in g)}\n\n{r}')

body = "\n".join(body_parts)

total_chars = sum(len(r) for r in results if r)
success = sum(1 for r in results if r)

# Build source file index
index_rows = []
for i, (r, g) in enumerate(zip(results, groups)):
    status = chr(0x2713) if r else chr(0x2717)
    f_list = ", ".join(f.replace("_transcript.txt", "") for f in g)
    index_rows.append(f"| {i+1} | {status} | {f_list} |")

index_table = "\n".join(index_rows)

# Use regular string concatenation to avoid f-string issues with unicode
output = ""
output += "# Scarface / J-Dub Canonical Rules -- Video Course Extraction\n"
output += f"## Extracted {time.strftime('%Y-%m-%d')} -- {success}/36 groups, {total_chars:,} chars\n\n"
output += "Source: 89 whisper-transcribed WAV recordings in `video_transcripts/*_transcript.txt`.\n"
output += "Every rule backed by verbatim quote + (filename, timestamp). 'NOT COVERED' = never taught in source.\n"
output += "Boot camp Day 5+6 pre-extracted from `EXTRACTED_TRADING_RULES.md`.\n\n"
output += "---\n\n"
output += "## HEADLINE FINDINGS\n\n"
output += "> Post-extraction analysis pass pending. Headline findings (new rules, contradictions with existing\n"
output += "> rulebooks, A/A+ grading evidence) compiled by Claude Code in next step after this raw extraction.\n\n"
output += "---\n\n"
output += "# EXTRACTION RESULTS\n\n"
output += body
output += "\n\n---\n\n"
output += "# PRE-EXTRACTED (Day 5 + Day 6 Boot Camp)\n\n"
output += boot if boot else "(None found)\n"
output += "\n\n---\n\n"
output += "# SOURCE FILE INDEX\n\n"
output += "| Group | Status | Files |\n|-------|--------|-------|\n"
output += index_table + "\n"

OUT.write_text(output, encoding="utf-8")
print(f"Written: {OUT} ({len(output):,} chars, {success}/36 groups)")
