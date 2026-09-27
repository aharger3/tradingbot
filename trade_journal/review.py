"""trade_journal.review -- weekly review report (markdown) from journal.db.

    python -m trade_journal.review                      # last completed ISO week, all modes
    python -m trade_journal.review --week 2026-W38 --mode REPLAY
    python -m trade_journal.review --ingest-acks research/paper_journal/acks_replay.jsonl

Writes research/paper_journal/reviews/<week>[_<mode>].md and prints its path.
Card PNGs are linked relative to that file so it renders in any md viewer.

Honesty rules baked in:
  * "eye value" = mean shadow R of TAKEN cards minus PASSED cards, one-sided
    label-shuffle permutation p (seeded). Shadow R uses the same honest fills
    as the taken trades (next-bar open +1 tick, stop -1 tick, 2R limit).
  * taken mean R gets a one-sided sign-flip p vs 0.
  * the backtest band is the ship-plan in-sample cell (+0.31R, n=105), whose
    OOS was -0.17R -- landing inside the band is necessary, not sufficient.
  * n < 20 prints a small-sample warning; nothing here is an edge claim.
"""
from __future__ import annotations

import argparse
import math
import os
import random
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median
from typing import Optional

from trade_journal.journal import DB_PATH, JOURNAL_DIR, connect, ingest_acks, rows_for_week, time_bucket

# OMEN-SHIP-PLAN-v3 sec 2 (frozen orb1m.py cell, MNQ OR5 10:30 2R, in-sample)
BACKTEST_MEAN_R = 0.31
BACKTEST_N = 105
BACKTEST_SD_R = 1.5   # approx per-trade sd of a -1R/+2R system at 46.7% win
N_PERM = 5000
SMALL_N = 20


def last_completed_week(today: Optional[date] = None) -> str:
    today = today or date.today()
    y, w, _ = (today - timedelta(days=7)).isocalendar()
    return f"{y}-W{w:02d}"


def perm_p_diff(a: list, b: list, n_perm: int = N_PERM, seed: int = 7) -> Optional[float]:
    """One-sided P(mean(a)-mean(b) >= observed) under label shuffle."""
    if len(a) < 1 or len(b) < 1:
        return None
    obs = mean(a) - mean(b)
    pool = list(a) + list(b)
    rng = random.Random(seed)
    k = len(a)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(pool)
        if mean(pool[:k]) - mean(pool[k:]) >= obs - 1e-12:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def signflip_p(x: list, n_perm: int = N_PERM, seed: int = 11) -> Optional[float]:
    """One-sided P(mean >= observed) under random sign flips (H0: mean 0)."""
    if not x:
        return None
    obs = mean(x)
    rng = random.Random(seed)
    hits = sum(1 for _ in range(n_perm)
               if mean(v if rng.random() < 0.5 else -v for v in x) >= obs - 1e-12)
    return (hits + 1) / (n_perm + 1)


def backtest_band(n: int, z: float = 1.645) -> tuple:
    half = z * BACKTEST_SD_R / math.sqrt(max(n, 1))
    return BACKTEST_MEAN_R - half, BACKTEST_MEAN_R + half


def max_consec_losses(rs: list) -> int:
    best = cur = 0
    for r in rs:
        cur = cur + 1 if r < 0 else 0
        best = max(best, cur)
    return best


def _fmt(x, nd=2, signed=True):
    if x is None:
        return "—"
    return f"{x:+.{nd}f}" if signed else f"{x:.{nd}f}"


def _group_table(rows: list, key, title: str) -> list:
    groups: dict = {}
    for r in rows:
        groups.setdefault(key(r), []).append(r)
    out = [f"### by {title}", "| value | cards | taken | taken mean R | shadow mean R (all) |",
           "|---|--:|--:|--:|--:|"]
    for k in sorted(groups, key=str):
        g = groups[k]
        tk = [r["r"] for r in g if r["taken"]]
        sh = [r["shadow_r"] for r in g if r["shadow_r"] is not None]
        out.append(f"| {k} | {len(g)} | {len(tk)} | {_fmt(mean(tk) if tk else None)} | "
                   f"{_fmt(mean(sh) if sh else None)} |")
    return out + [""]


def build_report(rows: list, week: str, mode: Optional[str], review_path: Path,
                 journal_dir: Path) -> str:
    taken = [r for r in rows if r["taken"]]
    passed = [r for r in rows if not r["taken"]]
    tr = [r["r"] for r in taken]
    sessions = sorted({r["session_date"] for r in rows})
    lat = [r["tap_latency_s"] for r in rows if r["tap_latency_s"] is not None]
    L = [f"# OMEN trade journal — {week}" + (f" ({mode})" if mode else ""),
         "", "Paper only. Honest fills (next-bar open +1 tick, stop −1 tick). No orders placed.", ""]
    if not rows:
        return "\n".join(L + ["No cards journaled this week."]) + "\n"

    hit = f"{100 * sum(1 for x in tr if x > 0) / len(tr):.0f}%" if tr else "—"
    usd = sum(r["usd"] or 0 for r in taken)
    L += ["## Scoreboard",
          "| sessions | cards | taken (S ≤120s) | Σ R | mean R | hit % | $ | max consec losses | median tap s |",
          "|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
          f"| {len(sessions)} | {len(rows)} | {len(taken)} | {_fmt(sum(tr))} | "
          f"{_fmt(mean(tr) if tr else None)} | {hit} | {usd:+.2f} | {max_consec_losses(tr)} | "
          f"{_fmt(median(lat) if lat else None, 1, False)} |", ""]

    # vs backtest
    L.append("## vs backtest")
    if tr:
        lo, hi = backtest_band(len(tr))
        inside = lo <= mean(tr) <= hi
        L.append(f"Taken mean {_fmt(mean(tr))}R on n={len(tr)}; backtest cell +{BACKTEST_MEAN_R}R "
                 f"(n={BACKTEST_N}, in-sample; OOS was −0.17R) → 90% band for n={len(tr)}: "
                 f"[{lo:+.2f}, {hi:+.2f}] → **{'inside' if inside else 'OUTSIDE'}**. "
                 f"Sign-flip p (mean>0) = {signflip_p(tr):.3f}.")
    else:
        L.append("No taken trades.")
    if len(tr) < SMALL_N:
        L.append(f"⚠ n={len(tr)} < {SMALL_N}: read as a log, not evidence.")
    L.append("")

    # eye value
    L.append("## Eye value (taken vs passed, shadow R)")
    ts = [r["shadow_r"] for r in taken if r["shadow_r"] is not None]
    ps = [r["shadow_r"] for r in passed if r["shadow_r"] is not None]
    if ts and ps:
        L.append(f"Taken shadow {_fmt(mean(ts))}R (n={len(ts)}) vs passed {_fmt(mean(ps))}R (n={len(ps)}) "
                 f"→ eye **{_fmt(mean(ts) - mean(ps))}R**, permutation p = {perm_p_diff(ts, ps):.3f} "
                 f"({N_PERM} label shuffles, one-sided).")
    else:
        L.append(f"Need both taken and passed cards with shadow R (have {len(ts)} / {len(ps)}).")
    reasons: dict = {}
    for r in passed:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    if reasons:
        L.append("Passed because: " + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items())) + ".")
    L.append("")

    L.append("## Tags")
    L += _group_table(rows, lambda r: r["austin_grade"], "his grade (S tag)")
    L += _group_table(rows, lambda r: r["engine_grade"], "engine grade")
    L += _group_table(rows, lambda r: r["setup"], "setup")
    L += _group_table(rows, lambda r: r["instrument"], "instrument")
    L += _group_table(rows, lambda r: time_bucket(r["minutes_after_open"]), "time")
    L += _group_table(rows, lambda r: r["direction"], "direction")

    L += ["## Every card", "| date | time | inst | dir | eng | his | tap s | taken | R | shadow R | card |",
          "|---|---|---|---|---|---|--:|---|--:|--:|---|"]
    for r in rows:
        if r["screenshot"]:
            rel = os.path.relpath(journal_dir / r["screenshot"], review_path.parent).replace(os.sep, "/")
            shot = f"[png]({rel})"
        else:
            shot = "missing"
        L.append(f"| {r['session_date']} | {r['signal_time'] or '—'} | {r['instrument']} | {r['direction']} | "
                 f"{r['engine_grade'] or '—'} | {r['austin_grade']} | "
                 f"{_fmt(r['tap_latency_s'], 1, False)} | {'yes' if r['taken'] else r['reason']} | "
                 f"{_fmt(r['r'])} | {_fmt(r['shadow_r'])} | {shot} |")
    L.append("")
    missing = sum(1 for r in rows if not r["screenshot"])
    if missing:
        L.append(f"⚠ {missing} card(s) have no archived screenshot.")
    return "\n".join(L) + "\n"


def write_review(week: str, mode: Optional[str] = None, db_path: Path = DB_PATH,
                 out_dir: Optional[Path] = None) -> Path:
    db_path = Path(db_path)
    journal_dir = db_path.parent
    out_dir = Path(out_dir) if out_dir else journal_dir / "reviews"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (f"{week}_{mode}.md" if mode else f"{week}.md")
    con = connect(db_path)
    try:
        rows = rows_for_week(con, week, mode)
    finally:
        con.close()
    path.write_text(build_report(rows, week, mode, path, journal_dir), encoding="utf-8")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", default=None, help="YYYY-Www; default = last completed ISO week")
    ap.add_argument("--mode", default=None, help="REPLAY | PAPER | LIVE_PAPER; default = all")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--ingest-acks", default=None, help="backfill from an acks*.jsonl first")
    ap.add_argument("--chart-dir", default=str(JOURNAL_DIR.parents[1] / "eye_card" / "sent_charts"))
    args = ap.parse_args(argv)
    if args.ingest_acks:
        con = connect(Path(args.db))
        n = ingest_acks(con, Path(args.ingest_acks), Path(args.chart_dir), mode=args.mode or "REPLAY",
                        journal_dir=Path(args.db).parent)
        con.close()
        print(f"ingested {n} rows")
    week = args.week or last_completed_week()
    print(write_review(week, args.mode, Path(args.db), args.out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
