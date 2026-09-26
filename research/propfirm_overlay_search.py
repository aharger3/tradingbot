"""propfirm_overlay_search.py -- can a followable risk overlay make OMEN's
existing trade stream pass a futures prop-firm evaluation?

Austin, 2026-09-26: "agents hunt a strategy that passes" the prop-firm trailing
drawdown; nothing is bought until one passes on paper. PR #26
(`research/propfirm_gate.py`) put 0/6 firms at PASS on the committed book at
flat $1,000/R one-trade-a-day. This script asks the next question: holding the
TRADES fixed (no new market data, no new signals), is there a sizing / daily-
stop / trade-count / grade / cooldown overlay a human or a bot could follow
that passes, and does it pass in BOTH halves of the history?

REUSED, NOT REIMPLEMENTED
  * the book loader            propfirm_gate._load_book
  * the firm rules             propfirm_gate.FIRM_RULES (the six $50k rows)
  * the PASS/FAIL simulator    omen_metrics.evaluate_prop_challenge -- every
                               start date is scored by that function, unmodified
  * the size gate              omen_metrics._row_is_sizeable (min_risk_floor)
  * the candidate stream       same construction as omen_metrics.first_of_day_arm
                               (fired-and-traded + halted rows, size-gated,
                               arrival order); selfcheck() asserts that the
                               1-trade/all-grades/no-stop overlay reproduces
                               first_of_day_arm and the gate's own all-starts
                               pass rates exactly.

THE OVERLAYS (all decidable in real time from closed trades)
  risk_$       dollars per 1R (MES = $5/pt, ES = $50/pt, so $100-$1,000 per R is
               reachable in whole micros for a 4-20 point index stop)
  grade        Austin's ladder `sgrade` (downgrade.py, measured-only): S, S+A, all
  max_trades   per day, one position at a time (a candidate whose entry minute is
               before the open trade's exit minute is skipped)
  loss_stop    stop for the day once realized day P&L <= -L R
  profit_stop  stop for the day once realized day P&L >= +P R
  skip         none | red1 (sit out the session after any red day) |
               red2 (sit out one session after two red days in a row)
  sat          stop-at-target: once equity >= target AND the consistency cap
               already holds, trade 0.1x size until the firm's minimum days are
               logged (only changes anything for firms with min_trading_days > 0)

OVERFIT GUARD
  H1 = day < 2025-09-01, H2 = day >= 2025-09-01 (the split CLAUDE.md and g174
  already use). Every start date inside a half that leaves a full HORIZON-session
  window INSIDE that half is scored; the eval never reads the other half. Pass
  rate = starts that PASS within the window / starts. An overlay COUNTS only if
  it passes >= COUNT_BAR of starts in H1 AND in H2. Per firm the reported overlay
  maximises min(H1, H2).

  THE START DATES ARE NOT INDEPENDENT. ~130 overlapping 120-session windows per
  half are about one independent eval each, so the actual-order pass rate mostly
  says "did this half's one regime run up before it ran down". Two shuffle checks
  on the chosen overlay, N_PERM permutations of the half's sessions each (the
  overlay is re-applied to the shuffled days, so cooldown rules still act):
    shuffled    same days, same drift, random order -> the pass rate a fresh
                window drawn from this half's day distribution would have
    zero-drift  the same, with the overlay's daily P&L demeaned -> what pure
                variance buys at this size. shuffled <= zero-drift means the
                stream's drift is not helping; the pass is the dice.

Run: python research/propfirm_overlay_search.py [--book PATH] [--procs N]
Writes research/propfirm_overlay_search.json; research/propfirm_overlay_search.md
is written by hand from it.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from collections import defaultdict
from itertools import product
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from omen_metrics import (evaluate_prop_challenge, first_of_day_arm,  # noqa: E402
                          _row_is_sizeable)
from propfirm_gate import (DEFAULT_BOOK, FIRM_RULES, _challenge_kwargs,  # noqa: E402
                           _load_book, all_starts_pass_rate)

SPLIT_DAY = "2025-09-01"
HORIZON = 120          # sessions per eval window (Topstep/Apex/MFFU's own max_days)
COUNT_BAR = 50.0       # % of start dates that must pass in EACH half
TOKEN = 0.1            # stop-at-target size multiplier
N_PERM = 200           # permutations per shuffle check
STAGE2_RISKS = [150, 200, 250, 300, 400, 500]
STAGE2_PERM = 40

RISKS = [100, 150, 200, 250, 300, 400, 500, 750, 1000]
GRADES = {"all": None, "S+A": ("S", "A"), "S": ("S",)}
MAX_TRADES = [1, 2, 3, 5]
LOSS_STOPS = [None, 1.0, 2.0, 3.0]
PROFIT_STOPS = [None, 1.0, 2.0, 3.0]
SKIPS = ["none", "red1", "red2"]

OUT_JSON = os.path.join(HERE, "propfirm_overlay_search.json")


# ==========================================================================
# 1. the candidate stream -- first_of_day_arm's construction, all rows kept
# ==========================================================================

def _minute(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def load_candidates(book_path):
    """(sessions, by_day, meta). by_day[day] = [(entry_min, exit_min, r, sgrade)]
    in arrival order (day, et, sym) -- the same eligibility and order as
    omen_metrics.first_of_day_arm, with the size gate applied per row."""
    rows, meta = _load_book(book_path)
    sessions = sorted({r["day"] for r in rows})
    by_day = defaultdict(list)
    for r in rows:
        if not ((r["status"] == "fired" and r.get("traded")) or r["status"] == "halted"):
            continue
        if _row_is_sizeable(r) is False:
            continue
        by_day[r["day"]].append(r)
    out = {}
    for day, v in by_day.items():
        v.sort(key=lambda r: (r["day"], r["et"], r["sym"]))
        # entry_tf is 1m for every row in this book; bars = exit_idx - entry_idx
        out[day] = [(_minute(r["et"]), _minute(r["et"]) + int(r.get("bars") or 0),
                     float(r["r"]), r.get("sgrade")) for r in v]
    return sessions, out, meta, rows


# ==========================================================================
# 2. an overlay -> one (day, pnl_R, intraday_low_R) row per session
# ==========================================================================

def _one_day(cands, grades, max_trades, loss_stop, profit_stop):
    cum = 0.0
    low = 0.0
    n = 0
    busy_until = -1
    for entry_min, exit_min, r, sg in cands:
        if grades is not None and sg not in grades:
            continue
        if entry_min < busy_until:
            continue                      # one position at a time
        cum += r
        low = min(low, cum)
        n += 1
        busy_until = exit_min
        if n >= max_trades:
            break
        if loss_stop is not None and cum <= -loss_stop:
            break
        if profit_stop is not None and cum >= profit_stop:
            break
    return cum, low, n


def build_series(sessions, by_day, spec, n_out=None):
    """spec = (grade, max_trades, loss_stop, profit_stop, skip). Returns a list
    of (day, pnl_R, low_R) -- low_R is the day's worst REALIZED running P&L
    (<= 0), which evaluate_prop_challenge uses for the daily-loss-limit check."""
    grade, max_trades, loss_stop, profit_stop, skip = spec
    grades = GRADES[grade]
    out = []
    sit_out = False
    red_streak = 0
    for day in sessions:
        if sit_out:
            out.append((day, 0.0, 0.0))
            if n_out is not None:
                n_out.append(0)
            sit_out = False
            red_streak = 0
            continue
        pnl, low, n = _one_day(by_day.get(day, []), grades, max_trades, loss_stop, profit_stop)
        out.append((day, pnl, low))
        if n_out is not None:
            n_out.append(n)
        if n:
            red_streak = red_streak + 1 if pnl < 0 else 0
            if (skip == "red1" and red_streak >= 1) or (skip == "red2" and red_streak >= 2):
                sit_out = True
    return out


def spec_name(spec):
    grade, mt, ls, ps, skip = spec
    parts = ["grade=%s" % grade, "max%d/day" % mt]
    if ls is not None:
        parts.append("stop -%gR/day" % ls)
    if ps is not None:
        parts.append("stop +%gR/day" % ps)
    if skip != "none":
        parts.append({"red1": "sit out after a red day",
                      "red2": "sit out after 2 red days"}[skip])
    return ", ".join(parts)


def all_specs():
    """Simplest specs first, so dedupe keeps the simplest name for a series."""
    specs = []
    for grade, skip in product(GRADES, SKIPS):
        specs.append((grade, 1, None, None, skip))
    for grade, mt, ls, ps, skip in product(GRADES, MAX_TRADES[1:], LOSS_STOPS,
                                           PROFIT_STOPS, SKIPS):
        specs.append((grade, mt, ls, ps, skip))
    return specs


# ==========================================================================
# 3. scoring start dates -- evaluate_prop_challenge on every window
# ==========================================================================

def _counts(pnl, low):
    """evaluate_prop_challenge's own 'is this a trading day' predicate."""
    return not (pnl == 0 and not low)


def _apply_sat(seg, rule):
    """Stop-at-target: after the first day equity >= target with the best day
    already inside the consistency cap, every later day trades at TOKEN size."""
    target = rule["profit_target_pct"] * rule["account_size"]
    cons = rule["consistency_pct"]
    eq = 0.0
    best = None
    for i, (d, p, lo) in enumerate(seg):
        if not _counts(p, lo):
            continue
        eq += p
        best = p if best is None else max(best, p)
        if eq >= target and eq > 0 and best / eq <= cons:
            return seg[:i + 1] + [(dd, pp * TOKEN, ll * TOKEN) for dd, pp, ll in seg[i + 1:]]
    return seg


def _sessions_to_pass(seg, days_traded):
    k = 0
    for i, (d, p, lo) in enumerate(seg):
        if _counts(p, lo):
            k += 1
            if k == days_traded:
                return i + 1
    return None


def score_windows(dollar_series, rule, sat, horizon=HORIZON, full_window=True):
    """(pass_pct, n_starts, sessions_to_pass list). full_window=True: only starts
    with `horizon` sessions left, each window scored on exactly those sessions.
    full_window=False with horizon=None reproduces propfirm_gate.all_starts_pass_rate
    (every start, the rest of the series, a censored start counts as a fail)."""
    kw = _challenge_kwargs(rule)
    n = len(dollar_series)
    if full_window:
        starts = range(0, n - horizon + 1)
    else:
        starts = range(n)
    passed = 0
    to_pass = []
    for s in starts:
        seg = dollar_series[s:s + horizon] if horizon else dollar_series[s:]
        if sat:
            seg = _apply_sat(seg, rule)
        res = evaluate_prop_challenge(seg, **kw)
        if res["passed"]:
            passed += 1
            to_pass.append(_sessions_to_pass(seg, res["days_traded"]))
    ns = len(starts)
    return (round(100.0 * passed / ns, 1) if ns else None), ns, to_pass


def _dollars(series_r, risk):
    return [(d, p * risk, lo * risk) for d, p, lo in series_r]


def _per_day(series_r, risk):
    return round(risk * sum(p for _, p, _ in series_r) / len(series_r), 2) if series_r else None


def _median(xs):
    return statistics.median(xs) if xs else None


# ==========================================================================
# 4. the search
# ==========================================================================

def _search_one(args):
    spec, h1, h2 = args
    out = []
    for firm, rule in FIRM_RULES.items():
        sats = (False, True) if rule["min_trading_days"] > 0 else (False,)
        for risk, sat in product(RISKS, sats):
            p1, n1, t1 = score_windows(_dollars(h1, risk), rule, sat)
            p2, n2, t2 = score_windows(_dollars(h2, risk), rule, sat)
            out.append(dict(firm=firm, spec=list(spec), risk=risk, sat=sat,
                            h1_pass=p1, h2_pass=p2, h1_starts=n1, h2_starts=n2,
                            h1_med_sessions=_median(t1), h2_med_sessions=_median(t2),
                            h1_per_day=_per_day(h1, risk), h2_per_day=_per_day(h2, risk)))
    return out


def _demean(series_r):
    traded = [p for _, p, lo in series_r if _counts(p, lo)]
    mu = sum(traded) / len(traded) if traded else 0.0
    return [(d, p - mu, lo - mu) if _counts(p, lo) else (d, p, lo) for d, p, lo in series_r]


def _shuffle_job(args):
    """Mean / p10 / p90 pass rate over N_PERM shuffles of one half's sessions."""
    firm, half, spec, risk, sat, days, cand_lists, demean, seed, n_perm = args
    rule = FIRM_RULES[firm]
    rng = random.Random(seed)
    rates = []
    for _ in range(n_perm):
        order = list(range(len(days)))
        rng.shuffle(order)
        remap = {d: cand_lists[j] for d, j in zip(days, order)}
        s = build_series(days, remap, spec)
        if demean:
            s = _demean(s)
        rates.append(score_windows(_dollars(s, risk), rule, sat)[0])
    rates.sort()
    return (firm, half, demean, round(statistics.mean(rates), 1),
            rates[len(rates) // 10], rates[(9 * len(rates)) // 10], tuple(spec), risk, sat)


def selfcheck(sessions, by_day, rows):
    """The 1-trade / all-grades / no-stop overlay must BE the gate's stream."""
    base = build_series(sessions, by_day, ("all", 1, None, None, "none"))
    arm = first_of_day_arm(rows)
    got = [(d, p) for d, p, lo in base if lo != 0.0 or p != 0.0]
    want = [(r["day"], float(r["r"])) for r in arm if float(r["r"]) != 0.0]
    assert got == want, "overlay base stream != omen_metrics.first_of_day_arm"
    gate_daily = [(r["day"], float(r["r"]) * 1000.0) for r in arm]
    mine = _dollars(base, 1000.0)
    for firm in ("Apex 50K Eval EOD", "Topstep 50K Combine"):
        rule = FIRM_RULES[firm]
        want_pct, _ = all_starts_pass_rate(gate_daily, rule)
        horizon = rule.get("max_days")
        kw = _challenge_kwargs(rule)
        passed = sum(1 for s in range(len(mine)) if evaluate_prop_challenge(
            mine[s:s + horizon] if horizon else mine[s:], **kw)["passed"])
        got_pct = round(100.0 * passed / len(mine), 1)
        assert got_pct == want_pct, (firm, got_pct, want_pct)
    return len(base)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default=DEFAULT_BOOK)
    ap.add_argument("--procs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--out", default=OUT_JSON)
    args = ap.parse_args()

    sessions, by_day, meta, rows = load_candidates(args.book)
    n = selfcheck(sessions, by_day, rows)
    print("selfcheck ok: base overlay == first_of_day_arm and gate all-starts (%d sessions)" % n)

    # dedupe overlays that produce the identical daily series
    seen = {}
    for spec in all_specs():
        s = build_series(sessions, by_day, spec)
        key = tuple((round(p, 9), round(lo, 9)) for _, p, lo in s)
        seen.setdefault(key, (spec, s))
    uniq = list(seen.values())
    print("overlays: %d specs -> %d distinct daily series" % (len(all_specs()), len(uniq)))

    jobs = []
    for spec, s in uniq:
        h1 = [x for x in s if x[0] < SPLIT_DAY]
        h2 = [x for x in s if x[0] >= SPLIT_DAY]
        jobs.append((spec, h1, h2))
    with Pool(args.procs) as pool:
        results = [row for chunk in pool.imap_unordered(_search_one, jobs, chunksize=4)
                   for row in chunk]
    print("configs scored: %d" % len(results))

    series_by_spec = {tuple(spec): s for spec, s in uniq}
    per_firm = {}
    for firm, rule in FIRM_RULES.items():
        rs = [r for r in results if r["firm"] == firm]
        for r in rs:
            r["min_pass"] = min(r["h1_pass"], r["h2_pass"])
            r["counts"] = r["h1_pass"] >= COUNT_BAR and r["h2_pass"] >= COUNT_BAR
        rs.sort(key=lambda r: (-r["min_pass"], -(r["h1_per_day"] + r["h2_per_day"]),
                               (r["h1_med_sessions"] or 1e9) + (r["h2_med_sessions"] or 1e9)))
        best = dict(rs[0])
        spec = tuple(best["spec"])
        full = series_by_spec[spec]
        h1 = [x for x in full if x[0] < SPLIT_DAY]
        h2 = [x for x in full if x[0] >= SPLIT_DAY]
        risk, sat = best["risk"], best["sat"]
        best["overlay"] = spec_name(spec) + ", $%d/R" % risk + (", stop-at-target" if sat else "")
        best["full_per_day"] = _per_day(full, risk)
        n_trades = []
        build_series(sessions, by_day, spec, n_out=n_trades)
        best["trades_per_session"] = round(sum(n_trades) / len(n_trades), 2)
        best["trades_total"] = sum(n_trades)
        # gate convention on the whole history: every start, firm max_days or rest
        gp, gn, gt = score_windows(_dollars(full, risk), rule, sat,
                                   horizon=rule.get("max_days"), full_window=False)
        best["gate_all_starts_pass"] = gp
        best["gate_all_starts_n"] = gn
        best["gate_first_day_pass"] = evaluate_prop_challenge(
            _apply_sat(_dollars(full, risk), rule) if sat else _dollars(full, risk),
            **_challenge_kwargs(rule))["passed"]
        per_firm[firm] = dict(
            best=best,
            n_configs=len(rs),
            n_counting=sum(1 for r in rs if r["counts"]),
            n_h1_only=sum(1 for r in rs if r["h1_pass"] >= COUNT_BAR),
            n_h2_only=sum(1 for r in rs if r["h2_pass"] >= COUNT_BAR),
            top5=[{k: r[k] for k in ("spec", "risk", "sat", "h1_pass", "h2_pass",
                                     "h1_per_day", "h2_per_day")} for r in rs[:5]],
            best_h1=max(r["h1_pass"] for r in rs),
            best_h2=max(r["h2_pass"] for r in rs),
        )

    # shuffle checks on each firm's chosen overlay
    halves = {"h1": [d for d in sessions if d < SPLIT_DAY],
              "h2": [d for d in sessions if d >= SPLIT_DAY]}
    jobs = []
    for i, (firm, v) in enumerate(per_firm.items()):
        b = v["best"]
        for half, days in halves.items():
            cands = [by_day.get(d, []) for d in days]
            for demean in (False, True):
                jobs.append((firm, half, tuple(b["spec"]), b["risk"], b["sat"], days, cands,
                             demean, 1000 + i, N_PERM))
    with Pool(args.procs) as pool:
        for firm, half, demean, mean, p10, p90, *_ in pool.imap_unordered(_shuffle_job, jobs):
            key = "%s_%s" % (half, "zero_drift" if demean else "shuffled")
            per_firm[firm]["best"][key] = dict(mean=mean, p10=p10, p90=p90)
    for firm, v in per_firm.items():
        b = v["best"]
        b["robust"] = bool(b["counts"] and all(
            b["%s_shuffled" % h]["mean"] >= COUNT_BAR and
            b["%s_shuffled" % h]["mean"] > b["%s_zero_drift" % h]["mean"] for h in halves))

    # stage 2 -- the i.i.d. question asked directly. Shuffled pass rate is set
    # by the stream's drift and spread, so the overlays with the best chance are
    # the ones whose mean R/session is positive in BOTH halves. Score every one
    # of them, every firm, every stage-2 size, on shuffled days.
    drift = []
    for spec, srs in uniq:
        m1 = statistics.mean(p for d, p, _ in srs if d < SPLIT_DAY)
        m2 = statistics.mean(p for d, p, _ in srs if d >= SPLIT_DAY)
        if m1 > 0 and m2 > 0:
            drift.append((spec, round(m1, 4), round(m2, 4)))
    jobs = []
    for spec, _, _ in drift:
        for firm in FIRM_RULES:
            for risk in STAGE2_RISKS:
                for half, days in halves.items():
                    jobs.append((firm, half, spec, risk, False, days,
                                 [by_day.get(d, []) for d in days], False, 7, STAGE2_PERM))
    cell = defaultdict(dict)
    with Pool(args.procs) as pool:
        for firm, half, _, mean, p10, p90, spec, risk, sat in pool.imap_unordered(
                _shuffle_job, jobs, chunksize=4):
            cell[(firm, spec, risk)][half] = mean
    stage2 = {}
    for firm in FIRM_RULES:
        cands = [(min(v["h1"], v["h2"]), v["h1"], v["h2"], spec, risk)
                 for (f, spec, risk), v in cell.items() if f == firm]
        cands.sort(key=lambda c: -c[0])
        mn, s1, s2, spec, risk = cands[0]
        actual = next(r for r in results if r["firm"] == firm and tuple(r["spec"]) == spec
                      and r["risk"] == risk and not r["sat"])
        stage2[firm] = dict(overlay=spec_name(spec) + ", $%d/R" % risk, spec=list(spec),
                            risk=risk, h1_shuffled=s1, h2_shuffled=s2,
                            clears_bar=bool(mn >= COUNT_BAR),
                            **{k: actual[k] for k in ("h1_pass", "h2_pass", "h1_med_sessions",
                                                      "h2_med_sessions", "h1_per_day",
                                                      "h2_per_day")})
    report_stage2 = dict(n_positive_drift_series=len(drift), risks=STAGE2_RISKS,
                         n_perm=STAGE2_PERM, positive_drift_series=[
                             dict(overlay=spec_name(sp), h1_r_per_session=a,
                                  h2_r_per_session=b2) for sp, a, b2 in drift],
                         best_per_firm=stage2)

    # the gate's own baseline, same windows, for the "before" column
    base = series_by_spec[("all", 1, None, None, "none")]
    bh1 = [x for x in base if x[0] < SPLIT_DAY]
    bh2 = [x for x in base if x[0] >= SPLIT_DAY]
    baseline = {firm: dict(h1_pass=score_windows(_dollars(bh1, 1000), rule, False)[0],
                           h2_pass=score_windows(_dollars(bh2, 1000), rule, False)[0])
                for firm, rule in FIRM_RULES.items()}

    report = dict(
        book=os.path.relpath(args.book, ROOT) if os.path.isabs(args.book) else args.book,
        book_sessions=meta.get("sessions"), book_first=meta.get("first"),
        book_last=meta.get("last"), split_day=SPLIT_DAY, horizon=HORIZON,
        count_bar_pct=COUNT_BAR, grid=dict(risks=RISKS, grades=list(GRADES),
                                           max_trades=MAX_TRADES, loss_stops=LOSS_STOPS,
                                           profit_stops=PROFIT_STOPS, skips=SKIPS,
                                           sat_token=TOKEN),
        n_specs=len(all_specs()), n_distinct_series=len(uniq), n_configs=len(results),
        baseline_1000_first_of_day=baseline, firms=per_firm, stage2_iid=report_stage2,
    )
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, default=str)

    print("\n%-28s %6s %6s %5s %5s %8s %8s %6s %6s %6s %6s %8s %7s" % (
        "firm", "H1%", "H2%", "medH1", "medH2", "$/d H1", "$/d H2",
        "shufH1", "shufH2", "zeroH1", "zeroH2", "count", "robust"))
    for firm, v in per_firm.items():
        b = v["best"]
        print("%-28s %6.1f %6.1f %5s %5s %8.2f %8.2f %6.1f %6.1f %6.1f %6.1f %4d/%d %7s" % (
            firm[:28], b["h1_pass"], b["h2_pass"],
            b["h1_med_sessions"], b["h2_med_sessions"], b["h1_per_day"], b["h2_per_day"],
            b["h1_shuffled"]["mean"], b["h2_shuffled"]["mean"],
            b["h1_zero_drift"]["mean"], b["h2_zero_drift"]["mean"],
            v["n_counting"], v["n_configs"], b["robust"]))
        print("    %s  (%.2f trades/session)" % (b["overlay"], b["trades_per_session"]))
    print("\nstage 2 -- %d overlays with positive mean R/session in both halves, "
          "shuffled days (%d perms):" % (len(drift), STAGE2_PERM))
    for firm, v in stage2.items():
        print("  %-28s shufH1 %5.1f  shufH2 %5.1f  clears %s  (actual order %5.1f / %5.1f, "
              "$/d %.2f / %.2f)  %s" % (
                  firm[:28], v["h1_shuffled"], v["h2_shuffled"], v["clears_bar"],
                  v["h1_pass"], v["h2_pass"], v["h1_per_day"], v["h2_per_day"], v["overlay"]))
    print("\nwrote", args.out)


if __name__ == "__main__":
    main()
