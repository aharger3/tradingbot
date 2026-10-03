"""OMEN v3 B3: daily 4:30pm ET report — paper signals vs backtest expectation.

Compares today's paper-engine output (journal/acks.jsonl, if the paper engine
has written one) against the frozen v2 MNQ ORB5 backtest baseline
(research/agent_runs/v2-t01-orb-1m/trades_MNQ_OR5_1030_D1_strong.json), and
sends ONE ntfy push only if something is off by more than 2 sigma. No push
otherwise (Austin wants only important pings).

Baseline (frozen, from REFEREE-v2.md, rerun 2026-09-26):
  n=105 trades, hit rate 46.7% (2R target), mean +0.309R, sigma_R from the
  trade sample itself. Fire rate ~1 signal / 4.4 Mon-Thu sessions (0.227/day).

Run: `python research/daily_report.py` (intended 16:30 ET via Scheduled Task).
Writes research/reports/daily_<date>.md and .json every run.
Pushes ntfy topic $OMEN_NTFY_TOPIC (env var; no-op if unset) only on a >2sigma
flag, tagged [n small] whenever the day's own sample is too thin to trust.
"""
import json
import math
import os
import sys
import statistics
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
BASELINE_TRADES = ROOT / "research/agent_runs/v2-t01-orb-1m/trades_MNQ_OR5_1030_D1_strong.json"
JOURNAL = ROOT / "research/paper_journal" / "acks.jsonl"  # written by the (not-yet-shipped) live paper engine
REPORTS_DIR = ROOT / "research/reports"
ET = ZoneInfo("America/New_York")
FIRE_RATE_BASELINE = 1 / 4.4  # sessions, from OMEN-SHIP-PLAN-v2.md sec 1
SIGMA_THRESHOLD = 2.0


def load_baseline():
    if not BASELINE_TRADES.exists():
        return {"n": 105, "hit_rate": 0.467, "mean_r": 0.309, "sigma_r": 1.4, "trades": []}
    rows = json.loads(BASELINE_TRADES.read_text())
    rs = [t.get("r", t.get("R")) for t in rows if isinstance(t, dict) and (t.get("r") is not None or t.get("R") is not None)]
    rs = [float(x) for x in rs]
    n = len(rs)
    mean_r = sum(rs) / n if n else 0.309
    sigma_r = statistics.pstdev(rs) if n > 1 else 1.4
    wins = sum(1 for x in rs if x > 0)
    hit_rate = wins / n if n else 0.467
    return {"n": n, "hit_rate": hit_rate, "mean_r": mean_r, "sigma_r": sigma_r, "trades": rs}


def load_today_signals(today_str):
    """Paper engine (Lane R/L, B1/B2) is not shipped per REFEREE-v2.md.
    If/when it writes acks.jsonl, pick up today's rows; otherwise 0 signals."""
    if not JOURNAL.exists():
        return []
    out = []
    for line in JOURNAL.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("date") == today_str or str(row.get("ts", "")).startswith(today_str):
            out.append(row)
    return out


def binom_sigma_flag(observed_fire, expected_p, n_days=1):
    """z-score for observing `observed_fire` (0/1 today) vs Bernoulli(expected_p)."""
    var = expected_p * (1 - expected_p) / max(n_days, 1)
    sd = math.sqrt(var) if var > 0 else 1e-9
    return (observed_fire - expected_p) / sd



CORPUS_HEALTH = Path(os.environ.get("OMEN_CORPUS_HEALTH", r"C:\Users\aharg\Desktop\ops\corpus-health.json"))


def corpus_health_line(path=CORPUS_HEALTH):
    """One line on the nightly corpus scrape (Discord/YouTube/Circle) + harvest tasks.
    Written by Desktop\\Scripts\\corpus-scrape.ps1 (task omen-corpus-scrape)."""
    try:
        h = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as e:
        return f"Corpus health: NO STATUS ({type(e).__name__}) - omen-corpus-scrape has not written {path}"
    steps = " ".join(f"{k}={v.get('rc')}" for k, v in (h.get("steps") or {}).items())
    tasks = " ".join(f"{k}={v.get('result')}" for k, v in (h.get("tasks") or {}).items())
    f = h.get("fresh") or {}
    return (f"Corpus health: {'OK' if h.get('ok') else 'FAIL'} @ {h.get('run_at')} | {steps} | "
            f"tasks {tasks} | scarface {f.get('discord_scarface')} jdub {f.get('discord_jdub')} "
            f"yt {f.get('youtube_count')} transcripts")


def main():
    now_et = datetime.now(ET)
    today_str = now_et.strftime("%Y-%m-%d")
    baseline = load_baseline()
    todays = load_today_signals(today_str)

    fired_today = 1 if todays else 0
    z_fire = binom_sigma_flag(fired_today, FIRE_RATE_BASELINE)

    flags = []
    if abs(z_fire) > SIGMA_THRESHOLD:
        direction = "MORE signals than expected" if z_fire > 0 else "a quiet stretch vs expected fire rate"
        flags.append(f"fire-rate z={z_fire:.2f} ({direction}; expected ~1/4.4 sessions)")

    trade_lines = []
    for t in todays:
        r = t.get("r", t.get("R"))
        if r is None:
            continue
        r = float(r)
        z_r = (r - baseline["mean_r"]) / baseline["sigma_r"] if baseline["sigma_r"] else 0
        trade_lines.append(f"- signal {t.get('id', '?')}: R={r:+.2f} (baseline {baseline['mean_r']:+.3f}, z={z_r:.2f})")
        if abs(z_r) > SIGMA_THRESHOLD:
            flags.append(f"trade {t.get('id', '?')} R={r:+.2f} is {z_r:.2f} sigma off baseline mean {baseline['mean_r']:+.3f}")

    n_flag_note = " [n small, baseline n={}]".format(baseline["n"]) if baseline["n"] < 30 else ""

    report_md = [
        f"# OMEN daily report — {today_str} 16:30 ET",
        "",
        f"Baseline (v2 MNQ ORB5, frozen): n={baseline['n']}, hit rate {baseline['hit_rate']*100:.1f}%, "
        f"mean {baseline['mean_r']:+.3f}R, sigma {baseline['sigma_r']:.3f}R, fire rate ~1/4.4 sessions.",
        "",
        f"Today: {len(todays)} paper signal(s) logged." + (" (no live paper engine shipped yet — B1/B2 struck by REFEREE-v2, this is a placeholder run)" if not JOURNAL.exists() else ""),
        "",
    ]
    report_md.extend(trade_lines or ["- no trades today"])
    report_md.append("")
    report_md.append(f"Fire-rate check: fired={bool(fired_today)}, z={z_fire:.2f}{n_flag_note}")
    report_md.append("")
    if flags:
        report_md.append("## FLAGGED (>2 sigma)")
        report_md.extend(f"- {f}" for f in flags)
    else:
        report_md.append("Nothing >2 sigma off baseline. No push sent.")
    report_md.append("")
    report_md.append(corpus_health_line())

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / f"daily_{today_str}.md").write_text("\n".join(report_md) + "\n")
    (REPORTS_DIR / f"daily_{today_str}.json").write_text(json.dumps({
        "date": today_str, "baseline": {k: v for k, v in baseline.items() if k != "trades"},
        "today_signals": todays, "z_fire": z_fire, "flags": flags,
    }, indent=2))

    if flags:
        topic = os.environ.get("OMEN_NTFY_TOPIC")
        if topic:
            import urllib.request
            msg = f"OMEN {today_str}: " + "; ".join(flags)
            try:
                req = urllib.request.Request(
                    f"https://ntfy.sh/{topic}", data=msg.encode(), method="POST",
                    headers={"Title": "OMEN daily flag", "Priority": "default"},
                )
                urllib.request.urlopen(req, timeout=10)
                print(f"ntfy sent: {msg}")
            except Exception as e:
                print(f"ntfy send failed: {e}", file=sys.stderr)
        else:
            print("FLAG (no OMEN_NTFY_TOPIC set, not pushed): " + "; ".join(flags))
    else:
        print("No flags. No push sent.")
    print(f"Report: research/reports/daily_{today_str}.md")


if __name__ == "__main__":
    main()
