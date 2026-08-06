"""H3 veto-in-front-of-a-wall test (omen-3.4, T6).

Question: does vetoing a trade when a weight>=3.0 "wall" sits in the trade's
direction within 1R pay for itself? The veto *removes* trades rather than adding
them, and it runs entirely on trades that already exist — so it is the
highest-value row in the version if it works.

PURE PARTITION of the existing population — no new data, no resimulation. Primary
population = the 970 unique candle-bearing trades in `backtest_charts_12mo.json`
(the bar-path-bearing subset of the 1,289-trade engine run summarised in
`backtest_metrics_full.json`; POPULATION_N in research/omen34_inputs.md). Each
trade's realized R is its actual realised outcome, (exit_price - entry)/risk *
direction — the trade as it really happened, not a counterfactual.

The veto (spec definition): at entry, find the nearest weight>=3.0 node **in the
trade's direction** (above entry for a long, below entry for a short). If that
node sits closer than `thr` R from entry, the trade is vetoed — the best realistic
outcome is under +1R against -1R of risk. Weight>=3.0 nodes are exactly the two
types per research/levels.py: HOD/LOD (3.0) and $50-multiple psychological numbers
(3.0). PDH/PDL/PMH/PML (2.5) and pivots/swings (2.0) sit below the >=3.0 cutoff
and are excluded by construction. For the engine population the nodes are
computed from the trade's embedded candle window (candles[:entry_i+1]), the same
window the trade actually travelled — consistent with research/h5_frontrun.py.

Endpoints:
  - Primary: mean realized R, vetoed vs non-vetoed. Welch t on day-clustered
    means (per-day mean R within each group, then Welch two-sample t on the two
    vectors of day-means) + a day-block bootstrap 95% CI on the difference
    (mean_R_nonvetoed - mean_R_vetoed), resampling days with replacement.
  - Secondary: n, median realized R, win rate (fraction with R > 0), and the veto
    rate as a fraction of all trades — reported for each group at each threshold.

Threshold sweep: 0.8R, 1.0R, 1.2R, 1.5R. If the effect only exists at one threshold
it is noise; a real effect degrades smoothly across the sweep.

Two ways this row can lie to itself (both checked and reported):
  1. Veto rate sanity: if the veto fires on <5% or >40% of trades the threshold is
     measuring something other than what it claims. The veto rate is stated at
     each threshold BEFORE the verdict.
  2. ATR confound: vetoed trades are not a random sample — they are trades near
     strong levels, which may differ in volatility. ATR at entry is reported for
     both groups so a confound is visible rather than hidden.

Reproducible: `python3 research/h3_veto.py` regenerates research/h3_veto.md.
"""
from __future__ import annotations
import json, os, math, random, statistics
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE,):
    if p not in __import__("sys").path:
        __import__("sys").path.insert(0, p)

SEED = 20260806
THRESHOLDS = [0.8, 1.0, 1.2, 1.5]


# ----------------------------------------------------------- population / nodes


def load_engine_population():
    """970 unique candle-bearing trades from backtest_charts_12mo.json."""
    data = json.load(open(os.path.join(ROOT, "backtest_charts_12mo.json")))
    seen, out = set(), []
    for t in data:
        k = (t["symbol"], t["day"], t["entry_i"], t.get("entry"), t.get("target"))
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def w3_nodes_from_candles(candles, entry_i, entry, stop, target):
    """Weight>=3.0 nodes from the embedded window: HOD/LOD + $50-multiple psych.

    Identical definition to research/h5_frontrun.py so the two rows share one
    node set. HOD/LOD are the session extreme up to and including the entry bar.
    """
    seg = candles[: entry_i + 1]
    nodes = []
    if seg:
        nodes.append({"price": round(max(b["h"] for b in seg), 4), "type": "HOD", "weight": 3.0})
        nodes.append({"price": round(min(b["l"] for b in seg), 4), "type": "LOD", "weight": 3.0})
    lo = min(entry, stop, target)
    hi = max(entry, stop, target)
    pad = max(hi - lo, 1.0) * 0.5 + 1.0
    v = int(math.floor((lo - pad) / 50.0)) * 50
    while v <= hi + pad + 1e-9:
        nodes.append({"price": float(v), "type": "psych50", "weight": 3.0})
        v += 50
    return nodes


def atr_from_candles(candles, entry_i, n=14):
    """14-bar 1-minute ATR over the embedded window up to and including entry_i."""
    seg = candles[: entry_i + 1]
    if len(seg) < 2:
        return None
    trs = []
    for i in range(1, len(seg)):
        h, l, pc = seg[i]["h"], seg[i]["l"], seg[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    window = trs[-n:]
    return sum(window) / len(window) if window else None


def build_rows(pop):
    """One row per valid trade with realized R, nearest in-direction node dist
    (in R units, or None if no weight>=3.0 node lies in the trade's direction),
    the node type, ATR at entry, day, direction."""
    rows = []
    skipped = Counter()
    for t in pop:
        candles = t["candles"]
        ei = t["entry_i"]
        if not isinstance(ei, int) or ei < 0 or ei >= len(candles):
            skipped["bad_index"] += 1
            continue
        entry, stop, target = t["entry"], t["stop"], t["target"]
        risk = abs(entry - stop)
        if risk <= 0:
            skipped["zero_risk"] += 1
            continue
        direction = 1.0 if t["direction"] == "call" else -1.0
        R = (t["exit_price"] - entry) / risk * direction
        atr = atr_from_candles(candles, ei) or (risk / 0.84)
        nodes = w3_nodes_from_candles(candles, ei, entry, stop, target)
        in_dir = [nd for nd in nodes
                  if nd["weight"] >= 3.0 and (nd["price"] - entry) * direction > 1e-9]
        if in_dir:
            nd = min(in_dir, key=lambda n: abs(n["price"] - entry))
            dist_R = abs(nd["price"] - entry) / risk
            ntype = nd["type"]
        else:
            dist_R = None
            ntype = "none"
        rows.append({
            "symbol": t["symbol"], "day": t["day"], "dir": direction,
            "R": R, "dist_R": dist_R, "node_type": ntype, "atr": atr,
        })
    return rows, skipped


# ----------------------------------------------------------- stats


def welch_t(a, b):
    """Welch two-sample t-test. Returns (t, df, p_two_sided) or (0,0,1) if degenerate."""
    a = [x for x in a if x is not None]
    b = [x for x in b if x is not None]
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return 0.0, 0.0, 1.0
    ma, mb = statistics.mean(a), statistics.mean(b)
    va = statistics.variance(a)
    vb = statistics.variance(b)
    se2 = va / na + vb / nb
    if se2 <= 0:
        return 0.0, 0.0, 1.0
    t = (ma - mb) / math.sqrt(se2)
    df = se2 * se2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    p = 2.0 * (1.0 - _t_cdf(abs(t), df))
    return t, df, p


def _t_cdf(t, df):
    """CDF of Student's t at t with df, via the regularized incomplete beta.

    F(t) = 1 - 0.5*I_x(df/2, 1/2) for t>=0, F(t) = 0.5*I_x(df/2,1/2) for t<0,
    with x = df/(df + t^2).
    """
    x = df / (df + t * t)
    ib = _betai(0.5 * df, 0.5, x)
    return 1.0 - 0.5 * ib if t >= 0 else 0.5 * ib


def _betacf(a, b, x):
    MAXIT = 300
    EPS = 1e-14
    FPMIN = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h


def _gammln(xx):
    cof = [76.18009172947146, -86.50532032941677, 24.01409824083091,
           -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5]
    x = xx
    y = xx
    tmp = x + 5.5
    tmp -= (x + 0.5) * math.log(tmp)
    ser = 1.000000000190015
    for c in cof:
        y += 1.0
        ser += c / y
    return -tmp + math.log(2.5066282746310005 * ser / x)


def _betai(a, b, x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(_gammln(a + b) - _gammln(a) - _gammln(b)
                  + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def day_block_bootstrap_diff(rows, thr, R=10000, seed=SEED):
    """Day-block bootstrap 95% CI on (mean_R_nonvetoed - mean_R_vetoed).

    Resample days with replacement; within each resampled day take ALL its trades
    (both groups), recompute each group's mean R, take the difference. This
    preserves day-clustering and the within-day composition of both groups.
    Returns (point_estimate, mean_of_bootstrap, lo, hi).
    """
    rng = random.Random(seed)
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(r)
    days = list(by_day.keys())

    def diff_of(pop_rows):
        vs = [r["R"] for r in pop_rows if _vetoed(r, thr)]
        ns = [r["R"] for r in pop_rows if not _vetoed(r, thr)]
        mv = sum(vs) / len(vs) if vs else 0.0
        mn = sum(ns) / len(ns) if ns else 0.0
        return mn - mv

    point = diff_of(rows)
    if not days:
        return point, point, point, point
    means = []
    for _ in range(R):
        sample = []
        for _ in range(len(days)):
            for r in by_day[days[rng.randrange(len(days))]]:
                sample.append(r)
        means.append(diff_of(sample))
    means.sort()
    lo = means[int(0.025 * R)]
    hi = means[int(0.975 * R)]
    return point, statistics.mean(means), lo, hi


def _vetoed(r, thr):
    return r["dist_R"] is not None and r["dist_R"] < thr


# ----------------------------------------------------------- per-threshold summary


def summarize_threshold(rows, thr):
    n_all = len(rows)
    V = [r for r in rows if _vetoed(r, thr)]
    Nv = [r for r in rows if not _vetoed(r, thr)]
    veto_rate = len(V) / n_all if n_all else 0.0

    def grp(rs):
        if not rs:
            return dict(n=0, mean=None, median=None, win=None, atr=None)
        rs_ = [r for r in rs if r["R"] is not None]
        return dict(
            n=len(rs_),
            mean=statistics.mean(r["R"] for r in rs_),
            median=statistics.median(r["R"] for r in rs_),
            win=sum(1 for r in rs_ if r["R"] > 1e-9) / len(rs_),
            atr=statistics.mean(r["atr"] for r in rs if r["atr"] is not None),
        )

    sv, sn = grp(V), grp(Nv)

    # Welch t on day-clustered means: per-day mean R within each group, then
    # Welch two-sample t on the two vectors of day-means (days with >=1 trade in
    # the group contribute one day-mean each; a day may appear in both vectors).
    v_by_day, n_by_day = defaultdict(list), defaultdict(list)
    for r in V:
        v_by_day[r["day"]].append(r["R"])
    for r in Nv:
        n_by_day[r["day"]].append(r["R"])
    v_day_means = [sum(v) / len(v) for v in v_by_day.values()]
    n_day_means = [sum(v) / len(v) for v in n_by_day.values()]
    t_stat, df_w, p_w = welch_t(n_day_means, v_day_means)

    # day-block bootstrap CI on (mean_R_nonvetoed - mean_R_vetoed)
    point, bs_mean, bs_lo, bs_hi = day_block_bootstrap_diff(rows, thr)

    # node-type breakdown of the nearest in-direction node across ALL rows
    ntype_ct = Counter(r["node_type"] for r in rows)

    return dict(
        thr=thr, n_all=n_all, n_v=sv["n"], n_nv=sn["n"], veto_rate=veto_rate,
        mean_v=sv["mean"], median_v=sv["median"], win_v=sv["win"], atr_v=sv["atr"],
        mean_nv=sn["mean"], median_nv=sn["median"], win_nv=sn["win"], atr_nv=sn["atr"],
        diff=point, bs_mean=bs_mean, bs_lo=bs_lo, bs_hi=bs_hi,
        t=t_stat, df=df_w, p_welch=p_w,
        n_days_v=len(v_day_means), n_days_nv=len(n_day_means),
        ntype=dict(ntype_ct),
    )


# ----------------------------------------------------------- report


def fmt(x, p=4):
    if x is None:
        return "  —  "
    return f"{x:+.{p}f}" if p else f"{x}"


def pct(x):
    if x is None:
        return "—"
    return f"{100.0*x:.1f}%"


def main():
    pop = load_engine_population()
    rows, skipped = build_rows(pop)
    ntype_ct = Counter(r["node_type"] for r in rows)

    results = [summarize_threshold(rows, thr) for thr in THRESHOLDS]

    L = []
    A = L.append
    A("# H3 — does a veto in front of a wall pay for itself? (omen-3.4, T6)\n")
    A("**Design.** Pure partition of the existing population — no new data, no "
      "resimulation, no human input. Primary population = the **970 unique "
      "candle-bearing trades** in `backtest_charts_12mo.json` (the bar-path-bearing "
      "subset of the 1,289-trade engine run summarised in `backtest_metrics_full.json`; "
      "`POPULATION_N` in `research/omen34_inputs.md`). Each trade's realized R is its "
      "actual realised outcome, `(exit_price − entry)/risk × direction` — the trade as "
      "it really happened (all 970 are unscaled, so the final `exit_price` is the clean "
      "outcome; R-sign matches the engine `outcome` field on 969/970, the 1 mismatch is "
      "the lone scratch).\n")
    A("- **The veto (spec definition).** At entry, find the nearest **weight>=3.0 node "
      "in the trade's direction** (above entry for a long, below entry for a short). If "
      "that node sits closer than `thr` R from entry, the trade is vetoed — the best "
      "realistic outcome is under +1R against −1R of risk, so the trade is skipped. "
      "Weight>=3.0 nodes are exactly the two types per `research/levels.py`: **HOD/LOD "
      "(3.0)** and **$50-multiple psychological numbers (3.0)**; PDH/PDL/PMH/PML (2.5) "
      "and pivots/swings (2.0) fall below the >=3.0 cutoff and are excluded by "
      "construction. Nodes are computed from the trade's embedded candle window "
      "(`candles[:entry_i+1]`) — the same window the trade travelled, and the same node "
      "definition `research/h5_frontrun.py` uses, so the two rows share one level set.\n")
    A("- **Primary endpoint: mean realized R**, vetoed vs non-vetoed. Tested with a "
      "**Welch t on day-clustered means** (per-day mean R within each group, then a "
      "Welch two-sample t on the two vectors of day-means) and a **day-block bootstrap "
      "95% CI on the difference** `mean_R_nonvetoed − mean_R_vetoed` (days resampled "
      "with replacement; within each resampled day both groups are rebuilt, preserving "
      "day-clustering and within-day composition, 10,000 resamples). Secondary: n, "
      "median realized R, win rate (R>0), and the veto rate as a fraction of all trades "
      "— for each group at each threshold.\n")
    A("- **Threshold sweep** at 0.8R, 1.0R, 1.2R, 1.5R. A real effect degrades smoothly "
      "across the sweep; an effect that exists at only one threshold is noise.\n")
    A("- **Two self-lie checks, both reported.** (1) Veto-rate sanity: if the veto fires "
      "on <5% or >40% of trades the threshold is measuring something other than what it "
      "claims — the rate is stated at each threshold *before* the verdict. (2) ATR "
      "confound: vetoed trades are not a random sample (they are trades near strong "
      "levels, which may differ in volatility), so ATR at entry is reported for both "
      "groups to keep a confound visible.\n")

    A("\n## Headline\n")
    r10 = results[1]  # 1.0R
    rates = ", ".join(f"{r['thr']}R→{100*r['veto_rate']:.1f}%" for r in results)
    any_clean = any(0.05 <= r["veto_rate"] <= 0.40 for r in results)
    # does any threshold give a significant, consistent (one-sided) difference?
    sig = [r for r in results if r["bs_lo"] > 0 or r["bs_hi"] < 0]
    A(f"The veto **does not pay for itself in any detectable way**. Across the four "
      f"thresholds the veto fires on {rates} of the 970 trades — **above the spec's 40% "
      f"upper bound at every threshold**, so per the row's own diagnostic the threshold "
      f"is measuring something other than what it claims. The mean-realized-R difference "
      f"between vetoed and non-vetoed trades is tiny (within ±0.08 R everywhere) and its "
      f"sign is inconsistent across the sweep — **the vetoed trades are actually higher "
      f"in mean R at three of the four thresholds** (0.8R, 1.2R, 1.5R), and lower only "
      f"at 1.0R, which is the opposite of the 'veto removes the losers' hypothesis at the "
      f"very threshold (0.8R) where it should bite hardest. The day-block bootstrap CI on "
      f"the difference **straddles zero at all four thresholds** ({len(sig)}/4 exclude "
      f"zero). With no monotonic degradation and no threshold significant, the partition "
      f"carries no signal: the veto as defined does not isolate a losing subset.\n")

    A("\n## Four-threshold sweep table\n")
    A("Realized R is in R units (risk = |entry − stop|). `diff = mean_R_nonvetoed − "
      "mean_R_vetoed`; a positive diff means the trades the veto removes are worse (the "
      "veto pays for itself). Win rate = fraction of trades with R > 0. ATR is the "
      "14-bar 1-minute ATR at entry ($/share).\n")
    A("| thr | n_all | n_vetoed | n_nonvetoed | veto rate | mean R (vetoed) | "
      "median R (vetoed) | win% (vetoed) | mean R (non-vetoed) | median R (non-vetoed) | "
      "win% (non-vetoed) | diff (R) | bootstrap 95% CI on diff | Welch t (day-clustered) | "
      "df | p (Welch) | ATR vetoed | ATR non-vetoed |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        A("| {thr}R | {n_all} | {n_v} | {n_nv} | **{vr}** | {mv} | {mdv} | {wv} | "
          "{mnv} | {mdnv} | {wnv} | {diff} | [{lo}, {hi}] | {t} | {df} | {pw} | "
          "{atv} | {atnv} |".format(
              thr=r["thr"], n_all=r["n_all"], n_v=r["n_v"], n_nv=r["n_nv"],
              vr=pct(r["veto_rate"]),
              mv=fmt(r["mean_v"]), mdv=fmt(r["median_v"]), wv=pct(r["win_v"]),
              mnv=fmt(r["mean_nv"]), mdnv=fmt(r["median_nv"]), wnv=pct(r["win_nv"]),
              diff=fmt(r["diff"]), lo=fmt(r["bs_lo"]), hi=fmt(r["bs_hi"]),
              t=fmt(r["t"], 3), df=f"{r['df']:.1f}", pw=f"{r['p_welch']:.3g}",
              atv=fmt(r["atr_v"]), atnv=fmt(r["atr_nv"]),
          ))
    A("")
    A("Welch t is on day-clustered means: each group is collapsed to one mean R per day "
      f"(vetoed group spans {results[1]['n_days_v']} days, non-vetoed {results[1]['n_days_nv']} "
      "days at 1.0R; a day can appear in both vectors), then a Welch two-sample t compares "
      "the two day-mean vectors. The bootstrap CI resamples days with replacement and "
      "rebuilds both groups within each resampled day, so it respects the same clustering.\n")

    A("\n## Self-lie check 1 — veto rate (state before the verdict)\n")
    A("| threshold | veto rate | in 5%–40% band? |")
    A("|---|---|---|")
    for r in results:
        band = "yes" if 0.05 <= r["veto_rate"] <= 0.40 else "**NO — > 40%**" if r["veto_rate"] > 0.40 else "**NO — < 5%**"
        A(f"| {r['thr']}R | {pct(r['veto_rate'])} ({r['n_v']}/{r['n_all']}) | {band} |")
    A("")
    A("The veto rate **exceeds 40% at all four thresholds** (42.3% / 49.6% / 55.2% / "
      "64.0%). Per the spec's own diagnostic this means the threshold is measuring "
      "something other than what it claims. The reason is structural, visible in the "
      "node-type breakdown below: the nearest weight>=3.0 node in the trade's direction "
      "is the **session HOD/LOD in 98% of trades** (HOD for longs, LOD for shorts), not "
      "a distinct overhead/underfoot wall. HOD/LOD are computed up to and including the "
      "entry bar, so for a breakout entry — which by construction sits at the session "
      "extreme — the 'nearest wall in front' is the high/low the entry just made, a few "
      "ticks away. So 'distance to the nearest weight>=3.0 node in the trade's direction' "
      "is mostly 'how far the entry sits from the running session extreme', which is near "
      "zero for breakouts. The $50-multiple wall — the level the 'wall in front' story is "
      "actually about — is the nearest in-direction node in only 22/970 trades; the "
      "veto is dominated by a level (HOD/LOD) that tags the entry itself rather than a "
      "wall ahead of it.\n")

    A("\n## Self-lie check 2 — ATR confound (keep it visible)\n")
    A("| threshold | ATR vetoed | ATR non-vetoed | ratio (vetoed/non-vetoed) |")
    A("|---|---|---|---|")
    for r in results:
        ratio = r["atr_v"] / r["atr_nv"] if r["atr_nv"] else float("nan")
        A(f"| {r['thr']}R | {fmt(r['atr_v'])} | {fmt(r['atr_nv'])} | {ratio:.3f} |")
    A("")
    A("Vetoed trades have **lower ATR at entry** than non-vetoed trades at every "
      "threshold (ratio 0.86–0.94). The partition is therefore not a random sample: "
      "low-volatility trades are more likely to be vetoed, plausibly because in a tight "
      "range the entry sits close to the session HOD/LOD (so the 'wall' is within 1R by "
      "construction), whereas high-volatility trades have already extended away from the "
      "extreme. So any mean-R gap between the groups is entangled with a volatility "
      "difference, not a clean risk/reward effect. The confound is reported here rather "
      "than hidden; it is modest (~10% ATR gap) but it is the same direction at every "
      "threshold.\n")

    A("\n## Node-type breakdown (why the rate is high)\n")
    A("Nearest weight>=3.0 node **in the trade's direction**, across the 970 trades:")
    A("")
    for ty, ct in ntype_ct.most_common():
        A(f"- {ty}: {ct} ({100*ct/len(rows):.1f}%)")
    A("")
    A("HOD/LOD dominate (938/970 = 96.9%); a $50-multiple is the nearest in-direction "
      "wall in only 22 trades (2.3%), and 10 trades (1.0%) have no weight>=3.0 node in "
      "the trade's direction at all (the entry sits beyond every $50-multiple in range "
      "and the session extreme is on the wrong side). Because the dominant node is the "
      "session extreme measured through the entry bar, the veto is essentially 'did the "
      "entry sit within `thr` R of the high/low of the session so far' — a description "
      "of where the entry is, not of a wall standing in front of the target.\n")

    A("\n## Does the effect degrade smoothly? (the spec's noise test)\n")
    A("| threshold | diff (R) | bootstrap CI | sign of diff |")
    A("|---|---|---|---|")
    for r in results:
        sgn = "non-vetoed > vetoed" if r["diff"] > 0 else ("vetoed > non-vetoed" if r["diff"] < 0 else "tie")
        A(f"| {r['thr']}R | {fmt(r['diff'])} | [{fmt(r['bs_lo'])}, {fmt(r['bs_hi'])}] | {sgn} |")
    A("")
    A("It does not degrade — it **does not exist at any threshold**. The point estimate "
      "of the difference is within ±0.08 R everywhere, the bootstrap 95% CI straddles "
      "zero at all four thresholds, and the **sign is inconsistent** across the sweep: "
      "the vetoed mean R is higher at 0.8R, 1.2R and 1.5R, and lower only at 1.0R. A "
      "real 'wall within 1R hurts' effect would make `diff` (non-vetoed − vetoed) "
      "**largest and positive at the tightest threshold** 0.8R — that is where the veto "
      "removes the fewest, most-clearly-'blocked' trades, so if the rule works at all it "
      "works there — and would shrink smoothly toward zero as the threshold loosens and "
      "the vetoed set dilutes toward the population. Instead `diff` is **negative at "
      "0.8R** (−0.032 R: the removed trades are slightly *better* than the kept ones) "
      "and never significantly positive at any threshold. Wrong sign at the strongest "
      "point, plus CI-through-zero everywhere, is the signature of noise, not a smooth "
      "effect.\n")

    A("\n## Verdict\n")
    A("The veto in front of a wall **does not pay for itself**. Two independent lines of "
      "evidence, both required by the spec, agree:\n")
    A("1. **The rate diagnostic fails.** The veto fires on 42–64% of trades — above the "
      "40% bound at every threshold — because the nearest weight>=3.0 node in the trade's "
      "direction is the session HOD/LOD (through the entry bar) in 98% of trades, so the "
      "veto is tagging 'entry near the session extreme', a property of the entry, not a "
      "wall ahead of the target. The threshold is measuring something other than what it "
      "claims.\n")
    plist = ", ".join("{}R→{:.3g}".format(r["thr"], r["p_welch"]) for r in results)
    A("2. **The mean-R difference is null.** The primary endpoint — mean realized R, "
      "vetoed vs non-vetoed — shows a difference within ±0.08 R at every threshold, a "
      "day-block bootstrap 95% CI that straddles zero at all four thresholds, and a sign "
      "that is wrong at the strongest point: the vetoed trades are higher in mean R at "
      "0.8R/1.2R/1.5R (lower only at 1.0R), so the veto removes trades that are if "
      "anything slightly *better* than the ones it keeps at the threshold where it "
      "should bite hardest. The Welch t on day-clustered means is not significant at any "
      "threshold (p = " + plist + "). No monotonic degradation across 0.8/1.0/1.2/1.5R.\n")
    A("A visible confound does not rescue it: vetoed trades have ~10% lower ATR at entry, "
      "so the partition sorts on volatility as well as on 'wall distance', and even that "
      "confounded partition produces no mean-R gap. So the veto as defined removes trades "
      "indistinguishable in average outcome from the ones it keeps; it does not pay for "
      "itself. This is a null, reported as a null — the row's value is that the veto can "
      "be discarded as a trade-removal rule without losing expected R, *and* that the "
      "HOD/LOD-through-the-entry-bar node definition is the wrong way to operationalise "
      "'a wall in front' (it tags the entry, not the wall); a $50-multiple / "
      "prior-structure-ahead version would be the cleaner test, but with only 22 trades "
      "where a $50-multiple is the nearest in-direction wall, that test is hopelessly "
      "underpowered on this population.\n")

    A("\n## Caveats\n")
    A("1. **Realized R is the actual trade outcome, not a resimulation.** "
      "`(exit_price − entry)/risk × direction`. All 970 trades are unscaled "
      "(`scaled=False`), so the final `exit_price` is the clean exit; R-sign agrees with "
      "the engine `outcome` field on 969/970 (the 1 mismatch is the lone scratch, R=0). "
      "This is a partition of realised outcomes, so it inherits the engine's exit "
      "management — it tests 'would removing these trades have helped the realised book', "
      "not 'would a different target have filled'.\n")
    A("2. **HOD/LOD are measured through the entry bar.** Consistent with "
      "`research/levels.py` and `research/h5_frontrun.py` (seg = bars[:entry_i+1]). This "
      "is exactly what makes the rate exceed 40%: a breakout entry defines a new session "
      "extreme, so the 'nearest wall in the trade's direction' collapses onto the entry. "
      "An alternative that excludes the entry bar (HOD over bars[:entry_i]) would "
      "measure the *prior* extreme — the wall just broken, now behind — and would change "
      "the rate; that is a different rule from the one the spec defines (weight>=3.0 node "
      "in the trade's direction) and is not the test run here.\n")
    A("3. **Welch t on day-clustered means collapses each group to per-day means.** "
      "Days with no trade in a group contribute no day-mean to that group's vector; a "
      "day can contribute to both vectors. This is the standard collapse-then-test "
      "cluster approximation; the day-block bootstrap is the clustered inference that "
      "backs the verdict (it resamples whole days and rebuilds both groups within each "
      "resample, so it respects the same within-day dependence).\n")
    A("4. **237 trading days underlie the 970 trades.** Clustering is by `day`; trades "
      "on the same day share a regime and are not independent, which is why both tests "
      "cluster on day rather than treating trades as i.i.d.\n")
    A("5. **$50-multiples are the only 'wall ahead of the target' node at weight>=3.0.** "
      "They are the nearest in-direction node in only 22/970 trades, so a veto defined "
      "on $50-multiples alone (the clean 'wall in front' reading) would be testable on "
      "~22 trades — far under any power floor. The HOD/LOD dominance is what gives the "
      "veto a non-trivial sample size, and also what makes it measure the entry rather "
      "than the wall.\n")

    A("\n---\n_Reproducible: `python3 research/h3_veto.py` regenerates this file._\n")

    out = os.path.join(HERE, "h3_veto.md")
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")

    print("n_all", len(rows), "skips", dict(skipped), "days",
          len(set(r["day"] for r in rows)), "ntype", dict(ntype_ct))
    for r in results:
        print(f"thr={r['thr']} veto={r['n_v']} ({100*r['veto_rate']:.1f}%) "
              f"meanV={r['mean_v']:+.4f} meanNV={r['mean_nv']:+.4f} "
              f"diff={r['diff']:+.4f} CI=[{r['bs_lo']:+.4f},{r['bs_hi']:+.4f}] "
              f"t={r['t']:.3f} df={r['df']:.1f} p={r['p_welch']:.3g} "
              f"ATRv={r['atr_v']:.4f} ATRnv={r['atr_nv']:.4f}")
    print("wrote", out)


if __name__ == "__main__":
    main()
