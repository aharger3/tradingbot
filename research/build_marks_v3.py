#!/usr/bin/env python3
"""Build austin_marks_v3.jsonl by merging mark_batch_02_grades into austin_marks_v2."""

import json, os, re, sys
from collections import OrderedDict

V2_PATH = "research/austin_marks_v2.jsonl"
BATCH02_PATH = "research/mark_batch_02_grades.jsonl"
HOMEWORK_PATH = "research/austin_homework_39.md"
OUT_PATH = "research/austin_marks_v3.jsonl"
REPORT_PATH = "research/t3_marks_v3.md"

# ── 1. Load v2 ──────────────────────────────────────────────────────────────
v2_rows = []
with open(V2_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            v2_rows.append(json.loads(line))

v2_by_key = {}
for r in v2_rows:
    key = (r["symbol"], r["day"], r["entry_i"])
    v2_by_key[key] = r

# ── 2. Load batch_02 ────────────────────────────────────────────────────────
batch02_rows = []
with open(BATCH02_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            batch02_rows.append(json.loads(line))

# ── 3. Merge ────────────────────────────────────────────────────────────────
overwrites = []
new_count = 0
overwrite_count = 0

merged = OrderedDict()  # key -> row, preserving v2 order then new append order
for r in v2_rows:
    key = (r["symbol"], r["day"], r["entry_i"])
    merged[key] = dict(r)  # shallow copy

for br in batch02_rows:
    key = (br["symbol"], br["day"], br["entry_i"])
    new_tier = br["austin_grade"]

    if key in merged:
        existing_tier = merged[key].get("tier")
        if existing_tier != new_tier:
            overwrites.append({
                "key": key,
                "old_tier": existing_tier,
                "new_tier": new_tier,
                "note": br.get("note"),
                "kind": br.get("kind"),
            })
            overwrite_count += 1
            merged[key]["tier"] = new_tier
            # Carry forward note/kind from batch_02 when overwriting
            if br.get("note") is not None:
                merged[key]["note"] = br["note"]
            if br.get("kind") is not None:
                merged[key]["kind"] = br["kind"]
    else:
        new_count += 1
        row = {
            "symbol": br["symbol"],
            "day": br["day"],
            "entry_i": br["entry_i"],
            "tier": new_tier,
        }
        if br.get("note") is not None:
            row["note"] = br["note"]
        if br.get("kind") is not None:
            row["kind"] = br["kind"]
        merged[key] = row

# ── 4. Homework adjustments (if file exists) ────────────────────────────────
homework_applied = False
if os.path.exists(HOMEWORK_PATH):
    homework_applied = True
    # Pattern: **SYMBOL** YYYY-MM-DD ... setup: <X> · still S? <Y>
    pattern = re.compile(
        r'\*\*(?P<symbol>[A-Z]+)\*\*\s+(?P<day>\d{4}-\d{2}-\d{2})'
        r'.*?setup:\s*(?P<setup>\S+?)'
        r'\s*[·.]\s*still\s+S\?\s*(?P<still>[^\n]+)',
        re.IGNORECASE | re.DOTALL
    )
    hw_text = open(HOMEWORK_PATH, encoding="utf-8").read()
    for m in pattern.finditer(hw_text):
        sym = m.group("symbol")
        day = m.group("day")
        setup = m.group("setup")
        still_raw = m.group("still").strip().lower()

        # Find all matching keys in merged (we don't have entry_i from homework)
        matching_keys = [k for k in merged if k[0] == sym and k[1] == day]
        for k in matching_keys:
            merged[k]["austin_setup"] = setup
            # Downgrade tier if "still S?" answer is a clear no
            if still_raw.startswith("no") or still_raw == "x" or still_raw == "n":
                merged[k]["tier"] = "X"
            elif "borderline" in still_raw or "maybe" in still_raw:
                # Borderline — downgrade S to A, leave A/X as-is
                if merged[k]["tier"] == "S":
                    merged[k]["tier"] = "A"
else:
    print("Skipping homework step: austin_homework_39.md not found.")

# ── 5. Write v3 ────────────────────────────────────────────────────────────
final_rows = list(merged.values())
with open(OUT_PATH, "w", encoding="utf-8") as f:
    for r in final_rows:
        f.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")

v2_total = len(v2_rows)
v3_total = len(final_rows)

# Per-tier breakdown
tiers_v2 = {"S": 0, "A": 0, "X": 0}
tiers_v3 = {"S": 0, "A": 0, "X": 0}
for r in v2_rows:
    t = r.get("tier", "?")
    tiers_v2[t] = tiers_v2.get(t, 0) + 1
for r in final_rows:
    t = r.get("tier", "?")
    tiers_v3[t] = tiers_v3.get(t, 0) + 1

# ── 6. Write report ─────────────────────────────────────────────────────────
lines = [
    "# T3: marks_v3 build report\n",
    f"**Date:** 2026-08-09\n",
    f"**Source:** `austin_marks_v2.jsonl` ({v2_total} rows) + `mark_batch_02_grades.jsonl` (60 rows)\n",
    f"\n",
    f"## Merge summary\n",
    f"\n",
    f"| Metric | Value |\n",
    f"|--------|-------|\n",
    f"| v2 rows | {v2_total} |\n",
    f"| batch_02 new keys appended | {new_count} |\n",
    f"| batch_02 overwrites (grade changed) | {overwrite_count} |\n",
    f"| v3 total | {v3_total} |\n",
    f"\n",
    f"**marks_v3_total: {v2_total} -> {v3_total}**\n",
    f"\n",
    f"## Per-tier breakdown\n",
    f"\n",
    f"| Tier | v2 | v3 | Δ |\n",
    f"|------|----|----|----|\n",
]

for t in ["S", "A", "X"]:
    v2c = tiers_v2.get(t, 0)
    v3c = tiers_v3.get(t, 0)
    delta = v3c - v2c
    lines.append(f"| {t} | {v2c} | {v3c} | {'+' if delta >= 0 else ''}{delta} |\n")

lines.append("\n")

if homework_applied:
    lines.append("## Homework adjustments: applied\n")
else:
    lines.append("## Homework adjustments: skipped (file not found)\n")

if overwrites:
    lines.append("## Overwrites (batch_02 grading differs from v2)\n")
    lines.append("\n")
    lines.append("| symbol | day | entry_i | old tier | new tier |\n")
    lines.append("|--------|-----|---------|----------|----------|\n")
    for ow in overwrites:
        sym, day, ei = ow["key"]
        lines.append(f"| {sym} | {day} | {ei} | {ow['old_tier']} | {ow['new_tier']} |\n")

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.writelines(lines)

print(f"Done: {v3_total} rows written (v2 had {v2_total})")
print(f"  New keys from batch_02: {new_count}")
print(f"  Overwrites (tier changed): {overwrite_count}")
print(f"  Homework: {'applied' if homework_applied else 'skipped (not found)'}")
print(f"  Tier breakdown: {tiers_v3}")