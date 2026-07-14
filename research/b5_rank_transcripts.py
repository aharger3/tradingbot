#!/usr/bin/env python3
"""B5: Rank YouTube transcripts by title + content relevance.

Two signals:
  (a) Title keywords (same as before but simplified)
  (b) First 3000 chars scanned for trading-methodology term frequency

Weighted: 40% title, 60% content.
Outputs ranked list to b5_ranking.csv, top 100 filenames to stdout.
"""
import re, csv, sys
from pathlib import Path
from collections import Counter

YOUTUBE = Path(r"C:\Users\aharg\tradingbot\youtube_data")

# Weight
TITLE_WT = 0.4
CONTENT_WT = 0.6

# Keywords for title scoring (tiered)
TITLE_L1 = [
    r"\border\s*blocks?\b", r"\bopening\s*(range|candle|drive|plays?)\b",
    r"\bbreak\s*(and|&)?\s*retest\b", r"\b84[%\s]*rule\b", r"\bre[- ]?entries?\b",
    r"\breclaim\b", r"\bconfluence\b", r"\bA\+?\s*setup", r"\bdisplacement\b",
    r"\bFVG\b", r"\bone\s*candle\s*rule\b", r"\bscalping?\b",
    r"\bswing\b", r"\bplaybook\b", r"\bpre.?market\b.*(high|low|level)",
    r"\bkey\s*levels?\b"
]
TITLE_L2 = [
    r"\bQQQ\b", r"\bindex\b", r"\breversal\b", r"\btrend\b",
    r"\bgap\s*(fill|go)\b", r"\bliquidity\b", r"\bfutures\b",
    r"\bhow\s+to\b", r"\bpick\b.*\bwatchlist\b",
    r"\bpsychology\b", r"\bmindset\b",
    r"\brisk\s*manage\b", r"\bsizing?\b",
    r"\bperformance\b", r"\bdiscipline\b", r"\broutine\b",
    r"\bweekly\s*(recap|session)\b",
    r"\btrade\s*(review|recap)\b",
    r"\bmarket\s*structure\b",
    r"\bprice\s*action\b",
    r"\bpractice\b"
]
TITLE_L1_WT = 8
TITLE_L2_WT = 3

# Content keywords — count occurrences in first 3KB
CONTENT_KW = [
    "break and retest", "order block", "one candle rule", "retest",
    "opening candle", "opening range", "opening drive",
    "84%", "re-entry", "re-entry",
    "reclaim", "confluence", "A+", "A setup",
    "displacement", "FVG", "hammer", "shooting star",
    "key level", "support and resistance", "PDH", "PDL", "PMH",
    "pre-market high", "pre-market low",
    "gap fill", "gap go", "stop loss", "profit target",
    "scale out", "scale in", "trailing stop", "breakeven",
    "risk management", "risk to reward", "win rate",
    "trend", "reversal", "liquidity", "swing trade",
    "QQQ", "index", "futures",
    "entry trigger", "confirmation candle", "close above", "close below",
    "trending", "consolidation", "chop",
    "A+ setup", "A+ entry",
    "daily level", "weekly level",
    "max risk", "position size", "risk per trade",
    "price action", "market structure",
    "first break", "first retest", "second entry",
    "trade management", "exit strategy",
    "psychology", "mindset", "discipline",
    "watchlist", "pre-market prep",
    "high probability", "low probability",
]


def score_title(title):
    """Score title by keyword presence."""
    t = title.lower()
    s = 0
    for pat in TITLE_L1:
        if re.search(pat, t):
            s += TITLE_L1_WT
    for pat in TITLE_L2:
        if re.search(pat, t):
            s += TITLE_L2_WT
    return s


def score_content(text_sample):
    """Score content snippet by keyword frequency."""
    t = text_sample.lower()
    s = 0
    for kw in CONTENT_KW:
        c = t.count(kw)
        if c:
            s += c * (2 if len(kw.split()) >= 2 else 1)
    return s


def extract_info(filepath):
    """Extract title and content sample from transcript."""
    raw = filepath.read_text(encoding="utf-8", errors="replace")
    lines = raw.split("\n")

    # Title is first line, may or may not start with #
    first = lines[0].strip()
    title = first.lstrip("# ").strip() if first.startswith("#") else first[:80].strip()

    # Get first 3000 chars of actual content (skip title line)
    content = "\n".join(lines[1:])[:3000]

    return title, len(raw), content


def main():
    files = sorted(YOUTUBE.glob("*_transcript.txt"))
    print(f"Found {len(files)} transcript files", file=sys.stderr)

    results = []
    for fp in files:
        title, size, content_snip = extract_info(fp)

        t_score = score_title(title)
        c_score = score_content(content_snip)

        # Normalize: content score is absolute, title score is additive
        combined = TITLE_WT * t_score + CONTENT_WT * c_score

        results.append((combined, t_score, c_score, fp.name, title, size))

    results.sort(key=lambda x: (-x[0], -x[2], x[3]))

    # CSV
    csv_path = Path(r"C:\Users\aharg\tradingbot\research") / "b5_ranking.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "combined_score", "title_score", "content_score", "filename", "title", "size_bytes"])
        for i, (cb, ts, cs, fn, ti, sz) in enumerate(results):
            w.writerow([i+1, round(cb, 1), ts, cs, fn, ti, sz])

    print(f"CSV: {csv_path}", file=sys.stderr)

    # Stats
    all_scores = [r[0] for r in results]
    print(f"Score range: {min(all_scores):.1f} to {max(all_scores):.1f}", file=sys.stderr)
    print(f"Median: {sorted(all_scores)[len(all_scores)//2]:.1f}", file=sys.stderr)
    print(f"Mean: {sum(all_scores)/len(all_scores):.1f}", file=sys.stderr)

    # Top 100 with scores
    top100 = results[:100]
    threshold = top100[-1][0]
    print(f"\nTop 100 threshold: {threshold:.1f}", file=sys.stderr)

    # Print for consumption
    print(f"RANK\tCOMB\tTITLE\tCONTENT\tFILENAME\tTITLE_SHORT")
    for i, (cb, ts, cs, fn, ti, sz) in enumerate(results):
        ti_short = ti[:60]
        print(f"{i+1}\t{cb:.1f}\t{ts}\t{cs}\t{fn}\t{ti_short}")

    return [r[3] for r in top100], results


if __name__ == "__main__":
    top100, all_ranked = main()
