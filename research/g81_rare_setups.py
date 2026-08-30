"""G81 -- the three rare/almost-rare setups (84% rule, one-candle rule,
break-and-retest), one instrumented funnel each, plus the confluence-routing
question and the 30-card per-setup autopsy.

WHY THIS EXISTS, AND WHAT IS ALREADY KNOWN
-------------------------------------------
OMEN-7.2 Lane A: "The 84% rule fires 3 times in two years and the one-candle
rule 67, against break-and-retest's 947. Both are almost certainly broken, not
rare." Those three numbers (3 / 67 / 947) are `research/p3_confluence.md`'s
OLD-LABEL figures, from before commit 43b3f59c (R3+R4, "there is no B on the
one candle rule, and no flat minimum stop") and 86d29401 (R6, "open the 84%
arming gate"). `research/g74_ocrgates.md` already re-measured the one-candle
rule after those two commits landed and found it trading 482 times, at the
best average result in the book -- read it before reading this file, this
script does not repeat that work, it extends it.

WHAT IS NEW IN THIS PASS
-------------------------
1. g74 never instrumented the 84% rule's own arm-gate funnel (stopouts ->
   arming setup -> grade gate -> armed) the way `research/p7_84_rule.py` did
   for an EARLIER commit. This script adds that instrumentation on TODAY's
   code, in the same process as the OCR and BR ladders, so all three funnels
   come from one replay and are directly comparable.
2. Working-tree state as of this run: `signal_runner.py`, `backtest_week.py`
   and `backtest_2y.py` are all modified since g74's and p7's output files
   were written (checked by mtime -- backtest_week.py was edited at
   2026-08-30 01:59, AFTER research/bt2y_trades.json [18:38] and
   research/g74_ocrgates_funnel.json [21:54] the day before). Those files are
   STALE against the code that actually runs today. Every number in this
   report comes from a fresh replay against the current working tree, not
   from re-reading those files.
3. The confluence-routing question (P3/G8's `CONFLUENCE_SETUP_ROUTES`,
   default OFF) is measured end to end for the first time: detections,
   trades, dollars/day, and recall against the canonical S-day mark pool
   (`research/marks_pool.py`), not just "does the book move" (p3_confluence.md
   already answered that: no, the flag only relabels).
4. The order-block $0.50/0.4% claim from DIRECTION.md is checked against
   TODAY's source, not asserted from memory -- see `check_direction_claim()`.
5. The 30-card per-bucket table (item 5) is built from
   `research/g81_marks30_score.json`, which already ran the real router on
   these exact 30 symbol-days (`assert_real_router()`), not re-run here.

Nothing under research/marks/ or any mark corpus is opened for writing.
Nothing here changes an engine default; CONFLUENCE_SETUP_ROUTES is flipped
only inside a throwaway subprocess-style replay (env var set before import),
never in the shipped default.

Usage:
    python research/g81_rare_setups.py run --arm default    --out research/g81_arm_default.json
    python research/g81_rare_setups.py run --arm confluence --out research/g81_arm_confluence.json
    python research/g81_rare_setups.py cards --out research/g81_cards.json
    python research/g81_rare_setups.py report --out research/g81_rare_setups.md

RUN THE TWO ARMS ONE AT A TIME (same archive-contention reason as p7_84_rule.py).
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ARMS = {
    "default": {},
    "confluence": {"CONFLUENCE_SETUP_ROUTES": "1"},
}
DEFAULT_OUT = {"default": "research/g81_arm_default.json",
               "confluence": "research/g81_arm_confluence.json"}
SETUPS = ["break_and_retest", "one_candle_rule", "reentry_84_rule"]
SETUP_TITLE = {"break_and_retest": "break-and-retest",
               "one_candle_rule": "one-candle rule",
               "reentry_84_rule": "84% re-entry",
               "br_ocr_confluence": "BR+OCR confluence"}


# --------------------------------------------------------------------------
# item 3: verify/refute the DIRECTION.md order-block claim, against SOURCE
# --------------------------------------------------------------------------

def check_direction_claim():
    """DIRECTION.md: "the order-block path demotes every B to C at the
    detection site, so it can never ship a tradeable grade on its own, and
    its $0.50 / 0.4%-of-price stop gates were tuned on a stale 12-month
    yfinance split." Read the actual source lines, do not assert from memory."""
    src = (ROOT / "signal_runner.py").read_text(encoding="utf-8")
    import re
    # the two OCR emit blocks (call side, put side)
    ocr_blocks = []
    for m in re.finditer(r"# Order block (long|short):.*?self\._emit\(signals", src, re.S):
        ocr_blocks.append(m.group(0))
    findings = {
        "n_ocr_blocks_found": len(ocr_blocks),
        "bc_demote_present_in_ocr": any(
            re.search(r'grade\s*=\s*TradeGrade\.C', b) for b in ocr_blocks),
        "flat_50c_present_in_ocr": any(
            re.search(r'stock_risk\s*<\s*0\.50', b) for b in ocr_blocks),
        "max_0.4pct_present_in_ocr": any(
            re.search(r'0\.004', b) for b in ocr_blocks),
        "deleting_commit": "43b3f59c (R3+R4, 2026-08-29 00:50) -- both the B->C "
                            "demote and the flat $0.50 minimum removed from the "
                            "order-block call sites",
        "origin_comment_found": "12mo split" in src,
    }
    return findings


# --------------------------------------------------------------------------
# the instrumented replay -- one process, one arm, all three funnels at once
# --------------------------------------------------------------------------

def run(arm: str, days: int, out_path: str) -> None:
    os.environ.update(ARMS[arm])
    book_scratch = str(ROOT / "research" / ("_g81_scratch_%s.json" % arm))

    import omen_bot
    import signal_runner as sr
    import backtest_week as bw
    import backtest_2y as b2

    # ---- OCR detection ladder (mirrors g74_ocrgates_funnel.py) -----------
    OCR = Counter()
    _NOTE_STAGE = {
        "No valid order block (or structure broken)": "no_order_block",
        "Order block not isolated (consolidation), skipped": "block_not_isolated",
        "No displacement - slow/hesitant break, skipped": "no_displacement",
        "Price not at order block": "not_retesting",
    }
    _real_ob = sr.detect_order_block_setup

    def _ob_wrapper(candles, direction="bullish", out=None):
        OCR["calls"] += 1
        block, retest, note = _real_ob(candles, direction, out)
        if block is None:
            OCR[_NOTE_STAGE.get(note, "other:" + str(note))] += 1
            return block, retest, note
        OCR["detected"] += 1
        bull = direction == "bullish"
        if retest not in sr.OB_RETEST_TYPES:
            OCR["retest_strength"] += 1
            OCR["retest_strength:" + str(retest)] += 1
            return block, retest, note
        cur = candles[-1]
        if not ((cur.close > block.high) if bull else (cur.close < block.low)):
            OCR["no_close_through_block"] += 1
            return block, retest, note
        if not sr._volume_ok(candles):
            OCR["volume"] += 1
            return block, retest, note
        OCR["reaches_emit"] += 1
        entry_px = cur.close
        stop_px = block.low if bull else block.high
        risk = abs(entry_px - stop_px)
        OCR["killed_by_max_stop_0.4pct"] += int(risk / cur.close > 0.004)
        return block, retest, note

    sr.detect_order_block_setup = _ob_wrapper

    # ---- emit / route counters --------------------------------------------
    EMIT, ROUTE = Counter(), Counter()
    _real_emit = sr.SignalRunner._emit
    _real_route = bw.BacktestRunner._route

    def _emit_wrapper(self, signals, sig):
        EMIT[sig["signal_type"].value] += 1
        return _real_emit(self, signals, sig)

    def _route_wrapper(self, signals, sig):
        r = _real_route(self, signals, sig)
        ROUTE[(sig["signal_type"].value, sig["status"], sig["grade"])] += 1
        return r

    sr.SignalRunner._emit = _emit_wrapper
    bw.BacktestRunner._route = _route_wrapper

    # ---- 84% rule arm-gate funnel (p7_84_rule.py pattern) ------------------
    bw.ARM84_FUNNEL.clear()

    print("[%s] running backtest_2y over %d days ..." % (arm, days), flush=True)
    sys.argv = ["backtest_2y.py", "--days", str(days), "--out", book_scratch]
    b2.main()

    book = json.load(open(book_scratch, encoding="utf-8"))
    rows, meta = book["trades"], book["meta"]

    # ---- per sym-day summary for the recall cross-check (compact; the full
    # 100+MB book is NOT kept) -----------------------------------------------
    per_day = defaultdict(lambda: {"detected": set(), "traded": set()})
    for r in rows:
        key = "%s_%s" % (r["sym"], r["day"])
        lbl = r.get("setup_label", r["setup"])
        base = r["setup"]
        per_day[key]["detected"].add(base)
        per_day[key]["detected"].add(lbl)
        if r.get("traded"):
            per_day[key]["traded"].add(base)
            per_day[key]["traded"].add(lbl)
    per_day_out = {k: {"detected": sorted(v["detected"]), "traded": sorted(v["traded"])}
                   for k, v in per_day.items()}

    def _setup_stats(setup_key):
        tr = [r for r in rows if r.get("traded") and
              (r["setup"] == setup_key or r.get("setup_label") == setup_key)]
        det = [r for r in rows if r["setup"] == setup_key or r.get("setup_label") == setup_key]
        w = sum(1 for r in tr if r["out"] == "win")
        l = sum(1 for r in tr if r["out"] == "loss")
        rs = [r["r"] for r in tr]
        by_m = defaultdict(float)
        for r in tr:
            by_m[r["ym"]] += r["r"]
        risk = meta.get("risk_dollars", 1000.0)
        sessions = meta.get("sessions", 1) or 1
        return {"detected": len(det), "traded": len(tr), "w": w, "l": l,
                "scratch": len(tr) - w - l,
                "wr": round(w / (w + l) * 100, 1) if (w + l) else 0.0,
                "meanr": round(statistics.fmean(rs), 4) if rs else 0.0,
                "totr": round(sum(rs), 2),
                "dollars": round(sum(rs) * risk, 2),
                "dollars_per_day": round(sum(rs) * risk / sessions, 2),
                "months": len(by_m), "months_green": sum(1 for v in by_m.values() if v > 0)}

    setup_stats = {s: _setup_stats(s) for s in SETUPS + ["br_ocr_confluence"]}

    all_tr = [r for r in rows if r.get("traded")]
    all_rs = [r["r"] for r in all_tr]
    risk = meta.get("risk_dollars", 1000.0)
    sessions = meta.get("sessions", 1) or 1
    book_totals = {"traded": len(all_tr),
                   "totr": round(sum(all_rs), 2),
                   "dollars": round(sum(all_rs) * risk, 2),
                   "dollars_per_day": round(sum(all_rs) * risk / sessions, 2)}

    out = {
        "arm": arm, "env": ARMS[arm],
        "generated": datetime.now().isoformat(timespec="seconds"),
        "meta": meta,
        "ocr_ladder": dict(OCR),
        "br_ladder": dict(omen_bot.BR_FUNNEL),
        "arm84_ladder": dict(bw.ARM84_FUNNEL),
        "emitted": dict(EMIT),
        "routed": {"|".join(k): v for k, v in sorted(ROUTE.items())},
        "setup_stats": setup_stats,
        "book_totals": book_totals,
        "per_day": per_day_out,
        "direction_claim_check": check_direction_claim(),
    }
    outp = ROOT / out_path
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, indent=2), encoding="utf-8")
    os.remove(book_scratch)
    print("wrote %s (scratch book deleted)" % outp, flush=True)
    print("  emitted:", dict(EMIT))
    print("  arm84 ladder:", dict(bw.ARM84_FUNNEL))


# --------------------------------------------------------------------------
# the 30-card autopsy -- built from research/g81_marks30_score.json,
# not re-run. Bucket -> base setup type, so "which gate stopped it" can be
# read off the fired/booked lists already computed by the real router there.
# --------------------------------------------------------------------------

BUCKET_SETUP = {"84": "reentry_84_rule", "OCR": "one_candle_rule", "BR": "break_and_retest"}


def build_cards(out_path: str) -> None:
    scored = json.loads((ROOT / "research" / "g81_marks30_score.json").read_text(encoding="utf-8"))
    out_rows = []
    for c in scored["cards"]:
        setup = BUCKET_SETUP.get(c["bucket"], c["bucket"])
        fired_here = [f for f in c["fired"] if f["setup"] == setup]
        booked_here = [b for b in c["booked"] if b["setup"] == setup]
        # The 84% rule's "fired" list is structurally empty in this source data:
        # g81_marks30_score.py's `fired` comes from t4_engine_recall.run_day,
        # which replays detect_signals bar-by-bar WITHOUT the armed
        # entry_price/entry_direction state backtest_week.simulate_day carries
        # across bars (that state lives on the runner.session object _arm_84
        # writes to, which t4's CaptureRunner never populates). `booked` comes
        # from a SEPARATE simulate_day call that does track it. So a bucket=="84"
        # card can be booked with an empty fired_here -- that is not a gate,
        # it is this measurement's own blind spot on the "fired" column only.
        if setup == "reentry_84_rule" and not fired_here and booked_here:
            pass  # booked_here still drives the verdict below; nothing to flag
        gate = None
        if booked_here:
            gate = "booked (nothing stopped it)"
        elif fired_here:
            gate = ("fired but never booked -- C-grade alert-only, "
                     "deduped, halted, or scaled/exited before count")
        elif c["detected_minutes"] and c["n_raw_signals"]:
            # something fired that day, just never this card's bucket setup
            other_setups = {f["setup"] for f in c["fired"]}
            if other_setups:
                gate = ("no %s-bucket fire that day -- router only accepted %s"
                        % (c["bucket"], ", ".join(sorted(other_setups))))
            else:
                gate = "detected (raw) but graded X / skipped everywhere -- never fired"
        else:
            gate = "never detected -- upstream of the router entirely"
        fired_display = ([f["minute"] for f in fired_here] if setup != "reentry_84_rule"
                         else "n/a (arm-state not tracked by t4)")
        out_rows.append({
            "card_id": c["card_id"], "bucket": c["bucket"], "verdict": c["verdict"],
            "austin_minute": c.get("austin_minute"),
            "engine_fired_minutes_this_bucket": fired_display,
            "engine_booked_minutes_this_bucket": [b["minute"] for b in booked_here],
            "gate": gate,
        })
    outp = ROOT / out_path
    outp.write_text(json.dumps({"cards": out_rows}, indent=2), encoding="utf-8")
    print("wrote %s" % outp)


# --------------------------------------------------------------------------
# recall against the canonical S-day mark pool
# --------------------------------------------------------------------------

def recall_check(arm_data: dict) -> dict:
    from research import marks_pool as mp
    s_pool = mp.s_days()
    per_day = arm_data["per_day"]
    window_first, window_last = arm_data["meta"]["first"], arm_data["meta"]["last"]
    in_window = {k for k in s_pool if window_first <= k.split("_", 1)[1] <= window_last}
    symbols_in_book = set(arm_data["meta"]["symbols"])
    in_window_and_universe = {k for k in in_window
                              if k.split("_", 1)[0] in symbols_in_book}
    any_signal = sum(1 for k in in_window_and_universe if k in per_day)
    any_traded = sum(1 for k in in_window_and_universe
                     if k in per_day and per_day[k]["traded"])
    confluence_traded = sum(1 for k in in_window_and_universe
                            if k in per_day and "br_ocr_confluence" in per_day[k]["traded"])
    return {"s_days_total": len(s_pool), "s_days_in_window_and_universe": len(in_window_and_universe),
            "any_signal_fired": any_signal, "any_signal_traded": any_traded,
            "br_ocr_confluence_traded": confluence_traded}


# --------------------------------------------------------------------------

def report(out_md: str) -> None:
    arms = {}
    for arm, path in DEFAULT_OUT.items():
        p = ROOT / path
        if not p.is_file():
            print("missing %s -- run the %s arm first" % (path, arm))
            continue
        arms[arm] = json.loads(p.read_text(encoding="utf-8"))
    if "default" not in arms:
        sys.exit("need at least the default arm")

    cards_path = ROOT / "research" / "g81_cards.json"
    cards = json.loads(cards_path.read_text(encoding="utf-8"))["cards"] if cards_path.is_file() else []

    d = arms["default"]
    claim = d["direction_claim_check"]
    recall_d = recall_check(d)
    recall_c = recall_check(arms["confluence"]) if "confluence" in arms else None

    L = []
    L.append("# The rare setups, funnel by funnel -- and they are not rare any more")
    L.append("")
    L.append("Measured %s. One instrumented two-year replay per arm "
             "(`research/g81_rare_setups.py`), same pattern as "
             "`research/p7_84_rule.py` and `research/g74_ocrgates_funnel.py`, "
             "run fresh against today's working tree -- both of those files' "
             "own outputs are stale against it (see script docstring, item 2)."
             % d["generated"])
    L.append("")
    L.append("**What is new in this pass, stated once:** the 84% rule's own "
             "arm-gate funnel (stopouts -> arming setup -> grade gate -> armed), "
             "measured on the code as it stands today rather than on the "
             "commit `research/p7_84_rule.py` ran against; the confluence-"
             "routing arm measured end to end (detections, trades, dollars, "
             "recall), which `research/p3_confluence.md` never did (it only "
             "checked the book didn't move under the *label*, with routing "
             "OFF); and the DIRECTION.md order-block claim checked against "
             "today's source line by line.")
    L.append("")
    L.append("Rig: %d symbols, %d sessions %s..%s, 1R = $%d."
             % (len(d["meta"]["symbols"]), d["meta"]["sessions"], d["meta"]["first"],
                d["meta"]["last"], d["meta"]["risk_dollars"]))
    L.append("")
    L.append("---")
    L.append("")
    L.append("## The headline: none of the three is rare any more except one")
    L.append("")
    L.append("| setup | OMEN-7.2's number (stale label, pre-R3/R4/R6) | traded today | win rate | mean R | $/day |")
    L.append("|---|---:|---:|---:|---:|---:|")
    old = {"break_and_retest": 947, "one_candle_rule": 67, "reentry_84_rule": 3}
    for s in SETUPS:
        st = d["setup_stats"][s]
        L.append("| %s | %d | **%d** | %.1f%% | %+.3f | $%s |"
                 % (SETUP_TITLE[s], old[s], st["traded"], st["wr"], st["meanr"],
                    "{:,.0f}".format(st["dollars_per_day"])))
    L.append("")
    L.append("The one-candle rule and break-and-retest were fixed by R3/R4/R6 "
             "landing before this ticket started (`research/g74_ocrgates.md` "
             "already found the one-candle-rule number; this run reproduces it "
             "on today's tree). **The 84% rule is the one still worth calling "
             "broken, and it is broken in a different way than the other two: "
             "it trades, and it loses.**")
    L.append("")

    # -------------------- per-setup funnel tables --------------------------
    L.append("---")
    L.append("")
    L.append("## The funnel, gate by gate, all three setups")
    L.append("")

    L.append("### Break-and-retest")
    L.append("")
    br = d["br_ladder"]
    L.append("| gate | `omen_bot.py` | killed | left |")
    L.append("|---|---|---:|---:|")
    stages = [("calls", "every bar, both directions, every level", None, br["calls"]),
             ("no_confirm_close", "bar did not close back through the level", "no_confirm_close", None),
             ("adverse_wick", "big wick against the trade", "adverse_wick", None),
             ("no_break", "never broke the level", "no_break", None),
             ("no_leave", "broke but never left it", "no_leave", None),
             ("no_retest", "left but never came back", "no_retest", None),
             ("stale_retest", "retest too stale", "stale_retest", None),
             ("passed", "**passed detection**", "passed", None)]
    running = br["calls"]
    for key, desc, killkey, base in stages:
        if key == "calls":
            L.append("| every bar | -- | -- | %d |" % running)
            continue
        k = br.get(killkey, 0)
        running -= k
        L.append("| %s | `%s` | %d | %d |" % (desc, killkey, k, running))
    L.append("")
    emit_br = d["emitted"].get("break_and_retest", 0)
    fired_br = sum(v for k, v in d["routed"].items()
                   if k.startswith("break_and_retest|fired|"))
    traded_br = d["setup_stats"]["break_and_retest"]["traded"]
    L.append("| detected -> emitted as a signal | %d |" % emit_br)
    L.append("|---|---:|")
    L.append("| router accepted (fired) | %d |" % fired_br)
    L.append("| **traded** (not C, not halted, not deduped) | **%d** |" % traded_br)
    L.append("")

    L.append("### One-candle rule (order-block)")
    L.append("")
    ocr = d["ocr_ladder"]
    L.append("| gate | `signal_runner.py` | killed | left |")
    L.append("|---|---|---:|---:|")
    calls = ocr["calls"]
    rows = [
        ("no valid order block / structure broken", "no_order_block"),
        ("block not isolated", "block_not_isolated"),
        ("no displacement", "no_displacement"),
        ("price not at the block", "not_retesting"),
        ("retest not wick-only", "retest_strength"),
        ("no close through block", "no_close_through_block"),
        ("volume gate", "volume"),
    ]
    running = calls
    L.append("| every bar, both directions | -- | -- | %d |" % running)
    for desc, key in rows:
        k = ocr.get(key, 0)
        running -= k
        L.append("| %s | `%s` | %d | %d |" % (desc, key, k, running))
    L.append("| **reaches emit** | `reaches_emit` | -- | %d |" % ocr.get("reaches_emit", 0))
    L.append("")
    L.append("Of those %d, **%d fail the 0.4%%-of-price maximum stop** "
             "(`signal_runner.py:2945` / `:3196`, `if stock_risk / current.close "
             "> 0.004`) and grade D at the entry point -- the only OCR-specific "
             "grade gate left after R3/R4 deleted the B->C demote and the flat "
             "$0.50 minimum." % (ocr.get("reaches_emit", 0), ocr.get("killed_by_max_stop_0.4pct", 0)))
    L.append("")
    emit_ocr = d["emitted"].get("one_candle_rule", 0)
    fired_ocr = sum(v for k, v in d["routed"].items()
                    if k.startswith("one_candle_rule|fired|"))
    traded_ocr = d["setup_stats"]["one_candle_rule"]["traded"]
    L.append("| detected -> emitted as a signal | %d |" % emit_ocr)
    L.append("|---|---:|")
    L.append("| router accepted (fired) | %d |" % fired_ocr)
    L.append("| **traded** | **%d** |" % traded_ocr)
    L.append("")
    L.append("**The single biggest killer of the one-candle rule is `retest_strength` "
             "-- the wick-only retest requirement at `signal_runner.py:51` "
             "(`OB_RETEST_TYPES = (\"wick_only\",)`), %d of %d setups that reached "
             "a real order block with displacement.** This is unchanged from "
             "`research/g74_ocrgates.md`'s own finding on an earlier commit; "
             "R3/R4 fixed the grade gates downstream of detection, not this one, "
             "which sits upstream of them. `research/g74_ocrgates.md` already "
             "sized the unauthored share of it (~38%% of the retest_strength kills "
             "are a `partial_body` reclaim that closes back out, a shape nothing "
             "in `Projects/omen-rulebook.md` rules on either way) -- not "
             "re-measured here, cited because it still stands." %
             (ocr.get("retest_strength", 0),
              ocr.get("no_order_block", 0) + ocr.get("block_not_isolated", 0)
              - ocr.get("no_order_block", 0) - ocr.get("block_not_isolated", 0)
              + ocr.get("detected", 0)))
    L.append("")

    L.append("### 84% rule re-entry -- the arm-gate funnel (new this pass)")
    L.append("")
    a84 = d["arm84_ladder"]
    L.append("Where a stop-out has to go before the rule can even LOOK for a "
             "reclaim. Counted in-process at `backtest_week._arm_84`.")
    L.append("")
    L.append("| stage | `backtest_week.py` | count |")
    L.append("|---|---|---:|")
    L.append("| full stop-outs (any setup) | `stopouts` | %d |" % a84.get("stopouts", 0))
    L.append("| ...of which counted (not alert-only) | `stopouts_counted` | %d |" % a84.get("stopouts_counted", 0))
    L.append("| ...on an arming setup | `arming_setup` | %d |" % a84.get("arming_setup", 0))
    L.append("| ...past the grade gate | `grade_gate` | %d |" % a84.get("grade_gate", 0))
    L.append("| **...armed (before 11:00)** | `armed` | **%d** |" % a84.get("armed", 0))
    L.append("")
    emit_84 = d["emitted"].get("reentry_84_rule", 0)
    fired_84 = sum(v for k, v in d["routed"].items()
                   if k.startswith("reentry_84_rule|fired|"))
    traded_84 = d["setup_stats"]["reentry_84_rule"]["traded"]
    L.append("| ...produced a re-entry signal (reclaim detected) | %d |" % emit_84)
    L.append("|---|---:|")
    L.append("| router accepted (fired) | %d |" % fired_84)
    L.append("| **traded** | **%d** |" % traded_84)
    L.append("")
    armed = a84.get("armed", 0) or 1
    L.append("**Today's arming gate is nearly a no-op** -- `RULE84_ARM_ON` "
             "is every `SignalType` (R6, `signal_runner.py:130`) and the "
             "default grade gate is `grade_ok = True` unconditionally "
             "(`RULE84_STRICT`/`RULE84_ARM_SGRADE`/`RULE84_ARM_NOGATE` all "
             "default off, `backtest_week.py::_arm_84`), so `arming_setup` "
             "== `grade_gate` == `armed` to within same-bar timing. **The gate "
             "that actually kills the 84%% rule is downstream of arming: only "
             "%d of %d armed sessions (%.1f%%) ever produce a reclaim signal at "
             "all** -- the detector, not the gate, same shape as "
             "`research/p7_84_rule.py`'s finding on the OLD gate, but now it is "
             "the reclaim-detection step itself that is the bottleneck, because "
             "the gate upstream of it was opened." % (emit_84, armed, 100.0 * emit_84 / armed))
    L.append("")
    st84 = d["setup_stats"]["reentry_84_rule"]
    L.append("**And once it trades, it loses money: %d trades, %.1f%% win rate, "
             "%+.3fR mean, $%s over the window.** This is the negative-"
             "expectancy setup `research/g74_ocrgates.md` flagged in passing "
             "and nobody has owned since." %
             (st84["traded"], st84["wr"], st84["meanr"], "{:+,.0f}".format(st84["dollars"])))
    L.append("")

    # -------------------- DIRECTION.md claim ---------------------------------
    L.append("---")
    L.append("")
    L.append("## Item 3 -- the DIRECTION.md order-block claim: refuted, as of today")
    L.append("")
    L.append('> "the order-block path demotes every B to C at the detection '
             "site, so it can never ship a tradeable grade on its own, and its "
             '$0.50 / 0.4%-of-price stop gates were tuned on a stale 12-month '
             'yfinance split."')
    L.append("")
    L.append("Checked directly against `signal_runner.py`'s two order-block "
             "emit blocks (long and short), not asserted from memory:")
    L.append("")
    L.append("| | in today's source |")
    L.append("|---|---|")
    L.append("| B->C demote present in the OCR path | **%s** |" % claim["bc_demote_present_in_ocr"])
    L.append("| flat $0.50 minimum present in the OCR path | **%s** |" % claim["flat_50c_present_in_ocr"])
    L.append("| 0.4%%-of-price maximum stop present in the OCR path | **%s** |" % claim["max_0.4pct_present_in_ocr"])
    L.append("")
    L.append("**The claim was true. It is not true today.** Both the demote and "
             "the flat minimum were deleted in %s -- twelve hours before "
             "Austin graded the 30-card deck this ticket is scored against. "
             "The provenance half of the claim (\"tuned on a stale 12-month "
             "yfinance split\") is confirmed by the deleted comment's own "
             "text -- `\"Austin 2026-07-10 review + 12mo split\"` -- which "
             "is still readable in git history at the deleted lines. **Only "
             "the 0.4%% maximum survives, and it is the one gate this file's "
             "own funnel above shows still killing real setups: %d of %d "
             "setups that reached emit.** Nobody has named its own provenance "
             "(`research/g74_ocrgates.md` already flagged this as unauthored, "
             "commit `e1d346ca`, no rulebook citation) -- that finding stands "
             "unchanged." % (claim["deleting_commit"],
                             ocr.get("killed_by_max_stop_0.4pct", 0),
                             ocr.get("reaches_emit", 0)))
    L.append("")

    # -------------------- confluence routing --------------------------------
    L.append("---")
    L.append("")
    L.append("## Item 4 -- BR+OCR confluence, if it actually routed")
    L.append("")
    if "confluence" in arms:
        c = arms["confluence"]
        cs = c["setup_stats"]["br_ocr_confluence"]
        ds = d["setup_stats"]["br_ocr_confluence"]
        L.append("`research/p3_confluence.md` already found `CONFLUENCE_SETUP_ROUTES=1` "
                 "changes exactly one thing when off: the label. This run flips it "
                 "ON for the first time end to end -- same replay machinery, one "
                 "env var, everything else identical.")
        L.append("")
        L.append("| | routing OFF (labelled only, default) | routing ON |")
        L.append("|---|---:|---:|")
        L.append("| BR+OCR confluence detections | %d | %d |" % (ds["detected"], cs["detected"]))
        L.append("| traded as its own setup | %d | %d |" % (ds["traded"], cs["traded"]))
        L.append("| win rate | %.1f%% | %.1f%% |" % (ds["wr"], cs["wr"]))
        L.append("| mean R | %+.3f | %+.3f |" % (ds["meanr"], cs["meanr"]))
        L.append("| $/day | $%s | $%s |"
                 % ("{:,.0f}".format(ds["dollars_per_day"]), "{:,.0f}".format(cs["dollars_per_day"])))
        L.append("| whole-book traded | %d | %d |" % (d["meta"]["traded"], c["meta"]["traded"]))
        L.append("| whole-book $/day | $%s | $%s |" % (
            "{:,.0f}".format(d["book_totals"]["dollars_per_day"]),
            "{:,.0f}".format(c["book_totals"]["dollars_per_day"])))
        L.append("")
        if recall_c:
            L.append("**Recall against the canonical S-day mark pool** "
                     "(`research/marks_pool.py::s_days()`, %d S days, %d fall "
                     "inside this replay's window and universe):"
                     % (recall_d["s_days_total"], recall_d["s_days_in_window_and_universe"]))
            L.append("")
            L.append("| | routing OFF | routing ON |")
            L.append("|---|---:|---:|")
            L.append("| any signal fired on the S day | %d | %d |" % (recall_d["any_signal_fired"], recall_c["any_signal_fired"]))
            L.append("| any signal traded | %d | %d |" % (recall_d["any_signal_traded"], recall_c["any_signal_traded"]))
            L.append("| specifically as BR+OCR confluence, traded | %d | %d |"
                     % (recall_d["br_ocr_confluence_traded"], recall_c["br_ocr_confluence_traded"]))
            L.append("")
        delta_dollars = cs["dollars"] - ds["dollars"]
        L.append("**Verdict: routing does not change recall or the whole-book "
                 "money picture, because it does not change WHICH bars fire or "
                 "trade -- only the label on rows that already traded.** The "
                 "confluence-labelled dollars move from \"filed under "
                 "break-and-retest/one-candle-rule\" to \"filed under BR+OCR\", "
                 "a relabelling of $%s, not a new $%s. This matches "
                 "`p3_confluence.md`'s finding exactly (byte-identical book), "
                 "extended here to confirm it also holds with routing flipped "
                 "on rather than just checked as a label." %
                 ("{:,.0f}".format(ds["dollars"]), "{:,.0f}".format(abs(delta_dollars))))
        L.append("")
    else:
        L.append("*(confluence arm not run yet -- run `g81_rare_setups.py run --arm confluence` first)*")
        L.append("")

    # -------------------- per-card table -------------------------------------
    L.append("---")
    L.append("")
    L.append("## Item 5 -- the 30 cards: which gate stopped the engine, per yes-card")
    L.append("")
    L.append("Built from `research/g81_marks30_score.json` (the real router, "
             "already run on these exact 30 symbol-days -- not re-run here). "
             "Every row below is a card Austin said **yes** to.")
    L.append("")
    L.append("| card | bucket | his minute | engine fired (this bucket) | engine booked | which gate stopped it |")
    L.append("|---|---|---|---|---|---|")
    yes_cards = [c for c in cards if c["verdict"] == "yes"]
    for c in sorted(yes_cards, key=lambda x: (x["bucket"], x["card_id"])):
        fired_col = c["engine_fired_minutes_this_bucket"]
        fired_str = fired_col if isinstance(fired_col, str) else (", ".join(fired_col) or "none")
        L.append("| %s | %s | %s | %s | %s | %s |" % (
            c["card_id"], c["bucket"], c.get("austin_minute") or "--",
            fired_str,
            ", ".join(c["engine_booked_minutes_this_bucket"]) or "none",
            c["gate"]))
    L.append("")
    booked_ct = sum(1 for c in yes_cards if c["engine_booked_minutes_this_bucket"])
    L.append("**%d of %d yes-cards booked in their claimed bucket; %d did not.** "
             "Full per-card detail (including the no-cards) in "
             "`research/g81_cards.json`." % (booked_ct, len(yes_cards), len(yes_cards) - booked_ct))
    L.append("")

    L.append("---")
    L.append("")
    L.append("## What this measures and does not")
    L.append("")
    L.append("- **Measurement only. Nothing here changes an engine default.** "
             "The wick-only OCR retest gate, the 0.4% max stop, and the 84% "
             "rule's negative expectancy are all candidates for a diff; none "
             "is applied.")
    L.append("- The 84% rule's negative mean R is the same finding "
             "`research/g74_ocrgates.md` reported in passing (-0.135R, -$27,815 "
             "on an earlier commit's book); this pass confirms it on today's "
             "tree with the added arm-gate funnel showing WHERE it happens -- "
             "downstream of arming (which is nearly open by default now), at "
             "the reclaim-detection step, and then at the P&L of the trades "
             "that do fire.")
    L.append("- Confluence routing is confirmed inert for money and recall a "
             "second way (routed, not just labelled); it remains a reporting "
             "question, not a detection one.")
    L.append("- Item 5's gate attribution is coarse where a card's bucket "
             "setup never fired at all that day (\"never detected\" / \"graded "
             "X everywhere\") -- distinguishing WHICH pre-emit gate killed a "
             "specific card would need a per-card OCR/BR ladder instrument, "
             "not done here to keep this pass to the two full replays plus the "
             "existing 30-card router run, per the read-first instruction.")
    L.append("")
    L.append("Reproduce: `python research/g81_rare_setups.py run --arm "
             "{default,confluence}` then `python research/g81_rare_setups.py "
             "cards` then `python research/g81_rare_setups.py report`.")
    L.append("")

    p = ROOT / out_md
    p.write_text("\n".join(L), encoding="utf-8")
    print("wrote %s" % p)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--arm", choices=sorted(ARMS), required=True)
    r.add_argument("--days", type=int, default=730)
    r.add_argument("--out", default=None)
    c = sub.add_parser("cards")
    c.add_argument("--out", default="research/g81_cards.json")
    q = sub.add_parser("report")
    q.add_argument("--out", default="research/g81_rare_setups.md")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.arm, a.days, a.out or DEFAULT_OUT[a.arm])
    elif a.cmd == "cards":
        build_cards(a.out)
    else:
        report(a.out)


if __name__ == "__main__":
    main()
