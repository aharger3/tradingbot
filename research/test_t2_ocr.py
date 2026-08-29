"""T2 -- the one-candle-rule definition, pinned on hand-built bars.

Austin, probe_master_2026-08-29, fact_ocr_demote:
  "s trades are all about being early and the most important thing is that clear
   break retest with displacement that happens quick and strong PA entry"

Each clause gets a bar sequence that satisfies everything else and fails only
that clause, so a regression in one clause cannot hide behind another.

Also asserts the two invariants the report depends on:
  * OCR_STRONG_PA_MULT is the SAME number as signal_runner.STRONG_PA_MULT (the
    engine's own definition of strong price action, the 84% reclaim gate) -- the
    T2 report claims "reused, not invented" and this is what makes that true.
  * OCR_STRICT is OFF by default. R3 (lift the demote) is ratified and ships ON;
    this new lever ships behind a flag.

Run: python research/test_t2_ocr.py
"""
from __future__ import annotations
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("POLYGON_API_KEY", "unset")

from omen_bot import (Candle, ocr_quality, ocr_is_his,        # noqa: E402
                      OCR_STRONG_PA_MULT, OCR_QUICK_BLOCK_TO_BREAK,
                      OCR_QUICK_BREAK_TO_ENTRY)
import signal_runner as sr                                    # noqa: E402

FAILS = []


def check(name, cond):
    print(("  PASS  " if cond else "  FAIL  ") + name)
    if not cond:
        FAILS.append(name)


def bar(i, o, h, l, c, v=100000):
    return Candle(timestamp="09:%02d:00" % (30 + i), open=o, high=h, low=l,
                  close=c, volume=v)


def build(entry_body=1.0, leave=True, break_to_entry=3, block_to_break=2,
          entry_bullish=True):
    """A bullish one-candle-rule sequence with each clause under control.

    Layout: 10 flat prior bars (avg body 0.10) -> block (red) -> break leg ->
    departure bars -> retest bars -> entry bar.
    """
    cs = []
    px = 100.0
    for i in range(10):                       # prior 10, body 0.10 each
        cs.append(bar(len(cs), px, px + 0.15, px - 0.15, px + 0.10))
        px += 0.10
    block_i = len(cs)
    cs.append(bar(len(cs), px, px + 0.05, px - 0.30, px - 0.25))   # red block
    b_hi, b_lo = px + 0.05, px - 0.30
    px -= 0.25
    for _ in range(block_to_break):           # displacement leg up
        # `leave=False` is the chop case: the leg closes higher but every bar's
        # LOW is still back inside the block, so price never actually departed.
        lo = (px - 0.05) if leave else (b_lo - 0.02)
        cs.append(bar(len(cs), px, px + 1.10, lo, px + 1.00))
        px += 1.00
    break_i = len(cs) - 1
    # bars between the break and the entry: either clear of the block (leave)
    # or hugging it (no leave)
    for _ in range(max(0, break_to_entry - 1)):
        if leave:
            lo = b_hi + 0.20
            cs.append(bar(len(cs), lo + 0.10, lo + 0.40, lo, lo + 0.15))
        else:
            cs.append(bar(len(cs), b_hi, b_hi + 0.10, b_lo - 0.05, b_hi + 0.02))
    # entry bar: dips into the block with its WICK only, closes back above b_hi.
    # `entry_body` is a multiple of the avg body of the prior 10 bars, which at
    # this point is dominated by the 1.00-body displacement leg.
    prior = cs[-10:]
    avg = sum(c.body_size for c in prior) / len(prior)
    body = avg * entry_body
    if entry_bullish:
        o, c = b_hi + 0.02, b_hi + 0.02 + body
    else:
        o, c = b_hi + 0.02 + body, b_hi + 0.02
    cs.append(bar(len(cs), o, max(o, c) + 0.05, b_lo + 0.01, c))
    return cs, block_i, break_i, cs[block_i]


def main():
    print("T2 -- one candle rule, his definition")

    # --- constants -------------------------------------------------------
    check("OCR_STRONG_PA_MULT == signal_runner.STRONG_PA_MULT (reused, not invented)",
          OCR_STRONG_PA_MULT == sr.STRONG_PA_MULT)
    check("OCR_STRICT is OFF by default (R3 ships ON, this lever ships behind a flag)",
          sr.OCR_STRICT is False)

    # --- the happy path --------------------------------------------------
    cs, bi, ki, blk = build(entry_body=3.0, leave=True, break_to_entry=3,
                            block_to_break=2)
    q = ocr_quality(cs, blk, bi, ki, "bullish")
    check("clean setup: clear_break", q["clear_break"])
    check("clean setup: quick", q["quick"])
    check("clean setup: strong_pa", q["strong_pa"])
    check("clean setup: ocr_is_his", ocr_is_his(cs, blk, bi, ki, "bullish"))

    # --- "clear break": price must LEAVE the block -----------------------
    cs, bi, ki, blk = build(entry_body=3.0, leave=False, break_to_entry=4)
    q = ocr_quality(cs, blk, bi, ki, "bullish")
    check("chop on the level -> clear_break False", q["clear_break"] is False)
    check("chop on the level -> ocr_is_his False",
          ocr_is_his(cs, blk, bi, ki, "bullish") is False)

    # --- "strong PA entry": body size ------------------------------------
    cs, bi, ki, blk = build(entry_body=0.5, leave=True, break_to_entry=3)
    q = ocr_quality(cs, blk, bi, ki, "bullish")
    check("doji entry -> strong_pa False", q["strong_pa"] is False)
    check("doji entry -> clear_break still True (clauses are independent)",
          q["clear_break"] is True)

    # --- "strong PA entry": direction ------------------------------------
    cs, bi, ki, blk = build(entry_body=3.0, leave=True, break_to_entry=3,
                            entry_bullish=False)
    q = ocr_quality(cs, blk, bi, ki, "bullish")
    check("RED entry candle on a long -> strong_pa False", q["strong_pa"] is False)
    check("RED entry candle on a long -> _dir_ok False", q["_dir_ok"] is False)

    # --- "quick": break -> entry -----------------------------------------
    slow = OCR_QUICK_BREAK_TO_ENTRY + 4
    cs, bi, ki, blk = build(entry_body=3.0, leave=True, break_to_entry=slow)
    q = ocr_quality(cs, blk, bi, ki, "bullish")
    check("stale retest (%d bars after the break) -> quick False" % slow,
          q["quick"] is False)

    # --- "quick": block -> break -----------------------------------------
    slow_leg = OCR_QUICK_BLOCK_TO_BREAK + 3
    cs, bi, ki, blk = build(entry_body=3.0, leave=True, break_to_entry=3,
                            block_to_break=slow_leg)
    q = ocr_quality(cs, blk, bi, ki, "bullish")
    check("slow leg (%d bars block->break) -> quick False" % slow_leg,
          q["quick"] is False)

    # --- his 20 refusals, as a standing assertion ------------------------
    # The T2 report's headline number. Recomputed from the committed feature
    # file when it is present so a definition change that stops rejecting his
    # refusals fails here rather than in a report nobody re-runs.
    import json
    feats = os.path.join(HERE, "_t2_ocr_features.json")
    marks = os.path.join(HERE, "marks", "probe_master_2026-08-29.jsonl")
    if os.path.exists(feats):
        from research.t2_ocr_detector import clauses, refusal_ids
        rows = {"%s_%s" % (f["sym"], f["day"]): f
                for f in json.loads(open(feats).read())["rows"]}
        ref = refusal_ids()
        kept = [cid for cid in ref if cid in rows and all(clauses(rows[cid]).values())]
        check("rejects >= 18 of his 20 refusals (kept %d: %s)"
              % (len(kept), kept), len(ref) - len(kept) >= 18)
    else:
        print("  SKIP  refusal check (run research/t2_ocr_detector.py --stage1 first)")
    assert os.path.exists(marks), "mark file missing"

    if FAILS:
        print("\nFAILED: %s" % ", ".join(FAILS))
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
