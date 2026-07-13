"""E5 Sunday cron — refresh 12mo backtest + diff vs prior week to Discord.

Flow:
  1. PRIOR = parse backtest_report_12mo.md (last Sunday's snapshot, pre-run).
  2. Run backtest_12mo.py 365 --snapshot → overwrites report_12mo.md with NEW.
  3. NEW = parse fresh backtest_report_12mo.md.
  4. Diff (signals, win rate, P&L, per-grade) → Discord embed.

backtest_12mo.py --snapshot copies backtest_report.md → backtest_report_12mo.md,
so PRIOR must be read before the subprocess runs (it overwrites the snapshot).

Usage:
    py -3.13 sunday_backtest.py            # full run + post diff
    py -3.13 sunday_backtest.py --dry-run  # parse current snapshot, print embed, no run/post
    py -3.13 sunday_backtest.py --test    # skip backtest; diff last_snapshot vs current_report, post (proves path)
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from signal_runner import _load_env_file
_load_env_file(Path(__file__).parent / ".env")

from discord_bot import DiscordSignalBot

ROOT = Path(__file__).parent
SNAP = ROOT / "backtest_report_12mo.md"      # weekly snapshot (PRIOR before run, NEW after)
CURRENT = ROOT / "backtest_report.md"        # most recent ad-hoc run (NEW for --test)
GRADES = ["A+", "A", "B"]

# ponytail: regex parse of the markdown report. If write_report format changes, this breaks loudly.
RE_WEEK = re.compile(r"^# Backtest Report: Week of (.+) to (.+)$", re.MULTILINE)
RE_SUMM = re.compile(r"Traded signals.*?\*\*(\d+)\*\* \| (\d+)W (\d+)L (\d+) scratch \| win rate ([\d.]+)%")
RE_PNL = re.compile(r"Simulated P&L.*?\*\*([+-]?\$?[\d.]+)\*\*")
RE_GRADE = re.compile(r"^\| (A\+|A|B) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| ([\d.]+)% \| \$([-\d.]+) \|")


def parse_report(path: Path) -> dict | None:
    """Extract headline stats from a backtest report md. None if unparseable."""
    if not path.exists():
        return None
    txt = path.read_text(encoding="utf-8", errors="replace")
    m_summ = RE_SUMM.search(txt)
    m_pnl = RE_PNL.search(txt)
    if not m_summ or not m_pnl:
        return None
    grades = {}
    for line in txt.splitlines():
        m = RE_GRADE.match(line)
        if m:
            grades[m.group(1)] = {"n": int(m.group(2)), "w": int(m.group(3)),
                                 "l": int(m.group(4)), "wr": float(m.group(6)),
                                 "pnl": float(m.group(7))}
    m_week = RE_WEEK.search(txt)
    week = (m_week.group(1), m_week.group(2)) if m_week else ("?", "?")
    return {"week": week, "signals": int(m_summ.group(1)),
            "w": int(m_summ.group(2)), "l": int(m_summ.group(3)),
            "wr": float(m_summ.group(5)),
            "pnl": float(m_pnl.group(1).replace("$", "").replace("+", "")),
            "grades": grades}


def _d(a, b, fmt="{:+.1f}"):
    """Signed delta string old→new, '' if either missing."""
    if a is None or b is None:
        return "—"
    return fmt.format(b - a)


def build_diff(prior: dict | None, new: dict | None, reason: str) -> dict:
    if new is None:
        return {"embeds": [{"title": "📊 Sunday Backtest Diff",
                             "description": "New run produced no parseable report — check backtest logs.",
                             "color": 15158332,
                             "footer": {"text": f"sunday_backtest · trigger={reason}"}}]}
    if prior is None:
        desc = ("*No prior snapshot to diff (first run or snapshot missing).*\n\n"
                f"**NEW** — week of {new['week'][0]} → {new['week'][1]}\n")
        rows = new_rows(new)
    else:
        desc = (f"**{prior['week'][0]} → {prior['week'][1]}**  ⟶  "
                f"**{new['week'][0]} → {new['week'][1]}**\n\n")
        rows = diff_rows(prior, new)
    return {"embeds": [{"title": "📊 Sunday Backtest Diff",
                        "description": desc + "```\n" + rows + "\n```",
                        "color": 3066993,
                        "footer": {"text": f"sunday_backtest · trigger={reason}"}}]}


def new_rows(new: dict) -> str:
    lines = [f"Signals   {new['signals']:>6}",
             f"Win rate  {new['wr']:>6.1f}%",
             f"P&L     ${new['pnl']:>10.0f}"]
    for g in GRADES:
        if g in new["grades"]:
            gd = new["grades"][g]
            lines.append(f"  {g:<3}    {gd['n']:>4}  WR {gd['wr']:>5.1f}%  ${gd['pnl']:>9.0f}")
    return "\n".join(lines)


def diff_rows(prior: dict, new: dict) -> str:
    def row(label, p, n, fmt="{:>9}", delta_fmt="{:+.0f}"):
        d = delta_fmt.format(n - p) if p is not None else ""
        return f"{label:<10}{fmt.format(n) if not isinstance(n,str) else n:>9}  ({d})"

    lines = [
        f"Signals   {new['signals']:>6}  ({_d(prior['signals'], new['signals'], '{:+d}')})",
        f"Win rate  {new['wr']:>5.1f}%  ({_d(prior['wr'], new['wr'], '{:+.1f}pp')})",
        f"P&L     ${new['pnl']:>9.0f}  (${_d(prior['pnl'], new['pnl'], '{:+.0f}')})",
        "",
        f"{'grade':<6}{'n':>6}{'(Δ)':>7}  {'wr':>6}{'(Δ)':>8}  {'pnl':>10}{'(Δ)':>10}",
    ]
    for g in GRADES:
        pg, ng = prior["grades"].get(g), new["grades"].get(g)
        if not ng:
            continue
        if pg:
            lines.append(f"{g:<6}{ng['n']:>6}{(ng['n']-pg['n']):>+7d}  "
                         f"{ng['wr']:>5.1f}%{(ng['wr']-pg['wr']):>+7.1f}pp  "
                         f"${ng['pnl']:>9.0f}{(ng['pnl']-pg['pnl']):>+10.0f}")
        else:
            lines.append(f"{g:<6}{ng['n']:>6}{'':>7}  {ng['wr']:>5.1f}%{'':>8}  ${ng['pnl']:>9.0f}")
    return "\n".join(lines)


def run_backtest(days: int) -> int:
    """Run backtest_12mo.py with --snapshot. Returns subprocess returncode."""
    py = r"C:\Users\aharg\AppData\Local\Programs\Python\Python313\python.exe"
    cmd = [py, str(ROOT / "backtest_12mo.py"), str(days), "--snapshot"]
    print("running:", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


def main():
    p = argparse.ArgumentParser(description="E5 Sunday backtest refresh + diff")
    p.add_argument("--days", type=int, default=365)
    p.add_argument("--dry-run", action="store_true",
                   help="parse current snapshot, print embed, no run/post")
    p.add_argument("--test", action="store_true",
                   help="skip backtest; diff last_snapshot vs current_report, post (proves path)")
    args = p.parse_args()

    if args.dry_run:
        new = parse_report(SNAP)
        payload = build_diff(None, new, "dry-run")
        print(json.dumps(payload, indent=2))
        return

    if args.test:
        prior = parse_report(SNAP)       # last Sunday's snapshot
        new = parse_report(CURRENT)      # most recent ad-hoc run
        reason = "test"
    else:
        prior = parse_report(SNAP)       # PRIOR before subprocess overwrites it
        rc = run_backtest(args.days)
        if rc != 0:
            print(f"backtest_12mo exited {rc} — aborting diff post", file=sys.stderr)
            sys.exit(rc)
        new = parse_report(SNAP)         # NEW after --snapshot
        reason = "sunday-cron"

    payload = build_diff(prior, new, reason)
    ok = DiscordSignalBot()._post_with_retry(payload)
    print(f"sunday diff ({reason}): {'posted' if ok else 'FAILED'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
