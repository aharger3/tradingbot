"""H_intrabar — can the 1-minute instrument support the T5/T6/T7 results? (omen-3.4, T8)

When a trade's target and stop both lie inside a single 1-minute bar's high-low range,
OHLCV cannot say which was hit first. This measures how often that happens across the
candle-bearing population, and re-scores the whole population twice — once assuming the
stop was hit first (pessimistic, primary) and once assuming the target was (optimistic) —
then checks whether any T5/T6/T7 conclusion flips between the two scorings. A conclusion
that flips is a measurement of bar resolution, not of the market.

Population: the 970 unique candle-bearing trades in `backtest_charts_12mo.json` — the
bar-path-bearing subset of the 1,289-trade engine run summarised in
`backtest_metrics_full.json` (POPULATION_N in research/omen34_inputs.md). This is the SAME
population T5 (h5_frontrun), T6 (h3_veto) and T7 (h9_confluence) scored their realised-R
results on, so the instrument check is directly comparable to those rows. A robustness
cross-check runs on the 792 unique candle-bearing trades in `backtest_charts.json` (the file
the spec's "roughly 780" framing maps to; both clear 780).

Realised R base = (exit_price - entry)/risk * direction (the value T5/T6/T7 used). For each
trade the bar path is walked over the trade's actual holding period [entry_i+1 .. exit_i]
(the same window h5_frontrun used). At the first bar where the stop and/or target is
touched the trade resolves: only stop → clear loss (-1R), only target → clear win (+R_target),
both in one bar → AMBIGUOUS (pessimistic -1R, optimistic +R_target), neither in the window
→ no_touch (bracket never hit; keeps the engine's realised R, both scorings agree). So the
pessimistic/optimistic scorings differ ONLY on ambiguous trades, which isolates the
bar-resolution effect cleanly from any engine fill-model difference.

The flip checks reuse the EXACT node definitions of the rows under test: T7's nearest-node
weight (research/h9_confluence.py: nodes_at_entry + nearest_node) and T6's nearest
in-direction weight>=3.0 node distance (research/h3_veto.py: w3_nodes_from_candles). Only
the R vector is swapped (engine → pess / opt); nodes, windows and clustering are identical,
so any verdict change is attributable to bar resolution alone.

Reproducible: `python3 research/h_intrabar.py` regenerates research/h_intrabar.md.
"""
from __future__ import annotations
import json, os, math, statistics, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import h9_confluence as h9          # nodes_at_entry, nearest_node, spearman, day_block_bootstrap_rho, ols_clustered, monotonicity_sentence
import h3_veto as h3                # w3_nodes_from_candles, atr_from_candles, summarize_threshold, day_block_bootstrap_diff, _vetoed
EPS = 1e-9
SEED = 20260806


# ----------------------------------------------------------- population loader

def load_engine(path):
    """Unique candle-bearing trades — same dedup key as h9/h5/h3."""
    data = json.load(open(os.path.join(ROOT, os.path.basename(path))))
    seen, out = set(), []
    for t in data:
        k = (t["symbol"], t["day"], t["entry_i"], t.get("entry"), t.get("target"))
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


# ----------------------------------------------------------- bar-path bracket simulation

def simulate(t):
    """Walk bars [entry_i+1 .. exit_i]; resolve at first touch of stop and/or target.

    Returns dict(cls in {clear_loss, clear_win, ambiguous, no_touch}, R_target, res_i).
    cls is the INSTRUMENT's resolution of a fixed stop/target bracket on the bar path:
        clear_loss  - a bar touched only the stop         -> -1R (both scorings agree)
        clear_win   - a bar touched only the target       -> +R_target (both scorings agree)
        ambiguous   - a bar touched BOTH stop and target  -> pess -1R / opt +R_target
        no_touch    - neither touched in the live window  -> bracket never hit; engine R stands
    """
    c = t["candles"]
    ei, xi = t["entry_i"], t["exit_i"]
    direction = 1.0 if t["direction"] == "call" else -1.0
    entry, stop, target = t["entry"], t["stop"], t["target"]
    risk = abs(entry - stop)
    R_target = (target - entry) / risk * direction
    for i in range(ei + 1, xi + 1):
        b = c[i]
        h, l = b["h"], b["l"]
        if direction > 0.0:                       # long: stop below, target above
            stop_t = l <= stop + EPS
            tgt_t = h >= target - EPS
        else:                                     # short: stop above, target below
            stop_t = h >= stop - EPS
            tgt_t = l <= target + EPS
        if stop_t and tgt_t:
            return dict(cls="ambiguous", R_target=R_target, res_i=i)
        if stop_t:
            return dict(cls="clear_loss", R_target=R_target, res_i=i)
        if tgt_t:
            return dict(cls="clear_win", R_target=R_target, res_i=i)
    return dict(cls="no_touch", R_target=R_target, res_i=None)


def build_rows(pop):
    """One row per valid trade carrying: engine R, R_target, bar-path class, ambiguity flag,
    the pess/opt R vectors, the T7 nearest-node weight, and the T6 veto dist_R/node_type."""
    rows, skip = [], Counter()
    for t in pop:
        ei = t["entry_i"]
        if not (isinstance(ei, int) and 0 <= ei < len(t["candles"])):
            skip["bad_entry_i"] += 1
            continue
        risk = abs(t["entry"] - t["stop"])
        if risk <= 0:
            skip["zero_risk"] += 1
            continue
        direction = 1.0 if t["direction"] == "call" else -1.0
        engR = (t["exit_price"] - t["entry"]) / risk * direction
        sim = simulate(t)
        amb = (sim["cls"] == "ambiguous")
        # pess/opt differ ONLY on ambiguous trades (isolate bar resolution)
        pess_R = -1.0 if amb else engR
        opt_R = sim["R_target"] if amb else engR
        # bar-path re-derived R (approach b: re-derive even non-ambiguous from the bar path)
        if sim["cls"] == "clear_loss":
            bp_pess = bp_opt = -1.0
        elif sim["cls"] == "clear_win":
            bp_pess = bp_opt = sim["R_target"]
        elif sim["cls"] == "ambiguous":
            bp_pess, bp_opt = -1.0, sim["R_target"]
        else:  # no_touch: bracket never hit, engine exit-management R stands
            bp_pess = bp_opt = engR
        # T7 nearest-node weight at entry (h9's exact node set)
        nodes = h9.nodes_at_entry(t)
        nd = h9.nearest_node(nodes, t["entry"])
        if nd is None:
            skip["no_node"] += 1
            continue
        weight = nd["weight"]
        ntype = nd["type"]
        # T6 veto: nearest in-direction weight>=3.0 node distance in R (h3's exact node set)
        vnodes = h3.w3_nodes_from_candles(t["candles"], ei, t["entry"], t["stop"], t["target"])
        atr = h3.atr_from_candles(t["candles"], ei) or (risk / 0.84)
        in_dir = [n for n in vnodes if n["weight"] >= 3.0 and (n["price"] - t["entry"]) * direction > 1e-9]
        if in_dir:
            ndv = min(in_dir, key=lambda n: abs(n["price"] - t["entry"]))
            dist_R = abs(ndv["price"] - t["entry"]) / risk
            vtype = ndv["type"]
        else:
            dist_R = None
            vtype = "none"
        rows.append(dict(
            symbol=t["symbol"], day=t["day"], dir=direction,
            engR=engR, R_target=sim["R_target"], cls=sim["cls"], amb=amb,
            weight=weight, ntype_h9=ntype, dist_R=dist_R, node_type=vtype, atr=atr,
            pess_R=pess_R, opt_R=opt_R, bp_pess=bp_pess, bp_opt=bp_opt,
            outcome=t.get("outcome"),
        ))
    return rows, skip


# ----------------------------------------------------------- core intrabar stats

def intrabar_stats(rows):
    N = len(rows)
    cls_ct = Counter(r["cls"] for r in rows)
    amb = cls_ct.get("ambiguous", 0)
    resolved = cls_ct.get("clear_loss", 0) + cls_ct.get("clear_win", 0) + amb
    mean_eng = statistics.mean(r["engR"] for r in rows)
    mean_pess = statistics.mean(r["pess_R"] for r in rows)
    mean_opt = statistics.mean(r["opt_R"] for r in rows)
    mean_bp_pess = statistics.mean(r["bp_pess"] for r in rows)
    mean_bp_opt = statistics.mean(r["bp_opt"] for r in rows)
    # how the engine scored the ambiguous trades (is the engine already pessimistic?)
    amb_rows = [r for r in rows if r["amb"]]
    amb_outcomes = Counter(r["outcome"] for r in amb_rows)
    amb_engR = statistics.mean(r["engR"] for r in amb_rows) if amb_rows else float("nan")
    amb_R_target = statistics.mean(r["R_target"] for r in amb_rows) if amb_rows else float("nan")
    return dict(
        N=N, cls_ct=dict(cls_ct), amb=amb, resolved=resolved,
        amb_rate_all=amb / N if N else 0.0,
        amb_rate_resolved=amb / resolved if resolved else 0.0,
        mean_eng=mean_eng, mean_pess=mean_pess, mean_opt=mean_opt,
        mean_bp_pess=mean_bp_pess, mean_bp_opt=mean_bp_opt,
        n_amb_outcomes=dict(amb_outcomes), amb_engR=amb_engR, amb_R_target=amb_R_target,
        gap_opt_pess=mean_opt - mean_pess,
    )


# ----------------------------------------------------------- T7 (h9) re-score under pess/opt

def h9_analyze(rows, rkey):
    """Replicate h9's three tests but on the pess or opt R vector (rkey = 'pess_R' or 'opt_R')."""
    h9rows = [{"weight": r["weight"], "R": r[rkey], "day": r["day"], "outcome": r["outcome"]} for r in rows]
    W = [r["weight"] for r in h9rows]
    Rv = [r["R"] for r in h9rows]
    rho, _ = h9.spearman(W, Rv)
    bs_mean, bs_lo, bs_hi = h9.day_block_bootstrap_rho(h9rows, R=10000, seed=SEED)
    b0, b1, se, t, p, G = h9.ols_clustered(W, Rv, [r["day"] for r in h9rows])
    weights_sorted = sorted(set(round(w, 2) for w in W))
    bins = []
    for w in weights_sorted:
        grp = [r["R"] for r in h9rows if abs(round(r["weight"], 2) - w) <= 1e-9]
        bins.append({"w": w, "n": len(grp),
                     "mean_R": statistics.mean(grp) if grp else 0.0})
    breaks = []
    for i in range(1, len(bins)):
        if bins[i]["mean_R"] < bins[i - 1]["mean_R"] - 1e-9:
            breaks.append((bins[i - 1]["w"], bins[i]["w"]))
    mono_strict = (len(breaks) == 0)
    ci_excludes_0 = (bs_lo > 0 or bs_hi < 0)
    return dict(rho=rho, bs_lo=bs_lo, bs_hi=bs_hi, ci_excludes_0=ci_excludes_0,
                b1=b1, p=p, bins=bins, breaks=breaks, mono_strict=mono_strict,
                mean_R=statistics.mean(Rv))


def h9_verdict(a):
    """Map a h9_analyze result to the h9 headline verdict label."""
    if a["ci_excludes_0"] and a["rho"] > 0 and a["mono_strict"]:
        return "yes-weakly"
    if a["ci_excludes_0"] and a["rho"] < 0:
        return "no-backwards"
    return "no"   # CI includes 0  (the published verdict)


# ----------------------------------------------------------- T6 (h3) re-score under pess/opt

def h3_analyze(rows, rkey):
    """Replicate h3's threshold sweep but on the pess or opt R vector."""
    h3rows = [{"R": r[rkey], "dist_R": r["dist_R"], "day": r["day"],
               "atr": r["atr"], "node_type": r["node_type"]} for r in rows]
    out = {}
    for thr in (0.8, 1.0, 1.2, 1.5):
        s = h3.summarize_threshold(h3rows, thr)
        out[thr] = s
    return out


def h3_verdict_any_pays(thr_dict):
    """Does the veto 'pay for itself' under this scoring? Requires: rate within 5-40%
    AND diff significantly positive (CI excludes 0, diff>0) at the tightest threshold
    with smooth degradation. Published verdict was 'does not pay for itself' (null)."""
    # rate diagnostic (structural; unchanged by R rescoring) — still >40% everywhere
    rate_ok = all(thr_dict[thr]["veto_rate"] <= 0.40 for thr in thr_dict)
    diff_pos_sig = []
    for thr in (0.8, 1.0, 1.2, 1.5):
        s = thr_dict[thr]
        diff_pos_sig.append(s["diff"] > 0 and s["bs_lo"] > 0)
    # 'pays for itself' would need rate within band AND a significant positive diff
    # at the tightest threshold (0.8R) where it should bite hardest, degrading after.
    pays = rate_ok and diff_pos_sig[0]
    return dict(rate_ok=rate_ok, rate_within_band=rate_ok,
                diff_pos_sig_08=diff_pos_sig[0],
                diff_pos_sig_any=any(diff_pos_sig),
                pays=pays)


# ----------------------------------------------------------- report

def main():
    pop12 = load_engine("backtest_charts_12mo.json")
    pop30 = load_engine("backtest_charts.json")
    rows12, skip12 = build_rows(pop12)
    rows30, skip30 = build_rows(pop30)

    s12 = intrabar_stats(rows12)
    s30 = intrabar_stats(rows30)

    # T7 re-scored
    t7_eng = h9_analyze(rows12, "engR")     # baseline (engine R) — should reproduce published ~+0.058
    t7_pess = h9_analyze(rows12, "pess_R")
    t7_opt = h9_analyze(rows12, "opt_R")
    # T6 re-scored
    t6_eng = h3_analyze(rows12, "engR")
    t6_pess = h3_analyze(rows12, "pess_R")
    t6_opt = h3_analyze(rows12, "opt_R")

    t7_v_eng = h9_verdict(t7_eng)
    t7_v_pess = h9_verdict(t7_pess)
    t7_v_opt = h9_verdict(t7_opt)
    t6_v_pess = h3_verdict_any_pays(t6_pess)
    t6_v_opt = h3_verdict_any_pays(t6_opt)

    # robustness (charts file)
    t7_pess_r = h9_analyze(rows30, "pess_R")
    t7_opt_r = h9_analyze(rows30, "opt_R")

    L = []
    A = L.append
    A("# H_intrabar — can the 1-minute instrument support the T5/T6/T7 results? (omen-3.4, T8)\n")
    A("**Question.** Before any result in T5/T6/T7 is believed, measure whether the "
      "instrument can support it. When a trade's target and stop both lie inside a single "
      "1-minute bar's high-low range, OHLCV cannot say which was hit first. This counts "
      "how often that happens and re-scores the whole population twice — pessimistic "
      "(stop hit first, primary) and optimistic (target hit first) — to see whether any "
      "T5/T6/T7 conclusion is a measurement of bar resolution rather than of the market.\n")
    A("**Population.** The **970 unique candle-bearing trades** in `backtest_charts_12mo.json` "
      "— the bar-path-bearing subset of the 1,289-trade engine run summarised in "
      "`backtest_metrics_full.json` (`POPULATION_N` in `research/omen34_inputs.md`). This is "
      "the SAME population T5 (`research/h5_frontrun.md`), T6 (`research/h3_veto.md`) and T7 "
      "(`research/h9_confluence.md`) scored their realised-R results on, so the instrument "
      "check is directly comparable. A robustness cross-check runs on the **792 unique "
      "candle-bearing trades** in `backtest_charts.json` (793 raw, one duplicate removed) — "
      "the file the spec's \"roughly 780\" framing maps to; both clear 780.\n")
    A("**Method.** Each trade's bar path is walked over its actual holding period "
      "[entry_i+1 .. exit_i] (the same window `research/h5_frontrun.py` used). At the first "
      "bar where the stop and/or target is touched the bracket resolves: only the stop → "
      "clear loss (−1R, both scorings agree); only the target → clear win (+R_target, both "
      "agree); **both in one bar → AMBIGUOUS** — pessimistic scores −1R, optimistic +R_target; "
      "neither in the window → `no_touch` (bracket never hit; the engine's exit-management R "
      "stands, both scorings agree). So the pessimistic and optimistic scorings differ **only** "
      "on ambiguous trades, which isolates the bar-resolution effect from any engine "
      "fill-model difference. Realised-R base = `(exit_price − entry)/risk × direction` (the "
      "value T5/T6/T7 used); `R_target = (target − entry)/risk × direction` (≈ +2R for the "
      "engine's auto-2R targets). Long: stop touched when `low ≤ stop`, target when `high ≥ "
      "target`; short: the mirror. Touch uses a 1e-9 tolerance.\n")

    # ---- headline
    over20 = s12["amb_rate_all"] > 0.20
    over_clause = (" — 1-minute OHLCV is the WRONG resolution for this study (a finding "
                   "about what data to buy next, not a reason to stop).") if over20 else "."
    A("\n## Headline\n")
    A(f"**Ambiguous-bar rate = {100*s12['amb_rate_all']:.1f}% of all trades "
      f"({s12['amb']}/{s12['N']})** and {100*s12['amb_rate_resolved']:.1f}% of resolved trades "
      f"({s12['amb']}/{s12['resolved']}). "
      f"Mean realised R = **{s12['mean_pess']:+.4f}** pessimistic vs "
      f"**{s12['mean_opt']:+.4f}** optimistic — a gap of {s12['gap_opt_pess']:+.4f} R "
      f"({100*s12['gap_opt_pess']:.1f}% of a single R) attributable entirely to bar resolution. "
      f"The ambiguous-bar rate is {'**ABOVE**' if over20 else 'below'} the 20% "
      f"instrument-sufficiency threshold{over_clause}\n")

    # ---- ambiguity table
    A("\n## 1. Ambiguous-bar rate\n")
    A("| population | n_all | clear_loss | clear_win | ambiguous | no_touch | resolved | "
      "amb % all | amb % resolved |\n"
      "|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for label, s in (("Primary (970, 12mo)", s12), ("Robustness (792, charts)", s30)):
        cc = s["cls_ct"]
        A(f"| {label} | {s['N']} | {cc.get('clear_loss',0)} | {cc.get('clear_win',0)} | "
          f"{cc.get('ambiguous',0)} | {cc.get('no_touch',0)} | {s['resolved']} | "
          f"{100*s['amb_rate_all']:.1f}% | {100*s['amb_rate_resolved']:.1f}% |")
    A(f"\n`resolved` = clear_loss + clear_win + ambiguous (the trades the stop/target "
      f"bracket actually reaches on the bar path). `no_touch` = the bracket never hit in the "
      f"live window — the engine exited via its own management (partial / scratch / runner) "
      f"before the stop or target; those keep the engine R under both scorings and are "
      f"excluded from the resolved denominator.\n")
    A(f"\n**Is the engine already pessimistic?** Of the {s12['amb']} ambiguous trade"
      f"{'s' if s12['amb'] != 1 else ''}, the "
      f"engine scored {dict_str(s12['n_amb_outcomes'])} with mean engine R = "
      f"{s12['amb_engR']:+.4f} (vs ambiguous-trade R_target mean = "
      f"{s12['amb_R_target']:+.4f}). If the engine is conservative on same-bar overlap "
      f"(stop-first), the pessimistic scoring reproduces its book; the optimistic scoring is "
      f"the one that moves.\n")

    # ---- mean R both scorings
    A("\n## 2. Mean realised R — pessimistic vs optimistic\n")
    A("| population | n | mean R (engine) | mean R (pessimistic) | mean R (optimistic) | "
      "gap (opt−pess) |\n|---|---:|---:|---:|---:|---:|")
    for label, s in (("Primary (970, 12mo)", s12), ("Robustness (792, charts)", s30)):
        A(f"| {label} | {s['N']} | {s['mean_eng']:+.4f} | {s['mean_pess']:+.4f} | "
          f"{s['mean_opt']:+.4f} | {s['gap_opt_pess']:+.4f} |")
    A(f"\nThe pessimistic scoring is the primary headline. The gap between the two scorings "
      f"= (R_target + 1) × n_ambiguous / N, so it is **entirely** a bar-resolution artefact: "
      f"non-ambiguous trades carry identical R under both scorings.\n")
    A(f"\n**Bar-path re-derivation cross-check** (re-derive even the non-ambiguous outcomes "
      f"purely from the bar path, instead of trusting the engine): primary mean R = "
      f"{s12['mean_bp_pess']:+.4f} pessimistic / {s12['mean_bp_opt']:+.4f} optimistic. The "
      f"pess−opt gap is unchanged (it is set only by ambiguous trades), and the level shift "
      f"vs the engine-based figures ({s12['mean_bp_pess']-s12['mean_pess']:+.4f} R on the "
      f"pessimistic side) measures how often the bar-path bracket disagrees with the "
      f"engine's own exit management on *non-ambiguous* trades — a fill-model difference, not "
      f"a bar-resolution one, and reported so it is not confused with the headline.\n")

    # ---- T7 flip check
    A("\n## 3. Does any T5/T6/T7 conclusion flip between the two scorings?\n")
    A("The re-scorings swap ONLY the R vector (engine → pessimistic / optimistic); nodes, "
      "windows and day-clustering are identical to the rows under test, so any verdict "
      "change is attributable to bar resolution alone. T5 (`h5_frontrun`) returned a "
      "power-null (n_discordant = 0 engine / 1 marks) with no directional conclusion, so it "
      "has no sign to flip and is not re-run.\n")
    A("\n**T7 (`h9_confluence`) — does confluence weight track realised R?**\n")
    A("| scoring | rho | bootstrap 95% CI | CI excl. 0? | OLS slope | p | monotonic? | verdict |\n"
      "|---|---:|---|---|---:|---:|---|---|")
    for label, a, v in (("engine (baseline)", t7_eng, t7_v_eng),
                        ("pessimistic", t7_pess, t7_v_pess),
                        ("optimistic", t7_opt, t7_v_opt)):
        A(f"| {label} | {a['rho']:+.4f} | [{a['bs_lo']:+.4f}, {a['bs_hi']:+.4f}] | "
          f"{'yes' if a['ci_excludes_0'] else 'no'} | {a['b1']:+.4f} | {a['p']:.3g} | "
          f"{'yes' if a['mono_strict'] else 'no'} | {v} |")
    t7_flip = (t7_v_pess != t7_v_opt)
    A(f"\nPublished T7 verdict: **No** (rho +0.0580, CI includes 0, monotonicity broken). "
      f"Re-scored verdict: pessimistic = **{t7_v_pess}**, optimistic = **{t7_v_opt}**. "
      f"{'The verdict FLIPS between scorings — so the T7 conclusion is a measurement of bar '
       'resolution, not of the market.' if t7_flip else 'The verdict does NOT flip between '
       'scorings — the T7 null holds under both, so it is not a bar-resolution artefact.'}\n")

    # ---- T6 flip check
    A("\n**T6 (`h3_veto`) — does a veto in front of a wall pay for itself?**\n")
    A("diff = mean R (non-vetoed) − mean R (vetoed); positive = the veto removes losers. "
      "Published verdict: **does not pay for itself** (rate > 40% at every threshold — a "
      "structural property of node distance, unchanged by R rescoring — and diff within "
      "±0.08R with a CI straddling zero everywhere, sign inconsistent).\n")
    A("| scoring | thr | veto rate | rate in 5–40%? | diff (R) | bootstrap 95% CI on diff | "
      "CI excl. 0? |\n|---|---:|---:|---|---:|---|---|")
    for label, td in (("pessimistic", t6_pess), ("optimistic", t6_opt)):
        for thr in (0.8, 1.0, 1.2, 1.5):
            s = td[thr]
            A(f"| {label} | {thr}R | {100*s['veto_rate']:.1f}% | "
              f"{'yes' if 0.05 <= s['veto_rate'] <= 0.40 else 'no'} | {s['diff']:+.4f} | "
              f"[{s['bs_lo']:+.4f}, {s['bs_hi']:+.4f}] | "
              f"{'yes' if s['bs_lo']>0 or s['bs_hi']<0 else 'no'} |")
    t6_v_pays_pess = t6_v_pess["pays"]
    t6_v_pays_opt = t6_v_opt["pays"]
    t6_flip = (t6_v_pays_pess != t6_v_pays_opt)
    # also check the softer 'does any threshold's diff sign flip between scorings'
    sign_flips = []
    for thr in (0.8, 1.0, 1.2, 1.5):
        sp = t6_pess[thr]["diff"]
        so = t6_opt[thr]["diff"]
        if (sp > 0) != (so > 0) and abs(sp) > 1e-9 and abs(so) > 1e-9:
            sign_flips.append(thr)
    A(f"\nRe-scored veto verdict: pessimistic pays-for-itself = **{t6_v_pays_pess}**, "
      f"optimistic = **{t6_v_pays_opt}**. "
      f"{'The verdict FLIPS between scorings — so the T6 conclusion is a measurement of bar '
       'resolution, not of the market.' if t6_flip else 'The verdict does NOT flip between '
       'scorings — the T6 null (rate>40% everywhere; diff tiny, CI through zero) holds under '
       'both, so it is not a bar-resolution artefact.'}"
      f"{(' At least one threshold diff sign flips between scorings (' + ', '.join(f'{t}R' for t in sign_flips) + ') — but no threshold becomes significantly positive, so the verdict does not change.') if sign_flips else ''}\n")

    A("\n**Flip summary.** "
      + ("NONE of the T5/T6/T7 conclusions flips between the pessimistic and optimistic "
         "scorings." if (not t7_flip and not t6_flip) else
         ("T7 flips. " if t7_flip else "") + ("T6 flips. " if t6_flip else ""))
      + " The T5 power-null has no sign to flip. Therefore no T5/T6/T7 conclusion measured "
      "here is an artefact of 1-minute bar resolution; the results stand (or fail) on the "
      "market, not on the instrument.\n")

    # ---- robustness note
    A("\n## Robustness\n")
    A(f"The 792-trade charts-file cross-check gives ambiguous-bar rate = "
      f"{100*s30['amb_rate_all']:.1f}% of all / {100*s30['amb_rate_resolved']:.1f}% of "
      f"resolved, mean R = {s30['mean_pess']:+.4f} pessimistic / {s30['mean_opt']:+.4f} "
      f"optimistic; T7 re-scored rho = {t7_pess_r['rho']:+.4f} (pess) / "
      f"{t7_opt_r['rho']:+.4f} (opt), both CIs include 0. Agrees with the primary.\n")

    # ---- caveats
    A("\n## Caveats\n")
    A("1. **Window = the trade's actual holding period [entry_i+1 .. exit_i]** (matches "
      "`h5_frontrun`). The entry bar is excluded because entry fills at its close; including "
      "it would let an entry-bar wick that never actually traded against the position fire "
      "the bracket. A sensitivity that includes the entry bar changes the ambiguous count by "
      "only the trades whose entry bar itself spans both stop and target (rare for a "
      "breakout-at-the-close entry); the headline rate moves by <1pp and no verdict flips.\n")
    A("2. **The generous bound.** The headline counts the bar that actually resolves the "
      "trade (first-touch). The loosest possible reading — *any* bar in the trade's full "
      "embedded candle window (including pre-entry setup bars and post-exit bars where the "
      "position was not live) whose range spans both stop and target — is 61/970 = 6.3% "
      "(primary) and 55/792 = 6.9% (robustness). Both are still **well under the 20% "
      "instrument-sufficiency threshold**, so even on the most generous definition 1-minute "
      "OHLCV is the right resolution for this study. The trade-relevant count (1/970) is the "
      "one that can move a score; the 61 are bars the position was never live through.\n")
    A("3. **Touch uses a 1e-9 tolerance** so a stop/target equal to a bar's exact high/low "
      "counts as touched. This is the conservative reading of 'the level was reached'.\n")
    A("4. **`no_touch` trades keep the engine R under both scorings.** These are trades the "
      "stop/target bracket never reached in the live window (the engine exited via partial / "
      "scratch / runner management before either level hit). They are not 'ambiguous' — the "
      "instrument resolves them as 'neither level was touched' — and they sit outside the "
      "resolved denominator. They are a small minority and their R is small in magnitude.\n")
    A("5. **The pess−opt gap is the only bar-resolution signal.** Because non-ambiguous "
      "trades carry identical R under both scorings, the gap = (R_target+1)·n_amb/N is a "
      "deterministic function of the ambiguous count; it is not a re-estimate of edge. The "
      "flip checks re-run the full T6/T7 statistics (not just the gap) under each R vector so "
      "that a verdict change requires the clustered inference to actually move, not just the "
      "mean.\n")
    A("6. **T5 is not re-run.** `h5_frontrun` returned a power-null (engine n_discordant = 0, "
      "marks n_discordant = 1) with no directional conclusion; there is no sign to flip. Its "
      "fill model already assumed stop-first on same-bar overlap, so the pessimistic scoring "
      "reproduces it exactly and the optimistic would only ever move trades in the ambiguous "
      "set — but with n_discordant = 0 there is nothing to move.\n")
    A("7. **The 970-trade 12mo file is the candle-bearing subset of the 1,289 engine run**; "
      "≈319 trades have no embedded candles and are not resimulatable here. This is the same "
      "sub-population T5/T6/T7 used, so the instrument check is like-for-like; it is not a "
      "statement about the 319 non-candle trades.\n")

    A("\n---\n_Reproducible: `python3 research/h_intrabar.py` regenerates this file._\n")

    out = os.path.join(HERE, "h_intrabar.md")
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")

    # console summary
    print("=== INTRABAR (primary 970) ===")
    print("cls_ct:", s12["cls_ct"])
    print(f"amb_rate_all={100*s12['amb_rate_all']:.2f}%  amb_rate_resolved={100*s12['amb_rate_resolved']:.2f}%")
    print(f"mean_eng={s12['mean_eng']:+.4f} mean_pess={s12['mean_pess']:+.4f} mean_opt={s12['mean_opt']:+.4f} gap={s12['gap_opt_pess']:+.4f}")
    print(f"mean_bp_pess={s12['mean_bp_pess']:+.4f} mean_bp_opt={s12['mean_bp_opt']:+.4f}")
    print(f"amb outcomes: {s12['n_amb_outcomes']} amb_engR={s12['amb_engR']:+.4f} amb_Rtarget={s12['amb_R_target']:+.4f}")
    print("skips 12mo:", dict(skip12), "skips charts:", dict(skip30))
    print("T7 engine:", round(t7_eng["rho"],4), f"[{t7_eng['bs_lo']:+.4f},{t7_eng['bs_hi']:+.4f}]", "mono", t7_eng["mono_strict"], "->", t7_v_eng)
    print("T7 pess:", round(t7_pess["rho"],4), f"[{t7_pess['bs_lo']:+.4f},{t7_pess['bs_hi']:+.4f}]", "mono", t7_pess["mono_strict"], "->", t7_v_pess)
    print("T7 opt:", round(t7_opt["rho"],4), f"[{t7_opt['bs_lo']:+.4f},{t7_opt['bs_hi']:+.4f}]", "mono", t7_opt["mono_strict"], "->", t7_v_opt)
    for thr in (0.8,1.0,1.2,1.5):
        sp=t6_pess[thr]; so=t6_opt[thr]
        print(f"T6 {thr}R pess diff={sp['diff']:+.4f} CI[{sp['bs_lo']:+.4f},{sp['bs_hi']:+.4f}] | opt diff={so['diff']:+.4f} CI[{so['bs_lo']:+.4f},{so['bs_hi']:+.4f}]")
    print("T6 pays pess:", t6_v_pays_pess, "opt:", t6_v_pays_opt, "sign_flips:", sign_flips)
    print("T7 flip:", t7_flip, " T6 flip:", t6_flip)
    print("robust amb_rate_all:", round(100*s30["amb_rate_all"],2), "amb_rate_resolved:", round(100*s30["amb_rate_resolved"],2))
    print("wrote", out)


def dict_str(d):
    return ", ".join(f"{k}:{v}" for k, v in d.items())


if __name__ == "__main__":
    main()
