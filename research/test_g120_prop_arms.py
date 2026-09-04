"""g120 -- checks on research/g120_prop_arms.py's output.

Plain asserts, exits non-zero on failure, same shape as
`research/test_g119_htf_bias_veto_ab.py` / `research/test_downgrade_grader.py`.
Does not re-run the backtest; asserts against the two committed output
artifacts (`.md` and `.json`) the script itself writes.

    python research/test_g120_prop_arms.py
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT_JSON = os.path.join(HERE, "g120_prop_arms.json")
OUT_MD = os.path.join(HERE, "g120_prop_arms.md")


def check_files_exist_and_parse():
    assert os.path.exists(OUT_JSON), "missing %s -- run research/g120_prop_arms.py" % OUT_JSON
    assert os.path.exists(OUT_MD), "missing %s -- run research/g120_prop_arms.py" % OUT_MD
    blob = json.load(open(OUT_JSON, encoding="utf-8"))
    text = open(OUT_MD, encoding="utf-8").read()
    assert isinstance(blob, dict) and blob, "%s parsed to an empty/non-dict blob" % OUT_JSON
    assert len(text) > 200, "%s is suspiciously short (%d chars)" % (OUT_MD, len(text))
    for key in ("meta", "arm1_vanquish", "arm2_pool_shares", "arm3_personal", "ranking"):
        assert key in blob, "missing top-level key %r in %s" % (key, os.path.basename(OUT_JSON))
    print("  ok   both output files exist and parse (%s: %d chars, %s: %d top-level keys)"
          % (os.path.basename(OUT_MD), len(text), os.path.basename(OUT_JSON), len(blob)))
    return blob, text


def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def check_all_dollar_figures_finite(blob):
    """Every dollar figure in the JSON is a finite, non-NaN number. Walks the
    whole tree looking for keys that look like dollar amounts rather than
    hand-listing every path, so a new field added later is covered too."""
    dollar_key_hints = ("dollar", "cost", "fee", "equity", "net_", "sub", "risk_dollars",
                        "total_net", "headline_risk")
    checked = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                p = path + "." + k
                if isinstance(v, (dict, list)):
                    walk(v, p)
                elif any(h in k.lower() for h in dollar_key_hints) and isinstance(v, (int, float)) and not isinstance(v, bool):
                    assert _finite(v), "%s = %r is not finite (NaN/inf)" % (p, v)
                    checked.append(p)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, "%s[%d]" % (path, i))

    walk(blob, "root")
    assert len(checked) > 10, "found suspiciously few dollar-like fields (%d) -- check the walk" % len(checked)
    print("  ok   every dollar-like figure in the JSON (%d fields found) is finite and not NaN"
          % len(checked))


def check_pool_arm_risk_varies(blob):
    """Proof the shares arm was actually repriced off entry/stop, not left
    at the book's flat $1,000/trade convention."""
    a2 = blob["arm2_pool_shares"]
    lo, hi, mean = a2["risk_dollars_min"], a2["risk_dollars_max"], a2["risk_dollars_mean"]
    assert _finite(lo) and _finite(hi) and _finite(mean), "arm2 risk_dollars stats not finite"
    assert hi > lo, "arm2 shares-repriced risk_dollars_max (%r) <= risk_dollars_min (%r) -- " \
        "looks like a flat risk, not repriced per-trade off entry/stop" % (hi, lo)
    # not pinned at the book's flat $1,000 convention
    assert not (abs(lo - 1000.0) < 1e-6 and abs(hi - 1000.0) < 1e-6), \
        "arm2 risk_dollars is flat at $1,000 -- the shares arm was not repriced"
    sample = a2.get("per_trade_sample", [])
    assert len(sample) >= 2, "arm2 per_trade_sample too small to check variance directly"
    sample_risks = [row["risk_dollars"] for row in sample]
    assert len(set(round(r, 6) for r in sample_risks)) > 1 or (hi - lo) > 1.0, (
        "arm2 per-trade sample shows no variance in risk_dollars either: %r" % sample_risks)
    # cross-check: risk_dollars = shares * |entry - stop| for the sampled rows
    for row in sample:
        want = row["shares"] * abs(row["entry"] - row["stop"])
        assert abs(row["risk_dollars"] - want) < 1e-6, (
            "arm2 sample row risk_dollars %r != shares*|entry-stop| %r for %r"
            % (row["risk_dollars"], want, row))
    print("  ok   arm2 (Trade The Pool, shares) per-trade risk_dollars actually varies "
          "(min $%.0f, max $%.0f, mean $%.0f across %d trades) and matches "
          "shares*|entry-stop| on the sampled rows -- proof it was repriced off entry/stop, "
          "not left at the flat $1,000 convention" % (lo, hi, mean, a2["n_trades"]))


def _check_bool_or_none(v, label):
    assert v is None or isinstance(v, bool), "%s must be bool or None, got %r (%s)" % (label, v, type(v))


def check_pass_fail_fields_are_boolean(blob):
    a1 = blob["arm1_vanquish"]
    a2 = blob["arm2_pool_shares"]
    for row in a1["sweep"]:
        _check_bool_or_none(row["passed"], "arm1 sweep row (risk_pct=%r) passed" % row["risk_pct"])
        # passed False/True must be consistent with pass_day being set/unset
        if row["passed"]:
            assert row["pass_day"] is not None, "arm1 row passed=True but pass_day is None"
            assert row["fail_reason"] is None, "arm1 row passed=True but fail_reason=%r" % row["fail_reason"]
        else:
            assert row["pass_day"] is None, "arm1 row passed=False but pass_day=%r" % row["pass_day"]
            assert row["fail_reason"] is not None, "arm1 row passed=False but fail_reason is None"
    _check_bool_or_none(a2["passed"], "arm2 passed")
    if a2["passed"]:
        assert a2["pass_day"] is not None, "arm2 passed=True but pass_day is None"
        assert a2["fail_reason"] is None, "arm2 passed=True but fail_reason=%r" % a2["fail_reason"]
    else:
        assert a2["pass_day"] is None, "arm2 passed=False but pass_day=%r" % a2["pass_day"]
        assert a2["fail_reason"] is not None, "arm2 passed=False but fail_reason is None"
    print("  ok   PASS/FAIL fields for arm1 (all %d sweep rows) and arm2 are real booleans "
          "(or None if never resolved), and pass_day/fail_reason are consistent with the "
          "passed flag in every row" % len(a1["sweep"]))


def check_pass_fail_matches_evaluate_prop_challenge(blob):
    """Re-derive PASS/FAIL for arm1's headline $1,000 row and arm2 directly
    from omen_metrics.evaluate_prop_challenge on the raw book, independent of
    g120's own arithmetic -- catches a case where the JSON's stored
    'passed' disagrees with what the simulator itself would say."""
    from omen_metrics import evaluate_prop_challenge
    from g116_sizing_kelly_options import load_rows, build_arm

    rows = load_rows()
    arm = build_arm(rows, keep=lambda r: True)

    a1 = blob["arm1_vanquish"]
    headline = a1["headline"]
    pnl = [(r["day"], r["r"] * headline["risk_dollars"]) for r in arm]
    kw = dict(a1["params"])
    res = evaluate_prop_challenge(pnl, account_size=a1["account_size"], **kw)
    assert res["passed"] == headline["passed"], (
        "re-derived PASS/FAIL for arm1 headline ($1,000/trade) = %r but stored JSON says %r"
        % (res["passed"], headline["passed"]))
    if not res["passed"]:
        assert res["fail_reason"] == headline["fail_reason"], (
            "re-derived fail_reason %r != stored %r" % (res["fail_reason"], headline["fail_reason"]))

    a2 = blob["arm2_pool_shares"]
    import math as _m
    daily_loss_limit_pct = a2["params"]["daily_loss_limit_pct"]
    pnl2 = []
    for r in arm:
        shares = min(a2["share_cap"], _m.floor(a2["account_size"] * a2["bp_mult"] / r["entry"]))
        risk_per_share = abs(r["entry"] - r["stop"])
        # the firm's own daily loss limit also caps the position, not just the
        # buying-power/share-count rule -- shares_for()'s ADVERSARIAL FIX #2
        if daily_loss_limit_pct and risk_per_share > 0:
            limit_shares = _m.floor(daily_loss_limit_pct * a2["account_size"] / risk_per_share)
            shares = min(shares, limit_shares)
        risk = shares * risk_per_share
        pnl2.append((r["day"], r["r"] * risk))
    res2 = evaluate_prop_challenge(pnl2, account_size=a2["account_size"], **a2["params"])
    assert res2["passed"] == a2["passed"], (
        "re-derived PASS/FAIL for arm2 = %r but stored JSON says %r" % (res2["passed"], a2["passed"]))
    print("  ok   arm1 headline ($1,000/trade) and arm2 PASS/FAIL, independently re-derived "
          "by calling omen_metrics.evaluate_prop_challenge on the raw book/shares repricing, "
          "match what g120_prop_arms.py stored in the JSON")


def _derive_ranking(blob):
    """Re-derive the ranking from the JSON's own PASS/FAIL + days-to-pass
    numbers -- does not read blob['ranking'] or grep the .md text.

    Ranking is built off `best_pass` (the lowest-months PASSING row in the
    full Vanquish sweep), NOT `headline` (the book's native $1,000/trade,
    which an adversarial pass found FAILs even though a real passing band
    exists elsewhere in the sweep) -- re-deriving off `headline` here would
    silently reintroduce the exact bug that was fixed, so this test checks
    the ranking actually uses the field g120_prop_arms.py's own rank_arms()
    is called with."""
    a1_best = blob["arm1_vanquish"].get("best_pass")
    a2 = blob["arm2_pool_shares"]
    candidates = []
    if a1_best:
        assert a1_best["passed"], (
            "arm1_vanquish.best_pass is set but passed=False -- best_pass must only ever "
            "hold a PASSing row")
        cost1 = (a1_best["subscription_cost"] or 0.0) + (a1_best["reset_cost"] or 0.0)
        candidates.append(("Vanquish Advanced Options $50k (at $%.0f/trade)" % a1_best["risk_dollars"],
                           a1_best["months_to_event"], cost1))
    if a2["passed"]:
        candidates.append(("Trade The Pool (shares)", a2["months_to_event"], a2["eval_fee"]))
    if not candidates:
        return None, []
    candidates.sort(key=lambda c: (c[1], c[2]))
    return candidates[0][0], candidates


def check_ranking_matches_json(blob, text):
    """The reported ranking in the .md text must match what the JSON's own
    PASS/FAIL + days-to-pass numbers imply, re-derived here independently of
    blob['ranking'] (which is g120's own claim, not ground truth)."""
    winner, candidates = _derive_ranking(blob)
    stored = blob["ranking"]
    if winner is None:
        assert stored["winner"] is None, (
            "re-derived ranking has NO winner (neither PASS/FAIL arm ever passes) but "
            "stored JSON ranking claims winner=%r" % stored["winner"])
        assert "no arm is fundable" in text.lower() or "no winner" in text.lower(), (
            "%s does not state that no arm is fundable, but the re-derived ranking from "
            "the JSON's own PASS/FAIL fields found no arm ever passes" % OUT_MD)
        print("  ok   ranking re-derived from arm1/arm2 PASS/FAIL fields: NO WINNER (neither "
              "clears its target anywhere in the book), and the .md text says so")
    else:
        assert stored["winner"] == winner, (
            "re-derived ranking winner %r != stored JSON ranking winner %r" % (winner, stored["winner"]))
        assert winner in text, "%s never names the re-derived winning arm (%s)" % (OUT_MD, winner)
        print("  ok   ranking re-derived from arm1/arm2 PASS/FAIL + months-to-pass fields "
              "matches the stored JSON ranking (winner=%r) and the .md text states it" % winner)


def check_md_states_headline_numbers(blob, text):
    a1 = blob["arm1_vanquish"]["headline"]
    a2 = blob["arm2_pool_shares"]
    a3 = blob["arm3_personal"]
    needles = [
        ("$1,000", "the book's native $1,000/trade unit"),
        ("Vanquish", "Vanquish arm name"),
        ("Trade The Pool", "Trade The Pool arm name"),
        ("$97", "the Trade The Pool eval fee"),
        ("$499", "the Vanquish monthly fee"),
        ("UNVERIFIED", "the Vanquish underlyings CONDITIONAL flag"),
        ("%.0f" % a3["book_native_1000"]["max_drawdown_dollars"], "arm3 book-native max drawdown"),
        ("%.0f" % a3["conservative_1pct"]["max_drawdown_dollars"], "arm3 conservative max drawdown"),
    ]
    for needle, label in needles:
        assert needle in text, "%s never states the %s (looked for %r)" % (OUT_MD, label, needle)
    print("  ok   %s states the headline numbers (native $1,000 unit, both arm names, both "
          "cost lines, the Vanquish CONDITIONAL flag, and arm3's drawdown figures)" % os.path.basename(OUT_MD))


def check_arm3_solvency_fields(blob):
    a3 = blob["arm3_personal"]
    for key in ("book_native_1000", "conservative_1pct"):
        d = a3[key]
        assert isinstance(d["wiped"], bool), "arm3[%r].wiped must be bool, got %r" % (key, d["wiped"])
        assert _finite(d["total_dollars"]) and _finite(d["max_drawdown_dollars"]), (
            "arm3[%r] dollar figures not finite" % key)
        assert d["max_drawdown_dollars"] >= 0, "arm3[%r] max_drawdown_dollars must be >= 0, got %r" % (
            key, d["max_drawdown_dollars"])
        assert 0.0 <= d["max_drawdown_pct_of_account"], (
            "arm3[%r] max_drawdown_pct_of_account must be >= 0, got %r" % (key, d["max_drawdown_pct_of_account"]))
        # internal consistency: pct = dollars / account_size * 100
        want_pct = round(d["max_drawdown_dollars"] / d["account_size"] * 100, 3)
        assert abs(d["max_drawdown_pct_of_account"] - want_pct) < 1e-2, (
            "arm3[%r] max_drawdown_pct_of_account %r != max_drawdown_dollars/account*100 %r"
            % (key, d["max_drawdown_pct_of_account"], want_pct))
        if d["wiped"]:
            assert d["wipe_day"] is not None, "arm3[%r].wiped=True but wipe_day is None" % key
    print("  ok   arm3 (personal $10k) solvency fields are internally consistent for both "
          "sizings: wiped is a real bool, drawdown dollars/pct agree with each other, and a "
          "wipe (if any) names the day it happened")


def check_sweep_covers_worked_example_and_finds_a_band(blob):
    """ADVERSARIAL REGRESSION GUARD (2026-09-03 night): this file's first cut
    swept only g116's 9-point RISK_PCTS grid (0.25%, 0.50%, ..., 3.00% of
    account), which straddled Vanquish's real passing band without ever
    landing in it -- an opus REFUTE pass found a clean PASS at every level
    from $131.00-$178.50/trade using this file's own
    evaluate_prop_challenge, bracketed by the grid's $125 (FAIL) and $250
    (FAIL) points. This check would have caught that bug: it requires (1)
    the sweep to include the sources' own worked example ($150/trade, named
    in both Projects/AUGUR.md and research/prop_vanquish_terms.md) as an
    explicit tested row, and (2) if ANY row in the sweep passes, that
    a1['passing_band'] and a1['best_pass'] are populated and self-consistent
    with the sweep's own rows -- so a future coarse-grid regression fails
    this test rather than silently reporting 'no arm fundable' again."""
    a1 = blob["arm1_vanquish"]
    sweep = a1["sweep"]

    worked = [r for r in sweep if abs(r["risk_dollars"] - 150.0) < 1e-6]
    assert worked, ("arm1_vanquish.sweep never tests $150/trade, the sources' own worked "
                    "example (Projects/AUGUR.md, research/prop_vanquish_terms.md) -- a sweep "
                    "that skips the one number the sources actually name cannot be trusted "
                    "to find a real passing band")
    assert worked[0]["is_worked_example_150"] is True, (
        "the $150 sweep row is not flagged is_worked_example_150=True")

    passing = [r for r in sweep if r["passed"]]
    if passing:
        band = a1["passing_band"]
        assert band, "sweep has %d passing row(s) but arm1_vanquish.passing_band is empty" % len(passing)
        lo_want = min(r["risk_dollars"] for r in passing)
        hi_want = max(r["risk_dollars"] for r in passing)
        assert abs(band["low_dollars"] - lo_want) < 1e-6 and abs(band["high_dollars"] - hi_want) < 1e-6, (
            "passing_band %r does not match min/max risk_dollars of the sweep's own passing "
            "rows ($%.2f-$%.2f)" % (band, lo_want, hi_want))
        assert band["n_passing"] == len(passing), (
            "passing_band.n_passing %r != actual passing row count %d" % (band["n_passing"], len(passing)))
        best = a1["best_pass"]
        assert best and best["passed"], "sweep has passing rows but best_pass is missing/not passed"
        cheapest_fastest = min(passing, key=lambda r: (r["months_to_event"], r["risk_dollars"]))
        assert best["risk_dollars"] == cheapest_fastest["risk_dollars"], (
            "best_pass risk_dollars %r != the sweep's own fastest-then-cheapest passing row %r"
            % (best["risk_dollars"], cheapest_fastest["risk_dollars"]))
        print("  ok   sweep includes the $150 worked example, and passing_band/best_pass are "
              "self-consistent with the sweep's own %d passing row(s) ($%.2f-$%.2f)"
              % (len(passing), band["low_dollars"], band["high_dollars"]))
    else:
        assert a1.get("passing_band") is None, (
            "no sweep row passes but arm1_vanquish.passing_band is non-empty: %r" % a1.get("passing_band"))
        assert a1.get("best_pass") is None, (
            "no sweep row passes but arm1_vanquish.best_pass is non-empty: %r" % a1.get("best_pass"))
        print("  ok   sweep includes the $150 worked example; no row passes and "
              "passing_band/best_pass correctly report empty")


def main():
    blob, text = check_files_exist_and_parse()
    check_all_dollar_figures_finite(blob)
    check_pool_arm_risk_varies(blob)
    check_pass_fail_fields_are_boolean(blob)
    check_pass_fail_matches_evaluate_prop_challenge(blob)
    check_arm3_solvency_fields(blob)
    check_sweep_covers_worked_example_and_finds_a_band(blob)
    check_ranking_matches_json(blob, text)
    check_md_states_headline_numbers(blob, text)
    print("\nPASS: g120_prop_arms outputs exist and parse, every dollar figure is finite, "
          "the shares arm (Trade The Pool) is proven repriced off entry/stop rather than left "
          "flat at $1,000, PASS/FAIL fields for arms 1 and 2 are real booleans consistent with "
          "what evaluate_prop_challenge itself returns on independent re-derivation, arm3's "
          "solvency fields are internally consistent, and the ranking re-derived from the "
          "JSON's own PASS/FAIL + days-to-pass numbers matches both the stored ranking and "
          "the .md text.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
