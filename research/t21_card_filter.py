"""t21_card_filter.py -- the deck PRE-FILTER. Every future deck passes through it.

Austin's process complaint, research/marks/probe_master_2026-08-29.jsonl:

    "Sometimes in certain categories I had to give u the same answer over and over,
     you know better not to give me old trades that don't fit my system."

Of the 90 graded cards in that probe he refused 64 outright -- 27 of 40 vetoes,
20 of 20 rare, 12 of 15 index, 5 of 15 runner. His reasons, verbatim:

    "The chop is really really bad" / "too choppy"  -> CHOP
    "Later in the day lower probability"            -> WINDOW
    "you know better"
    "what am I looking at you know this is wrong easilly"

The spec named five criteria: in-window, not chop, clean level, real displacement,
plausible RR. **Three of the five do not survive contact with his labels.**
Measured as a ranking AUC over the 26 cards he engaged with vs the 64 he refused
(`--auc` reproduces this table):

    nearest-level distance    AUC 0.486   chance
    level touch count         AUC 0.442   chance
    break-bar range vs prior  AUC 0.490   chance
    RR to the NEAREST level   AUC 0.466   chance

What does separate them, all four backward-looking at the proposed entry bar:

    minute of the proposed entry (earlier better)   AUC 0.714
    session efficiency ratio (chop)                 AUC 0.678
    reach: R to the FURTHEST watched level ahead    AUC 0.728, INVERTED
    impulse: best 3-bar close move in the prior 10  AUC 0.608

`reach` is the surprise and it is the opposite of "plausible RR". The cards he
refused have levels EIGHT R away (median 7.24R) while the cards he graded have
them at 2.66R. A level 8R away is not a target -- it means price is in
no-man's-land with no structure near it. Big paper RR is a symptom of a bad
card, not a good one.

SCOPE. This selects CARDS OUT OF COMPLETED SESSIONS for homework. It reads the
whole session (the chop measure spans 09:30-11:00) because that is exactly the
chart Austin will be shown. It must NEVER be wired into detection or into
backtest_week -- that would be look-ahead. Deliberately excluded for the same
reason: any feature measuring how far price travelled AFTER the entry (the
strongest single feature found, AUC 0.675), because selecting on it would stack
future decks with winners and corrupt the grading it exists to protect.

Public API -- this is what research/build_deck.py imports:

    features(symbol, day, et=None) -> dict | None
    verdict(feat, cfg=DEFAULT)     -> (bool ok, list[str] reasons)
    card_ok(symbol, day, et=None)  -> bool

Reproduce every number in research/t21_card-selection.md:

    python research/t21_card_filter.py --auc --sweep --cv --pool 600
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import statistics
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from t4_engine_recall import (rth_candles, prior_day_levels,  # noqa: E402
                              premarket_extremes)

MASTER = os.path.join(HERE, "marks", "probe_master_2026-08-29.jsonl")
ARCHIVE = os.path.join(ROOT, "data_archive")

SESSION_START = "09:30"
SESSION_END = "11:00"


# ---------------------------------------------------------------- thresholds
# Not one of these numbers is Austin's. Each is fitted, and the fit is reported
# with an out-of-sample estimate in research/t21_card-selection.md.
#
# `late_window` sits at 11:00, i.e. the window check only asserts the deck
# standard's own 09:30-11:00 bound, because R13 is explicit that 10:45-11:00 is
# "a bad ENTRY window, noted not banned". The sweep agrees: banning 10:45+ costs
# more graded cards than it saves refusals.
DEFAULT = {
    "late_window": "11:00",       # reject entries at/after this clock time
    "min_er_session": 0.05,       # Kaufman efficiency ratio 09:30-11:00
    "max_reach_r": 8.0,           # R to the furthest watched level ahead
    "min_impulse_atr": 1.2,       # best 3-bar close move in the prior 10, in ATR
}

ALL_CHECKS = ("window", "chop", "reach", "displacement")
# Checks that need a proposed entry minute. A whole-session card (a silent day
# in a mixed deck) is judged on `chop` alone -- see features().
ENTRY_CHECKS = ("window", "reach", "displacement")


# ------------------------------------------------------------------ features
def _session(symbol: str, day: str):
    c = rth_candles(symbol, day)
    if not c:
        return None
    out = [x for x in c if SESSION_START <= x.timestamp[:5] < SESSION_END]
    return out or None


def _mean_range(bars) -> float:
    return (sum(b.high - b.low for b in bars) / len(bars)) if bars else 0.0


def _efficiency_ratio(bars) -> float:
    """Kaufman ER: net displacement / total path length. 1.0 = a straight line,
    ~0.0 = pure chop. This is the number behind "the chop is really really bad"."""
    if len(bars) < 3:
        return 0.0
    path = sum(abs(bars[i].close - bars[i - 1].close) for i in range(1, len(bars)))
    return (abs(bars[-1].close - bars[0].close) / path) if path > 0 else 0.0


def _levels(symbol: str, day: str, bars) -> dict:
    """The six levels OMEN watches (R23: premarket levels are one of them)."""
    pdh, pdl, _o, _c = prior_day_levels(symbol, day)
    pmh, pml = premarket_extremes(symbol, day)
    orh = max(b.high for b in bars[:5]) if len(bars) >= 5 else None
    orl = min(b.low for b in bars[:5]) if len(bars) >= 5 else None
    return {"PDH": pdh, "PDL": pdl, "PMH": pmh, "PML": pml, "ORH": orh, "ORL": orl}


def features(symbol: str, day: str, et: str | None = None) -> dict | None:
    """Bar-computable description of one candidate card, or None if unscoreable.

    ``et`` is the proposed entry minute "HH:MM". When it is None the card is a
    whole-session card and only the session-level features are meaningful;
    ``entry_anchored`` is False and verdict() then applies `chop` alone.
    """
    bars = _session(symbol, day)
    if not bars or len(bars) < 20:
        return None

    f = {"symbol": symbol, "day": day, "bars": len(bars),
         "er_session": round(_efficiency_ratio(bars), 4),
         "entry_anchored": False, "et": None,
         "reach_r": None, "impulse_atr": None,
         "level": None, "level_dist_atr": None, "rr_near": None}

    if not et:
        return f

    idx = next((i for i, b in enumerate(bars) if b.timestamp[:5] == et[:5]), None)
    if idx is None:
        return None
    f["entry_anchored"] = True
    f["et"] = bars[idx].timestamp[:5]

    atr = _mean_range(bars[:max(10, idx)]) or _mean_range(bars) or 0.01
    lv = _levels(symbol, day, bars)
    px = bars[idx].close
    direction = 1 if bars[idx].close >= bars[idx].open else -1

    # risk = the retest swing behind the entry, the same 5-bar look-back the
    # deck card shows as its stop
    lo = min(b.low for b in bars[max(0, idx - 5):idx + 1])
    hi = max(b.high for b in bars[max(0, idx - 5):idx + 1])
    risk = max((px - lo) if direction > 0 else (hi - px), atr * 0.25)

    ahead = [v for v in lv.values()
             if v is not None and ((v > px) if direction > 0 else (v < px))]
    if ahead:
        far = (max(ahead) - px) if direction > 0 else (px - min(ahead))
        near = (min(ahead) - px) if direction > 0 else (px - max(ahead))
        f["reach_r"] = round(far / risk, 4)
        f["rr_near"] = round(near / risk, 4)
    else:                       # R9's fallback: no level ahead -> default 2R
        f["reach_r"] = 2.0
        f["rr_near"] = 2.0

    f["impulse_atr"] = round(
        max(abs(bars[j].close - bars[max(0, j - 3)].close)
            for j in range(max(3, idx - 10), idx + 1)) / atr, 4) if idx >= 3 else 0.0

    dists = sorted((abs(px - v) / atr, n) for n, v in lv.items() if v is not None)
    if dists:
        f["level_dist_atr"], f["level"] = round(dists[0][0], 4), dists[0][1]
    f["risk_atr"] = round(risk / atr, 4)
    f["atr"] = round(atr, 4)

    # --- diagnostic only, never used by verdict(). These are the alternative
    # definitions of the spec's "clean level", "real displacement" and
    # "plausible RR" that were tried and did NOT separate his labels. They are
    # computed here so `--auc` can print the evidence rather than assert it.
    p10 = bars[max(0, idx - 10):idx]
    mr = _mean_range(p10) or 0.01
    tol = max(0.25 * (bars[idx - 1].high - bars[idx - 1].low), atr * 0.10) \
        if idx >= 1 else atr * 0.25
    lvl_val = lv[f["level"]] if f["level"] else None
    touches, armed = 0, True
    if lvl_val is not None:
        for b in bars[:idx + 1]:
            near = (b.low - tol) <= lvl_val <= (b.high + tol)
            if near and armed:
                touches, armed = touches + 1, False
            elif not near:
                armed = True
    f["dx_level_touches"] = touches
    f["dx_level_clutter"] = sum(1 for d, _ in dists if d < 1.0)
    f["dx_disp_bar_range"] = round((bars[idx].high - bars[idx].low) / mr, 4)
    f["dx_disp_bar_body"] = round(abs(bars[idx].close - bars[idx].open) / mr, 4)
    f["dx_disp_max5"] = round(max((b.high - b.low) / mr
                                  for b in bars[max(0, idx - 5):idx + 1]), 4)
    f["dx_disp_move5_atr"] = round(
        abs(bars[idx].close - bars[max(0, idx - 5)].close) / atr, 4)
    f["dx_er_pre15"] = round(_efficiency_ratio(bars[max(0, idx - 15):idx + 1]), 4)
    f["dx_er_pre30"] = round(_efficiency_ratio(bars[max(0, idx - 30):idx + 1]), 4)
    f["dx_vol_ratio"] = round(
        bars[idx].volume / (sum(b.volume for b in p10) / len(p10)), 4) \
        if p10 and sum(b.volume for b in p10) else 0.0
    return f


# ------------------------------------------------------------------- verdict
def verdict(feat: dict, cfg: dict = None, checks=ALL_CHECKS):
    """(ok, reasons). ``reasons`` names every check the card failed.

    A card with no proposed entry is judged on the session checks only; the
    entry-anchored checks are skipped rather than failed, so a clean trending
    day the engine was silent on still reaches the deck. That is the recall half
    of a mixed deck and it must not be filtered away.
    """
    cfg = cfg or DEFAULT
    if not feat.get("entry_anchored"):
        checks = tuple(c for c in checks if c not in ENTRY_CHECKS)
    bad = []
    if "window" in checks and not (SESSION_START <= feat["et"] < cfg["late_window"]):
        bad.append("window")
    if "chop" in checks and feat["er_session"] < cfg["min_er_session"]:
        bad.append("chop")
    if "reach" in checks and feat["reach_r"] > cfg["max_reach_r"]:
        bad.append("reach")
    if "displacement" in checks and feat["impulse_atr"] < cfg["min_impulse_atr"]:
        bad.append("displacement")
    return (not bad), bad


def card_ok(symbol: str, day: str, et: str | None = None, cfg: dict = None) -> bool:
    f = features(symbol, day, et)
    return False if f is None else verdict(f, cfg)[0]


# ---------------------------------------------------------------- label set
def load_labels():
    """His 90 card verdicts from probe_master_2026-08-29.jsonl.

    KEEP   = he engaged with the card (gave it a grade, or an exit plan)
    REJECT = he refused it outright

    vetoes  40  grade s/a/c = KEEP (13),  grade "no" = REJECT (27)
    runner  15  gave an exit = KEEP (10), "wouldn't trade" = REJECT (5)
    rare    20  ALL REJECT -- 17 "not this setup at all" + 3 "real but not tradeable"
    index   15  s = KEEP (3), no = REJECT (12)

    The file is READ ONLY. Never write it.
    """
    out = []
    with open(MASTER, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            lane = r.get("lane")
            if lane not in ("vetoes", "rare", "index", "runner"):
                continue
            a = r.get("answers") or {}
            if lane == "vetoes":
                keep = (a.get("grade") or [""])[0] in ("s", "a", "c")
            elif lane == "index":
                keep = (a.get("s") or [""])[0] == "s"
            elif lane == "runner":
                keep = bool(a.get("exit"))
            else:
                keep = False
            out.append({"card_id": r["card_id"], "symbol": r["symbol"],
                        "day": r["date"], "et": r.get("et") or None,
                        "lane": lane, "keep": keep,
                        "note": " ".join((r.get("notes") or {}).values())})
    return out


# -------------------------------------------------------------------- scoring
def score(rows, cfg, checks=ALL_CHECKS):
    """Confusion against his verdicts. PASS is the positive class."""
    tp = fp = tn = fn = 0
    for r in rows:
        f = r.get("_f")
        if f is None:
            continue
        ok = verdict(f, cfg, checks)[0]
        if r["keep"] and ok:
            tp += 1
        elif r["keep"]:
            fn += 1
        elif ok:
            fp += 1
        else:
            tn += 1
    n = tp + fp + tn + fn
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    spec = tn / (tn + fp) if (tn + fp) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"n": n, "tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": prec,
            "recall": rec, "specificity": spec, "f1": f1,
            "pass_rate": (tp + fp) / n if n else 0.0,
            "accuracy": (tp + tn) / n if n else 0.0}


def wilson(k, n, z=1.96):
    """95% CI on a proportion -- this track's error bar (method rule 1)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - h), min(1.0, c + h))


def fisher_exact(a, b, c, d):
    """Two-sided Fisher exact p on the 2x2 [[a,b],[c,d]]. The right test here:
    the passing cards are a SUBSET of the graded cards, so comparing the filtered
    keep-rate to the whole-deck keep-rate double-counts. What is actually being
    asked is whether PASS and FAIL differ in keep-rate."""
    from math import comb
    n = a + b + c + d
    r1, r2, c1 = a + b, c + d, a + c

    def p(x):
        return comb(r1, x) * comb(r2, c1 - x) / comb(n, c1)

    obs = p(a)
    lo = max(0, c1 - r2)
    hi = min(r1, c1)
    return sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs * (1 + 1e-9))


def newcombe_diff(k1, n1, k2, n2, z=1.96):
    """95% CI on (p1 - p2) by Newcombe's score method -- the error bar this
    track reports (method rule 1)."""
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    p1 = k1 / n1 if n1 else 0.0
    p2 = k2 / n2 if n2 else 0.0
    d = p1 - p2
    lo = d - ((p1 - l1) ** 2 + (u2 - p2) ** 2) ** 0.5
    hi = d + ((u1 - p1) ** 2 + (p2 - l2) ** 2) ** 0.5
    return d, max(-1.0, lo), min(1.0, hi)


def _auc(pos, neg):
    if not pos or not neg:
        return 0.5
    tot = hits = 0.0
    for a in pos:
        for b in neg:
            tot += 1
            hits += 1.0 if a > b else (0.5 if a == b else 0.0)
    return hits / tot


def _fmt(s):
    return ("n=%3d pass=%3d(%5.1f%%) prec=%5.1f%% rec=%5.1f%% spec=%5.1f%% "
            "acc=%5.1f%% F1=%.3f [tp%d fp%d tn%d fn%d]"
            % (s["n"], s["tp"] + s["fp"], 100 * s["pass_rate"], 100 * s["precision"],
               100 * s["recall"], 100 * s["specificity"], 100 * s["accuracy"],
               s["f1"], s["tp"], s["fp"], s["tn"], s["fn"]))


GRID = {
    "late_window": ["10:30", "10:45", "11:00"],
    "min_er_session": [0.00, 0.05, 0.07, 0.09, 0.11, 0.13],
    "max_reach_r": [3.0, 4.0, 5.0, 6.0, 8.0, 1e9],
    "min_impulse_atr": [0.0, 1.2, 1.5, 1.8, 2.1],
}


def _fit_cfg(rows):
    """Pick the highest-F1 config on ``rows``, refusing configs whose pass rate
    is outside 10-60% (method rule 3: an unreachable or saturated gate is a
    finding about the gate)."""
    best, bestkey = None, None
    for combo in itertools.product(*GRID.values()):
        cfg = dict(zip(GRID, combo))
        s = score(rows, cfg)
        if not (0.10 <= s["pass_rate"] <= 0.60):
            continue
        key = (s["f1"], s["accuracy"])
        if bestkey is None or key > bestkey:
            best, bestkey = cfg, key
    return best or dict(DEFAULT)


# ------------------------------------------------------------------- driver
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", type=int, default=400)
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--auc", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--cv", action="store_true")
    args = ap.parse_args()

    rows = load_labels()
    for r in rows:
        r["_f"] = features(r["symbol"], r["day"], r["et"])
    usable = [r for r in rows if r["_f"] is not None]
    print("labels: %d cards, %d scoreable, %d without archive bars"
          % (len(rows), len(usable), len(rows) - len(usable)))
    for lane in ("vetoes", "runner", "rare", "index"):
        s = [r for r in usable if r["lane"] == lane]
        print("   %-7s %3d cards  KEEP %2d  REJECT %2d"
              % (lane, len(s), sum(r["keep"] for r in s),
                 sum(not r["keep"] for r in s)))
    fit = [r for r in usable if r["lane"] in ("vetoes", "runner")]
    held = [r for r in usable if r["lane"] in ("rare", "index")]

    # ---------- do the five spec criteria separate his labels at all?
    if args.auc:
        print("\n=== RANKING POWER of every candidate feature (AUC, 0.5=chance) ===")
        cand = [("entry minute (earlier)", lambda f: -(int(f["et"][:2]) * 60 + int(f["et"][3:5]))),
                ("chop: session ER", lambda f: f["er_session"]),
                ("reach: R to furthest level (LOWER better)", lambda f: -f["reach_r"]),
                ("displacement: 3-bar impulse/ATR", lambda f: f["impulse_atr"]),
                ("SPEC clean-level: nearest-level dist (LOWER better)", lambda f: -f["level_dist_atr"]),
                ("SPEC clean-level: touch count (LOWER better)", lambda f: -f["dx_level_touches"]),
                ("SPEC clean-level: levels within 1 ATR (LOWER better)", lambda f: -f["dx_level_clutter"]),
                ("SPEC displacement: break-bar range / prior 10", lambda f: f["dx_disp_bar_range"]),
                ("SPEC displacement: break-bar BODY / prior 10", lambda f: f["dx_disp_bar_body"]),
                ("SPEC displacement: widest of the last 5 bars", lambda f: f["dx_disp_max5"]),
                ("SPEC displacement: 5-bar close move / ATR", lambda f: f["dx_disp_move5_atr"]),
                ("SPEC plausible-RR: RR to the NEAREST level", lambda f: f["rr_near"]),
                ("alt chop: ER over the prior 15 bars", lambda f: f["dx_er_pre15"]),
                ("alt chop: ER over the prior 30 bars", lambda f: f["dx_er_pre30"]),
                ("volume on the entry bar / prior 10", lambda f: f["dx_vol_ratio"]),
                ("risk in ATR", lambda f: f["risk_atr"])]
        print("   (entry-anchored cards only -- the 15 index cards carry no proposed")
        print("    entry minute, so only the session chop feature exists for them)")
        for nm, S in (("ALL", usable), ("FIT vetoes+runner", fit),
                      ("HELD-OUT rare+index", held)):
            S = [r for r in S if r["_f"]["entry_anchored"]]
            P = [r for r in S if r["keep"]]
            N = [r for r in S if not r["keep"]]
            print("   --- %s (%d keep / %d reject)" % (nm, len(P), len(N)))
            for label, fn in cand:
                a = _auc([fn(r["_f"]) for r in P], [fn(r["_f"]) for r in N])
                mark = "  <-- chance" if abs(a - 0.5) < 0.06 else ""
                print("       %-45s AUC %.3f%s" % (label, a, mark))

    # ---------- reachability BEFORE tuning (method rule 3)
    print("\n=== REACHABILITY of each check on all 90 cards ===")
    for chk in ALL_CHECKS:
        trip = sum(1 for r in usable if chk in verdict(r["_f"], DEFAULT, (chk,))[1])
        rate = trip / len(usable)
        flag = ""
        if rate < 0.01:
            flag = "  <-- DEAD (<1%): the finding is the check, not the threshold"
        elif rate > 0.85:
            flag = "  <-- SATURATED (>85%)"
        print("   %-13s trips on %3d/%3d = %5.1f%%%s"
              % (chk, trip, len(usable), 100 * rate, flag))

    print("\n=== SINGLE-CHECK power (all 90) ===")
    for chk in ALL_CHECKS:
        print("   %-13s %s" % (chk, _fmt(score(usable, DEFAULT, (chk,)))))

    print("\n=== ABLATION: leave one check out (all 90) ===")
    print("   %-13s %s" % ("ALL", _fmt(score(usable, DEFAULT))))
    for chk in ALL_CHECKS:
        rest = tuple(c for c in ALL_CHECKS if c != chk)
        print("   %-13s %s" % ("-" + chk, _fmt(score(usable, DEFAULT, rest))))

    # ---------- headline
    print("\n=== THE FILTER at DEFAULT ===")
    print("   %s" % json.dumps(DEFAULT))
    print("   fit      (vetoes+runner)  %s" % _fmt(score(fit, DEFAULT)))
    print("   held-out (rare+index)     %s" % _fmt(score(held, DEFAULT)))
    print("   all 90                    %s" % _fmt(score(usable, DEFAULT)))

    def _headline(name, S):
        s = score(S, DEFAULT)
        npass, nfail = s["tp"] + s["fp"], s["tn"] + s["fn"]
        k = sum(r["keep"] for r in S)
        d, lo, hi = newcombe_diff(s["tp"], npass, s["fn"], nfail) if (npass and nfail) \
            else (0.0, 0.0, 0.0)
        p = fisher_exact(s["tp"], s["fp"], s["fn"], s["tn"])
        print("   --- %s (n=%d, he graded %d)" % (name, len(S), k))
        print("       whole deck, no filter : he refuses %d/%d = %.1f%%"
              % (len(S) - k, len(S), 100 * (len(S) - k) / len(S)))
        print("       cards the filter PASSES: he refuses %d/%d = %.1f%%  (graded %.1f%%)"
              % (s["fp"], npass, 100 * s["fp"] / npass if npass else 0,
                 100 * s["precision"]))
        print("       cards the filter DROPS : he refuses %d/%d = %.1f%%  (graded %.1f%%)"
              % (s["tn"], nfail, 100 * s["tn"] / nfail if nfail else 0,
                 100 * s["fn"] / nfail if nfail else 0))
        print("       EFFECT  pass-group graded-rate MINUS drop-group graded-rate")
        print("               = %+.1f points   95%% CI [%+.1f, %+.1f]   Fisher p = %.4f"
              % (100 * d, 100 * lo, 100 * hi, p))
        print("               %s"
              % ("INSIDE its own bar -> NULL RESULT" if lo <= 0 <= hi
                 else "outside its bar -> real"))
        print("       recall of his graded cards kept: %d/%d = %.1f%%"
              % (s["tp"], k, 100 * s["recall"]))
        return s, d, lo, hi, p

    print("\n   THE NUMBER THAT MATTERS -- how much of his attention a deck wastes:")
    _headline("ALL 90 (fit + held-out)", usable)
    _headline("FIT vetoes+runner (thresholds fitted here)", fit)
    _headline("HELD-OUT rare+index (never fitted on)", held)

    # ---------- nested CV: the honest out-of-sample estimate
    if args.cv:
        print("\n=== NESTED CV -- thresholds REFIT inside every fold, 5 folds x 20 seeds ===")
        keeps, precs, recs = [], [], []
        for seed in range(20):
            rng = random.Random(1000 + seed)
            idx = list(range(len(usable)))
            rng.shuffle(idx)
            folds = [idx[i::5] for i in range(5)]
            tp = fp = fn = 0
            for fo in folds:
                test = [usable[i] for i in fo]
                train = [usable[i] for i in idx if i not in set(fo)]
                cfg = _fit_cfg(train)
                for r in test:
                    ok = verdict(r["_f"], cfg)[0]
                    if r["keep"] and ok:
                        tp += 1
                    elif r["keep"]:
                        fn += 1
                    elif ok:
                        fp += 1
            precs.append(tp / (tp + fp) if (tp + fp) else 0.0)
            recs.append(tp / (tp + fn) if (tp + fn) else 0.0)
            keeps.append(tp + fp)
        print("   out-of-fold keep-rate of passing cards: mean %.1f%%  sd %.1f  min %.1f%%  max %.1f%%"
              % (100 * statistics.mean(precs), 100 * statistics.pstdev(precs),
                 100 * min(precs), 100 * max(precs)))
        print("   out-of-fold recall of his graded cards: mean %.1f%%  sd %.1f"
              % (100 * statistics.mean(recs), 100 * statistics.pstdev(recs)))
        nk = sum(r["keep"] for r in usable)
        print("   base rate to beat (unfiltered deck): %.1f%%" % (100 * nk / len(usable)))
        print("   cards passing per fold-set: mean %.1f of %d" %
              (statistics.mean(keeps), len(usable)))

    if args.sweep:
        print("\n=== THRESHOLD SWEEP (top 10 by all-90 F1, pass rate 10-60%%) ===")
        out = []
        for combo in itertools.product(*GRID.values()):
            cfg = dict(zip(GRID, combo))
            s = score(usable, cfg)
            if not (0.10 <= s["pass_rate"] <= 0.60):
                continue
            out.append((s["f1"], cfg, s, score(fit, cfg), score(held, cfg)))
        out.sort(key=lambda x: -x[0])
        for f1, cfg, s, sf, sh in out[:10]:
            print("   F1=%.3f  %s" % (f1, json.dumps(cfg)))
            print("      all90 %s" % _fmt(s))
        print("   (%d of %d grid points are reachable at all)"
              % (len(out), len(list(itertools.product(*GRID.values())))))

    print("\n=== WHY his 64 refused cards were rejected (reason mix) ===")
    nref = sum(not r["keep"] for r in usable)
    cnt = Counter()
    for r in usable:
        if not r["keep"]:
            for why in verdict(r["_f"], DEFAULT)[1]:
                cnt[why] += 1
    for kk, v in cnt.most_common():
        print("   %-13s caught %3d of %d refused cards (%.1f%%)"
              % (kk, v, nref, 100 * v / nref))

    print("\n=== HIS REFUSALS THE FILTER STILL LETS THROUGH ===")
    for r in usable:
        if not r["keep"] and verdict(r["_f"], DEFAULT)[0]:
            f = r["_f"]
            print("   %-22s %-7s et=%-5s er=%.3f reach=%-7s imp=%-5s %s"
                  % (r["card_id"], r["lane"], f["et"] or "--", f["er_session"],
                     ("%.2fR" % f["reach_r"]) if f["reach_r"] is not None else "--",
                     ("%.2f" % f["impulse_atr"]) if f["impulse_atr"] is not None else "--",
                     r["note"][:38]))

    print("\n=== CARDS HE GRADED THAT THE FILTER DROPS (the cost) ===")
    for r in usable:
        ok, why = verdict(r["_f"], DEFAULT)
        if r["keep"] and not ok:
            print("   %-22s %-7s %-24s %s"
                  % (r["card_id"], r["lane"], ",".join(why), r["note"][:38]))

    # ---------- pool survival
    print("\n=== POOL SURVIVAL ===")
    days = []
    for sym in sorted(os.listdir(ARCHIVE)):
        d = os.path.join(ARCHIVE, sym)
        if not os.path.isdir(d):
            continue
        days += [(sym, f[:-4]) for f in os.listdir(d) if f.endswith(".csv")]
    rng = random.Random(args.seed)
    rng.shuffle(days)
    sample = days[:args.pool]

    # (a) whole-session cards, the silent half of a mixed deck: chop only
    ok = bad = skip = 0
    for sym, day in sample:
        f = features(sym, day, None)
        if f is None:
            skip += 1
            continue
        if verdict(f, DEFAULT)[0]:
            ok += 1
        else:
            bad += 1
    lo, hi = wilson(ok, ok + bad)
    print("   whole-session cards (silent half, chop check only):")
    print("      %d/%d = %.1f%% survive  95%% CI [%.1f%%, %.1f%%]   (%d unscoreable of %d sampled, pool %d days)"
          % (ok, ok + bad, 100 * ok / (ok + bad), 100 * lo, 100 * hi, skip,
             len(sample), len(days)))

    # (b) entry-anchored cards: the engine's own first proposed entry
    from t4_engine_recall import run_day
    ok = bad = nofire = err = 0
    reasons = Counter()
    probed = 0
    for sym, day in sample:
        if probed >= args.pool:
            break
        try:
            entries, _s, _r = run_day(sym, day)
        except Exception:
            err += 1
            continue
        if not entries:
            nofire += 1
            continue
        probed += 1
        et = entries[0]["timestamp"][:5]
        f = features(sym, day, et)
        if f is None:
            err += 1
            continue
        good, why = verdict(f, DEFAULT)
        if good:
            ok += 1
        else:
            bad += 1
            for w in why:
                reasons[w] += 1
    tot = ok + bad
    if tot:
        lo, hi = wilson(ok, tot)
        print("   entry-anchored cards (fire half, all four checks):")
        print("      %d/%d = %.1f%% survive  95%% CI [%.1f%%, %.1f%%]   (%d sampled days were silent, %d unscoreable)"
              % (ok, tot, 100 * ok / tot, 100 * lo, 100 * hi, nofire, err))
        for kk, v in reasons.most_common():
            print("         rejected for %-13s %4d (%.1f%% of fire days)"
                  % (kk, v, 100 * v / tot))


if __name__ == "__main__":
    main()
