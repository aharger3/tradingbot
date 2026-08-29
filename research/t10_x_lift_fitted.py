"""T10 -- the targeted X lift, fitted to Austin's 40 veto verdicts.

THE WOUND IS THE GRADER, NOT THE DETECTOR. T1 (`research/t1_entry_minute_autopsy.md`)
measured that on Austin's 34 fresh S days the engine is never silent -- 0 of 34 --
and that where it reaches his setup its timing is exact. What it does instead is
find the trade and grade it `X`. 70,319 of the 75,953 signals in the ratified
two-year book are `X`, and `_route` skips every one of them.

TWO ARMS EXISTED AND NOBODY HAD RUN THE MIDDLE:

  off      today. 3/15 held-out S recall on the OMEN Test 1 cards.
  on_all   W1's `SAC_LADDER_REGRADE_ALL` (research/w1_sac_ladder_ab.md).
           6/15, bought with a 12.5x book of 12,770 rows and 33/42 false fires.

NOW THERE IS A LABEL SET. On 2026-08-29 Austin graded 40 of these vetoes himself
(`research/marks/probe_master_2026-08-29.jsonl`, lane `vetoes`): 5 S, 4 A, 4 C,
27 "no". S/A/C = the engine should have fired. "no" = the veto was right.

The arms are the clauses of ONE sentence of his, taken in the order he said them
(`fact_ocr_demote`): *"s trades are all about being early and the most important
thing is that clear break retest with displacement that happens quick and strong
PA entry."* They are a nested ladder, not a search over feature space -- with 13
positive labels an exhaustive conjunction search overfits by construction, and
section 4 of the report runs that search as a CONTROL to show by how much.

  br     lift only `break_and_retest`
  clean  br AND the retest is [clean], not [late]
  pa     clean AND strong PA entry ([hammer] or [disp])
  disp   pa AND the break leg displaced ([disp])
  all    lift every X -- the `on_all` control, re-run on the T0 engine

Every lift, `all` included, must clear `_min_viable_stop`. See the X_LIFT block
in signal_runner.py for why that guard is load-bearing.

Marks are READ, never written.

Usage:
    python research/t10_x_lift_fitted.py fit       # the 40 labels, no replay
    python research/t10_x_lift_fitted.py verify    # predicate == engine, row for row
    python research/t10_x_lift_fitted.py books     # 6 x 2-year replay (~10 min each)
    python research/t10_x_lift_fitted.py stats     # book stats per arm
    python research/t10_x_lift_fitted.py heldout   # 3 held-out sets x 6 arms
    python research/t10_x_lift_fitted.py report    # writes research/t10_x-lift-fitted.md
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.t0_rebaseline import stats as book_stats          # noqa: E402
from research.g13_floor_fix_ab import test1_counts, trades_digest  # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades.json")
MASTER = os.path.join(HERE, "marks", "probe_master_2026-08-29.jsonl")
MANIFEST = os.path.join(HERE, "probes", "omen-master-2026-08-28-manifest.jsonl")
OUT_MD = os.path.join(HERE, "t10_x-lift-fitted.md")
FIT_JSON = os.path.join(HERE, "_t10_fit.json")
STATS_JSON = os.path.join(HERE, "_t10_book_stats.json")
HELD_JSON = os.path.join(HERE, "_t10_heldout.json")

ARMS = ("off", "br", "clean", "pa", "disp", "all")
ARM_BOOK = {a: os.path.join(HERE, "_t10_arm_%s.json" % a) for a in ARMS}
YES = ("s", "a", "c")     # his S/A/C -- the engine should have fired
NO = "no"                 # the veto was right


# ---------------------------------------------------------------------------
# 0. shared
# ---------------------------------------------------------------------------

def rows(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def child_env(arm: str) -> dict:
    env = dict(os.environ)
    env.pop("X_LIFT", None)
    env["X_LIFT"] = arm
    return env


def wilson(hits: int, n: int):
    """95% Wilson interval for a proportion. n=0 -> (0,0)."""
    if not n:
        return (0.0, 0.0)
    z = 1.959963985
    p = hits / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


# ---------------------------------------------------------------------------
# 1. the fit -- his 40 verdicts, joined to the book rows they were drawn from
# ---------------------------------------------------------------------------

def labelled():
    """(card_id, his_grade, book_row) for every veto card, joined on the
    committed book by symbol+day+entry-time+setup, level breaking ties.

    The deck (`research/build_x_veto_deck.py`) drew from the PRE-T0 book, so the
    join is re-made against the ratified book and any card whose row cannot be
    resolved is REPORTED rather than dropped silently.
    """
    man = {r["card_id"]: r for r in rows(MANIFEST) if r.get("lane") == "vetoes"}
    marks = {r["card_id"]: r["answers"]["grade"][0].lower()
             for r in rows(MASTER)
             if r.get("lane") == "vetoes" and r["answers"].get("grade")}
    book = json.load(open(BOOK, encoding="utf-8"))["trades"]
    idx = defaultdict(list)
    for x in book:
        idx[(x["sym"], x["day"])].append(x)

    out, ambiguous = [], []
    for cid, m in sorted(man.items()):
        cand = [x for x in idx[(m["symbol"], m["date"])]
                if x["et"] == m["et"] and x["setup"] == m["setup"]]
        if len(cand) > 1:
            narrowed = [x for x in cand if x["level"] == m["level"]]
            if len(narrowed) == 1:
                cand = narrowed
            else:
                ambiguous.append([cid, len(cand)])
                cand = cand[:1]
        if not cand:
            ambiguous.append([cid, 0])
            continue
        out.append((cid, marks[cid], cand[0]))
    return out, ambiguous


def predicate(arm: str):
    """The book-row spelling of `signal_runner.x_lift_qualifies`.

    The engine reads `sig["signal_type"]` and the tags in `sig["reason"]`;
    `backtest_2y` copies exactly those two things onto every row as `setup` and
    `tags`. The fit therefore scores the SAME condition the arms run, and
    `verify_predicate()` asserts that on every row of the committed book.
    """
    def f(r):
        if arm == "off":
            return False
        if arm == "all":
            return True
        if r["setup"] != "break_and_retest":
            return False
        if arm == "br":
            return True
        t = r["tags"]
        if "clean" not in t:
            return False
        if arm == "clean":
            return True
        if "hammer" not in t and "disp" not in t:
            return False
        if arm == "pa":
            return True
        return "disp" in t
    return f


def verify_predicate():
    """The book-row predicate must agree with the engine's, row for row."""
    from omen_bot import SignalType
    import signal_runner as sr
    book = json.load(open(BOOK, encoding="utf-8"))["trades"]
    bad = n = 0
    for r in book:
        try:
            st = SignalType(r["setup"])
        except ValueError:
            continue
        sig = {"signal_type": st, "reason": r["reason"]}
        n += 1
        for arm in ARMS:
            if predicate(arm)(r) != sr.x_lift_qualifies(sig, arm):
                bad += 1
                if bad < 4:
                    print("MISMATCH %s %s %s %s" % (arm, r["sym"], r["day"], r["et"]))
    print("predicate agreement: %d mismatches over %d rows x %d arms"
          % (bad, n, len(ARMS)))
    return 1 if bad else 0


def fit_scores(lab):
    """Precision / recall of each arm over his 40 labels, plus the leave-one-out
    stability the track was asked for: how much of each arm's decision is
    carried by a single card."""
    out = {}
    n_yes = sum(1 for _, g, _ in lab if g in YES)
    n_no = sum(1 for _, g, _ in lab if g == NO)
    for arm in ARMS:
        f = predicate(arm)
        lifted = [(cid, g, r) for cid, g, r in lab if f(r)]
        tp = [x for x in lifted if x[1] in YES]
        fp = [x for x in lifted if x[1] == NO]
        prec = len(tp) / len(lifted) if lifted else 0.0
        # single-card dependence: recompute precision with each labelled card
        # removed in turn, and report the widest swing and which card causes it.
        swings = []
        for cid, g, r in lab:
            keep = [x for x in lab if x[0] != cid]
            lf = [y for y in keep if f(y[2])]
            p = (sum(1 for y in lf if y[1] in YES) / len(lf)) if lf else 0.0
            swings.append((abs(p - prec), cid, p))
        swings.sort(reverse=True)
        out[arm] = {
            "lifted": len(lifted),
            "tp": len(tp), "fp": len(fp),
            "n_yes": n_yes, "n_no": n_no,
            "recall": len(tp) / n_yes if n_yes else 0.0,
            "precision": prec,
            "false_fire_rate": len(fp) / n_no if n_no else 0.0,
            "precision_ci": wilson(len(tp), len(lifted)),
            "his_S_lifted": sum(1 for x in lifted if x[1] == "s"),
            "his_A_lifted": sum(1 for x in lifted if x[1] == "a"),
            "his_C_lifted": sum(1 for x in lifted if x[1] == "c"),
            "loo_worst_card": swings[0][1] if swings else None,
            "loo_worst_swing": swings[0][0] if swings else 0.0,
            "loo_min_precision": min(s[2] for s in swings) if swings else 0.0,
            "loo_max_precision": max(s[2] for s in swings) if swings else 0.0,
            "tp_cards": sorted(x[0] for x in tp),
            "fp_cards": sorted(x[0] for x in fp),
        }
    return out


def control_search(lab, max_terms=2):
    """THE CONTROL, not the answer. Exhaustive search over single terms and
    pairs of terms drawn from at-detection book fields, scored on the same 40
    rows. Its purpose is to show what a fitted rule can reach on 13 positives so
    the ladder's number can be read against it.

    Look-ahead fields are excluded BY NAME: `drange`, `dret`, `rangeb`, `bars`,
    `out`, `r`, `exit`, `pnl`, `scaled`, `traded`, and `spy_trend`/`vol_regime`
    (SPY context computed per day). `seq` is excluded for a different reason: it
    is arrival order within the day's skip list and is not stable under the very
    intervention being measured.
    """
    terms = []
    for f in ("setup", "level", "dir", "aligned", "stopb", "gapb", "sgrade",
              "tripped", "confluence", "cls", "pool", "slot"):
        for v in sorted({r[f] for _, _, r in lab}):
            terms.append(("%s==%s" % (f, v), (lambda f=f, v=v: lambda r: r[f] == v)()))
    for tag in ("clean", "late", "hammer", "disp", "nodisp", "brocr", "chase"):
        terms.append(("tag:%s" % tag, (lambda t=tag: lambda r: t in r["tags"])()))
        terms.append(("!tag:%s" % tag, (lambda t=tag: lambda r: t not in r["tags"])()))
    for thr in (0.05, 0.10, 0.15, 0.20, 0.30):
        terms.append(("stop_pct<%.2f" % thr,
                      (lambda t=thr: lambda r: r["stop_pct"] < t)()))
    for dg in ("level_not_respected", "counter_trend_not_respected",
               "no_displacement", "ocr_not_respected", "no_retest",
               "exhausted", "chase"):
        terms.append(("!dg:%s" % dg,
                      (lambda d=dg: lambda r: d not in (r.get("downgrades") or []))()))

    n_yes = sum(1 for _, g, _ in lab if g in YES)
    best = []
    combos = list(itertools.combinations(range(len(terms)), 1))
    if max_terms >= 2:
        combos += list(itertools.combinations(range(len(terms)), 2))
    for combo in combos:
        fs = [terms[i][1] for i in combo]
        sel = [(cid, g) for cid, g, r in lab if all(fn(r) for fn in fs)]
        if len(sel) < 5:            # a rule that lifts <5 of 40 is a card list
            continue
        tp = sum(1 for _, g in sel if g in YES)
        prec = tp / len(sel)
        rec = tp / n_yes if n_yes else 0.0
        best.append({"terms": [terms[i][0] for i in combo],
                     "n": len(sel), "tp": tp, "precision": prec, "recall": rec,
                     "f1": (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0})
    best.sort(key=lambda d: (-d["f1"], -d["precision"], -d["n"]))
    return best[:12]


def reachability():
    """Method rule 3: what fraction of the vetoed pool each arm would touch,
    BEFORE any tuning. Under 1% or over 85% and the finding is the gate."""
    book = json.load(open(BOOK, encoding="utf-8"))["trades"]
    x = [r for r in book if r["grade"] == "X"]
    out = {}
    for arm in ARMS:
        f = predicate(arm)
        n = sum(1 for r in x if f(r))
        out[arm] = {"x_rows": len(x), "lifted": n,
                    "pct": n / len(x) * 100 if x else 0.0,
                    "book_pct": n / len(book) * 100 if book else 0.0}
    return out


def cmd_fit(a):
    lab, amb = labelled()
    res = {
        "n_cards": len(lab), "ambiguous": amb,
        "label_mix": dict(Counter(g for _, g, _ in lab)),
        "still_vetoed": dict(Counter(r["status"] for _, _, r in lab)),
        "arms": fit_scores(lab),
        "control_search": control_search(lab),
        "reachability": reachability(),
        "cards": [{"card": cid, "his": g, "setup": r["setup"], "level": r["level"],
                   "tags": r["tags"], "status": r["status"], "sgrade": r["sgrade"],
                   "stop_pct": r["stop_pct"], "aligned": r["aligned"],
                   "et": r["et"], "r": r["r"]}
                  for cid, g, r in lab],
    }
    with open(FIT_JSON, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    for arm in ARMS:
        d = res["arms"][arm]
        print("%-6s lifts %2d/40  his S/A/C %2d/%d  his-no %2d/%d  precision %.2f "
              "(LOO %.2f-%.2f, worst card %s)"
              % (arm, d["lifted"], d["tp"], d["n_yes"], d["fp"], d["n_no"],
                 d["precision"], d["loo_min_precision"], d["loo_max_precision"],
                 d["loo_worst_card"]))
    print("\nreachability over the whole book (method rule 3):")
    for arm in ARMS:
        r = res["reachability"][arm]
        print("  %-6s lifts %6d of %6d X rows = %5.1f%%"
              % (arm, r["lifted"], r["x_rows"], r["pct"]))
    print("\ncontrol search top 5 (NOT the answer -- see the report):")
    for d in res["control_search"][:5]:
        print("  %-46s n=%2d tp=%2d prec=%.2f rec=%.2f"
              % (" & ".join(d["terms"]), d["n"], d["tp"], d["precision"], d["recall"]))
    print("wrote %s" % FIT_JSON)
    return 0


# ---------------------------------------------------------------------------
# 2. the books
# ---------------------------------------------------------------------------

def cmd_books(a):
    for arm in (a.arms or ARMS):
        out = ARM_BOOK[arm]
        assert "bt2y_trades.json" not in out, "never overwrite the canonical book"
        cmd = [sys.executable, os.path.join(ROOT, "backtest_2y.py"),
               "--days", str(a.days), "--out", os.path.relpath(out, ROOT)]
        print("X_LIFT=%s %s" % (arm, " ".join(cmd)), flush=True)
        rc = subprocess.call(cmd, cwd=ROOT, env=child_env(arm))
        if rc:
            return rc
    return 0


def cmd_stats(a):
    out = {}
    for arm in ARMS:
        p = ARM_BOOK[arm]
        if not os.path.exists(p):
            print("missing %s -- run `books` first" % p)
            continue
        b = json.load(open(p, encoding="utf-8"))
        s = book_stats(b["trades"])
        s["digest"] = trades_digest(b)
        for k in ("setups", "levels", "sgrade", "grade", "syms"):
            s[k] = dict(s[k])
        s["lifted_rows"] = sum(1 for r in b["trades"] if "[x-lift:" in r["reason"])
        s["lifted_traded"] = sum(1 for r in b["trades"]
                                 if "[x-lift:" in r["reason"] and r["traded"])
        lr = [r["r"] for r in b["trades"]
              if "[x-lift:" in r["reason"] and r["traded"]]
        s["lifted_mean_r"] = sum(lr) / len(lr) if lr else 0.0
        # How much of what the arm PROMOTED then died on `_min_viable_stop`.
        # A row that was lifted no longer carries grade X, so the pool the arm
        # reached is (lifted rows) + (rows still graded X that satisfy it).
        f = predicate(arm)
        still_x = sum(1 for r in b["trades"] if r["grade"] == "X" and f(r))
        s["qualified_pool"] = still_x + s["lifted_rows"]
        s["killed_by_stop_guard"] = still_x
        s["lift_survival_pct"] = (100.0 * s["lifted_rows"] / s["qualified_pool"]
                                  if s["qualified_pool"] else 0.0)
        out[arm] = s
        print("%-6s signals %6d  traded %6d  meanR %+.4f  win %.1f%%  months %d/%d"
              % (arm, s["signals"], s["traded"], s["mean_r"], s["win_rate"],
                 s["months_green"], s["months"]))
    with open(STATS_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("wrote %s" % STATS_JSON)
    return 0


# ---------------------------------------------------------------------------
# 2b. WHY a lifted card can still not fire: the stop-viability guard
# ---------------------------------------------------------------------------
#
# The fit (section 3 of the report) scores the lift CONDITION on a book row. The
# engine additionally requires `_min_viable_stop`, and nothing on a book row can
# evaluate that -- it needs the ten bars before the signal. So the fit's
# precision is an UPPER BOUND on what the arm actually does, and the gap is
# measured here rather than modelled.


def _guard_child():
    """Run inside a child with X_LIFT set. Replays each of his 40 card-days and
    records, for every signal that SATISFIES the arm's lift condition, whether
    it also cleared the stop guard. Prints one JSON line."""
    import signal_runner as sr
    import research.t4_engine_recall as t4
    pairs = json.loads(sys.argv[sys.argv.index("--pairs") + 1])
    seen = []
    orig = sr.SignalRunner._apply_x_lift

    def patched(self, sig):
        qualifies = (sr.X_LIFT != "off"
                     and sig.get("grade") in sr._SKIP_GRADES
                     and sr.x_lift_qualifies(sig, sr.X_LIFT))
        if qualifies:
            # `_min_viable_stop` is two independent clauses and they have very
            # different provenance, so they are counted separately:
            #   range  the human-proof one -- the stop may not sit inside one
            #          typical candle (0.75 x the avg range of the last 10 bars).
            #          This is what keeps a 2-cent stop out of the book.
            #   width  risk >= 0.5% of entry OR estimated premium risk >= $0.20.
            #          G4 flagged this family as tuned on a stale 12-month
            #          yfinance split, and R4 ("no minimum stop distance, size to
            #          the stop") is Austin deleting its OCR twin.
            e, st_, d = sig["entry"], sig["stop"], sig["direction"]
            risk = abs(e - st_)
            recent = self.candles[-11:-1]
            avg_range = (sum(c.high - c.low for c in recent) / len(recent)
                         if recent else 0.0)
            range_ok = bool(risk) and risk >= sr.STOP_RANGE_MULT * avg_range
            width_ok = bool(e) and (risk / e >= 0.005 or risk * 0.5 >= 0.20)
            seen.append({
                "ts": self.candles[-1].timestamp[:5],
                "setup": sig["signal_type"].value,
                "stop_ok": bool(self._min_viable_stop(e, st_, d)),
                "range_ok": range_ok, "width_ok": width_ok,
                "stop_pct": round(risk / e * 100, 4) if e else 0.0,
            })
        return orig(self, sig)

    sr.SignalRunner._apply_x_lift = patched
    out = {}
    for sym, day in pairs:
        del seen[:]
        try:
            t4.run_day(sym, day)
        except Exception as e:                       # noqa: BLE001
            out["%s_%s" % (sym, day)] = [{"error": type(e).__name__}]
            continue
        out["%s_%s" % (sym, day)] = list(seen)
    print(json.dumps(out))


def cmd_guard(a):
    lab, _ = labelled()
    pairs = sorted({(cid.rsplit("_", 1)[0], cid.rsplit("_", 1)[1])
                    for cid, _, _ in lab})
    code = ("import sys;sys.path.insert(0,%r);"
            "import research.t10_x_lift_fitted as m;m._guard_child()" % ROOT)
    res = subprocess.run([sys.executable, "-c", code, "--pairs", json.dumps(pairs)],
                         cwd=ROOT, env=child_env(a.arm),
                         capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stderr[-3000:])
        return 1
    per_day = json.loads(res.stdout.strip().splitlines()[-1])
    out = {"arm": a.arm, "cards": {}}
    for cid, g, r in lab:
        rs = [x for x in per_day.get(cid, []) if "error" not in x]
        at_bar = [x for x in rs if x.get("ts") == r["et"]]
        out["cards"][cid] = {
            "his": g, "et": r["et"],
            "qualified_on_day": len(rs),
            "stop_ok_on_day": sum(1 for x in rs if x.get("stop_ok")),
            "qualified_at_his_bar": len(at_bar),
            "stop_ok_at_his_bar": sum(1 for x in at_bar if x.get("stop_ok")),
            "range_ok_at_his_bar": sum(1 for x in at_bar if x.get("range_ok")),
            "width_ok_at_his_bar": sum(1 for x in at_bar if x.get("width_ok")),
            "stop_pct_at_his_bar": [x.get("stop_pct") for x in at_bar],
        }
    yes = [c for c in out["cards"].values() if c["his"] in YES]
    no = [c for c in out["cards"].values() if c["his"] == NO]
    out["summary"] = {
        "arm": a.arm, "his_yes": len(yes), "his_no": len(no),
        "yes_qualified_at_his_bar": sum(1 for c in yes if c["qualified_at_his_bar"]),
        "yes_stop_ok_at_his_bar": sum(1 for c in yes if c["stop_ok_at_his_bar"]),
        "yes_blocked_by_stop_guard": sum(1 for c in yes
                                         if c["qualified_at_his_bar"]
                                         and not c["stop_ok_at_his_bar"]),
        "no_qualified_at_his_bar": sum(1 for c in no if c["qualified_at_his_bar"]),
        "no_stop_ok_at_his_bar": sum(1 for c in no if c["stop_ok_at_his_bar"]),
        # which of the two clauses is the binding one, over his YES cards that
        # produce a qualifying signal at the minute he named
        "yes_range_ok": sum(1 for c in yes if c["range_ok_at_his_bar"]),
        "yes_width_ok": sum(1 for c in yes if c["width_ok_at_his_bar"]),
        "no_range_ok": sum(1 for c in no if c["range_ok_at_his_bar"]),
        "no_width_ok": sum(1 for c in no if c["width_ok_at_his_bar"]),
    }
    with open(os.path.join(HERE, "_t10_guard_%s.json" % a.arm), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out["summary"], indent=2))
    for cid, c in sorted(out["cards"].items()):
        print("  %-20s his=%-3s qual@bar=%d stop_ok@bar=%d  (day: %d qual, %d stop-ok)"
              % (cid, c["his"], c["qualified_at_his_bar"], c["stop_ok_at_his_bar"],
                 c["qualified_on_day"], c["stop_ok_on_day"]))
    return 0


# ---------------------------------------------------------------------------
# 3. the held-out sets -- reported FIRST in the report
# ---------------------------------------------------------------------------

_TEST1 = ("import json,sys;sys.path.insert(0,{root!r});"
          "import research.t70_test1_score as t70;"
          "print(json.dumps(t70.score_all(t70.load_cards())))")

_SWEEP = ("import json,sys;sys.path.insert(0,{root!r});"
          "import research.t0_heldout_recall as h;"
          "print(json.dumps({{'sweep':h.score_sweep(),'vetoes':h.score_vetoes()}}))")


def _child(code: str, arm: str):
    res = subprocess.run([sys.executable, "-c", code.format(root=ROOT)],
                         cwd=ROOT, env=child_env(arm),
                         capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stderr[-3000:])
        raise SystemExit("arm %s failed" % arm)
    return json.loads(res.stdout.strip().splitlines()[-1])


def cmd_heldout(a):
    out = {}
    if os.path.exists(HELD_JSON):
        out = json.load(open(HELD_JSON, encoding="utf-8"))
    for arm in (a.arms or ARMS):
        t1 = _child(_TEST1, arm)
        sw = _child(_SWEEP, arm)
        c = test1_counts(t1)
        out[arm] = {"test1": c, "sweep": sw["sweep"], "vetoes": sw["vetoes"]}
        print("%-6s  test1 S %d/%d  false %d/%d  |  sweep S %d/%d prec %.1f%%  |  "
              "veto S %d/%d A %d/%d C %d/%d  no %d/%d"
              % (arm, c["s_hit"], c["s_n"], c["x_fire"], c["x_n"],
                 sw["sweep"]["fired_on_S"], sw["sweep"]["n_S"],
                 sw["sweep"]["precision_pct"],
                 sw["vetoes"]["fired_on_his_S"], sw["vetoes"]["his_S"],
                 sw["vetoes"]["fired_on_his_A"], sw["vetoes"]["his_A"],
                 sw["vetoes"]["fired_on_his_C"], sw["vetoes"]["his_C"],
                 sw["vetoes"]["fired_on_his_no"], sw["vetoes"]["his_no"]))
        with open(HELD_JSON, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
    print("wrote %s" % HELD_JSON)
    return 0


# ---------------------------------------------------------------------------
# 4. the report tables
# ---------------------------------------------------------------------------

def _f(n, d):
    return "%d/%d = %.0f%%" % (n, d, (100.0 * n / d) if d else 0.0)


def _bar(a_stats, b_stats):
    se = math.sqrt(a_stats["se_r"] ** 2 + b_stats["se_r"] ** 2)
    return 1.96 * se


def build_tables(fit, st, hd):
    L = []
    P = L.append
    arms = [a for a in ARMS if a in st and a in hd]
    base = st.get("off")

    P("## 1. Held-out first (method rule 2)")
    P("")
    P("| metric | " + " | ".join("`%s`" % a for a in arms) + " |")
    P("|---|" + "---:|" * len(arms))
    P("| **Test 1 S recall** (15 S of 100) | "
      + " | ".join(_f(hd[a]["test1"]["s_hit"], hd[a]["test1"]["s_n"]) for a in arms) + " |")
    P("| Test 1 false fire on days he refused | "
      + " | ".join(_f(hd[a]["test1"]["x_fire"], hd[a]["test1"]["x_n"]) for a in arms) + " |")
    P("| Test 1 day precision | "
      + " | ".join(_f(hd[a]["test1"]["day_prec_hit"], hd[a]["test1"]["day_prec_n"])
                   for a in arms) + " |")
    P("| **S-sweep recall** (34 S of 100) | "
      + " | ".join(_f(hd[a]["sweep"]["fired_on_S"], hd[a]["sweep"]["n_S"]) for a in arms) + " |")
    P("| S-sweep precision | "
      + " | ".join("%.1f%%" % hd[a]["sweep"]["precision_pct"] for a in arms) + " |")
    P("| veto lane: his 5 S | "
      + " | ".join(_f(hd[a]["vetoes"]["fired_on_his_S"], hd[a]["vetoes"]["his_S"]) for a in arms) + " |")
    P("| veto lane: his 4 A | "
      + " | ".join(_f(hd[a]["vetoes"]["fired_on_his_A"], hd[a]["vetoes"]["his_A"]) for a in arms) + " |")
    P("| veto lane: his 4 C | "
      + " | ".join(_f(hd[a]["vetoes"]["fired_on_his_C"], hd[a]["vetoes"]["his_C"]) for a in arms) + " |")
    P("| **veto lane: his 27 `no`** (false fire) | "
      + " | ".join(_f(hd[a]["vetoes"]["fired_on_his_no"], hd[a]["vetoes"]["his_no"]) for a in arms) + " |")
    P("")
    P("## 2. The book")
    P("")
    P("| figure | " + " | ".join("`%s`" % a for a in arms) + " |")
    P("|---|" + "---:|" * len(arms))
    for lab, key, fmt in (("signals detected", "signals", "%d"),
                          ("**traded**", "traded", "%d"),
                          ("**mean R**", "mean_r", "%+.4f"),
                          ("total R", "total_r", "%+.1f"),
                          ("**win rate**", "win_rate", "%.1f%%"),
                          ("profit factor", "pf", "%.4f"),
                          ("max drawdown (R)", "max_dd_r", "%.2f"),
                          ("worst trade (R)", "worst_r", "%.3f"),
                          ("best trade (R)", "best_r", "%.1f"),
                          ("signals the arm's condition reached", "qualified_pool", "%d"),
                          ("of those, killed by `_min_viable_stop`", "killed_by_stop_guard", "%d"),
                          ("**survival of the lift**", "lift_survival_pct", "%.1f%%"),
                          ("rows carrying `[x-lift:]`", "lifted_rows", "%d"),
                          ("mean R of the lifted traded rows", "lifted_mean_r", "%+.4f")):
        P("| %s | " % lab + " | ".join(fmt % st[a][key] for a in arms) + " |")
    P("| months green | "
      + " | ".join("%d/%d" % (st[a]["months_green"], st[a]["months"]) for a in arms) + " |")
    if base:
        P("| mean-R move vs `off` | "
          + " | ".join(("%+.4f" % (st[a]["mean_r"] - base["mean_r"])) for a in arms) + " |")
        P("| its own 95% bar | "
          + " | ".join(("+/-%.4f" % _bar(base, st[a])) for a in arms) + " |")
        P("| clears its bar? | "
          + " | ".join(("yes" if abs(st[a]["mean_r"] - base["mean_r"]) > _bar(base, st[a])
                        else "**no -- null**") for a in arms) + " |")
    P("")
    P("## 3. The fit on his 40 verdicts")
    P("")
    P("| arm | lifts | his S/A/C caught | his 27 `no` lifted | precision | 95% CI | "
      "leave-one-out precision range |")
    P("|---|---:|---:|---:|---:|---|---|")
    for a in ARMS:
        d = fit["arms"][a]
        P("| `%s` | %d/40 | %d/%d | %d/%d | %.0f%% | [%.0f%%, %.0f%%] | %.0f%%-%.0f%% "
          "(widest single-card swing: `%s`) |"
          % (a, d["lifted"], d["tp"], d["n_yes"], d["fp"], d["n_no"],
             100 * d["precision"], 100 * d["precision_ci"][0], 100 * d["precision_ci"][1],
             100 * d["loo_min_precision"], 100 * d["loo_max_precision"],
             d["loo_worst_card"]))
    P("")
    P("## 4. Reachability (method rule 3, checked BEFORE tuning)")
    P("")
    P("| arm | X rows lifted | of the %d vetoes | of the whole book |"
      % fit["reachability"]["off"]["x_rows"])
    P("|---|---:|---:|---:|")
    for a in ARMS:
        r = fit["reachability"][a]
        P("| `%s` | %d | %.1f%% | %.1f%% |" % (a, r["lifted"], r["pct"], r["book_pct"]))
    P("")
    P("## 5. The control search -- what a FITTED rule reaches on 13 positives")
    P("")
    P("| rank | terms | n lifted | his S/A/C | precision | recall |")
    P("|---:|---|---:|---:|---:|---:|")
    for i, d in enumerate(fit["control_search"], 1):
        P("| %d | `%s` | %d | %d | %.0f%% | %.0f%% |"
          % (i, " & ".join(d["terms"]), d["n"], d["tp"],
             100 * d["precision"], 100 * d["recall"]))
    P("")
    P("## 6. Every card, with the arm that lifts it")
    P("")
    P("| card | his | setup | level | tags | stop% | deepest arm that lifts it |")
    P("|---|---|---|---|---|---:|---|")
    for c in sorted(fit["cards"], key=lambda c: (c["his"], c["card"])):
        r = {"setup": c["setup"], "tags": c["tags"]}
        deepest = "-"
        for a in ("br", "clean", "pa", "disp"):
            if predicate(a)(r):
                deepest = a
        P("| `%s` | **%s** | %s | %s | %s | %.3f | %s |"
          % (c["card"], c["his"].upper(), c["setup"][:16], c["level"],
             ",".join(c["tags"]), c["stop_pct"], deepest))
    P("")
    return "\n".join(L)


def cmd_report(a):
    fit = json.load(open(FIT_JSON, encoding="utf-8"))
    st = json.load(open(STATS_JSON, encoding="utf-8"))
    hd = json.load(open(HELD_JSON, encoding="utf-8"))
    body = build_tables(fit, st, hd)
    print(body)
    with open(os.path.join(HERE, "_t10_tables.md"), "w", encoding="utf-8") as fh:
        fh.write(body + "\n")
    print("\nwrote research/_t10_tables.md -- paste into %s" % OUT_MD)
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fit"); p.set_defaults(fn=cmd_fit)
    p = sub.add_parser("verify"); p.set_defaults(fn=lambda a: verify_predicate())
    p = sub.add_parser("books"); p.set_defaults(fn=cmd_books)
    p.add_argument("--days", type=int, default=730)
    p.add_argument("--arms", nargs="*")
    p = sub.add_parser("stats"); p.set_defaults(fn=cmd_stats)
    p = sub.add_parser("guard"); p.set_defaults(fn=cmd_guard)
    p.add_argument("--arm", default="clean")
    p = sub.add_parser("heldout"); p.set_defaults(fn=cmd_heldout)
    p.add_argument("--arms", nargs="*")
    p = sub.add_parser("report"); p.set_defaults(fn=cmd_report)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
