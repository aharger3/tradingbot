"""
SPEC12 — Position Tracking + Daily Session Review (PNL Journal)

WHAT: After each trading session, produce a structured daily review
that includes:
  - All signals fired (including skips, alerts, and C-grade notes)
  - Paper position P&L by symbol
  - Win/loss streak, consecutive losses, max drawdown
  - Daily grade distribution (how many A+, A, B, C, D signals)
  - Lessons / notes field for human annotation

WHY: Without a daily review, the bot's learning loop has no feedback.
Spec10 and Spec11 add intelligence to signal filtering, but we can't
tell if they're working without comparing "before" and "after" stats.
A structured daily review makes it possible to tune grade thresholds,
volume multipliers, and OR timing based on real data.

FILES TO MODIFY:
  - signal_tracker.py — add daily_review() method
  - live_scanner.py — trigger daily review at session end
  - spec12_check.py (new) — verification
  - journal/daily_review_*.md (output, created automatically)

IMPLEMENTATION:

--- Step 1: Enhance signal_tracker.py ---

signal_tracker.py already has log_signal() and a daily .jsonl file.
Add:

def read_signals(date_str: str = None) -> list[dict]:
    \"\"\"Read all signal records for a given date.\"\"\"
    path = _log_path(date_str or date.today().isoformat())
    if not path.exists():
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

def daily_review(date_str: str = None, paper_ledger_path: Path = None) -> dict:
    \"\"\"Compile structured daily review from signal log + paper trades.

    Returns dict with:
      - date, total_signals, fired, skipped, alerts
      - by_grade: {A+: N, A: N, B: N, C: N, D: N}
      - by_symbol: {TSLA: N, NVDA: N, ...}
      - by_signal_type: {break_and_retest: N, ...}
      - paper: {total_pnl, win_rate, total_trades, avg_win, avg_loss}
      - consecutive: {wins, losses, max_consecutive_losses}
      - notes: "" (empty, for human to fill in)
    \"\"\"
    signals = read_signals(date_str)
    fired = [s for s in signals if s.get("status") == "fired"]
    skipped = [s for s in signals if s.get("status") == "skipped"]
    alerts = [s for s in signals if s.get("status") == "alert"]

    # Count by grade, symbol, signal type
    from collections import Counter
    by_grade = Counter(s.get("grade") for s in fired)
    by_symbol = Counter(s.get("symbol") for s in fired)
    by_type = Counter(s.get("signal_type") for s in fired)

    # Paper P&L stats from paper-trades.jsonl
    paper_stats = {"total_pnl": 0.0, "win_rate": 0.0, "total_trades": 0,
                   "avg_win": 0.0, "avg_loss": 0.0}
    if paper_ledger_path and paper_ledger_path.exists():
        trades = []
        with open(paper_ledger_path) as f:
            for line in f:
                ev = json.loads(line)
                if ev.get("event") == "CLOSE":
                    # Only count today's trades
                    ev_date = ev.get("ts", "")[:10]
                    if ev_date == (date_str or date.today().isoformat()):
                        trades.append(ev)

        if trades:
            wins = [t for t in trades if t.get("pnl", 0) > 0]
            losses = [t for t in trades if t.get("pnl", 0) <= 0]
            paper_stats["total_pnl"] = round(sum(t["pnl"] for t in trades), 2)
            paper_stats["total_trades"] = len(trades)
            paper_stats["win_rate"] = round(len(wins) / len(trades) * 100, 1)
            paper_stats["avg_win"] = round(
                sum(t["pnl"] for t in wins) / len(wins), 2) if wins else 0.0
            paper_stats["avg_loss"] = round(
                sum(t["pnl"] for t in losses) / len(losses), 2) if losses else 0.0

    return {
        "date": date_str or date.today().isoformat(),
        "total_signals": len(signals),
        "fired": len(fired),
        "skipped": len(skipped),
        "alerts": len(alerts),
        "by_grade": dict(by_grade),
        "by_symbol": dict(by_symbol),
        "by_signal_type": dict(by_type),
        "paper": paper_stats,
        "notes": "",
    }

--- Step 2: Add render_review() to produce markdown ---

def render_review(review: dict) -> str:
    \"\"\"Render daily review dict as markdown for journal/.\"\"\"
    lines = []
    lines.append(f"# Daily Review — {review['date']}")
    lines.append("")
    lines.append(f"**Signals:** {review['total_signals'] total | "
                 f"{review['fired']} fired | {review['skipped']} skipped | "
                 f"{review['alerts']} alerts**")
    lines.append("")
    if review["by_grade"]:
        lines.append("### Grade Distribution")
        lines.append(f"| Grade | Count |")
        lines.append(f"|-------|-------|")
        for g in ["A+", "A", "B", "C", "D"]:
            n = review["by_grade"].get(g, 0)
            if n:
                lines.append(f"| {g} | {n} |")
    lines.append("")
    if review["by_symbol"]:
        lines.append("### By Symbol")
        for sym, n in sorted(review["by_symbol"].items()):
            lines.append(f"- **{sym}**: {n} signals")
    lines.append("")
    if review["by_signal_type"]:
        lines.append("### By Pattern")
        for t, n in sorted(review["by_signal_type"].items()):
            lines.append(f"- **{t}**: {n}")
    lines.append("")
    p = review["paper"]
    if p["total_trades"] > 0:
        lines.append("### Paper Trading")
        lines.append(f"- Realized P&L: **${p['total_pnl']:.2f}**")
        lines.append(f"- Win rate: **{p['win_rate']}%** ({p['total_trades']} trades)")
        lines.append(f"- Avg win: ${p['avg_win']:.2f} | Avg loss: ${p['avg_loss']:.2f}")
        lines.append("")
    lines.append("### Notes")
    lines.append("_Click to add observations about today's session_")
    lines.append("")
    return "\n".join(lines)

--- Step 3: Wire up in live_scanner.py ---

In live_scanner.py main(), after the scan loop ends (or on
KeyboardInterrupt / exit), call daily_review() and write result
to journal/daily_review_YYYY-MM-DD.md.

Add to signal_runner.py's __init__:

  self.daily_review_written = False

In the main loop of live_scanner.py, after session ends
(day_ended() returns True or window closes), do:

  if not runner.daily_review_written:
      from signal_tracker import daily_review, render_review
      rev = daily_review(paper_ledger_path=paper.ledger_path if paper else None)
      md = render_review(rev)
      review_path = Path(__file__).parent / "journal" / f"daily_review_{rev['date']}.md"
      review_path.write_text(md)
      print(f"📄 Daily review written to {review_path}")
      runner.daily_review_written = True

--- Step 4: Add a CLI command for manual review ---

Add to signal_runner.py CLI:

  python signal_runner.py --review [date]
  # Outputs the daily review markdown to stdout

VERIFICATION:
  python spec12_check.py
  - Creates synthetic signal log entries for today
  - Runs daily_review() and render_review() on them
  - Verifies counts match (3 fired, 2 skipped, 1 alert)
  - Verifies grade distribution (2×A, 1×B)
  - Daily review markdown looks correct

SUCCESS CRITERIA:
  [ ] daily_review() reads signal_log_*.jsonl and returns stats
  [ ] render_review() produces valid markdown
  [ ] live_scanner writes daily_review_*.md at end of session
  [ ] Paper trade P&L stats included when --paper is used
  [ ] `--review` CLI flag works standalone
  [ ] Empty days produce a valid stub review (0 signals, 0 trades)
"""
