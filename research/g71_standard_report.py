"""The one standard report. Every future measurement publishes THESE numbers.

One book in, one page out. No track IDs, no code names, no jargon in the output:
Austin reads the page cold and knows whether OMEN is closer to done.

The page always answers four questions in the same order, with the same numbers,
so two runs can be laid side by side:

  1. Did it make money?      dollars, average per trade, win rate
  2. Did it hold up?         months green, weeks green, worst drawdown
  3. Did it find his trades? recall on his best days, and the false-fire cost
  4. How busy is it?         trades per market day, total trades

Inputs
  --book     a backtest_2y.py book (research/bt2y_trades.json shape:
             {"meta": {...}, "trades": [ {...}, ... ]}). Every row is a signal;
             rows with traded=true are the book.
  --recall   the held-out recall JSON written by research/t0_heldout_recall.py.
             Optional: without it section 3 prints "not measured this run"
             rather than a stale number.
  --against  a previous run's sidecar JSON, to print a "what moved" column.

Outputs
  --out      the markdown page (default research/omen_report.md)
  --json     the machine-readable sidecar (default research/omen_report.json),
             which is what a later run passes to --against.

Nothing here re-implements a fill, a stop, or a grade. It only counts rows a
book already contains. R is the result; dollars are the sizing skin at
1R = $1,000.

Usage:
  python research/g71_standard_report.py
  python research/g71_standard_report.py --book research/bt2y_trades.json \
      --recall research/t0_heldout_recall.json --against research/omen_report.json
"""
from __future__ import annotations
import argparse, datetime, json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# The three gates, in Austin's words. These are the only targets on the page.
GATE_MEAN_R = 2.0          # average per trade
GATE_WIN_RATE = 55.0       # percent
GATE_RECALL = 90.0         # percent of his best days the engine must fire on
RISK_DOLLARS = 1000.0      # 1R


# ---------------------------------------------------------------- counting

def load_book(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    meta = data.get("meta", {})
    traded = [t for t in data["trades"] if t.get("traded")]
    return meta, traded, len(data["trades"])


def iso_week(day):
    y, m, d = (int(x) for x in day.split("-"))
    iy, iw, _ = datetime.date(y, m, d).isocalendar()
    return f"{iy}-W{iw:02d}"


def bucket_sums(traded, key):
    out = defaultdict(float)
    for t in traded:
        out[key(t)] += t["r"]
    return dict(out)


def max_drawdown(traded):
    """Deepest peak-to-trough fall of the running R total, trades in time order.

    Returned positive: 32.43 means the account gave back 32.43 R (=$32,430)
    from its own high-water mark before making a new one.
    """
    seq = sorted(traded, key=lambda t: (t.get("day", ""), t.get("et", "")))
    peak = run = worst = 0.0
    for t in seq:
        run += t["r"]
        peak = max(peak, run)
        worst = max(worst, peak - run)
    return worst


def measure(book_path, recall_path=None):
    meta, traded, n_signals = load_book(book_path)
    n = len(traded)
    if not n:
        raise SystemExit(f"{book_path}: no traded rows")

    total_r = sum(t["r"] for t in traded)
    dollars = sum(t.get("pnl", t["r"] * RISK_DOLLARS) for t in traded)
    wins = sum(1 for t in traded if t.get("out") == "win")
    losses = sum(1 for t in traded if t.get("out") == "loss")
    scratches = n - wins - losses
    decided = wins + losses

    months = bucket_sums(traded, lambda t: t.get("ym") or t["day"][:7])
    weeks = bucket_sums(traded, lambda t: iso_week(t["day"]))
    sessions = meta.get("sessions") or len({t["day"] for t in traded})

    gross_win = sum(t["r"] for t in traded if t["r"] > 0)
    gross_loss = -sum(t["r"] for t in traded if t["r"] < 0)

    m = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "book": os.path.relpath(book_path, ROOT).replace("\\", "/"),
        "book_generated": meta.get("generated"),
        "first_day": meta.get("first") or min(t["day"] for t in traded),
        "last_day": meta.get("last") or max(t["day"] for t in traded),
        "sessions": sessions,
        "symbols": len(meta.get("symbols", [])) or len({t["sym"] for t in traded}),
        "signals_seen": n_signals,
        "trades": n,
        "dollars": round(dollars, 2),
        "total_r": round(total_r, 4),
        "mean_r": round(total_r / n, 4),
        "win_rate_pct": round(100.0 * wins / decided, 2) if decided else 0.0,
        "wins": wins, "losses": losses, "scratches": scratches,
        "profit_factor": round(gross_win / gross_loss, 4) if gross_loss else None,
        "months_total": len(months),
        "months_green": sum(1 for v in months.values() if v > 0),
        "weeks_total": len(weeks),
        "weeks_green": sum(1 for v in weeks.values() if v > 0),
        "max_drawdown_r": round(max_drawdown(traded), 4),
        "trades_per_day": round(n / sessions, 3) if sessions else None,
        "best_trade_r": round(max(t["r"] for t in traded), 4),
        "worst_trade_r": round(min(t["r"] for t in traded), 4),
        "month_r": {k: round(v, 2) for k, v in sorted(months.items())},
        "worst_month": min(months.items(), key=lambda kv: kv[1]) if months else None,
    }

    if recall_path and os.path.exists(recall_path):
        r = json.load(open(recall_path, encoding="utf-8"))
        s = r.get("sweep", {})
        v = r.get("vetoes", {})
        m["recall"] = {
            "source": os.path.relpath(recall_path, ROOT).replace("\\", "/"),
            "set": s.get("set"),
            "best_days": s.get("n_S"),
            "fired_on_best_days": s.get("fired_on_S"),
            "recall_pct": s.get("recall_pct"),
            "refused_days": s.get("n_no"),
            "fired_on_refused_days": s.get("fired_on_no"),
            "precision_pct": s.get("precision_pct"),
            "veto_best_days": (v.get("his_S", 0) or 0) + (v.get("his_A", 0) or 0),
            "veto_fired": (v.get("fired_on_his_S", 0) or 0)
                          + (v.get("fired_on_his_A", 0) or 0),
        }
    else:
        m["recall"] = None
    return m


# ---------------------------------------------------------------- rendering

def money(d):
    return f"-${abs(d):,.0f}" if d < 0 else f"${d:,.0f}"


def signed(x, places=4):
    return f"{x:+.{places}f}"


def move(now, before, places=4, pct=False):
    if before is None:
        return "—"
    d = now - before
    unit = " pts" if pct else ""
    if abs(d) < 10 ** -places:
        return "no change"
    return f"{d:+.{places}f}{unit}"


def render(m, prev=None):
    p = prev or {}
    L = []
    a = L.append

    a(f"# OMEN — the book, as of {m['generated'][:10]}")
    a("")
    a(f"Every trade the engine would have taken over {m['sessions']} market days, "
      f"{m['first_day']} to {m['last_day']}, across {m['symbols']} symbols. "
      f"Risk on every trade is ${RISK_DOLLARS:,.0f}. "
      f"\"R\" is that $1,000: +2R is +$2,000.")
    a("")
    a(f"It looked at **{m['signals_seen']:,}** setups and took **{m['trades']:,}** of them.")
    if prev:
        a("")
        a(f"Compared against the run of {p.get('generated', '?')[:10]} "
          f"(`{p.get('book', '?')}`).")
    a("")

    # 1
    a("## 1. Did it make money?")
    a("")
    a("| | this run | needs to be | there yet? | moved |")
    a("|---|---:|---:|:--:|---:|")
    a(f"| Money made | **{money(m['dollars'])}** | — | — | "
      f"{money(m['dollars'] - p['dollars']) if 'dollars' in p else '—'} |")
    a(f"| Average made per trade | **{signed(m['mean_r'], 2)}R** "
      f"({money(m['mean_r'] * RISK_DOLLARS)}) | +2.00R | "
      f"{'YES' if m['mean_r'] >= GATE_MEAN_R else 'no'} | "
      f"{move(m['mean_r'], p.get('mean_r'), 2)} |")
    a(f"| Win rate | **{m['win_rate_pct']:.1f}%** | 55.0% | "
      f"{'YES' if m['win_rate_pct'] >= GATE_WIN_RATE else 'no'} | "
      f"{move(m['win_rate_pct'], p.get('win_rate_pct'), 1, pct=True)} |")
    a("")
    a(f"{m['wins']:,} winners, {m['losses']:,} losers, {m['scratches']:,} closed flat. "
      f"Best trade {signed(m['best_trade_r'], 2)}R, worst {signed(m['worst_trade_r'], 2)}R. "
      + (f"It makes ${m['profit_factor']:.2f} for every $1.00 it loses."
         if m['profit_factor'] else ""))
    a("")

    # 2
    a("## 2. Did it hold up?")
    a("")
    a("| | this run | needs to be | there yet? | moved |")
    a("|---|---:|---:|:--:|---:|")
    a(f"| Months in profit | **{m['months_green']} of {m['months_total']}** | "
      f"all {m['months_total']} | "
      f"{'YES' if m['months_green'] == m['months_total'] else 'no'} | "
      f"{move(m['months_green'], p.get('months_green'), 0)} |")
    a(f"| Weeks in profit | **{m['weeks_green']} of {m['weeks_total']}** "
      f"({100.0 * m['weeks_green'] / m['weeks_total']:.0f}%) | — | — | "
      f"{move(m['weeks_green'], p.get('weeks_green'), 0)} |")
    a(f"| Worst run of losses | **{m['max_drawdown_r']:.1f}R** "
      f"({money(-m['max_drawdown_r'] * RISK_DOLLARS)}) | smaller is better | — | "
      f"{move(m['max_drawdown_r'], p.get('max_drawdown_r'), 1)} |")
    a("")
    if m["worst_month"]:
        wm, wr = m["worst_month"]
        a(f"Worst month was {wm} at {signed(wr, 2)}R ({money(wr * RISK_DOLLARS)}). "
          f"\"Worst run of losses\" is how far the account fell from its own high "
          f"point before making a new one.")
    a("")

    # 3
    a("## 3. Did it find his trades?")
    a("")
    if m["recall"]:
        r = m["recall"]
        pr = (p.get("recall") or {})
        a("| | this run | needs to be | there yet? | moved |")
        a("|---|---:|---:|:--:|---:|")
        a(f"| Fires on the days he graded best | "
          f"**{r['fired_on_best_days']} of {r['best_days']} "
          f"({r['recall_pct']:.1f}%)** | 90% | "
          f"{'YES' if (r['recall_pct'] or 0) >= GATE_RECALL else 'no'} | "
          f"{move(r['recall_pct'], pr.get('recall_pct'), 1, pct=True)} |")
        a(f"| Also fires on days he refused | "
          f"{r['fired_on_refused_days']} of {r['refused_days']} "
          f"({100.0 * r['fired_on_refused_days'] / r['refused_days']:.1f}%) | "
          f"fewer is better | — | — |")
        a(f"| Of the setups it saw and threw away, how many he wanted | "
          f"{r['veto_fired']} of {r['veto_best_days']} | all of them | "
          f"{'YES' if r['veto_best_days'] and r['veto_fired'] == r['veto_best_days'] else 'no'} | — |")
        a("")
        a(f"Measured on days the engine has never been tuned on "
          f"(`{r['source']}`, {r['set']}).")
    else:
        a("**Not measured this run.** Re-run "
          "`python research/t0_heldout_recall.py` and pass `--recall` to get "
          "this section. A stale recall number is worse than none.")
    a("")

    # 4
    a("## 4. How busy is it?")
    a("")
    a("| | this run | moved |")
    a("|---|---:|---:|")
    a(f"| Trades per market day | **{m['trades_per_day']:.2f}** | "
      f"{move(m['trades_per_day'], p.get('trades_per_day'), 2)} |")
    a(f"| Trades in total | {m['trades']:,} | "
      f"{move(m['trades'], p.get('trades'), 0)} |")
    a(f"| Setups looked at | {m['signals_seen']:,} | "
      f"{move(m['signals_seen'], p.get('signals_seen'), 0)} |")
    a("")

    # scoreboard
    met = sum([m["mean_r"] >= GATE_MEAN_R and m["win_rate_pct"] >= GATE_WIN_RATE,
               m["months_green"] == m["months_total"],
               bool(m["recall"]) and (m["recall"]["recall_pct"] or 0) >= GATE_RECALL])
    a("## The scoreboard")
    a("")
    a(f"**{met} of 3 finished.** OMEN is done when all three are true at once: "
      f"it averages +2R a trade at a 55% win rate, every month is green, and it "
      f"fires on 90% of the days he grades best.")
    a("")

    # month table
    a("## Month by month")
    a("")
    a("| month | R | dollars |")
    a("|---|---:|---:|")
    for k, v in m["month_r"].items():
        a(f"| {k} | {signed(v, 2)} | {money(v * RISK_DOLLARS)} |")
    a("")
    a("---")
    a("")
    a(f"Book: `{m['book']}` (built {m.get('book_generated') or 'unknown'}). "
      f"Page: `research/g71_standard_report.py`. "
      f"Numbers: `research/omen_report.json`.")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default=os.path.join(ROOT, "research", "bt2y_trades.json"))
    ap.add_argument("--recall", default=os.path.join(ROOT, "research", "t0_heldout_recall.json"))
    ap.add_argument("--against", default=None,
                    help="a previous run's sidecar JSON, for the 'moved' column")
    ap.add_argument("--out", default=os.path.join(ROOT, "research", "omen_report.md"))
    ap.add_argument("--json", default=os.path.join(ROOT, "research", "omen_report.json"))
    args = ap.parse_args()

    prev = None
    if args.against and os.path.exists(args.against):
        prev = json.load(open(args.against, encoding="utf-8"))

    m = measure(args.book, args.recall)
    page = render(m, prev)

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(page)
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=1)
    print(page)
    print(f"\nwrote {args.out} and {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
