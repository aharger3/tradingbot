"""edge_slices.py -- is there ANY subset of OMEN's existing signals with a
real, stable edge?

Austin, 2026-09-26: "agents hunt a strategy that passes" the prop-firm drawdown;
nothing is bought until one passes on paper. PR #27
(`research/propfirm_overlay_search.py`) found no sizing/stop overlay passes
robustly: pass rates collapse under day-shuffle to a zero-drift baseline. So
the question moves from risk management to the edge itself: is there a slice
of the trades already in the committed book whose average R is positive,
significantly better than chance, and stable across both halves?

THE BOOK. The same committed book and the same candidate stream PR #26/#27
use: `research/bt2y_trades_retest_on.json.gz` (RETEST_REQUIRED=1, 498
sessions, 2024-09-03 -> 2026-09-02), fired-and-traded plus halted rows,
size-gated through `omen_metrics._row_is_sizeable`. Every candidate is kept
(not just first-of-day); each trade's own R is the unit. `check_stream()`
asserts this population is exactly `propfirm_overlay_search.load_candidates`.

THE SLICES (every dimension decidable before the entry, no same-day lookahead)
  grade     Austin's `sgrade` ladder: S, A, C, and S+A
  setup     break_and_retest / one_candle_rule / reentry_84_rule
  sym       28 symbols
  tod       15-minute entry bucket, 09:30 .. 10:45
  dow       day of week
  dir       call / put
  htf       the book's `aligned`: 1h close vs SMA20 of 1h closes BEFORE the
            session (backtest_week.htf_bias_for), with / against / neutral
  mkt       with / against the PRIOR session's SPY 20-day trend
  spyvol    the PRIOR session's SPY realized-vol tercile (calm/normal/wild)
  symrange  the symbol's PRIOR session range (quiet <1.5%, normal <3%, big)
  gap       the day's opening gap bucket (flat / small / big), known at 09:30
Excluded as same-day lookahead: `rangeb`/`drange`/`dret` (the full session's
range and return) and same-day `spy_trend`/`vol_regime` (both use that day's
16:00 SPY close, backtest_2y.spy_context). The vol terciles' cut points are
full-sample -- a mild threshold lookahead, flagged, not fixed.

Singles plus every 2-dimension combination (max 2 filters, the data-mining
guard), kept only if n >= N_MIN trades. Each slice is ONE test in the family.

THE STATISTICS
  n, days, avg R, win rate (R > 0), profit factor (sum wins / |sum losses|),
  and the same for H1 (day < 2025-09-01) and H2.
  perm_p   one-sided permutation p for the slice's avg R: shuffle R across all
           N trades of the book (N_PERM reps), recompute the slice mean, count
           reps >= observed. p = (1 + count) / (1 + N_PERM). The null is "this
           slice is a random draw from the book" -- its centre is the BOOK's
           mean (-0.035R), not zero.
  bh_q     Benjamini-Hochberg adjusted p across every slice tested.
  day_t    avg R / its day-clustered standard error -- a t against ZERO that
           does not treat 14 same-day trades as 14 independent draws. The
           permutation test does, so day_t is the sanity check on it.
  SURVIVES = bh_q <= Q  AND  avg R > 0  AND  avg R > 0 in H1 AND in H2.

THE GATE, top 3 survivors (or, if none survive, the 3 lowest-p slices,
labelled as not surviving). Reused, not reimplemented:
  * propfirm_gate.gate_series -- PR #26's gate, first-of-day in the slice,
    $1,000/R, every firm, first-day PASS and all-starts pass rate
  * propfirm_overlay_search.build_series / score_windows / _shuffle_job --
    PR #27's per-half real-order pass rate, day-shuffle and zero-drift checks,
    over a small overlay grid (max 1/2/3 trades a day, no stop or a -1R day
    stop, STAGE2_RISKS) chosen per firm by min(shuffled H1, shuffled H2).
    ROBUST = shuffled >= 50% in both halves AND shuffled > zero-drift in both.

Run: python3 research/edge_slices.py [--procs N] [--perm N]
Writes research/edge_slices.json; research/edge_slices_2026-09-26.md is
written by hand from it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from itertools import combinations, product
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import propfirm_overlay_search as pos  # noqa: E402
from omen_metrics import _row_is_sizeable  # noqa: E402
from propfirm_gate import DEFAULT_BOOK, FIRM_RULES, _load_book, gate_series  # noqa: E402

SPLIT_DAY = pos.SPLIT_DAY
N_MIN = 50             # smallest slice tested
N_PERM = 100_000       # permutation reps (min p ~ 1e-5, below BH's rank-1 bar)
CHUNK = 2_500          # permutations per matmul block
SEED = 20260926
Q = 0.05               # BH false-discovery rate
GATE_SPECS = [("all", mt, ls, None, "none") for mt in (1, 2, 3) for ls in (None, 1.0)]
GATE_ZERO_PERM = 200   # zero-drift / shuffle reps for each firm's chosen config

OUT_JSON = os.path.join(HERE, "edge_slices.json")

SETUP_SHORT = {"break_and_retest": "BR", "one_candle_rule": "OCR", "reentry_84_rule": "84"}


# ==========================================================================
# 1. the population and its pre-entry features
# ==========================================================================

def _tod(et):
    h, m = (int(x) for x in et.split(":")[:2])
    start = (h * 60 + m) // 15 * 15
    return "%02d:%02d" % (start // 60, start % 60)


def _range_bucket(drange):
    if drange is None:
        return "n/a"
    return "quiet" if drange < 1.5 else "normal" if drange < 3.0 else "big"


def load_population(book):
    rows, meta = _load_book(book)
    sessions = sorted({r["day"] for r in rows})
    prev = {d: (sessions[i - 1] if i else None) for i, d in enumerate(sessions)}
    day_ctx, sym_range = {}, {}
    for r in rows:
        ctx = (r.get("spy_trend"), r.get("vol_regime"))
        if day_ctx.setdefault(r["day"], ctx) != ctx:
            raise ValueError("inconsistent SPY context on %s" % r["day"])
        sym_range.setdefault((r["sym"], r["day"]), r.get("drange"))
    pop = [r for r in rows
           if ((r["status"] == "fired" and r.get("traded")) or r["status"] == "halted")
           and _row_is_sizeable(r) is not False]
    pop.sort(key=lambda r: (r["day"], r["et"], r["sym"]))
    feats = []
    for r in pop:
        pd = prev[r["day"]]
        spy_trend, spy_vol = day_ctx.get(pd, (None, None)) if pd else (None, None)
        mkt = ("n/a" if spy_trend not in ("bull", "bear") else
               "with" if (spy_trend == "bull") == (r["dir"] == "call") else "against")
        feats.append(dict(
            grade=r.get("sgrade"),
            setup=SETUP_SHORT.get(r["setup"], r["setup"]),
            sym=r["sym"],
            tod=_tod(r["et"]),
            dow=r["dow"],
            dir=r["dir"],
            htf={"with": "with", "against": "against"}.get(r.get("aligned"), "neutral"),
            mkt=mkt,
            spyvol=spy_vol if spy_vol in ("calm", "normal", "wild") else "n/a",
            symrange=_range_bucket(sym_range.get((r["sym"], pd))) if pd else "n/a",
            gap=r.get("gapb") or "n/a",
        ))
    return rows, meta, sessions, pop, feats


def check_stream(book, sessions, pop):
    """The population must BE propfirm_overlay_search's candidate stream."""
    s2, by_day, _, _ = pos.load_candidates(book)
    assert s2 == sessions, "session list differs from propfirm_overlay_search"
    mine = by_day_of(pop, [True] * len(pop))
    assert dict(mine) == by_day, "population != propfirm_overlay_search.load_candidates"
    return sum(len(v) for v in by_day.values())


def by_day_of(pop, mask):
    out = defaultdict(list)
    for r, m in zip(pop, mask):
        if m:
            em = pos._minute(r["et"])
            out[r["day"]].append((em, em + int(r.get("bars") or 0), float(r["r"]), r.get("sgrade")))
    return out


# ==========================================================================
# 2. the slice family
# ==========================================================================

DIMS = ["grade", "setup", "sym", "tod", "dow", "dir", "htf", "mkt", "spyvol", "symrange", "gap"]


def dim_levels(feats):
    lv = {}
    for d in DIMS:
        vals = sorted({f[d] for f in feats})
        lv[d] = [(v, np.array([f[d] == v for f in feats])) for v in vals]
    g = np.array([f["grade"] in ("S", "A") for f in feats])
    lv["grade"].append(("S+A", g))
    return lv


def build_slices(feats, n_min):
    lv = dim_levels(feats)
    names, masks = [], []
    for d in DIMS:
        for v, m in lv[d]:
            if m.sum() >= n_min:
                names.append("%s=%s" % (d, v))
                masks.append(m)
    for d1, d2 in combinations(DIMS, 2):
        for (v1, m1), (v2, m2) in product(lv[d1], lv[d2]):
            m = m1 & m2
            if m.sum() >= n_min:
                names.append("%s=%s & %s=%s" % (d1, v1, d2, v2))
                masks.append(m)
    return names, np.array(masks).T          # N x S


# ==========================================================================
# 3. statistics
# ==========================================================================

def _pf(r):
    w = r[r > 0].sum()
    lo = -r[r < 0].sum()
    return round(float(w / lo), 3) if lo > 0 else None


def describe(r, h1, days, mask):
    rs = r[mask]
    out = dict(n=int(mask.sum()), days=int(len(set(days[mask]))),
               avg_r=round(float(rs.mean()), 4), win=round(float((rs > 0).mean()) * 100, 1),
               pf=_pf(rs))
    for tag, hm in (("h1", h1), ("h2", ~h1)):
        x = r[mask & hm]
        out[tag + "_n"] = int(len(x))
        out[tag + "_avg_r"] = round(float(x.mean()), 4) if len(x) else None
        out[tag + "_pf"] = _pf(x) if len(x) else None
    return out


def perm_pvalues(r, M, n_perm, seed):
    """One-sided permutation p for every slice at once: R shuffled across all
    trades, each slice's mean recomputed, reps >= observed counted."""
    n = M.sum(axis=0)
    W = M / n                                  # N x S, column = slice-mean weights
    obs = r @ W
    count = np.zeros(M.shape[1], dtype=np.int64)
    rng = np.random.default_rng(seed)
    done = 0
    while done < n_perm:
        k = min(CHUNK, n_perm - done)
        P = rng.permuted(np.broadcast_to(r, (k, len(r))), axis=1)
        count += (P @ W >= obs - 1e-12).sum(axis=0)
        done += k
    return (1 + count) / (1 + n_perm), obs


def bh(p):
    """Benjamini-Hochberg adjusted p-values (q), monotone, capped at 1."""
    p = np.asarray(p)
    m = len(p)
    order = np.argsort(p)
    q = p[order] * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(q, 1.0)
    return out


def day_clustered_t(r, day_idx, n_days, M):
    """avg R / day-clustered SE, per slice (t against zero)."""
    D = np.zeros((n_days, len(r)))
    D[day_idx, np.arange(len(r))] = 1.0
    S = D @ (M * r[:, None])
    C = D @ M
    n = M.sum(axis=0)
    mean = S.sum(axis=0) / n
    resid = S - C * mean
    g = (C > 0).sum(axis=0)
    var = (resid ** 2).sum(axis=0) / n ** 2 * g / np.maximum(g - 1, 1)
    return mean / np.sqrt(var)


# ==========================================================================
# 4. the prop-firm gate on a slice -- PR #26 and PR #27 code, reused
# ==========================================================================

def gate_slice(name, sessions, bd, procs):
    base = pos.build_series(sessions, bd, ("all", 1, None, None, "none"))
    g26 = gate_series(pos._dollars(base, 1000.0))
    pr26 = {f: dict(first_day_pass=v["passed"], all_starts_pass_pct=v["all_starts_pass_pct"])
            for f, v in g26.items()}

    halves = {"h1": [d for d in sessions if d < SPLIT_DAY],
              "h2": [d for d in sessions if d >= SPLIT_DAY]}
    jobs = []
    for firm in FIRM_RULES:
        for spec, risk in product(GATE_SPECS, pos.STAGE2_RISKS):
            for half, days in halves.items():
                jobs.append((firm, half, spec, risk, False, days,
                             [bd.get(d, []) for d in days], False, 7, pos.STAGE2_PERM))
    cell = defaultdict(dict)
    with Pool(procs) as pool:
        for firm, half, _, mean, _, _, spec, risk, _ in pool.imap_unordered(
                pos._shuffle_job, jobs, chunksize=4):
            cell[(firm, spec, risk)][half] = mean

    pr27 = {}
    zjobs = []
    for i, firm in enumerate(FIRM_RULES):
        cands = sorted(((min(v["h1"], v["h2"]), spec, risk) for (f, spec, risk), v in cell.items()
                        if f == firm), key=lambda c: -c[0])
        _, spec, risk = cands[0]
        series = pos.build_series(sessions, bd, spec)
        h1 = [x for x in series if x[0] < SPLIT_DAY]
        h2 = [x for x in series if x[0] >= SPLIT_DAY]
        rule = FIRM_RULES[firm]
        pr27[firm] = dict(overlay=pos.spec_name(spec) + ", $%d/R" % risk, spec=list(spec),
                          risk=risk,
                          h1_real=pos.score_windows(pos._dollars(h1, risk), rule, False)[0],
                          h2_real=pos.score_windows(pos._dollars(h2, risk), rule, False)[0],
                          h1_per_day=pos._per_day(h1, risk), h2_per_day=pos._per_day(h2, risk))
        for half, days in halves.items():
            for demean in (False, True):
                zjobs.append((firm, half, spec, risk, False, days,
                              [bd.get(d, []) for d in days], demean, 1000 + i, GATE_ZERO_PERM))
    with Pool(procs) as pool:
        for firm, half, demean, mean, p10, p90, *_ in pool.imap_unordered(pos._shuffle_job, zjobs):
            pr27[firm]["%s_%s" % (half, "zero_drift" if demean else "shuffled")] = mean
    for v in pr27.values():
        v["robust"] = bool(all(v["%s_shuffled" % h] >= pos.COUNT_BAR and
                               v["%s_shuffled" % h] > v["%s_zero_drift" % h] for h in halves))
    return dict(slice=name, pr26_first_of_day_1000=pr26, pr27_iid=pr27)


# ==========================================================================
# 5. main
# ==========================================================================

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default=DEFAULT_BOOK)
    ap.add_argument("--procs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--perm", type=int, default=N_PERM)
    ap.add_argument("--out", default=OUT_JSON)
    args = ap.parse_args()

    rows, meta, sessions, pop, feats = load_population(args.book)
    n_stream = check_stream(args.book, sessions, pop)
    print("stream check ok: %d trades == propfirm_overlay_search.load_candidates" % n_stream)

    r = np.array([float(x["r"]) for x in pop])
    days = np.array([x["day"] for x in pop])
    h1 = days < SPLIT_DAY
    day_list = sorted(set(days))
    day_idx = np.searchsorted(day_list, days)

    names, M = build_slices(feats, N_MIN)
    Mf = M.astype(np.float64)
    print("slices tested: %d (n >= %d; singles + 2-filter combos)" % (len(names), N_MIN))

    p, obs = perm_pvalues(r, Mf, args.perm, SEED)
    q = bh(p)
    t = day_clustered_t(r, day_idx, len(day_list), Mf)

    table = []
    for j, name in enumerate(names):
        d = describe(r, h1, days, M[:, j])
        d.update(slice=name, filters=name.count("&") + 1, perm_p=float(p[j]),
                 bh_q=round(float(q[j]), 5), day_t=round(float(t[j]), 2))
        d["stable"] = bool(d["avg_r"] > 0 and (d["h1_avg_r"] or 0) > 0 and (d["h2_avg_r"] or 0) > 0)
        d["survives"] = bool(d["bh_q"] <= Q and d["stable"])
        table.append(d)
    table.sort(key=lambda d: (d["perm_p"], -d["avg_r"]))

    book_row = describe(r, h1, days, np.ones(len(r), dtype=bool))
    survivors = [d for d in table if d["survives"]]
    n_q05 = sum(1 for d in table if d["bh_q"] <= 0.05)
    n_q10 = sum(1 for d in table if d["bh_q"] <= 0.10)
    n_stable = sum(1 for d in table if d["stable"])
    n_nominal = sum(1 for d in table if d["perm_p"] <= 0.05)
    # the permutation null centres on the BOOK mean; pass on to zero as well
    n_nominal_pos = sum(1 for d in table if d["perm_p"] <= 0.05 and d["avg_r"] > 0)

    picked = survivors[:3] if survivors else table[:3]
    gates = []
    for d in picked:
        j = names.index(d["slice"])
        bd = by_day_of(pop, M[:, j])
        print("gating %s ..." % d["slice"])
        g = gate_slice(d["slice"], sessions, bd, args.procs)
        g["survived_bh"] = d["survives"]
        gates.append(g)

    report = dict(
        book=os.path.relpath(args.book, ROOT) if os.path.isabs(args.book) else args.book,
        book_sessions=meta.get("sessions"), book_first=meta.get("first"),
        book_last=meta.get("last"), split_day=SPLIT_DAY, n_trades=len(r),
        n_min=N_MIN, n_perm=args.perm, seed=SEED, bh_fdr=Q, dims=DIMS,
        n_slices=len(names), n_singles=sum(1 for d in table if d["filters"] == 1),
        n_pairs=sum(1 for d in table if d["filters"] == 2),
        book_row=book_row, n_nominal_p05=n_nominal, n_nominal_p05_positive=n_nominal_pos,
        n_bh_q05=n_q05, n_bh_q10=n_q10, n_stable=n_stable, n_survivors=len(survivors),
        survivors=survivors, gated_from="survivors" if survivors else "lowest-p (none survived)",
        gates=gates, slices=table,
    )
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, default=str)

    print("\nbook: n=%d avgR=%+.4f win=%.1f%% pf=%s  H1 %+.4f  H2 %+.4f" % (
        book_row["n"], book_row["avg_r"], book_row["win"], book_row["pf"],
        book_row["h1_avg_r"], book_row["h2_avg_r"]))
    print("slices %d | nominal p<=.05: %d (%d with avgR>0) | BH q<=.05: %d | q<=.10: %d | "
          "stable both halves: %d | SURVIVE: %d" % (
              len(names), n_nominal, n_nominal_pos, n_q05, n_q10, n_stable, len(survivors)))
    hdr = "%-44s %5s %5s %8s %6s %6s %8s %8s %9s %8s %6s %s"
    print("\n" + hdr % ("slice (lowest p first)", "n", "days", "avgR", "win%", "PF", "H1 R",
                        "H2 R", "perm_p", "bh_q", "day_t", "stable"))
    for d in table[:30]:
        print(hdr % (d["slice"][:44], d["n"], d["days"], "%+.3f" % d["avg_r"], d["win"], d["pf"],
                     "%+.3f" % d["h1_avg_r"], "%+.3f" % d["h2_avg_r"], "%.2e" % d["perm_p"],
                     "%.3f" % d["bh_q"], d["day_t"], d["stable"]))
    for g in gates:
        print("\nGATE %s (survived BH: %s)" % (g["slice"], g["survived_bh"]))
        for firm, v in g["pr26_first_of_day_1000"].items():
            w = g["pr27_iid"][firm]
            print("  %-30s PR26 first-day %-5s all-starts %5s%% | PR27 %s: real %5.1f/%5.1f "
                  "shuf %5.1f/%5.1f zero %5.1f/%5.1f $/d %.2f/%.2f robust %s" % (
                      firm[:30], v["first_day_pass"], v["all_starts_pass_pct"], w["overlay"],
                      w["h1_real"], w["h2_real"], w["h1_shuffled"], w["h2_shuffled"],
                      w["h1_zero_drift"], w["h2_zero_drift"], w["h1_per_day"], w["h2_per_day"],
                      w["robust"]))
    print("\nwrote", args.out)


if __name__ == "__main__":
    main()
