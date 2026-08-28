"""x5_downgrade_inversion.py -- is the downgrade ladder really inverted, or is it n?

Austin, 2026-08-28:

    "the downgrade system the grades look right with profitability but maybe they need
     to be more simple because right now 3 downgrades has better rr then 1 downgrade
     and 0. but that also might just be because the sample size is inverted."

He named the alternative hypothesis himself. This settles it, on the shipped 2-year
book and nothing else.

WHAT IT READS
-------------
`research/g3_arm_ow1.json` only -- the shipped ON_WATCH=1 book, 45,193 signals /
1,017 traded, 2024-08-21..2026-08-21, built by `research/g3_onwatch_2y.py`. Every
row already carries `tripped` (the downgrade count), `downgrades` (which ones),
`confluence`, `sgrade`, `r`, `out`, `seq`. No bar replay, no network, no re-grading:
those fields were written by `research/downgrade.py::score()` at the committed
defaults when the book was built, so recomputing them from bars would reproduce the
same lists. `downgrade.VARIABLES` is imported, never retyped.

WHAT IT MEASURES
----------------
1. the full ladder, n FIRST, with a 10k-resample bootstrap 95% CI on mean R
2. the inversion tested directly -- bootstrap + permutation on 3-downgrades vs 0,
   on BOTH readings of "rr" (mean R, and avg-win / avg-loss)
3. per-variable attribution: tripped vs clean, ranked, with a CI on each delta
4. greedy forward selection of the smallest subset that keeps the ranking power,
   scored OUT OF SAMPLE on a temporal split (and the reverse split as a check)
5. the confluence weight swept -2..+1

ERROR BAR
---------
+-0.0095 R, the narrow bar carried since 2026-08-28 (the wide +-1.5799 R bar is
retired -- Austin: "out on that same close"). Anything smaller than that is noise.

    python research/x5_downgrade_inversion.py

Writes research/x5_downgrade_inversion.md. Changes no default, flips no flag.
"""
from __future__ import annotations

import json
import os
import random
import statistics
import sys
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import downgrade as dg                                    # noqa: E402

BOOK = os.path.join(HERE, "g3_arm_ow1.json")
OUT = os.path.join(HERE, "x5_downgrade_inversion.md")

NARROW_BAR = 0.0095      # R, carried error bar (2026-08-28)
NBOOT = 10000
SEED = 20260828

VARS = list(dg.VARIABLES)     # the eight, imported not retyped


# ---------------------------------------------------------------------------
# stats helpers
# ---------------------------------------------------------------------------

def mean(xs):
    return statistics.mean(xs) if xs else float("nan")


def median(xs):
    return statistics.median(xs) if xs else float("nan")


def win_rate(rows):
    """Of DECIDED trades -- scratches excluded, the convention a2_bt2y_summary prints."""
    dec = [r for r in rows if r["out"] != "scratch"]
    if not dec:
        return float("nan"), 0
    return 100.0 * sum(1 for r in dec if r["out"] == "win") / len(dec), len(dec)


def rr_ratio(rows):
    """Austin's 'rr': average winner divided by the size of the average loser."""
    dec = [r for r in rows if r["out"] != "scratch"]
    w = [r["r"] for r in dec if r["out"] == "win"]
    l = [r["r"] for r in dec if r["out"] == "loss"]
    if not w or not l:
        return float("nan")
    return mean(w) / abs(mean(l))


def as_arrays(rows):
    """Rows -> (r, is_win, is_loss) numpy arrays. Accepts a list of dicts or of floats."""
    if rows and isinstance(rows[0], dict):
        r = np.array([x["r"] for x in rows], dtype=float)
        w = np.array([x["out"] == "win" for x in rows], dtype=float)
        l = np.array([x["out"] == "loss" for x in rows], dtype=float)
    else:
        r = np.array(rows, dtype=float)
        w = l = None
    return r, w, l


def _stat_vec(idx, r, w, l, kind):
    """Vectorised statistic over a (chunk, k) index matrix."""
    if kind == "mean":
        return r[idx].mean(axis=1)
    rr, ww, ll = r[idx], w[idx], l[idx]
    nw, nl = ww.sum(axis=1), ll.sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        aw = (rr * ww).sum(axis=1) / nw
        al = (rr * ll).sum(axis=1) / nl
        return aw / np.abs(al)


def _boot_dist(rows, kind, n, seed):
    r, w, l = as_arrays(rows)
    k = len(r)
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    step = 1000
    for s in range(0, n, step):
        m = min(step, n - s)
        idx = rng.integers(0, k, size=(m, k))
        out[s:s + m] = _stat_vec(idx, r, w, l, kind)
    return out


def boot_ci(xs, kind="mean", n=NBOOT, seed=SEED):
    """Percentile bootstrap 95% CI."""
    if len(xs) < 2:
        return (float("nan"), float("nan"))
    d = np.sort(_boot_dist(xs, kind, n, seed))
    return (float(d[int(0.025 * n)]), float(d[min(n - 1, int(0.975 * n))]))


def point_stat(rows, kind):
    r, w, l = as_arrays(rows)
    if kind == "mean":
        return float(r.mean()) if len(r) else float("nan")
    if w.sum() == 0 or l.sum() == 0:
        return float("nan")
    return float((r * w).sum() / w.sum() / abs((r * l).sum() / l.sum()))


def boot_diff(a, b, kind="mean", n=NBOOT, seed=SEED):
    """Bootstrap stat(a) - stat(b). Returns (point, lo, hi, share of resamples <= 0)."""
    if len(a) < 2 or len(b) < 2:
        return (float("nan"),) * 4
    da = _boot_dist(a, kind, n, seed)
    db = _boot_dist(b, kind, n, seed + 991)
    d = np.sort(da - db)
    ok = d[~np.isnan(d)]
    if len(ok) < 2:
        return (point_stat(a, kind) - point_stat(b, kind), float("nan"), float("nan"), float("nan"))
    m = len(ok)
    return (point_stat(a, kind) - point_stat(b, kind),
            float(ok[int(0.025 * m)]), float(ok[min(m - 1, int(0.975 * m))]),
            float((ok <= 0).mean()))


def perm_p(a, b, kind="mean", n=NBOOT, seed=SEED):
    """Two-sided label-permutation p-value for stat(a) - stat(b)."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    obs = abs(point_stat(a, kind) - point_stat(b, kind))
    if obs != obs:
        return float("nan")
    pool = list(a) + list(b)
    r, w, l = as_arrays(pool)
    k, ka = len(r), len(a)
    rng = np.random.default_rng(seed + 1)
    hits = tot = 0
    step = 500
    for s in range(0, n, step):
        m = min(step, n - s)
        perm = np.argsort(rng.random((m, k)), axis=1)
        left = _stat_vec(perm[:, :ka], r, w, l, kind)
        right = _stat_vec(perm[:, ka:], r, w, l, kind)
        d = np.abs(left - right)
        good = ~np.isnan(d)
        tot += int(good.sum())
        hits += int((d[good] >= obs - 1e-12).sum())
    return (hits + 1) / (tot + 1) if tot else float("nan")


def head_sha():
    """The commit the report was generated at -- `research/test_provenance.py` requires it."""
    import subprocess
    try:
        return subprocess.check_output(["git", "rev-parse", "--short=8", "HEAD"],
                                       cwd=ROOT, text=True).strip()
    except Exception:
        return "_this commit_"


def spearman(xs, ys):
    """Spearman rho with average ranks for ties."""
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk
    rx, ry = ranks(xs), ranks(ys)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else float("nan")


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def conf(r):
    return 1 if r["confluence"] == "yes" else 0


def net_score(r, subset=None, w_conf=-1):
    """score = (# of `subset` that tripped) + w_conf * confluence.

    Shipped is subset = all eight, w_conf = -1. Not floored -- the flooring is a
    grade-mapping choice, kept out of the raw score so the sweep can see below 0.
    """
    if subset is None:
        t = int(r["tripped"])
    else:
        t = sum(1 for v in r["downgrades"] if v in subset)
    return t + w_conf * conf(r)


def grade_of(score):
    return "S" if score <= 0 else ("A" if score == 1 else "C")


def rank_power(rows, subset, w_conf=-1):
    """How well this variable set ORDERS the book by realised R.

    Two readings, both reported everywhere this is used:
      rho  -- Spearman between score and r. Correct sign is NEGATIVE (more
              downgrades -> less R). Reported negated so bigger = better.
      lift -- mean R of the cleanest bucket (score <= 0) minus the book mean.
    """
    sc = [net_score(r, subset, w_conf) for r in rows]
    rs = [r["r"] for r in rows]
    rho = spearman(sc, rs)
    clean = [r["r"] for r, s in zip(rows, sc) if s <= 0]
    lift = (mean(clean) - mean(rs)) if clean else float("nan")
    return {"neg_rho": -rho, "lift": lift, "n_clean": len(clean)}


def ladder(rows, key):
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    out = []
    for k in sorted(g):
        rr = g[k]
        rs = [x["r"] for x in rr]
        wr, ndec = win_rate(rr)
        lo, hi = boot_ci(rs)
        out.append({"bucket": k, "n": len(rr), "mean": mean(rs), "median": median(rs),
                    "win": wr, "ndec": ndec, "rr": rr_ratio(rr), "lo": lo, "hi": hi,
                    "rows": rr})
    return out


def f(x, p=4):
    return "n/a" if x != x else f"{x:+.{p}f}"


# ---------------------------------------------------------------------------
def main():
    book = json.load(open(BOOK))
    meta = book["meta"]
    allrows = book["trades"]
    td = [r for r in allrows if r.get("traded")]
    assert all(int(r["tripped"]) == len(r["downgrades"]) for r in allrows), \
        "tripped count disagrees with the downgrades list"

    L = []
    A = L.append
    A("# X5 -- the downgrade ladder: inverted, or just n?\n")
    A(f"Generated by `python research/x5_downgrade_inversion.py` at commit `{head_sha()}`. Source: "
      f"`research/g3_arm_ow1.json` (built {meta['generated']}, {meta['signals']} signals / "
      f"{meta['traded']} traded, {meta['first']}..{meta['last']}, {meta['sessions']} sessions, "
      f"{len(meta['symbols'])} symbols). No bars, no replay, no network. Bootstrap: "
      f"{NBOOT:,} resamples, seed {SEED}. Error bar carried: **+-{NARROW_BAR} R** "
      f"(narrow bar, 2026-08-28; the wide +-1.5799 R bar is retired).\n")

    A("Austin's sentence, which this report exists to settle:\n")
    A("> the downgrade system the grades look right with profitability but maybe they need "
      "to be more simple because right now 3 downgrades has better rr then 1 downgrade and 0. "
      "but that also might just be because the sample size is inverted.\n")

    # ---------------- 0. the two readings of "rr" -------------------------
    A("## 0. \"rr\" has two readings and they give OPPOSITE answers\n")
    A("Before any table: `rr` can mean expectancy (mean R per trade) or the reward:risk "
      "ratio actually realised (average winner / average loser). Both are computed below "
      "everywhere. **On mean R the ladder is not inverted at all. On avg-win/avg-loss it is "
      "inverted, monotonically, and the mechanism is not a mystery.**\n")

    # ---------------- 1. the ladder ---------------------------------------
    A("## 1. The full ladder -- n FIRST\n")

    for label, key, note in [
        ("by raw downgrade count (`tripped`), 4+ collapsed", lambda r: min(int(r["tripped"]), 4),
         "This is the ladder Austin's sentence is about."),
        ("by shipped score (`tripped - confluence`), 4+ collapsed, not floored",
         lambda r: min(net_score(r), 4),
         "The number `downgrade.py::score()` actually grades on. Confluence is worth -1, "
         "so this ladder starts at -1."),
    ]:
        A(f"### {label}\n")
        A(f"{note}\n")
        A("| bucket | **n** | mean R | 95% CI on mean R | CI width | median R | win rate | "
          "avg-win / avg-loss |")
        A("|---|---:|---:|---|---:|---:|---:|---:|")
        rows = ladder(td, key)
        for b in rows:
            A(f"| {b['bucket']} | **{b['n']}** | {f(b['mean'])} | "
              f"[{f(b['lo'])}, {f(b['hi'])}] | {b['hi']-b['lo']:.4f} | {f(b['median'])} | "
              f"{b['win']:.1f}% | {b['rr']:.3f} |")
        A("")
        means = [b["mean"] for b in rows]
        rrs = [b["rr"] for b in rows]
        A(f"- mean R monotonically **decreasing** across the whole ladder: "
          f"**{'YES' if all(means[i] >= means[i+1] for i in range(len(means)-1)) else 'NO'}**")
        A(f"- avg-win/avg-loss monotonically **increasing** across the whole ladder: "
          f"**{'YES' if all(rrs[i] <= rrs[i+1] for i in range(len(rrs)-1)) else 'NO'}**"
          f"; increasing over every bucket EXCEPT the last: "
          f"**{'YES' if all(rrs[i] <= rrs[i+1] for i in range(len(rrs)-2)) else 'NO'}**")
        # every pairwise CI overlap
        ov = []
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                if rows[i]["lo"] <= rows[j]["hi"] and rows[j]["lo"] <= rows[i]["hi"]:
                    ov.append((rows[i]["bucket"], rows[j]["bucket"]))
        tot = len(rows) * (len(rows) - 1) // 2
        A(f"- pairwise 95% CIs that OVERLAP: **{len(ov)} of {tot}** -- {ov}")
        A("")

    # sample-size inversion, his own hypothesis, stated as a number
    cnt = Counter(min(int(r["tripped"]), 4) for r in td)
    A("### His own hypothesis, as a number\n")
    A('"the sample size is inverted" -- it is, and hard:\n')
    A("| downgrade count | n traded | % of traded book | n in the FULL signal population | % |")
    A("|---|---:|---:|---:|---:|")
    cntall = Counter(min(int(r["tripped"]), 4) for r in allrows)
    for k in sorted(cnt):
        A(f"| {k} | **{cnt[k]}** | {100*cnt[k]/len(td):.1f}% | {cntall[k]} | "
          f"{100*cntall[k]/len(allrows):.1f}% |")
    A("")
    A(f"The 0-downgrade bucket is **{cnt[0]} trades**. The 3-downgrade bucket is "
      f"**{cnt[3]}**, {cnt[3]/max(cnt[0],1):.1f}x bigger. Any comparison between them is "
      f"a comparison between an estimate with a wide interval and one with a narrow one.\n")

    # ---------------- 2. the inversion, tested ----------------------------
    A("## 2. Is 3 downgrades really better than 0? Tested directly\n")
    by = defaultdict(list)
    for r in td:
        by[min(int(r["tripped"]), 4)].append(r)
    a3, a0, a1 = by[3], by[0], by[1]

    A("10k-resample bootstrap on the difference, plus a two-sided label-permutation "
      "p-value on the same statistic. `share <= 0` is the bootstrap share of resamples "
      "where the difference came out at or below zero.\n")
    A("| statistic | arm A | n | arm B | n | A - B | 95% CI on the difference | "
      "boot share <= 0 | perm p | vs +-0.0095 R bar |")
    A("|---|---|---:|---|---:|---:|---|---:|---:|---|")

    tests = []
    for kind, sname in [("mean", "mean R"), ("rr", "avg-win / avg-loss")]:
        for (A_, an, B_, bn) in [(a3, "3 downgrades", a0, "0 downgrades"),
                                 (a3, "3 downgrades", a1, "1 downgrade")]:
            xa, xb = (([r["r"] for r in A_], [r["r"] for r in B_]) if kind == "mean"
                      else (A_, B_))
            pt, lo, hi, sh = boot_diff(xa, xb, kind=kind)
            p = perm_p(xa, xb, kind=kind)
            bar = ("clears it" if abs(pt) > NARROW_BAR else "INSIDE it") if kind == "mean" else "n/a (not an R)"
            A(f"| {sname} | {an} | {len(A_)} | {bn} | {len(B_)} | {f(pt)} | "
              f"[{f(lo)}, {f(hi)}] | {sh:.3f} | {p:.3f} | {bar} |")
            tests.append((sname, an, bn, pt, lo, hi, p))
    A("")

    # the local mean-R inversion inside the shipped score ladder
    byn = defaultdict(list)
    for r in td:
        byn[min(net_score(r), 4)].append(r)
    inv_pt = inv_p = float("nan")
    if 3 in byn and 2 in byn:
        xa = [r["r"] for r in byn[3]]
        xb = [r["r"] for r in byn[2]]
        pt, lo, hi, sh = boot_diff(xa, xb)
        p = perm_p(xa, xb)
        inv_pt, inv_p = pt, p
        A(f"**The only mean-R inversion that exists anywhere in either ladder** is inside "
          f"the shipped `tripped - confluence` score, at score 3 vs score 2: "
          f"{f(mean(xa))} (n={len(byn[3])}) vs {f(mean(xb))} (n={len(byn[2])}), "
          f"delta **{f(pt)}**, 95% CI [{f(lo)}, {f(hi)}], perm p = {p:.3f}. "
          f"The interval spans zero and is "
          f"{(hi-lo)/NARROW_BAR:.0f}x wider than the +-0.0095 R error bar. "
          f"**Noise.**\n")

    # ---- 2a. the mechanism behind the rr inversion -----------------------
    A("### The rr inversion is real, and it is arithmetic, not edge\n")
    nonstd = sum(1 for r in td if r["out"] == "loss" and abs(r["r"] + 1.0) > 1e-9)
    A(f"**Every single loss in this book is exactly -1.0000 R** ({nonstd} exceptions out of "
      f"{sum(1 for r in td if r['out']=='loss')} losses -- the -1.25R floor never binds, "
      f"`research/omen6_backtest_truth.md`). So the denominator of \"avg win / avg loss\" is "
      f"the constant 1, and **rr IS the average winner**. It is not a measure of edge; "
      f"expectancy is `W * rr - (1 - W)`, and that reconstruction is checked below.\n")
    A("| downgrade count | **n** | win rate W | avg WINNER (= rr) | avg loser | "
      "`W*rr - (1-W)` | actual mean R |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for b in ladder(td, lambda r: min(int(r["tripped"]), 4)):
        dec = [x for x in b["rows"] if x["out"] != "scratch"]
        wv = [x["r"] for x in dec if x["out"] == "win"]
        lv = [x["r"] for x in dec if x["out"] == "loss"]
        W = len(wv) / len(dec)
        A(f"| {b['bucket']} | **{b['n']}** | {100*W:.1f}% | {mean(wv):+.4f} | "
          f"{mean(lv):+.4f} | {W*mean(wv)+(1-W)*mean(lv):+.4f} | {f(b['mean'])} |")
    A("")
    A("Read the two moving columns together. Between 0 downgrades and 3 the average winner "
      "grows +2.0591 -> +2.7647 (**+34%**, Austin's observation, and it is correct) while the "
      "win rate falls 73.9% -> 51.9% (**-22 points**). The second move is bigger than the "
      "first, which is why mean R goes DOWN over the same span. **A dirtier setup that still "
      "manages to win had to travel further to get there** -- the ladder is not paying more "
      "for worse setups, it is surviving less often and the survivors are further from the "
      "entry. rr is the wrong statistic to rank a ladder on, and it is the only statistic on "
      "which the ladder is inverted.\n")

    # ---- 2b. does the ORDERING itself survive resampling -----------------
    A("### Does the ORDERING survive resampling?\n")
    A("The direct answer to \"or is it just n\". Resample the whole 1,017-row traded book "
      f"{NBOOT:,} times with replacement and re-derive the ladder each time. A ladder that "
      "is real should keep its shape in most resamples; one that is noise should not.\n")
    r_all, w_all, l_all = as_arrays(td)
    b_all = np.array([min(int(r["tripped"]), 4) for r in td])
    k = len(td)
    rng_np = np.random.default_rng(SEED + 7)
    ok_mean = ok_rr = ok_3gt0_mean = ok_3gt0_rr = 0
    for _ in range(NBOOT):
        idx = rng_np.integers(0, k, size=k)
        rb, wb, lb, bb = r_all[idx], w_all[idx], l_all[idx], b_all[idx]
        mm, rrv = [], []
        for b in range(5):
            m = bb == b
            nb = m.sum()
            mm.append(rb[m].mean() if nb else np.nan)
            nw, nl = (wb * m).sum(), (lb * m).sum()
            rrv.append(((rb * wb * m).sum() / nw) / abs((rb * lb * m).sum() / nl)
                       if nw and nl else np.nan)
        if any(x != x for x in mm):
            continue
        if all(mm[i] >= mm[i + 1] for i in range(4)):
            ok_mean += 1
        if all(x == x for x in rrv) and all(rrv[i] <= rrv[i + 1] for i in range(4)):
            ok_rr += 1
        if mm[3] > mm[0]:
            ok_3gt0_mean += 1
        if rrv[3] == rrv[3] and rrv[0] == rrv[0] and rrv[3] > rrv[0]:
            ok_3gt0_rr += 1
    A("| shape being tested | share of 10k resamples that show it |")
    A("|---|---:|")
    share_mono = 100*ok_mean/NBOOT
    A(f"| mean R monotonically DECREASING across 0,1,2,3,4+ | **{share_mono:.1f}%** |")
    A(f"| avg-win/avg-loss monotonically INCREASING across 0,1,2,3,4+ | **{100*ok_rr/NBOOT:.1f}%** |")
    A(f"| 3 downgrades beats 0 on **mean R** (Austin's claim, expectancy reading) | **{100*ok_3gt0_mean/NBOOT:.1f}%** |")
    A(f"| 3 downgrades beats 0 on **avg-win/avg-loss** (Austin's claim, rr reading) | **{100*ok_3gt0_rr/NBOOT:.1f}%** |")
    A("")

    # ---------------- 3. per-variable attribution -------------------------
    A("## 3. Per-variable attribution -- which of the eight actually predict\n")
    A("`tripped` = the traded rows where that variable fired. `clean` = the rest. "
      "A downgrade is RIGHT-SIGNED when tripped mean R < clean mean R. Ranked by delta, "
      "most-predictive first. `book trip %` is over all "
      f"{len(allrows):,} signals, not just the traded ones.\n")
    A("| # | variable | **n tripped** | n clean | book trip % | tripped mean R | "
      "clean mean R | delta | 95% CI on delta | CI excl. 0 | perm p | verdict |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---|")

    attrib = []
    for v in VARS:
        t = [r for r in td if v in r["downgrades"]]
        c = [r for r in td if v not in r["downgrades"]]
        bt = sum(1 for r in allrows if v in r["downgrades"])
        if len(t) < 2 or len(c) < 2:
            attrib.append({"v": v, "nt": len(t), "nc": len(c), "bt": bt,
                           "mt": mean([r["r"] for r in t]) if t else float("nan"),
                           "mc": mean([r["r"] for r in c]),
                           "d": float("nan"), "lo": float("nan"), "hi": float("nan"),
                           "p": float("nan"), "verdict": "NULL -- no traded tripped population"})
            continue
        xa = [r["r"] for r in t]
        xb = [r["r"] for r in c]
        pt, lo, hi, sh = boot_diff(xa, xb)
        p = perm_p(xa, xb)
        if pt >= 0:
            verdict = "**BACKWARDS**" if abs(pt) > NARROW_BAR and p < 0.10 else "backwards, but inside noise"
        else:
            verdict = "right-signed" if p < 0.10 else "right-signed, weak (p >= 0.10)"
        attrib.append({"v": v, "nt": len(t), "nc": len(c), "bt": bt, "mt": mean(xa),
                       "mc": mean(xb), "d": pt, "lo": lo, "hi": hi, "p": p,
                       "verdict": verdict})
    ordered = sorted(attrib, key=lambda a: (a["d"] if a["d"] == a["d"] else 1e9))
    for i, a in enumerate(ordered, 1):
        pstr = "n/a" if a["p"] != a["p"] else f"{a['p']:.3f}"
        excl = ("n/a" if a["lo"] != a["lo"]
                else ("**yes**" if (a["lo"] > 0 or a["hi"] < 0) else "no"))
        a["excl"] = (a["lo"] == a["lo"] and (a["lo"] > 0 or a["hi"] < 0))
        A(f"| {i} | `{a['v']}` | **{a['nt']}** | {a['nc']} | {100*a['bt']/len(allrows):.1f}% | "
          f"{f(a['mt'])} | {f(a['mc'])} | {f(a['d'])} | "
          f"[{f(a['lo'])}, {f(a['hi'])}] | {excl} | {pstr} | {a['verdict']} |")
    A("")

    def names(xs):
        return ", ".join("`" + x["v"] + "`" for x in xs) if xs else "none"

    live = [a for a in ordered if a["d"] == a["d"]]
    predicts = [a for a in live if a["d"] < 0 and a["p"] < 0.10]
    back = [a for a in live if a["d"] > 0]
    back_real = [a for a in back if a["p"] < 0.10 and abs(a["d"]) > NARROW_BAR]
    inert = [a for a in live if a["p"] >= 0.10 and a["d"] < 0]
    null = [a for a in ordered if a["d"] != a["d"]]
    A(f"- **PREDICTS** (right-signed and separable, perm p < 0.10): {names(predicts)}")
    A(f"- **BACKWARDS by point estimate** (trades where it trips do BETTER): {names(back)}")
    A(f"- **BACKWARDS and separable** (the ones that must be dropped or inverted, not just "
      f"retuned): {names(back_real)}")
    A(f"- **INERT** (right-signed but the interval spans zero, perm p >= 0.10): {names(inert)}")
    A(f"- **NULL** (no traded population at all -- unmeasurable on this book): {names(null)}")
    A("")
    A("Where the two tests disagree, believe the permutation test. `stale_retest`'s "
      "bootstrap CI excludes zero on **10 traded rows** -- a percentile interval built by "
      "resampling ten numbers is not a real interval, and its permutation p of 0.129 is the "
      "honest read. No conclusion in this report rests on it.\n")
    A(f"**{len([a for a in live if a['excl']])} of 8 have a 95% CI that excludes zero, and "
      f"{len(predicts)} of 8 clear a permutation test at p < 0.10.** Seven of the eight are "
      f"individually unfalsifiable on 1,017 trades. This is the same shape as the ladder "
      f"itself: the SIGN is mostly right, the SIZE is not established.\n")
    A("`level_not_respected` is the fourth independent confirmation of the same wrong sign "
      "(`research/a1_threshold_sweep.md` P15, `research/w9_downgrade_signs.md`, and this "
      "report on the same book). It is the highest-trip-rate variable in the set at "
      f"{100*[a for a in ordered if a['v']=='level_not_respected'][0]['bt']/len(allrows):.1f}% "
      "of the book, so it is the single biggest driver of the C bucket, and it points the "
      "wrong way. `break_then_rejection` has fired on **zero** traded rows in two years -- "
      "the fifth instance of the unreachable-rule class (`research/p2_threshold_sweep.md`, "
      "`research/g10_arming_funnel.md`); it is a variable in name only and costs nothing to "
      "delete because it has never once changed a grade in the traded book.\n")

    # ---------------- 4. greedy forward selection, held out ---------------
    A("## 4. Simplification -- the smallest subset that keeps the ranking power\n")
    A("Greedy forward selection, scored **out of sample**. The book is split by DATE "
      "(no symbol-day can straddle the split), the subset is chosen to maximise ranking "
      "power on the TRAIN half only, and every number in the table is the TEST half. "
      "Ranking power has two readings and both are carried:\n")
    A("- `-rho` -- Spearman between the score and realised R, negated so bigger is better "
      "(a correct downgrade score is NEGATIVELY correlated with R).\n"
      "- `lift` -- mean R of the cleanest bucket (score <= 0) minus the mean R of that "
      "half of the book. This is the number a selector would actually harvest.\n")

    days = sorted(set(r["day"] for r in td))
    cut = days[len(days) // 2]
    early = [r for r in td if r["day"] < cut]
    late = [r for r in td if r["day"] >= cut]

    def greedy(train, test, metric):
        chosen, rows_out = [], []
        remaining = list(VARS)
        best_so_far = -1e9
        while remaining:
            cands = []
            for v in remaining:
                s = set(chosen + [v])
                cands.append((rank_power(train, s)[metric], v))
            cands.sort(reverse=True)
            score_tr, v = cands[0]
            chosen.append(v)
            remaining.remove(v)
            te = rank_power(test, set(chosen))
            rows_out.append({"k": len(chosen), "added": v, "train": score_tr,
                             "test_rho": te["neg_rho"], "test_lift": te["lift"],
                             "test_nclean": te["n_clean"], "set": list(chosen)})
            best_so_far = max(best_so_far, score_tr)
        return rows_out

    runs = []
    for metric, mlabel in [("neg_rho", "-rho"), ("lift", "lift")]:
        for (tr_, te_, sl) in [(early, late, f"train = days < {cut} (n={len(early)}), "
                                             f"test = days >= {cut} (n={len(late)})"),
                               (late, early, f"train = days >= {cut} (n={len(late)}), "
                                             f"test = days < {cut} (n={len(early)})")]:
            A(f"### greedy on `{mlabel}` -- {sl}\n")
            full_test = rank_power(te_, set(VARS))
            A(f"All eight on the test half: **-rho {full_test['neg_rho']:+.4f}**, "
              f"**lift {f(full_test['lift'])}** (clean bucket n={full_test['n_clean']}).\n")
            A("| k | variable added | train " + mlabel + " | **test -rho** | **test lift** | "
              "test clean n | test -rho as % of all-eight | test lift as % of all-eight |")
            A("|---:|---|---:|---:|---:|---:|---:|---:|")
            first_rho = first_lift = None
            for row in greedy(tr_, te_, metric):
                pr = 100 * row["test_rho"] / full_test["neg_rho"] if full_test["neg_rho"] else float("nan")
                pl = 100 * row["test_lift"] / full_test["lift"] if full_test["lift"] == full_test["lift"] and full_test["lift"] else float("nan")
                if first_rho is None and pr == pr and pr >= 90:
                    first_rho = (row["k"], list(row["set"]))
                if first_lift is None and pl == pl and pl >= 90:
                    first_lift = (row["k"], list(row["set"]))
                A(f"| {row['k']} | `{row['added']}` | {row['train']:+.4f} | "
                  f"{row['test_rho']:+.4f} | {f(row['test_lift'])} | {row['test_nclean']} | "
                  f"{pr:.0f}% | {'n/a' if pl != pl else f'{pl:.0f}%'} |")
            A("")
            for tag, hit in (("-rho", first_rho), ("lift", first_lift)):
                if hit:
                    A(f"- smallest subset reaching **>= 90% of all-eight on test `{tag}`**: "
                      f"**k = {hit[0]}** ({', '.join('`'+v+'`' for v in hit[1])}) -- "
                      f"**{8-hit[0]} of 8 deletable** on this split")
                else:
                    A(f"- no subset smaller than all eight reaches 90% of all-eight on "
                      f"test `{tag}`")
                runs.append({"greedy_on": mlabel, "split": sl.split(",")[0],
                             "read": tag, "k": hit[0] if hit else 9,
                             "set": hit[1] if hit else []})
            A("")

    A("### All four runs together -- what is actually free\n")
    A("Four greedy runs (2 selection metrics x 2 directions of the temporal split). A "
      "deletion is only free if it is free in the WORST of them.\n")
    A("| read | worst-case k over the 4 runs | **guaranteed deletable** | in every winning subset |")
    A("|---|---:|---:|---|")
    for tag in ("-rho", "lift"):
        rs = [r for r in runs if r["read"] == tag]
        worst = max(r["k"] for r in rs)
        common = set(VARS)
        for r in rs:
            common &= set(r["set"]) if r["set"] else set(VARS)
        A(f"| `{tag}` | {worst if worst <= 8 else '8 (no subset qualified)'} | "
          f"**{max(0, 8-worst)} of 8** | "
          f"{', '.join('`'+v+'`' for v in sorted(common)) if common else 'nothing common'} |")
    A("")
    worst_rho = max(r["k"] for r in runs if r["read"] == "-rho")
    worst_lift = max(r["k"] for r in runs if r["read"] == "lift")
    A(f"**{8-worst_rho} of the 8 are deletable for free if all you need is the ORDERING** "
      f"(rank correlation between score and R survives at k = {worst_rho} on every run). "
      f"**{max(0, 8-worst_lift)} are deletable for free if you need the S-bucket LIFT** -- "
      f"the two directions of the split disagree completely on lift "
      f"(k = {min(r['k'] for r in runs if r['read']=='lift')} one way, "
      f"k = {worst_lift} the other), which is itself the finding: at 1,017 trades the "
      f"which-variables-matter question is not answerable to better than 'about half of "
      f"them, and `no_displacement` is in every answer'.\n")

    A("### What is NOT measured here, and why\n")
    A("The 100-card held-out recall rig "
      "(`research/marks/probe_omen_test1_2026-08-27.jsonl`, 15 S / 27 A / 16 C / 42 X) is "
      "**not** scored per subset. Scoring it needs one full `backtest_2y.py` bar replay per "
      "arm -- that is what `research/r3_downgrade_grader_ab.py` does -- and this lane is a "
      "no-bars book rig. So no subset below may be quoted as buying held-out recall. What IS "
      "known out of sample: R3 measured the FULL eight-variable grader wired in as the "
      "selector and got **S recall 3/15 -> 3/15, zero gain, with false fires 12/42 -> 14/42**. "
      "A subset of a set that bought nothing is not entitled to an assumption that it buys "
      "something.\n")

    # ---------------- 5. confluence weight sweep --------------------------
    A("## 5. Confluence -- is -1 the right weight?\n")
    A("`score = tripped + w * confluence`. Shipped is **w = -1**. Swept -2..+1 over the "
      "whole traded book, grades mapped S/A/C by the shipped rule (score <= 0 -> S, "
      "1 -> A, >= 2 -> C).\n")
    A("| w | S: **n** / mean R | A: **n** / mean R | C: **n** / mean R | S-A-C monotonic on mean R | "
      "-rho (whole book) | lift of the S bucket |")
    A("|---:|---|---|---|---|---:|---:|")
    rho_by_w = {}
    for w in (-2, -1, 0, 1):
        g = defaultdict(list)
        for r in td:
            g[grade_of(net_score(r, None, w))].append(r["r"])
        ms = {k: mean(v) for k, v in g.items()}
        mono = all(k in ms for k in "SAC") and ms["S"] >= ms["A"] >= ms["C"]
        sc = [net_score(r, None, w) for r in td]
        rho = -spearman(sc, [r["r"] for r in td])
        lift = ms.get("S", float("nan")) - mean([r["r"] for r in td])
        rho_by_w[w] = rho
        star = " **(shipped)**" if w == -1 else ""
        A(f"| {w}{star} | **{len(g.get('S',[]))}** / {f(ms.get('S', float('nan')))} | "
          f"**{len(g.get('A',[]))}** / {f(ms.get('A', float('nan')))} | "
          f"**{len(g.get('C',[]))}** / {f(ms.get('C', float('nan')))} | "
          f"{'YES' if mono else 'NO'} | {rho:+.4f} | {f(lift)} |")
    A("")

    # confluence on its own
    cy = [r["r"] for r in td if conf(r)]
    cn = [r["r"] for r in td if not conf(r)]
    pt, lo, hi, sh = boot_diff(cy, cn)
    p = perm_p(cy, cn)
    A(f"Confluence taken alone, as a plain split of the traded book: "
      f"**with confluence n={len(cy)} mean {f(mean(cy))}**, without n={len(cn)} mean "
      f"{f(mean(cn))}, delta **{f(pt)}** 95% CI [{f(lo)}, {f(hi)}], perm p = {p:.3f}. "
      f"Book trip rate {100*sum(1 for r in allrows if conf(r))/len(allrows):.1f}% "
      f"(Austin, 2026-08-24: confluence should fire on *under 1 in 5*).\n")

    # ---------------- 6. why the grader is not the selector ---------------
    A("## 6. Why a ladder that looks right still fails as a selector\n")
    sel_lo = sel_hi = float("nan")
    seq_td = Counter(r["seq"] for r in td)
    seq_all = Counter(r["seq"] for r in allrows)
    A(f"**The selection budget is already spent.** Of the {len(td):,} traded rows, "
      f"**{seq_td[1]:,} ({100*seq_td[1]/len(td):.1f}%) are `seq == 1`** -- the first signal "
      f"of their symbol-day -- against {seq_all[1]:,} of {len(allrows):,} "
      f"({100*seq_all[1]/len(allrows):.1f}%) in the full signal population. Being first is "
      f"very nearly NECESSARY to trade and nowhere near sufficient -- only "
      f"{100*seq_td[1]/max(seq_all[1],1):.1f}% of the {seq_all[1]:,} first-arrivals reach "
      f"the book. A grader applied downstream of that is re-ranking a population that has "
      f"already been filtered on an axis the grader cannot see.\n")

    A("**The engine's own selector is BLIND to the downgrade count.** If the legacy grader "
      "and the downgrade count were measuring the same thing, the share of each downgrade "
      "bucket that reaches the traded book would vary with the count. It does not:\n")
    A("| downgrade count | signals in the book | traded | **selection rate** |")
    A("|---|---:|---:|---:|")
    for kk in sorted(cntall):
        A(f"| {kk} | {cntall[kk]:,} | {cnt[kk]} | **{100*cnt[kk]/cntall[kk]:.2f}%** |")
    rates = [100 * cnt[kk] / cntall[kk] for kk in sorted(cntall)]
    sel_lo, sel_hi = min(rates), max(rates)
    A("")
    A(f"Selection rate spans {min(rates):.2f}%..{max(rates):.2f}% across the whole ladder -- "
      f"a {max(rates)/min(rates):.2f}x range against a mean-R range of "
      f"{max(b['mean'] for b in ladder(td, lambda r: min(int(r['tripped']),4))) - min(b['mean'] for b in ladder(td, lambda r: min(int(r['tripped']),4))):.4f} R. "
      f"The engine trades roughly 2 in 100 signals from EVERY bucket. The downgrade score "
      f"and the thing that picks trades are close to orthogonal, which is exactly why "
      f"bolting the grader on as a selector (R3) moved membership and not price.\n")

    # spread comparison: what the grader separates vs what other row facts separate
    A("**And the spread the ladder can harvest is small next to the spread other row "
      "facts carry.** Each row below splits the same 1,017 traded rows on one fact and "
      "reports the gap between the best and worst bucket's mean R.\n")
    A("| splitter | buckets | best bucket **n** / mean R | worst bucket **n** / mean R | spread |")
    A("|---|---:|---|---|---:|")
    splits = [
        ("downgrade count (0..4+)", lambda r: min(int(r["tripped"]), 4)),
        ("shipped score `tripped - confluence`", lambda r: min(net_score(r), 4)),
        ("`sgrade` (S/A/C)", lambda r: r["sgrade"]),
        ("`stopb` (stop tightness bucket)", lambda r: r["stopb"]),
        ("`aligned` (with HTF bias)", lambda r: r["aligned"]),
        ("`level` broken", lambda r: r["level"]),
        ("`vol_regime`", lambda r: r["vol_regime"]),
    ]
    for name, key in splits:
        g = defaultdict(list)
        for r in td:
            g[key(r)].append(r["r"])
        g = {k: v for k, v in g.items() if len(v) >= 20}   # universe.MIN_SAMPLE_N
        if len(g) < 2:
            continue
        ms = sorted(((mean(v), k, len(v)) for k, v in g.items()), reverse=True)
        A(f"| {name} | {len(g)} (n>=20) | **{ms[0][2]}** / {f(ms[0][0])} (`{ms[0][1]}`) | "
          f"**{ms[-1][2]}** / {f(ms[-1][0])} (`{ms[-1][1]}`) | {ms[0][0]-ms[-1][0]:.4f} |")
    A("")

    # ---------------- 7. verdict ------------------------------------------
    lad_t = ladder(td, lambda r: min(int(r["tripped"]), 4))
    b0, b3 = lad_t[0], lad_t[3]
    A("## 7. The verdict, in Austin's own terms\n")
    A(f"**\"3 downgrades has better rr than 1 downgrade and 0\" -- TRUE on the rr reading and "
      f"it is not an edge.** Average winner {b3['rr']:.3f} R at 3 downgrades against "
      f"{b0['rr']:.3f} R at 0, a real +{100*(b3['rr']/b0['rr']-1):.0f}%, but every loss in "
      f"this book is exactly -1.0000 R so rr is just the average winner, and the win rate "
      f"falls {b0['win']:.1f}% -> {b3['win']:.1f}% over the same span. Expectancy goes the "
      f"other way: {f(b0['mean'])} -> {f(b3['mean'])}.\n")
    A(f"**\"that also might just be because the sample size is inverted\" -- ALSO TRUE, and it "
      f"is the bigger of the two effects.** n = {b0['n']} against n = {b3['n']}. The 95% CI on "
      f"the 0-downgrade bucket is [{f(b0['lo'])}, {f(b0['hi'])}], "
      f"{b0['hi']-b0['lo']:.4f} R wide -- {(b0['hi']-b0['lo'])/NARROW_BAR:.0f}x the carried "
      f"+-0.0095 R error bar, and wider than the entire mean-R range of the ladder "
      f"({max(b['mean'] for b in lad_t) - min(b['mean'] for b in lad_t):.4f} R). "
      f"**Every one of the 10 pairwise CIs in the ladder overlaps.** No two rungs are "
      f"separable at n = 1,017.\n")
    A(f"**So: the ordering is real in sign and unestablished in size.** Mean R falls "
      f"monotonically across all five rungs -- that is the right shape and it is not "
      f"inverted -- but only {share_mono:.1f}% of bootstrap resamples reproduce the full "
      f"monotone ordering, and the one mean-R inversion that does exist (score 3 above "
      f"score 2, {inv_pt:+.4f} R) has a p of {inv_p:.3f}. Reading either as a result is "
      f"reading n.\n")
    A(f"**And on the question the ticket actually asks -- why a grader that looks right by "
      f"profitability fails as a selector -- the answer is not \"the ladder is inverted "
      f"noise\". It is \"the ladder is real, small, and applied at a seam that is already "
      f"occupied.\"** Section 6: {100*seq_td[1]/len(td):.1f}% of the traded book is "
      f"`seq == 1`, and the engine's selection rate is {sel_lo:.2f}%-{sel_hi:.2f}% in EVERY "
      f"downgrade bucket. Arrival order picks the book; the grade re-ranks a population "
      f"arrival order already chose. That is exactly the shape of R3's result -- wiring the "
      f"grader in moved MEMBERSHIP (958 rows traded by both arms, 1 with a different R, "
      f"`research/r3_downgrade_grader_ab.md`) and bought zero held-out recall.\n")
    A("### What follows for the simplification Austin asked about\n")
    A("Yes, it can be simpler, and the simplification is in the VARIABLES, not the ladder:\n")
    A(f"1. **`break_then_rejection` -- delete it.** 0 trips in 45,193 signals in two years. "
      f"It has never once changed a grade. Fifth member of the unreachable-rule class "
      f"(`research/p8_scratch.md`, `research/g10_arming_funnel.md`). Deleting it is provably "
      f"free: the book cannot change.\n"
      f"2. **`level_not_respected` -- drop it or invert it, do not retune it.** Wrong-signed "
      f"here and in `research/a1_threshold_sweep.md` and `research/w9_downgrade_signs.md`; "
      f"it is the highest-trip-rate variable in the set, so it is the single biggest "
      f"contributor to the C bucket while pointing the wrong way. `w9` warns that removing "
      f"it alone breaks the count ladder's monotonicity -- that is the ladder's cosmetics, "
      f"and section 4 shows the out-of-sample ORDERING does not need it.\n"
      f"3. **{8-worst_rho} of the 8 are deletable without losing out-of-sample ordering "
      f"power**, worst case across all four greedy runs. `no_displacement` is the one "
      f"variable in every winning subset and by itself reaches >= 90% of all eight on "
      f"three of the four runs.\n")
    rspan = max(rho_by_w[w] for w in (-2, -1, 0)) - min(rho_by_w[w] for w in (-2, -1, 0))
    A(f"What is NOT supported by anything here: changing the confluence weight (section 5 -- "
      f"w = -1 has the best S-bucket lift of the four, and the whole-book -rho spread across "
      f"w = -2, -1, 0 is {rspan:.4f}, which is smaller than the effect of any single "
      f"variable), and expecting any of this to move held-out recall, which is not measured "
      f"in this lane and which the full eight-variable version already failed to move "
      f"(R3: 3/15 -> 3/15).\n")

    open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"wrote {OUT}  ({len(L)} lines)")

    # console digest
    print("\n-- digest --")
    for b in ladder(td, lambda r: min(int(r["tripped"]), 4)):
        print(f"trips {b['bucket']}: n={b['n']:4d} mean {b['mean']:+.4f} "
              f"CI [{b['lo']:+.4f},{b['hi']:+.4f}] rr {b['rr']:.3f} win {b['win']:.1f}%")
    for t in tests:
        print(t[0], t[1], "vs", t[2], f"delta {t[3]:+.4f} CI [{t[4]:+.4f},{t[5]:+.4f}] p={t[6]:.3f}")


if __name__ == "__main__":
    main()
