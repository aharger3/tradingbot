#!/usr/bin/env python3
"""Deterministic parser for discord_data/premarket-charts.json.

WHAT THIS CHANNEL ACTUALLY IS
-----------------------------
591 messages, every one authored by TonyMontana, every one carrying 1-10 chart
image attachments (3,980 images total).  The message *text* is a date header and
nothing else -- mean content length 21.9 chars, max 61.  There is not one decimal
number, not one level name, and (with one exception) not one ticker in the entire
text corpus:

    grep -c '[0-9]\\.[0-9]'  -> 0 messages
    embeds                   -> 0
    reply_to                 -> 0
    attachment filenames     -> image.png / IMG_1234.png, zero symbol info

So the levels this channel is famous for live *inside the PNGs*.  A regex parser
cannot recover level_name / level_price / entry / stop / target from text that
does not contain them, and inventing them is forbidden.  What this parser does
instead, honestly:

  * resolves the SESSION DATE the human wrote in the header ("April 2nd, 2024",
    "September 10", "UPDATED MARCH 23 LEVELS") and reconciles it against the
    message timestamp -- this is the join key a later vision/OCR pass needs;
  * emits one row per message with the full image_urls[] list, so the chart set
    for a trading day is addressable;
  * fills symbol only when a ticker is literally written in the text (1 message);
  * leaves every price/level/outcome field null, which is the correct value.

Output: research/corpus_sf/premarket_charts.jsonl
Run:    python research/corpus_sf/parse_premarket_charts.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(REPO, "discord_data", "premarket-charts.json")
OUT = os.path.join(REPO, "research", "corpus_sf", "premarket_charts.jsonl")

# ---------------------------------------------------------------- ticker vocab
try:
    sys.path.insert(0, REPO)
    import universe  # noqa: E402

    KNOWN = set(getattr(universe, "ALL_SYMS", []))
except Exception:  # universe.py is the single source of truth; never inline a list
    KNOWN = set()

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

# "April 2nd, 2024" | "September 10" | "MARCH 23" | "Feb 3rd"
# The word class is deliberately loose (any alpha run) so that the human's
# typos -- "Novermber 14th", "Decenber 24" -- still reach the fuzzy matcher
# below instead of silently failing to parse.
RE_MONTH_DAY = re.compile(
    r"\b([A-Za-z]{3,12})\b\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(20\d{2}))?",
)


def _match_month(word: str):
    """Exact month name, else a one-edit-distance typo of one. None otherwise."""
    w = word.lower()
    if w in MONTHS:
        return MONTHS[w], True
    for name, num in MONTHS.items():
        if len(name) < 4 or abs(len(name) - len(w)) > 1:
            continue
        if _within_one_edit(w, name):
            return num, False
    return None, None


def _within_one_edit(a: str, b: str) -> bool:
    if a == b:
        return True
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    if len(b) - len(a) != 1:
        return False
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]
# "4/2/24", "4-2-2024"
RE_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")

RE_MENTION = re.compile(r"<@[!&]?\d+>")
RE_EMOJI = re.compile(r"<a?:\w+:\d+>")
RE_TICKER_CAND = re.compile(r"\b[A-Z]{2,5}\b")

# words that look like tickers but are not
TICKER_STOP = {
    "AM", "PM", "ET", "EST", "EDT", "OK", "THE", "AND", "FOR", "YOU", "ALL",
    "NEW", "OLD", "PRE", "HERE", "GO", "LOAD", "CHART", "LEVEL", "LEVELS",
    "UPDATED", "UPDATE", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUG",
    "SEPT", "OCT", "NOV", "DEC", "JAN", "FEB", "MON", "TUE", "WED", "THU",
    "FRI", "OR", "PDH", "PDL", "PMH", "PML", "HOD", "LOD",
}

LEVEL_WORDS = [
    (re.compile(r"\b(or[\s_-]?high|opening\s+range\s+high)\b", re.I), "or_high"),
    (re.compile(r"\b(or[\s_-]?low|opening\s+range\s+low)\b", re.I), "or_low"),
    (re.compile(r"\b(pdh|prev(?:ious)?\s+day\s+high)\b", re.I), "pdh"),
    (re.compile(r"\b(pdl|prev(?:ious)?\s+day\s+low)\b", re.I), "pdl"),
    (re.compile(r"\b(pmh|pre[\s-]?market\s+high)\b", re.I), "pmh"),
    (re.compile(r"\b(pml|pre[\s-]?market\s+low)\b", re.I), "pml"),
    (re.compile(r"\b(hod|high\s+of\s+day)\b", re.I), "hod"),
    (re.compile(r"\b(lod|low\s+of\s+day)\b", re.I), "lod"),
]

RE_LONG = re.compile(r"\b(long|calls?|bullish|break\s*out|upside)\b", re.I)
RE_SHORT = re.compile(r"\b(short|puts?|bearish|break\s*down|downside)\b", re.I)
RE_BR = re.compile(r"\b(break\s*(?:and|&|\+|/)?\s*re[\s-]?test|b\s*&\s*r|b/r)\b", re.I)
RE_OCR = re.compile(r"\b(one[\s-]?candle(?:\s+rule)?|ocr|1[\s-]?candle)\b", re.I)


def clean(text: str) -> str:
    t = RE_MENTION.sub(" ", text)
    t = RE_EMOJI.sub(" ", t)
    t = t.replace("@everyone", " ").replace("@here", " ")
    return re.sub(r"\s+", " ", t).strip()


def parse_header_date(text: str, post_day: date):
    """The date the human WROTE in the header. Returns (date|None, exact_spelling).

    This is reported separately from session_date on purpose: 12 of 591 headers
    disagree with the day they were posted ("September 15th" posted Sept 5), and
    those are typos in the header, not charts posted ten days early.
    """
    for m in RE_MONTH_DAY.finditer(text):
        mon, exact = _match_month(m.group(1))
        if mon is None:
            continue
        day = int(m.group(2))
        yr = int(m.group(3)) if m.group(3) else None
        if yr is None:
            best, bestgap = None, None
            for cand in (post_day.year - 1, post_day.year, post_day.year + 1):
                try:
                    d = date(cand, mon, day)
                except ValueError:
                    continue
                gap = abs((d - post_day).days)
                if bestgap is None or gap < bestgap:
                    best, bestgap = d, gap
            return best, exact
        try:
            return date(yr, mon, day), exact
        except ValueError:
            return None, exact

    m = RE_NUMERIC_DATE.search(text)
    if m:
        mon, day = int(m.group(1)), int(m.group(2))
        yr = m.group(3)
        yr = int(yr) + 2000 if yr and len(yr) == 2 else (int(yr) if yr else post_day.year)
        try:
            return date(yr, mon, day), True
        except ValueError:
            return None, True
    return None, None


def parse_symbol(text: str):
    for tok in RE_TICKER_CAND.findall(text):
        if tok in TICKER_STOP:
            continue
        if KNOWN and tok not in KNOWN:
            continue
        return tok
    return None


def parse_level_name(text: str):
    for rx, name in LEVEL_WORDS:
        if rx.search(text):
            return name
    return None


def parse_direction(text: str):
    lo, sh = bool(RE_LONG.search(text)), bool(RE_SHORT.search(text))
    if lo and not sh:
        return "long"
    if sh and not lo:
        return "short"
    return None


def parse_setup(text: str):
    br, ocr = bool(RE_BR.search(text)), bool(RE_OCR.search(text))
    if br and ocr:
        return "br_ocr"
    if br:
        return "break_retest"
    if ocr:
        return "one_candle"
    return None


def parse_price_after(text: str, anchor_rx):
    """Only ever returns a number that is literally written next to a keyword."""
    m = anchor_rx.search(text)
    if not m:
        return None
    tail = text[m.end(): m.end() + 24]
    n = re.search(r"(\d{1,6}(?:\.\d{1,4})?)", tail)
    return float(n.group(1)) if n else None


RE_ENTRY = re.compile(r"\b(entry|entries|enter|trigger)\b\s*[:@-]?\s*", re.I)
RE_STOP = re.compile(r"\b(stop|sl|stop\s*loss)\b\s*[:@-]?\s*", re.I)
RE_TARGET = re.compile(r"\b(target|pt\d?|tp\d?)\b\s*[:@-]?\s*", re.I)
RE_R = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*R\b")
RE_WIN = re.compile(r"\b(win|winner|hit\s+(?:pt|target)|profit)\b", re.I)
RE_LOSS = re.compile(r"\b(loss|loser|stopped\s+out|stop\s+hit)\b", re.I)
RE_BE = re.compile(r"\b(break\s*even|breakeven|\bb/?e\b)\b", re.I)


def parse_outcome(text: str):
    if RE_WIN.search(text):
        return "win"
    if RE_LOSS.search(text):
        return "loss"
    if RE_BE.search(text):
        return "be"
    return None


def main():
    with open(SRC, encoding="utf-8") as fh:
        msgs = json.load(fh)

    rows, skipped = [], []
    for m in msgs:
        # The export stamps UTC with no offset. Premarket charts land 08:00-10:00
        # ET; reading the raw clock as ET would put them at lunchtime.
        ts_utc = datetime.fromisoformat(m["ts"]).replace(tzinfo=timezone.utc)
        ts = ts_utc.astimezone(ET)
        txt = clean(m.get("content", ""))
        imgs = list(m.get("attachments") or [])

        # session_date is the ET day the chart set was POSTED -- every set is
        # posted premarket on the morning it is for. The header date is recorded
        # beside it, not instead of it, because the header is sometimes mistyped.
        sess = ts.date()
        hdr, hdr_exact = parse_header_date(txt, sess)

        sym = parse_symbol(txt)
        if not imgs and not sym:
            skipped.append({"msg_id": m["id"], "ts": m["ts"], "text": txt,
                            "reason": "no attachments and no symbol"})
            continue

        # confidence describes the (date -> chart set) binding, the only claim
        # this row makes. High when the human's own header agrees with the day.
        conf = "high" if (imgs and hdr == sess) else ("medium" if imgs else "low")

        rows.append({
            "src": "discord_data/premarket-charts.json",
            "msg_id": m["id"],
            "ts": ts.isoformat(),
            "author": m["author"],
            "symbol": sym,
            "direction": parse_direction(txt),
            "setup": parse_setup(txt),
            "level_price": None,          # never written in text in this channel
            "level_name": parse_level_name(txt),
            "entry": parse_price_after(txt, RE_ENTRY),
            "stop": parse_price_after(txt, RE_STOP),
            "target": parse_price_after(txt, RE_TARGET),
            "outcome": parse_outcome(txt),
            "r_multiple": (lambda x: float(x.group(1)) if x else None)(RE_R.search(txt)),
            "quote": m.get("content", ""),
            "image_urls": imgs,
            "confidence": conf,
            # --- channel-specific extras (the actual join keys for an OCR pass)
            "session_date": sess.isoformat(),
            "header_date": hdr.isoformat() if hdr else None,
            "header_date_matches_post": (hdr == sess) if hdr else None,
            "header_month_spelled_correctly": hdr_exact,
            "is_update": bool(re.search(r"\bupdated?\b", txt, re.I)),
            "n_images": len(imgs),
            "levels_in_text": False,
            "payload": "chart_images",
        })

    with open(OUT, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    sk = os.path.join(os.path.dirname(OUT), "premarket_charts_skipped.jsonl")
    with open(sk, "w", encoding="utf-8") as fh:
        for r in skipped:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"messages={len(msgs)} extracted={len(rows)} skipped={len(skipped)}")
    print(f"images={sum(r['n_images'] for r in rows)}")
    print("session_date resolved=", sum(1 for r in rows if r["session_date"]))
    print("header_date parsed=", sum(1 for r in rows if r["header_date"]))
    print("header disagrees with post day=",
          sum(1 for r in rows if r["header_date_matches_post"] is False))
    print("header month misspelled=",
          sum(1 for r in rows if r["header_month_spelled_correctly"] is False))
    print("distinct session_date=", len({r["session_date"] for r in rows}))
    print("with_symbol=", sum(1 for r in rows if r["symbol"]))
    print("with_level_name=", sum(1 for r in rows if r["level_name"]))
    print("with_direction=", sum(1 for r in rows if r["direction"]))
    print("with_outcome=", sum(1 for r in rows if r["outcome"]))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
