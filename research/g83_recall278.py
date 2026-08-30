"""g83_recall278 -- replay EVERY bar-backed graded day through the REAL router.

Austin ratified this on 2026-08-30 ("run the free 278 first"). It is the machine
half of the accuracy question: no new grading, two minutes of compute per arm,
and it moves the sample the whole project steers by from 34 cards to every
symbol-day he has ever judged that has bars on disk.

What this file does that nothing before it did
----------------------------------------------
1. **Reads the whole pile, once.** Grades come from `research/marks_pool.py`,
   the canonical (symbol, date) -> grade view across all 24 mark corpora, which
   knows the NINE spellings of "S" that `research/g71_board.md` reported as five.
   Every earlier recall script was hardcoded to ONE 100-card file
   (`research/marks/probe_s_sweep_2026-08-28.jsonl`, 34 S days).
2. **Uses the fixed router.** `research/t4_engine_recall.CaptureRunner._route`
   used to be a hand-written copy of `signal_runner.SignalRunner._route` that
   never called `super()`, so every gate the shipped engine grew after that copy
   was written was invisible to the only rig that scores recall. Fixed in
   145d564e. This script asserts the delegation is present before it will
   produce a number (`assert_real_router()`).
3. **Breaks the rates down by SETUP and by ENTRY MINUTE**, using Austin's own
   labels off the mark rows (setup / answers.setup / eng_setup, and
   answers.emin / entry_t / et) as well as the engine's side, and puts a Wilson
   95% interval on every single rate.
4. **Re-runs the four A/B arms that were previously decided on 34 cards** --
   higher-timeframe veto off, pivot levels off, X-lift off, minimum-stop-percent
   off -- paired on the same days, with an exact McNemar test, and says for each
   whether the 34-card conclusion survives.

Definitions, stated once
------------------------
* A day is a **HIT** if the engine takes at least one entry on it before 11:00.
  Day-level, exactly `research/t0_heldout_recall.py::score_sweep`'s rule.
* **Recall** = hits / his S days.   **False-fire rate** = hits / his refusals
  (grade "none" -- a judgement, not a blank).
* **Precision** = S-hits / (S-hits + refusal-hits).
* Austin's ladder (S/A/C/none) is the one being scored. The legacy engine ladder
  (A+/A/B/C/X) is reported beside it and never mixed into it.

Every mark file is opened READ-ONLY. No engine file is modified. The A/B arms
are run as separate subprocesses with environment flags, because the engine
reads its tunables from the environment at import time.

Usage
-----
    python research/g83_recall278.py                 # all five arms, ~20 min
    python research/g83_recall278.py --arms base     # base only, ~4 min
    python research/g83_recall278.py --arm base --worker-out FILE   # internal
"""
from __future__ import annotations

import argparse
import inspect
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

OUT_JSON = os.path.join(HERE, "g83_recall278.json")
OUT_MD = os.path.join(HERE, "g83_recall278.md")

GATE = 0.90                       # DIRECTION.md's recall gate
Z = 1.959963984540054             # two-sided 95%
RISK_DOLLARS = 1000               # 1R, for any dollar sentence
SIX_FIG_PER_DAY = 100_000 / 252   # $396.83 -- Austin's money bar, 2026-08-30

# The four arms this project decided on 34 cards. Each is (env override, the
# 34-card file that carried the old answer).
ARMS = {
    "base":        ({}, "g71_scanners_recall_base"),
    "no_htf_veto": ({"HTF_BIAS_VETO": "0"}, "g71_scanners_recall_nohtf"),
    "no_pivot":    ({"PIVOT_LEVELS": "0"}, "g71_scanners_recall_nopivot"),
    "no_xlift":    ({"X_LIFT": "off"}, "g71_scanners_recall_noxlift"),
    "no_minstop":  ({"MIN_STOP_PCT": "0"}, "g71_scanners_recall_nominstop"),
}

BUCKETS = (("09:30-09:45", 570, 585),      # minutes from midnight, [lo, hi)
           ("09:45-10:15", 585, 615),
           ("10:15-11:00", 615, 660))


# ------------------------------------------------------------------ statistics

def wilson(k, n):
    """Wilson score 95% interval as (lo, hi) fractions. The interval this repo
    already uses (research/g72_recall278_paired.py)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def rate(k, n):
    lo, hi = wilson(k, n)
    return {"k": k, "n": n,
            "pct": round(k / n * 100, 1) if n else None,
            "wilson95_pct": [round(lo * 100, 1), round(hi * 100, 1)],
            "half_width_pts": round((hi - lo) * 50, 1) if n else None}


def newcombe_diff(k1, n1, k2, n2):
    """Newcombe hybrid-score 95% interval for (p1 - p2) between two INDEPENDENT
    groups -- his S days and his refusal days are different days, so the paired
    McNemar machinery below does not apply to the gap between them."""
    if n1 == 0 or n2 == 0:
        return (None, None)
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = k1 / n1 - k2 / n2
    lo = d - math.sqrt((k1 / n1 - l1) ** 2 + (u2 - k2 / n2) ** 2)
    hi = d + math.sqrt((u1 - k1 / n1) ** 2 + (k2 / n2 - l2) ** 2)
    return (lo, hi)


def separation(k_s, n_s, k_no, n_no):
    """The number that actually matters: how many more points of the time the
    engine fires on a day he graded S than on a day he refused. Recall alone can
    be bought by firing on everything."""
    lo, hi = newcombe_diff(k_s, n_s, k_no, n_no)
    d = (k_s / n_s - k_no / n_no) if (n_s and n_no) else None
    return {"points": round(d * 100, 1) if d is not None else None,
            "newcombe95_pts": [round(lo * 100, 1), round(hi * 100, 1)]
                              if lo is not None else None,
            "beats_coin_flip": bool(lo is not None and lo > 0)}


def binom_cdf(k, n, p):
    return min(1.0, sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                        for i in range(0, k + 1)))


def mcnemar_exact(b, c):
    """Two-sided exact McNemar on discordant pairs. b = A-only, c = B-only."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def paired_power(n, psi, d):
    """Power of a paired McNemar test to see a true d-point move when a fraction
    psi of days disagree between the arms."""
    if psi <= abs(d):
        return None
    x = (math.sqrt(n) * d - Z * math.sqrt(psi)) / math.sqrt(psi - d * d)
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# --------------------------------------------------------- his labels off marks

_SETUP_KEYS = ("break_and_retest", "one_candle_rule", "rule_84")

_MIN_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")


def _norm_setups(text):
    """Austin's setup labels are free text in five corpora and a checkbox list in
    two. Map to the three families he names. A row may carry more than one."""
    t = str(text).lower()
    out = set()
    if "84" in t:
        out.add("rule_84")
    if ("ocr" in t or "one candle" in t or "one_candle" in t
            or "order block" in t or "order_block" in t):
        out.add("one_candle_rule")
    if ("break" in t and "retest" in t) or re.search(r"\bbr\b", t) or "b&r" in t:
        out.add("break_and_retest")
    return out


def _norm_minute(v):
    """-> minutes from midnight, or None. Rejects the ['9'] junk in two files."""
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        v = v[0] if len(v) == 1 else None
    if v is None:
        return None
    m = _MIN_RE.search(str(v))
    if not m:
        return None
    h, mm = int(m.group(1)), int(m.group(2))
    if h < 4 or h > 16 or mm > 59:
        return None
    return h * 60 + mm


def bucket_of(minute):
    if minute is None:
        return None
    for name, lo, hi in BUCKETS:
        if lo <= minute < hi:
            return name
    return "outside_window"


def his_labels():
    """{key: {"setups": set, "minutes": [int]}} read-only off every mark corpus.

    Uses build_deck's own enumerator and key normaliser so this can never drift
    from the no-repeat guarantee's idea of what one symbol-day is."""
    import build_deck as bd
    out = defaultdict(lambda: {"setups": set(), "minutes": []})
    for path in bd.mark_sources():
        for row in bd._rows(path):
            key = bd._judgement_key(row)
            if not key:
                continue
            ans = row.get("answers") if isinstance(row.get("answers"), dict) else {}
            for fld in (row.get("setup"), ans.get("setup"), row.get("eng_setup"),
                        row.get("lane")):
                if fld:
                    out[key]["setups"] |= _norm_setups(fld)
            for fld in (ans.get("emin"), row.get("entry_t"), row.get("et"),
                        row.get("eng_et")):
                mn = _norm_minute(fld)
                if mn is not None:
                    out[key]["minutes"].append(mn)
    return {k: {"setups": sorted(v["setups"]), "minutes": sorted(set(v["minutes"]))}
            for k, v in out.items()}


# ------------------------------------------------------------------- the replay

def assert_real_router():
    """Refuse to publish a number off the hand-written router copy. The copy
    flattered held-out recall (23/34 vs the engine's real 22/34) because it never
    called super() -- fixed in 145d564e."""
    import t4_engine_recall as t4
    src = inspect.getsource(t4.CaptureRunner._route)
    if "super()._route" not in src:
        raise SystemExit(
            "REFUSING TO MEASURE: t4_engine_recall.CaptureRunner._route does not "
            "delegate to the shipped router. Every recall number off this path is "
            "a lie in the engine's favour. See commit 145d564e.")
    return True


def replay_all(days, label="base"):
    """days: [(key, symbol, date)] -> {key: day record}. One replay per day."""
    import t4_engine_recall as t4
    out, errs = {}, []
    t0 = time.time()
    for i, (key, sym, date) in enumerate(days):
        try:
            entries, sigs, _raw = t4.run_day(sym, date)
        except Exception as e:                                  # noqa: BLE001
            errs.append({"key": key, "error": type(e).__name__ + ": " + str(e)[:140]})
            continue
        if entries is None:
            errs.append({"key": key, "error": "no archived bars"})
            continue
        out[key] = {
            "hit": bool(entries),
            "n_entries": len(entries),
            "n_signals": len(sigs),
            "entries": [{"min": _norm_minute(e["timestamp"]),
                         "setup": e["signal_type"],
                         "legacy_grade": e["grade"]} for e in entries],
            "detected_setups": sorted({s["signal_type"] for s in sigs}),
        }
        if i and i % 250 == 0:
            print("  [%s] %d/%d  %.0fs" % (label, i, len(days), time.time() - t0),
                  flush=True)
    print("  [%s] done %d days, %d errors, %.0fs"
          % (label, len(out), len(errs), time.time() - t0), flush=True)
    return out, errs, round(time.time() - t0, 1)


# --------------------------------------------------------------------- scoring

_ENGINE_SETUP_TO_FAMILY = {
    "break_and_retest": "break_and_retest",
    "one_candle_rule": "one_candle_rule",
    "br_ocr_confluence": "break_and_retest",   # both, filed under B&R for the
                                               # family split; counted in OCR too
    "reentry_84_rule": "rule_84",
}


def engine_families(rec):
    fams = set()
    for e in rec["entries"]:
        st = e["setup"]
        if st == "br_ocr_confluence":
            fams |= {"break_and_retest", "one_candle_rule"}
        elif st in _ENGINE_SETUP_TO_FAMILY:
            fams.add(_ENGINE_SETUP_TO_FAMILY[st])
        else:
            fams.add("other:" + st)
    return fams


def score_arm(pool, labels, rep):
    """Everything the report needs for ONE arm."""
    scored = {k: e for k, e in pool.items() if k in rep}
    S = [k for k, e in scored.items() if e.grade == "S"]
    NO = [k for k, e in scored.items() if e.grade == "none"]
    A = [k for k, e in scored.items() if e.grade == "A"]
    C = [k for k, e in scored.items() if e.grade == "C"]
    hit = lambda k: rep[k]["hit"]                                # noqa: E731

    s_hits = [k for k in S if hit(k)]
    no_hits = [k for k in NO if hit(k)]

    res = {
        "n_days_replayed": len(scored),
        "recall_S": rate(len(s_hits), len(S)),
        "false_fire_none": rate(len(no_hits), len(NO)),
        "fire_A": rate(sum(1 for k in A if hit(k)), len(A)),
        "fire_C": rate(sum(1 for k in C if hit(k)), len(C)),
        "precision_pct": (round(len(s_hits) / (len(s_hits) + len(no_hits)) * 100, 1)
                          if (s_hits or no_hits) else None),
        "separation_S_minus_none": separation(len(s_hits), len(S),
                                              len(no_hits), len(NO)),
        "detected_any_signal_S": rate(sum(1 for k in S if rep[k]["n_signals"]), len(S)),
        "detected_any_signal_none": rate(sum(1 for k in NO if rep[k]["n_signals"]),
                                         len(NO)),
        "points_below_gate": (round(GATE * 100 - len(s_hits) / len(S) * 100, 1)
                              if S else None),
        "p_one_sided_recall_below_90": (binom_cdf(len(s_hits), len(S), GATE)
                                        if S else None),
    }

    # ---- by HIS setup label -------------------------------------------------
    by_setup = {}
    for fam in _SETUP_KEYS:
        s_f = [k for k in S if fam in labels.get(k, {}).get("setups", [])]
        n_f = [k for k in NO if fam in labels.get(k, {}).get("setups", [])]
        ks, kn = sum(1 for k in s_f if hit(k)), sum(1 for k in n_f if hit(k))
        by_setup[fam] = {
            "recall_S": rate(ks, len(s_f)),
            "false_fire_none": rate(kn, len(n_f)),
            "separation_S_minus_none": separation(ks, len(s_f), kn, len(n_f)),
            # ...and when it does fire on one of his S days of this family, does
            # it fire THAT family, or a different one?
            "engine_fired_the_same_family_on_S": rate(
                sum(1 for k in s_f if hit(k) and fam in engine_families(rep[k])),
                len(s_f)),
        }
    s_un = [k for k in S if not labels.get(k, {}).get("setups")]
    n_un = [k for k in NO if not labels.get(k, {}).get("setups")]
    ks, kn = sum(1 for k in s_un if hit(k)), sum(1 for k in n_un if hit(k))
    by_setup["unlabelled"] = {
        "recall_S": rate(ks, len(s_un)),
        "false_fire_none": rate(kn, len(n_un)),
        "separation_S_minus_none": separation(ks, len(s_un), kn, len(n_un)),
    }
    res["by_his_setup"] = by_setup

    # ---- by setup the ENGINE fired (attribution of the hits) ----------------
    eng_fam_S = Counter()
    eng_fam_NO = Counter()
    for k in s_hits:
        for f in engine_families(rep[k]):
            eng_fam_S[f] += 1
    for k in no_hits:
        for f in engine_families(rep[k]):
            eng_fam_NO[f] += 1
    res["by_engine_setup"] = {
        "on_S_hits": {f: rate(c, len(S)) for f, c in sorted(eng_fam_S.items())},
        "on_refusal_hits": {f: rate(c, len(NO)) for f, c in sorted(eng_fam_NO.items())},
    }

    # ---- by entry-minute bucket, engine side (denominator = all S / all none)
    eng_buckets = {}
    for name, lo, hi in BUCKETS:
        in_b = lambda k: any(e["min"] is not None and lo <= e["min"] < hi   # noqa: E731
                             for e in rep[k]["entries"])
        ks, kn = sum(1 for k in S if in_b(k)), sum(1 for k in NO if in_b(k))
        eng_buckets[name] = {
            "recall_S": rate(ks, len(S)),
            "false_fire_none": rate(kn, len(NO)),
            "separation_S_minus_none": separation(ks, len(S), kn, len(NO)),
        }
    res["by_engine_fire_bucket"] = eng_buckets

    # ---- by entry-minute bucket, HIS stated minute --------------------------
    his_buckets = {}
    for name, _lo, _hi in BUCKETS:
        s_b = [k for k in S
               if any(bucket_of(m) == name for m in labels.get(k, {}).get("minutes", []))]
        n_b = [k for k in NO
               if any(bucket_of(m) == name for m in labels.get(k, {}).get("minutes", []))]
        ks, kn = sum(1 for k in s_b if hit(k)), sum(1 for k in n_b if hit(k))
        his_buckets[name] = {
            "recall_S": rate(ks, len(s_b)),
            "false_fire_none": rate(kn, len(n_b)),
            "separation_S_minus_none": separation(ks, len(s_b), kn, len(n_b)),
        }
    s_nom = [k for k in S if not labels.get(k, {}).get("minutes")]
    his_buckets["no_stated_minute"] = {
        "recall_S": rate(sum(1 for k in s_nom if hit(k)), len(s_nom)),
        "false_fire_none": rate(0, 0),
        "separation_S_minus_none": separation(0, 0, 0, 0),
    }
    res["by_his_stated_bucket"] = his_buckets

    # ---- index vs equity (universe.py is the only symbol list) --------------
    from universe import pool_for
    by_pool = {}
    for p in ("index", "equity", "other"):
        s_p = [k for k in S if pool_for(k.split("_", 1)[0]) == p]
        n_p = [k for k in NO if pool_for(k.split("_", 1)[0]) == p]
        ks, kn = sum(1 for k in s_p if hit(k)), sum(1 for k in n_p if hit(k))
        by_pool[p] = {"recall_S": rate(ks, len(s_p)),
                      "false_fire_none": rate(kn, len(n_p)),
                      "separation_S_minus_none": separation(ks, len(s_p),
                                                            kn, len(n_p))}
    res["by_pool"] = by_pool

    # ---- legacy ladder, side by side, never mixed ---------------------------
    legacy = Counter()
    for k in s_hits:
        for e in rep[k]["entries"]:
            legacy[e["legacy_grade"]] += 1
    res["legacy_grade_mix_on_S_hits"] = dict(sorted(legacy.items()))

    res["_S_keys"] = sorted(S)
    res["_NO_keys"] = sorted(NO)
    res["missed_S"] = sorted(k for k in S if not hit(k))
    return res


def pair_arms(pool, rep_a, rep_b, grade):
    keys = [k for k, e in pool.items()
            if e.grade == grade and k in rep_a and k in rep_b]
    both = only_a = only_b = neither = 0
    for k in keys:
        ha, hb = rep_a[k]["hit"], rep_b[k]["hit"]
        if ha and hb:
            both += 1
        elif ha:
            only_a += 1
        elif hb:
            only_b += 1
        else:
            neither += 1
    n = len(keys)
    psi = (only_a + only_b) / n if n else 0.0
    return {
        "n": n, "both": both, "only_base": only_a, "only_arm": only_b,
        "neither": neither,
        "base_pct": round((both + only_a) / n * 100, 1) if n else None,
        "arm_pct": round((both + only_b) / n * 100, 1) if n else None,
        "delta_pts": round(((only_b - only_a) / n) * 100, 1) if n else None,
        "discordance_psi": round(psi, 4),
        "mcnemar_exact_p": round(mcnemar_exact(only_a, only_b), 5),
        "power_to_see_10pts": (None if paired_power(n, psi, 0.10) is None
                               else round(paired_power(n, psi, 0.10), 3)),
    }


# ------------------------------------------------------------------- the worker

def run_worker(arm, out_path):
    assert_real_router()
    import marks_pool as mp
    pool = mp.canonical_pool()
    days = sorted((k, e.symbol, e.date) for k, e in pool.items() if e.has_bars)
    rep, errs, secs = replay_all(days, arm)
    import signal_runner as sr
    import omen_bot as ob
    flags = {k: getattr(sr, k, None) for k in
             ("X_LIFT", "MIN_STOP_PCT", "PIVOT_LEVELS", "AUSTIN_TIER_ENABLED",
              "S_GATE", "RULE_710_ENABLED", "NO_REPEAT_ENTRIES",
              "LEVEL_RETIRE_TOUCHES", "HTF_BIAS_GATE")}
    flags["HTF_BIAS_VETO"] = ob.HTF_BIAS_VETO
    json.dump({"arm": arm, "flags": flags, "elapsed_sec": secs,
               "errors": errs[:40], "n_errors": len(errs), "days": rep},
              open(out_path, "w", encoding="utf-8"))
    print("wrote " + out_path)


# ------------------------------------------------------------------- the driver

SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")


def sweep34_keys():
    """The 34 S days of the 100-card blind sweep every earlier recall number was
    scored on. Read-only, through grade_read so the field name cannot hide the
    answer again (research/g72_onespelling.md)."""
    import grade_read
    s, no = set(), set()
    if not os.path.exists(SWEEP):
        return s, no
    with open(SWEEP, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if grade_read.read_grade(r) is None:
                continue
            (s if grade_read.is_s(r) else no).add("%s_%s" % (r["symbol"], r["date"]))
    return s, no


def cross_check_34(rep):
    """Reproduce the standing 100-card number off THIS run. If it does not come
    back 22/34 the pipeline has drifted from research/g72_recall278_t0_rerun.json
    and nothing else on the page should be believed."""
    s_keys, no_keys = sweep34_keys()
    k = sum(1 for x in s_keys if rep.get(x, {}).get("hit"))
    fp = sum(1 for x in no_keys if rep.get(x, {}).get("hit"))
    return {"n_S": len(s_keys), "fired_on_S": k,
            "recall": rate(k, len(s_keys)),
            "fired_on_refusals": fp, "n_refusals": len(no_keys),
            "expected_from_g72_recall278_t0_rerun": "22/34",
            "matches_g72": k == 22 and len(s_keys) == 34}


def old34(name):
    """The answer this project recorded on 34 cards, for the survives/flips call."""
    p = os.path.join(HERE, name + ".json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding="utf-8")).get("sweep", {})
    return {"n_S": d.get("n_S"), "fired_on_S": d.get("fired_on_S"),
            "recall_pct": d.get("recall_pct"), "precision_pct": d.get("precision_pct"),
            "source": "research/%s.json" % name}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", help="internal: run one arm in this process")
    ap.add_argument("--worker-out")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--workdir", default=os.environ.get(
        "G83_WORKDIR", os.path.join(HERE, "_g83_arms")))
    ap.add_argument("--reuse", action="store_true",
                    help="score the arm replays already on disk in --workdir "
                         "instead of replaying (scoring-only re-runs are free)")
    a = ap.parse_args()

    if a.arm:
        return run_worker(a.arm, a.worker_out)

    assert_real_router()
    os.makedirs(a.workdir, exist_ok=True)
    arms = [x for x in a.arms.split(",") if x]

    procs = {}
    for arm in ([] if a.reuse else arms):
        env = dict(os.environ)
        env.update(ARMS[arm][0])
        env["PYTHONPATH"] = ROOT + os.pathsep + HERE
        out = os.path.join(a.workdir, "arm_%s.json" % arm)
        cmd = [sys.executable, os.path.abspath(__file__), "--arm", arm,
               "--worker-out", out]
        print("launching %-12s %s" % (arm, ARMS[arm][0] or "(shipped flags)"),
              flush=True)
        procs[arm] = (subprocess.Popen(cmd, cwd=ROOT, env=env), out)

    if a.reuse:
        procs = {arm: (None, os.path.join(a.workdir, "arm_%s.json" % arm))
                 for arm in arms}

    reps, meta = {}, {}
    for arm, (p, out) in procs.items():
        rc = p.wait() if p is not None else 0
        if rc != 0 or not os.path.exists(out):
            print("ARM FAILED: %s (rc=%s)" % (arm, rc))
            continue
        d = json.load(open(out, encoding="utf-8"))
        reps[arm] = d["days"]
        meta[arm] = {"flags": d["flags"], "elapsed_sec": d["elapsed_sec"],
                     "n_errors": d["n_errors"], "errors": d["errors"]}
        print("loaded %-12s %d days, %.0fs" % (arm, len(d["days"]), d["elapsed_sec"]))

    import marks_pool as mp
    pool = mp.canonical_pool()
    labels = his_labels()

    res = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "money_bar_per_day_usd": round(SIX_FIG_PER_DAY, 2),
        "pool": {
            "total_judged_symbol_days": len(pool),
            "with_bars": sum(1 for e in pool.values() if e.has_bars),
            "grade_mix_with_bars": dict(Counter(
                e.grade for e in pool.values() if e.has_bars)),
            "source": "research/marks_pool.py (nine spellings, 24 corpora)",
        },
        "his_labels_coverage": {
            "days_with_a_setup_label": sum(1 for v in labels.values() if v["setups"]),
            "days_with_a_stated_minute": sum(1 for v in labels.values() if v["minutes"]),
        },
        "router": "signal_runner.SignalRunner._route via "
                  "t4_engine_recall.CaptureRunner (delegation asserted)",
        "arm_meta": meta,
        "arms": {},
        "paired_vs_base": {},
    }
    for arm, rep in reps.items():
        res["arms"][arm] = score_arm(pool, labels, rep)
        res["arms"][arm]["old_34_card_answer"] = old34(ARMS[arm][1])
        res["arms"][arm]["same_34_cards_this_run"] = cross_check_34(rep)

    if "base" in reps:
        for arm, rep in reps.items():
            if arm == "base":
                continue
            res["paired_vs_base"][arm] = {
                "S_days": pair_arms(pool, reps["base"], rep, "S"),
                "refusal_days": pair_arms(pool, reps["base"], rep, "none"),
                "old_34_card": {
                    "base": old34(ARMS["base"][1]),
                    "arm": old34(ARMS[arm][1]),
                },
            }

    # what the bigger sample bought
    if "base" in res["arms"]:
        b = res["arms"]["base"]["recall_S"]
        res["what_the_bigger_sample_bought"] = {
            "n_S_now": b["n"], "n_S_before": 34,
            "half_width_now_pts": b["half_width_pts"],
            "half_width_before_pts": round(
                (wilson(round(b["pct"] / 100 * 34), 34)[1]
                 - wilson(round(b["pct"] / 100 * 34), 34)[0]) * 50, 1),
            "paired_power_10pts_at_psi_0.147": {
                "n34": round(paired_power(34, 0.147, 0.10), 3),
                "n%d" % b["n"]: round(paired_power(b["n"], 0.147, 0.10), 3),
            },
        }

    slim = json.loads(json.dumps(res))
    for arm in slim["arms"]:
        slim["arms"][arm].pop("_S_keys", None)
        slim["arms"][arm].pop("_NO_keys", None)
    json.dump(slim, open(OUT_JSON, "w", encoding="utf-8"), indent=2, sort_keys=True)
    print("wrote " + OUT_JSON)

    if "base" in res["arms"]:
        b = res["arms"]["base"]
        print("\nBASE, full pool")
        print("  recall on his S days     %s%% (%d/%d) 95%% CI %s"
              % (b["recall_S"]["pct"], b["recall_S"]["k"], b["recall_S"]["n"],
                 b["recall_S"]["wilson95_pct"]))
        print("  false fire on refusals   %s%% (%d/%d) 95%% CI %s"
              % (b["false_fire_none"]["pct"], b["false_fire_none"]["k"],
                 b["false_fire_none"]["n"], b["false_fire_none"]["wilson95_pct"]))
        print("  precision                %s%%" % b["precision_pct"])
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
