"""No number without its script.

    python research/test_provenance.py            # the gate
    python research/test_provenance.py --list     # what fails, and why
    python research/test_provenance.py --freeze   # rewrite the grandfather list

CLAUDE.md: *"Reproducibility is not assumed: 5.2's committed scale-out table could
not be regenerated from committed code. If you publish a number, commit the script
that made it."* Nothing enforced that, and it has bitten three times -- the 5.2
scale-out table, a stale flip file, and source edits that never landed in the
working tree.

The rule, stated so a machine can check it: **a report in `research/` that states a
headline number must, in the same file, name the script that produced it and the
commit it was produced at.**

- headline number = an R-multiple (`+0.957R`), a win rate or share (`53.2%`), or a
  sample size (`n=1016`). Those are the three shapes every finding in this repo is
  published in.
- names the script = a `research/*.py` or top-level `*.py` path appears in the file.
- names the commit = a 7-40 char hex sha, or the literal `_this commit_`, which is
  how TASKS.md rows are written before the hash exists.

Existing reports are grandfathered in KNOWN_UNPROVENANCED so the gate is green today
and tightens over time. A report written after this gate landed is NOT eligible --
add the provenance line, do not add the filename to the list.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

NUMBER = re.compile(r"[-+]?\d+\.\d+R\b|\b\d{1,3}\.\d\s?%|\bn\s?=\s?\d{2,}")
SCRIPT = re.compile(r"\b(?:research/)?[a-z0-9_]+\.py\b")
COMMIT = re.compile(r"\b[0-9a-f]{7,40}\b|_this commit_")

# Reports that predate this gate. Each line is a filename and the reason it is
# here. Shrink this list; never grow it.
KNOWN_UNPROVENANCED = {
    "84rule-sizing-dossier.md",  # pre-gate: no script named
    "_run1_h3_veto.md",  # pre-gate: no commit named
    "_run1_h5_frontrun.md",  # pre-gate: no commit named
    "_run1_h9_confluence.md",  # pre-gate: no commit named
    "_run1_h_intrabar.md",  # pre-gate: no commit named
    "_run1_target_autopsy.md",  # pre-gate: no commit named
    "a3_composition_check.md",  # pre-gate: no commit named
    "aplus-inversion-audit.md",  # pre-gate: no commit named
    "b4_baseline_report.md",  # pre-gate: no script named
    "b4_grade_fix_ab.md",  # pre-gate: no commit named
    "b4_gradefix_report.md",  # pre-gate: no script named
    "c10_strict_gradefix_report.md",  # pre-gate: no script named
    "c10_synthesis.md",  # pre-gate: no commit named
    "c1_displacement_gate_ab.md",  # pre-gate: no commit named
    "c1_off_report.md",  # pre-gate: no script named
    "c1_on_report.md",  # pre-gate: no script named
    "c2_fvg_displacement_ab.md",  # pre-gate: no commit named
    "c3_tag_split.md",  # pre-gate: no commit named
    "c4_puts_decision.md",  # pre-gate: no commit named
    "c5_htf_gate_ab.md",  # pre-gate: no commit named
    "c6_symbol_attribution.md",  # pre-gate: no commit named
    "c7_dow_split.md",  # pre-gate: no commit named
    "c8_loss_halt_ab.md",  # pre-gate: no commit named
    "c9_baseline_report.md",  # pre-gate: no script named
    "c9_off_report.md",  # pre-gate: no script named
    "c9_rule84_strict_ab.md",  # pre-gate: no commit named
    "c9_strict_report.md",  # pre-gate: no script named
    "corpus_miss_autopsy.md",  # pre-gate: no commit named
    "corpus_recall.md",  # pre-gate: neither script nor commit named
    "d1_scarface_contract_ab.md",  # pre-gate: no commit named
    "d2_sscore_sizing_ab.md",  # pre-gate: no commit named
    "d3_risk_of_ruin.md",  # pre-gate: no commit named
    "deepseek-spec-2.md",  # pre-gate: no script named
    "deepseek-spec-4.md",  # pre-gate: no commit named
    "detect_wide.md",  # pre-gate: no commit named
    "downgrade_tune.md",  # pre-gate: no commit named
    "engine_recall.md",  # pre-gate: neither script nor commit named
    "f1_walkforward.md",  # pre-gate: no commit named
    "fable-spec-2026-07-12.md",  # pre-gate: no commit named
    "g5_youtube_remainder.md",  # pre-gate: no commit named
    "g7_exit_sweep.md",  # pre-gate: no commit named
    "h3_veto.md",  # pre-gate: no commit named
    "h5_frontrun.md",  # pre-gate: no commit named
    "h9_confluence.md",  # pre-gate: no commit named
    "h_intrabar.md",  # pre-gate: no commit named
    "hallucination-audit.md",  # pre-gate: no commit named
    "next-session-brief.md",  # pre-gate: no commit named
    "omen_test1.md",  # pre-gate: no commit named
    "p10_structure_trail.md",  # pre-gate: no commit named
    "p11_parameter_provenance.md",  # pre-gate: no commit named
    "p12_sample_floor.md",  # pre-gate: no commit named
    "p18_p19_new_variables.md",  # pre-gate: no commit named
    "p20_sequence_gate.md",  # pre-gate: no commit named
    "p21_target_availability.md",  # pre-gate: no commit named
    "p23_combined_arms.md",  # pre-gate: no commit named
    "p2_threshold_sweep.md",  # pre-gate: no commit named
    "p3_confluence.md",  # pre-gate: no commit named
    "p7_84_rule.md",  # pre-gate: no commit named
    "p8_scratch.md",  # pre-gate: no commit named
    "parameter_catalog_draft.md",  # pre-gate: no commit named
    "qqq-alignment-rules.md",  # pre-gate: neither script nor commit named
    "recall_ab.md",  # pre-gate: no commit named
    "recall_off.md",  # pre-gate: neither script nor commit named
    "recall_on.md",  # pre-gate: neither script nor commit named
    "s_gate_spec.md",  # pre-gate: neither script nor commit named
    "scarface-rules-accelerator.md",  # pre-gate: no script named
    "scarface-rules-coaching-bonus.md",  # pre-gate: no script named
    "scarface-rules-mastermind.md",  # pre-gate: neither script nor commit named
    "scarface-rules-videos.md",  # pre-gate: neither script nor commit named
    "t11_s_quality.md",  # pre-gate: neither script nor commit named
    "t3_consolidation_effect.md",  # pre-gate: no commit named
    "t3_session_extreme.md",  # pre-gate: neither script nor commit named
    "t4_geometry_fix.md",  # pre-gate: no commit named
    "t4_stop_on_close.md",  # pre-gate: neither script nor commit named
    "t51_eye_match.md",  # pre-gate: no commit named
    "t51_fill.md",  # pre-gate: neither script nor commit named
    "t51_index_funnel.md",  # pre-gate: no commit named
    "t51_vs_t50.md",  # pre-gate: no commit named
    "t60_baseline.md",  # pre-gate: no commit named
    "t60_coverage.md",  # pre-gate: no commit named
    "t62_veto_autopsy.md",  # pre-gate: no commit named
    "t65_execution_architecture.md",  # pre-gate: no commit named
    "t66_downgrade_measure.md",  # pre-gate: no commit named
    "t70_metric_sweep.md",  # pre-gate: no commit named
    "t71_near_miss.md",  # pre-gate: no commit named
    "t7_pools.md",  # pre-gate: neither script nor commit named
    "t8_ev.md",  # pre-gate: neither script nor commit named
    "t8_power.md",  # pre-gate: neither script nor commit named
    "t8_rule84.md",  # pre-gate: no commit named
    "t8_significance.md",  # pre-gate: neither script nor commit named
    "t8_two_year.md",  # pre-gate: neither script nor commit named
    "target_autopsy.md",  # pre-gate: no commit named
    "v37_verdict.md",  # pre-gate: no commit named
    "v38_verdict.md",  # pre-gate: no commit named
    "v39_verdict.md",  # pre-gate: no commit named
    "v51_verdict.md",  # pre-gate: neither script nor commit named
    "video_ladder.md",  # pre-gate: no commit named
    "vision_ladder.md",  # pre-gate: no commit named
}

FREEZE_MARK = "    # populated by --freeze on the commit that introduced this gate\n"


def offenders():
    """(path, has_number, has_script, has_commit) for every failing report."""
    bad = []
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".md"):
            continue
        text = io.open(os.path.join(HERE, name), encoding="utf-8",
                       errors="replace").read()
        if not NUMBER.search(text):
            continue                      # states no headline number, nothing to prove
        has_script = bool(SCRIPT.search(text))
        has_commit = bool(COMMIT.search(text))
        if has_script and has_commit:
            continue
        bad.append((name, has_script, has_commit))
    return bad


def freeze():
    """Rewrite KNOWN_UNPROVENANCED from what fails right now."""
    bad = offenders()
    lines = []
    for name, has_script, has_commit in bad:
        why = ("no commit named" if has_script else
               "no script named" if has_commit else
               "neither script nor commit named")
        lines.append('    "%s",  # pre-gate: %s\n' % (name, why))
    path = os.path.abspath(__file__)
    src = io.open(path, encoding="utf-8").read()
    start = src.index("KNOWN_UNPROVENANCED = {") + len("KNOWN_UNPROVENANCED = {\n")
    end = src.index("}", start)
    src = src[:start] + "".join(lines or [FREEZE_MARK]) + src[end:]
    io.open(path, "w", encoding="utf-8", newline="\n").write(src)
    print("froze %d grandfathered reports" % len(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    args = ap.parse_args()

    if args.freeze:
        freeze()
        return 0

    bad = [b for b in offenders() if b[0] not in KNOWN_UNPROVENANCED]

    if args.list:
        for name, has_script, has_commit in offenders():
            tag = "GRANDFATHERED" if name in KNOWN_UNPROVENANCED else "FAIL"
            print("%-14s %-46s script=%s commit=%s"
                  % (tag, name, has_script, has_commit))
        print("\n%d grandfathered, %d failing" % (len(offenders()) - len(bad), len(bad)))
        return 0

    if bad:
        print("Reports state a number but do not name the script and commit "
              "that produced it:\n")
        for name, has_script, has_commit in bad:
            missing = []
            if not has_script:
                missing.append("the script (a research/*.py path)")
            if not has_commit:
                missing.append("the commit (a sha, or `_this commit_`)")
            print("  %-46s missing %s" % (name, " and ".join(missing)))
        print("\nAdd the provenance line. Do NOT add the filename to "
              "KNOWN_UNPROVENANCED -- that list only holds reports written "
              "before this gate existed.")
        return 1

    print("provenance ok (%d reports grandfathered)" % len(KNOWN_UNPROVENANCED))
    return 0


def _selfcheck():
    """The regexes, on strings we control. These are the only thing that can
    silently rot -- a regex that stops matching turns the gate green forever."""
    assert NUMBER.search("mean +0.957R against the gate")
    assert NUMBER.search("win 53.2% over the book")
    assert NUMBER.search("tripped (n=1016) versus clean")
    assert not NUMBER.search("ticket 19 closed on 2026")   # a bare year is not a finding
    assert SCRIPT.search("see `research/p20_sequence_gate.py` for the rig")
    assert SCRIPT.search("regenerate with backtest_2y.py")
    assert COMMIT.search("committed `eff5a9e9`")
    assert COMMIT.search("| `_this commit_` |")
    assert not COMMIT.search("the gate is 2.0R and the book is short")
    print("selfcheck ok")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        sys.exit(main())
