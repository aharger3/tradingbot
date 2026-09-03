"""g75_lateness_cases.py -- why is the engine ~40 min late on the one-candle
rule and on time on break-and-retest?

Seven case studies, one per one-candle-rule card on which Austin wrote the
minute he would have entered, plus the seven break-and-retest cards where the
engine was on his minute. For every bar of every one of those sessions this
walks the engine's OWN detector chain and records the FIRST condition that was
false. Nothing is re-implemented: detect_order_block_setup, ocr_quality,
detect_break_retest, MarketStructure and SignalRunner are imported and called.

Read-only. Touches no mark file, no engine file, no book.
Writes research/g75_lateness_cases.json.
"""
from __future__ import annotations
import json, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t4_engine_recall as T4
import omen_bot as OB
from omen_bot import (MarketStructure, detect_order_block_setup,
                      detect_break_retest, ocr_quality)
from signal_runner import OB_RETEST_TYPES, _volume_ok

MARKS = os.path.join(HERE, "marks", "probe_g71_homework_s3_2026-08-29_complete.jsonl")
MANI = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")
OUT = os.path.join(HERE, "g75_lateness_cases.json")

TOK = re.compile(r"\b(\d{1,2})[:;.](\d{2})\b")


def his_minute(note):
    m = TOK.search(note or "")
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h < 9 or h > 11:
        return None
    t = (h - 9) * 60 + mi - 30
    return t if 0 <= t <= 95 else None


def clock(off):
    return "%d:%02d" % (9 + (30 + off) // 60, (30 + off) % 60)


def ocr_trace(candles, i, direction):
    """Walk detect_order_block_setup's chain on candles[:i+1] and return the
    FIRST gate that is false, plus the anatomy. Branches mirror the shipped
    function; its own reason strings are matched, not re-derived."""
    w = candles[: i + 1]
    bull = direction == "bullish"
    st = MarketStructure()
    st.update(w)
    anchor = st.last_hh if bull else st.last_ll
    if anchor is None:
        return {"stage": "no_structure_break", "block_idx": None, "break_idx": None}
    _ob = {}
    block, retest, note = detect_order_block_setup(w, direction, out=_ob)
    d = {"break_idx": _ob.get("break_idx"), "block_idx": _ob.get("block_idx")}
    if block is None:
        if note.startswith("No valid order block"):
            d["stage"] = "block_broken_or_absent"
        elif note.startswith("Order block not isolated"):
            d["stage"] = "not_isolated"
        elif note.startswith("No displacement"):
            d["stage"] = "no_displacement"
        else:
            d["stage"] = "not_at_block"
        return d
    d["retest"] = retest
    d["block_hi"], d["block_lo"] = block.high, block.low
    if retest not in OB_RETEST_TYPES:
        d["stage"] = "retest_too_deep"
        return d
    cur = w[-1]
    beyond = cur.close > block.high if bull else cur.close < block.low
    if not beyond:
        d["stage"] = "close_not_beyond"
        return d
    if not _volume_ok(w):
        d["stage"] = "volume"
        return d
    q = ocr_quality(w, block, _ob["block_idx"], _ob["break_idx"], direction)
    d["stage"] = "PASS"
    d["q"] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in q.items()}
    risk = abs(cur.close - (block.low if bull else block.high))
    d["stop_pct"] = round(risk / cur.close * 100, 3)
    return d


def first_structure_bar(candles, direction, upto):
    """Earliest bar at which MarketStructure has a confirmed break (last_hh for
    long / last_ll for short) -- the earliest bar an order block can EXIST."""
    for i in range(3, upto + 1):
        st = MarketStructure()
        st.update(candles[: i + 1])
        if (st.last_hh if direction == "bullish" else st.last_ll) is not None:
            return i
    return None


def br_trace(candles, i, level, is_long):
    b = dict(OB.BR_FUNNEL)
    note = detect_break_retest(candles[: i + 1], level, is_long)
    a = OB.BR_FUNNEL
    if note:
        return "passed"
    for k in ("no_confirm_close", "adverse_wick", "no_break", "no_leave",
              "no_retest", "stale_retest", "too_short"):
        if a[k] - b.get(k, 0) > 0:
            return k
    return "?"


def first_br_bar(candles, level, is_long, upto):
    for i in range(4, upto + 1):
        if detect_break_retest(candles[: i + 1], level, is_long):
            return i
    return None


def main():
    marks = [json.loads(l) for l in open(MARKS, encoding="utf-8")]
    mani = {json.loads(l)["card_id"]: json.loads(l) for l in open(MANI, encoding="utf-8")}
    cards = []
    for m in marks:
        r = dict(mani[m["card_id"]])
        r["yes"] = m["answers"]["is_s"][0] == "yes"
        r["note"] = " ".join(str(v) for v in (m.get("notes") or {}).values())
        r["his"] = his_minute(r["note"])
        r["eng"] = (int(r["et"][:2]) - 9) * 60 + int(r["et"][3:]) - 30
        cards.append(r)

    OUTJ = {"cases": []}
    TARGET = [c for c in cards if c["yes"] and c["his"] is not None
              and c["bucket"] in ("OCR", "BR")]
    TARGET.sort(key=lambda c: (c["bucket"] != "OCR", c["card_id"]))

    print("=" * 92)
    print("SEVEN ONE-CANDLE-RULE CASE STUDIES, then the seven break-and-retest controls")
    print("=" * 92)

    for c in TARGET:
        sym, day = c["symbol"], c["date"]
        candles = T4.rth_candles(sym, day)
        direction = "bullish" if c["dir"] == "call" else "bearish"
        is_long = c["dir"] == "call"
        his, eng = c["his"], c["eng"]
        eng = min(eng, len(candles) - 1)
        print()
        print("-" * 92)
        print("%s  [%s]  he: %s   engine: %s   (+%d min)   dir=%s  level=%s"
              % (c["card_id"], c["bucket"], clock(his), clock(eng), eng - his,
                 c["dir"], c["level_name"]))
        print("-" * 92)
        rec = {"card_id": c["card_id"], "bucket": c["bucket"], "his": his,
               "eng": eng, "late": eng - his, "dir": c["dir"],
               "level_name": c["level_name"], "level_px": c.get("level_px")}

        fsb = first_structure_bar(candles, direction, eng)
        rec["first_structure_bar"] = fsb
        rec["first_structure_clock"] = clock(fsb) if fsb is not None else None
        t_his = ocr_trace(candles, his, direction)
        t_eng = ocr_trace(candles, eng, direction)
        rec["ocr_at_his"] = t_his
        rec["ocr_at_eng"] = t_eng
        print("  earliest bar an order block can EXIST (structure break confirmed): %s"
              % (clock(fsb) if fsb is not None else "not before the engine fired"))
        print("  at HIS minute  %-6s OCR chain stops at: %-22s %s"
              % (clock(his), t_his["stage"],
                 ("block %.2f-%.2f, retest=%s" % (t_his.get("block_lo", 0),
                                                  t_his.get("block_hi", 0),
                                                  t_his.get("retest")))
                 if t_his.get("block_hi") else ""))
        print("  at ITS minute  %-6s OCR chain stops at: %-22s %s"
              % (clock(eng), t_eng["stage"],
                 ("block %.2f-%.2f, retest=%s" % (t_eng.get("block_lo", 0),
                                                  t_eng.get("block_hi", 0),
                                                  t_eng.get("retest")))
                 if t_eng.get("block_hi") else ""))
        if t_eng.get("break_idx") is not None:
            print("     the block it eventually used: block bar %s, structure break bar %s"
                  % (clock(t_eng["block_idx"]), clock(t_eng["break_idx"])))
            rec["eng_block_clock"] = clock(t_eng["block_idx"])
            rec["eng_break_clock"] = clock(t_eng["break_idx"])

        census = Counter()
        for i in range(5, eng + 1):
            census[ocr_trace(candles, i, direction)["stage"]] += 1
        rec["ocr_stage_census_to_fire"] = dict(census)
        print("  every bar 9:35 -> the fire, where the OCR chain died: %s"
              % ", ".join("%s x%d" % (k, v) for k, v in census.most_common()))

        lp = c.get("level_px")
        if lp:
            bh = br_trace(candles, his, lp, is_long)
            fb = first_br_bar(candles, lp, is_long, eng)
            rec["br_at_his"] = bh
            rec["br_first_bar"] = fb
            rec["br_first_clock"] = clock(fb) if fb is not None else None
            print("  same session, B&R chain on %s $%.2f: at his minute -> %s ; "
                  "first bar it would fire -> %s"
                  % (c["level_name"], lp, bh, clock(fb) if fb is not None else "never"))
        OUTJ["cases"].append(rec)

    json.dump(OUTJ, open(OUT, "w"), indent=1)
    print()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
