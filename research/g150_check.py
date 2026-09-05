#!/usr/bin/env python
"""
Verify that the merged g150 marks comments file is valid:
1. Row count is within 5% of the sum of the parts
2. No marks corpus files have been modified
"""

import json
import glob
import subprocess
import sys


def count_merged():
    """Count rows in merged file."""
    count = 0
    with open('research/g150_marks_comments.jsonl') as f:
        for line in f:
            count += 1
    return count


def count_parts():
    """Sum rows across all part files."""
    total = 0
    for partfile in sorted(glob.glob('research/g150_marks_comments_part*.jsonl')):
        with open(partfile) as f:
            for line in f:
                total += 1
    return total


def check_marks_unchanged():
    """Verify no marks files have been modified."""
    result = subprocess.run(
        ['git', 'status', '--porcelain', 'research/marks'],
        capture_output=True,
        text=True,
        cwd='.'
    )
    return result.stdout.strip() == ''


def main():
    merged_count = count_merged()
    parts_count = count_parts()
    
    # Deduped count should be <= parts count
    # Allow 5% variance
    tolerance = parts_count * 0.05
    diff = parts_count - merged_count
    
    print("Merged row count: {}".format(merged_count))
    print("Sum of parts: {}".format(parts_count))
    print("Deduplicated: {}".format(diff))
    print("5% tolerance: {}".format(tolerance))
    
    within_tolerance = diff <= tolerance
    print("Row count check: {} (diff={}, tolerance={})".format(
        "PASS" if within_tolerance else "FAIL",
        diff,
        tolerance
    ))
    
    marks_clean = check_marks_unchanged()
    print("Marks files unchanged: {} ('git status --porcelain research/marks' = '{}')".format(
        "PASS" if marks_clean else "FAIL",
        "" if marks_clean else "dirty"
    ))
    
    if within_tolerance and marks_clean:
        print("\nAll checks passed.")
        sys.exit(0)
    else:
        print("\nSome checks failed.")
        sys.exit(1)


if __name__ == '__main__':
    main()
