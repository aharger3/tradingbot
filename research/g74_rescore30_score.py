"""g74_rescore30_score.py -- re-score the G7.1 precision homework on ALL 30 answers.

Austin graded 30 cards on 2026-08-29. Every card is a symbol-day the ENGINE claims
is an S; he answered yes/no and, when no, why. An earlier read used only the first
25 rows. The 5 late cards are all "yes", so every per-arm number published before
this script is stale.

    input  research/marks/probe_g71_homework_s3_2026-08-29_complete.jsonl   READ-ONLY
           research/decks/g71-homework-s3-manifest.jsonl                    the answer key
           research/bt2y_trades.json                                        the 2-year book
           data/cache/<SYM>/1min/<DAY>.csv                                  bars

    output research/g74_rescore30.json      every number in the write-up
           (prints the same tables to stdout)

WHAT IT MEASURES
    1. precision per arm, Wilson 95% intervals, pairwise Newcombe difference
       intervals, Fisher exact, and the sample size that would actually separate
       80% from 60%.
    2. the "BR+OCR" label: how it is assigned, how often, and whether it tests
       each leg for displacement (Austin's NVDA 2025-06-24 note says it must).
    3. entry-minute ground truth -- his minute vs the engine's entry bar.
    4. his rejection reasons vs the checks the engine actually owns.
    5. two ballot candidates: retest tolerance in cents, and S-vs-tradeable.

Touches no engine code and no mark file. Re-runnable.

    python research/g74_rescore30_score.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

MARKS = os.path.join(HERE, "marks",
                     "probe_g71_homework_s3_2026-08-29_complete.jsonl")
MANIFEST = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")
BOOK = os.path.join(HERE, "bt2y_trades.json")
OUT = os.path.join(HERE, "g74_rescore30.json")

Z = 1.959963984540054          # 95% two-sided
Z80 = 0.8416212335729143       # 80% power


# ---------------------------------------------------------------------------
# statistics -- written out rather than imported so the numbers are auditable
# ---------------------------------------------------------------------------

def wilson(k, n, z=Z):
    """Wilson score interval. The right one at n=10; normal-approximation
    intervals go outside [0,1] and are simply wrong at this sample size."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def newcombe(k1, n1, k2, n2, z=Z):
    """Newcombe's hybrid-score interval for p1 - p2 (independent samples).
    If it straddles 0 the two arms are not separated."""
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    d = k1 / n1 - k2 / n2
    lo = d - z * math.sqrt(l1 * (1 - l1) / n1 + u2 * (1 - u2) / n2)
    hi = d + z * math.sqrt(u1 * (1 - u1) / n1 + l2 * (1 - l2) / n2)
    return d, lo, hi


def _logchoose(n, k):
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1))


def fisher_exact_2x2(a, b, c, d):
    """Two-sided Fisher exact p for [[a,b],[c,d]] by summing every table at or
    below the observed probability. Exact, no scipy dependency."""
    n = a + b + c + d
    r1, c1 = a + b, a + c
    lo = max(0, c1 - (n - r1))
    hi = min(r1, c1)
    denom = _logchoose(n, c1)

    def lp(x):
        return math.exp(_logchoose(r1, x) + _logchoose(n - r1, c1 - x) - denom)

    obs = lp(a)
    tot = 0.0
    for x in range(lo, hi + 1):
        p = lp(x)
        if p <= obs * (1 + 1e-9):
            tot += p
    return min(1.0, tot)


def n_per_arm(p1, p2, z=Z, zb=Z80):
    """Cards PER ARM needed to call p1 vs p2 at 95% / 80% power."""
    pbar = (p1 + p2) / 2
    num = (z * math.sqrt(2 * pbar * (1 - pbar))
           + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return math.ceil(num / (p1 - p2) ** 2)


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

def jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def load():
    marks = jsonl(MARKS)
    man = {r["card_id"]: r for r in jsonl(MANIFEST)}
    assert len(marks) == 30, f"expected 30 answers, got {len(marks)}"
    for m in marks:
        assert m["card_id"] in man, m["card_id"]
    return marks, man


def said_yes(m):
    v = m.get("answers", {}).get("is_s") or []
    return v[0] == "yes"


# ---------------------------------------------------------------------------
# 1. precision per arm
# ---------------------------------------------------------------------------

def part1(marks):
    arms = defaultdict(lambda: [0, 0])          # bucket -> [yes, n]
    for m in marks:
        a = arms[m["bucket"]]
        a[1] += 1
        a[0] += 1 if said_yes(m) else 0

    rows = []
    for b in ("OCR", "BR", "84"):
        k, n = arms[b]
        lo, hi = wilson(k, n)
        rows.append({"arm": b, "yes": k, "n": n, "p": k / n,
                     "ci_lo": lo, "ci_hi": hi, "ci_width_pts": (hi - lo) * 100})

    k = sum(1 for m in marks if said_yes(m))
    lo, hi = wilson(k, len(marks))
    overall = {"yes": k, "n": len(marks), "p": k / len(marks),
               "ci_lo": lo, "ci_hi": hi}

    pairs = []
    order = {r["arm"]: r for r in rows}
    for x, y in (("OCR", "84"), ("OCR", "BR"), ("BR", "84")):
        rx, ry = order[x], order[y]
        d, lo_, hi_ = newcombe(rx["yes"], rx["n"], ry["yes"], ry["n"])
        p = fisher_exact_2x2(rx["yes"], rx["n"] - rx["yes"],
                             ry["yes"], ry["n"] - ry["yes"])
        pairs.append({"a": x, "b": y, "diff_pts": d * 100,
                      "lo_pts": lo_ * 100, "hi_pts": hi_ * 100,
                      "fisher_p": p, "separated": (lo_ > 0 or hi_ < 0)})

    need = n_per_arm(0.80, 0.60)
    return {"arms": rows, "overall": overall, "pairs": pairs,
            "arm_counts": {b: arms[b] for b in arms},
            "n_per_arm_for_80_vs_60": need,
            "extra_cards_needed": (need - 10) * 3,
            "any_pair_separated": any(p["separated"] for p in pairs)}


# ---------------------------------------------------------------------------
# 2. the BR+OCR label
# ---------------------------------------------------------------------------

def part2(marks, man, book):
    """Two questions. (a) In THIS deck, what does the BR+OCR label actually
    select? (b) In the whole book, does the label carry information at all?"""
    by_label = defaultdict(lambda: [0, 0])
    for m in marks:
        lab = m["claimed_setup"]
        by_label[lab][1] += 1
        by_label[lab][0] += 1 if said_yes(m) else 0

    deck_conf = Counter(man[m["card_id"]].get("confluence") for m in marks)

    # the label rule, read out of research/g71_homework_build.py:322 --
    #   BR bucket AND confluence == yes -> "BR+OCR"; otherwise the bucket name.
    # So an OCR-bucket card with confluence yes is still labelled "OCR".
    mislabel = [{"card_id": m["card_id"], "bucket": m["bucket"],
                 "claimed_setup": m["claimed_setup"],
                 "confluence": man[m["card_id"]].get("confluence")}
                for m in marks
                if man[m["card_id"]].get("confluence") == "yes"
                and m["claimed_setup"] != "BR+OCR"]

    xt = Counter((r["setup"], r.get("setup_label"), r.get("confluence"))
                 for r in book)
    s_rows = [r for r in book if r.get("sgrade") == "S"]
    xt_s = Counter((r["setup"], r.get("confluence")) for r in s_rows)
    conf_all = Counter(r.get("confluence") for r in book)
    conf_s = Counter(r.get("confluence") for r in s_rows)

    # can a setup reach S without the confluence +1?
    reach = {}
    for setup in ("break_and_retest", "one_candle_rule", "reentry_84_rule"):
        for c in ("yes", "no"):
            tot = sum(1 for r in book
                      if r["setup"] == setup and r.get("confluence") == c)
            s = sum(1 for r in s_rows
                    if r["setup"] == setup and r.get("confluence") == c)
            reach[f"{setup}|conf={c}"] = {
                "rows": tot, "S": s, "S_rate": (s / tot if tot else None)}

    # does has_confluence test displacement on either leg? read the source.
    import research.downgrade as dg
    import inspect
    src = inspect.getsource(dg.has_confluence)
    legs = inspect.getsource(dg.find_ocr) + inspect.getsource(dg._break_bar)
    disp_in_conf = ("displac" in src.lower()) or ("displac" in legs.lower())

    # THE MECHANISM. downgrade.score(): net = len(tripped) - (1 if confluence)
    # and S is net <= 0. So the confluence +1 buys exactly one forgiveness. Split
    # the 30 cards by whether the engine's S was bought with that +1.
    bought, merit = [0, 0], [0, 0]
    detail = []
    for m in marks:
        mm = man[m["card_id"]]
        dgs = list(mm.get("downgrades") or [])
        tgt = bought if dgs else merit
        tgt[1] += 1
        tgt[0] += 1 if said_yes(m) else 0
        if dgs:
            detail.append({"card_id": m["card_id"], "downgrades": dgs,
                           "confluence": mm.get("confluence"),
                           "he_said_yes": said_yes(m)})
    d, lo_, hi_ = newcombe(merit[0], merit[1], bought[0], bought[1])
    split = {
        "S_on_merit_zero_downgrades": {"yes": merit[0], "n": merit[1],
                                       "p": merit[0] / merit[1],
                                       "ci": wilson(*merit)},
        "S_bought_with_the_confluence_plus_one": {
            "yes": bought[0], "n": bought[1], "p": bought[0] / bought[1],
            "ci": wilson(*bought), "cards": detail},
        "diff_pts": d * 100, "lo_pts": lo_ * 100, "hi_pts": hi_ * 100,
        "fisher_p": fisher_exact_2x2(merit[0], merit[1] - merit[0],
                                     bought[0], bought[1] - bought[0]),
        "separated": (lo_ > 0 or hi_ < 0),
    }

    # ...and what that +1 is worth in money. Every S row in the book, split by
    # whether it had a downgrade the +1 erased. R x $1,000 = dollars.
    def money(rs):
        rs = [r for r in rs if r.get("traded")]
        if not rs:
            return {"trades": 0}
        v = [r["r"] for r in rs]
        return {"trades": len(v), "mean_r": sum(v) / len(v),
                "dollars_per_trade": 1000 * sum(v) / len(v),
                "win_rate": sum(1 for r in rs if r.get("out") == "win") / len(v)}

    s_merit = [r for r in s_rows if not (r.get("downgrades") or [])]
    s_bought = [r for r in s_rows if (r.get("downgrades") or [])]
    money_split = {"S_on_merit": money(s_merit), "S_bought_with_plus_one": money(s_bought),
                   "rows_merit": len(s_merit), "rows_bought": len(s_bought)}

    return {
        "confluence_plus_one_split": split,
        "confluence_plus_one_money": money_split,
        "deck_by_label": {k: {"yes": v[0], "n": v[1],
                              "p": v[0] / v[1],
                              "ci": wilson(v[0], v[1])}
                          for k, v in by_label.items()},
        "deck_confluence_counts": dict(deck_conf),
        "cards_confluent_but_not_labelled_BR+OCR": mislabel,
        "book_crosstab_setup_label_confluence": {"|".join(map(str, k)): v
                                                 for k, v in xt.items()},
        "book_S_setup_confluence": {"|".join(map(str, k)): v
                                    for k, v in xt_s.items()},
        "book_confluence_all": dict(conf_all),
        "book_confluence_S": dict(conf_s),
        "book_rows": len(book), "book_S_rows": len(s_rows),
        "S_reachability_by_confluence": reach,
        "has_confluence_tests_displacement": disp_in_conf,
    }


# ---------------------------------------------------------------------------
# 3. entry minute
# ---------------------------------------------------------------------------

TIME_RE = re.compile(r"\b(\d{1,2}):([0-5]\d)\b")
BAD_RE = re.compile(r"\b\d{1,2}:[^0-9\s]")     # "9:%5" -- a typo, never a guess


def his_minutes(m):
    """Every parseable clock token in his note, in the order he typed them,
    plus a flag for tokens that are damaged and must NOT be guessed."""
    txt = " ".join(str(v) for v in (m.get("notes") or {}).values())
    ok = [f"{int(h):02d}:{mm}" for h, mm in TIME_RE.findall(txt)]
    damaged = bool(BAD_RE.search(txt))
    return ok, damaged, txt


def to_min(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def part3(marks, man, book):
    by_day = defaultdict(list)
    for r in book:
        by_day[(r["sym"], r["day"])].append(r)

    rows = []
    for m in marks:
        cid = m["card_id"]
        mm = man[cid]
        toks, damaged, txt = his_minutes(m)
        eng = mm["et"]
        day_rows = by_day.get((mm["symbol"], mm["date"]), [])
        day_ets = sorted({r["et"] for r in day_rows})
        day_s_ets = sorted({r["et"] for r in day_rows if r.get("sgrade") == "S"})

        rec = {"card_id": cid, "bucket": m["bucket"], "yes": said_yes(m),
               "engine_et": eng, "his_tokens": toks, "damaged_token": damaged,
               "note": txt,
               "engine_signals_that_day": len(day_rows),
               "engine_S_ets_that_day": day_s_ets}
        if toks:
            first = toks[0]
            rec["his_minute"] = first
            rec["offset_min"] = to_min(eng) - to_min(first)
            if day_ets:
                rec["nearest_any_signal"] = min(
                    (abs(to_min(e) - to_min(first)), e) for e in day_ets)[1]
                rec["nearest_any_offset"] = min(
                    to_min(e) - to_min(first) for e in day_ets
                    if abs(to_min(e) - to_min(first)) == min(
                        abs(to_min(x) - to_min(first)) for x in day_ets))
            if day_s_ets:
                rec["nearest_S_offset"] = min(
                    (abs(to_min(e) - to_min(first)) for e in day_s_ets))
        else:
            rec["his_minute"] = None
            rec["offset_min"] = None
        rows.append(rec)

    # the clean subset: he said YES and the first token is stated as the entry.
    # On a NO card a clock token is a reference ("9:47 is what you liked"), not
    # a minute he would have entered, so it is reported separately, never mixed.
    clean = [r for r in rows if r["yes"] and r["offset_min"] is not None]
    allp = [r for r in rows if r["offset_min"] is not None]

    def dist(rs):
        v = sorted(r["offset_min"] for r in rs)
        if not v:
            return {}
        n = len(v)
        return {"n": n, "min": v[0], "max": v[-1],
                "median": (v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2),
                "mean": sum(v) / n,
                "engine_later": sum(1 for x in v if x > 0),
                "exact": sum(1 for x in v if x == 0),
                "engine_earlier": sum(1 for x in v if x < 0),
                "within_2min": sum(1 for x in v if abs(x) <= 2),
                "values": v}

    nearest = [r["nearest_S_offset"] for r in rows
               if r.get("nearest_S_offset") is not None]
    by_bucket = {}
    for b in ("OCR", "BR", "84"):
        sub = [r for r in clean if r["bucket"] == b]
        by_bucket[b] = dist(sub)
        ets = sorted(to_min(man[r["card_id"]]["et"]) for r in rows
                     if r["bucket"] == b)
        by_bucket[b]["engine_et_median"] = "%02d:%02d" % divmod(
            ets[len(ets) // 2], 60)
    return {"cards": rows, "by_bucket": by_bucket,
            "no_token": [r["card_id"] for r in rows if not r["his_tokens"]],
            "damaged": [r["card_id"] for r in rows if r["damaged_token"]],
            "offsets_yes_cards": dist(clean),
            "offsets_all_parseable": dist(allp),
            "nearest_S_signal_gap": {"n": len(nearest),
                                     "median": sorted(nearest)[len(nearest) // 2],
                                     "within_2min": sum(1 for x in nearest if x <= 2),
                                     "values": sorted(nearest)}}


# ---------------------------------------------------------------------------
# 4. rejection reasons vs the engine's checks
# ---------------------------------------------------------------------------

def part4(marks, man):
    import research.downgrade as dg
    checks = set(dg.CHECKS)

    # a reason maps to an engine check only if the check answers the SAME
    # question. "late" is wall-clock; stale_retest counts bars after the break,
    # which is a different question, so it is recorded as a near-miss not a hit.
    MAP = {
        "no_displacement": ("no_displacement", "exact"),
        "level_not_respected": ("level_not_respected", "exact"),
        "no_retest": ("no_retest", "exact"),
        "chop": (None, "absent"),
        "late": (None, "absent"),
        "other": (None, "case-by-case"),
    }

    rows, tally = [], Counter()
    for m in marks:
        if said_yes(m):
            continue
        mm = man[m["card_id"]]
        fired = list(mm.get("downgrades") or [])
        for why in m["answers"].get("why_not", []):
            check, kind = MAP.get(why, (None, "unknown"))
            hit = bool(check and check in fired)
            tally[(why, kind, hit)] += 1
            rows.append({"card_id": m["card_id"], "reason": why,
                         "engine_check": check, "kind": kind,
                         "engine_fired_it": hit,
                         "engine_downgrades": fired,
                         "engine_tripped": mm.get("tripped"),
                         "note": " ".join(str(v) for v in
                                          (m.get("notes") or {}).values())})

    # is the chop rule written anywhere, and is it reachable from the engine?
    chop_written = False
    chop_wired = False
    pred = os.path.join(ROOT, "predicates.py")
    if os.path.exists(pred):
        chop_written = "def is_chop_market" in open(pred, encoding="utf-8").read()
    sr = os.path.join(ROOT, "signal_runner.py")
    if os.path.exists(sr):
        t = open(sr, encoding="utf-8").read()
        chop_wired = "is_chop_market" in t
    bt = os.path.join(ROOT, "backtest_week.py")
    if os.path.exists(bt):
        chop_wired = chop_wired or "is_chop_market" in open(bt, encoding="utf-8").read()

    per_reason = defaultdict(lambda: {"n": 0, "engine_fired": 0, "kind": None,
                                      "engine_check": None})
    for r in rows:
        d = per_reason[r["reason"]]
        d["n"] += 1
        d["engine_fired"] += 1 if r["engine_fired_it"] else 0
        d["kind"] = r["kind"]
        d["engine_check"] = r["engine_check"]

    return {"rows": rows, "per_reason": dict(per_reason),
            "engine_checks": sorted(checks),
            "reason_tags_total": len(rows),
            "reason_tags_engine_agreed": sum(1 for r in rows if r["engine_fired_it"]),
            "chop_rule_written_in_predicates": chop_written,
            "chop_rule_reachable_from_engine": chop_wired}


# ---------------------------------------------------------------------------
# 5. the two ballot candidates
# ---------------------------------------------------------------------------

def read_bars(sym, day):
    p = os.path.join(ROOT, "data", "cache", sym, "1min", f"{day}.csv")
    if not os.path.exists(p):
        return []
    out = []
    with open(p, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            t = row["Datetime"][11:16]
            if not ("09:30" <= t <= "16:00"):
                continue
            out.append({"t": t, "o": float(row["Open"]), "h": float(row["High"]),
                        "l": float(row["Low"]), "c": float(row["Close"])})
    return out


def part5(marks, man):
    import research.downgrade as dg

    # (a) AVGO 2025-12-03 -- "9:33 can be a great break of pdl but the retest
    #     missed by a few cents". How many cents, and what does the engine's
    #     tolerance allow at that bar?
    mm = man["AVGO_2025-12-03"]
    bars = read_bars("AVGO", "2025-12-03")
    a = {"card_id": "AVGO_2025-12-03", "bars": len(bars),
         "claimed_level": mm.get("claimed_level"),
         "level_px_on_card": mm.get("level_px"),
         "drawn_levels": mm.get("drawn_levels"), "engine_et": mm["et"]}
    if bars:
        pdl = (mm.get("drawn_levels") or {}).get("pdl")
        idx = {b["t"]: i for i, b in enumerate(bars)}
        i33 = idx.get("09:33")
        a["bar_0933"] = bars[i33] if i33 is not None else None
        if i33 is not None:
            # He named PDL. Scan the closest approach back to EVERY level the
            # card drew, over the rest of the 09:30-11:00 window, so the answer
            # does not depend on guessing which line he meant.
            sess = [b for b in bars[i33 + 1:] if b["t"] <= "11:00"]
            approaches = {}
            for name, px in (mm.get("drawn_levels") or {}).items():
                if px is None or not sess:
                    continue
                miss = min(min(abs(b["h"] - px), abs(b["l"] - px)) for b in sess)
                approaches[name] = round(miss * 100, 1)
            a["closest_approach_cents_by_level"] = approaches
            pdl = (mm.get("drawn_levels") or {}).get("pdl")
            if pdl is not None and sess:
                miss = min(min(abs(b["h"] - pdl), abs(b["l"] - pdl))
                           for b in sess)
                a["pdl"] = pdl
                a["closest_retest_miss_dollars"] = miss
                a["closest_retest_miss_cents"] = round(miss * 100, 1)
            # the engine's own tolerance at that bar, and the two things that
            # both get called "the tolerance unit"
            a["eps_downgrade_quarter_ATR14_dollars"] = dg._eps(bars, i33)
            a["eps_downgrade_quarter_ATR14_cents"] = round(dg._eps(bars, i33) * 100, 1)
            prev_rng = bars[i33 - 1]["h"] - bars[i33 - 1]["l"] if i33 else 0.0
            a["quarter_prev_candle_range_dollars"] = 0.25 * prev_rng
            a["quarter_prev_candle_range_cents"] = round(25 * prev_rng, 1)
            a["engine_tolerance_covers_his_miss"] = (
                a.get("closest_retest_miss_dollars", 9e9)
                <= a["eps_downgrade_quarter_ATR14_dollars"])

    # (b) does S mean tradeable? scan every note for a split.
    SPLIT = [
        ("would_not_trade_but_graded_S", r"would never trade|wouldn'?t trade|would not trade"),
        ("would_trade_but_not_S", r"wish it was an s|good.{0,20}trade.{0,40}but"),
        ("hedged", r"i may be biased|its tight on|hard to get past|close i see"),
    ]
    splits = []
    for m in marks:
        txt = " ".join(str(v) for v in (m.get("notes") or {}).values()).lower()
        tags = [name for name, pat in SPLIT if re.search(pat, txt)]
        if tags:
            splits.append({"card_id": m["card_id"], "said_S": said_yes(m),
                           "tags": tags, "note": txt})
    return {"retest_cents": a, "s_vs_tradeable": splits}


# ---------------------------------------------------------------------------

def main():
    marks, man = load()
    print(f"answers: {len(marks)}   manifest rows matched: {len(man)}")
    book = json.load(open(BOOK, encoding="utf-8"))["trades"]
    print(f"book rows: {len(book)}")

    res = {"n_answers": len(marks)}
    res["precision"] = part1(marks)
    res["label"] = part2(marks, man, book)
    res["entry_minute"] = part3(marks, man, book)
    res["reasons"] = part4(marks, man)
    res["ballot"] = part5(marks, man)

    p = res["precision"]
    print("\n--- 1. precision per arm (all 30) ---")
    for r in p["arms"]:
        print(f"  {r['arm']:>4}  {r['yes']}/{r['n']}  {r['p']*100:5.1f}%   "
              f"95% CI {r['ci_lo']*100:5.1f} .. {r['ci_hi']*100:5.1f}  "
              f"(width {r['ci_width_pts']:.0f} pts)")
    o = p["overall"]
    print(f"  ALL   {o['yes']}/{o['n']}  {o['p']*100:5.1f}%   "
          f"95% CI {o['ci_lo']*100:5.1f} .. {o['ci_hi']*100:5.1f}")
    for q in p["pairs"]:
        print(f"  {q['a']} - {q['b']}: {q['diff_pts']:+.0f} pts, "
              f"95% CI {q['lo_pts']:+.0f} .. {q['hi_pts']:+.0f}, "
              f"Fisher p={q['fisher_p']:.3f}, separated={q['separated']}")
    print(f"  cards per arm to separate 80% vs 60%: {p['n_per_arm_for_80_vs_60']} "
          f"(+{p['extra_cards_needed']} more cards in total)")

    L = res["label"]
    print("\n--- 2. the BR+OCR label ---")
    for k, v in L["deck_by_label"].items():
        print(f"  {k:>7}  {v['yes']}/{v['n']}  {v['p']*100:5.1f}%  "
              f"CI {v['ci'][0]*100:.0f}..{v['ci'][1]*100:.0f}")
    print(f"  deck confluence flags: {L['deck_confluence_counts']}")
    print(f"  confluent cards NOT labelled BR+OCR: "
          f"{len(L['cards_confluent_but_not_labelled_BR+OCR'])}")
    print(f"  book: confluence={L['book_confluence_all']} of {L['book_rows']}")
    print(f"  book S rows: confluence={L['book_confluence_S']} of {L['book_S_rows']}")
    for k, v in L["S_reachability_by_confluence"].items():
        rate = "n/a" if v["S_rate"] is None else f"{v['S_rate']*100:.2f}%"
        print(f"    {k:<34} rows={v['rows']:>6}  S={v['S']:>5}  {rate}")
    print(f"  has_confluence tests displacement on either leg: "
          f"{L['has_confluence_tests_displacement']}")
    sp = L["confluence_plus_one_split"]
    mrt = sp["S_on_merit_zero_downgrades"]
    bgt = sp["S_bought_with_the_confluence_plus_one"]
    print(f"  S with ZERO downgrades:        {mrt['yes']}/{mrt['n']} "
          f"{mrt['p']*100:.1f}%  CI {mrt['ci'][0]*100:.0f}..{mrt['ci'][1]*100:.0f}")
    print(f"  S bought with the +1 (1 dg):   {bgt['yes']}/{bgt['n']} "
          f"{bgt['p']*100:.1f}%  CI {bgt['ci'][0]*100:.0f}..{bgt['ci'][1]*100:.0f}")
    print(f"  diff {sp['diff_pts']:+.0f} pts, CI {sp['lo_pts']:+.0f}..{sp['hi_pts']:+.0f}, "
          f"Fisher p={sp['fisher_p']:.3f}, separated={sp['separated']}")
    for c in bgt["cards"]:
        print(f"    {c['card_id']:<18} dg={c['downgrades']} he_said_yes={c['he_said_yes']}")
    ms = L["confluence_plus_one_money"]
    for k in ("S_on_merit", "S_bought_with_plus_one"):
        d = ms[k]
        if d.get("trades"):
            print(f"  book money {k:<24} trades={d['trades']:>4} "
                  f"${d['dollars_per_trade']:+8.0f}/trade  win {d['win_rate']*100:.1f}%")

    E = res["entry_minute"]
    print("\n--- 3. entry minute: him vs the engine ---")
    print(f"  no clock token: {E['no_token']}")
    print(f"  damaged token (never guessed): {E['damaged']}")
    for tag in ("offsets_yes_cards", "offsets_all_parseable"):
        d = E[tag]
        print(f"  {tag}: n={d['n']} median={d['median']:+} mean={d['mean']:+.1f} "
              f"range {d['min']:+}..{d['max']:+}  "
              f"engine later={d['engine_later']} exact={d['exact']} "
              f"earlier={d['engine_earlier']} within2={d['within_2min']}")
    for b, d in E["by_bucket"].items():
        if d.get("n"):
            print(f"  {b:>4}: n={d['n']} median offset {d['median']:+} min, "
                  f"engine median entry {d['engine_et_median']}")
    g = E["nearest_S_signal_gap"]
    print(f"  nearest engine S signal that day: median gap {g['median']} min, "
          f"within 2 min on {g['within_2min']}/{g['n']}")

    R = res["reasons"]
    print("\n--- 4. his reasons vs the engine's checks ---")
    for why, d in sorted(R["per_reason"].items()):
        print(f"  {why:<22} n={d['n']}  engine check={d['engine_check']} "
              f"({d['kind']})  fired {d['engine_fired']}/{d['n']}")
    print(f"  reason tags total {R['reason_tags_total']}, "
          f"engine agreed on {R['reason_tags_engine_agreed']}")
    print(f"  chop rule written in predicates.py: {R['chop_rule_written_in_predicates']}; "
          f"reachable from the engine: {R['chop_rule_reachable_from_engine']}")

    B = res["ballot"]
    a = B["retest_cents"]
    print("\n--- 5. ballot candidates ---")
    print(f"  AVGO 2025-12-03 09:33 bar: {a.get('bar_0933')}")
    print(f"  PDL {a.get('pdl')}  closest retest miss "
          f"{a.get('closest_retest_miss_cents')} cents")
    print(f"  engine tolerance (0.25*ATR14) {a.get('eps_downgrade_quarter_ATR14_cents')} cents; "
          f"25% of prev candle range {a.get('quarter_prev_candle_range_cents')} cents")
    print(f"  covered by the existing unit: {a.get('engine_tolerance_covers_his_miss')}")
    for s in B["s_vs_tradeable"]:
        print(f"  {s['card_id']:<18} said_S={s['said_S']}  {s['tags']}")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
