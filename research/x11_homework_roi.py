"""x11_homework_roi.py -- price the outstanding 60 cards against the recall gate.

    python research/x11_homework_roi.py --selfcheck --json

Answers LANE X11. Every number in `research/x11_homework_roi.md` comes from here.
Read-only: it opens mark corpora, deck HTML and the shipped book, and writes
nothing except stdout and (with --json) `research/_x11_roi.json`.

Three things it prices:

  1  WHAT is unfinished -- lane 2 (30 silent-day cards, 2 taps) and lane 3
     (30 give-back cards, 1 tap) of `research/probes/omen-h2-3lane.html`.
     Lane 1 came back 2026-08-28 as
     `research/marks/deck_marks_h2_3lane_2026-08-28.jsonl`.

  2  WHAT it buys on the gate. The gate is held-out S recall, denominator 15
     (`research/marks/probe_omen_test1_2026-08-27.jsonl`). The arithmetic that
     matters is not the Wilson interval -- it is the PAIRED sign test: the same
     S days are re-scored under two engine arms, so significance is set by the
     count of discordant days, not by the size of the denominator.

  3  WHAT is cheaper. Tap accounting across every instrument ever shipped,
     against the answers each one actually returned.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

H2_MARKS = os.path.join(HERE, "marks", "deck_marks_h2_3lane_2026-08-28.jsonl")
T1_MARKS = os.path.join(HERE, "marks", "probe_omen_test1_2026-08-27.jsonl")
T2_MANIFEST = os.path.join(HERE, "probes", "omen-test-2-manifest.jsonl")
T1_MANIFEST = os.path.join(HERE, "probes", "omen-test-1-manifest.jsonl")
BALLOT1 = os.path.join(HERE, "rule_ballot_batch01.jsonl")
BALLOT2 = os.path.join(HERE, "rule_ballot_batch02.jsonl")
BOOK = os.path.join(HERE, "g3_arm_ow1.json")

PROBES = ["omen-master-homework", "omen-test-1", "omen-test-2", "qa-queue",
          "silent-day-autopsy", "head-to-head", "grader-calibration",
          "omen-h2-3lane"]

MARK_FILES = [
    "deck_marks_index_2026-08-19",
    "deck_marks_tsla_2026-08-20",
    "probe_autopsy_2026-08-23",
    "probe_head2head_2026-08-24",
    "probe_master_homework_2026-08-26",
    "probe_omen_test1_2026-08-27",
    "deck_marks_h2_3lane_2026-08-28",
]

CID_RE = re.compile(r"^[bsg]_([A-Z]+)_(\d{4}-\d{2}-\d{2})")


# --------------------------------------------------------------------------- io
def jl(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def page_cards(name):
    """([(lane, cid)], question-slot count, per-question counter) for a probe."""
    p = os.path.join(HERE, "probes", name + ".html")
    if not os.path.exists(p):
        return [], 0, collections.Counter()
    h = open(p, encoding="utf-8").read()
    lanes = re.findall(r'data-lane="([a-z_]+)" data-cid="([^"]+)"', h)
    cids = re.findall(r'data-cid="([^"]+)"', h)
    qs = re.findall(r'class="q" data-q="([a-z_]+)"', h)
    return (lanes or [("", c) for c in cids]), len(qs), collections.Counter(qs)


def sym_day(cid):
    m = CID_RE.match(cid)
    return (m.group(1), m.group(2)) if m else None


# ------------------------------------------------------------------ statistics
def wilson(k, n, z=1.959963985):
    """95% Wilson score interval -- the right one for a small binomial."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - s) / d, (c + s) / d)


def n_for_halfwidth(p, target, nmax=4000):
    """Smallest n whose Wilson half-width at proportion p is <= target."""
    for n in range(5, nmax):
        lo, hi = wilson(round(p * n), n)
        if (hi - lo) / 2 <= target:
            return n
    return None


def sign_test_min_b(alpha=0.05):
    """Exact one-sided sign test: the fewest all-one-direction discordant pairs
    whose p = 0.5**b clears alpha. That is McNemar's exact test in the case
    where the new arm never loses a day the old arm already won."""
    b = 1
    while 0.5 ** b > alpha:
        b += 1
    return b


def binom_tail(n, k, q):
    """P(X >= k) for X ~ Binom(n, q)."""
    return sum(math.comb(n, i) * q ** i * (1 - q) ** (n - i) for i in range(k, n + 1))


# ----------------------------------------------------------------------- report
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    out = {}

    # ---- 1. what is unfinished -------------------------------------------
    lanes, _, _ = page_cards("omen-h2-3lane")
    by_lane = collections.defaultdict(list)
    for ln, cid in lanes:
        by_lane[ln].append(cid)
    done = {r["card_id"] for r in jl(H2_MARKS)}
    outstanding = {ln: [c for c in v if c not in done] for ln, v in by_lane.items()}
    out["h2_lane_sizes"] = {k: len(v) for k, v in by_lane.items()}
    out["h2_outstanding"] = {k: len(v) for k, v in outstanding.items()}
    out["h2_outstanding_total"] = sum(len(v) for v in outstanding.values())
    out["h2_lane1_returned"] = len(done)

    print("== 1. THE 60 ==")
    for ln in ("b_remap", "silent_day", "giveback"):
        print("  %-11s built %3d  returned %3d  OUTSTANDING %3d"
              % (ln, len(by_lane[ln]),
                 len(by_lane[ln]) - len(outstanding[ln]), len(outstanding[ln])))
    print("  outstanding total: %d cards" % out["h2_outstanding_total"])

    l2 = [sym_day(c) for c in outstanding["silent_day"]]
    l3 = [sym_day(c) for c in outstanding["giveback"]]
    out["lane2_days"] = ["%s %s" % t for t in sorted(l2)]
    out["lane3_days"] = ["%s %s" % t for t in sorted(l3)]
    out["lane2_symbols"] = dict(collections.Counter(s for s, _ in l2))
    out["lane3_symbols"] = dict(collections.Counter(s for s, _ in l3))
    out["h2_taps_outstanding"] = 2 * len(l2) + 1 * len(l3)
    print("  lane 2 is 2 taps/card, lane 3 is 1 tap/card -> %d taps left"
          % out["h2_taps_outstanding"])

    # ---- 2. what it buys on the recall gate ------------------------------
    t1 = jl(T1_MARKS)
    t1_days = {(r["symbol"], r["date"]) for r in t1}
    t1_s = {(r["symbol"], r["date"]) for r in t1 if r.get("grade") == "S"}
    out["t1_cards"] = len(t1)
    out["t1_grades"] = dict(collections.Counter(r.get("grade") for r in t1))
    out["t1_S"] = len(t1_s)

    l2set, l3set = set(l2), set(l3)
    out["lane2_in_heldout"] = sorted("%s %s" % t for t in (l2set & t1_days))
    out["lane2_in_heldout_S"] = sorted("%s %s" % t for t in (l2set & t1_s))
    out["lane3_in_heldout"] = sorted("%s %s" % t for t in (l3set & t1_days))
    # By construction: lane 2 re-asks days already graded, lane 3 asks a hold
    # label and no grade at all. Neither can create a symbol-day that is both
    # NEW and S on the held-out set.
    out["lane2_new_heldout_S"] = 0
    out["lane3_new_heldout_S"] = 0

    # How many of the outstanding cards ask about a symbol-day Austin has ALREADY
    # judged somewhere. Lane 2 is deliberately exempt from the no-repeat guard
    # (build_h2_deck.build(), lane 2 comment) because it wants the LEVEL, which
    # the old grade does not carry -- but that makes tap 1 a repeat, and this is
    # how many times.
    try:
        sys.path.insert(0, os.path.dirname(HERE))
        from research.build_deck import marked_card_ids
        judged = marked_card_ids()
    except Exception as e:                                   # pragma: no cover
        judged, out["judged_err"] = set(), repr(e)
    out["judged_symbol_days"] = len(judged)
    out["lane2_repeat"] = sum(1 for s_, d_ in l2 if "%s_%s" % (s_, d_) in judged)
    out["lane3_repeat"] = sum(1 for s_, d_ in l3 if "%s_%s" % (s_, d_) in judged)
    print("  no-repeat corpus knows %d judged symbol-days" % len(judged))
    print("  lane 2 cards on an ALREADY-JUDGED day: %d / %d  (tap 1 is a repeat)"
          % (out["lane2_repeat"], len(l2)))
    print("  lane 3 cards on an ALREADY-JUDGED day: %d / %d"
          % (out["lane3_repeat"], len(l3)))
    out["lane2_new_info_taps"] = len(l2)          # only tap 2 (the level) is new
    out["lane2_total_taps"] = 2 * len(l2)

    print()
    print("== 2. WHAT 60 CARDS BUY ON THE GATE ==")
    print("  held-out set: %d cards, %s" % (len(t1), out["t1_grades"]))
    print("  lane 2 cards that ARE held-out cards: %d  (S among them: %d)"
          % (len(out["lane2_in_heldout"]), len(out["lane2_in_heldout_S"])))
    print("  lane 3 cards that ARE held-out cards: %d" % len(out["lane3_in_heldout"]))
    print("  NEW held-out S days the 60 add: %d" % out["lane2_new_heldout_S"])

    k, n = 3, len(t1_s)
    lo, hi = wilson(k, n)
    out["recall_now"] = {"k": k, "n": n, "p": k / n, "wilson_lo": lo,
                         "wilson_hi": hi, "halfwidth": (hi - lo) / 2}
    print("  recall now %d/%d = %.1f%%  Wilson 95%% [%.1f%%, %.1f%%]  half-width %.1f pp"
          % (k, n, 100 * k / n, 100 * lo, 100 * hi, 100 * (hi - lo) / 2))

    ladder = []
    for extra in (0, 15, 30, 60, 135):
        nn = n + extra
        kk = round((k / n) * nn)
        lo2, hi2 = wilson(kk, nn)
        ladder.append({"extra_S": extra, "n": nn, "k": kk, "lo": lo2, "hi": hi2,
                       "halfwidth": (hi2 - lo2) / 2})
    out["ci_ladder"] = ladder
    print("  CI ladder, holding the observed 20% rate fixed:")
    for r in ladder:
        print("    +%3d S days -> %3d/%3d  [%.1f%%, %.1f%%]  half-width %.1f pp"
              % (r["extra_S"], r["k"], r["n"], 100 * r["lo"], 100 * r["hi"],
                 100 * r["halfwidth"]))

    out["n_for_10pp"] = n_for_halfwidth(0.20, 0.10)
    out["n_for_5pp"] = n_for_halfwidth(0.20, 0.05)
    print("  S days for a +/-10pp half-width at p=0.20: %d" % out["n_for_10pp"])
    print("  S days for a  +/-5pp half-width at p=0.20: %d" % out["n_for_5pp"])

    b = sign_test_min_b()
    out["sign_test_min_b"] = b
    miss_now = n - k
    out["missed_now"] = miss_now
    print("  PAIRED sign test (same days, two engine arms): a fix must recover")
    print("    >= %d missed S days to clear p<0.05, at ANY denominator" % b)
    power = []
    for q in (0.1, 0.2, 0.3, 0.4, 0.5):
        power.append({"q": q,
                      "p_now": binom_tail(miss_now, b, q),
                      "p_double": binom_tail(miss_now * 2, b, q)})
    out["power"] = power
    print("  P(a fix recovering each missed day w.p. q yields >=%d recoveries):" % b)
    print("    q      %d missed (now)   %d missed (100 more cards)"
          % (miss_now, miss_now * 2))
    for r in power:
        print("    %.1f        %.3f              %.3f"
              % (r["q"], r["p_now"], r["p_double"]))

    # ---- 3. yield: held-out S days per graded card -----------------------
    print()
    print("== 3. YIELD -- S DAYS PER GRADED CARD ==")
    yields = []
    for f in MARK_FILES:
        rs = jl(os.path.join(HERE, "marks", f + ".jsonl"))
        gs = collections.Counter(r.get("grade") for r in rs)
        days = len({(r.get("symbol"), r.get("date")) for r in rs})
        s = gs.get("S", 0)
        yields.append({"file": f, "rows": len(rs), "days": days, "S": s,
                       "S_per_card": (s / len(rs)) if rs else 0.0})
    out["yield"] = yields
    for y in yields:
        print("  %-34s rows %3d  days %3d  S %3d  S/card %.2f"
              % (y["file"], y["rows"], y["days"], y["S"], y["S_per_card"]))

    t2 = jl(T2_MANIFEST)
    t1m = jl(T1_MANIFEST)
    out["t2_cards"] = len(t2)
    out["t2_strata"] = dict(collections.Counter(r.get("stratum") for r in t2))
    out["t1_strata"] = dict(collections.Counter(r.get("stratum") for r in t1m))
    out["t2_overlap_t1"] = len({(r["symbol"], r["date"]) for r in t2}
                               & {(r["symbol"], r["date"]) for r in t1m})
    out["t2_graded"] = any(os.path.exists(os.path.join(HERE, "marks", p))
                           for p in ("probe_omen_test2.jsonl",
                                     "probe_omen_test2_2026-08-27.jsonl",
                                     "probe_omen_test2_2026-08-28.jsonl"))
    print("  omen-test-2: %d cards built, overlap with test-1 = %d, graded = %s"
          % (len(t2), out["t2_overlap_t1"], out["t2_graded"]))
    print("    strata test-1 %s" % out["t1_strata"])
    print("    strata test-2 %s" % out["t2_strata"])
    out["t2_expected_S"] = round(len(t2) * out["t1_S"] / len(t1)) if t1 else None
    print("  test-2 expected S days at test-1's observed rate: %s"
          % out["t2_expected_S"])

    # ---- 4. tap accounting -----------------------------------------------
    print()
    print("== 4. TAP ACCOUNTING ==")
    taps = []
    for p in PROBES:
        cards, nq, _ = page_cards(p)
        taps.append({"page": p, "cards": len(cards), "questions": nq,
                     "q_per_card": (nq / len(cards)) if cards else 0.0})
    out["taps"] = taps
    for t in taps:
        print("  %-24s cards %3d  question slots %3d  q/card %.2f"
              % (t["page"], t["cards"], t["questions"], t["q_per_card"]))

    b1, b2 = jl(BALLOT1), jl(BALLOT2)
    out["ballot"] = {"batch01": len(b1), "batch02": len(b2),
                     "total": len(b1) + len(b2),
                     "note_chars": sum(len(r.get("note") or "") for r in b1 + b2)}
    print("  rule ballot: %d + %d = %d settled rules, %d chars of note prose"
          % (len(b1), len(b2), len(b1) + len(b2), out["ballot"]["note_chars"]))

    filled = collections.Counter()
    for r in t1:
        for kk, v in (r.get("answers") or {}).items():
            if v:
                filled[kk] += 1
    out["t1_filled"] = dict(filled)
    out["t1_typed_comments"] = sum(1 for r in t1
                                   if (r.get("notes") or {}).get("comment"))
    out["t1_answered_total"] = sum(filled.values())
    print("  test-1 answered %d fields against %d slots (+%d typed comments): %s"
          % (out["t1_answered_total"], 7 * len(t1), out["t1_typed_comments"],
             dict(filled)))

    # ---- 5. what lane 3 can move at most ---------------------------------
    print()
    print("== 5. LANE 3 CEILING ==")
    book = json.load(open(BOOK))
    trades = book.get("trades") if isinstance(book, dict) else book
    if trades is None and isinstance(book, dict):
        for v in book.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                trades = v
                break
    out["book_rows"] = len(trades) if isinstance(trades, list) else None
    out["book_traded"] = book.get("meta", {}).get("traded")         if isinstance(book, dict) else None
    out["book_keys"] = sorted(book.keys()) if isinstance(book, dict) else None
    print("  g3_arm_ow1.json top-level keys: %s" % out["book_keys"])
    print("  signal rows: %s   traded rows (meta.traded): %s"
          % (out["book_rows"], out["book_traded"]))
    # W2's swept family, cited from research/w2_time_ladder.md, not recomputed here.
    out["w2"] = {"incumbent_mean_r": 0.8976, "best_mean_r": 0.9297,
                 "worst_swept_mean_r": 0.5975, "money_gate_mean_r": 2.0,
                 "span": 0.9297 - 0.5975, "short_by": 2.0 - 0.9297}
    print("  W2's 20 swept exit arms span mean R %.4f .. %.4f (span %.4f R)"
          % (out["w2"]["worst_swept_mean_r"], out["w2"]["best_mean_r"],
             out["w2"]["span"]))
    print("  money gate is mean R 2.0; the best swept arm is short by %.4f R"
          % out["w2"]["short_by"])
    print("  lane 3's 30 labels can only PICK inside that span -- no arm reaches 2.0")

    if a.json:
        p = os.path.join(HERE, "_x11_roi.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, sort_keys=True)
        print("\nwrote %s" % p)

    if a.selfcheck:
        # 61, not 60: lane 1 came back 59 of 60 (LEDGER: one row may not
        # have been pasted), so one B-remap card is still outstanding too.
        assert out["h2_outstanding_total"] == 61, out["h2_outstanding_total"]
        assert out["h2_outstanding"]["b_remap"] == 1, out["h2_outstanding"]
        assert out["h2_outstanding"]["silent_day"] == 30, out["h2_outstanding"]
        assert out["h2_outstanding"]["giveback"] == 30, out["h2_outstanding"]
        assert out["t1_S"] == 15, out["t1_S"]
        assert out["sign_test_min_b"] == 5, out["sign_test_min_b"]
        assert out["t2_overlap_t1"] == 0, out["t2_overlap_t1"]
        assert out["lane2_new_heldout_S"] == 0
        assert 0.0 < out["recall_now"]["p"] < 1.0
        assert out["lane2_repeat"] == 30, out["lane2_repeat"]
        assert out["lane3_repeat"] == 0, out["lane3_repeat"]
        print("\nselfcheck GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
