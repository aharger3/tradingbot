"""Replay Scarface's actual alert entries against OMEN's detector.

For each "TOOK ..." alert in discord_data/scarface-alerts.json that falls on a
day with cached 1-min data, feed the day bar-by-bar and report what the bot
saw within +/-3 minutes of his entry. Misses = named detector gaps.
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta

from backtest_week import BacktestRunner, SYMBOLS, htf_bias_for
from backtest_sweep import load_data

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ENTRY_RE = re.compile(r"\bTOOK\b", re.I)
DIR_RE = re.compile(r"\b(calls?|puts?)\b", re.I)
UTC_OFFSET = 4  # ET during DST (all cached data is Jun-Jul)


def parse_entries(known_syms):
    msgs = json.load(open("discord_data/scarface-alerts.json", encoding="utf-8"))
    out = []
    for m in msgs:
        c = m.get("content", "")
        if not ENTRY_RE.search(c):
            continue
        d = DIR_RE.search(c)
        syms = [s for s in known_syms if re.search(rf"\b{s}\b", c, re.I)]
        if not d or len(syms) != 1:
            continue
        ts = datetime.fromisoformat(m["ts"][:19]) - timedelta(hours=UTC_OFFSET)
        out.append({"symbol": syms[0], "day": ts.date().isoformat(),
                    "time": ts.strftime("%H:%M"), "direction":
                    "call" if d.group(1).lower().startswith("call") else "put",
                    "text": c[:80].replace("\n", " ")})
    return out


def _polygon_day(symbol: str, day_iso: str):
    """(rth_candles, pdh, pdl, pmh, pml) via Polygon, or None if no data."""
    from datetime import date as _date
    import polygon_feed as pg
    full = pg.fetch_day(symbol, day_iso)
    candles = pg.rth(full)
    if len(candles) < 30:
        return None
    pmh, pml = pg.premarket_hi_lo(full)
    pdh = pdl = None
    d = _date.fromisoformat(day_iso)
    for k in range(1, 5):  # walk back to previous trading day
        prev = pg.rth(pg.fetch_day(symbol, (d - timedelta(days=k)).isoformat()))
        if prev:
            pdh, pdl = max(c.high for c in prev), min(c.low for c in prev)
            break
    return candles, pdh, pdl, pmh, pml


def replay(full_history: bool = False):
    data = load_data(29)
    entries = parse_entries(set(SYMBOLS))
    if not full_history:
        entries = [e for e in entries
                   if e["symbol"] in data and e["day"] in data[e["symbol"]]["days"]]
    print(f"{len(entries)} replayable entries\n")
    outcomes = Counter()
    for e in entries:
        d = data.get(e["symbol"], {})
        if e["day"] in d.get("days", {}):
            candles = d["days"][e["day"]]
            prev = [k for k in sorted(d["days"]) if k < e["day"]]
            if prev:
                pc = d["days"][prev[-1]]
                pdh, pdl = max(c.high for c in pc), min(c.low for c in pc)
            else:
                pdh = pdl = None
            bias = htf_bias_for(d["hourly"], e["day"])
            pmh, pml = d.get("premkt", {}).get(e["day"], (None, None))
        else:
            try:
                got = _polygon_day(e["symbol"], e["day"])
            except Exception as ex:
                print(f"{e['day']} {e['symbol']}: polygon error {ex}")
                continue
            if got is None:
                outcomes["no_data"] += 1
                continue
            candles, pdh, pdl, pmh, pml = got
            bias = None  # no hourly history via this path; PA-only grading
        runner = BacktestRunner(e["symbol"])
        runner.pdh, runner.pdl = pdh, pdl
        runner.htf_bias = bias
        runner.pmh, runner.pml = pmh, pml

        # bars within +/-3 min of his entry
        t0 = datetime.strptime(e["time"], "%H:%M")
        window = {(t0 + timedelta(minutes=k)).strftime("%H:%M") for k in range(-3, 4)}
        seen = []
        for i in range(5, len(candles)):
            runner.candles = candles[:i + 1]
            n_before = len(runner.captured)
            runner.detect_signals()
            bar_t = candles[i].timestamp[:5]
            for sig in runner.captured[n_before:]:
                if bar_t in window and sig["direction"] == e["direction"]:
                    seen.append((bar_t, sig["status"], sig["grade"],
                                 getattr(sig["signal_type"], "value", str(sig["signal_type"]))))
        if any(s[1] == "fired" for s in seen):
            best = next(s for s in seen if s[1] == "fired")
            outcomes["FIRED"] += 1
            verdict = f"FIRED {best[3]} {best[2]} @{best[0]}"
        elif seen:
            s = seen[0]
            outcomes[f"skip:{s[1]}"] += 1
            verdict = f"seen but {s[1]} ({s[3]} {s[2]}) @{s[0]}"
        else:
            outcomes["NOTHING"] += 1
            verdict = "NOTHING detected"
        print(f"{e['day']} {e['time']} {e['symbol']:5s} {e['direction']:4s} | {verdict}  [{e['text'][:50]}]")
    print(f"\nSUMMARY: {dict(outcomes)}")


if __name__ == "__main__":
    replay(full_history="--full" in sys.argv)
