"""g73_marks25_precision.py -- what the 25 graded cards of 2026-08-29 actually say.

READ-ONLY on every judgement file. Reads:
    research/marks/probe_g71_homework_s3_2026-08-29.jsonl   (25 answers, Austin)
    research/decks/g71-homework-s3-manifest.jsonl           (30 served + answer key)
    research/bt2y_trades.json                               (the 2-year book)
    research/g71_samplesize_corpus.json                     (the graded corpus index)

Writes ONE file: research/g73_marks25_precision.json.

Four questions, in order of how much they are worth:

1. PRECISION BY ARM, with Wilson intervals. n = 7..10 per arm. The intervals
   overlap so heavily that ranking the arms is not supported; the script prints
   the pairwise overlap explicitly so nobody is tempted.

2. THE REJECTION REASONS AS A SPEC. For each reason he gave, does the engine
   have a check that means the same thing, and did it fire on that card? The
   answer key carries `downgrades` -- downgrade.score()'s verdict at the
   engine's own entry bar -- so this is a direct comparison, not a re-derivation.

3. ENTRY-MINUTE GROUND TRUTH. 21 of 25 notes carry the minute he would have
   entered. Compared against (a) the engine's entry bar on the card's own
   signal and (b) the nearest engine signal of ANY kind on the same symbol-day.
   The gap between (a) and (b) is the whole finding.

4. RECALL/PRECISION RE-STATED. The sample is selected on "the engine fired and
   graded it S", so it can measure precision and CANNOT measure recall. Said out
   loud, with the arithmetic.

    python research/g73_marks25_precision.py
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MARKS = os.path.join(HERE, "marks", "probe_g71_homework_s3_2026-08-29.jsonl")
MANIFEST = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")
BOOK = os.path.join(HERE, "bt2y_trades.json")
CORPUS = os.path.join(HERE, "g71_samplesize_corpus.json")
OUT = os.path.join(HERE, "g73_marks25_precision.json")

Z = 1.959963984540054                      # two-sided 95%


# ------------------------------------------------------------------ statistics

def wilson(k: int, n: int, z: float = Z):
    """Wilson score interval. The right interval at n=7; the normal
    approximation is not defined there and would print nonsense."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1.0 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def jeffreys(k: int, n: int):
    """Beta(k+.5, n-k+.5) 95% -- a second opinion so the width of the bar is not
    an artefact of one interval's convention. Computed by bisection on the
    regularised incomplete beta, no scipy dependency."""
    a, b = k + 0.5, n - k + 0.5

    def betacf(x, a, b):
        # Lentz's method, standard.
        tiny = 1e-30
        qab, qap, qam = a + b, a + 1.0, a - 1.0
        c, d = 1.0, 1.0 - qab * x / qap
        if abs(d) < tiny:
            d = tiny
        d = 1.0 / d
        h = d
        for m in range(1, 300):
            m2 = 2 * m
            aa = m * (b - m) * x / ((qam + m2) * (a + m2))
            d = 1.0 + aa * d
            if abs(d) < tiny:
                d = tiny
            c = 1.0 + aa / c
            if abs(c) < tiny:
                c = tiny
            d = 1.0 / d
            h *= d * c
            aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
            d = 1.0 + aa * d
            if abs(d) < tiny:
                d = tiny
            c = 1.0 + aa / c
            if abs(c) < tiny:
                c = tiny
            d = 1.0 / d
            de = d * c
            h *= de
            if abs(de - 1.0) < 3e-16:
                break
        return h

    def ibeta(x, a, b):
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        lbeta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                 + a * math.log(x) + b * math.log(1 - x))
        if x < (a + 1) / (a + b + 2):
            return math.exp(lbeta) * betacf(x, a, b) / a
        return 1.0 - math.exp(lbeta) * betacf(1 - x, b, a) / b

    def inv(target):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if ibeta(mid, a, b) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    return (inv(0.025), inv(0.975))


def fisher_2x2(a, b, c, d):
    """Two-sided Fisher exact on [[a,b],[c,d]]. Small n; chi-square is invalid."""
    from math import comb
    n = a + b + c + d
    r1, c1 = a + b, a + c

    def p_of(x):
        return (comb(r1, x) * comb(n - r1, c1 - x)) / comb(n, c1)

    obs = p_of(a)
    lo = max(0, c1 - (n - r1))
    hi = min(r1, c1)
    return sum(p_of(x) for x in range(lo, hi + 1) if p_of(x) <= obs + 1e-12)


# ------------------------------------------------------------------ time parse

# Austin writes the minute bare: "9:47", "10:09", sometimes inside a sentence.
# "9:%5" (IWM 2026-08-06) is a typo. It is NOT guessed at -- it is reported as
# unparseable and dropped from the timing sample, which is the whole point of
# saying so.
TIME_RE = re.compile(r"\b(\d{1,2}):([0-5]\d)\b")


def parse_times(note: str):
    """Every well-formed clock time in a note, in session order, as minutes past
    midnight ET. Returns ([mins], [raw]) plus a list of malformed near-misses."""
    if not note:
        return [], [], []
    good, raw = [], []
    for m in TIME_RE.finditer(note):
        h, mi = int(m.group(1)), int(m.group(2))
        if not (9 <= h <= 11):
            continue
        t = h * 60 + mi
        if not (9 * 60 + 30 <= t <= 11 * 60):
            continue
        good.append(t)
        raw.append(m.group(0))
    # near-miss: a colon with something that is not two digits round it
    bad = [s for s in re.findall(r"\b\d{1,2}:\S{1,2}", note)
           if not TIME_RE.fullmatch(s)]
    return good, raw, bad


# --------------------------------------------------------------- time INTENT
# A clock time in a note is not automatically "the minute I would have entered".
# Three of them are him narrating something else, and folding those into the
# offset distribution would be inventing data. Every classification below quotes
# the clause it is read from; the note is printed beside it in the JSON so the
# call is checkable rather than asserted.
#
#   entry      -- the minute he would have taken
#   candidate  -- the minute he evaluated and then rejected (still a real
#                 timestamp of where his eye went, but not a trade he'd take)
#   narration  -- a minute that is about something else entirely
TIME_INTENT = {
    "NFLX_2026-05-26": ("entry", "'9:47 OCR stop green candle wick'"),
    "COIN_2025-07-10": ("entry", "bare time, yes card"),
    "MSFT_2025-08-29": ("entry", "'9:38 is the entry'"),
    "GOOGL_2024-10-29": ("entry", "bare time, yes card"),
    "AAPL_2026-04-17": ("entry", "bare time, yes card"),
    "SPY_2025-05-21": ("entry", "'9:45 BR OCR confluence'"),
    "INTC_2026-03-24": ("entry", "'entry at 9:38'"),
    "AVGO_2024-11-04": ("entry", "bare time, yes card"),
    "TSM_2026-07-07": ("entry", "'9:38 and yes reclaim'"),
    "AMZN_2025-12-11": ("entry", "bare time, yes card"),
    "ACHR_2026-06-16": ("entry", "'9:57 as candle forming'"),
    "SPY_2026-06-17": ("entry", "'i see a fake out S trade at 9:48'"),
    "ACHR_2026-04-13": ("entry", "'10:09 would never trade because look how the "
                                 "candles are' -- the minute is his, the trade is not"),
    "META_2026-06-22": ("entry", "bare time, yes card"),
    "QQQ_2024-08-26": ("entry", "'9:56 but i may be biased' -- the 9:45 in the "
                                "same note is the thing biasing him, not an entry"),
    "AMD_2025-09-08": ("candidate", "'10:37 but really no displacement ... so i "
                                    "have to downgrade'"),
    "QQQ_2025-12-22": ("candidate", "'9:45 its close i see what your seeing'"),
    "AVGO_2025-12-03": ("candidate", "'9:33 can be a great break of pdl but the "
                                     "retest missed by a few cents'"),
    "MSFT_2024-09-13": ("narration", "'9:47 is what YOU liked' -- he is naming "
                                     "the engine's pick, not his own"),
    "TSM_2025-11-26": ("narration", "'hard to get past the green candle at 9:35' "
                                    "-- an obstacle, not an entry"),
}


def hhmm(t: int) -> str:
    return f"{t // 60:02d}:{t % 60:02d}"


def to_min(s: str) -> int:
    h, m = s.split(":")[:2]
    return int(h) * 60 + int(m)


# ------------------------------------------------------------------ load

def load():
    answers = [json.loads(l) for l in open(MARKS, encoding="utf-8") if l.strip()]
    manifest = {}
    for l in open(MANIFEST, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            manifest[r["card_id"]] = r
    return answers, manifest


def book_rows_for(keys):
    """Every book row on the 25 symbol-days. The book is 137 MB; loaded once."""
    with open(BOOK, encoding="utf-8") as f:
        book = json.load(f)
    want = set(keys)
    out = defaultdict(list)
    for t in book["trades"]:
        k = f"{t['sym']}_{t['day']}"
        if k in want:
            out[k].append(t)
    for k in out:
        out[k].sort(key=lambda t: (to_min(t["et"]), t.get("seq", 0)))
    return out, book["meta"]


# ------------------------------------------------------------------ main

def main():
    answers, manifest = load()
    cards = []
    for a in answers:
        cid = a["card_id"]
        m = manifest.get(cid, {})
        yes = a["answers"]["is_s"][0] == "yes"
        why = a["answers"].get("why_not", [])
        notes = a.get("notes", {}) or {}
        note_text = " ".join(v for v in notes.values() if v)
        mins, raws, bad = parse_times(note_text)
        cards.append({
            "card_id": cid, "symbol": a["symbol"], "date": a["date"],
            "bucket": a["bucket"], "claimed_setup": a["claimed_setup"],
            "claimed_level": a["claimed_level"],
            "is_s": yes, "why_not": why, "note": note_text,
            "his_times": [hhmm(t) for t in mins], "his_times_min": mins,
            "unparseable_time_tokens": bad,
            "engine_et": m.get("et"), "engine_setup": m.get("engine_setup"),
            "engine_downgrades": m.get("downgrades", []),
            "engine_tripped": m.get("tripped"),
            "engine_confluence": m.get("confluence"),
            "legacy_grade": m.get("legacy_grade"),
            "traded": m.get("traded"), "r": m.get("r"), "out": m.get("outcome"),
            "dir": m.get("dir"),
            "s_signals_that_day": m.get("s_signals_that_day"),
            "er_session": (m.get("prefilter") or {}).get("er_session"),
            "impulse_atr": (m.get("prefilter") or {}).get("impulse_atr"),
        })

    res = {"generated": "g73_marks25_precision.py", "n_cards": len(cards)}

    # ---------------------------------------------------------- 1. precision
    overall_k = sum(1 for c in cards if c["is_s"])
    arms = {}
    for arm in ("84", "OCR", "BR"):
        sub = [c for c in cards if c["bucket"] == arm]
        k, n = sum(1 for c in sub if c["is_s"]), len(sub)
        lo, hi = wilson(k, n)
        jlo, jhi = jeffreys(k, n)
        arms[arm] = {"yes": k, "n": n, "rate": round(k / n, 4),
                     "wilson95": [round(lo, 4), round(hi, 4)],
                     "wilson_width_pts": round((hi - lo) * 100, 1),
                     "jeffreys95": [round(jlo, 4), round(jhi, 4)],
                     "cards": [c["card_id"] for c in sub]}
    lo, hi = wilson(overall_k, len(cards))
    res["precision"] = {
        "overall": {"yes": overall_k, "n": len(cards),
                    "rate": round(overall_k / len(cards), 4),
                    "wilson95": [round(lo, 4), round(hi, 4)],
                    "wilson_width_pts": round((hi - lo) * 100, 1)},
        "by_arm": arms,
    }
    # pairwise: do the intervals overlap, and does Fisher separate them
    pairs = {}
    names = ["84", "OCR", "BR"]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            A, B = arms[a], arms[b]
            ov = not (A["wilson95"][1] < B["wilson95"][0]
                      or B["wilson95"][1] < A["wilson95"][0])
            p = fisher_2x2(A["yes"], A["n"] - A["yes"], B["yes"], B["n"] - B["yes"])
            pairs[f"{a}_vs_{b}"] = {"intervals_overlap": ov,
                                    "fisher_p_two_sided": round(p, 4),
                                    "separated_at_0.05": p < 0.05}
    res["precision"]["pairwise"] = pairs
    # how many more cards per arm to halve the interval
    res["precision"]["note"] = (
        "Every pairwise interval overlaps. At n=7..10 the 95% interval is "
        "40-60 points wide, so the arms are not ranked by this sample and no "
        "reading of it supports 'the 84% rule is better than break-and-retest'.")

    # ------------------------------------------------- 2. rejection reasons
    ENGINE_VARS = {
        "no_displacement": "downgrade.no_displacement",
        "level_not_respected": "downgrade.level_not_respected",
        "no_retest": "downgrade.no_retest",
        "stale_retest": "downgrade.stale_retest",
        "exhausted": "downgrade.exhausted",
        "counter_trend_not_respected": "downgrade.counter_trend_not_respected",
        "break_then_rejection": "downgrade.break_then_rejection",
        "ocr_not_respected": "downgrade.ocr_not_respected",
    }
    # his reason -> the nearest engine check, and whether it is really the same
    REASON_MAP = {
        "no_displacement": ("no_displacement", "same question"),
        "level_not_respected": ("level_not_respected", "same question"),
        "no_retest": ("no_retest", "same question"),
        "chop": ("level_not_respected",
                 "PARTIAL -- the engine only knows chop ON THE LEVEL "
                 "(closes sitting on it). It has no whole-session chop "
                 "variable in the ladder."),
        "late": (None,
                 "ABSENT -- signal_runner's [late] tag means 'the level was "
                 "already broken earlier in the session' (omen_bot.py:696), "
                 "a DIRTY-LEVEL test, not a clock test. Nothing in "
                 "downgrade.VARIABLES asks how far into the session the entry "
                 "is, and the only clock rule is the 09:30-11:00 window "
                 "(SESSION_END), which 10:37 passes."),
        "other": (None, "free text -- read the note"),
    }
    reasons = Counter()
    for c in cards:
        for w in c["why_not"]:
            reasons[w] += 1
    reason_rows = []
    for reason, n in reasons.most_common():
        var, verdict = REASON_MAP[reason]
        hits = []
        for c in cards:
            if reason not in c["why_not"]:
                continue
            fired = (var in (c["engine_downgrades"] or [])) if var else None
            hits.append({"card_id": c["card_id"], "engine_et": c["engine_et"],
                         "engine_downgrades": c["engine_downgrades"],
                         "engine_variable_fired": fired,
                         "er_session": c["er_session"],
                         "note": c["note"]})
        reason_rows.append({
            "reason": reason, "count": n,
            "engine_variable": var,
            "engine_has_this_check": verdict,
            "fired_on": sum(1 for h in hits if h["engine_variable_fired"]),
            "cards": hits,
        })
    res["rejection_reasons"] = {
        "tally": dict(reasons),
        "rows": reason_rows,
        "cannot_compute": [
            r["reason"] for r in reason_rows if r["engine_variable"] is None],
    }
    # the chop cards vs the yes cards on the one chop-ish number the engine
    # already computes but never gates on: session efficiency ratio.
    chop_cards = [c for c in cards if "chop" in c["why_not"]]
    yes_cards = [c for c in cards if c["is_s"]]
    def _mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 4) if xs else None
    res["rejection_reasons"]["er_session_probe"] = {
        "what": ("t21_card_filter already computes a session efficiency ratio "
                 "(er_session) on every card. Nothing gates on it. If 'chop' "
                 "is a real variable, the chop cards should sit low."),
        "chop_cards": {c["card_id"]: c["er_session"] for c in chop_cards},
        "mean_er_chop": _mean([c["er_session"] for c in chop_cards]),
        "mean_er_yes": _mean([c["er_session"] for c in yes_cards]),
        "mean_er_all": _mean([c["er_session"] for c in cards]),
        "caveat": "n=3 chop cards. Directional only, not a result.",
    }

    # --------------------------------------------- 3. entry-minute ground truth
    keys = [c["card_id"] for c in cards]
    rows_by_day, meta = book_rows_for(keys)
    res["book_meta"] = meta

    # ---- the card's own book row, matched on et + setup + level price + dir,
    # so the legacy tags can be read. The engine has a SECOND displacement test
    # besides downgrade.no_displacement: the [nodisp] tag on B&R rows.
    def card_row(c):
        m = manifest[c["card_id"]]
        for t in rows_by_day.get(c["card_id"], []):
            if (t["et"] == m["et"] and t["setup"] == m["engine_setup"]
                    and t["dir"] == m["dir"]
                    and abs((t.get("level_px") or 0) - (m.get("level_px") or 0)) < 1e-6):
                return t
        return None

    disp = []
    for c in cards:
        t = card_row(c)
        tags = t.get("tags", []) if t else None
        disp.append({"card_id": c["card_id"], "bucket": c["bucket"],
                     "is_s": c["is_s"], "why_not": c["why_not"],
                     "matched_book_row": t is not None,
                     "tags": tags,
                     "legacy_nodisp_tag": ("nodisp" in tags) if tags is not None else None,
                     "legacy_late_tag": ("late" in tags) if tags is not None else None,
                     "downgrade_no_displacement": "no_displacement" in c["engine_downgrades"]})
    nod_yes = sum(1 for d in disp if d["legacy_nodisp_tag"] and d["is_s"])
    nod_no = sum(1 for d in disp if d["legacy_nodisp_tag"] and not d["is_s"])
    res["displacement"] = {
        "why": ("The engine tests displacement in TWO places and neither agrees "
                "with him here: downgrade.no_displacement (fired on 0 of his 3 "
                "no-displacement rejections) and the legacy [nodisp] tag."),
        "legacy_nodisp_tag_on_yes_cards": nod_yes,
        "legacy_nodisp_tag_on_no_cards": nod_no,
        "nodisp_tag_by_bucket": dict(Counter(
            d["bucket"] for d in disp if d["legacy_nodisp_tag"])),
        "cards_with_nodisp_tag": [d["card_id"] for d in disp if d["legacy_nodisp_tag"]],
        "unmatched_rows": [d["card_id"] for d in disp if not d["matched_book_row"]],
        "structural": ("[nodisp] is emitted only on the break-and-retest path "
                       "(signal_runner writes it beside the B&R note). Two of "
                       "his three no-displacement rejections are OCR cards, "
                       "where no displacement test of any kind runs."),
        "rows": disp,
    }

    timing = []
    for c in cards:
        if not c["his_times_min"]:
            timing.append({"card_id": c["card_id"], "status": "no time given",
                           "unparseable": c["unparseable_time_tokens"],
                           "note": c["note"]})
            continue
        # If he names more than one minute, the FIRST is his entry; later ones
        # are him narrating another candle ("a break retest ... happens at 9:45").
        his = c["his_times_min"][0]
        eng = to_min(c["engine_et"])
        day_rows = rows_by_day.get(c["card_id"], [])
        all_ets = sorted({to_min(t["et"]) for t in day_rows})
        s_ets = sorted({to_min(t["et"]) for t in day_rows if t.get("sgrade") == "S"})
        traded_ets = sorted({to_min(t["et"]) for t in day_rows if t.get("traded")})

        def nearest(pool):
            if not pool:
                return None, None
            best = min(pool, key=lambda t: abs(t - his))
            return hhmm(best), best - his

        n_all, d_all = nearest(all_ets)
        n_s, d_s = nearest(s_ets)
        n_tr, d_tr = nearest(traded_ets)
        # Was the card late because the DETECTOR is late, or because the card
        # builder's level filter pushed it late? The builder takes
        # min(tripped, et) among rows in the bucket whose level resolves to one
        # of Austin's six (g71_homework_build.py:312), so an earlier row in the
        # same bucket that named no level of his is invisible to the card.
        SETUP_OF = {"reentry_84_rule": "84", "one_candle_rule": "OCR",
                    "break_and_retest": "BR"}
        same = [t for t in day_rows if SETUP_OF.get(t["setup"]) == c["bucket"]]
        same_ets = sorted({to_min(t["et"]) for t in same})
        same_s = sorted({to_min(t["et"]) for t in same if t.get("sgrade") == "S"})
        intent, why = TIME_INTENT.get(c["card_id"], ("unclassified", ""))
        timing.append({
            "card_id": c["card_id"], "bucket": c["bucket"], "is_s": c["is_s"],
            "time_intent": intent, "intent_reason": why,
            "his_time": hhmm(his), "his_all_times": c["his_times"],
            "engine_card_et": c["engine_et"],
            "offset_card_min": eng - his,
            "n_engine_signals_that_day": len(all_ets),
            "engine_first_et": hhmm(all_ets[0]) if all_ets else None,
            "engine_last_et": hhmm(all_ets[-1]) if all_ets else None,
            "bucket_first_et": hhmm(same_ets[0]) if same_ets else None,
            "offset_bucket_first_min": (same_ets[0] - his) if same_ets else None,
            "bucket_first_S_et": hhmm(same_s[0]) if same_s else None,
            "offset_bucket_first_S_min": (same_s[0] - his) if same_s else None,
            "nearest_any_et": n_all, "offset_nearest_any_min": d_all,
            "nearest_S_et": n_s, "offset_nearest_S_min": d_s,
            "nearest_traded_et": n_tr, "offset_nearest_traded_min": d_tr,
            "note": c["note"],
        })

    have = [t for t in timing if "offset_card_min" in t]

    def dist(vals):
        vals = sorted(v for v in vals if v is not None)
        if not vals:
            return {}
        n = len(vals)
        med = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
        return {
            "n": n, "min": vals[0], "max": vals[-1], "median": med,
            "mean": round(sum(vals) / n, 2),
            "exact_0": sum(1 for v in vals if v == 0),
            "within_1": sum(1 for v in vals if abs(v) <= 1),
            "within_3": sum(1 for v in vals if abs(v) <= 3),
            "within_5": sum(1 for v in vals if abs(v) <= 5),
            "engine_later": sum(1 for v in vals if v > 0),
            "engine_earlier": sum(1 for v in vals if v < 0),
            "values": vals,
        }

    entry_only = [t for t in have if t["time_intent"] == "entry"]

    res["entry_minute"] = {
        "parsed": len(have), "unparsed": len(timing) - len(have),
        "intent_mix": dict(Counter(t["time_intent"] for t in have)),
        "unparseable_detail": [
            {"card_id": t["card_id"], "tokens": t.get("unparseable"),
             "note": t.get("note")}
            for t in timing if "offset_card_min" not in t],
        "vs_card_signal": dist([t["offset_card_min"] for t in have]),
        "vs_nearest_any_engine_signal": dist(
            [t["offset_nearest_any_min"] for t in have]),
        "vs_nearest_S_signal": dist([t["offset_nearest_S_min"] for t in have]),
        "vs_nearest_traded_signal": dist(
            [t["offset_nearest_traded_min"] for t in have]),
        "vs_bucket_first_signal": dist(
            [t["offset_bucket_first_min"] for t in have]),
        "vs_bucket_first_S_signal": dist(
            [t["offset_bucket_first_S_min"] for t in have]),
        # the clean sample: only the minutes he actually meant as an entry
        "ENTRY_INTENT_ONLY": {
            "n": len(entry_only),
            "vs_card_signal": dist([t["offset_card_min"] for t in entry_only]),
            "vs_nearest_any_engine_signal": dist(
                [t["offset_nearest_any_min"] for t in entry_only]),
            "vs_bucket_first_signal": dist(
                [t["offset_bucket_first_min"] for t in entry_only]),
        },
        "rows": timing,
    }

    # What IS the engine doing at his minute? +/-2 bars, every row, with the
    # grade it gave. This is the direct test of DIRECTION.md's claim that "the
    # engine reaches his setup and grades it X".
    at_his_minute = []
    for t in timing:
        if "offset_card_min" not in t or t["time_intent"] != "entry":
            continue
        his = to_min(t["his_time"])
        rows = [r for r in rows_by_day.get(t["card_id"], [])
                if abs(to_min(r["et"]) - his) <= 2]
        at_his_minute.append({
            "card_id": t["card_id"], "his_time": t["his_time"],
            "bucket": t["bucket"],
            "engine_rows_within_2min": len(rows),
            "setups": sorted({r["setup"] for r in rows}),
            "sgrades": dict(Counter(r.get("sgrade") for r in rows)),
            "legacy_grades": dict(Counter(r.get("grade") for r in rows)),
            "traded": sum(1 for r in rows if r.get("traded")),
            "detail": [{"et": r["et"], "setup": r["setup"], "dir": r["dir"],
                        "level": r.get("level_name"), "sgrade": r.get("sgrade"),
                        "grade": r.get("grade"), "traded": r.get("traded"),
                        "r": r.get("r"), "downgrades": r.get("downgrades")}
                       for r in rows],
        })
    silent = [a["card_id"] for a in at_his_minute
              if a["engine_rows_within_2min"] == 0]
    fired_x = [a for a in at_his_minute
               if a["engine_rows_within_2min"] and not a["traded"]]
    res["entry_minute"]["at_his_minute"] = {
        "n": len(at_his_minute),
        "engine_has_a_signal_within_2min": len(at_his_minute) - len(silent),
        "engine_silent_within_2min": len(silent),
        "silent_cards": silent,
        "has_signal_but_took_no_trade": [a["card_id"] for a in fired_x],
        "took_a_trade_at_his_minute": [a["card_id"] for a in at_his_minute
                                       if a["traded"]],
        "rows": at_his_minute,
    }
    # split by arm -- the 84% arm is a re-entry by construction, so its card
    # signal is the SECOND attempt and a large positive offset is expected
    by_arm = {}
    for arm in ("84", "OCR", "BR"):
        sub = [t for t in have if t["bucket"] == arm]
        by_arm[arm] = {
            "vs_card": dist([t["offset_card_min"] for t in sub]),
            "vs_nearest_any": dist([t["offset_nearest_any_min"] for t in sub]),
        }
    res["entry_minute"]["by_arm"] = by_arm

    # ------------------------------------------- 3b. what these 25 days paid
    # The engine's own S-grader nominated these 25 symbol-days as its best. What
    # did the engine actually DO with them, in dollars, at 1R = $1,000?
    money = {"days_with_a_trade": 0, "trades": 0, "pnl": 0.0,
             "yes_days": {"days": 0, "trades": 0, "pnl": 0.0},
             "no_days": {"days": 0, "trades": 0, "pnl": 0.0}, "rows": []}
    yes_of = {c["card_id"]: c["is_s"] for c in cards}
    for cid, rows in sorted(rows_by_day.items()):
        taken = [t for t in rows if t.get("traded")]
        if not taken:
            continue
        pnl = sum(t["pnl"] for t in taken)
        money["days_with_a_trade"] += 1
        money["trades"] += len(taken)
        money["pnl"] += pnl
        side = "yes_days" if yes_of[cid] else "no_days"
        money[side]["days"] += 1
        money[side]["trades"] += len(taken)
        money[side]["pnl"] += pnl
        money["rows"].append({"card_id": cid, "austin_says_S": yes_of[cid],
                              "n_trades": len(taken), "pnl": round(pnl, 2),
                              "ets": [t["et"] for t in taken],
                              "r": [t["r"] for t in taken]})
    money["days_with_no_trade"] = len(cards) - money["days_with_a_trade"]
    money["per_trade"] = round(money["pnl"] / money["trades"], 2) if money["trades"] else None
    money["note"] = ("1R = $1,000, book research/bt2y_trades.json rebuilt "
                     "2026-08-29 18:38. These are the engine's OWN best days by "
                     "its own S-grader.")
    res["money_on_these_25_days"] = money

    # ------------------------------------------------ 4. precision vs recall
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    corpus_keys = {r["key"] for r in corpus["rows"]}
    repeats = [c["card_id"] for c in cards if c["card_id"] in corpus_keys]
    res["corpus"] = {
        "corpus_judged_symbol_days_before": corpus["summary"][
            "distinct_judged_symbol_days"],
        "cards_already_in_corpus": repeats,
        "new_symbol_days": len(cards) - len(repeats),
        "new_S_days": sum(1 for c in cards
                          if c["is_s"] and c["card_id"] not in corpus_keys),
        "S_days_before": corpus["summary"]["S_days_total"],
    }

    res["what_this_can_and_cannot_measure"] = {
        "precision_measured": {
            "definition": ("of the symbol-days the engine BOTH fired on AND "
                           "graded S on Austin's ladder (downgrade.py), what "
                           "share does his eye also call S"),
            "value": f"{overall_k}/{len(cards)} = {overall_k/len(cards):.1%}",
            "wilson95": res["precision"]["overall"]["wilson95"],
        },
        "recall_NOT_measurable_here": (
            "Every card was selected because the engine fired and graded it S. "
            "Recall asks the opposite question -- of HIS S days, how many does "
            "the engine reach -- and a sample conditioned on the engine firing "
            "has recall 25/25 by construction. Pooling these 25 into the recall "
            "number would move it up for free. They are excluded."),
        "recall_side_effect": (
            "The 16 new yes-days DO enlarge the S pool for the NEXT recall "
            "measurement, and on all 16 the engine already fires, so the honest "
            "arithmetic is stated in the report rather than folded in here."),
        "different_precision_already_on_the_board": (
            "g72_recall278_paired reports precision 37.7% -- 'the engine fired "
            "on a day Austin graded none'. That is a DAY-level question over an "
            "unselected corpus. This page's 64% is a SIGNAL-level question over "
            "days the engine's own S-grader already picked. They are not the "
            "same number and must never be compared as though they were."),
    }

    res["cards"] = cards
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)

    # ---------------------------------------------------------------- console
    p = res["precision"]
    print(f"OVERALL {p['overall']['yes']}/{p['overall']['n']} = "
          f"{p['overall']['rate']:.1%}  95% CI "
          f"[{p['overall']['wilson95'][0]:.1%}, {p['overall']['wilson95'][1]:.1%}]")
    for arm, a in p["by_arm"].items():
        print(f"  {arm:>3}  {a['yes']}/{a['n']} = {a['rate']:.1%}  "
              f"95% CI [{a['wilson95'][0]:.1%}, {a['wilson95'][1]:.1%}]  "
              f"width {a['wilson_width_pts']} pts")
    for k, v in p["pairwise"].items():
        print(f"  {k}: overlap={v['intervals_overlap']} "
              f"fisher p={v['fisher_p_two_sided']}")
    print()
    print("REASONS", dict(reasons))
    for r in reason_rows:
        print(f"  {r['reason']:>20}  n={r['count']}  engine fired on "
              f"{r['fired_on']}  [{r['engine_variable'] or 'NO ENGINE CHECK'}]")
    print()
    em = res["entry_minute"]
    print(f"ENTRY MINUTE  parsed {em['parsed']}, unparsed {em['unparsed']}")
    print("  intent mix:", em["intent_mix"])
    for label in ("vs_card_signal", "vs_nearest_any_engine_signal",
                  "vs_nearest_S_signal", "vs_nearest_traded_signal",
                  "vs_bucket_first_signal", "vs_bucket_first_S_signal"):
        d = em[label]
        if d:
            print(f"  {label:>32}  median {d['median']:+} min  "
                  f"mean {d['mean']:+}  exact {d['exact_0']}  "
                  f"<=1 {d['within_1']}  <=3 {d['within_3']}  "
                  f"later {d['engine_later']} earlier {d['engine_earlier']}  "
                  f"range [{d['min']:+}, {d['max']:+}]")
    eo = em["ENTRY_INTENT_ONLY"]
    print(f"  ENTRY-INTENT ONLY (n={eo['n']}):")
    for label in ("vs_card_signal", "vs_nearest_any_engine_signal",
                  "vs_bucket_first_signal"):
        d = eo[label]
        if d:
            print(f"    {label:>32}  median {d['median']:+} min  "
                  f"exact {d['exact_0']}  <=1 {d['within_1']}  "
                  f"<=3 {d['within_3']}  later {d['engine_later']} "
                  f"earlier {d['engine_earlier']}")
    for arm, d in em["by_arm"].items():
        c = d["vs_card"]
        a = d["vs_nearest_any"]
        if c:
            print(f"  arm {arm:>3}: vs card median {c['median']:+}  "
                  f"vs nearest-any median {a['median']:+}")
    print()
    ahm = em["at_his_minute"]
    print(f"  AT HIS MINUTE (+/-2, n={ahm['n']}): signal on "
          f"{ahm['engine_has_a_signal_within_2min']}, silent on "
          f"{ahm['engine_silent_within_2min']} {ahm['silent_cards']}")
    print(f"    traded at his minute: {ahm['took_a_trade_at_his_minute']}")
    for a in ahm["rows"]:
        print(f"    {a['card_id']:>18} {a['his_time']} rows={a['engine_rows_within_2min']:>2} "
              f"setups={','.join(s[:3] for s in a['setups']):<12} "
              f"sgrade={a['sgrades']} legacy={a['legacy_grades']} traded={a['traded']}")
    print()
    mo = res["money_on_these_25_days"]
    print(f"MONEY on the 25 days: traded {mo['days_with_a_trade']}/25 days, "
          f"{mo['trades']} trades, ${mo['pnl']:,.0f} "
          f"(${mo['per_trade']:,.0f}/trade).  "
          f"his-S days ${mo['yes_days']['pnl']:,.0f}, "
          f"his-not-S days ${mo['no_days']['pnl']:,.0f}")
    print()
    d = res["displacement"]
    print(f"DISPLACEMENT: legacy [nodisp] tag on {d['legacy_nodisp_tag_on_yes_cards']} "
          f"YES cards vs {d['legacy_nodisp_tag_on_no_cards']} NO cards; "
          f"by bucket {d['nodisp_tag_by_bucket']}; unmatched {d['unmatched_rows']}")
    print()
    print("corpus:", json.dumps(res["corpus"]))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
