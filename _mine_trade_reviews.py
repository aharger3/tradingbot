"""Mine discord_data for trade-review judgments: specific trades called good/bad + why."""
import json, os, re, sys
from collections import defaultdict
from pathlib import Path

DATA = Path(r"C:\Users\aharg\tradingbot\discord_data")
OUT = Path(r"C:\Users\aharg\tradingbot\_trade_reviews_mined.json")

# Priority order: check these for judgments
REVIEW_FILES = [
    "futures-trade-reviews.json",
    "jdub-trade-reviews.json",
    "options-trade-reviews.json",
    "scarface-trade-reviews.json",
    "trade-feedback.json",
    "trading-floor.json",
    "jdub-alerts.json",
    "futures-alerts.json",
    "scarface-alerts.json",
    "live-sessions.json",
    "premarket-charts.json",
    "swing-ideas.json",
    "backtesting.json",
]

# Strong judgment keywords (adjective + trade/entry/exit)
STRONG_JUDGMENT = re.compile(
    r'\b(great|good|bad|terrible|horrible|beautiful|perfect|clean|sloppy|nasty|solid|excellent|amazing|awful|trash|stupid|smart|best|worst|dumb|sharp|smooth|rough|tight|weak|strong|reckless|disciplined|greedy|scared)'
    r'\s+(trade|call|entry|exit|fill|play|move|read|pick|signal|alert|setup)',
    re.IGNORECASE
)

# Pattern: X is/was a good/bad/... trade
COPULA_JUDGMENT = re.compile(
    r'(trade|call|entry|exit|play|move)\s+(was|is|looks?|feels?|seems?)\s+(good|bad|great|terrible|solid|perfect|sloppy|clean|trash|smart|dumb|amazing|awful|beautiful)',
    re.IGNORECASE
)

# P&L mention with value
PL_PATTERN = re.compile(
    r'[+-]?\$[\d,]+(?:\.\d{2})?|\b(?:profit|loss|made|lost|gained|paid|bought|sold)\s+\$[\d,]+',
    re.IGNORECASE
)

SHOULD_JUDGMENT = re.compile(
    r"(should(?:\s+have|\s+n't\s+have|n't|'ve|n't\s+have)?)\s+(\w+\s*){0,4}(taken|entered|sold|bought|held|closed|exited|cut|added|scaled)",
    re.IGNORECASE
)

TICKER_PATTERN = re.compile(
    r'\b[A-Z]{1,5}\s+(long|short|called|took|hit|ran|ripped|dumped|crashed|pumped|printed|filled|cancelled|stopped|targeted)\b|\b(long|short)\s+[A-Z]{1,5}\b',
    re.IGNORECASE
)

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"  ERROR loading {path}: {e}", file=sys.stderr)
        return []

def extract_judgments(msg):
    """Score a message for trade-judgment content. Return (score, categories)"""
    content = msg.get("content", "") or ""
    score = 0
    cats = []

    matches = STRONG_JUDGMENT.findall(content)
    if matches:
        score += len(matches) * 2
        cats.append("adj-trade")

    matches = COPULA_JUDGMENT.findall(content)
    if matches:
        score += len(matches) * 2
        cats.append("copula-judgment")

    if PL_PATTERN.search(content):
        score += 1
        cats.append("pnl-mention")

    if SHOULD_JUDGMENT.search(content):
        score += 2
        cats.append("should-judgment")

    if TICKER_PATTERN.search(content):
        score += 1
        cats.append("ticker-action")

    # Specific "good" or "bad" on its own near trade terms
    if re.search(r'\b(good|bad|trash|amazing|terrible|perfect|sloppy)\b', content, re.IGNORECASE):
        score += 1
        cats.append("polar-term")

    return score, cats

def extract_trade_info(content):
    """Extract tickers, numbers, direction from content"""
    tickers = set()
    # Find ticker patterns
    for m in re.finditer(r'\b([A-Z]{1,5})\s*[/.]?[A-Z]?\b', content):
        t = m.group(1)
        if t.upper() in ("I", "A", "THE", "FOR", "AND", "NOT", "YOU", "ALL", "CAN", "ARE", "BUT", "HAS", "WAS", "OUT", "ITS", "ONE", "WAY", "MAY", "SAID", "GET", "SEE", "USE", "NOW", "NEW", "HOW", "ANY", "TWO", "MORE", "DAY", "NQ", "ES", "YM", "RTY", "CL", "GC", "SI"):
            continue
        if len(t) >= 2 and len(t) <= 5:
            tickers.add(t.upper())

    return tickers

def main():
    all_judgments = []
    total_msgs = 0
    scored_msgs = 0

    for fname in REVIEW_FILES:
        path = DATA / fname
        if not path.exists():
            continue
        data = load_json(path)
        if not data:
            continue
        total_msgs += len(data)

        channel_matches = []
        for msg in data:
            content = msg.get("content", "") or ""
            score, cats = extract_judgments(msg)
            if score >= 2:  # threshold
                channel_matches.append({
                    "id": msg.get("id", ""),
                    "ts": msg.get("ts", ""),
                    "author": msg.get("author", ""),
                    "content": content,
                    "score": score,
                    "categories": cats,
                    "tickers": list(extract_trade_info(content)),
                    "reply_to": msg.get("reply_to"),
                })
                scored_msgs += 1

        print(f"  {fname}: {len(data)} msgs -> {len(channel_matches)} judgment msgs")
        all_judgments.append({
            "channel": fname.replace(".json", ""),
            "total_messages": len(data),
            "judgment_count": len(channel_matches),
            "messages": channel_matches,
        })

    # Save full output
    out = {
        "total_messages_scanned": total_msgs,
        "total_judgments": scored_msgs,
        "channels": all_judgments,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Scanned {total_msgs} messages across {len(REVIEW_FILES)} files")
    print(f"Extracted {scored_msgs} messages with trade-judgment content")
    print(f"Output: {OUT}")

    # Summary stats
    print(f"\nBy channel:")
    for ch in all_judgments:
        if ch["judgment_count"] > 0:
            print(f"  {ch['channel']}: {ch['judgment_count']} judgments / {ch['total_messages']} msgs")

if __name__ == "__main__":
    main()
