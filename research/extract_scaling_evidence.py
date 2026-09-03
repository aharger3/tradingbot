#!/usr/bin/env python3
"""extract_scaling_evidence.py -- Extract all statements about targets/scaling/exits from mark corpus.

Search every mark corpus for Austin's statements about price targets, scaling, runners, exits.
Group by rung, count supporting evidence, report strength of each claim.

Usage:
    python research/extract_scaling_evidence.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

# Keywords to search for, grouped by topic
SCALING_KEYWORDS = [
    "price target", "pt1", "pt2", "pt3", "pt4", "pt5",
    "scale", "scaling", "scaled out", "scale out",
    "runner", "runners",
    "target", "targets",
    "lod", "hod", "high of day", "low of day",
    "2r", "3r", "4r", "5r",
    "break.?even", "breakeven", "be", r"\bbe\b",
    "trail", "trailing",
    "took profit", "take profit",
    "scalp", "scalped",
    "took something off",
    "got out", "exit", "exiting",
    "whole", "all of it",
    "psych", "psychological"
]

# Mark files to search
MARK_FILES = [
    # Legacy files
    "austin_marks_v2.jsonl", "austin_marks_v3.jsonl", "austin_marks_v4.jsonl",
    "austin_marks_v5.jsonl", "austin_marks_v6.jsonl", "austin_marks_v7.jsonl",
    "blind_marks_all.jsonl", "derived_marks_v1.jsonl", "derived_marks_v2.jsonl",
    "mark_batch_02_grades.jsonl", "mark_batch_03_regrades.jsonl", "mark_batch_04_grades.jsonl",
    "marks_clean.jsonl", "recovered_reviews.jsonl",
    # Recent probes and decks (all .jsonl files in research/marks/)
]

# Add all .jsonl files from research/marks/
marks_dir = os.path.join(HERE, "marks")
if os.path.exists(marks_dir):
    for f in os.listdir(marks_dir):
        if f.endswith(".jsonl"):
            MARK_FILES.append(os.path.join("marks", f))

# Add austin_verdicts.json
MARK_FILES.append("austin_verdicts.json")


class EvidenceCollector:
    def __init__(self):
        self.statements = []  # List of (file, card_id, date, text, keyword)

    def search_text(self, text, file, card_id, date):
        """Search text for any scaling/exit keywords."""
        if not text:
            return
        text_lower = text.lower()
        for keyword in SCALING_KEYWORDS:
            if re.search(keyword, text_lower, re.IGNORECASE):
                # Found a match, record the statement
                self.statements.append({
                    'file': file,
                    'card_id': card_id or '',
                    'date': date or '',
                    'keyword': keyword,
                    'text': text[:500],  # First 500 chars of the statement
                })

    def read_jsonl(self, path):
        """Read a .jsonl file and extract all scaling-related statements."""
        full_path = os.path.join(HERE, path)
        if not os.path.exists(full_path):
            return

        print(f"Reading {path}...", file=sys.stderr)

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as e:
                        print(f"  {path}:{line_num} -- JSON error: {e}", file=sys.stderr)
                        continue

                    card_id = row.get('card_id') or row.get('id') or row.get('card') or ''
                    date = row.get('date') or row.get('day') or ''
                    symbol = row.get('symbol', '')

                    # Search in notes (most important)
                    notes = row.get('notes') or row.get('note') or ''
                    if notes:
                        self.search_text(notes, path, card_id, date)

                    # Search in answers dict
                    answers = row.get('answers', {})
                    if isinstance(answers, dict):
                        for key, val in answers.items():
                            if isinstance(val, str):
                                self.search_text(val, path, card_id, date)

                    # Search in other text fields
                    for field in ['review', 'comment', 'feedback', 'prose', 'description', 'reason']:
                        val = row.get(field)
                        if isinstance(val, str):
                            self.search_text(val, path, card_id, date)

        except Exception as e:
            print(f"Error reading {path}: {e}", file=sys.stderr)

    def read_json_list(self, path):
        """Read a .json file containing a list of records."""
        full_path = os.path.join(HERE, path)
        if not os.path.exists(full_path):
            return

        print(f"Reading {path}...", file=sys.stderr)

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                return

            for row in data:
                if not isinstance(row, dict):
                    continue

                card_id = row.get('card_id') or row.get('id') or row.get('card') or ''
                date = row.get('date') or row.get('day') or ''

                # Search in notes and other fields
                notes = row.get('notes') or row.get('note') or ''
                if notes:
                    self.search_text(notes, path, card_id, date)

                answers = row.get('answers', {})
                if isinstance(answers, dict):
                    for key, val in answers.items():
                        if isinstance(val, str):
                            self.search_text(val, path, card_id, date)

        except Exception as e:
            print(f"Error reading {path}: {e}", file=sys.stderr)


def main():
    collector = EvidenceCollector()

    # Read all mark files
    for mark_file in MARK_FILES:
        if mark_file.endswith('.json'):
            collector.read_json_list(mark_file)
        else:
            collector.read_jsonl(mark_file)

    # Group by keyword
    by_keyword = defaultdict(list)
    for stmt in collector.statements:
        by_keyword[stmt['keyword'].lower()].append(stmt)

    print("\n" + "="*80)
    print("SCALING/EXIT STATEMENTS IN CORPUS")
    print("="*80)

    # Print summary by keyword
    for keyword in sorted(by_keyword.keys()):
        stmts = by_keyword[keyword]
        print(f"\n{keyword.upper()}: {len(stmts)} statements")
        for stmt in stmts[:5]:  # Show first 5
            print(f"  [{stmt['file']}] {stmt['card_id']}/{stmt['date']}")
            print(f"    {stmt['text'][:100]}...")


if __name__ == '__main__':
    main()
