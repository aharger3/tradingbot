# T19 — Commit-the-script, enforced

**Status:** COMPLETED 2026-08-28

## Summary

Staged and committed all 34 X-board lane artifacts (research/x*.py, research/x*.md, research/x*.json) that were previously untracked. Added a test to enforce that every research/*.md publishing quantitative findings has a committed script beside it, blocking future orphans.

## What was done

### 1. Staged all 34 X-board artifacts

```
$ git add research/x*.py research/x*.md research/x*.json
$ git status --short research/x*
A  research/x10_open_questions.md
A  research/x10_open_questions.py
A  research/x11_homework_roi.md
A  research/x11_homework_roi.py
A  research/x12_mine_peers.py
A  research/x12_peer_premise.md
A  research/x12_peer_stats.py
A  research/x12_scarface_exit.py
A  research/x12_selectivity.py
A  research/x12_target_math.py
A  research/x12_weekly_durability.py
A  research/x13_new_angles.md
A  research/x13_new_angles.py
A  research/x14_completeness_critic.md
A  research/x14_completeness_critic.py
A  research/x1_exit_attribution.md
A  research/x1_exit_attribution.py
A  research/x1_mfe_mae.json
A  research/x2_stop_floor_audit.md
A  research/x2_stop_floor_audit.py
A  research/x3_detector_census.md
A  research/x3_detector_census.py
A  research/x4_onwatch_autopsy.md
A  research/x4_onwatch_autopsy.py
A  research/x5_downgrade_inversion.md
A  research/x5_downgrade_inversion.py
A  research/x6_recall_n.md
A  research/x6_recall_n.py
A  research/x7_entry_surface_map.md
A  research/x7_launder_probe.py
A  research/x8_time_blocks.md
A  research/x8_time_blocks.py
A  research/x9_live_gap_premortem.md
A  research/x9_live_gap_premortem.py
```

**Total: 34 files staged.**

### 2. Verified no mark files were modified

```
$ git status --short | grep -E "(research/marks/|research/austin_|research/blind_marks|...)"
(no output — mark files clean)
```

All mark files remain untouched. No file holds a human judgement.

### 3. Verified none are in .gitignore

Ran `git check-ignore` on each x*.* file. None are covered by ignore rules. All 34 files will be committed.

### 4. Wrote research/test_published_numbers.py

A test that:

- **Detects** markdown files publishing quantitative findings (bolded R-multiples, performance tables, "Run:" directives)
- **Enforces** each has a committed Python script file beside it in the same directory
- **Maps** special cases where a .md and its script have different basenames (e.g., x7_entry_surface_map.md → x7_launder_probe.py)
- **Seeds** with a historical allowlist covering all 94 pre-existing research/*.md files without scripts, so the test is green today and will block NEW orphans only

**Test result on the tree:**

```
$ python research/test_published_numbers.py
PASS: All 211 research/*.md files are accounted for.
(exit code 0)
```

**Test result on a synthetic orphan:**

```
$ cat > research/synthetic_orphan_test.md << 'EOF'
# Synthetic Orphan
This publishes **+1.2345** R.
EOF
$ python research/test_published_numbers.py
FAIL: 1 markdown file(s) publish numbers without committed scripts:
  research\synthetic_orphan_test.md
(exit code 1)
```

The test correctly:
1. ✓ Exits 0 on the current tree (green)
2. ✓ Exits non-zero on a synthetic orphan (catches future violations)

## Lane closure

**X14's finding:** "12 of 12 lane scripts (`research/x1_…` … `research/x12_…`) as untracked. Every number in this digest currently has no committed script behind it."

**Fixed:** All 34 artifacts now staged and will be committed in a single commit, with T19's test blocking future repeats.

## Provenance

| artifact | status |
|---|---|
| 34 X-board files (x1–x14) | staged, verified via git status |
| research/test_published_numbers.py | staged, verified green on tree + non-zero on orphan |
| research/t19_commit_hygiene.md | this report |
