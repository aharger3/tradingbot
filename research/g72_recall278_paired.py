"""G7.2 / recall278 -- held-out S recall measured on ALL 278 bar-backed S days,
with the REAL engine router, paired.

Two things this fixes, both measurement-only (no engine file is touched):

1. Sample size. Every recall comparison in this repo was scored on one 100-card
   file (research/marks/probe_s_sweep_2026-08-28.jsonl), which carries 34 S days.
   research/g71_samplesize_corpus.json shows 278 of Austin's S days already have
   archived bars, and the whole graded corpus replays in minutes. 34 cards buys
   +/-15 points; 278 buys about +/-5, and paired power to see a real 10-point
   improvement goes from ~0.15 to ~0.87.

2. The router. research/t4_engine_recall.CaptureRunner._route used to be a
   hand-rolled copy of signal_runner.SignalRunner._route that never called
   super(), so gates the shipped engine grew after it was written were inert in
   the one rig that scores recall. It now delegates (fixed in the same change as
   this script). This script measures BOTH arms -- old copy vs shipped engine --
   on the same days, paired, so the cost of the lie is a measured number and not
   an assertion.

Scoring is exactly research/t0_heldout_recall.py::score_sweep's day-level rule:
a day counts as a HIT if the engine takes ANY entry on it. Grades come from
research/g71_samplesize_corpus.json (built by g71_samplesize_corpus.py from all
19 mark corpora); Austin's ladder (S/A/C/none) only -- the legacy A+/A/B/C/X
ladder is reported beside it, never mixed into it.

Every mark file is opened read-only. The hand-rolled router is restored by
monkeypatch IN THIS PROCESS ONLY.

Usage:
  python research/g72_recall278_paired.py            # all graded days, both arms
  python research/g72_recall278_paired.py --pool S   # S days only (faster)
  python research/g72_recall278_paired.py --arms engine
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t4_engine_recall as t4            # noqa: E402
import signal_runner as sr               # noqa: E402
from signal_runner import TradeGrade      # noqa: E402

CORPUS = os.path.join(HERE, "g71_samplesize_corpus.json")
SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
GATE = 0.90                              # DIRECTION.md's recall gate
Z = 1.959963984540054                    # two-sided 95%


# ---------------------------------------------------------------- the two arms

_ENGINE_ROUTE = t4.CaptureRunner._route   # the delegating router (shipped today)


def _hand_rolled_route(self, signals, sig):
    """t4_engine_recall.CaptureRunner._route as it stood before G7.2 -- a copy of
    the router that never calls super(), so every gate the base grew after it was
    written (S_GATE, RULE_710, austin tier, LEVEL_RETIRE, repeat-idea/entry,
    MIN_STOP_PCT) is invisible to it. Kept here ONLY so the change can be priced.
    """
    self._grade_for_levels(sig)
    self._calibration_grade(sig)
    self._apply_x_lift(sig)
    if sig["grade"] != TradeGrade.D.value:
        if (sig["grade"] != "C"
                or self._min_viable_stop(sig["entry"], sig["stop"], sig["direction"])):
            sig["status"] = "fired"
            self._dir_fired[sig["direction"]] = self._dir_fired.get(sig["direction"], 0) + 1
            signals.append(sig)
        else:
            sig["status"] = "skipped_tight"
    else:
        sig["status"] = "skipped_d"
    self.captured.append(sig)


ARMS = {"engine": _ENGINE_ROUTE, "hand_rolled": _hand_rolled_route}


# ------------------------------------------------------------------ statistics

def wilson(k, n):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return (c - h, c + h)


def binom_cdf(k, n, p):
    """P(X <= k). Exact, no scipy dependency."""
    tot = 0.0
    for i in range(0, k + 1):
        tot += math.comb(n, i) * p ** i * (1 - p) ** (n - i)
    return min(1.0, tot)


def binom_test_less(k, n, p):
    """One-sided exact p for 'recall is below p'. Doubling it is the two-sided
    read used elsewhere in this repo (g71_ssverify_power.py)."""
    return binom_cdf(k, n, p)


def mcnemar_exact(b, c):
    """Two-sided exact McNemar on the discordant pairs: b = A-only hits,
    c = B-only hits. Returns p."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def paired_power(n, psi, d, alpha_z=Z):
    """Power of a paired (McNemar) test to see a true d-point recall move when a
    fraction psi of days disagree between the two arms."""
    if psi <= abs(d):
        return None
    x = (math.sqrt(n) * d - alpha_z * math.sqrt(psi)) / math.sqrt(psi - d * d)
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def unpaired_power(n, p1, p2, alpha_z=Z):
    pb = (p1 + p2) / 2
    x = (abs(p1 - p2) - alpha_z * math.sqrt(2 * pb * (1 - pb) / n)) / \
        math.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n)
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ----------------------------------------------------------------------- corpus

def top_austin(r):
    for g in ("S", "A", "C", "none"):
        if r["austin"].get(g):
            return g
    return None


def load_days(pool):
    audit = json.load(open(CORPUS, encoding="utf-8"))
    rows = [r for r in audit["rows"] if r["bars"] and r["austin"]]
    for r in rows:
        r["grade"] = top_austin(r)
    if pool == "S":
        rows = [r for r in rows if r["grade"] == "S"]
    return rows


def sweep_keys():
    keys = set()
    with open(SWEEP, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                j = json.loads(line)
                if j.get("answers", {}).get("s"):
                    keys.add("%s_%s" % (j["symbol"], j["date"]))
    return keys


def replay(rows, label):
    """Day-level result for one arm: did the engine take ANY entry that day."""
    out, errs = {}, []
    t0 = time.time()
    for i, r in enumerate(rows):
        try:
            ent, sigs, _raw = t4.run_day(r["symbol"], r["day"])
        except Exception as e:                                   # noqa: BLE001
            errs.append({"key": r["key"], "error": type(e).__name__ + ": " + str(e)[:120]})
            continue
        if ent is None:
            errs.append({"key": r["key"], "error": "no archived bars"})
            continue
        out[r["key"]] = {
            "hit": bool(ent),
            "entries": len(ent),
            "signals": len(sigs),
            "legacy_grades": sorted({e["grade"] for e in ent}),
        }
        if i and i % 200 == 0:
            print("  %s %d/%d  %.0fs" % (label, i, len(rows), time.time() - t0), flush=True)
    print("  %s done %d days %.0fs" % (label, len(out), time.time() - t0), flush=True)
    return out, errs, round(time.time() - t0, 1)


def score(rows, rep, keys=None):
    sel = [r for r in rows if r["key"] in rep and (keys is None or r["key"] in keys)]
    S = [r for r in sel if r["grade"] == "S"]
    NO = [r for r in sel if r["grade"] == "none"]
    hit = lambda r: rep[r["key"]]["hit"]                          # noqa: E731
    tp = [r for r in S if hit(r)]
    fp = [r for r in NO if hit(r)]
    lo, hi = wilson(len(tp), len(S))
    by_grade = {}
    for g in ("S", "A", "C", "none"):
        gr = [r for r in sel if r["grade"] == g]
        k = sum(1 for r in gr if hit(r))
        l, h = wilson(k, len(gr))
        by_grade[g] = {"n": len(gr), "fired": k,
                       "pct": round(k / len(gr) * 100, 1) if gr else 0.0,
                       "wilson95_pct": [round(l * 100, 1), round(h * 100, 1)]}
    legacy = Counter()
    for r in tp:
        for g in rep[r["key"]]["legacy_grades"]:
            legacy[g] += 1
    return {
        "n_days_scored": len(sel),
        "n_S": len(S), "S_fired": len(tp),
        "recall_pct": round(len(tp) / len(S) * 100, 1) if S else 0.0,
        "recall_wilson95_pct": [round(lo * 100, 1), round(hi * 100, 1)],
        "points_below_90": round(90.0 - len(tp) / len(S) * 100, 1) if S else None,
        "p_one_sided_vs_90": binom_test_less(len(tp), len(S), GATE) if S else None,
        "n_none": len(NO), "none_fired": len(fp),
        "precision_vs_none_pct": (round(len(tp) / (len(tp) + len(fp)) * 100, 1)
                                  if (tp or fp) else 0.0),
        "by_austin_grade": by_grade,
        "legacy_grade_mix_on_S_hits": dict(sorted(legacy.items())),
        "missed_S": sorted(r["key"] for r in S if not hit(r)),
    }


def pair(rows, a, b):
    """Paired comparison of two arms over the same S days."""
    S = [r for r in rows if r["grade"] == "S" and r["key"] in a and r["key"] in b]
    both = only_a = only_b = neither = 0
    flips = []
    for r in S:
        ha, hb = a[r["key"]]["hit"], b[r["key"]]["hit"]
        if ha and hb:
            both += 1
        elif ha:
            only_a += 1
            flips.append({"key": r["key"], "arm_a_fired": True, "arm_b_fired": False})
        elif hb:
            only_b += 1
            flips.append({"key": r["key"], "arm_a_fired": False, "arm_b_fired": True})
        else:
            neither += 1
    n = len(S)
    psi = (only_a + only_b) / n if n else 0.0
    return {
        "n_S_paired": n,
        "both": both, "only_a": only_a, "only_b": only_b, "neither": neither,
        "delta_pct_b_minus_a": round(((both + only_b) - (both + only_a)) / n * 100, 1) if n else 0.0,
        "discordance_psi": round(psi, 4),
        "mcnemar_exact_p": round(mcnemar_exact(only_a, only_b), 4),
        "flips": flips,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="all", choices=["all", "S"])
    ap.add_argument("--arms", default="engine,hand_rolled")
    ap.add_argument("--out", default=os.path.join(HERE, "g72_recall278_paired.json"))
    a = ap.parse_args()

    rows = load_days(a.pool)
    keys34 = sweep_keys()
    print("corpus: %d bar-backed graded days (%s)"
          % (len(rows), Counter(r["grade"] for r in rows)), flush=True)

    flags = {k: getattr(sr, k) for k in
             ("X_LIFT", "MIN_STOP_PCT", "PIVOT_LEVELS", "AUSTIN_TIER_ENABLED",
              "NO_REPEAT_ENTRIES", "ENFORCE_NO_REPEAT", "LEVEL_RETIRE_TOUCHES",
              "S_GATE", "RULE_710_ENABLED", "SESSION_EXTREME_FRAC", "HODLOD_PAIR")}
    flags["DEDUPE_BARS"] = t4.DEDUPE_BARS
    flags["ENTRY_CUTOFF"] = t4.ENTRY_CUTOFF

    res = {"flags": flags, "pool": a.pool, "n_days_replayed_target": len(rows),
           "grade_mix": dict(Counter(r["grade"] for r in rows)), "arms": {}}
    reps = {}
    for name in a.arms.split(","):
        t4.CaptureRunner._route = ARMS[name]
        rep, errs, secs = replay(rows, name)
        t4.CaptureRunner._route = _ENGINE_ROUTE
        reps[name] = rep
        res["arms"][name] = {
            "elapsed_sec": secs, "replay_errors": len(errs), "errors": errs[:20],
            "full_278": score(rows, rep),
            "sweep_34_cards": score(rows, rep, keys=keys34),
        }

    if len(reps) == 2:
        a_name, b_name = a.arms.split(",")
        res["paired"] = {"arm_a": a_name, "arm_b": b_name,
                         **pair(rows, reps[a_name], reps[b_name])}

    # what the bigger sample buys, at the discordance this repo actually measures
    n278 = res["arms"][a.arms.split(",")[0]]["full_278"]["n_S"]
    obs = res["arms"][a.arms.split(",")[0]]["full_278"]["recall_pct"] / 100
    res["power"] = {
        "note": "psi 0.147 = median discordance over 66 like-for-like G7.1 arm "
                "pairs (research/g71_ssverify_power.json); 0.088 and 0.30 bracket it",
        "n_S_now": n278, "n_S_before": 34,
        "paired_power_10pt": {
            "psi_%.3f_n%d" % (psi, n): (None if paired_power(n, psi, 0.10) is None
                                        else round(paired_power(n, psi, 0.10), 3))
            for psi in (0.088, 0.147, 0.30) for n in (34, n278)},
        "unpaired_power_10pt": {
            "n34": round(unpaired_power(34, obs, min(0.999, obs + 0.10)), 3),
            "n%d" % n278: round(unpaired_power(n278, obs, min(0.999, obs + 0.10)), 3)},
        "half_width_pct": {
            "n34": round((wilson(round(obs * 34), 34)[1] - wilson(round(obs * 34), 34)[0]) * 50, 1),
            "n%d" % n278: round((wilson(round(obs * n278), n278)[1]
                                 - wilson(round(obs * n278), n278)[0]) * 50, 1)},
    }

    slim = json.loads(json.dumps(res))
    for k in slim["arms"]:
        slim["arms"][k]["full_278"].pop("missed_S", None)
        slim["arms"][k]["full_278"].pop("by_austin_grade", None)
        slim["arms"][k]["sweep_34_cards"].pop("missed_S", None)
        slim["arms"][k]["sweep_34_cards"].pop("by_austin_grade", None)
        slim["arms"][k].pop("errors", None)
    slim.get("paired", {}).pop("flips", None)
    print(json.dumps(slim, indent=2))

    json.dump(res, open(a.out, "w", encoding="utf-8"), indent=2)
    print("wrote " + a.out)


if __name__ == "__main__":
    main()
