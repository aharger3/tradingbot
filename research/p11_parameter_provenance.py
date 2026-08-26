"""p11_parameter_provenance.py -- G5 corpus sweep, read-only.

Runs research/corpus_query.py's ranking function over every coded parameter
listed in research/parameter_catalog_draft.md, prints the top matches per
provenance class (TRADER_SAID / DOC_CLAIMS / CODE_COMMENT / DERIVED) for each,
and flags the circular-citation case explicitly: a parameter whose only
matching row of ANY kind is a CODE_COMMENT in signal_runner.py itself.

This script does not decide verdicts -- corpus_query.py's ranker is a keyword
overlap heuristic, not a judge. The verdicts (CONFIRMED / CONTRADICTED /
UNMENTIONED) live in research/p11_parameter_provenance.md, written by hand
against these query results plus the citations already gathered in
parameter_catalog_draft.md and hallucination-audit.md. Re-run this file to
reproduce the raw evidence behind every verdict in that report.

Read-only: only reads corpus_index.jsonl via corpus_query.py's loader.
Writes nothing except stdout.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

import corpus_query as cq  # noqa: E402

INDEX = ROOT / "research" / "corpus_index.jsonl"

# (id, constant name, sr location, current value, query string)
PARAMETERS = [
    ("A1", "OB_RETEST_TYPES", "sr:50", '("wick_only",)', "order block retest wick body strength hold"),
    ("A2", "OB_VOLUME_MULT", "sr:51", "0.0 (gate off)", "volume confirmation entry candle average"),
    ("A3", "FVG_RETEST", "sr:63", "False", "fair value gap fvg retest zone displacement"),
    ("A4", "FLAG_ENABLED", "sr:67", "False", "flag pattern pole pause breakout setup"),
    ("A5", "STRONG_PA_MULT", "sr:90", "1.5", "strong price action reclaim body average candle displacement"),
    ("A6", "CHASE_PCT", "sr:98", "0.005", "chase buying the top extended entry beyond level"),
    ("A7", "RULE84_LESSON", "sr:103", "True", "84 rule reclaim strong buying action same hammer pattern"),
    ("A8", "RULE84_ARM_BNR_ONLY", "sr:111", "True (== BREAK_AND_RETEST)", "84 rule arm A plus entry quality arming setup"),
    ("A9", "BNR_STOP_MODE", "sr:120", '"level"', "stop placement buffer below level retest candle low room"),
    ("A10", "HODLOD_PAIR", "sr:128", "False", "high of day low of day break retest HOD LOD nothing in between"),
    ("A11", "LEVEL_BLOCK_CAP", "sr:152", "True", "level in the middle probability goes down 2R path average range"),
    ("A12", "CLEAR_FOR_APLUS", "sr:153", "True", "open road new high low breakout clear no levels in the way"),
    ("A13", "STOP_RANGE_MULT", "sr:154", "0.75", "tight stop lose the thousand dollars in a second clear stop"),
    ("A14", "_GRADE_RANK", "sr:157", '{"A+":4,"A":3,"B":2,"C":1,"X":0,"D":0}', None),  # structural, no query
    ("B1", "Hammer confirm thresholds", "sr:_confirm_candle", "wick>=body, close favorable half", "hammer inverted hammer shooting star candle wick body"),
    ("B2", "Min viable stop", "sr:_min_viable_stop", ">=0.5% entry OR >=$0.20 premium", "minimum stop risk premium delta tight stop skip tradeable"),
    ("B3", "A+ stack displacement", "sr:_aplus_stack", "first break + 1.5x body + strong PA", "A plus setup first clean break displacement strong price action QQQ alignment HTF level"),
    ("B4", "Stack floor-B / pattern demotions", "sr:463-470", "stack floors at B unless HTF opposed", "stack outranks candle pattern floor grade bench"),
    ("B5", "LATE cap", "sr:458-461", "level already broken earlier => cap B", "level already broken earlier session late dirty first retest fresh level"),
    ("B6", "B&R min risk", "sr:471", "max(0.10, 0.0015*close) else D", "minimum risk stop distance relative sub fifty dollar stock"),
    ("B7", "PMH/PML cap to C", "sr:476-477", "PM-level B&R never above alert tier", "premarket levels pre-market high low rarely use"),
    ("B8", "S-score weights", "sr:479-488", "clean+2 A+2 stop+2 nonPM+1 hammer+2 qqq+1", "clean entry A grade structural stop QQQ aligned selection score"),
    ("B9", "OCR demote + wide-stop D-gate", "sr:548-551", "OCR only A-grade tight stop trades", "order block tight stop A grade wide stop 2R unreachable"),
    ("B10", "OCR/FVG/Flag min risk $0.50", "sr:520,543,571", "sub-$0.50 stop grades D", "minimum risk fifty cents order block fvg flag stop distance"),
    ("B11", "84% RR gate", "sr:598-599", ">=1.5x remaining reward", "remaining reward risk re-entry ratio geometry gone"),
    ("B12", "84% HOD/LOD proximity skip", "sr:600", "skip if close within top/bottom 20% of day range", "near high of day low of day skip candle close top bottom day range"),
    ("B13", "84% C->B floor", "sr:606-607", "alert-tier 84% promoted to tradeable B", "84 rule alert only tradeable promote floor bench"),
    ("B14", "84% one-shot disarm", "sr:624-625", "one re-entry per failed setup then disarm", "two or three same setups choppy day one re-entry disarm"),
    ("B15", "Calibration grade (counter-trend/first-signal/90min)", "sr:_calibration_grade", "counter cap C; first w/-trend signal in first 90min floors C->B", "first signal with the trend first 90 minutes counter trend day"),
    ("B16", "Consolidation skip 0.5%", "sr:_is_consolidation", "PDH/PDL/ORH/ORL within 0.5% of mean = skip", "choppy market skip entirely size down consolidation levels close together"),
    ("B17", "_closes_strong shape", "sr:329-340", "body>=0.5x range, close within 0.25x of extreme", "candle closes strong body range close near high low"),
    ("B18", "Blind 2R target", "sr:246,352", "target = entry +/- 2x risk everywhere", "2 to 1 minimum aggregate expectation not the exit mechanism scale out liquidity"),
    ("B19", "F3 HOD/LOD level-pair constants", "sr:423-432", ">=43 candles, 30min age, 0.1% dedupe", "session extreme rolling high low established minutes level pair duplicate"),
    ("B20", "Traded-level ignore band", "sr:249", "0.1x risk band ignores the traded level", "ignore traded level band duplicate ties dedupe grading"),
    ("X1", "BAR_EXTREME_FRAC", "sr:339", "0.25", "reclaim distance tolerance how far entry percent of range"),
]


def main() -> None:
    rows = cq.load_index(INDEX)
    print(f"# raw corpus_query results -- {len(rows)} indexed rows, {len(PARAMETERS)} parameters\n")
    for pid, name, loc, value, query in PARAMETERS:
        print("=" * 100)
        print(f"{pid} {name}  ({loc} = {value})")
        if query is None:
            print("  -- structural constant, no corpus query run (no evidence needed)")
            continue
        buckets = cq.rank(rows, query, classes=set(), top=3)
        total = sum(len(v) for v in buckets.values())
        print(f'  Q: "{query}"')
        if total == 0:
            print("  UNMENTIONED -- zero rows matched in any provenance class.")
            continue
        only_code_comment = (
            buckets["CODE_COMMENT"]
            and not buckets["TRADER_SAID"]
            and not buckets["DOC_CLAIMS"]
            and not buckets["DERIVED"]
        )
        for cls in cq.CLASS_ORDER:
            section = buckets[cls]
            if not section:
                continue
            print(f"  --- {cls} ({len(section)}) ---")
            for score, row in section:
                print("    " + cq.format_row(score, row))
        if only_code_comment:
            print("  *** CIRCULAR-CITATION FLAG: only CODE_COMMENT rows matched. ***")


if __name__ == "__main__":
    main()
