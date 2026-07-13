"""E3 pre-market Discord card — 9:00 ET, before the 9:25 scanner launch.

One embed: watchlist key levels (PDH/PDL/PMH/PML, last pre-market price)
+ QQQ daily bias (gap vs prior close, position vs PDH/PDL). Data via the
same yfinance helpers live_scanner uses (Tastytrade not needed pre-market).

Usage:
    py -3.13 premarket_card.py            # post to Discord
    py -3.13 premarket_card.py --dry-run  # print embed JSON, don't post
    py -3.13 premarket_card.py --symbols TSLA NVDA
"""
import argparse
import json
from datetime import time as dtime
from pathlib import Path

from signal_runner import _load_env_file
_load_env_file(Path(__file__).parent / ".env")

from live_scanner import DEFAULT_SYMBOLS, _yf_daily_context, _yf_history, now_et


def _premarket_last(symbol: str):
    """Last pre-market trade price, or None."""
    m = _yf_history(symbol, period="1d", interval="1m", prepost=True)
    if m is None:
        return None
    pm = m[m.index.time < dtime(9, 30)]
    return float(pm.Close.iloc[-1]) if not pm.empty else None


def _fmt(v) -> str:
    return f"{v:.2f}" if v is not None else "—"


def _qqq_bias() -> str:
    try:
        pdh, pdl, _, pmh, pml, _, pdc = _yf_daily_context("QQQ")
        last = _premarket_last("QQQ")
    except Exception as e:
        return f"QQQ bias: data error ({type(e).__name__})"
    if last is None or pdc is None:
        return "QQQ bias: unknown (no pre-market data)"
    gap = (last - pdc) / pdc * 100
    bias = "BULLISH" if gap > 0.15 else "BEARISH" if gap < -0.15 else "NEUTRAL"
    pos = ""
    if pdh is not None and last > pdh:
        pos = " — above PDH"
    elif pdl is not None and last < pdl:
        pos = " — below PDL"
    return (f"**{bias}** gap {gap:+.2f}% ({_fmt(last)} vs PDC {_fmt(pdc)}){pos}\n"
            f"PDH {_fmt(pdh)} / PDL {_fmt(pdl)} / PMH {_fmt(pmh)} / PML {_fmt(pml)}")


def build_card(symbols) -> dict:
    lines = []
    for sym in symbols:
        try:
            pdh, pdl, _, pmh, pml, _, _ = _yf_daily_context(sym)
            last = _premarket_last(sym)
            lines.append(f"{sym:<5} {_fmt(last):>8} | PDH {_fmt(pdh):>8} PDL {_fmt(pdl):>8}"
                         f" | PMH {_fmt(pmh):>8} PML {_fmt(pml):>8}")
        except Exception as e:
            lines.append(f"{sym:<5} data error: {type(e).__name__}")

    # Discord field cap 1024 chars -> chunk watchlist into fields
    fields = [{"name": "QQQ Daily Bias", "value": _qqq_bias(), "inline": False}]
    chunk, size, part = [], 0, 1
    for ln in lines:
        if size + len(ln) + 9 > 1000:  # +9 for code fences/newline
            fields.append({"name": f"Levels ({part})",
                           "value": "```\n" + "\n".join(chunk) + "\n```", "inline": False})
            chunk, size, part = [], 0, part + 1
        chunk.append(ln)
        size += len(ln) + 1
    if chunk:
        name = "Levels" if part == 1 else f"Levels ({part})"
        fields.append({"name": name,
                       "value": "```\n" + "\n".join(chunk) + "\n```", "inline": False})

    return {"embeds": [{
        "title": f"🌅 Pre-Market Card — {now_et().date().isoformat()}",
        "color": 15844367,
        "fields": fields,
        "footer": {"text": "Omen Pre-Market · 9:30-11:00 window · S≥4+[hammer] max 2 stop-green"},
    }]}


def main():
    parser = argparse.ArgumentParser(description="E3 pre-market Discord card")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--dry-run", action="store_true",
                        help="print embed JSON instead of posting")
    args = parser.parse_args()

    payload = build_card(args.symbols)
    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return
    from discord_bot import DiscordSignalBot
    ok = DiscordSignalBot()._post_with_retry(payload)
    print(f"Pre-market card: {'posted' if ok else 'FAILED'}")


if __name__ == "__main__":
    main()
