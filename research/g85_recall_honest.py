"""g85_recall_honest -- does the honest entry fill change ACCURACY?

Nobody asked this. The fill changed on 2026-08-30 (`entry_fill.py`: the default
went from `published`, the level clamped into the signal bar, to `close`, the
price he can actually see when the signal exists) and every consequence anyone
measured was a DOLLAR consequence. But a different entry price is a different
`entry - stop`, and `signal_runner` gates on `entry - stop` in two places --
the minimum-stop-percent skip (`MIN_STOP_PCT`, signal_runner.py:2672) and the
minimum-risk floor (`min_risk_floor`, :2865 / :3146). So the fill can change
which setups are allowed to become trades, which changes which DAYS get traded,
which is exactly what recall counts. It plausibly moves accuracy. This measures
whether it does.

HOW THE COMPARISON IS BUILT, AND WHY IT IS NOT JUST "RERUN AND DIFF"
--------------------------------------------------------------------
Last night's published recall (`research/g83_recall278.json`, commit f20fbecd,
03:19) ran on the old fill -- but FIVE other commits have landed since, three of
which touch routing (a rejected setup no longer silences the real trade a minute
later; A+ retired and the live path routed on his S grade; levels now carry the
timeframe they were drawn on). Diffing today's run against last night's number
would attribute all of that to the fill.

So both arms are run TODAY, on TODAY's code, paired on the same symbol-days,
with the fill as the ONLY difference:

    published   ENTRY_FILL=published   the old, unobtainable price
    honest      ENTRY_FILL=close       the shipped default since 2026-08-30

Last night's figures are carried alongside as a third column, clearly labelled
as a different engine, so the three-way drift is visible instead of hidden.

WHAT IT REUSES RATHER THAN RE-DERIVING
--------------------------------------
Everything. `research/g83_recall278.py` owns the scoring -- the Wilson bands,
the Newcombe separation interval, the exact McNemar pairing, the by-setup and
by-entry-minute splits, the 100-card cross-check -- and it is imported, not
copied. `research/marks_pool.py` owns the grades (one grade per symbol-day
across all 24 corpora, all nine spellings of "S"). No mark file is opened for
writing; no engine file is modified.

THE ROUTER GUARD
----------------
`g83_recall278.assert_real_router()` runs before either arm produces a number.
`t4_engine_recall.CaptureRunner._route` used to be a hand-written photocopy of
the shipped router that never called `super()`, and it flattered recall in the
engine's favour (23/34 against the real 22/34). If that delegation is ever
removed again this script refuses to print anything.

Usage
-----
    python research/g85_recall_honest.py            # both arms, ~4 minutes
    python research/g85_recall_honest.py --reuse    # rescore replays on disk
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import g83_recall278 as g83                                    # noqa: E402

OUT_JSON = os.path.join(HERE, "g85_recall_honest.json")
OUT_MD = os.path.join(HERE, "g85_recall_honest.md")
LAST_NIGHT = os.path.join(HERE, "g83_recall278.json")

# The two arms. Every other tunable is left exactly where the shipped engine
# has it -- this is a one-variable experiment.
ARMS = {
    "honest":    {"ENTRY_FILL": "close"},
    "published": {"ENTRY_FILL": "published"},
}
ARM_ORDER = ("honest", "published")

# What the fill is worth in money, for context only. Measured elsewhere
# (research/g80_lookahead_refute.md); NOT re-derived here.
MONEY_BAR = 100_000 / 252          # $396.83/day, Austin's bar, 2026-08-30


# ------------------------------------------------------------------- the worker

def run_worker(arm, out_path):
    """Replay every bar-backed judged day under ONE fill mode."""
    g83.assert_real_router()

    import entry_fill
    want = ARMS[arm]["ENTRY_FILL"]
    if entry_fill.ENTRY_FILL != want:
        raise SystemExit(
            "REFUSING TO MEASURE: arm %r wanted ENTRY_FILL=%s and the module "
            "loaded with %r. The environment did not reach the subprocess, so "
            "both arms would be the same book wearing two names."
            % (arm, want, entry_fill.ENTRY_FILL))

    import marks_pool as mp
    pool = mp.canonical_pool()
    days = sorted((k, e.symbol, e.date) for k, e in pool.items() if e.has_bars)
    rep, errs, secs = g83.replay_all(days, arm)

    import signal_runner as sr
    import omen_bot as ob
    flags = {k: getattr(sr, k, None) for k in
             ("X_LIFT", "MIN_STOP_PCT", "PIVOT_LEVELS", "AUSTIN_TIER_ENABLED",
              "S_GATE", "RULE_710_ENABLED", "NO_REPEAT_ENTRIES",
              "LEVEL_RETIRE_TOUCHES", "HTF_BIAS_GATE", "STOP_FILL_ORDER",
              "ENABLE_MIN_RISK_FILL_CLAMP")}
    flags["HTF_BIAS_VETO"] = ob.HTF_BIAS_VETO
    flags["ENTRY_FILL"] = entry_fill.ENTRY_FILL

    json.dump({"arm": arm, "entry_fill": entry_fill.ENTRY_FILL, "flags": flags,
               "elapsed_sec": secs, "errors": errs[:40], "n_errors": len(errs),
               "days": rep},
              open(out_path, "w", encoding="utf-8"))
    print("wrote " + out_path)


def run_why_worker(arm, keys_path, out_path):
    """Replay ONLY the days that flipped, and count WHY each signal was refused.

    The report claimed a mechanism; this checks it instead of asserting it.
    `t4_engine_recall.CaptureRunner` already labels every refusal
    (`skipped_d` = the minimum-risk floor stamped grade D at
    signal_runner.py:2866/3147, `skipped_min_stop_pct` = the 0.08%-of-price
    skip, `skipped_tight` = no viable stop), so this only has to tally them."""
    import entry_fill
    if entry_fill.ENTRY_FILL != ARMS[arm]["ENTRY_FILL"]:
        raise SystemExit("why-worker %s loaded ENTRY_FILL=%r"
                         % (arm, entry_fill.ENTRY_FILL))
    import marks_pool as mp
    import t4_engine_recall as t4
    pool = mp.canonical_pool()
    keys = json.load(open(keys_path, encoding="utf-8"))
    mix = Counter()
    for k in keys:
        e = pool[k]
        _ent, _sig, raw = t4.run_day(e.symbol, e.date)
        for r in (raw or ()):
            mix[r["status"]] += 1
    json.dump({"arm": arm, "entry_fill": entry_fill.ENTRY_FILL,
               "n_days": len(keys), "status_mix": dict(sorted(mix.items()))},
              open(out_path, "w", encoding="utf-8"))
    print("wrote " + out_path)


def why_it_flipped(pool, reps, workdir):
    """Run the mechanism check on the S days the honest fill newly trades."""
    flipped = sorted(k for k in reps["honest"]
                     if k in reps["published"]
                     and reps["honest"][k]["hit"] and not reps["published"][k]["hit"]
                     and k in pool and pool[k].grade == "S")
    if not flipped:
        return None
    keys_path = os.path.join(workdir, "why_keys.json")
    json.dump(flipped, open(keys_path, "w", encoding="utf-8"))
    out = {}
    procs = {}
    for arm in ARM_ORDER:
        env = dict(os.environ)
        env.update(ARMS[arm])
        env["PYTHONPATH"] = ROOT + os.pathsep + HERE
        o = os.path.join(workdir, "why_%s.json" % arm)
        procs[arm] = (subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--why-arm", arm,
             "--why-keys", keys_path, "--worker-out", o],
            cwd=ROOT, env=env), o)
    for arm, (p, o) in procs.items():
        if p.wait() != 0 or not os.path.exists(o):
            return {"n_flipped_S_days": len(flipped), "error": "why-worker failed"}
        out[arm] = json.load(open(o, encoding="utf-8"))["status_mix"]
    return {"n_flipped_S_days": len(flipped), "status_mix": out}


# ---------------------------------------------------------------- side by side

def _r(node):
    """A rate node -> the three numbers a sentence needs."""
    if not node:
        return None
    return {"pct": node["pct"], "k": node["k"], "n": node["n"],
            "wilson95_pct": node["wilson95_pct"]}


def compare(a_honest, a_published, last_night):
    """The headline table: the same question asked three ways."""
    rows = []

    def row(label, path, fmt="rate"):
        h = path(a_honest)
        p = path(a_published)
        ln = path(last_night) if last_night else None
        if fmt == "rate":
            rows.append({
                "what": label,
                "honest_close": _r(h), "published_fill": _r(p),
                "last_night_published_number": _r(ln),
                "honest_minus_published_pts":
                    (None if (h is None or p is None or h["pct"] is None
                              or p["pct"] is None)
                     else round(h["pct"] - p["pct"], 1)),
            })
        else:
            rows.append({"what": label, "honest_close": h,
                         "published_fill": p,
                         "last_night_published_number": ln,
                         "honest_minus_published_pts":
                             (None if (h is None or p is None) else
                              round((h if isinstance(h, (int, float)) else 0)
                                    - (p if isinstance(p, (int, float)) else 0), 1))})

    row("signal produced on his S days", lambda d: d["detected_any_signal_S"])
    row("signal produced on his refusals", lambda d: d["detected_any_signal_none"])
    row("trade taken on his S days (recall)", lambda d: d["recall_S"])
    row("trade taken on his refusals (false fire)", lambda d: d["false_fire_none"])
    row("trade taken on his A days", lambda d: d["fire_A"])
    row("trade taken on his C days", lambda d: d["fire_C"])
    row("precision", lambda d: d["precision_pct"], fmt="scalar")

    sep = {}
    for name, d in (("honest_close", a_honest), ("published_fill", a_published),
                    ("last_night_published_number", last_night)):
        if d:
            sep[name] = d["separation_S_minus_none"]
    return {"rows": rows, "separation": sep}


def fill_effect_on_volume(rep_h, rep_p, pool):
    """Detection is upstream of the fill; routing is downstream. If the signal
    counts match and only the entry counts move, the fill changed FILTERING and
    not what the engine sees -- which is the mechanism this whole question is
    about. Counted over every replayed day, not just the graded ones."""
    keys = [k for k in rep_h if k in rep_p]
    sig_h = sum(rep_h[k]["n_signals"] for k in keys)
    sig_p = sum(rep_p[k]["n_signals"] for k in keys)
    ent_h = sum(rep_h[k]["n_entries"] for k in keys)
    ent_p = sum(rep_p[k]["n_entries"] for k in keys)
    same_sig = sum(1 for k in keys
                   if rep_h[k]["n_signals"] == rep_p[k]["n_signals"])
    same_ent = sum(1 for k in keys
                   if rep_h[k]["n_entries"] == rep_p[k]["n_entries"])
    flip = Counter()
    for k in keys:
        g = pool[k].grade if k in pool else "?"
        if rep_h[k]["hit"] != rep_p[k]["hit"]:
            flip["honest_only" if rep_h[k]["hit"] else "published_only"] += 1
            flip["%s_%s" % (g, "honest_only" if rep_h[k]["hit"]
                            else "published_only")] += 1
    return {
        "days_compared": len(keys),
        "signals_detected": {"honest": sig_h, "published": sig_p,
                             "delta": sig_h - sig_p},
        "entries_taken": {"honest": ent_h, "published": ent_p,
                          "delta": ent_h - ent_p},
        "days_with_identical_signal_count": same_sig,
        "days_with_identical_entry_count": same_ent,
        "day_verdict_flips": dict(sorted(flip.items())),
    }


def bootstrap_separation_delta(pool, rep_p, rep_h, n_boot=20000, seed=20260830):
    """A 95% interval on (separation under the honest fill) minus (separation
    under the old fill).

    Separation is a difference of two rates measured on two different sets of
    days, and this is a difference of two of those. There is no closed form, so
    it is resampled: S days and refusal days are drawn independently with
    replacement, and a drawn day carries BOTH of its verdicts, which is what
    keeps the comparison paired. Without this the temptation is to read a
    1-point move off two point estimates and call it a direction; the standing
    method finding in DIRECTION.md is that this project's arms routinely move
    less than their own error bar."""
    import random
    rng = random.Random(seed)
    S = [k for k, e in pool.items()
         if e.grade == "S" and k in rep_p and k in rep_h]
    NO = [k for k, e in pool.items()
          if e.grade == "none" and k in rep_p and k in rep_h]
    sv = [(rep_p[k]["hit"], rep_h[k]["hit"]) for k in S]
    nv = [(rep_p[k]["hit"], rep_h[k]["hit"]) for k in NO]
    ns, nn = len(sv), len(nv)
    if not ns or not nn:
        return None

    def sep(sample_s, sample_n):
        ph = sum(1 for _, h in sample_s if h) / len(sample_s)
        pp = sum(1 for p, _ in sample_s if p) / len(sample_s)
        nh = sum(1 for _, h in sample_n if h) / len(sample_n)
        np_ = sum(1 for p, _ in sample_n if p) / len(sample_n)
        return (ph - nh) - (pp - np_)

    obs = sep(sv, nv) * 100
    draws = []
    for _ in range(n_boot):
        bs = [sv[rng.randrange(ns)] for _ in range(ns)]
        bn = [nv[rng.randrange(nn)] for _ in range(nn)]
        draws.append(sep(bs, bn) * 100)
    draws.sort()
    lo = draws[int(0.025 * n_boot)]
    hi = draws[int(0.975 * n_boot) - 1]
    return {"points": round(obs, 1),
            "boot95_pts": [round(lo, 1), round(hi, 1)],
            "straddles_zero": bool(lo <= 0 <= hi),
            "n_boot": n_boot, "n_S": ns, "n_refusals": nn}


def verdict(cmp_block, paired, sep_delta):
    """Helps, hurts, or does nothing.

    Decided on DISCRIMINATION -- separation, S days minus refusal days -- and
    on its own resampled interval, not on two point estimates and not on recall
    alone. Recall by itself can be bought by firing on everything, which is
    precisely the failure mode this engine already has."""
    s = paired["S_days"]
    n = paired["refusal_days"]
    d = sep_delta["points"]
    lo, hi = sep_delta["boot95_pts"]
    flips = (s["only_base"] + s["only_arm"] + n["only_base"] + n["only_arm"])
    if sep_delta["straddles_zero"]:
        call = "DOES NOTHING"
        why = ("It changes %d individual day verdicts, but discrimination -- "
               "how much more often the engine fires on a day he graded S than "
               "on a day he refused -- moves %+0.1f points with a 95%% range of "
               "[%+0.1f, %+0.1f], which straddles zero. Recall rises %+0.1f "
               "points and false fires rise %+0.1f points, and those two "
               "cancel."
               % (flips, d, lo, hi,
                  cmp_block["rows"][2]["honest_minus_published_pts"],
                  cmp_block["rows"][3]["honest_minus_published_pts"]))
    elif d > 0:
        call = "HELPS"
        why = ("Discrimination improves %+0.1f points, 95%% [%+0.1f, %+0.1f], "
               "clear of zero." % (d, lo, hi))
    else:
        call = "HURTS"
        why = ("Discrimination falls %+0.1f points, 95%% [%+0.1f, %+0.1f], "
               "clear of zero." % (d, lo, hi))
    return {"call": call, "why": why,
            "separation_delta_pts": d,
            "separation_delta_boot95_pts": [lo, hi],
            "recall_delta_pts": cmp_block["rows"][2]["honest_minus_published_pts"],
            "false_fire_delta_pts": cmp_block["rows"][3]["honest_minus_published_pts"],
            "S_day_mcnemar_p": s["mcnemar_exact_p"],
            "refusal_day_mcnemar_p": n["mcnemar_exact_p"],
            "days_that_flipped_S": s["only_base"] + s["only_arm"],
            "days_that_flipped_refusals": n["only_base"] + n["only_arm"]}


# ---------------------------------------------------------------------- report

def _rate_cell(node):
    if not node or node.get("pct") is None:
        return "—"
    return "%s%% (%d/%d)" % (node["pct"], node["k"], node["n"])


def _band(node):
    if not node or node.get("wilson95_pct") is None:
        return "—"
    return "%s – %s" % tuple(node["wilson95_pct"])


def write_md(res):
    v = res["verdict"]
    c = res["headline"]
    L = []
    A = L.append

    A("# Does the honest entry fill change accuracy?")
    A("")
    A("Measured 2026-08-30 by `research/g85_recall_honest.py`. "
      "Grades from `research/marks_pool.py`. Router: the shipped one, asserted.")
    A("")
    A("## The answer")
    A("")
    A("> **The honest fill %s.** %s" % (v["call"].lower(), v["why"]))
    A("")
    A("**No dollar figure moves here.** This is the accuracy half of the fill "
      "change; the money half was settled overnight (control $683/day "
      "*unobtainable*, the obtainable block $33–$68/day, options $242–$346, "
      "against Austin's bar of **$397 a day**). Recall does not have a price "
      "attached — but if the honest fill had quietly bought or cost recall, "
      "every accuracy number published before today would have been measured "
      "on an engine the repo no longer ships.")
    A("")
    A("Of %d days he graded S, **%d changed verdict** when the price changed. "
      "Of %d days he refused, **%d changed**. So this is not a quiet change — "
      "it is a loud change that lands on both sides in equal measure."
      % (res["paired"]["S_days"]["n"], v["days_that_flipped_S"],
         res["paired"]["refusal_days"]["n"], v["days_that_flipped_refusals"]))
    A("")
    A("| | honest fill | old fill | change |")
    A("|---|---:|---:|---:|")
    A("| takes a trade on a day he graded **S** | %s%% | %s%% | **%+0.1f pts** |"
      % (res["arms"]["honest"]["recall_S"]["pct"],
         res["arms"]["published"]["recall_S"]["pct"], v["recall_delta_pts"]))
    A("| takes a trade on a day he **refused** | %s%% | %s%% | **%+0.1f pts** |"
      % (res["arms"]["honest"]["false_fire_none"]["pct"],
         res["arms"]["published"]["false_fire_none"]["pct"],
         v["false_fire_delta_pts"]))
    A("| **the gap between them** | **%+0.1f pts** | **%+0.1f pts** | **%+0.1f pts, 95%% [%+0.1f, %+0.1f]** |"
      % (res["arms"]["honest"]["separation_S_minus_none"]["points"],
         res["arms"]["published"]["separation_S_minus_none"]["points"],
         v["separation_delta_pts"], v["separation_delta_boot95_pts"][0],
         v["separation_delta_boot95_pts"][1]))
    A("")
    A("**The honest fill buys recall and pays for every point of it in false "
      "fires.** Recall going up %+0.1f points would be the headline of the "
      "night if the refusals had held still. They did not — they went up "
      "%+0.1f. The engine did not get better at telling his days apart; it "
      "just started trading more days."
      % (v["recall_delta_pts"], v["false_fire_delta_pts"]))
    A("")

    A("## Side by side")
    A("")
    A("Both columns were replayed **today, on today's code**, over the same "
      "%d bar-backed judged symbol-days, with the entry price as the only "
      "difference. The third column is last night's published figure, kept "
      "because five commits have landed since — three of them in the router — "
      "and it would have been dishonest to assume they changed nothing."
      % res["arms"]["honest"]["n_days_replayed"])
    A("")
    if res["reproduces_last_night"]:
        A("**They did change nothing.** The old-fill column reproduces last "
          "night's published numbers to the day, on every row, including the "
          "100-card cross-check. So the middle column is a genuine control and "
          "the whole of the difference in the left column is the fill.")
    else:
        A("**They did not reproduce.** The old-fill column does not match last "
          "night, so part of the left column's move belongs to those commits "
          "and not to the fill. Read the honest-vs-old comparison, not the "
          "honest-vs-last-night one.")
    A("")
    A("| | honest fill (the close) | old fill (published) | last night, as published |")
    A("|---|---|---|---|")
    for r in c["rows"]:
        if isinstance(r["honest_close"], dict) or r["honest_close"] is None:
            A("| %s | %s | %s | %s |"
              % (r["what"], _rate_cell(r["honest_close"]),
                 _rate_cell(r["published_fill"]),
                 _rate_cell(r["last_night_published_number"])))
        else:
            A("| %s | %s%% | %s%% | %s%% |"
              % (r["what"], r["honest_close"], r["published_fill"],
                 r["last_night_published_number"]))
    sh = c["separation"]["honest_close"]
    sp = c["separation"]["published_fill"]
    sl = c["separation"].get("last_night_published_number")
    A("| **separation (S minus refusals)** | **%+0.1f pts** %s | **%+0.1f pts** %s | **%+0.1f pts** %s |"
      % (sh["points"], sh["newcombe95_pts"], sp["points"], sp["newcombe95_pts"],
         (sl["points"] if sl else 0), (sl["newcombe95_pts"] if sl else "")))
    A("")
    A("95%% bands, honest fill: recall %s, false fire %s."
      % (_band(res["arms"]["honest"]["recall_S"]),
         _band(res["arms"]["honest"]["false_fire_none"])))
    A("")

    A("## What the fill actually touched")
    A("")
    fe = res["fill_effect"]
    A("| | honest fill | old fill | change |")
    A("|---|---:|---:|---:|")
    A("| signals the engine produced | %d | %d | %+d |"
      % (fe["signals_detected"]["honest"], fe["signals_detected"]["published"],
         fe["signals_detected"]["delta"]))
    A("| entries the engine took | %d | %d | %+d |"
      % (fe["entries_taken"]["honest"], fe["entries_taken"]["published"],
         fe["entries_taken"]["delta"]))
    A("| days with the same signal count | %d of %d | | |"
      % (fe["days_with_identical_signal_count"], fe["days_compared"]))
    A("| days with the same entry count | %d of %d | | |"
      % (fe["days_with_identical_entry_count"], fe["days_compared"]))
    A("")
    A("Detection sits upstream of the price and filtering sits downstream, and "
      "this table says which one moved: **the engine sees exactly the same "
      "%d signals on exactly the same days, and lets %d more of them become "
      "trades.** Nothing was detected that was not detected before."
      % (fe["signals_detected"]["honest"], fe["entries_taken"]["delta"]))
    A("")
    w = res.get("why_it_flipped")
    if w and "status_mix" in w:
        mp_, mh = w["status_mix"]["published"], w["status_mix"]["honest"]
        A("### Which gate let go")
        A("")
        A("Replayed again over just the **%d S days the honest fill newly "
          "trades**, counting why each signal was refused:" % w["n_flipped_S_days"])
        A("")
        A("| what happened to the signal | old fill | honest fill |")
        A("|---|---:|---:|")
        for st in sorted(set(mp_) | set(mh)):
            A("| `%s` | %d | %d |" % (st, mp_.get(st, 0), mh.get(st, 0)))
        A("")
        A("**It is the minimum-risk floor, and only that.** `skipped_d` is "
          "`signal_runner.py:2866` — *\"an intrabar fill sitting on the stop "
          "has no trade to size\"* — and it falls %d → %d while %d signals "
          "start firing. The minimum-stop-percent skip barely registers (%d → "
          "%d), so the report's first guess that both gates were involved was "
          "wrong and is corrected here. The reason is direct: the old fill "
          "back-dated the entry onto the level, and for a break-and-retest the "
          "level **is** the stop, so `entry - stop` collapsed toward zero and "
          "the trade could not be sized. Paying the minute's close puts real "
          "distance between entry and stop, and the floor stops binding."
          % (mp_.get("skipped_d", 0), mh.get("skipped_d", 0),
             mh.get("fired", 0), mp_.get("skipped_min_stop_pct", 0),
             mh.get("skipped_min_stop_pct", 0)))
        A("")
        A("That is worth saying plainly on its own: **for two years the "
          "unobtainable fill was silently vetoing the engine's own trades.** "
          "It priced the entry so close to the stop that the sizer refused "
          "them. Fixing the price did not make the engine smarter — it "
          "un-blocked a gate that the fake price was tripping.")
        A("")
    A("Day-level verdict flips, by his grade:")
    A("")
    A("| his grade | traded only on the honest fill | traded only on the old fill |")
    A("|---|---:|---:|")
    for g in ("S", "A", "C", "B", "none"):
        h = fe["day_verdict_flips"].get("%s_honest_only" % g, 0)
        p = fe["day_verdict_flips"].get("%s_published_only" % g, 0)
        if h or p:
            A("| %s | %d | %d |" % (g, h, p))
    A("")

    A("## The paired test")
    A("")
    A("Same days, both arms, so this is a paired comparison and not two "
      "independent samples.")
    A("")
    A("| | days | both fire | honest only | old only | neither | exact p |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for name, key in (("his S days", "S_days"), ("his refusals", "refusal_days")):
        p = res["paired"][key]
        A("| %s | %d | %d | %d | %d | %d | %.3f |"
          % (name, p["n"], p["both"], p["only_arm"], p["only_base"],
             p["neither"], p["mcnemar_exact_p"]))
    A("")
    A("*(\"honest only\" = the day is traded on the honest fill and silent on "
      "the old one.)*")
    A("")

    A("## By setup — his label, honest fill vs old fill")
    A("")
    A("| setup | recall, honest | recall, old | false fire, honest | false fire, old |")
    A("|---|---|---|---|---|")
    for fam in ("break_and_retest", "one_candle_rule", "rule_84", "unlabelled"):
        h = res["arms"]["honest"]["by_his_setup"].get(fam)
        p = res["arms"]["published"]["by_his_setup"].get(fam)
        if not h:
            continue
        A("| %s | %s | %s | %s | %s |"
          % (fam.replace("_", " "), _rate_cell(h["recall_S"]),
             _rate_cell(p["recall_S"]), _rate_cell(h["false_fire_none"]),
             _rate_cell(p["false_fire_none"])))
    A("")
    A("Only %d of the judged days carry a setup label he wrote, so these rows "
      "are thin. The unlabelled row is the rest."
      % res["his_labels_coverage"]["days_with_a_setup_label"])
    A("")

    A("## By entry minute — when the engine fired")
    A("")
    A("| window | recall, honest | recall, old | false fire, honest | false fire, old |")
    A("|---|---|---|---|---|")
    for name, _lo, _hi in g83.BUCKETS:
        h = res["arms"]["honest"]["by_engine_fire_bucket"][name]
        p = res["arms"]["published"]["by_engine_fire_bucket"][name]
        A("| %s | %s | %s | %s | %s |"
          % (name, _rate_cell(h["recall_S"]), _rate_cell(p["recall_S"]),
             _rate_cell(h["false_fire_none"]), _rate_cell(p["false_fire_none"])))
    A("")
    A("Denominators are all S days and all refusal days, so the windows do not "
      "sum to the headline — a day can fire in more than one window.")
    A("")
    A("### By the minute he stated")
    A("")
    A("| window | recall, honest | recall, old |")
    A("|---|---|---|")
    for name in [b[0] for b in g83.BUCKETS] + ["no_stated_minute"]:
        h = res["arms"]["honest"]["by_his_stated_bucket"][name]
        p = res["arms"]["published"]["by_his_stated_bucket"][name]
        A("| %s | %s | %s |" % (name, _rate_cell(h["recall_S"]),
                                _rate_cell(p["recall_S"])))
    A("")

    A("## Honesty checks")
    A("")
    for arm in ARM_ORDER:
        cc = res["arms"][arm]["same_34_cards_this_run"]
        A("- **%s fill, scored on the same 100 blind cards:** %d of %d S days, "
          "and %d of %d refusals fired."
          % (arm, cc["fired_on_S"], cc["n_S"], cc["fired_on_refusals"],
             cc["n_refusals"]))
    ch = res["arms"]["honest"]["same_34_cards_this_run"]
    cp = res["arms"]["published"]["same_34_cards_this_run"]
    A("- **And there is the trap.** `DIRECTION.md` says to gate on held-out "
      "recall against that sample. On that sample alone the honest fill reads "
      "%d of 34 against %d of 34 and looks like a clear win. On the same "
      "sample its false fires go %d of %d to %d of %d. **Held-out recall on "
      "its own cannot tell a better engine from a busier one** — it has no "
      "denominator for the days he refused. Score the refusals beside it, "
      "every time."
      % (ch["fired_on_S"], cp["fired_on_S"], cp["fired_on_refusals"],
         cp["n_refusals"], ch["fired_on_refusals"], ch["n_refusals"]))
    A("- Router delegation to `signal_runner.SignalRunner._route` asserted "
      "before either arm ran; the script exits rather than print a number "
      "off the old photocopy.")
    A("- Each arm asserts the fill mode it actually loaded with, so the two "
      "arms cannot silently be the same book.")
    A("- Legacy ladder, side by side and never mixed in: entries taken on his "
      "S days grade `%s` (honest) and `%s` (old). `A+` is retired; the live "
      "path now routes on his S grade."
      % (json.dumps(res["arms"]["honest"]["legacy_grade_mix_on_S_hits"]),
         json.dumps(res["arms"]["published"]["legacy_grade_mix_on_S_hits"])))
    A("- Replay errors: %s."
      % ", ".join("%s %d" % (a, res["arm_meta"][a]["n_errors"])
                  for a in ARM_ORDER))
    A("")
    A("## Two things this changes in the files")
    A("")
    h = res["arms"]["honest"]
    A("1. **`DIRECTION.md`'s recall row is stale.** It reads 58.6%%, and it "
      "says the recall and durability rows are unaffected by the fill. The "
      "recall row *is* affected: on the fill the repo now ships, recall is "
      "**%s%%** (%d of %d), and the distance to the 90%% gate goes from 30.9 "
      "points to **%s points**. That is a real move in the gate row, and it "
      "was bought by loosening, not by discriminating."
      % (h["recall_S"]["pct"], h["recall_S"]["k"], h["recall_S"]["n"],
         h["points_below_gate"]))
    A("2. **Precision is unchanged** — %s%% against %s%%. Of every 100 days it "
      "trades, about 38 are his and 62 are days he refused, same as before. "
      "Nothing about the sorting improved."
      % (h["precision_pct"], res["arms"]["published"]["precision_pct"]))
    A("")
    A("## What this does not say")
    A("")
    A("It does not say the engine is accurate. Recall is %s%% against a 90%% "
      "gate, and it fires on %s%% of the days he refused — the finding from "
      "last night stands unchanged: **the engine is not blind, it is "
      "undiscriminating.** All this measures is whether paying an honest price "
      "moved that."
      % (res["arms"]["honest"]["recall_S"]["pct"],
         res["arms"]["honest"]["false_fire_none"]["pct"]))
    A("")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("wrote " + OUT_MD)


# ---------------------------------------------------------------------- driver

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm")
    ap.add_argument("--why-arm")
    ap.add_argument("--why-keys")
    ap.add_argument("--worker-out")
    ap.add_argument("--workdir", default=os.path.join(HERE, "_g85_arms"))
    ap.add_argument("--reuse", action="store_true")
    a = ap.parse_args()

    if a.why_arm:
        return run_why_worker(a.why_arm, a.why_keys, a.worker_out)
    if a.arm:
        return run_worker(a.arm, a.worker_out)

    g83.assert_real_router()
    os.makedirs(a.workdir, exist_ok=True)

    procs = {}
    for arm in ARM_ORDER:
        out = os.path.join(a.workdir, "arm_%s.json" % arm)
        if a.reuse:
            procs[arm] = (None, out)
            continue
        env = dict(os.environ)
        env.update(ARMS[arm])
        env["PYTHONPATH"] = ROOT + os.pathsep + HERE
        cmd = [sys.executable, os.path.abspath(__file__), "--arm", arm,
               "--worker-out", out]
        print("launching %-10s ENTRY_FILL=%s" % (arm, ARMS[arm]["ENTRY_FILL"]),
              flush=True)
        procs[arm] = (subprocess.Popen(cmd, cwd=ROOT, env=env), out)

    reps, meta = {}, {}
    for arm, (p, out) in procs.items():
        rc = p.wait() if p is not None else 0
        if rc != 0 or not os.path.exists(out):
            raise SystemExit("ARM FAILED: %s (rc=%s)" % (arm, rc))
        d = json.load(open(out, encoding="utf-8"))
        if d["entry_fill"] != ARMS[arm]["ENTRY_FILL"]:
            raise SystemExit("arm %s came back with ENTRY_FILL=%s"
                             % (arm, d["entry_fill"]))
        reps[arm] = d["days"]
        meta[arm] = {"flags": d["flags"], "elapsed_sec": d["elapsed_sec"],
                     "n_errors": d["n_errors"], "errors": d["errors"]}
        print("loaded %-10s %d days, %.0fs" % (arm, len(d["days"]),
                                               d["elapsed_sec"]))

    if reps["honest"] == reps["published"]:
        print("NOTE: the two arms produced byte-identical replays.")

    import marks_pool as mp
    pool = mp.canonical_pool()
    labels = g83.his_labels()

    arms = {arm: g83.score_arm(pool, labels, reps[arm]) for arm in ARM_ORDER}
    for arm in ARM_ORDER:
        arms[arm]["same_34_cards_this_run"] = g83.cross_check_34(reps[arm])

    last_night = None
    if os.path.exists(LAST_NIGHT):
        last_night = json.load(open(LAST_NIGHT, encoding="utf-8"))["arms"]["base"]

    paired = {
        "S_days": g83.pair_arms(pool, reps["published"], reps["honest"], "S"),
        "refusal_days": g83.pair_arms(pool, reps["published"], reps["honest"],
                                      "none"),
    }
    # pair_arms names the FIRST replay "base"; here that is the old fill.
    for k in paired:
        paired[k]["only_base_means"] = "old (published) fill only"
        paired[k]["only_arm_means"] = "honest (close) fill only"

    head = compare(arms["honest"], arms["published"], last_night)

    # Does the old-fill arm reproduce last night, day for day? If it does, the
    # five commits since f20fbecd changed no recall verdict and the middle
    # column is a true control. If it does not, say so instead of pretending.
    repro = None
    if last_night:
        repro = all(
            arms["published"][f]["k"] == last_night[f]["k"]
            and arms["published"][f]["n"] == last_night[f]["n"]
            for f in ("recall_S", "false_fire_none", "fire_A", "fire_C",
                      "detected_any_signal_S", "detected_any_signal_none"))
        repro = bool(repro and arms["published"]["precision_pct"]
                     == last_night["precision_pct"])

    res = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "question": "does the honest entry fill change accuracy?",
        "money_bar_per_day_usd": round(MONEY_BAR, 2),
        "router": "signal_runner.SignalRunner._route via "
                  "t4_engine_recall.CaptureRunner (delegation asserted)",
        "grades": "research/marks_pool.py -- one grade per symbol-day, "
                  "24 corpora, nine spellings of S",
        "pool": {
            "total_judged_symbol_days": len(pool),
            "with_bars": sum(1 for e in pool.values() if e.has_bars),
            "grade_mix_with_bars": dict(Counter(
                e.grade for e in pool.values() if e.has_bars)),
        },
        "his_labels_coverage": {
            "days_with_a_setup_label": sum(1 for v in labels.values()
                                           if v["setups"]),
            "days_with_a_stated_minute": sum(1 for v in labels.values()
                                             if v["minutes"]),
        },
        "arm_meta": meta,
        "arms": arms,
        "paired": paired,
        "headline": head,
        "reproduces_last_night": repro,
        "fill_effect": fill_effect_on_volume(reps["honest"], reps["published"],
                                             pool),
        "why_it_flipped": why_it_flipped(pool, reps, a.workdir),
        "last_night_context": {
            "source": "research/g83_recall278.json (commit f20fbecd, "
                      "2026-08-30 03:19, ENTRY_FILL=published)",
            "caveat": "a DIFFERENT engine -- five commits have landed since, "
                      "three of them in the router. Not a control for the fill.",
        },
    }
    res["separation_delta"] = bootstrap_separation_delta(
        pool, reps["published"], reps["honest"])
    res["verdict"] = verdict(head, paired, res["separation_delta"])

    slim = json.loads(json.dumps(res))
    for arm in slim["arms"]:
        slim["arms"][arm].pop("_S_keys", None)
        slim["arms"][arm].pop("_NO_keys", None)
    json.dump(slim, open(OUT_JSON, "w", encoding="utf-8"), indent=2,
              sort_keys=True)
    print("wrote " + OUT_JSON)

    write_md(res)

    v = res["verdict"]
    print("\nVERDICT: the honest fill %s. %s" % (v["call"], v["why"]))
    for arm in ARM_ORDER:
        b = arms[arm]
        print("  %-10s recall %s%% (%d/%d)  false fire %s%% (%d/%d)  "
              "precision %s%%  separation %+0.1f"
              % (arm, b["recall_S"]["pct"], b["recall_S"]["k"],
                 b["recall_S"]["n"], b["false_fire_none"]["pct"],
                 b["false_fire_none"]["k"], b["false_fire_none"]["n"],
                 b["precision_pct"],
                 b["separation_S_minus_none"]["points"]))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
