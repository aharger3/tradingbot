#!/usr/bin/env python3
"""Deterministic parser for discord_data/jdub-trade-reviews.json.

WHAT THIS CHANNEL ACTUALLY IS
-----------------------------
It is NOT a prose trade-review channel. All 129 messages are from one author
("Jdub") and every one of them is a link announcement for a YouTube video --
either a daily/weekly/monthly recap ("Weekly Trading Recap March 8th <url>")
or a YouTube upload notification whose *title* carries the P/L and, sometimes,
the setup ("@everyone Jdub Trades just uploaded How I Made $5200 Live Day
Trading (PDL Reclaim Setup) at <url>").

So the only structured judgement that exists in the text is:
  - the dollar P/L and its sign (made / lost)
  - the aggregation period the P/L covers (day / week / month)
  - occasionally a level name (PDH / PDL / 5-min range high / low)
  - occasionally a setup word (retest / reclaim)
  - the video URL, which is where the actual review lives

There are ZERO symbols, entries, stops, targets or R-multiples anywhere in the
file. Those fields are emitted as null, always -- see verify_no_invented_fields().

SCHEMA
------
Required keys (per spec): src, msg_id, ts, author, symbol, direction, setup,
level_price, level_name, entry, stop, target, outcome, r_multiple, quote,
image_urls, confidence.

Three EXTRA keys are emitted because dropping them would throw away the only
real signal this file has. They are additive; a consumer that ignores them
still gets a valid row:
  - pl_dollars : float|null  -- signed USD P/L stated in the title
  - period     : "day"|"week"|"month"|null -- what the P/L covers. CRITICAL:
                 a week/month row is an ACCOUNT AGGREGATE, not one trade.
  - video_url  : str|null    -- the review itself

r_multiple stays null even when pl_dollars is known: 1R = $1,000 is Austin's
sizing convention, not Jdub's, and converting would be inventing a number.

Usage:  python research/corpus_sf/parse_reviews_jdub.py
        python research/corpus_sf/parse_reviews_jdub.py --sample
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(REPO, "discord_data", "jdub-trade-reviews.json")
OUT = os.path.join(REPO, "research", "corpus_sf", "reviews_jdub.jsonl")
SRC_NAME = "discord_data/jdub-trade-reviews.json"

# ---------------------------------------------------------------- time

def _nth_sunday(year: int, month: int, n: int) -> datetime:
    d = datetime(year, month, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)  # first Sunday
    return d + timedelta(weeks=n - 1)


def utc_to_et(naive_utc: str) -> str:
    """Discord API timestamps are UTC (discord_scraper.py: m['timestamp'][:19]).

    Confirmed empirically: '2024-08-18T01:40:20' carries the title
    'Weekly Trade Recap August 17th' -- 01:40 UTC == 21:40 ET on Aug 17.

    US Eastern: DST from 2nd Sunday of March 02:00 local to 1st Sunday of
    November 02:00 local. Implemented inline so the parser has no tz deps.
    """
    dt = datetime.strptime(naive_utc[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    y = dt.year
    start = _nth_sunday(y, 3, 2).replace(hour=7)   # 02:00 EST = 07:00 UTC
    end = _nth_sunday(y, 11, 1).replace(hour=6)    # 02:00 EDT = 06:00 UTC
    start = start.replace(tzinfo=timezone.utc)
    end = end.replace(tzinfo=timezone.utc)
    off = -4 if start <= dt < end else -5
    return dt.astimezone(timezone(timedelta(hours=off))).isoformat()


# ---------------------------------------------------------------- regexes

URL_RE = re.compile(r"https?://\S+")
YT_RE = re.compile(r"https?://(?:youtu\.be/|www\.youtube\.com/watch\?v=)([\w-]{6,})")
PLAYLIST_RE = re.compile(r"youtube\.com/playlist", re.I)
IMG_RE = re.compile(r"\.(?:png|jpe?g|gif|webp)(?:\?|$)", re.I)

# "$6600", "+$2500", "(+2500)", "$10,500", "$35,000"
MONEY_RE = re.compile(r"[+\-]?\$?\s?(\d{1,3}(?:,\d{3})+|\d{3,6})(?![\d.%])")

# verb that gives the sign of the P/L
WIN_VERB_RE = re.compile(r"\b(?:how i made|i made|making|made)\b", re.I)
LOSS_VERB_RE = re.compile(r"\b(?:how i lost|i lost|losing|lost|down)\b", re.I)

PERIOD_MONTH_RE = re.compile(r"\bthis month\b|\bof the month\b", re.I)
PERIOD_WEEK_RE = re.compile(
    r"\bthis week\b|\blast week\b|\bon the week\b|\bof the week\b|\bweekly\b|\bweek recap\b", re.I
)

# a trailing "(...)" editorial tag on the video title
PAREN_RE = re.compile(r"\(([^)]{2,60})\)")

BE_RE = re.compile(r"\bbreak\s?even\b|\bbasically breakeven\b|\bflat\b", re.I)

# ---- levels. ORDER MATTERS: longest/most specific first.
LEVEL_PATTERNS = [
    ("pdh", re.compile(r"\bpdh\b|\bprevious day(?:'s)? high\b|\bprior day high\b", re.I)),
    ("pdl", re.compile(r"\bpdl\b|\bprevious day(?:'s)? low\b|\bprior day low\b", re.I)),
    ("pmh", re.compile(r"\bpmh\b|\bpre-?market high\b", re.I)),
    ("pml", re.compile(r"\bpml\b|\bpre-?market low\b", re.I)),
    ("hod", re.compile(r"\bhod\b|\bhigh of (?:the )?day\b", re.I)),
    ("lod", re.compile(r"\blod\b|\blow of (?:the )?day\b", re.I)),
    # the 5-minute opening-range levels -- Jdub's "5 min high / 5 min low"
    ("or_high", re.compile(r"\b5\s?-?\s?min(?:ute)?\s+high\b|\bopening range high\b|\bor high\b", re.I)),
    ("or_low", re.compile(r"\b5\s?-?\s?min(?:ute)?\s+low\b|\bopening range low\b|\bor low\b", re.I)),
]
# "5 Min Range Strategy" / "5 MINUTE STRATEGY" names the range, not a side.
OR_RANGE_RE = re.compile(r"\b5\s?-?\s?min(?:ute)?\s+range\b", re.I)

RETEST_RE = re.compile(r"\bre-?test\b|\bbreak and re-?test\b|\bb&r\b", re.I)
RECLAIM_RE = re.compile(r"\breclaim\b", re.I)
OCR_RE = re.compile(r"\bone[\s-]?candle\b|\bocr\b|\b1[\s-]?candle\b", re.I)

# Real US tickers are never emitted from this file, but keep the guard so a
# future message with one is caught rather than silently dropped.
TICKER_RE = re.compile(r"\$([A-Z]{1,5})\b|\b(SPY|QQQ|IWM|TSLA|NVDA|AAPL|AMD|MSFT|META|AMZN|NFLX|GOOG|GOOGL|COIN|MSTR|PLTR|SMCI|AVGO|CRWD|SHOP|BABA|ES|NQ)\b")

# noise that is not a P/L number
NOT_MONEY_CONTEXT_RE = re.compile(r"\b(?:20\d\d)\b")


def find_symbol(text: str):
    m = TICKER_RE.search(text)
    if not m:
        return None
    return (m.group(1) or m.group(2)).upper()


def headline(text: str) -> str:
    """The part of a video title before its trailing editorial "(...)" tag.

    FIX (hand-check round 1): the parenthetical is running commentary about the
    week or the market, not about the trade being reported. Reading period or
    P/L out of it produced wrong rows:
      "Losing $8000 Live Day Trading (I'M UP $3K THIS WEEK)"
        -> was period=week. It is a DAY loss of $8000; the week is context.
      "Making $35,000 Live Day Trading (I'M UP 83K THIS WEEK)"  -> same bug.
      "Losing $800 Live Day Trading (I'M RED ON THE WEEK)"      -> same bug.
    So period and the plain-$ amount are read from the headline only. Level and
    setup are still read from the FULL text, because the parenthetical is
    exactly where Jdub names them: "(PDL Reclaim Setup)", "(5 MIN HIGH RETEST)".
    """
    i = text.find("(")
    return text[:i].strip() if i > 0 else text


def find_money(text: str):
    """Return signed USD P/L stated in the title, or None.

    Only fires when the text carries an explicit $ amount AND a made/lost verb
    (or a bare '+NNNN' in parentheses, which Jdub used twice in 2024).
    """
    # explicit "(+2500)" / "(+$6600)" -- the whole title IS the amount
    m = re.search(r"\(\s*([+\-])\s*\$?\s?(\d{1,3}(?:,\d{3})+|\d{3,7})\s*\)", text)
    if m:
        v = float(m.group(2).replace(",", ""))
        return v if m.group(1) == "+" else -v

    hl = headline(text)
    # need a dollar sign to avoid grabbing dates/ids
    dm = re.search(r"\$\s?(\d{1,3}(?:,\d{3})+|\d{3,7})\b", hl)
    if not dm:
        return None
    val = float(dm.group(1).replace(",", ""))

    head = hl[: dm.start()]
    if LOSS_VERB_RE.search(head):
        return -val
    if WIN_VERB_RE.search(head):
        return val
    return None


def find_period(text: str):
    """What the headline P/L covers. Headline only -- see headline()."""
    hl = headline(text)
    if PERIOD_MONTH_RE.search(hl):
        return "month"
    if PERIOD_WEEK_RE.search(hl):
        return "week"
    if re.search(r"\bday trading\b|\bdaily\b|\btrade recap\b|\btoday\b", hl, re.I):
        return "day"
    return None


def find_level(text: str):
    for name, rx in LEVEL_PATTERNS:
        if rx.search(text):
            # NOTE: the spec's level_name enum lists or_high but has no or_low,
            # even though the 5-min opening-range low is one of the six levels
            # the engine trades. Emitting "or_low" verbatim rather than folding
            # it into "other", which would destroy the level identity.
            return name
    if OR_RANGE_RE.search(text):
        return None  # names the range, not one of the six levels
    return None


def find_setup(text: str):
    ret = bool(RETEST_RE.search(text))
    ocr = bool(OCR_RE.search(text))
    if ret and ocr:
        return "br_ocr"
    if ret:
        return "break_retest"
    if ocr:
        return "one_candle"
    if RECLAIM_RE.search(text):
        # a reclaim is the retest side of a break-and-retest in Jdub's language
        return "break_retest"
    return None


def find_outcome(text: str, pl):
    """FIX (hand-check round 1): when a dollar P/L is stated, outcome follows
    its SIGN. Previously "How I Made $1400 Day Trading (BASICALLY BREAKEVEN)"
    was emitted as outcome=be with pl_dollars=+1400 -- internally contradictory.
    The breakeven wording is Jdub's editorial read; it now only downgrades
    confidence (see conflicting_be()), it does not override +1400 into "be".
    """
    if pl is not None:
        return "win" if pl > 0 else ("loss" if pl < 0 else "be")
    if BE_RE.search(text):
        return "be"
    if LOSS_VERB_RE.search(text):
        return "loss"
    return None


def conflicting_be(text: str, pl) -> bool:
    """Jdub called it breakeven but the stated number is not zero."""
    return pl is not None and pl != 0 and bool(BE_RE.search(text))


def images(msg):
    out = [u for u in msg.get("attachments", []) if IMG_RE.search(str(u))]
    out += [u for u in msg.get("embeds", []) if IMG_RE.search(str(u))]
    return sorted(set(out))


def video_url(text, msg):
    m = YT_RE.search(text)
    if m:
        return m.group(0).rstrip(".,)")
    for e in msg.get("embeds", []):
        if YT_RE.search(str(e)):
            return str(e)
    return None


def clean(text: str) -> str:
    """Strip discord mention tokens and the URL so keyword matching is clean."""
    t = re.sub(r"<@&?\d+>", " ", text)
    t = t.replace("@everyone", " ").replace("@here", " ")
    t = URL_RE.sub(" ", t)
    t = re.sub(r"\bJdub Trades just uploaded\b", " ", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


SKIP_REASONS = {}


def parse_message(msg):
    raw = msg.get("content", "") or ""
    mid = msg.get("id")
    body = clean(raw)

    # a bare-link message or a playlist index carries no judgement
    if PLAYLIST_RE.search(raw):
        SKIP_REASONS[mid] = "playlist index, no trade content"
        return None
    if not body:
        SKIP_REASONS[mid] = "bare url, no text"
        return None

    pl = find_money(body)
    period = find_period(body)
    level = find_level(body)
    setup = find_setup(body)
    outcome = find_outcome(body, pl)
    sym = find_symbol(body)

    # A row must carry at least one substantive field beyond the date/title.
    if pl is None and level is None and setup is None and sym is None and outcome is None:
        SKIP_REASONS[mid] = "recap title only: date + link, no P/L, level, setup or symbol"
        return None

    # ---- confidence
    # high   : explicit signed $ P/L (the title states it outright)
    # medium : a level or setup keyword but no P/L, or an aggregate-period P/L
    #          whose parenthetical tag is editorial rather than numeric
    # low    : outcome inferred from wording alone
    if conflicting_be(body, pl):
        conf = "medium"  # "(BASICALLY BREAKEVEN)" sitting on a +$1400 day
    elif pl is not None and period == "day":
        conf = "high"
    elif pl is not None:
        conf = "medium"  # week/month aggregate, or period unknown
    elif level is not None or setup is not None:
        conf = "medium"
    else:
        conf = "low"

    row = {
        "src": SRC_NAME,
        "msg_id": mid,
        "ts": utc_to_et(msg["ts"]),
        "author": msg.get("author"),
        "symbol": sym,
        "direction": None,          # never stated in this channel
        "setup": setup,
        "level_price": None,        # never stated
        "level_name": level,
        "entry": None,              # never stated
        "stop": None,               # never stated
        "target": None,             # never stated
        "outcome": outcome,
        "r_multiple": None,         # never stated; $->R would be inventing
        "quote": raw,
        "image_urls": images(msg),
        "confidence": conf,
        # --- additive, documented in the module docstring
        "pl_dollars": pl,
        "period": period,
        "video_url": video_url(raw, msg),
    }
    return row


def verify_no_invented_fields(rows):
    """These four are never stated anywhere in this file. Assert it."""
    for r in rows:
        for k in ("level_price", "entry", "stop", "target", "r_multiple", "direction"):
            assert r[k] is None, f"{r['msg_id']}: {k} was populated from a file that never states it"


def main():
    with open(SRC, encoding="utf-8") as f:
        msgs = json.load(f)

    rows, skipped = [], []
    for m in msgs:
        r = parse_message(m)
        if r is None:
            skipped.append(m)
        else:
            rows.append(r)

    verify_no_invented_fields(rows)

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def c(key):
        return sum(1 for r in rows if r.get(key) is not None)

    print(f"messages      {len(msgs)}")
    print(f"extracted     {len(rows)}")
    print(f"skipped       {len(skipped)}")
    print(f"  with symbol    {c('symbol')}")
    print(f"  with direction {c('direction')}")
    print(f"  with setup     {c('setup')}")
    print(f"  with level     {c('level_name')}")
    print(f"  with outcome   {c('outcome')}")
    print(f"  with pl_dollars{c('pl_dollars')}")
    print(f"  with image     {sum(1 for r in rows if r['image_urls'])}")
    print(f"  period day/week/month "
          f"{sum(1 for r in rows if r['period']=='day')}/"
          f"{sum(1 for r in rows if r['period']=='week')}/"
          f"{sum(1 for r in rows if r['period']=='month')}")
    print(f"  ts range   {min(r['ts'] for r in rows)} .. {max(r['ts'] for r in rows)}")
    print(f"-> {OUT}")

    if "--sample" in sys.argv:
        import random
        random.seed(7)
        print("\n==================== 30 EXTRACTED ====================")
        for r in random.sample(rows, min(30, len(rows))):
            print(f"[{r['ts'][:10]}] out={r['outcome']} pl={r['pl_dollars']} "
                  f"per={r['period']} lvl={r['level_name']} setup={r['setup']} "
                  f"conf={r['confidence']}\n    {clean(r['quote'])}")
        print("\n==================== 15 SKIPPED ====================")
        for m in random.sample(skipped, min(15, len(skipped))):
            print(f"[{m['ts']}] {SKIP_REASONS.get(m['id'])}\n    {m['content']}")


if __name__ == "__main__":
    main()
