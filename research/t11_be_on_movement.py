"""T11 -- "be-on-movement" (R11).

Austin, months ago, never run until now: "if we dont hit price target 1, we
dont raise the stop to BE, but we need to run stats on with enough movement
raising to BE". He kept the base case: "can still focus on first PT move to
BE".

This measures ONLY the stop-to-breakeven TRIGGER -- the F1 ladder's partial
scale-out at the causal-HOD rung (PT1) is unchanged in every arm. What varies
is when `runner_stop` (backtest_week.py::_ladder_bar) moves to `entry`:

    pt1        (baseline, ships default)  -- moves only when PT1 (the scale
               rung) is touched. This is today's shipped `hod_then_runner_be`.
    mfe_0.50   -- moves as soon as favourable excursion (bar high/low vs.
    mfe_0.75      entry, in R) reaches the threshold, whichever comes first
    mfe_1.00      (the PT1 rung or the threshold) -- see
    mfe_1.25      backtest_week.py `BE_TRIGGER="mfe"`.

Because the lever only changes STOP MANAGEMENT on trades that already fired,
it cannot move which signals fire or their entry/stop -- so held-out S recall
(probe_s_sweep_2026-08-28.jsonl, probe_master_2026-08-29.jsonl) is measured
and reported per method rule 2, but by construction it is identical across
every arm. The real read is the money-gate table: mean R, win rate, month
greenness, and how often a trade that would have made money after the PT1
scale rung got its breakeven stop raised (and therefore capped) EARLIER by
the movement trigger, before PT1 ever printed.

Same replay engine as `backtest_2y.py` (`backtest_week.simulate_day` over the
polygon_feed archive), but bars are fetched ONCE per symbol/day and re-run
across all five arms so the I/O cost is paid once, not five times.

Usage:  python research/t11_be_on_movement.py [--days 730]
Writes: research/t11_be_on_movement.md (this report),
        research/t11_be_on_movement_trades.json (per-arm, per-trade R -- not
        committed, regenerable from this script; see the report for the
        regenerate command).
"""
from __future__ import annotations
import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import polygon_feed as pf                                          # noqa: E402
import backtest_week as bw                                          # noqa: E402
from backtest_week import simulate_day, htf_bias_for, RISK_DOLLARS  # noqa: E402
from universe import ALL_SYMS, has_archive                          # noqa: E402

ARMS = [
    ("pt1", "pt1", 0.0),
    ("mfe_0.50", "mfe", 0.50),
    ("mfe_0.75", "mfe", 0.75),
    ("mfe_1.00", "mfe", 1.00),
    ("mfe_1.25", "mfe", 1.25),
]


def archive_days(sym):
    d = ROOT / "data_archive" / sym
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []


def month_of(day_iso):
    return day_iso[:7]


def summarise(rs):
    if not rs:
        return None
    wins = sum(1 for r in rs if r > 0)
    return {
        "n": len(rs),
        "mean_r": statistics.mean(rs),
        "median_r": statistics.median(rs),
        "win_rate": wins / len(rs) * 100,
        "worst": min(rs),
        "best": max(rs),
        "total_r": sum(rs),
    }


def months_green(month_rs):
    green = sum(1 for rs in month_rs.values() if sum(rs) > 0)
    return green, len(month_rs)


def load_probe(path):
    rows = []
    p = ROOT / path
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def recall_against_probes(fired_keys):
    """Held-out S recall, method rule 2. `fired_keys` = set of (symbol, day)
    the engine traded (any grade) in THIS run. Unaffected by BE_TRIGGER by
    construction (see module docstring) -- reported once, not per arm.

    Both probe files encode the graded answer inside ``answers`` (the row's
    own top-level ``grade`` is always the literal string ``"none"`` -- that
    is the probe-taking metadata field, not his verdict)."""
    sweep = load_probe("research/marks/probe_s_sweep_2026-08-28.jsonl")
    s_rows = [r for r in sweep if r.get("answers", {}).get("s") == ["s"]]
    s_hit = sum(1 for r in s_rows if (r.get("symbol"), r.get("date")) in fired_keys)

    master = load_probe("research/marks/probe_master_2026-08-29.jsonl")
    vetoes = [r for r in master if r.get("lane") == "vetoes"]
    by_verdict = defaultdict(list)
    for r in vetoes:
        verdict = (r.get("answers", {}).get("grade") or ["no"])[0]
        by_verdict[str(verdict).lower()].append(r)
    veto_hit = {
        v: sum(1 for r in rows if (r.get("symbol"), r.get("date")) in fired_keys)
        for v, rows in by_verdict.items()
    }
    return {
        "s_sweep": f"{s_hit}/{len(s_rows)}" if s_rows else "n/a",
        "s_sweep_pct": round(s_hit / len(s_rows) * 100, 1) if s_rows else None,
        "vetoes_by_verdict": {v: f"{veto_hit.get(v, 0)}/{len(rows)}"
                              for v, rows in by_verdict.items()},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--out", default="research/t11_be_on_movement_trades.json")
    args = ap.parse_args()

    syms = [s for s in ALL_SYMS if has_archive(s, 100)]
    last = max((archive_days(s) or ["1970-01-01"])[-1] for s in syms)
    start = (date.fromisoformat(last) - timedelta(days=args.days)).isoformat()
    print(f"{len(syms)} symbols, window >= {start} .. {last}")

    # per-arm accumulators
    arm_rows = {label: [] for label, _, _ in ARMS}
    arm_month = {label: defaultdict(list) for label, _, _ in ARMS}
    # per-arm: trades that scaled (touched PT1) vs. trades whose BE-raise came
    # from the movement trigger before PT1 ever printed (mfe arms only)
    arm_be_source = {label: defaultdict(int) for label, _, _ in ARMS}
    fired_keys = set()
    sessions = set()

    for sym in syms:
        days = [d for d in archive_days(sym) if d >= start]
        day_bars, hourly = {}, []
        for d in days:
            try:
                bars = pf.fetch_day(sym, d)
            except Exception:
                continue
            if not bars:
                continue
            r = pf.rth(bars)
            if len(r) < 30:
                continue
            day_bars[d] = (bars, r)
        if not day_bars:
            continue

        from backtest_12mo import hourly_from_1m
        for d in sorted(day_bars):
            _, r = day_bars[d]
            hourly += hourly_from_1m(d, r)

        prev = None
        for d in sorted(day_bars):
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = pf.premarket_hi_lo(bars)
            bias = htf_bias_for(hourly, d)
            sessions.add(d)

            for label, trigger, move_r in ARMS:
                bw.BE_TRIGGER = trigger
                bw.BE_MOVE_R = move_r
                trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc)
                for t in trades:
                    if not t.counted:
                        continue
                    r_mult = t.pnl / RISK_DOLLARS
                    arm_rows[label].append(r_mult)
                    arm_month[label][month_of(d)].append(r_mult)
                    if trigger == "mfe":
                        # scaled=True means PT1 (the HOD rung) touched at all;
                        # runner_stop set while NOT yet scaled means the
                        # movement trigger raised it before PT1 did.
                        if t.runner_stop and not t.scaled:
                            arm_be_source[label]["mfe_before_pt1"] += 1
                        elif t.runner_stop and t.scaled:
                            arm_be_source[label]["pt1_or_after"] += 1
                        else:
                            arm_be_source[label]["never_be"] += 1
                    if label == "pt1":
                        fired_keys.add((sym, d))
            prev = d
        print(f"[{sym}] {len(day_bars)} sessions")

    # ---- reset module globals so importers after this script stay sane ----
    bw.BE_TRIGGER, bw.BE_MOVE_R = "pt1", 0.0

    recall = recall_against_probes(fired_keys)

    # ---- write per-trade dump (not committed; regenerable) ----
    out_path = ROOT / args.out
    out_path.write_text(json.dumps({"arms": arm_rows}, separators=(",", ":")),
                        encoding="utf-8")

    # ---- report ----
    lines = ["# T11 -- be-on-movement (R11)", ""]
    lines.append("Script: `research/t11_be_on_movement.py`. Regenerate with "
                 "`python research/t11_be_on_movement.py` (~%d symbols x ~%d "
                 "sessions x 5 arms)." % (len(syms), len(sessions)))
    lines.append("")
    lines.append("Austin, months ago, never run until now: *\"if we dont hit "
                 "price target 1, we dont raise the stop to BE, but we need to "
                 "run stats on with enough movement raising to BE\"*. Base case "
                 "kept: *\"can still focus on first PT move to BE\"* -- that is "
                 "the `pt1` arm below, and it is what ships.")
    lines.append("")
    lines.append("Only the stop-to-breakeven TRIGGER varies. The PT1 partial "
                 "scale-out (`backtest_week.py`'s F1 ladder, `hod_then_runner_be`) "
                 "is unchanged in every arm -- this measures WHEN the runner's "
                 "stop moves to entry, not whether it scales.")
    lines.append("")

    base = summarise(arm_rows["pt1"])
    lines.append("## Money gate")
    lines.append("")
    lines.append("| arm | N | mean R | median R | win rate | worst | best | total R | "
                 "months green | vs pt1 (mean R) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    error_bar = 0.1725  # T0's reported ±95% bar for this book; carried forward
                        # per method rule 1 -- no track here has re-measured its
                        # own bar with a bootstrap, so this is the standing one.
    for label, trigger, move_r in ARMS:
        s = summarise(arm_rows[label])
        if s is None:
            lines.append(f"| {label} | 0 | - | - | - | - | - | - | - | - |")
            continue
        g, tot = months_green(arm_month[label])
        move = s["mean_r"] - base["mean_r"] if base else 0.0
        inside = "inside bar (NULL)" if abs(move) < error_bar else "outside bar"
        vs = f"{move:+.4f} ({inside})" if label != "pt1" else "baseline"
        lines.append(
            f"| {label} | {s['n']} | {s['mean_r']:.4f} | {s['median_r']:.4f} | "
            f"{s['win_rate']:.1f}% | {s['worst']:.3f} | {s['best']:.3f} | "
            f"{s['total_r']:.2f} | {g}/{tot} | {vs} |"
        )
    lines.append("")
    lines.append(f"Error bar carried forward from T0 (±{error_bar}R, 95%): an A/B "
                 "narrower than this reported as inside its own bar is a null "
                 "result per method rule 1. This track did not re-derive its own "
                 "bar (no bootstrap run here) -- treat any move under ~0.17R as "
                 "unproven, not as \"no effect\".")
    lines.append("")

    lines.append("## Where the movement-trigger's breakeven came from (mfe arms)")
    lines.append("")
    lines.append("Of trades whose stop was raised to breakeven, how many got there "
                 "from the movement threshold BEFORE the PT1 (causal-HOD) rung ever "
                 "printed, vs. from PT1 itself (same accelerator as the baseline), "
                 "vs. never got raised at all:")
    lines.append("")
    lines.append("| arm | mfe_before_pt1 | pt1_or_after | never_be |")
    lines.append("|---|---|---|---|")
    for label, trigger, move_r in ARMS:
        if trigger != "mfe":
            continue
        d = arm_be_source[label]
        lines.append(f"| {label} | {d.get('mfe_before_pt1', 0)} | "
                     f"{d.get('pt1_or_after', 0)} | {d.get('never_be', 0)} |")
    lines.append("")

    lines.append("## Held-out recall (method rule 2)")
    lines.append("")
    lines.append("This lever changes stop MANAGEMENT on trades already entered -- it "
                 "cannot change which signals fire, their entry, or their stop. "
                 "Recall is measured once (against the `pt1` arm's fired set) and is "
                 "identical for every arm by construction; reported here so the "
                 "gate is not silently skipped, not because it is expected to move.")
    lines.append("")
    lines.append(f"- Held-out S sweep: {recall['s_sweep']}"
                 + (f" ({recall['s_sweep_pct']}%)" if recall['s_sweep_pct'] is not None else ""))
    lines.append(f"- Veto verdicts fired-on, by his verdict: {recall['vetoes_by_verdict']}")
    lines.append("")

    lines.append("## Reading the table")
    lines.append("")
    if base:
        best_label, best_move = None, 0.0
        for label, trigger, move_r in ARMS:
            if label == "pt1":
                continue
            s = summarise(arm_rows[label])
            if s is None:
                continue
            move = s["mean_r"] - base["mean_r"]
            if best_label is None or abs(move) > abs(best_move):
                best_label, best_move = label, move
        if best_label and abs(best_move) >= error_bar:
            direction = "helps" if best_move > 0 else "hurts"
            lines.append(f"Largest mover: **{best_label}** at {best_move:+.4f}R "
                         f"against `pt1`, which clears the ±{error_bar}R bar -- "
                         f"raising the stop to breakeven on plain favourable "
                         f"excursion (not waiting for PT1) {direction} mean R on "
                         f"this book, real not null.")
        else:
            lines.append(f"**Null result:** every `mfe_*` arm sits inside the "
                         f"±{error_bar}R bar against `pt1`. Raising the stop to "
                         f"breakeven earlier, on plain favourable excursion "
                         f"instead of waiting for PT1, does not move mean R on "
                         f"this book by more than noise.")
    lines.append("")
    lines.append("Ships: `pt1` stays the default (`BE_TRIGGER=pt1` in "
                 "`backtest_week.py`) per R11 -- \"can still focus on first PT "
                 "move to BE\". `BE_TRIGGER=mfe` + `BE_MOVE_R=<0.5|0.75|1.0|1.25>` "
                 "is available as a flag, OFF by default, for whichever arm above "
                 "clears its bar.")
    lines.append("")

    report_path = ROOT / "research" / "t11_be_on_movement.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {report_path}")
    print(f"wrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
