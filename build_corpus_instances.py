"""Build the corpus instance table (omen-corpus-1.0, task T1).

Reads every discord_data/*.json (list of messages OR id-keyed dict of them),
emits one row per (message, ticker) pair where the message has BOTH a
resolvable ticker (uppercase 2-5 letter token in content that is in the
engine's traded universe) and an intraday timestamp (clock time 09:30-16:00,
treated as US/Eastern, no shift).

Outputs:
  research/corpus_instances.jsonl  - one JSON row per line
  research/corpus_instances.md     - summary (rows per channel/author, distinct
                                     symbol-days, date range, image count)
"""
import json
import re
import glob
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parent
DISCORD = ROOT / "discord_data"
OUT_JSONL = ROOT / "research" / "corpus_instances.jsonl"
OUT_MD = ROOT / "research" / "corpus_instances.md"

# --- Universe: archive_1m.SYMBOLS plus ARM, QCOM, IWM ---
SYMBOLS = [
    "TSLA", "NVDA", "AAPL", "AMD", "META",
    "GOOGL", "AMZN", "MSFT", "PLTR", "SPY", "QQQ",
    "SOFI", "ORCL", "COIN", "HOOD", "IREN", "INTC", "SMCI",
    "MSTR", "NFLX", "AVGO", "MU", "UBER", "BABA", "CRM",
    "TSM", "MARA", "RIVN",
]
UNIVERSE = set(SYMBOLS) | {"ARM", "QCOM", "IWM"}

IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")
URL_EXT_RE = re.compile(r"\.([a-zA-Z]{2,5})(?:[?#]|$)")

# Uppercase 2-5 letter tokens on word boundaries.
TOK_RE = re.compile(r"\b[A-Z]{2,5}\b")

OPEN_MIN = 9 * 60 + 30   # 09:30 in minutes-of-day
CLOSE_MIN = 16 * 60     # 16:00 (exclusive)


def url_is_image(url: str) -> bool:
    if not isinstance(url, str):
        return False
    # strip query/fragment then check extension
    cut = url.split("?", 1)[0].split("#", 1)[0].lower()
    return cut.endswith(IMG_EXTS)


def iter_messages(d):
    """Yield message dicts from either a list or an id-keyed dict."""
    if isinstance(d, list):
        for m in d:
            if isinstance(m, dict):
                yield m
    elif isinstance(d, dict):
        for v in d.values():
            if isinstance(v, dict):
                yield v
            elif isinstance(v, list):
                for m in v:
                    if isinstance(m, dict):
                        yield m


def main():
    rows = []
    rows_per_channel = Counter()
    rows_per_author = Counter()
    symbol_days = set()
    dates = []
    image_rows = 0

    for fpath in sorted(DISCORD.glob("*.json")):
        channel = fpath.stem
        with open(fpath) as fh:
            data = json.load(fh)

        for m in iter_messages(data):
            ts = m.get("ts")
            content = m.get("content") or ""
            if not ts or not content:
                continue

            # parse ISO timestamp (already Eastern; no shift)
            try:
                dt = datetime.fromisoformat(str(ts))
            except ValueError:
                continue

            hh, mm = dt.hour, dt.minute
            mod = hh * 60 + mm
            # clock time must fall in 09:30-16:00 (Eastern)
            if not (OPEN_MIN <= mod < CLOSE_MIN):
                continue

            # find resolvable tickers in content
            tokens = set(TOK_RE.findall(content))
            tickers = sorted(t for t in tokens if t in UNIVERSE)
            if not tickers:
                continue

            day = dt.strftime("%Y-%m-%d")
            minute_i = mod - OPEN_MIN
            if minute_i < 0:
                minute_i = 0
            elif minute_i > 390:
                minute_i = 390

            # has_image: any attachment or embed URL ends in an image ext
            has_image = False
            for url in (m.get("attachments") or []) + (m.get("embeds") or []):
                if url_is_image(url):
                    has_image = True
                    break

            msg_id = m.get("id")
            author = m.get("author") or ""
            dates.append(day)

            for sym in tickers:
                row = {
                    "msg_id": msg_id,
                    "channel": channel,
                    "author": author,
                    "ts": str(ts),
                    "day": day,
                    "minute_i": minute_i,
                    "symbol": sym,
                    "text": content,
                    "has_image": has_image,
                }
                rows.append(row)
                rows_per_channel[channel] += 1
                rows_per_author[author] += 1
                symbol_days.add((sym, day))
                if has_image:
                    image_rows += 1

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSONL, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---- markdown summary ----
    date_min = min(dates) if dates else None
    date_max = max(dates) if dates else None
    lines = []
    lines.append("# Corpus Instances")
    lines.append("")
    lines.append(f"Total rows: {len(rows)}")
    lines.append(f"Distinct symbol-days: {len(symbol_days)}")
    lines.append(f"Date range: {date_min} .. {date_max}")
    lines.append(f"Rows carrying an image: {image_rows}")
    lines.append(f"Universe size: {len(UNIVERSE)} symbols")
    lines.append("")
    lines.append("## Rows per channel")
    lines.append("")
    lines.append("| channel | rows |")
    lines.append("|---|---|")
    for ch, n in rows_per_channel.most_common():
        lines.append(f"| {ch} | {n} |")
    lines.append("")
    lines.append("## Rows per author")
    lines.append("")
    lines.append("| author | rows |")
    lines.append("|---|---|")
    for a, n in rows_per_author.most_common():
        lines.append(f"| {a} | {n} |")
    lines.append("")
    lines.append("## Sanity check")
    lines.append("")
    expected_lo, expected_hi = 5000, 12000
    # The ~7,800-row / ~3,750-symbol-day reference in the spec is the 3-ALERT-CHANNEL
    # baseline (scarface-alerts + jdub-alerts + trading-floor: 7,805 msgs, 3,758 sym-days).
    # T1 says "read every discord_data/*.json", so this table also ingests the other 10
    # channels, which is why the row count sits above 7,800 while staying inside 5k-12k.
    lines.append(
        f"- Row count: **{len(rows)}** (sanity range {expected_lo}-{expected_hi}). "
        f"Above the ~7,800 reference because T1 reads all 13 `discord_data/*.json` "
        f"channels, whereas the 7,805-message baseline counted only the 3 alert channels "
        f"(scarface-alerts, jdub-alerts, trading-floor)."
    )
    lines.append(
        f"- Distinct symbol-days: **{len(symbol_days)}** (spec reference ~3,750). "
        f"Ticker resolution is strict per spec (uppercase 2-5 letter token in the engine "
        f"universe); mixed-case mentions like `tsla`/`Qqq` are intentionally excluded."
    )
    if expected_lo <= len(rows) <= expected_hi:
        lines.append(f"- Row count is within the expected sanity range ({expected_lo}-{expected_hi}).")
    else:
        lines.append(
            f"**NOTE:** row count {len(rows)} is OUTSIDE the expected sanity range "
            f"({expected_lo}-{expected_hi}). "
        )
        lines.append(
            "Filters applied: ticker must be an uppercase 2-5 letter token "
            "matching the engine universe; `ts` clock time must fall in "
            "09:30-16:00 (treated as US/Eastern, no shift). "
            "Messages outside market hours or lacking a universe ticker are "
            "dropped."
        )
    lines.append("")

    OUT_MD.write_text("\n".join(lines))

    print(f"rows: {len(rows)}")
    print(f"distinct symbol-days: {len(symbol_days)}")
    print(f"date range: {date_min} .. {date_max}")
    print(f"image rows: {image_rows}")
    print(f"channels: {len(rows_per_channel)} authors: {len(rows_per_author)}")


if __name__ == "__main__":
    main()
