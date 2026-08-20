"""OMEN 5.2 -- T5 scale-out runner.

Replays all six exit policies (the five from ``research/exit_lab.py`` plus an
``adaptive`` sixth that uses ``research/trend_gate.is_trending`` to pick
``30_30_30_10`` when trending and ``50_20_20_10`` when not) over **two** corpora
kept separate in the output:

  A. Austin's 64 marked entries (``research/marks/*.jsonl``) -- his entry bar,
     his stop, machine exits.
  B. the engine's backtest trades (``backtest_charts.json`` -- see
     ``research/v52_paths.md``) -- the engine's entries and stops, machine
     exits. This corpus carries a year, so it owns the yearly number.

Writes ``research/v52_scaleout_results.md`` (one table per corpus + four
summary lines taken from corpus B) and ``research/v52_scaleout_results.json``
(per-trade R per policy so 5.3 does not recompute).

Imported, not reimplemented: ``research/exit_lab.py`` (policy functions) and
``research/trend_gate.py`` (``is_trending``).
"""

from __future__ import annotations
import json
import os
import statistics
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import research.exit_lab as exit_lab  # noqa: E402
import research.trend_gate as trend_gate  # noqa: E402
from research.levels import load_rth_bars  # noqa: E402

POLICY_IDS = ["flat_1r", "flat_2r", "hod_only", "30_30_30_10", "50_20_20_10", "adaptive"]

# Annualisation: project the corpus's own trade rate onto a 252-trading-day
# year. trades_per_year = N_trades * 252 / N_distinct_trading_days_in_corpus.
TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# trade + bar sourcing
# ---------------------------------------------------------------------------

def bars_for(trade):
    """Bars for a trade dict. Primary: ``load_rth_bars`` from ``data_archive``
    (the verified loader every other row uses). Fallback: the embedded
    ``candles`` field on backtest trades, which the path map confirms carries
    that trade's 1-min bars in the same ``{t,o,h,l,c}`` shape."""
    bars = load_rth_bars(trade["symbol"], trade["date"])
    if bars:
        return bars
    cand = trade.get("candles")
    return cand or None


def run_policies(bars, entry_i, entry, stop, side, symbol, date):
    """Realised R per policy (incl. adaptive) for one trade. Calls the lab's
    policy functions directly; adaptive picks between two scale-outs via
    ``trend_gate.is_trending``."""
    out = {}
    if not bars or entry is None or stop is None or entry_i >= len(bars):
        for pid in POLICY_IDS:
            out[pid] = None
        return out
    for pid in POLICY_IDS:
        if pid == "adaptive":
            trending = trend_gate.is_trending(symbol, date, entry_i, side)
            sub = "30_30_30_10" if trending else "50_20_20_10"
            out["adaptive"] = exit_lab.POLICIES[sub](bars, entry_i, entry, stop, side)
            out["_adaptive_sub"] = sub
        else:
            out[pid] = exit_lab.POLICIES[pid](bars, entry_i, entry, stop, side)
    return out


# ---------------------------------------------------------------------------
# corpora
# ---------------------------------------------------------------------------

def corpus_a_trades():
    """Austin's 64 marked entries. Keys already match what the lab expects
    (``entry_p``/``stop_p``/``side``); fall back to bar close / None."""
    rows = []
    for m in exit_lab.load_marks():
        rows.append({
            "corpus": "A",
            "symbol": m["symbol"],
            "date": m["date"],
            "side": m["side"],
            "entry_i": m["entry_i"],
            "entry": m.get("entry_p") if m.get("entry_p") is not None else m.get("entry"),
            "stop": m.get("stop_p") if m.get("stop_p") is not None else m.get("stop"),
            "source": "austin_marks",
        })
    return rows


def corpus_b_trades():
    """The engine's backtest trades from ``backtest_charts.json`` (path map).
    Normalise ``day``->``date`` and ``direction`` (call/put)->``side`` (L/S).
    Keep the embedded ``candles`` for the bar-fallback path."""
    rows = []
    ledger = json.load(open(os.path.join(_REPO_ROOT, "backtest_charts.json"), encoding="utf-8"))
    for t in ledger:
        side = "L" if str(t["direction"]).lower().startswith("c") else "S"
        rows.append({
            "corpus": "B",
            "symbol": t["symbol"],
            "date": t["day"],
            "side": side,
            "entry_i": t["entry_i"],
            "entry": t["entry"],
            "stop": t["stop"],
            "source": "backtest_engine",
            "candles": t.get("candles"),
        })
    return rows


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def metrics_for(rows, policy_id):
    """Aggregate one policy over one corpus's per-trade rows."""
    rs = [r["results"][policy_id] for r in rows if r["results"].get(policy_id) is not None]
    if not rs:
        return None
    mean_r = statistics.mean(rs)
    median_r = statistics.median(rs)
    wins = sum(1 for r in rs if r > 0)
    win_rate = wins / len(rs)
    worst = min(rs)
    # max consecutive losers in trade order
    max_run = run = 0
    for r in rs:
        if r < 0:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    # annualise at the corpus's own trade rate
    days = {r["date"] for r in rows}
    tpy = len(rs) * TRADING_DAYS_PER_YEAR / len(days) if days else 0.0
    annual = mean_r * tpy
    return {
        "mean_r": mean_r,
        "median_r": median_r,
        "win_rate": win_rate,
        "worst_trade": worst,
        "max_consec_losers": max_run,
        "mean_r_annual": annual,
        "n": len(rs),
        "trades_per_year": tpy,
        "distinct_days": len(days),
    }


def fmt(x, p=4):
    return f"{x:.{p}f}" if isinstance(x, (int, float)) else str(x)


def table(rows, title):
    """Render one corpus's policy table."""
    lines = [f"## {title}", ""]
    lines.append("Counts N = trades with a realised R for that policy. "
                 "Mean R annualised = mean_R * trades_per_year, where "
                 "trades_per_year = N * 252 / distinct_trading_days_in_corpus "
                 "(the corpus's own trade rate projected onto a 252-day year).")
    lines.append("")
    lines.append("| policy | N | mean R | median R | win rate | worst trade | "
                 "max consec losers | mean R annualised |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for pid in POLICY_IDS:
        m = metrics_for(rows, pid)
        if m is None:
            lines.append(f"| {pid} | 0 | - | - | - | - | - | - |")
            continue
        lines.append(
            f"| {pid} | {m['n']} | {fmt(m['mean_r'])} | {fmt(m['median_r'])} | "
            f"{m['win_rate']:.4f} | {fmt(m['worst_trade'])} | "
            f"{m['max_consec_losers']} | {fmt(m['mean_r_annual'], 2)} |"
        )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    corpora = [("A", corpus_a_trades(), "Corpus A -- Austin's 64 marked entries "
                "(his entry bar, his stop, machine exits)"),
               ("B", corpus_b_trades(), "Corpus B -- the engine's backtest trades "
                "(engine entries & stops, machine exits; carries the year)")]

    # replay
    for label, rows, _title in corpora:
        for r in rows:
            bars = bars_for(r)
            r["results"] = run_policies(
                bars, r["entry_i"], r.get("entry"), r.get("stop"),
                r["side"], r["symbol"], r["date"],
            )

    # ---- markdown ----
    out = ["# OMEN 5.2 -- T5 scale-out results", ""]
    out.append("Six policies replayed over two corpora. The five fixed policies "
               "live in `research/exit_lab.py`; the sixth (`adaptive`) picks "
               "`30_30_30_10` when `research/trend_gate.is_trending` is true and "
               "`50_20_20_10` otherwise. Per-trade R is dumped to "
               "`research/v52_scaleout_results.json`.")
    out.append("")
    for label, rows, title in corpora:
        out.append(table(rows, title))
        out.append("")

    # four summary lines, taken from corpus B
    b_rows = corpora[1][1]
    best_pid = max(POLICY_IDS, key=lambda p: (metrics_for(b_rows, p) or {"mean_r": -1e9})["mean_r"])
    best_mean = metrics_for(b_rows, best_pid)["mean_r"]
    adapt_mean = metrics_for(b_rows, "adaptive")["mean_r"]
    base_mean = metrics_for(b_rows, "flat_1r")["mean_r"]
    out.append("```")
    out.append(f"best_policy: {best_pid}")
    out.append(f"best_policy_mean_r: {best_mean:.6f}")
    out.append(f"adaptive_mean_r: {adapt_mean:.6f}")
    out.append(f"baseline_flat_1r_mean_r: {base_mean:.6f}")
    out.append("```")
    out.append("")

    md_path = os.path.join(os.path.dirname(__file__), "v52_scaleout_results.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    # ---- json: per-trade results ----
    dump = {"corpus_a": [], "corpus_b": []}
    for label, rows, _title in corpora:
        key = "corpus_a" if label == "A" else "corpus_b"
        for r in rows:
            res = r["results"]
            rec = {
                "corpus": label,
                "symbol": r["symbol"],
                "date": r["date"],
                "side": r["side"],
                "entry_i": r["entry_i"],
                "entry": r.get("entry"),
                "stop": r.get("stop"),
                "source": r.get("source"),
                "results": {pid: res.get(pid) for pid in POLICY_IDS},
            }
            if "_adaptive_sub" in res:
                rec["adaptive_sub"] = res["_adaptive_sub"]
            dump[key].append(rec)
    json_path = os.path.join(os.path.dirname(__file__), "v52_scaleout_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dump, f, indent=1)

    # console summary
    for label, rows, _title in corpora:
        print(f"== corpus {label}: {len(rows)} trades ==")
        for pid in POLICY_IDS:
            m = metrics_for(rows, pid)
            if m:
                print(f"  {pid:16s} mean={m['mean_r']:+.4f} med={m['median_r']:+.4f} "
                      f"win={m['win_rate']:.3f} worst={m['worst_trade']:+.4f} "
                      f"mcl={m['max_consec_losers']} ann={m['mean_r_annual']:+.2f}")
    print(f"best_policy: {best_pid} ({best_mean:+.6f})")
    print(f"adaptive: {adapt_mean:+.6f}  flat_1r: {base_mean:+.6f}")


if __name__ == "__main__":
    main()
