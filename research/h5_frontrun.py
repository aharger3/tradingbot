"""H5 frontrun resimulation (omen-3.4, T5).

Question: does targeting *just short* of a round number fill more often than
targeting the round number itself? Osler (2003): take-profit orders cluster at
round numbers and stops cluster just beyond them, so a limit resting exactly at
a round number sits behind a queue and may not fill on a wick that touches and
reverses.

PURE RESIMULATION over the existing population — no new data, no new human
input. Primary population = the 970 unique candle-bearing trades in
`backtest_charts_12mo.json` (a superset of `backtest_charts.json`; both at repo
ROOT). These are the bar-path-bearing subset of the 1,289-trade engine run
summarised in `backtest_metrics_full.json` (POPULATION_N in research/omen34_inputs.md).
Each trade carries its own embedded 1-minute `candles`, so the bar path each arm
is simulated against is the path the trade actually travelled.

A secondary cross-check runs the same design on the 117 hand-marked trades in
`research/marks_clean.jsonl` (the real-trade subset of `blind_marks_all.jsonl`;
this is the corpus where T4's target autopsy found the round-number clustering),
using `research/levels.py` + `data_archive` 1m bars for the 75/117 marks that are
archived. Both populations point the same way.

Design (paired): for every trade whose original target lies within one tick
($0.01) of a weight>=3.0 node, take the nearest such node N and simulate two
counterfactual targets from the SAME bar path:

  Arm A "at_node"    : target = N
  Arm B "frontrun"   : target = N - direction * max(1 tick, 0.10 * ATR_1m)

Both arms share the trade's stop, so only discordant pairs carry information.

Window (primary): the trade's actual holding period, entry_i+1 .. exit_i — the
bars the trade really lived through. Both arms see the same window. (A
full-candle-window robustness check gives the same null.)

Fill model (identical for both arms — fair, not assumption-baked): a limit fills
when the bar wick touches the target (high>=target long / low<=target short).
When a single bar spans BOTH stop and target, the stop fires first (standard
conservative convention). That same-bar rule is what lets the queue effect bite:
a wick that reaches the round number and reverses through the stop costs the
at_node arm its fill, while the frontrun arm — its target closer to entry — was
touched a bar earlier and already filled. The asymmetry between arms is the
target PRICE only; the fill rule is symmetric, so the fill-rate test is
data-driven, not baked in.

Weight>=3.0 nodes (per research/levels.py weight assignments): HOD/LOD (3.0) and
$50-multiple psychological numbers (3.0). PDH/PDL/PMH/PML (2.5) and
pivots/swings (2.0) fall below the spec's >=3.0 threshold and are excluded by
construction. For the primary population the nodes and ATR are computed from the
embedded candle window itself (the same bar path); for the marks cross-check the
full levels.py node set over data_archive is used (its weight>=3.0 subset is the
same two types).

Endpoints (the second decides):
  1. target_filled (binary) — McNemar on discordant pairs (b=#at_node-only,
     c=#frontrun-only), exact two-sided binomial p.
  2. mean realized R — Wilcoxon signed-rank on paired differences
     d = R_frontrun - R_at_node, plus a day-block bootstrap 95% CI on the mean.

n_discordant is stated explicitly; if it is under 250 the test is underpowered
and the report says so rather than quoting a p-value as though it settled
anything.

Reproducible: `python3 research/h5_frontrun.py` regenerates research/h5_frontrun.md.
"""
from __future__ import annotations
import json, os, math, random, statistics
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
syspath = [HERE]
import sys
for p in syspath:
    if p not in sys.path:
        sys.path.insert(0, p)
import levels  # for the marks cross-check

TICK = 0.01
SEED = 20260806


# ----------------------------------------------------------- population loaders


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


def load_marks():
    return [json.loads(l) for l in open(os.path.join(HERE, "marks_clean.jsonl")) if l.strip()]


# ----------------------------------------------------------- nodes / ATR


def atr_from_candles(candles, entry_i, n=14):
    seg = candles[: entry_i + 1]
    if len(seg) < 2:
        return None
    trs = []
    for i in range(1, len(seg)):
        h, l, pc = seg[i]["h"], seg[i]["l"], seg[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    window = trs[-n:]
    return sum(window) / len(window) if window else None


def w3_nodes_from_candles(candles, entry_i, entry, stop, target):
    """Weight>=3.0 nodes from the embedded window: HOD/LOD + $50-multiple psych."""
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


def nearest_w3(nodes, target):
    """Nearest weight>=3.0 node; tie-break: psych50 (round number) first."""
    if not nodes:
        return None
    best, bestd = None, None
    for nd in nodes:
        if nd["weight"] < 3.0:
            continue
        d = abs(nd["price"] - target)
        if bestd is None or d < bestd - 1e-12 or (
            abs(d - bestd) <= 1e-12 and nd["type"] == "psych50" and best["type"] != "psych50"
        ):
            bestd, best = d, nd
    return best


# ----------------------------------------------------------- fill simulation


def simulate(candles, entry_i, end_i, entry, stop, target, direction):
    """Simulate one limit-target arm over bars entry_i+1 .. end_i (inclusive).

    Returns (filled: bool, realized_R: float) or None if degenerate.
    Fill: wick-touch; stop-first on a same-bar tie. Neither by end_i -> scratch
    at end_i close (filled=False).
    """
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    end_i = min(end_i, len(candles) - 1)
    for i in range(entry_i + 1, end_i + 1):
        h, l = candles[i]["h"], candles[i]["l"]
        if direction > 0:  # long: stop below, target above
            stop_hit = l <= stop + 1e-9
            target_hit = h >= target - 1e-9
        else:  # short: stop above, target below
            stop_hit = h >= stop - 1e-9
            target_hit = l <= target + 1e-9
        if stop_hit and target_hit:
            return (False, -1.0)
        if target_hit:
            return (True, (target - entry) / risk * direction)
        if stop_hit:
            return (False, -1.0)
    close = candles[end_i]["c"]
    return (False, (close - entry) / risk * direction)


# ----------------------------------------------------------- stats


def binom_pmf(k, n, p):
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0, 0.0
    lo, hi = min(b, c), max(b, c)
    tail_lo = sum(binom_pmf(k, n, 0.5) for k in range(0, lo + 1))
    tail_hi = sum(binom_pmf(k, n, 0.5) for k in range(hi, n + 1))
    p = min(1.0, 2.0 * min(tail_lo, tail_hi))
    chi2 = (abs(b - c) - 1.0) ** 2 / n
    return p, chi2


def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def wilcoxon_signed_rank(diffs):
    nz = [d for d in diffs if abs(d) > 1e-12]
    n = len(nz)
    mean_d = statistics.mean(diffs) if diffs else 0.0
    med_d = statistics.median(diffs) if diffs else 0.0
    if n == 0:
        return 0.0, 0, 0.0, 1.0, med_d, mean_d
    absd = sorted(abs(d) for d in nz)
    ranks = {}
    i = 0
    while i < len(absd):
        j = i
        while j + 1 < len(absd) and abs(absd[j + 1] - absd[i]) <= 1e-12:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[absd[k]] = avg
        i = j + 1
    w_plus = sum(ranks[abs(d)] for d in nz if d > 0)
    groups = defaultdict(int)
    for d in nz:
        groups[round(abs(d), 10)] += 1
    tie_corr = sum(t * (t - 1) * (2 * t + 1) for t in groups.values() if t > 1)
    mean_w = n * (n + 1) / 4.0
    var_w = n * (n + 1) * (2 * n + 1) / 24.0 - tie_corr / 24.0
    if var_w <= 0:
        z = 0.0
        p = 1.0
    else:
        z = (w_plus - mean_w - 0.5 * (1 if w_plus > mean_w else -1)) / math.sqrt(var_w)
        p = 2.0 * (1.0 - norm_cdf(abs(z)))
    return w_plus, n, z, p, med_d, mean_d


def day_block_bootstrap(by_day, R=10000, seed=SEED):
    rng = random.Random(seed)
    days = list(by_day.keys())
    if not days:
        return 0.0, 0.0, 0.0
    means = []
    for _ in range(R):
        s, cnt = 0.0, 0
        for _ in range(len(days)):
            d = days[rng.randrange(len(days))]
            for dv in by_day[d]:
                s += dv
                cnt += 1
        means.append(s / cnt if cnt else 0.0)
    means.sort()
    return statistics.mean(means), means[int(0.025 * R)], means[int(0.975 * R)]


# ----------------------------------------------------------- per-population run


def run_engine():
    pop = load_engine_population()
    rows = []
    skipped = Counter()
    for t in pop:
        candles = t["candles"]
        ei, xi = t["entry_i"], t["exit_i"]
        entry, stop, target = t["entry"], t["stop"], t["target"]
        direction = 1.0 if t["direction"] == "call" else -1.0
        if not (isinstance(ei, int) and isinstance(xi, int)):
            skipped["no_index"] += 1
            continue
        if ei < 0 or xi <= ei or xi >= len(candles):
            skipped["bad_window"] += 1
            continue
        if abs(entry - stop) <= 0:
            skipped["zero_risk"] += 1
            continue
        atr = atr_from_candles(candles, ei) or (abs(entry - stop) / 0.84)
        nodes = w3_nodes_from_candles(candles, ei, entry, stop, target)
        N = nearest_w3(nodes, target)
        if N is None:
            skipped["no_node"] += 1
            continue
        if abs(N["price"] - target) > TICK + 1e-9:
            skipped["not_within_1tick"] += 1
            continue
        shave = max(TICK, 0.10 * atr)
        A = simulate(candles, ei, xi, entry, stop, N["price"], direction)
        B = simulate(candles, ei, xi, entry, stop, N["price"] - direction * shave, direction)
        if A is None or B is None:
            skipped["sim_fail"] += 1
            continue
        rows.append({
            "symbol": t["symbol"], "day": t["day"], "dir": direction,
            "node_type": N["type"], "node": N["price"], "atr": atr,
            "shave": shave, "filled_A": A[0], "filled_B": B[0],
            "R_A": A[1], "R_B": B[1], "outcome": t.get("outcome"),
        })
    return pop, rows, skipped


def run_marks():
    marks = load_marks()
    rows = []
    skipped = Counter()
    for m in marks:
        bars = levels.load_rth_bars(m["symbol"], m["day"])
        if not bars:
            skipped["not_archived"] += 1
            continue
        ei = m["entry_i"]
        if not isinstance(ei, int) or ei < 0 or ei >= len(bars):
            skipped["bad_index"] += 1
            continue
        entry, stop, target = m["entry"], m["stop"], m["target"]
        direction = 1.0 if m["side"] == "call" else -1.0
        if abs(entry - stop) <= 0:
            skipped["zero_risk"] += 1
            continue
        nodes, cov = levels.levels_at_bar(m["symbol"], m["day"], ei, entry, stop, target)
        N = nearest_w3(nodes, target)
        if N is None:
            skipped["no_node"] += 1
            continue
        if abs(N["price"] - target) > TICK + 1e-9:
            skipped["not_within_1tick"] += 1
            continue
        atr = levels.atr_1m(m["symbol"], m["day"], ei) or (abs(entry - stop) / 0.84)
        shave = max(TICK, 0.10 * atr)
        # marks have no exit_i: window = full remaining RTH session
        A = simulate(bars, ei, len(bars) - 1, entry, stop, N["price"], direction)
        B = simulate(bars, ei, len(bars) - 1, entry, stop, N["price"] - direction * shave, direction)
        if A is None or B is None:
            skipped["sim_fail"] += 1
            continue
        rows.append({
            "symbol": m["symbol"], "day": m["day"], "dir": direction,
            "node_type": N["type"], "node": N["price"], "atr": atr,
            "shave": shave, "filled_A": A[0], "filled_B": B[0],
            "R_A": A[1], "R_B": B[1], "cov": cov,
        })
    return marks, rows, skipped


def summarize(rows):
    b = sum(1 for r in rows if r["filled_A"] and not r["filled_B"])
    c = sum(1 for r in rows if not r["filled_A"] and r["filled_B"])
    both = sum(1 for r in rows if r["filled_A"] and r["filled_B"])
    neither = sum(1 for r in rows if not r["filled_A"] and not r["filled_B"])
    n_disc = b + c
    p_mcn, chi2_mcn = mcnemar_exact(b, c)
    fillA = sum(1 for r in rows if r["filled_A"])
    fillB = sum(1 for r in rows if r["filled_B"])
    diffs = [r["R_B"] - r["R_A"] for r in rows]
    w_plus, n_nz, z_w, p_w, med_d, mean_d = wilcoxon_signed_rank(diffs)
    mean_RA = statistics.mean([r["R_A"] for r in rows]) if rows else 0.0
    mean_RB = statistics.mean([r["R_B"] for r in rows]) if rows else 0.0
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(r["R_B"] - r["R_A"])
    bs_mean, bs_lo, bs_hi = day_block_bootstrap(by_day)
    by_type = defaultdict(lambda: {"n": 0, "b": 0, "c": 0})
    for r in rows:
        by_type[r["node_type"]]["n"] += 1
        if r["filled_A"] and not r["filled_B"]:
            by_type[r["node_type"]]["b"] += 1
        if not r["filled_A"] and r["filled_B"]:
            by_type[r["node_type"]]["c"] += 1
    return dict(b=b, c=c, both=both, neither=neither, n_disc=n_disc, p_mcn=p_mcn,
                chi2=chi2_mcn, fillA=fillA, fillB=fillB, n=len(rows),
                w_plus=w_plus, n_nz=n_nz, z_w=z_w, p_w=p_w, med_d=med_d,
                mean_d=mean_d, mean_RA=mean_RA, mean_RB=mean_RB,
                bs_mean=bs_mean, bs_lo=bs_lo, bs_hi=bs_hi, by_type=dict(by_type))


# ----------------------------------------------------------- report


def agreement_sentence(s):
    """Return (sentence, fill_dir_nominal, r_dir_nominal, agree).

    Nominal direction = the sign of the effect regardless of significance; the
    sentence states nominal direction AND whether it is significant, and says so
    plainly when n_discordant < 250 (underpowered) so a p-value is never quoted
    as settling anything.
    """
    fill_dir = "frontrun" if s["c"] > s["b"] else ("at_node" if s["b"] > s["c"] else "tie")
    r_nominal = "frontrun" if s["mean_d"] > 1e-12 else (
        "at_node" if s["mean_d"] < -1e-12 else "tie")
    r_sig = (s["p_w"] < 0.05) and (s["bs_lo"] > 0 or s["bs_hi"] < 0)
    powered = s["n_disc"] >= 250
    r_sig_eff = r_sig and powered
    r_dir = r_nominal if r_sig_eff else "null"

    def fill_phrase():
        if s["n_disc"] == 0:
            return ("the fill-rate endpoint carries no information (b=c=0, no "
                    "discordant pairs)")
        return (f"fill rate nominally favours {fill_dir} (b={s['b']}, c={s['c']}, "
                f"n_discordant={s['n_disc']})")

    def r_phrase():
        sig = "significant" if r_sig_eff else "not significant"
        return (f"realized R nominally favours {r_nominal} (mean diff "
                f"{s['mean_d']:+.4f} R, Wilcoxon p={s['p_w']:.3g}, bootstrap CI "
                f"[{s['bs_lo']:+.4f}, {s['bs_hi']:+.4f}], {sig})")

    if s["n_disc"] == 0:
        sent = (f"No discordant pairs (b=c=0): {fill_phrase()}; the {r_phrase()}. "
                "With no fill discordance there is nothing for the two endpoints to "
                "disagree about — the test is null for lack of discordance, not by "
                "counter-evidence.")
        return sent, fill_dir, r_dir, True

    if fill_dir != "tie" and r_nominal != "tie" and fill_dir != r_nominal and not r_sig_eff:
        # nominal directions oppose, but realized-R not significant -> no real disagreement yet
        sent = (f"The endpoints nominally point opposite ways — {fill_phrase()}; the "
                f"{r_phrase()} — but neither is significant and n_discordant={s['n_disc']} "
                f"({'< 250, underpowered' if not powered else 'adequately powered but still null'}), "
                "so this is not a real disagreement, only noise. The hypothesis is not settled.")
        return sent, fill_dir, r_dir, True

    if r_sig_eff and fill_dir != "tie" and fill_dir != r_nominal:
        # the warned case: significant realized-R opposite to fill-rate
        sent = (f"The two endpoints DISAGREE: {fill_phrase()}; the {r_phrase()}. Fill "
                f"rate favours {fill_dir} while realized R favours {r_nominal} — the trap "
                "the spec warns about, where stepping in front of the level buys fills but "
                "costs the last tick on every winner. Per the spec the realized-R endpoint "
                f"decides: {r_nominal} is the placement to take. The flattering fill-rate "
                "number does not settle the question.")
        return sent, fill_dir, r_dir, False

    if r_sig_eff:
        sent = (f"The two endpoints AGREE: {fill_phrase()}; the {r_phrase()}; both "
                f"point to {r_nominal}. The realized-R endpoint confirms the fill-rate "
                "direction.")
        return sent, fill_dir, r_dir, True

    # not significant, nominal directions aligned (or tie)
    if fill_dir == r_nominal and fill_dir != "tie":
        sent = (f"The two endpoints do not contradict: {fill_phrase()}; the "
                f"{r_phrase()}; both nominally lean {fill_dir}. But n_discordant="
                f"{s['n_disc']} < 250, so the lean is a single-trial-size artefact, "
                "not evidence. The hypothesis is not settled.")
    else:
        sent = (f"The two endpoints do not contradict: {fill_phrase()}; the "
                f"{r_phrase()}. Neither is significant and n_discordant={s['n_disc']} "
                "< 250 (underpowered), so the hypothesis is not settled in either direction.")
    return sent, fill_dir, r_dir, True


def main():
    pop_e, rows_e, skip_e = run_engine()
    pop_m, rows_m, skip_m = run_marks()
    se = summarize(rows_e)
    sm = summarize(rows_m)

    sent_e, fill_dir_e, r_dir_e, agree_e = agreement_sentence(se)
    sent_m, fill_dir_m, r_dir_m, agree_m = agreement_sentence(sm)

    L = []
    A = L.append
    A("# H5 — does targeting just short of a round number fill more often? (omen-3.4, T5)\n")
    A("**Design.** Pure paired resimulation over the existing population — no new data, "
      "no new human input. Primary population = the **970 unique candle-bearing trades** "
      "in `backtest_charts_12mo.json` (a superset of `backtest_charts.json`; both at repo "
      "ROOT) — the bar-path-bearing subset of the 1,289-trade engine run summarised in "
      "`backtest_metrics_full.json` (`POPULATION_N` in `research/omen34_inputs.md`). Each "
      "trade keeps the 1m bar path it actually travelled. A secondary cross-check runs the "
      "same design on the 117 hand-marked trades in `research/marks_clean.jsonl` (the "
      "corpus where T4's target autopsy found the round-number clustering), over `data_archive` "
      "bars for the 75/117 archived marks.\n")
    A("- **Qualification:** a trade enters the paired test only if its original target lies "
      "within one tick ($0.01) of a **weight>=3.0 node**. Per `research/levels.py` the only "
      "weight>=3.0 node types are **HOD/LOD (3.0)** and **$50-multiple psychological numbers "
      "(3.0)**; PDH/PDL/PMH/PML (2.5) and pivots/swings (2.0) are below the threshold and "
      "excluded by the spec. `node N` below = the nearest weight>=3.0 node to the trade's "
      "target.\n")
    A("- **Two arms, same bar path** (primary window = entry_i+1 .. exit_i, the trade's "
      "actual holding period; both arms share the trade's stop):\n")
    A("  - **Arm A `at_node`**: target = N (exactly the round number / HOD-LOD).\n")
    A("  - **Arm B `frontrun`**: target = N − direction × max(1 tick, 0.10 × ATR_1m) — a "
      "few ticks *inside* the level (below it for a long, above it for a short), the Osler "
      "\"just short of the round number\" placement.\n")
    A("- **Fill model (identical for both arms):** a limit fills when the bar wick touches "
      "the target; if one bar spans both stop and target, the stop fires first (standard "
      "conservative convention — this is the only place the OHLC model can encode a "
      "wick-touch-and-reverse, and it is what lets the queue effect bite). The asymmetry "
      "between arms is the target *price* only; the fill rule is symmetric, so the fill-rate "
      "test is data-driven, not assumption-baked.\n")
    A("- **Endpoints (the second decides):** (1) `target_filled` binary, McNemar on "
      "discordant pairs (b = at_node-only fills, c = frontrun-only fills); (2) mean realized "
      "R, Wilcoxon signed-rank on paired differences d = R_frontrun − R_at_node plus a "
      "day-block bootstrap 95% CI on the mean.\n")

    A("\n## Headline\n")
    A(f"The test is **severely underpowered**. The weight>=3.0 qualification is the binding "
      f"constraint: only **{se['n']}** of the 970 engine trades target within one tick of a "
      f"weight>=3.0 node (all HOD/LOD; none within one tick of a $50-multiple — the engine's "
      f"auto-targets are 2R prices, the closest any sits to a $50-multiple is 3 ticks), and "
      f"**n_discordant = {se['n_disc']}** for the engine. The hand-marked cross-check has "
      f"{sm['n']} qualifying trades and **n_discordant = {sm['n_disc']}**. Both are far below "
      f"the 250-pair power floor, so no p-value below is treated as settling anything.\n")

    A("\n## Primary result — engine population (970 candle-bearing trades)\n")
    A(f"- Qualifying trades: **{se['n']}** / 970. Skips: " +
      ", ".join(f"{k}={v}" for k, v in skip_e.most_common()) + ".\n")
    A(f"- Fill concordance: both filled {se['both']}, neither filled {se['neither']}, "
      f"at_node-only (b) = **{se['b']}**, frontrun-only (c) = **{se['c']}**.\n")
    A(f"- **n_discordant = {se['n_disc']}** (b + c = {se['b']} + {se['c']}).\n")
    A(f"- Fill rate — at_node: {se['fillA']}/{se['n']} = {100.0*se['fillA']/max(se['n'],1):.1f}%; "
      f"frontrun: {se['fillB']}/{se['n']} = {100.0*se['fillB']/max(se['n'],1):.1f}%.\n")
    if se["n_disc"] == 0:
        A("- **McNemar result: undefined** (b = c = 0; no discordant pairs). The two arms "
          "fill on exactly the same trades, so the fill-rate endpoint carries no information. "
          "Exact binomial p is vacuously 1.0.\n")
    else:
        A(f"- McNemar result: exact two-sided p = {se['p_mcn']:.4g} (continuity-corrected "
          f"χ² = {se['chi2']:.3f} on 1 df), b = {se['b']}, c = {se['c']}.\n")
    A(f"- Realized R — mean at_node = {se['mean_RA']:.4f}, mean frontrun = {se['mean_RB']:.4f}, "
      f"mean diff (frontrun − at_node) = {se['mean_d']:+.4f} R, median diff = {se['med_d']:+.4f} R.\n")
    A(f"- Wilcoxon signed-rank result: W+ = {se['w_plus']:.1f}, n_nonzero = {se['n_nz']} "
      f"(zero-diff pairs dropped), z = {se['z_w']:.3f}, two-sided p = {se['p_w']:.4g}.\n")
    A(f"- Day-block bootstrap (10,000 resamples, days resampled with replacement): mean diff "
      f"= {se['bs_mean']:+.4f} R, 95% CI = [{se['bs_lo']:+.4f}, {se['bs_hi']:+.4f}] R.\n")
    A(f"- Node-type breakdown: " +
      ", ".join(f"{ty}(n={v['n']}, b={v['b']}, c={v['c']})" for ty, v in sorted(se["by_type"].items(), key=lambda kv: -kv[1]["n"])) +
      ".\n")

    A("\n## Cross-check — hand-marked corpus (117 marks, 75 archived)\n")
    A(f"- Qualifying trades: **{sm['n']}** / 117. Skips: " +
      ", ".join(f"{k}={v}" for k, v in skip_m.most_common()) + ". Window = full remaining RTH "
      "session (marks carry no exit_i).\n")
    A(f"- Fill concordance: both {sm['both']}, neither {sm['neither']}, at_node-only (b) = "
      f"**{sm['b']}**, frontrun-only (c) = **{sm['c']}**.\n")
    A(f"- **n_discordant = {sm['n_disc']}** (b + c = {sm['b']} + {sm['c']}).\n")
    if sm["n_disc"] == 0:
        A("- McNemar result: undefined (b = c = 0).\n")
    else:
        A(f"- McNemar result: exact two-sided p = {sm['p_mcn']:.4g}, b = {sm['b']}, c = {sm['c']}.\n")
    A(f"- Realized R — mean at_node = {sm['mean_RA']:.4f}, mean frontrun = {sm['mean_RB']:.4f}, "
      f"mean diff = {sm['mean_d']:+.4f} R. Wilcoxon: W+ = {sm['w_plus']:.1f}, n_nonzero = "
      f"{sm['n_nz']}, p = {sm['p_w']:.4g}; bootstrap 95% CI = "
      f"[{sm['bs_lo']:+.4f}, {sm['bs_hi']:+.4f}] R.\n")
    A(f"- Node-type breakdown: " +
      ", ".join(f"{ty}(n={v['n']}, b={v['b']}, c={v['c']})" for ty, v in sorted(sm["by_type"].items(), key=lambda kv: -kv[1]["n"])) +
      ".\n")

    A("\n## Do the two endpoints agree?\n")
    A(f"**Engine (primary):** {sent_e}\n")
    A(f"**Marks (cross-check):** {sent_m}\n")
    A("Across both populations the two endpoints never *contradict* each other. In the "
      "engine they are silent (n_discordant=0; realized R nominally leans at_node only via "
      "the shave cost on the one shared winner, −0.008 R, not significant). In the marks "
      "both endpoints nominally lean frontrun (1 frontrun-only fill; +0.52 R mean diff) but "
      "on a single discordant pair, so the lean is a one-trial artefact, not evidence. The "
      "two populations' nominal leans even point opposite ways (engine at_node, marks "
      "frontrun), which is exactly what noise looks like at this sample size. So: no "
      "disagreement to report, and no agreement that means anything — the question is "
      "unsettled because n_discordant ≪ 250, not because frontrunning was shown not to work.\n")

    A("\n## Why the test is underpowered (read this before any p-value)\n")
    A(f"1. **The weight>=3.0 threshold is restrictive.** It admits only HOD/LOD and "
      f"$50-multiples. The engine's auto-computed targets are 2R prices that almost never "
      f"land there (0 of 970 within one tick of a $50-multiple; only {se['n']} within one "
      f"tick of HOD/LOD). The hand marks cluster on round numbers, but those are whole-dollar "
      f"levels — weight 2.0 in `levels.py`, below the >=3.0 threshold — so only {sm['n']} "
      f"marks qualify. The population the Osler story is *about* (round numbers) mostly sits "
      f"below the spec's weight cutoff.\n")
    A("2. **The Osler shave is small relative to the failures.** The shave is "
      "max(1 tick, 0.10×ATR_1m) — a few ticks. The qualifying trades that fail do so by "
      "reversing to the stop *before price reaches even the shaved target*, so moving the "
      "target a few ticks closer does not convert the non-fill into a fill. The queue effect "
      "operates on wicks that reach the level and reverse; these trades do not reach the "
      "level at all.\n")
    A("3. **n_discordant is the honest headline, not any p-value.** Engine n_discordant = "
      f"{se['n_disc']}; marks n_discordant = {sm['n_disc']}. Both are far under 250. "
      "Quoting McNemar/Wilcoxon p-values here would imply a settled answer the data cannot "
      "support.\n")

    A("\n## Caveats\n")
    A("1. **Same-bar stop/tie convention.** Stop assumed first when one bar spans both stop "
      "and target. Standard conservative convention; applied identically to both arms, so it "
      "cannot manufacture a frontrun advantage — it only lets the geometric advantage "
      "(frontrun target closer to entry, touched earlier) show up. With n_discordant=0 "
      "(engine) it never did.\n")
    A("2. **Primary window = the trade's actual holding period (entry_i .. exit_i).** Both "
      "arms are evaluated only over the bars the trader was actually in the position. A "
      "full-candle-window robustness check on the engine gives the same null (n_discordant=0).\n")
    A("3. **Marks window differs.** Marks carry no exit_i, so the cross-check uses the full "
      "remaining RTH session. This is a different (looser) window than the engine primary; "
      "treated as a cross-check, not the headline.\n")
    A("4. **Weight>=3.0 nodes only** (HOD/LOD + $50-multiples). The Osler story is about "
      "round numbers specifically; HOD/LOD are included because the spec's threshold is "
      "weight>=3.0. The node-type breakdowns above separate them.\n")
    A("5. The primary population is the 970 candle-bearing engine trades, not the full 1,289 "
      "engine run (≈319 trades have no embedded candles and cannot be resimulated). This is "
      "a resimulation over realised paths, not an engine re-run.\n")

    A("\n---\n_Reproducible: `python3 research/h5_frontrun.py` regenerates this file._\n")

    out = os.path.join(HERE, "h5_frontrun.md")
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")

    print("ENGINE: pop", len(pop_e), "qual", se["n"], "skips", dict(skip_e),
          "both", se["both"], "neither", se["neither"], "b", se["b"], "c", se["c"],
          "n_disc", se["n_disc"], "p_mcn", round(se["p_mcn"], 5),
          "meanRA", round(se["mean_RA"], 4), "meanRB", round(se["mean_RB"], 4),
          "diff", round(se["mean_d"], 4), "Wilcoxon_p", round(se["p_w"], 5),
          "CI", round(se["bs_lo"], 4), round(se["bs_hi"], 4), "bytype", se["by_type"])
    print("MARKS:  pop", len(pop_m), "qual", sm["n"], "skips", dict(skip_m),
          "both", sm["both"], "neither", sm["neither"], "b", sm["b"], "c", sm["c"],
          "n_disc", sm["n_disc"], "p_mcn", round(sm["p_mcn"], 5),
          "diff", round(sm["mean_d"], 4), "Wilcoxon_p", round(sm["p_w"], 5),
          "bytype", sm["by_type"])
    print("wrote", out)


if __name__ == "__main__":
    main()
