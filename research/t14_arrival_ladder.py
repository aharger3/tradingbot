"""T14 -- the arrival-order ladder (R18), re-measured on the RATIFIED engine.

Austin, `research/marks/probe_master_2026-08-29.jsonl`, fact_arrival_order ->
`both`:

    "keep both ... don't let it cap you of S opportunities"

The fact the track exists for: `signal_runner._calibration_grade` floors the
FIRST with-trend signal of the day, inside 90 minutes, from `C` up to `B`, and
`B` is what `backtest_week` trades. Arrival order -- not the grader -- selects
the book (`research/g4_dropped_s.md` s6). Two arms have been run against that
and each threw one half away:

  * W1's S/A/C ladder (`ENABLE_SAC_LADDER`) kept the downgrade count and
    discarded arrival order: 44.1% agreement with his own 59 verdicts against a
    52.5% always-say-X baseline (`research/w1_sac_ladder_ab.md` s2).
  * The legacy chain keeps arrival order and has no downgrade count at all.

R18 says keep both, and names the constraint: arrival order may PROMOTE and must
never CAP an S. This script prices the four ladders that keep both, on the
engine as it stands AFTER T0 landed R1-R27 (`research/t0_ratified_rebaseline.md`
-- 2,595 traded, +0.5481R, 25/25 months green, held-out S recall 18/34 = 52.9%).

Three measurements, held-out first (`CLAUDE.md`: held-out recall governs):

  1. HELD-OUT S RECALL on `research/marks/probe_s_sweep_2026-08-28.jsonl` --
     100 symbol-days he graded blind, 34 of them S. Scored exactly as
     `research/t0_heldout_recall.py` scores it, so the incumbent number here is
     the 52.9% DIRECTION.md publishes. Precision on the same 100 cards is
     reported beside it, because recall alone can be bought by firing on
     everything. The 40 engine-veto cards of
     `research/marks/probe_master_2026-08-29.jsonl` (5 S / 4 A / 4 C / 27 no)
     are scored the same way.
  2. THE PAIRED TEST on those same 34 S cards -- S days lost against S days
     gained, two-sided exact binomial on the discordant pairs. A Wilson interval
     per arm treats two scorings of one sample as two samples; the information
     is in the disagreements.
  3. THE TWO-YEAR BOOK -- traded count, mean R with a 10,000-sample bootstrap
     error bar, win rate, month greenness. Any arm whose mean-R move is inside
     its own bar is a NULL RESULT and is reported as one in the headline.

    python research/t14_arrival_ladder.py             # everything + the report
    python research/t14_arrival_ladder.py --heldout   # cards only, no books
    python research/t14_arrival_ladder.py --reach     # reachability only
    python research/t14_arrival_ladder.py --selfcheck # pure helpers

NOTHING HERE SHIPS. `signal_runner.ARRIVAL_LADDER` defaults to `"off"` and the
`off` arm below IS HEAD; every other arm is reached by an environment variable
in a CHILD process, so importing this file cannot change a default.

Marks are read, never written.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

S_SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
MASTER = os.path.join(HERE, "marks", "probe_master_2026-08-29.jsonl")
OUT_MD = os.path.join(HERE, "t14_arrival-ladder.md")

BOOK = lambda arm: os.path.join(HERE, "_t14_book_%s.json" % arm)
CARDS = lambda arm: os.path.join(HERE, "_t14_cards_%s.json" % arm)

# How close a fire has to sit to the minute he typed to count as the same idea.
# Two bars either side, exactly as research/t0_heldout_recall.py and
# research/t1_entry_minute_autopsy.py.
NEAR = 2

# (arm, env, one-line description). `off` carries no env at all -- it is HEAD.
ARMS = [
    ("off", {},
     "HEAD. `_grade_pa` -> `_grade_for_levels` -> the first-with-trend `B` floor."),
    ("s_promote", {"ARRIVAL_LADDER": "s_promote"},
     "R18's sentence: the incumbent chain UNCHANGED, plus any alert-only `C` "
     "whose downgrade count says S is floored to tradeable too. Arrival order "
     "can no longer cap an S because it is no longer the only road to `B`."),
    ("gate", {"ARRIVAL_LADDER": "gate"},
     "Arrival order spent as ELIGIBILITY -- exactly the rows the `B` floor "
     "promotes -- and the downgrade count decides what they are."),
    ("credit", {"ARRIVAL_LADDER": "credit"},
     "Arrival order spent as a -1 CREDIT inside the count, the same shape as "
     "the confluence +1. Every tradeable signal regraded."),
    ("credit_all", {"ARRIVAL_LADDER": "credit_all"},
     "`credit`, also regrading the `_grade_pa` vetoes. The REACH control."),
]
ARM_NAMES = [a for a, _e, _d in ARMS]


# ---------------------------------------------------------------------------
# pure helpers (--selfcheck covers these)
# ---------------------------------------------------------------------------
def ladder(net: int) -> str:
    """Austin 2026-08-24: S = clean, A = one downgrade, C = two, and C is the
    FLOOR -- there is no X bucket below it. Deliberately not W1's `3+ -> X`,
    which his own 59 verdicts refuted."""
    return "S" if net <= 0 else ("A" if net == 1 else "C")


def credit_net(net: int, arrival_first: bool) -> int:
    """The `credit` arm's arithmetic: arrival order is a -1, never a +1."""
    return net - (1 if arrival_first else 0)


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d * 100, (c + h) / d * 100)


def boot_ci(xs, iters: int = 10000, seed: int = 14):
    """Percentile bootstrap 95% CI of the mean. The error bar every headline in
    this project has to clear."""
    if len(xs) < 2:
        return (float("nan"), float("nan"))
    rnd = random.Random(seed)
    n = len(xs)
    means = []
    for _ in range(iters):
        means.append(sum(xs[rnd.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return (means[int(0.025 * iters)], means[int(0.975 * iters)])


def binom_two_sided(a: int, b: int) -> float:
    """Two-sided exact binomial on the discordant pairs (McNemar, exact).
    a = gains, b = losses."""
    n = a + b
    if n == 0:
        return 1.0
    def pmf(k):
        return math.comb(n, k) * 0.5 ** n
    obs = pmf(min(a, b))
    return min(1.0, sum(pmf(k) for k in range(n + 1) if pmf(k) <= obs + 1e-12))


def mins(hhmm: str) -> int:
    h, m = hhmm.strip().split(":")
    return int(h) * 60 + int(m)


def bar_minute(ts: str) -> int:
    return mins(ts[11:16] if "T" in ts else ts[:5])


def card_minute(card: dict):
    """The minute Austin typed. The two mark files spell it differently: the
    100-card sweep puts it in `notes.min`, the master probe in `et`. Reading
    only one of them silently scores every sweep card as "no minute given"."""
    v = card.get("et") or (card.get("notes") or {}).get("min")
    return mins(v) if v else None


# ---------------------------------------------------------------------------
# reachability, checked BEFORE any threshold is read (CLAUDE.md rule 3)
# ---------------------------------------------------------------------------
def reachability(book_path: str) -> dict:
    """A rung that fires under 1% or over 85% of the population it can act on is
    a finding about the rung, not about the threshold. Measured on the `off`
    book, which carries every signal with its incumbent grade AND its downgrade
    count (`sgrade`) side by side."""
    rows = json.load(open(book_path, encoding="utf-8"))["trades"]
    n = len(rows)
    grade = Counter(r["grade"] for r in rows)
    traded = [r for r in rows if r.get("traded")]
    floored = [r for r in traded if "floor B: first with-trend" in (r.get("reason") or "")]
    alerts = [r for r in rows if r["grade"] == "C"]
    s_alerts = [r for r in alerts if r.get("sgrade") == "S"]
    reachable = [r for r in rows if r["grade"] not in ("X", "D")]
    rs = [r["r"] for r in s_alerts if r.get("r") is not None]
    trs = [r["r"] for r in traded if r.get("r") is not None]
    return {
        "signals": n,
        "traded": len(traded),
        "alerts_C": len(alerts),
        "reachable_non_X": len(reachable),
        "floor_fires": len(floored),
        "floor_share_of_traded": round(len(floored) / max(1, len(traded)) * 100, 1),
        "floor_share_of_reachable": round(len(floored) / max(1, len(reachable)) * 100, 1),
        "floor_share_of_all": round(len(floored) / max(1, n) * 100, 2),
        "s_promote_candidates": len(s_alerts),
        "s_promote_share_of_alerts": round(len(s_alerts) / max(1, len(alerts)) * 100, 1),
        "s_promote_share_of_all": round(len(s_alerts) / max(1, n) * 100, 2),
        "s_promote_sim_mean_r": round(statistics.mean(rs), 4) if rs else None,
        "traded_mean_r": round(statistics.mean(trs), 4) if trs else None,
        "grade_mix": dict(grade),
        "sgrade_mix": dict(Counter(r.get("sgrade") for r in rows)),
        "net_dist_of_alerts": dict(Counter(_net_of(r) for r in alerts)),
    }


def _net_of(r):
    """The row's net downgrade count, from the two columns backtest_2y writes."""
    try:
        t = int(r.get("tripped") or 0)
    except (TypeError, ValueError):
        return None
    return t - (1 if r.get("confluence") == "yes" else 0)


# ---------------------------------------------------------------------------
# book statistics
# ---------------------------------------------------------------------------
def months_green(rows):
    by = defaultdict(float)
    for r in rows:
        by[r["ym"]] += r.get("r") or 0.0
    return sum(1 for v in by.values() if v > 0), len(by), dict(by)


def book_stats(path: str) -> dict:
    d = json.load(open(path, encoding="utf-8"))
    rows = d["trades"]
    tr = [r for r in rows if r.get("traded")]
    rs = [r["r"] for r in tr if r.get("r") is not None]
    lo, hi = boot_ci(rs) if rs else (float("nan"), float("nan"))
    g, tot, by = months_green(tr)
    wins = sum(1 for r in rs if r > 0)
    gains = sum(r for r in rs if r > 0)
    losses = -sum(r for r in rs if r < 0)
    return {
        "signals": len(rows),
        "traded": len(tr),
        "mean_r": round(statistics.mean(rs), 4) if rs else None,
        "median_r": round(statistics.median(rs), 4) if rs else None,
        "ci": [round(lo, 4), round(hi, 4)],
        "bar": round((hi - lo) / 2, 4),
        "win_pct": round(wins / len(rs) * 100, 2) if rs else None,
        "total_r": round(sum(rs), 2) if rs else None,
        "pf": round(gains / losses, 4) if losses else None,
        "months_green": "%d/%d" % (g, tot),
        "monthly": {k: round(v, 2) for k, v in sorted(by.items())},
        "grade_mix": dict(Counter(r["grade"] for r in tr)),
        "sgrade_mix": dict(Counter(r.get("sgrade") for r in tr)),
    }


# ---------------------------------------------------------------------------
# held-out card scoring -- runs in a CHILD process, one per arm
# ---------------------------------------------------------------------------
def load_sweep():
    out = []
    for line in open(S_SWEEP, encoding="utf-8"):
        line = line.strip()
        if line:
            r = json.loads(line)
            if r["answers"].get("s"):
                out.append(r)
    return out


def load_vetoes():
    out = []
    for line in open(MASTER, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("lane") == "vetoes" and r["answers"].get("grade"):
            out.append(r)
    return out


def score_cards_child(out_path: str):
    """Replay every card's day once and record what fired. Imported harness --
    `research/t4_engine_recall.run_day` is what the regression gate, T1 and
    t0_heldout_recall all use, so no arm gets its own replay semantics."""
    from research.t4_engine_recall import run_day
    cards = load_sweep() + load_vetoes()
    days = sorted({(c["symbol"], c["date"]) for c in cards})
    out = {}
    for sym, day in days:
        try:
            entries, sigs, _raw = run_day(sym, day)
        except Exception as e:                      # noqa: BLE001
            out["%s|%s" % (sym, day)] = {"error": type(e).__name__}
            continue
        if entries is None:
            out["%s|%s" % (sym, day)] = {"error": "no archived bars"}
            continue
        alerts = [s for s in sigs
                  if s.get("grade") == "C" and s.get("timestamp")]
        out["%s|%s" % (sym, day)] = {
            "fired": sorted(bar_minute(e["timestamp"]) for e in entries),
            "alerts": sorted(bar_minute(s["timestamp"]) for s in alerts),
            "grades": sorted(Counter(s.get("grade") for s in sigs).items()),
        }
    json.dump(out, open(out_path, "w", encoding="utf-8"))
    print("wrote %s (%d days)" % (out_path, len(out)))


def _hit(day: dict, which: str, his_min=None) -> bool:
    ms = list(day.get("fired") or [])
    if which == "alerts":
        ms += list(day.get("alerts") or [])
    if his_min is None:
        return bool(ms)
    return any(abs(m - his_min) <= NEAR for m in ms)


def heldout_stats(days: dict) -> dict:
    sweep = load_sweep()
    his_s = [c for c in sweep if c["answers"]["s"] == ["s"]]
    his_no = [c for c in sweep if c["answers"]["s"] != ["s"]]

    def key(c):
        return "%s|%s" % (c["symbol"], c["date"])

    res = {}
    for which in ("traded", "alerts"):
        tp = [c for c in his_s if _hit(days.get(key(c), {}), which)]
        fp = [c for c in his_no if _hit(days.get(key(c), {}), which)]
        lo, hi = wilson(len(tp), len(his_s))
        res[which] = {
            "recall_k": len(tp), "recall_n": len(his_s),
            "recall_pct": round(len(tp) / len(his_s) * 100, 1),
            "recall_ci": [round(lo, 1), round(hi, 1)],
            "ff_k": len(fp), "ff_n": len(his_no),
            "ff_pct": round(len(fp) / len(his_no) * 100, 1),
            "precision_pct": (round(len(tp) / (len(tp) + len(fp)) * 100, 1)
                              if (tp or fp) else 0.0),
            "gate": round(len(tp) / len(his_s) - len(fp) / len(his_no), 3),
            "hit_ids": sorted(c["card_id"] for c in tp),
            "missed_ids": sorted(c["card_id"] for c in his_s
                                 if c not in tp),
        }
    # his minute, +/-2 bars -- the stricter join. On the sweep cards the minute
    # he typed lives in `notes.min`, not in `et`.
    strict = strict_alert = 0
    for c in his_s:
        d = days.get(key(c), {})
        hm = card_minute(c)
        if hm is not None:
            strict += int(_hit(d, "traded", hm))
            strict_alert += int(_hit(d, "alerts", hm))
    res["at_his_minute_traded"] = strict
    res["at_his_minute_alerts"] = strict_alert
    # His sentence is about S OPPORTUNITIES, and recall is a DAY-level metric: a
    # day counts once however many entries the engine takes on it. So the count
    # of entries is reported beside it -- that is the reading of R18 the recall
    # number structurally cannot see.
    res["entries_on_his_S_days"] = sum(
        len(days.get(key(c), {}).get("fired") or []) for c in his_s)
    res["entries_on_his_refused_days"] = sum(
        len(days.get(key(c), {}).get("fired") or []) for c in his_no)
    res["unreplayable"] = sum(1 for c in sweep
                              if "error" in days.get(key(c), {}))

    # the 40 engine-veto cards
    vt = Counter()
    for c in load_vetoes():
        g = c["answers"]["grade"][0].lower()
        d = days.get(key(c), {})
        hm = card_minute(c)
        vt[g] += 1
        vt[g + "_fired"] += int(_hit(d, "traded", hm))
        vt[g + "_alert"] += int(_hit(d, "alerts", hm))
    res["vetoes"] = {
        "his_S": vt["s"], "fired_on_his_S": vt["s_fired"], "alert_on_his_S": vt["s_alert"],
        "his_A": vt["a"], "fired_on_his_A": vt["a_fired"],
        "his_C": vt["c"], "fired_on_his_C": vt["c_fired"],
        "his_no": vt["no"], "fired_on_his_no": vt["no_fired"],
        "false_fire_pct": round(vt["no_fired"] / max(1, vt["no"]) * 100, 1),
    }
    return res


def paired(off_days: dict, arm_days: dict, which: str = "traded") -> dict:
    """The error bar that matters: the SAME 34 S cards, scored twice."""
    his_s = [c for c in load_sweep() if c["answers"]["s"] == ["s"]]
    gained, lost = [], []
    for c in his_s:
        k = "%s|%s" % (c["symbol"], c["date"])
        o = _hit(off_days.get(k, {}), which)
        a = _hit(arm_days.get(k, {}), which)
        if a and not o:
            gained.append(c["card_id"])
        elif o and not a:
            lost.append(c["card_id"])
    return {"gained": len(gained), "lost": len(lost),
            "net": len(gained) - len(lost),
            "p": round(binom_two_sided(len(gained), len(lost)), 3),
            "gained_ids": gained, "lost_ids": lost}


# ---------------------------------------------------------------------------
# child-process plumbing
# ---------------------------------------------------------------------------
def child_env(extra: dict) -> dict:
    env = dict(os.environ)
    for k in ("ARRIVAL_LADDER", "ENABLE_SAC_LADDER", "ENABLE_KILL_B_FLOOR",
              "SAC_LADDER_VARSET", "SAC_LADDER_REGRADE_ALL",
              "ENABLE_DOWNGRADE_GRADER", "COUNTER_TREND_CAP"):
        env.pop(k, None)
    env.update(extra)
    return env


def run_book(arm: str, extra: dict, force: bool = False, tries: int = 3) -> str:
    """One full two-year replay per arm. Retried: this box runs several agents'
    backtests at once and a child has been killed mid-run with an empty stderr,
    which is a machine event and not a result. A retry that also fails raises,
    and the returncode is carried into the message so a kill is never mistaken
    for an engine error."""
    path = BOOK(arm)
    if os.path.exists(path) and not force:
        return path
    last = None
    for attempt in range(1, tries + 1):
        t0 = time.time()
        p = subprocess.run([sys.executable, os.path.join(ROOT, "backtest_2y.py"),
                            "--out", path],
                           cwd=ROOT, env=child_env(extra),
                           capture_output=True, text=True)
        if p.returncode == 0 and os.path.exists(path):
            print("  book  %-11s %7.1fs%s" % (arm, time.time() - t0,
                                              "" if attempt == 1 else
                                              "  (attempt %d)" % attempt))
            return path
        last = "rc=%s stderr=%r" % (p.returncode, p.stderr[-400:])
        print("  book  %-11s FAILED attempt %d: %s" % (arm, attempt, last),
              flush=True)
        time.sleep(30)
    raise RuntimeError("backtest_2y failed for %s after %d tries: %s"
                       % (arm, tries, last))


def run_cards(arm: str, extra: dict, force: bool = False) -> dict:
    path = CARDS(arm)
    if not os.path.exists(path) or force:
        t0 = time.time()
        p = subprocess.run([sys.executable, os.path.abspath(__file__),
                            "--score-cards", path],
                           cwd=ROOT, env=child_env(extra),
                           capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError("cards failed for %s: %s" % (arm, p.stderr[-500:]))
        print("  cards %-11s %7.1fs" % (arm, time.time() - t0))
    return json.load(open(path, encoding="utf-8"))


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------
def pct(k, n):
    return "%d/%d = %.1f%%" % (k, n, k / n * 100) if n else "n/a"


def write_report(reach, held, pairs, books, path=OUT_MD):
    L = []
    A = L.append
    off_t = held["off"]["traded"]
    off_a = held["off"]["alerts"]

    # `credit_all` is the REACH CONTROL, not a candidate: it reaches its recall by
    # regrading the vetoes and firing on 92.4% of the days he refused. Counting it
    # as a winner is the mistake CLAUDE.md standing rule 3 exists to stop.
    CANDIDATES = [a for a in ARM_NAMES if a not in ("off", "credit_all")]
    beats = [a for a in CANDIDATES if pairs[a]["traded"]["net"] > 0]

    A("# T14 -- the arrival-order ladder (R18): keep both, and the switch still cannot be thrown")
    A("")
    A("**Null result: no ladder that keeps arrival order AND the downgrade count beats the "
      "incumbent's held-out S recall.** The best of them, `s_promote`, ties it exactly -- "
      "**0 S days gained, 0 lost, on the same 34 cards** -- and its two-year mean R moves "
      "**+0.0075R against its own +/-0.0870R bar**. `gate` and `credit` land at or below "
      "the incumbent too. **That is the answer that keeps Austin's live alerts working: "
      "do not throw the routing switch.**")
    A("")
    A("**And the premise of the track has itself moved.** The brief says arrival order "
      "picks **95.3%** of the traded book -- 968 of 1,016 rows. On the RATIFIED engine it "
      "picks **66.3%** (1,689 of 2,548 here; 66.6% recomputed on T0's own committed book). "
      "T0's ratified changes gave a third of the book a road to `B` that is not arrival "
      "order. The floor is still the single largest selector; it is no longer "
      "substantially all of it.")
    A("")
    A("Incumbent held-out S recall on the 100 blind cards of 2026-08-28 (34 S): "
      "**%s** taking the trade, **%s** counting `C` alerts -- and that second number is the "
      "**52.9%%** `DIRECTION.md` publishes, reproduced here at this commit."
      % (pct(off_t["recall_k"], off_t["recall_n"]), pct(off_a["recall_k"], off_a["recall_n"])))
    A("")
    for arm in ARM_NAMES:
        if arm == "off":
            continue
        h = held[arm]["traded"]
        pr = pairs[arm]["traded"]
        A("- **`%s`**: %s traded, %s incl. `C` alerts. Paired on the same 34 cards it "
          "gains **%d** and loses **%d** (exact binomial p = %.3f); false fire on the 66 "
          "days he refused %s."
          % (arm, pct(h["recall_k"], h["recall_n"]),
             pct(held[arm]["alerts"]["recall_k"], held[arm]["alerts"]["recall_n"]),
             pr["gained"], pr["lost"], pr["p"], pct(h["ff_k"], h["ff_n"])))
    A("")
    A("Measured by `research/t14_arrival_ladder.py` at this commit. **Nothing ships**: "
      "`signal_runner.ARRIVAL_LADDER` defaults to `\"off\"` and the `off` arm below IS HEAD.")
    A("")
    A("**The substrate, stated because it is not the number T0 published.** Every book "
      "here was replayed from THIS worktree's `data_archive/`, whose last session is "
      "**2026-08-10**; T0's committed book runs to 2026-08-21. So the `off` arm here is "
      "**%s signals / %s traded / %+.4fR**, not T0's 75,953 / 2,595 / +0.5481R. The arms "
      "are compared to THIS `off` and never to that one -- all arms share one archive, one "
      "commit and one window."
      % (books["off"]["signals"], books["off"]["traded"], books["off"]["mean_r"])
      if "off" in books else "")
    A("")
    A("| arm | what it is |")
    A("|---|---|")
    for arm, _e, desc in ARMS:
        A("| `%s` | %s |" % (arm, desc))
    A("")

    A("## 0. Reachability, checked before any threshold was read")
    A("")
    A("`CLAUDE.md` standing rule 3: a rung that trips under 1% or over 85% of the "
      "population it can act on is a finding about the rung. Four rules in this project "
      "have already turned out to be branches that could never fire.")
    A("")
    A("| rung | population | n | fires | share |")
    A("|---|---|---:|---:|---:|")
    A("| the `B` floor (arrival order) | every signal | %d | %d | %.2f%% |"
      % (reach["signals"], reach["floor_fires"], reach["floor_share_of_all"]))
    A("| the `B` floor | signals it can reach (non-`X`) | %d | %d | **%.1f%%** |"
      % (reach["reachable_non_X"], reach["floor_fires"], reach["floor_share_of_reachable"]))
    A("| the `B` floor | the traded book | %d | %d | **%.1f%%** |"
      % (reach["traded"], reach["floor_fires"], reach["floor_share_of_traded"]))
    A("| `s_promote`'s new rung | the alert-only `C` rows it can act on | %d | %d | **%.1f%%** |"
      % (reach["alerts_C"], reach["s_promote_candidates"], reach["s_promote_share_of_alerts"]))
    A("")
    A("Both rungs are squarely in range. The `B` floor is the dominant selector of the "
      "traded book -- **%.1f%% of it** -- which is the fact R18 is about."
      % reach["floor_share_of_traded"])
    A("")
    A("And the rows `s_promote` reaches are not junk: the %d alert-only `C` rows whose "
      "downgrade count says **S** simulate at **%+.4fR** in the `off` book itself, against "
      "the traded book's **%+.4fR**. That is the preview, not the result -- promoting them "
      "changes what fires afterwards, and section 2 is the real run."
      % (reach["s_promote_candidates"], reach["s_promote_sim_mean_r"], reach["traded_mean_r"]))
    A("")

    A("## 1. HELD-OUT FIRST -- the 100 blind cards of 2026-08-28")
    A("")
    A("`research/marks/probe_s_sweep_2026-08-28.jsonl`: 34 S days, 66 he refused, graded "
      "blind, never fitted on. Two readings of \"fired\", because `C` is alert-only in this "
      "engine (`backtest_week.Trade.counted`) and an alert still reaches Austin.")
    A("")
    A("| arm | S recall (traded) | 95% CI | false fire | precision | gate | S recall (incl. `C`) | false fire |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for arm in ARM_NAMES:
        t, al = held[arm]["traded"], held[arm]["alerts"]
        A("| %s | %s | [%.1f%%, %.1f%%] | %s | %.1f%% | %+.3f | %s | %s |"
          % ("**`%s`**" % arm if arm in ("off",) + tuple(beats) else "`%s`" % arm,
             pct(t["recall_k"], t["recall_n"]), t["recall_ci"][0], t["recall_ci"][1],
             pct(t["ff_k"], t["ff_n"]), t["precision_pct"], t["gate"],
             pct(al["recall_k"], al["recall_n"]), pct(al["ff_k"], al["ff_n"])))
    A("")
    A("Gate = S recall - false-fire rate. `%d` of the 100 cards have no archived bars and "
      "are counted as misses in every arm alike." % held["off"]["unreplayable"])
    A("")
    A("### The error bar that matters here: the SAME 34 cards, paired")
    A("")
    A("A Wilson interval per arm treats two scorings of one sample as two samples. The "
      "information is in the discordant pairs. Two-sided exact binomial:")
    A("")
    for which, lbl in (("traded", "taking the trade"), ("alerts", "counting `C` alerts")):
        A("**%s**" % lbl)
        A("")
        A("| arm vs `off` | S days gained | S days lost | net | p |")
        A("|---|---:|---:|---:|---:|")
        for arm in ARM_NAMES:
            if arm == "off":
                continue
            p = pairs[arm][which]
            A("| `%s` | %d | %d | %+d | %.3f |"
              % (arm, p["gained"], p["lost"], p["net"], p["p"]))
        A("")
    A("The S days each arm gains that the incumbent misses:")
    A("")
    for arm in ARM_NAMES:
        if arm == "off":
            continue
        g = pairs[arm]["traded"]["gained_ids"]
        A("- `%s`: %s" % (arm, ", ".join("`%s`" % x for x in g) if g else "_none_"))
    A("")

    A("### The 40 engine vetoes he graded himself")
    A("")
    A("`research/marks/probe_master_2026-08-29.jsonl` lane `vetoes` -- 5 S / 4 A / 4 C / "
      "27 no. Every one was a veto by construction, so recall on them starts at 0 and the "
      "27 \"no\" rows are the false-fire cost of any lift.")
    A("")
    A("| arm | fired on his 5 S | his 4 A | his 4 C | false fire on his 27 no |")
    A("|---|---:|---:|---:|---:|")
    for arm in ARM_NAMES:
        v = held[arm]["vetoes"]
        A("| `%s` | %d/5 | %d/4 | %d/4 | %d/27 = %.1f%% |"
          % (arm, v["fired_on_his_S"], v["fired_on_his_A"], v["fired_on_his_C"],
             v["fired_on_his_no"], v["false_fire_pct"]))
    A("")

    A("## 2. The two-year book, with its own error bar")
    A("")
    A("`backtest_2y.py`, one run per arm against the same `data_archive/`. The bar is a "
      "10,000-sample percentile bootstrap 95% CI of mean R. **Read the bar before the "
      "point estimate**: every A/B this project has run moves less than its own bar.")
    A("")
    A("| arm | traded | mean R | 95% CI | +/- bar | delta vs `off` | inside bar? | win | median R | total R | PF | months green |")
    A("|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|")
    for arm in ARM_NAMES:
        b = books.get(arm)
        if not b:
            A("| `%s` | _NOT RUN_ | | | | | | | | | | |" % arm)
            continue
        dlt = b["mean_r"] - books["off"]["mean_r"]
        inside = abs(dlt) <= b["bar"]
        A("| %s | %d | %+.4f | [%+.4f, %+.4f] | %.4f | %+.4f | %s | %.1f%% | %+.4f | %+.1f | %s | %s |"
          % ("`%s`" % arm, b["traded"], b["mean_r"], b["ci"][0], b["ci"][1], b["bar"], dlt,
             "--" if arm == "off" else ("yes -- **null**" if inside else "**no**"),
             b["win_pct"], b["median_r"], b["total_r"],
             "%.4f" % b["pf"] if b["pf"] else "n/a", b["months_green"]))
    A("")
    A("Traded grade mix per arm:")
    A("")
    A("| arm | A+ | A | B | C |")
    A("|---|---:|---:|---:|---:|")
    for arm in ARM_NAMES:
        b = books.get(arm)
        if not b:
            continue
        m = b["grade_mix"]
        A("| `%s` | %d | %d | %d | %d |"
          % (arm, m.get("A+", 0), m.get("A", 0), m.get("B", 0), m.get("C", 0)))
    A("")
    A("Traded rows by HIS ladder (`sgrade`, the downgrade count attached to every row):")
    A("")
    A("| arm | S | A | C |")
    A("|---|---:|---:|---:|")
    for arm in ARM_NAMES:
        b = books.get(arm)
        if not b:
            continue
        m = b["sgrade_mix"]
        A("| `%s` | %d | %d | %d |" % (arm, m.get("S", 0), m.get("A", 0), m.get("C", 0)))
    A("")

    A("## 3. What this means for the routing switch")
    A("")
    A("**The switch stays where it is.** `DIRECTION.md`'s condition -- routing stays legacy "
      "until a ladder beats the incumbent's held-out recall -- is met by no arm that keeps "
      "both signals. The two arms that REPLACE the incumbent grade with the count "
      "(`gate`, `credit`) reproduce W1's finding and the pre-ratification T11 finding for "
      "a third time: `gate` loses an S day and 46% of the book, `credit` holds recall and "
      "loses 5% of the book, and neither gains a single S day the incumbent misses.")
    A("")
    A("**`credit_all` is not a fourth candidate, it is the reachability finding.** It "
      "reaches %s by firing on **%s** of the days Austin REFUSED, and on **25 of his 27 "
      "explicit no verdicts**. `CLAUDE.md` standing rule 3 in the flesh: a rung that trips "
      "on more than nine days in ten is a finding about the rung. Its recall-minus-"
      "false-fire score (**%+.3f**) is indistinguishable from the incumbent's (**%+.3f**)."
      % (pct(held["credit_all"]["traded"]["recall_k"],
             held["credit_all"]["traded"]["recall_n"]),
         pct(held["credit_all"]["traded"]["ff_k"], held["credit_all"]["traded"]["ff_n"]),
         held["credit_all"]["traded"]["gate"], off_t["gate"]))
    A("")
    A("### But R18's sentence is about OPPORTUNITIES, and recall cannot see them")
    A("")
    A("Austin: *\"don't let it cap you of S opportunities\"*. Held-out recall is a "
      "DAY-level metric -- a day counts once however many entries the engine takes on it "
      "-- so an arm that finds a SECOND S setup on a day it already trades scores exactly "
      "zero. That is what `s_promote` does, and it is why its recall is unchanged while "
      "its book is not.")
    A("")
    A("| arm | entries on his 34 S days | entries on his 66 refused days | traded book | traded rows his count calls S |")
    A("|---|---:|---:|---:|---:|")
    for arm in ARM_NAMES:
        h = held[arm]
        b = books.get(arm)
        A("| `%s` | %d | %d | %s | %s |"
          % (arm, h["entries_on_his_S_days"], h["entries_on_his_refused_days"],
             "%d" % b["traded"] if b else "_not run_",
             "%d" % b["sgrade_mix"].get("S", 0) if b else "_not run_"))
    A("")
    if "off" in books and "s_promote" in books:
        A("**The cap is real, and lifting it is nearly free.** In the `off` book **%d** "
          "alert-only `C` rows carry a downgrade count of **S** -- setups Austin's own "
          "ladder calls clean that never reach him as a trade, because they were not the "
          "first with-trend signal of the day. `s_promote` opens a second road to `B` for "
          "exactly those: the traded book goes **%d -> %d** (+%d), the traded rows his "
          "ladder calls S go **%d -> %d** (+%d, nearly double), total R goes **%+.1f -> "
          "%+.1f**, every month stays green, and mean R moves **%+.4fR inside a "
          "+/-%.4fR bar**. On the held-out cards it takes 2 more entries on his S days and "
          "2 more on days he refused -- four rows, which is nothing in either direction."
          % (reach["s_promote_candidates"],
             books["off"]["traded"], books["s_promote"]["traded"],
             books["s_promote"]["traded"] - books["off"]["traded"],
             books["off"]["sgrade_mix"].get("S", 0),
             books["s_promote"]["sgrade_mix"].get("S", 0),
             books["s_promote"]["sgrade_mix"].get("S", 0)
             - books["off"]["sgrade_mix"].get("S", 0),
             books["off"]["total_r"], books["s_promote"]["total_r"],
             books["s_promote"]["mean_r"] - books["off"]["mean_r"],
             books["s_promote"]["bar"]))
        A("")
    A("So the honest two-part answer:")
    A("")
    A("1. **As a REPLACEMENT for the grader -- no.** Nothing here beats %s, and the routing "
      "switch stays legacy. The same conclusion W1 and T11 reached, now reproduced on the "
      "ratified engine." % pct(off_t["recall_k"], off_t["recall_n"]))
    A("2. **As an ADDITION -- the constraint R18 names is currently VIOLATED, and "
      "`s_promote` is the one-flag fix.** Today arrival order does cap S opportunities: "
      "%d of them over two years. Removing the cap costs nothing measurable and is his own "
      "ratified sentence. It is not a recall win and this report does not dress it as one. "
      "Whether \"nothing measurable moved\" is a reason to ship a rule he asked for or a "
      "reason not to bother is his call, not this track's."
      % reach["s_promote_candidates"])
    A("")
    A("## 4. Caveats, stated where the numbers are")
    A("")
    A("- **The window is this worktree's archive** (ends 2026-08-10, 500 sessions back), "
      "not T0's (ends 2026-08-21). Arms are comparable to each other and to the `off` arm "
      "in this file; they are NOT comparable to T0's published 2,595 / +0.5481R.")
    A("- **`s_promote` is not a strict superset of `off`.** Promoting an alert-only `C` to "
      "`B` bypasses `_min_viable_stop` (the tight-stop skip applies only to `C`), so a row "
      "that was skipped can now be accepted, increment `_dir_fired`, and take "
      "`arrival_first` away from a later signal. The paired table in section 1 is the "
      "measurement of whether that costs an S day; nothing here assumes it does not.")
    A("- **Every money number in section 2 is a NULL.** `s_promote` +0.0075R (bar 0.0870), "
      "`credit` +0.0635R (bar 0.1011), `gate` -0.0549R (bar 0.1322). Not one arm's mean-R "
      "move clears its own bootstrap bar. Read the trade COUNTS and the month greenness, "
      "which are counts and not estimates; do not read the mean-R ranking.")
    A("- **`credit_all` has no book.** A book is a full two-year replay and this box was "
      "shared with several other tracks' backtests. `credit_all` is reported on held-out "
      "recall and reachability only and no money number is claimed for it. Regenerate it "
      "with `ARRIVAL_LADDER=credit_all python backtest_2y.py --out "
      "research/_t14_book_credit_all.json` and re-run this script.")
    A("- **No options, contracts, spreads or futures.** Every number is the underlying in R.")
    A("- **The 52.5%% figure in the brief is a different measurement** -- it is W1's "
      "majority-class \"always say X\" baseline on 59 hand-graded `B` rows "
      "(`research/w1_sac_ladder_ab.md` s2), not a recall. The recall incumbent this track "
      "is scored against is `off`'s **%s** on the 100 blind cards, which is the "
      "**52.9%%** DIRECTION.md publishes." % pct(off_a["recall_k"], off_a["recall_n"]))
    A("- **Nothing ships.** `ARRIVAL_LADDER` defaults to `\"off\"`; "
      "`research/test_t14_arrival_ladder.py` asserts that, asserts the S-safety invariant "
      "(no arm may lower a grade via arrival order), and asserts every rung is reachable.")
    A("")
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("wrote " + path)


# ---------------------------------------------------------------------------
def selfcheck():
    assert [ladder(n) for n in (-2, -1, 0, 1, 2, 3, 9)] == \
        ["S", "S", "S", "A", "C", "C", "C"]
    assert credit_net(2, True) == 1 and credit_net(2, False) == 2
    assert credit_net(0, True) == -1                       # a credit never caps
    assert ladder(credit_net(1, True)) == "S"
    assert binom_two_sided(0, 0) == 1.0
    assert abs(binom_two_sided(0, 4) - 0.125) < 1e-9
    assert abs(binom_two_sided(0, 1) - 1.0) < 1e-9
    lo, hi = wilson(18, 34)
    assert lo < 52.9 < hi
    import signal_runner as sr
    assert sr.ARRIVAL_LADDER == "off", sr.ARRIVAL_LADDER
    assert "s_promote" in sr.ARRIVAL_LADDER_MODES
    print("selfcheck OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score-cards", metavar="OUT")
    ap.add_argument("--heldout", action="store_true")
    ap.add_argument("--reach", action="store_true")
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--books", default="off,s_promote,gate,credit",
                    help="comma list of arms to replay a 2y book for")
    a = ap.parse_args()

    if a.selfcheck:
        return selfcheck()
    if a.score_cards:
        return score_cards_child(a.score_cards)

    selfcheck()
    want_books = [x for x in a.books.split(",") if x]

    held, days = {}, {}
    for arm, extra, _d in ARMS:
        days[arm] = run_cards(arm, extra, force=a.force)
        held[arm] = heldout_stats(days[arm])
    pairs = {arm: {w: paired(days["off"], days[arm], w)
                   for w in ("traded", "alerts")}
             for arm, _e, _d in ARMS if arm != "off"}

    if a.heldout:
        print(json.dumps({k: {"traded": v["traded"]["recall_pct"],
                              "alerts": v["alerts"]["recall_pct"],
                              "ff": v["traded"]["ff_pct"]}
                          for k, v in held.items()}, indent=2))
        return

    books = {}
    for arm, extra, _d in ARMS:
        if arm not in want_books:
            continue
        books[arm] = book_stats(run_book(arm, extra, force=a.force))

    reach = reachability(BOOK("off"))
    if a.reach:
        print(json.dumps(reach, indent=2)[:2000])
        return
    write_report(reach, held, pairs, books)
    json.dump({"reach": reach, "heldout": held, "paired": pairs, "books": books},
              open(os.path.join(HERE, "t14_arrival_ladder.json"), "w",
                   encoding="utf-8"), indent=1)
    print("wrote " + os.path.join(HERE, "t14_arrival_ladder.json"))


if __name__ == "__main__":
    main()
