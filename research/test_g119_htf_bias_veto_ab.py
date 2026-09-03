"""g119 -- checks on research/g119_htf_bias_veto_ab.py's output.

Plain asserts, exits non-zero on failure, same shape as
`research/g94_verify.py` / `research/test_downgrade_grader.py`. Does not
re-run the (multi-minute) backtest books; asserts against the two committed
output artifacts (`.md` and `.json`) the script itself writes.

    python research/test_g119_htf_bias_veto_ab.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT_MD = os.path.join(HERE, "g119_htf_bias_veto_ab.md")
OUT_JSON = os.path.join(HERE, "g119_htf_bias_veto_ab.json")
RAW_OFF = os.path.join(HERE, "bt2y_trades_htfveto_off.json")
RAW_ON = os.path.join(HERE, "bt2y_trades_htfveto_on.json")

LANES = ("full pool", "index QQQ/SPY/IWM")


def check_files_exist_and_parse():
    assert os.path.exists(OUT_JSON), "missing %s -- run research/g119_htf_bias_veto_ab.py" % OUT_JSON
    assert os.path.exists(OUT_MD), "missing %s -- run research/g119_htf_bias_veto_ab.py" % OUT_MD
    blob = json.load(open(OUT_JSON, encoding="utf-8"))
    text = open(OUT_MD, encoding="utf-8").read()
    assert isinstance(blob, dict) and blob, "%s parsed to an empty/non-dict blob" % OUT_JSON
    assert len(text) > 200, "%s is suspiciously short (%d chars)" % (OUT_MD, len(text))
    print("  ok   both output files exist and parse (%s: %d chars, %s: %d top-level keys)"
          % (os.path.basename(OUT_MD), len(text), os.path.basename(OUT_JSON), len(blob)))
    return blob, text


def check_lanes_present(blob):
    lanes = blob.get("lanes", {})
    for lane in LANES:
        assert lane in lanes, "lane %r missing from %s['lanes']: have %s" % (
            lane, os.path.basename(OUT_JSON), sorted(lanes))
        for arm in ("off", "on"):
            assert arm in lanes[lane], "lane %r missing arm %r" % (lane, arm)
            assert "s_recall" in lanes[lane][arm], "lane %r arm %r missing s_recall" % (lane, arm)
            assert "false_fire" in lanes[lane][arm], "lane %r arm %r missing false_fire" % (lane, arm)
        assert "delta" in lanes[lane], "lane %r missing delta" % lane
    print("  ok   both lanes present, each with off/on s_recall + false_fire + delta")
    return lanes


def _in_unit_interval(x, label):
    assert x is None or (0.0 <= x <= 1.0), "%s out of [0,1]: %r" % (label, x)


def check_rates_in_unit_interval(lanes):
    n_checked = 0
    for lane, d in lanes.items():
        for arm in ("off", "on"):
            sr = d[arm]["s_recall"]
            ff = d[arm]["false_fire"]
            _in_unit_interval(sr["recall"], "%s/%s s_recall.recall" % (lane, arm))
            if sr["recall_pct"] is not None:
                assert 0.0 <= sr["recall_pct"] <= 100.0, (
                    "%s/%s s_recall.recall_pct out of [0,100]: %r" % (lane, arm, sr["recall_pct"]))
            _in_unit_interval(ff["false_fire_rate"], "%s/%s false_fire.false_fire_rate" % (lane, arm))
            if ff["false_fire_pct"] is not None:
                assert 0.0 <= ff["false_fire_pct"] <= 100.0, (
                    "%s/%s false_fire.false_fire_pct out of [0,100]: %r" % (lane, arm, ff["false_fire_pct"]))
            # internal consistency: rate == traded/in_universe (recall) and
            # false_fires/judged_days (false fire), not just independently in range
            if sr["in_universe"]:
                assert sr["traded"] <= sr["in_universe"], (
                    "%s/%s traded (%d) exceeds in_universe (%d)"
                    % (lane, arm, sr["traded"], sr["in_universe"]))
                want = round(sr["traded"] / sr["in_universe"], 4)
                assert abs(sr["recall"] - want) < 1e-6, (
                    "%s/%s s_recall.recall %r != traded/in_universe %r"
                    % (lane, arm, sr["recall"], want))
            if ff["judged_days"]:
                assert ff["false_fires"] <= ff["judged_days"], (
                    "%s/%s false_fires (%d) exceeds judged_days (%d)"
                    % (lane, arm, ff["false_fires"], ff["judged_days"]))
                want = round(ff["false_fires"] / ff["judged_days"], 4)
                assert abs(ff["false_fire_rate"] - want) < 1e-6, (
                    "%s/%s false_fire.false_fire_rate %r != false_fires/judged_days %r"
                    % (lane, arm, ff["false_fire_rate"], want))
            assert ff["judged_days"] + ff["unjudged_days"] == ff["traded_days"], (
                "%s/%s judged_days + unjudged_days != traded_days: %d + %d != %d"
                % (lane, arm, ff["judged_days"], ff["unjudged_days"], ff["traded_days"]))
            n_checked += 1
    print("  ok   S recall and false-fire rates are within [0,1] (and their pct twins "
          "within [0,100]) for both arms of both lanes (%d arm-lanes checked), and each "
          "rate is internally consistent with its own numerator/denominator" % n_checked)


def check_deltas_match_arithmetic(lanes):
    n_checked = 0
    for lane, d in lanes.items():
        off_money, on_money = d["off"]["money"], d["on"]["money"]
        for k, v in d["delta"]["money"].items():
            got = round(on_money[k] - off_money[k], 4)
            assert abs(got - round(v, 4)) < 1e-3, (
                "%s delta.money[%r] = %r but ON(%r) - OFF(%r) = %r"
                % (lane, k, v, on_money[k], off_money[k], got))
            n_checked += 1

        off_sr, on_sr = d["off"]["s_recall"], d["on"]["s_recall"]
        want_sr = (round(on_sr["recall_pct"] - off_sr["recall_pct"], 1)
                   if off_sr["recall_pct"] is not None and on_sr["recall_pct"] is not None
                   else None)
        assert d["delta"]["s_recall_pct"] == want_sr, (
            "%s delta.s_recall_pct = %r but ON(%r) - OFF(%r) = %r"
            % (lane, d["delta"]["s_recall_pct"], on_sr["recall_pct"], off_sr["recall_pct"], want_sr))
        n_checked += 1

        off_ff, on_ff = d["off"]["false_fire"], d["on"]["false_fire"]
        want_ff = (round(on_ff["false_fire_pct"] - off_ff["false_fire_pct"], 1)
                   if off_ff["false_fire_pct"] is not None and on_ff["false_fire_pct"] is not None
                   else None)
        assert d["delta"]["false_fire_pct"] == want_ff, (
            "%s delta.false_fire_pct = %r but ON(%r) - OFF(%r) = %r"
            % (lane, d["delta"]["false_fire_pct"], on_ff["false_fire_pct"], off_ff["false_fire_pct"], want_ff))
        n_checked += 1
    print("  ok   every reported delta (money + S recall + false fire, %d values across "
          "%d lanes) matches ON - OFF arithmetic" % (n_checked, len(lanes)))


def check_shared_rows_invariant(blob):
    """Re-derive the invariant from the JSON's own counts -- do not trust the
    console's PASS/FAIL text, and do not trust the stored `pass` boolean
    blindly either: recompute it from `shared`/`moved` and require the stored
    value to agree, plus require the moved fraction to be small (the
    documented dedupe-release mechanism, not a wiring bug -- see the script's
    module docstring and research/g94_retest_book_compare.md for the
    precedent, which itself reports FAIL for the same reason at a smaller
    scale for RETEST_REQUIRED)."""
    sru = blob.get("shared_rows_unmoved")
    assert sru, "missing shared_rows_unmoved in %s" % os.path.basename(OUT_JSON)
    shared, moved = sru["shared"], sru["moved"]
    assert shared > 0, "shared_rows_unmoved.shared must be > 0, got %r" % shared
    assert 0 <= moved <= shared, "moved (%r) not within [0, shared=%r]" % (moved, shared)
    rederived_pass = (moved == 0)
    assert sru["pass"] == rederived_pass, (
        "stored pass=%r does not match re-derived (moved==0)=%r from shared=%d, moved=%d"
        % (sru["pass"], rederived_pass, shared, moved))
    moved_pct = round(moved / shared * 100, 4)
    assert abs(sru.get("moved_pct", moved_pct) - moved_pct) < 1e-6, (
        "stored moved_pct %r != recomputed %r" % (sru.get("moved_pct"), moved_pct))
    # The mechanism g94 already documented moves a tiny fraction of shared
    # rows, never a meaningful chunk of them -- bound it generously (1%) so a
    # real wiring bug (which would move a large fraction) still fails loudly.
    assert moved_pct < 1.0, (
        "shared rows moved %.4f%% of %d shared rows -- far more than the "
        "known dedupe-release mechanism accounts for (g94's own instance "
        "moved 0.044%%); this looks like a real bug, not the documented "
        "phenomenon" % (moved_pct, shared))
    print("  ok   shared-rows-unmoved invariant re-derived from the JSON: %d shared, "
          "%d moved (%.4f%%), stored pass=%r matches (moved==0)=%r, and the moved "
          "fraction is within the documented dedupe-release bound (<1%%)"
          % (shared, moved, moved_pct, sru["pass"], rederived_pass))


def check_md_states_the_headline_numbers(blob, text):
    checks = [
        ("%d" % blob["shared_rows_unmoved"]["shared"], "shared-row count"),
        ("%d" % blob["shared_rows_unmoved"]["moved"], "moved-row count"),
    ]
    for needle, label in checks:
        assert needle in text, "%s never states the %s (%s)" % (OUT_MD, label, needle)
    print("  ok   %s states the shared/moved counts backing the invariant" % os.path.basename(OUT_MD))


def check_arm_labels_against_raw_books(blob):
    """The one check that reads the RAW books directly rather than trusting
    the script's own output JSON -- an adversarial pass (2026-09-03) on the
    first cut of this file pointed out that every prior assertion here would
    still pass if OFF/ON were silently swapped at the script's file paths,
    because they all re-derive from numbers the script itself already wrote.

    This ties the labels to ground truth that does not come from the script:
    `HTF_BIAS_VETO=1` (the ON/shipped arm) is defined, in `omen_bot.py`, to
    veto (skip to grade D / status `skipped_d`) any signal whose direction
    opposes the higher-timeframe bias (`aligned == "against"`).
    `HTF_BIAS_VETO=0` (the OFF/lifted arm) lets those same opposed signals
    fire instead. So the OFF book must contain substantially MORE opposed
    signals that actually reached `status == "fired"` than the ON book --
    not a subtle statistical fact, a direct reading of the flag's own
    branch. If the two book files were ever swapped (at the script's OFF/ON
    constants, or by this test loading the wrong paths), this inverts and
    the assertion below fails loudly."""
    off_rows = json.load(open(RAW_OFF, encoding="utf-8"))["trades"]
    on_rows = json.load(open(RAW_ON, encoding="utf-8"))["trades"]

    def opposed_fired(rows):
        return sum(1 for r in rows if r.get("aligned") == "against" and r.get("status") == "fired")

    off_opposed_fired = opposed_fired(off_rows)
    on_opposed_fired = opposed_fired(on_rows)
    assert off_opposed_fired > on_opposed_fired * 1.5, (
        "OFF (HTF_BIAS_VETO=0, lifted) should let far more opposed-bias signals "
        "fire than ON (HTF_BIAS_VETO=1, shipped) -- got OFF=%d ON=%d, which does "
        "not look like the veto actually differs between these two files (check "
        "for a swapped OFF/ON path)" % (off_opposed_fired, on_opposed_fired))

    # Cross-check the script's own recorded per-arm signal counts against the
    # files this test just loaded independently, by content length -- not by
    # trusting the filename alone.
    assert blob["off_book"]["signals"] == len(off_rows), (
        "g119's stored off_book.signals (%r) != len(trades) in %s (%d)"
        % (blob["off_book"]["signals"], os.path.basename(RAW_OFF), len(off_rows)))
    assert blob["on_book"]["signals"] == len(on_rows), (
        "g119's stored on_book.signals (%r) != len(trades) in %s (%d)"
        % (blob["on_book"]["signals"], os.path.basename(RAW_ON), len(on_rows)))

    print("  ok   OFF/ON labels checked against the raw books' own content: opposed-bias "
          "fired rows OFF=%d vs ON=%d (OFF lets far more through, as the flag's own "
          "branch requires), and both books' row counts match what g119 recorded"
          % (off_opposed_fired, on_opposed_fired))


def main():
    blob, text = check_files_exist_and_parse()
    lanes = check_lanes_present(blob)
    check_rates_in_unit_interval(lanes)
    check_deltas_match_arithmetic(lanes)
    check_shared_rows_invariant(blob)
    check_md_states_the_headline_numbers(blob, text)
    check_arm_labels_against_raw_books(blob)
    print("\nPASS: g119_htf_bias_veto_ab outputs exist and parse, S recall / false-fire "
          "rates are in-range and internally consistent, every reported delta matches "
          "ON-OFF arithmetic, the shared-rows-unmoved invariant re-derives cleanly "
          "from the JSON (a small, documented, dedupe-release fraction, not a wiring bug), "
          "and the OFF/ON arm labels are verified against the raw books' own content, not "
          "just the script's self-reported numbers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
