"""SPEC12 daily session review — after-close Discord embed.

Reads today's journal/ signal log + paper trade results and posts ONE Discord
embed via the existing DiscordSignalBot (which has retry). Covers:
  - Signals fired (symbol, grade, S, tags, outcome)
  - Paper P&L
  - Tier-rule compliance (v2: S>=4, no [chase], max 2 — flag violations)
  - News-day note if applicable
  - Posted/failed webhook counters

Empty day = one-line "no signals" post.

Usage:
    py -3.13 daily_review.py                # post today's review to Discord
    py -3.13 daily_review.py --dry-run      # print the embed JSON, don't post
    py -3.13 daily_review.py --date 2026-07-07   # review a specific date
"""
import argparse
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

_TIER_PREFIX_RE = re.compile(r"^(TRADE|WATCH)\s*·\s*")


def _is_tier_row(reason: str) -> bool:
    """Scanner tier rows carry a 'TRADE · ' or 'WATCH · ' prefix (live_scanner
    _emit_signal). Pre-tier rows from signal_runner._log_record lack it."""
    return bool(_TIER_PREFIX_RE.match(reason or ""))


def _parse_ts(ts: str):
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _entry_match(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return a == b


def _dedupe_signals(signals: list) -> tuple:
    """G1: split authoritative scanner tier rows from pre-tier duplicates.

    A pre-tier row (no TRADE/WATCH prefix) matching a tier row on
    (symbol, direction, entry) within ~5s is a dup of the same signal — drop
    it. A pre-tier 'fired' row with NO matching tier row was routed without a
    tier decision; count it separately as untiered, not as fired.

    Returns (tier_signals, untiered_fired_count).
    """
    tier, pre = [], []
    for s in signals:
        if s.get("status") not in ("fired", "alert"):
            continue  # skip D-grade / tight-stop skips
        (tier if _is_tier_row(s.get("reason", "")) else pre).append(s)

    untiered = 0
    for p in pre:
        pt = _parse_ts(p.get("timestamp", ""))
        matched = False
        for t in tier:
            if not (p.get("symbol") == t.get("symbol")
                    and p.get("direction") == t.get("direction")
                    and _entry_match(p.get("entry"), t.get("entry"))):
                continue
            tt = _parse_ts(t.get("timestamp", ""))
            if pt and tt and abs((pt - tt).total_seconds()) <= 5:
                matched = True
                break
        if not matched and p.get("status") == "fired":
            untiered += 1
    return tier, untiered

ROOT = Path(__file__).parent
JOURNAL = ROOT / "journal"


def _load_signal_log(date_str: str) -> list:
    """Load signal_log_YYYY-MM-DD.jsonl -> list of dicts."""
    path = JOURNAL / f"signal_log_{date_str}.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _load_paper_trades(date_str: str) -> list:
    """Load paper-trades.jsonl, filter to events on date_str.

    Paper trade ts fields are 'HH:MM:SS' (no date prefix) since live_scanner
    passes candle timestamps. When ts lacks a date, we include the record —
    the scanner restarts daily via schtask, so the ledger is effectively
    today's session. Full-date timestamps (from _now_et_iso fallback) are
    filtered properly.
    """
    path = JOURNAL / "paper-trades.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                rec = json.loads(line)
                ts = rec.get("ts", rec.get("opened_at", ""))
                # ts is either "HH:MM:SS" (candle timestamp) or
                # "YYYY-MM-DD HH:MM:SS" (_now_et_iso fallback)
                if len(ts) <= 8:  # no date prefix -> include (today's session)
                    out.append(rec)
                elif ts.startswith(date_str):
                    out.append(rec)
            except json.JSONDecodeError:
                pass
    return out


def _load_failed_webhooks(date_str: str) -> int:
    """Count failed webhook entries for date_str."""
    path = JOURNAL / "failed_webhooks.jsonl"
    if not path.exists():
        return 0
    n = 0
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                rec = json.loads(line)
                if rec.get("timestamp", "").startswith(date_str):
                    n += 1
            except json.JSONDecodeError:
                pass
    return n


def _is_news_day(date_str: str) -> tuple:
    """Return (bool, list_of_types) from news_days.json."""
    try:
        nd = json.loads((ROOT / "news_days.json").read_text())
        by_date = nd.get("by_date", {})
        if date_str in by_date:
            return True, by_date[date_str]
        return False, []
    except (OSError, ValueError):
        return False, []


def _s_score(reason: str):
    """Extract S-score from reason string (e.g. '... S3')."""
    m = re.search(r" S(\d+)", reason)  # S can reach 10 with F4 qqq +1
    return int(m.group(1)) if m else None


def _tags(reason: str) -> list:
    """Extract bracketed tags from reason (e.g. [hammer], [clean], [late]).

    Strips leading [SYMBOL] prefix that live_scanner prepends to reason
    strings (e.g. '[TSLA] B&R short...'). Symbol tags are 1-5 uppercase
    chars at the start; real tags are descriptive phrases.
    """
    # Strip leading [SYMBOL] that live_scanner prepends
    cleaned = re.sub(r"^\[[A-Z]{1,5}\]\s*", "", reason)
    return re.findall(r"\[([^\]]+)\]", cleaned)


def _build_signal_rows(signals: list, paper_trades: list) -> list:
    """Build per-signal rows: {symbol, grade, s, tags, outcome}."""
    # Index paper trade CLOSE events by symbol+direction for outcome lookup
    closes = {}
    for ev in paper_trades:
        if ev.get("event") == "CLOSE":
            key = (ev.get("symbol"), ev.get("direction"))
            closes[key] = ev

    rows = []
    for sig in signals:
        if sig.get("status") not in ("fired", "alert"):
            continue  # skip D-grade / tight-stop skips
        reason = sig.get("reason", "")
        # Strip leading "WATCH · " or "TRADE · " prefix for tag extraction
        clean_reason = re.sub(r"^(WATCH|TRADE)\s*·\s*", "", reason)
        s = _s_score(clean_reason)
        tags = _tags(clean_reason)
        outcome = "—"
        close = closes.get((sig.get("symbol"), sig.get("direction")))
        if close:
            outcome = close.get("outcome", "—")
            if close.get("pnl") is not None:
                outcome += f" (${close['pnl']:.0f})"
        rows.append({
            "symbol": sig.get("symbol", "?"),
            "grade": sig.get("grade", "?"),
            "s": s if s is not None else "—",
            "tags": ", ".join(tags) if tags else "—",
            "outcome": outcome,
            "status": sig.get("status"),
            "direction": sig.get("direction", "?"),
            "reason": clean_reason,
        })
    return rows


def _paper_pnl(paper_trades: list) -> float:
    """Sum realized P&L from CLOSE events."""
    return round(sum(ev.get("pnl", 0) for ev in paper_trades
                     if ev.get("event") == "CLOSE"), 2)


def _tier_compliance(rows: list, paper_trades: list) -> list:
    """Check tier-v2 rules (C10 2026-07-13): S>=4, no [chase], max 2/day.
    v1's [hammer] requirement and stop-when-green dropped per C10 sweep
    (research/c10_synthesis.md); news days already blocked by SKIP_NEWS.
    Returns list of violation strings (empty = all compliant)."""
    violations = []
    # G1: S=None = NON-TIER (untiered routed, or a tier row missing an S
    # score) — exclude from tier stats so they can't pass S>=4 vacuously.
    trade_rows = [r for r in rows if r["status"] == "fired"
                  and isinstance(r["s"], int)]

    # 1. S>=4 and not a [chase] entry
    for r in trade_rows:
        issues = []
        if r["s"] < 4:
            issues.append(f"S{r['s']}<4")
        if "chase" in r["tags"].lower():
            issues.append("[chase] entry (28%W tag — skip)")
        if issues:
            violations.append(
                f"{r['symbol']} {r['direction']} grade {r['grade']}: "
                + ", ".join(issues))

    # 2. max 2 trades/day
    if len(trade_rows) > 2:
        violations.append(f"max 2 exceeded: {len(trade_rows)} TRADE-tier signals fired")

    return violations


def build_embed(date_str: str) -> dict:
    """Build the Discord embed payload for the daily review."""
    signals = _load_signal_log(date_str)
    paper_trades = _load_paper_trades(date_str)
    failed_count = _load_failed_webhooks(date_str)
    is_news, news_types = _is_news_day(date_str)

    # No signals at all
    if not signals:
        text = f"📊 **Daily Review {date_str}** — no signals"
        if is_news:
            text += f" (news day: {', '.join(news_types)})"
        return {"content": text}

    tier_signals, untiered_fired = _dedupe_signals(signals)
    rows = _build_signal_rows(tier_signals, paper_trades)
    pnl = _paper_pnl(paper_trades)
    violations = _tier_compliance(rows, paper_trades)
    trade_count = sum(1 for r in rows if r["status"] == "fired")
    alert_count = sum(1 for r in rows if r["status"] == "alert")
    skip_count = sum(1 for s in signals if s.get("status") == "skipped")
    tier_trade_count = sum(1 for r in rows if r["status"] == "fired"
                           and isinstance(r["s"], int))

    # Build embed
    fields = []

    # Signals summary
    summary = (f"Fired: {trade_count} | Alerts: {alert_count} | "
               f"Skipped: {skip_count} | Routed (untiered): {untiered_fired} | "
               f"Paper P&L: {'+' if pnl >= 0 else ''}${pnl}")
    fields.append({"name": "Signals", "value": summary, "inline": False})

    # Per-signal detail (compact)
    if rows:
        lines = []
        for r in rows[:10]:  # Discord field limit ~1024 chars
            tier = "TRADE" if r["status"] == "fired" else "WATCH"
            lines.append(
                f"{'🎯' if r['status'] == 'fired' else '👀'} {r['symbol']} "
                f"{r['direction'].upper()} {r['grade']} S{r['s']} "
                f"[{r['tags']}] -> {r['outcome']}")
        detail = "\n".join(lines)
        if len(rows) > 10:
            detail += f"\n... +{len(rows) - 10} more"
        fields.append({"name": "Signal Detail", "value": detail, "inline": False})

    # Tier-rule compliance (G1: S=None rows are non-tier, excluded above)
    if tier_trade_count == 0:
        compliance = "0 tier trades"
    elif violations:
        compliance = "⚠ " + "; ".join(violations)
    else:
        compliance = "✓ All tier rules met (v2: S>=4, no [chase], max 2)"
    fields.append({"name": "Tier Compliance", "value": compliance, "inline": False})

    # News-day note
    if is_news:
        fields.append({"name": "News Day", "value":
                        f"⚠ {', '.join(news_types)} — size down / skip per Scarface rule",
                        "inline": False})

    # Webhook counters
    posted = trade_count + alert_count  # every fired/alert signal was attempted
    fields.append({"name": "Webhooks", "value":
                    f"Posted: {posted} | Failed: {failed_count}",
                    "inline": False})

    color = 3066993 if pnl >= 0 else 15158332  # green if profit, red if loss
    return {
        "embeds": [{
            "title": f"📊 Daily Review — {date_str}",
            "color": color,
            "fields": fields,
            "footer": {"text": "Omen Daily Review"},
        }]
    }


def main():
    parser = argparse.ArgumentParser(description="Daily session review (SPEC12)")
    parser.add_argument("--date", default=None,
                        help="review date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the embed JSON instead of posting to Discord")
    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        date_str = (date.today() - timedelta(days=1)).isoformat()

    payload = build_embed(date_str)

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return

    # Post via existing DiscordSignalBot (has retry + failed-log)
    from discord_bot import DiscordSignalBot
    try:
        bot = DiscordSignalBot()
    except ValueError as e:
        print(f"Discord init failed: {e}")
        print("Run with --dry-run to see the embed without posting.")
        return
    ok = bot._post_with_retry(payload)
    print(f"Daily review for {date_str}: {'posted' if ok else 'FAILED'}")


if __name__ == "__main__":
    main()
