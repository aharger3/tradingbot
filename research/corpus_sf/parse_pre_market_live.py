#!/usr/bin/env python3
"""Deterministic parser for discord_data/pre-market-live.json.

Channel shape (measured, 535 messages, 2024-05-14 .. 2026-08-21, author Jdub x532
/ Hayden x3): the channel is overwhelmingly a broadcast stub. 295 messages carry
no text at all (bare YouTube embed), 224 are the fixed announcement strings
("Pre Market Live" / "Pre Market Prep" / "Pre Market Charts ..."), and only FOUR
messages carry a written gameplan. Those four are the entire extractable payload
of this file. Everything else is skipped on purpose.

The parser therefore does one job well: turn a gameplan paragraph into one row
per (symbol, clause) call. No LLM. Regex + clause segmentation + a ticker
whitelist that comes from universe.py so no private list is kept here.

Field policy: never invent. A field is null unless a token in the clause (or,
for direction/level_name only, in the enclosing sentence/paragraph) says it.

Confidence:
  high   -- symbol AND (price or level_name) AND direction all read off the
            same clause.
  medium -- direction or level_name inherited from the enclosing sentence, or a
            symbol+price call with no direction stated.
  low    -- symbol carried from the enclosing paragraph (pronoun reference such
            as "on this one"), or nothing but a bare symbol mention.

Usage:  python research/corpus_sf/parse_pre_market_live.py
Writes: research/corpus_sf/pre_market_live.jsonl
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

from universe import ALL_SYMS  # noqa: E402
from chat_vocab import (  # noqa: E402
    PRE_MARKET_LIVE_EXTRA_SYMS as EXTRA_SYMS,
    PRE_MARKET_LIVE_NOT_TICKERS as NOT_TICKERS,
)

SRC = os.path.join(REPO, "discord_data", "pre-market-live.json")
OUT = os.path.join(HERE, "pre_market_live.jsonl")
SRC_NAME = "discord_data/pre-market-live.json"

# Whitelist = universe.py + index/futures tickers Jdub names in premarket that
# the engine does not trade but does reference for bias.
SYMBOLS = sorted(set(ALL_SYMS) | set(EXTRA_SYMS))

# ---------------------------------------------------------------------------
# lexicons
# ---------------------------------------------------------------------------

# Bear phrases are stripped BEFORE the bull scan so "pop and fade" does not
# score as a bull hit on "pop".
BEAR_PHRASES = [
    r"pop and fade[sd]?", r"pop & fade[sd]?", r"fade[sd]? the pop",
    r"short(?:s|ing|ed)?\b", r"\bputs?\b", r"downside", r"break(?:ing)?\s+down",
    r"breakdown", r"lose[s]?\s+the", r"reject(?:ion|s|ed)?", r"heavy\b",
    r"weak(?:er|ness)?\b", r"lagging", r"roll(?:ing)?\s+over", r"push lower",
    r"below the", r"drop toward", r"toward[s]? the low", r"lower low",
]
BULL_PHRASES = [
    r"reclaim(?:s|ing)?\b", r"long[s]?\b", r"\bcalls?\b", r"upside",
    r"push(?:ing)?\s+higher", r"continuation", r"strength", r"bounce off",
    r"bounce\b", r"gets? bought", r"break(?:ing)?\s+(?:out|above)",
    r"above the", r"back above", r"higher high", r"push toward[s]? the upside",
    r"\bstrong(?:er)?\b",
]
# Kills a direction read even when a directional word is present.
HEDGE = re.compile(r"\b(cautious|not looking|no longer|avoid|careful|unsure|"
                   r"wait(?:ing)? for a clear direction)\b", re.I)

LEVEL_PATTERNS = [
    ("pdh", r"\bPDH\b|previous day(?:'s)? high|prior day high"),
    ("pdl", r"\bPDL\b|previous day(?:'s)? low|prior day low"),
    ("pmh", r"\bPMH\b|pre.?market high"),
    ("pml", r"\bPML\b|pre.?market low"),
    ("hod", r"\bHOD\b|high of (?:the )?day"),
    ("lod", r"\bLOD\b|low of (?:the )?day"),
    ("or_high", r"\bOR ?high\b|opening range high|\bORH\b"),
    ("other", r"\bath[s]?\b|all.time high|key level[s]?|vwap|"
              r"\b(?:50|100|200)\s?(?:day|d)?\s?(?:ema|sma|ma)\b"),
]

SETUP_PATTERNS = [
    ("break_retest", r"break and retest|break.?&.?retest|\bB&R\b|retest"),
    ("one_candle", r"one candle rule|\bOCR\b|one.candle"),
]

GAMEPLAN = re.compile(r"\bgame\s?plan\b", re.I)

# Announcement-only messages: the whole channel except the four gameplans.
ANNOUNCE = re.compile(
    r"^(good morning[!\s]*)?(pre ?market)?\s*"
    r"(live[s]?|prep|charts?( indices| tech)?)?\s*$", re.I)

# Trailing "." must not eat the number: "TSLA key levels are going to be 242."
PRICE = re.compile(r"(?<![\w.])(\d{1,5}(?:\.\d{1,2})?)(?![\w%])(?!\.\d)")


def clean(text):
    """Strip URLs and Discord mention tokens; keep everything else verbatim."""
    t = re.sub(r"https?://\S+", " ", text or "")
    t = re.sub(r"<@[!&]?\d+>", " ", t)
    t = t.replace("@everyone", " ").replace("@here", " ")
    return re.sub(r"[ \t]+", " ", t).strip()


def to_et(ts):
    """Export stamps are naive UTC (11:57Z announcements == 07:57 ET). Convert."""
    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    # US DST: second Sunday March .. first Sunday November.
    y = dt.year
    mar = datetime(y, 3, 8, tzinfo=timezone.utc)
    dst_start = mar + timedelta(days=(6 - mar.weekday()) % 7)
    nov = datetime(y, 11, 1, tzinfo=timezone.utc)
    dst_end = nov + timedelta(days=(6 - nov.weekday()) % 7)
    off = -4 if dst_start <= dt < dst_end else -5
    return (dt + timedelta(hours=off)).strftime("%Y-%m-%dT%H:%M:%S") + \
        ("-04:00" if off == -4 else "-05:00")


def find_symbols(frag):
    """Whitelist ticker hits. Require >=2 uppercase letters so prose mentions
    ('the spy and qqq are gapping') do not become calls -- only the deliberate
    ticker form ('SPY', 'AAPl') counts."""
    out = []
    for m in re.finditer(r"\b([A-Za-z]{2,5})\b", frag):
        tok = m.group(1)
        up = tok.upper()
        if up in NOT_TICKERS or up not in SYMBOLS:
            continue
        if sum(1 for c in tok if c.isupper()) < 2:
            continue
        if up not in out:
            out.append(up)
    return out


def direction_of(text):
    stripped = text
    bear = 0
    for pat in BEAR_PHRASES:
        n = len(re.findall(pat, stripped, re.I))
        if n:
            bear += n
            stripped = re.sub(pat, " ", stripped, flags=re.I)
    bull = sum(len(re.findall(p, stripped, re.I)) for p in BULL_PHRASES)
    if HEDGE.search(text):
        return None
    if bull and not bear:
        return "long"
    if bear and not bull:
        return "short"
    return None


def level_of(text):
    for name, pat in LEVEL_PATTERNS:
        if re.search(pat, text, re.I):
            return name
    return None


def setup_of(text):
    hits = [n for n, p in SETUP_PATTERNS if re.search(p, text, re.I)]
    if len(hits) == 2:
        return "br_ocr"
    return hits[0] if hits else None


def price_near(frag, symbol):
    """A price belongs to a symbol only if it sits in the same clause. Reject
    numbers that are times (10:00AM), dates (March 14th) or percents."""
    f = re.sub(r"\b\d{1,2}:\d{2}\s?(?:AM|PM)?\b", " ", frag, flags=re.I)
    f = re.sub(r"\b\d{1,2}(?:st|nd|rd|th)\b", " ", f, flags=re.I)
    f = re.sub(r"\b(?:first|last)\s+\d+\s+minutes?\b", " ", f, flags=re.I)
    f = re.sub(r"\b\d+\s*(?:minute|min|hour|day)s?\b", " ", f, flags=re.I)
    vals = [float(v) for v in PRICE.findall(f)]
    vals = [v for v in vals if 1.0 <= v <= 100000.0]
    return vals[0] if len(vals) == 1 else None


def split_clauses(sentence):
    """Split on commas and on 'and' when BOTH sides name a ticker, so
    'AMD bounce off PDL, TSLA bounce off PDL' and '476 on the QQQ and 558 on
    SPY' each fall apart into one call per clause."""
    parts = [p for p in re.split(r"\s*,\s*", sentence) if p.strip()]
    out = []
    for p in parts:
        pieces = re.split(r"\s+and\s+", p)
        merged, buf = [], ""
        for piece in pieces:
            cand = (buf + " and " + piece).strip() if buf else piece
            if buf and find_symbols(buf) and find_symbols(piece):
                merged.append(buf)
                buf = piece
            else:
                buf = cand
        if buf:
            merged.append(buf)
        out.extend(merged)
    return [c.strip() for c in out if c.strip()]


def parse_message(msg):
    """Return (rows, skip_reason). skip_reason is None when rows were produced."""
    text = clean(msg.get("content") or "")
    images = [a for a in (msg.get("attachments") or []) if isinstance(a, str)]
    if not text and not images:
        return [], "no_text_link_only"
    if ANNOUNCE.match(text) and not images:
        return [], "announcement_only"
    if ANNOUNCE.match(text) and images:
        # "Pre Market Charts Indices/Tech" -- the day's level charts. No symbol
        # is written, but the artefact is the payload; keep it.
        return [mk(msg, None, None, None, None, None, text, images, "low")], None

    rows = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        para_syms = find_symbols(para)
        para_sym = para_syms[0] if len(para_syms) == 1 else None
        for sentence in re.split(r"(?<=[.!?])\s+|\n", para):
            sentence = sentence.strip()
            if not sentence or GAMEPLAN.search(sentence):
                continue
            s_dir, s_lvl, s_setup = (direction_of(sentence), level_of(sentence),
                                     setup_of(sentence))
            clauses = split_clauses(sentence)
            prev_lvl = None
            for clause in clauses:
                syms = find_symbols(clause)
                c_dir, c_lvl = direction_of(clause), level_of(clause)
                c_setup = setup_of(clause)
                if not syms:
                    # Pronoun carry: a level/direction statement with no ticker,
                    # inside a paragraph that names exactly one ticker.
                    if para_sym and (c_lvl or c_dir) and \
                            re.search(r"\bthis (one|name)\b|\bit\b", clause, re.I):
                        rows.append(mk(msg, para_sym, c_dir or s_dir,
                                       c_setup or s_setup, None,
                                       c_lvl or prev_lvl, clause, images, "low"))
                    continue
                for sym in syms:
                    price = price_near(clause, sym)

                    # A clause that names its own price states its own level;
                    # inheriting the sentence's level_name there is an
                    # invention ("the PDL on the QQQ and the 751 on the SPY"
                    # -- 751 is NOT the SPY's PDL).
                    lvl = c_lvl if (c_lvl or price is not None)                         else (prev_lvl or s_lvl)
                    dirn = c_dir or s_dir
                    inherited = (lvl is not None and c_lvl is None) or \
                                (dirn is not None and c_dir is None)
                    if price is None and lvl is None and dirn is None:
                        conf = "low"
                    elif inherited:
                        conf = "medium"
                    elif dirn and (price is not None or lvl):
                        conf = "high"
                    else:
                        conf = "medium"
                    rows.append(mk(msg, sym, dirn, c_setup or s_setup, price,
                                   lvl, clause, images, conf))
                if c_lvl:
                    prev_lvl = c_lvl
    if not rows:
        # No symbol call, but the post carries premarket chart images or the
        # gameplan video. Keep the artefact (symbol null) rather than drop it.
        if images:
            return [mk(msg, None, None, None, None, None, text, images,
                       "low")], None
        return [], "prose_no_symbol_call" if not ANNOUNCE.match(text)             else "announcement_only"
    return rows, None


def mk(msg, symbol, direction, setup, price, level_name, quote, images, conf):
    return {
        "src": SRC_NAME,
        "msg_id": msg["id"],
        "ts": to_et(msg["ts"]),
        "author": msg["author"],
        "symbol": symbol,
        "direction": direction,
        "setup": setup,
        "level_price": price,
        "level_name": level_name,
        "entry": None,       # premarket gameplans never state an entry price
        "stop": None,        # ... nor a stop
        "target": None,      # ... nor a target
        "outcome": None,     # ... and never a result: this channel is pre-open
        "r_multiple": None,
        "quote": quote,
        "image_urls": images,
        "confidence": conf,
    }


def main():
    msgs = json.load(open(SRC, encoding="utf-8"))
    rows, skips = [], {}
    skipped_ids = []
    for m in msgs:
        r, why = parse_message(m)
        if r:
            rows.extend(r)
        else:
            skips[why] = skips.get(why, 0) + 1
            skipped_ids.append((m["id"], why))
    with open(OUT, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"messages={len(msgs)} rows={len(rows)} "
          f"msgs_with_rows={len({r['msg_id'] for r in rows})}")
    print("skips:", json.dumps(skips))
    for k in ("direction", "symbol", "level_name", "level_price", "setup",
              "outcome"):
        print(f"  with_{k}={sum(1 for r in rows if r[k] is not None)}")
    print("  with_image=%d" % sum(1 for r in rows if r["image_urls"]))
    print("  conf:", json.dumps({c: sum(1 for r in rows if r["confidence"] == c)
                                 for c in ("high", "medium", "low")}))
    return skipped_ids


if __name__ == "__main__":
    main()
