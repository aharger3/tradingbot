#!/usr/bin/env python3
"""Deterministic parser for discord_data/options-trade-reviews.json.

This channel is a post-hoc trade-review INDEX: nearly every message is a link to a
Zoom/YouTube recording plus a one-line title. The structured signal therefore lives in
the title lines ("Trade Review | Profit: $2.8k on NVDA (06/25/25) 5 Mins ORB (BNR)")
and in the occasional prose sentence saying why a trade worked or failed.

No message in this file states an entry, stop, target or R-multiple, so those fields
are null by construction. We never invent them.

Output: research/corpus_sf/reviews_options.jsonl  (one object per extracted trade)

NOTE: these are mentor judgements (Neto / Hayden / Lauren). They are NOT Austin's marks
and must never be written into any Austin mark corpus.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "discord_data", "options-trade-reviews.json")
OUT = os.path.join(HERE, "reviews_options.jsonl")
SRC_NAME = "discord_data/options-trade-reviews.json"

# ---------------------------------------------------------------- time
# Discord exports are UTC. Cross-check: Lauren's "May 2nd ... Review" is stamped
# 2025-05-03T00:41:48 -> 20:41 ET on May 2. Titles line up with ET, so UTC it is.
def et_offset(dt_utc: datetime) -> timedelta:
    """US Eastern: DST 2nd Sun Mar 02:00 -> 1st Sun Nov 02:00 (local). Good enough
    at UTC granularity; only messages inside the 1h switch window could be off."""
    y = dt_utc.year

    def nth_sunday(month, n):
        d = datetime(y, month, 1)
        d += timedelta(days=(6 - d.weekday()) % 7)  # first Sunday
        return d + timedelta(weeks=n - 1)

    start = nth_sunday(3, 2) + timedelta(hours=7)   # 02:00 EST = 07:00 UTC
    end = nth_sunday(11, 1) + timedelta(hours=6)    # 02:00 EDT = 06:00 UTC
    naive = dt_utc.replace(tzinfo=None)
    return timedelta(hours=-4) if start <= naive < end else timedelta(hours=-5)


def to_et_iso(ts: str) -> str:
    dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    off = et_offset(dt)
    return (dt + off).replace(tzinfo=timezone(off)).isoformat()


# ---------------------------------------------------------------- symbols
# Whitelist only. Built from a census of every uppercase token in the file, minus
# jargon (BNR, ORB, PDH, PM, EST, VWAP, HTF, CHOCH, PNL, ASL, ...) and passcode noise.
TICKERS = {
    "QQQ", "SPY", "NVDA", "AMD", "TSLA", "PLTR", "GOOG", "GOOGL", "AAPL",
    "MSFT", "AMZN", "META", "NFLX", "COIN", "MSTR", "IWM", "SPX", "AVGO",
    "MU", "SMCI", "CRM", "BABA", "UBER", "HOOD", "SOFI", "DIA",
}
NAME_TO_TICKER = {
    "tesla": "TSLA", "nvidia": "NVDA", "apple": "AAPL", "google": "GOOG",
    "microsoft": "MSFT", "amazon": "AMZN", "palantir": "PLTR", "meta": "META",
    "netflix": "NFLX",
}
URL_RE = re.compile(r"https?://\S+")
PASSCODE_RE = re.compile(r"^\s*Passcode:.*$", re.M)
MENTION_RE = re.compile(r"<@!?\d+>")


def strip_noise(text: str) -> str:
    t = URL_RE.sub(" ", text)
    t = PASSCODE_RE.sub(" ", t)
    t = MENTION_RE.sub(" ", t)
    t = t.replace("@everyone", " ").replace("@here", " ")
    return t


def find_symbols(clean: str):
    """Ordered, de-duped [(symbol, char_index)] found in URL-stripped text."""
    hits = []
    for m in re.finditer(r"\$?\b([A-Z]{2,5})\b", clean):
        if m.group(1) in TICKERS:
            hits.append((m.group(1), m.start()))
    for m in re.finditer(r"\b([A-Za-z]+)\b", clean):
        t = NAME_TO_TICKER.get(m.group(1).lower())
        if t:
            hits.append((t, m.start()))
    hits.sort(key=lambda x: x[1])
    out, seen = [], set()
    for sym, idx in hits:
        if sym not in seen:
            seen.add(sym)
            out.append((sym, idx))
    return out


# ---------------------------------------------------------------- setup
BR_RE = re.compile(
    r"\bBNR\b|\bB\s*&\s*R\b|break\s*(?:and|&|n)\s*retest|break\s*/\s*retest|"
    r"\bBreak\s*and\s*Retest\b",
    re.I,
)
# one-candle-rule: an N-minute candle used as the trigger, or the opening candle.
OCR_RE = re.compile(
    r"\bOCR\b|one[\s-]*candle|\b\d+\s*-?\s*min(?:s|ute)?s?\s+candle\b|"
    r"\b(?:1st|first)\s+candle\b|candle\s+(?:high|low)\b",
    re.I,
)


def find_setup(clean: str):
    br = bool(BR_RE.search(clean))
    ocr = bool(OCR_RE.search(clean))
    if br and ocr:
        return "br_ocr"
    if br:
        return "break_retest"
    if ocr:
        return "one_candle"
    return None


# ---------------------------------------------------------------- level
# Order matters: most specific first.
LEVEL_PATTERNS = [
    ("pmh", r"(?:pre[\s-]*market|premarket|\bPM\b|\bPMH\b)[\s-]*high"),
    ("pml", r"(?:pre[\s-]*market|premarket|\bPM\b|\bPML\b)[\s-]*low"),
    ("pdh", r"\bPDH\b|previous\s+day(?:'s)?\s+high|prev(?:ious)?\s+day\s+high"),
    ("pdl", r"\bPDL\b|previous\s+day(?:'s)?\s+low|prev(?:ious)?\s+day\s+low"),
    ("hod", r"\bHOD\b|high\s+of\s+(?:the\s+)?day"),
    ("lod", r"\bLOD\b|low\s+of\s+(?:the\s+)?day"),
    ("or_high", r"\bORB?\s*high\b|\bhigh\s+ORB\b|\b(?:1st|first)\s+candle\s+high\b|"
                r"\b\d+\s*-?\s*min(?:s|ute)?s?\s+high\s+ORB\b|"
                r"\breversed?\s+\d+\s*-?\s*min(?:s|ute)?s?\s+high\b|"
                r"\b\d+\s*-?\s*min(?:s|ute)?s?\s+(?:candle\s+)?high\b|"
                r"\bORB\b"),
    # PWH = previous WEEK high; the schema has no slot for it, so it is "other".
    ("other", r"\bPWH\b|previous\s+week(?:'s)?\s+high|"
              r"\bORB?\s*low\b|\blow\s+ORB\b|\b(?:1st|first)\s+candle\s+low\b|"
              r"\b\d+\s*-?\s*min(?:s|ute)?s?\s+(?:candle\s+)?low\b|\bVWAP\b|"
              r"\border\s+block\b|\b(?:monday|tuesday|wednesday|thursday|friday)\s+high\b"),
]
# The "other" bucket is scanned before the generic bare-ORB fallback so an ORB LOW
# is not mislabelled or_high (the schema has no or_low slot).
LEVEL_ORDER = ["pmh", "pml", "pdh", "pdl", "hod", "lod"]


def find_level(clean: str):
    for name in LEVEL_ORDER:
        pat = dict((k, v) for k, v in LEVEL_PATTERNS)[name]
        if re.search(pat, clean, re.I):
            return name
    other_pat = [v for k, v in LEVEL_PATTERNS if k == "other"][0]
    or_pat = [v for k, v in LEVEL_PATTERNS if k == "or_high"][0]
    m_other = re.search(other_pat, clean, re.I)
    m_or = re.search(or_pat, clean, re.I)
    if m_other and (not m_or or m_other.start() <= m_or.start()):
        return "other"
    if m_or:
        return "or_high"
    return None


# ---------------------------------------------------------------- direction
# Bare "long"/"short" are ordinary English in this channel ("short but sweet trade
# review", "long minutes", "long weekend") and produced three false directions on the
# first pass. Only unambiguous trade verbs/nouns count.
CALL_RE = re.compile(r"\bcalls?\b|\blonged\b|\bwent\s+long\b|\bbought\b", re.I)
PUT_RE = re.compile(r"\bputs?\b|\bshorted\b|\bshorting\b|\bwent\s+short\b", re.I)
REJECT_RE = re.compile(r"revers(?:al|ed|e)|reject(?:ion|ed)|fade[d]?", re.I)


def find_direction(clean: str, level_name):
    """Explicit call/put wins. Otherwise a rejection/reversal AT a high is a short,
    AT a low is a long. Anything else stays null."""
    call, put = CALL_RE.search(clean), PUT_RE.search(clean)
    if call and not put:
        return "long", True
    if put and not call:
        return "short", True
    if call and put:
        return None, False  # both named: a two-legged post, resolved per-symbol
    if REJECT_RE.search(clean):
        if re.search(r"\bhigh\b|\bPDH\b|\bPMH\b|\bPWH\b|\bHOD\b", clean, re.I):
            return "short", False
        if re.search(r"\blow\b|\bPDL\b|\bPML\b|\bLOD\b", clean, re.I):
            return "long", False
    return None, False


# ---------------------------------------------------------------- outcome
WIN_RE = re.compile(
    r"\bprofit\b|\(winner\)|\bwinner\b|\bwin(?:s|ner)?\b|\bsmall\s+W\b|"
    r"\bdecent\s+W\b|\bbig\s+W\b|\bsolid\s+W\b|\b\d+\s*W\b|\bgreen\b|"
    r"\bPNL\s+ever\b|\bbanger\b",
    re.I,
)
LOSS_RE = re.compile(
    r"\(loser\)|\blosers?\b|(?<!stop )(?<!stop-)\bloss(?:es)?\b|\bsmall\s+L\b|\bbig\s+L\b|"
    r"\b\d+\s*L\b|\bstopped\s+out\b|\bgot\s+wrecked\b|\bred\b|"
    r"\bdidn'?t\s+play(?:ed)?\s*out\b",
    re.I,
)
BE_RE = re.compile(r"\bbreak[\s-]*even\b|\bbreakeven\b|\bB\.?E\.?\b(?!\w)", re.I)
PROFIT_RE = re.compile(r"profit[:\s]*\$\s*([\d,]+(?:\.\d+)?)\s*(k?)", re.I)
PROFIT_RE2 = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)\s*(k?)\s*profit", re.I)


def find_outcome(clean: str):
    w, l = bool(WIN_RE.search(clean)), bool(LOSS_RE.search(clean))
    if BE_RE.search(clean) and not (w or l):
        return "be"
    if w and l:
        return None  # a mixed post ("1L 1W"); message level cannot resolve it
    if w:
        return "win"
    if l:
        return "loss"
    return None


def find_pnl(clean: str):
    m = PROFIT_RE.search(clean) or PROFIT_RE2.search(clean)
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    if m.group(2).lower() == "k":
        v *= 1000
    return v


# ---------------------------------------------------------------- reason prose
# Sentences that state WHY it worked / failed. This is the highest-value field in
# this channel: the entry itself is behind a video link, the reasoning is in text.
# Narrow, causal, first-person cues only. The first pass also matched curriculum
# bullets ("- Market structure + trendlines", "- Risk and Stop Loss") and labelled a
# session agenda as a trade reason; those topical cues are deliberately gone.
REASON_CUES = re.compile(
    r"stuck to my plan|executed properly|managed risk perfectly|didn'?t play|"
    r"didn'?t work out|execution error|got wrecked|got a little lazy|hurt me|"
    r"happened too fast|low size|the reason (?:was|i)|my mistake|solid setup|"
    r"bottom ticked|thought process|didn'?t get the execution",
    re.I,
)
TITLE_ONLY = re.compile(
    r"^\s*(?:[\w'’\.\s]*?(?:coaching|trade\s+review|trades\s+review|trade\s+recap|"
    r"live trading|weekly recap)[\w'’\.\s\d\|\(\)\-–—:,/\+&$%\.]*)\s*$",
    re.I,
)


def find_reason(clean: str):
    parts = []
    for raw in re.split(r"[\n\r]+", clean):
        s = raw.strip()
        if len(s) < 12:
            continue
        for sent in re.split(r"(?<=[.!?])\s+", s):
            sent = sent.strip(" -–—•\t")
            if len(sent) < 12:
                continue
            if REASON_CUES.search(sent):
                parts.append(re.sub(r"\s+", " ", sent))
    if not parts:
        return None
    seen, uniq = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return " ".join(uniq)[:600]


# ---------------------------------------------------------------- gate
COACHING_ONLY = re.compile(
    r"coaching\s+session|coaching\s*\+\s*trade\s+feedback|weekly\s+recap", re.I
)
# "went over names like AMZN, GOOG, AAPL etc." is a session watchlist, not trades.
WATCHLIST_RE = re.compile(r"\bnames?\s+like\b|\bwent\s+over\s+names\b", re.I)
# A ticker written as a slash pair ("SPY/QQQ correlation", "looking at SPY/QQQ") is a
# topic in a session agenda, not a trade. Pass 2 emitted four such rows.
SLASH_PAIR_RE = re.compile(r"\b[A-Z]{2,5}\s*/\s*[A-Z]{2,5}\b")


def is_extractable(clean: str, syms, setup, level, outcome, reason, pnl):
    """Emit only when the message actually carries trade content. A bare
    'Wednesday coaching + trade feedback 6.3.2026 <zoom link>' carries none, and
    neither does a coaching post that merely lists the tickers discussed."""
    if not clean.strip():
        return False
    if not syms:
        # First pass emitted symbol-less rows off a stray "long weekend" / "BnR"
        # mention and every one of them was a non-trade. A ticker is now required.
        return False
    hard = setup or level or outcome or pnl
    if (COACHING_ONLY.search(clean) or WATCHLIST_RE.search(clean)) and not hard:
        return False
    if SLASH_PAIR_RE.search(clean) and not hard:
        return False
    return True


# ---------------------------------------------------------------- confidence
def score_confidence(sym, setup, level, direction, dir_explicit, outcome, reason):
    facts = sum(x is not None for x in (setup, level, outcome))
    if sym and facts >= 2 and (dir_explicit or outcome):
        return "high"
    if sym and (facts >= 1 or reason):
        return "medium"
    return "low"


# ---------------------------------------------------------------- main
def leg_windows(clean: str, syms, i):
    """Forward and backward text belonging to symbol i, each bounded by its
    neighbouring symbol mentions so one leg's words never bleed into the next."""
    start = syms[i][1]
    nxt = syms[i + 1][1] if i + 1 < len(syms) else len(clean)
    prev_end = syms[i - 1][1] + len(syms[i - 1][0]) if i > 0 else 0
    fwd = clean[start: min(nxt, start + 90)]
    bwd = clean[max(prev_end, start - 25): start]
    return fwd, bwd


def resolve_leg(clean, syms, i, fn):
    """Forward window first, backward window only as a fallback. Chosen over a
    nearest-marker rule because 'TSLA Call + NVDA Put' and 'Small L ... Decent W on
    GOOG' both bind wrong under nearest-distance."""
    fwd, bwd = leg_windows(clean, syms, i)
    v = fn(fwd)
    if v is not None:
        return v
    return fn(bwd)


def parse(messages):
    rows = []
    for m in messages:
        content = m.get("content") or ""
        clean = strip_noise(content)
        syms = find_symbols(clean)
        setup = find_setup(clean)
        level = find_level(clean)
        outcome = find_outcome(clean)
        reason = find_reason(clean)
        pnl = find_pnl(clean)
        if not is_extractable(clean, syms, setup, level, outcome, reason, pnl):
            continue
        direction, dir_explicit = find_direction(clean, level)
        images = [u for u in m.get("attachments", []) if isinstance(u, str)]
        ts = to_et_iso(m["ts"])

        for i, (sym, idx) in enumerate(syms):
            d, de = direction, dir_explicit
            o = outcome
            rsn = reason
            if len(syms) > 1:
                # Multi-leg post: resolve each ticker from its own text window.
                wd = resolve_leg(clean, syms, i, lambda t: find_direction(t, level)[0])
                if wd:
                    d, de = wd, True
                wo = resolve_leg(clean, syms, i, find_outcome)
                if wo:
                    o = wo
                # A stated reason belongs to the leg it was written about, not to
                # every ticker in the post ("execution error" was PLTR's, not GOOG's).
                fwd, _ = leg_windows(clean, syms, i)
                rsn = reason if (reason and REASON_CUES.search(fwd)) else None
            rows.append({
                "src": SRC_NAME,
                "msg_id": m["id"],
                "ts": ts,
                "author": m["author"],
                "symbol": sym,
                "direction": d,
                "setup": setup,
                "level_price": None,   # never stated in this channel
                "level_name": level,
                "entry": None,         # never stated in this channel
                "stop": None,          # never stated in this channel
                "target": None,        # never stated in this channel
                "outcome": o,
                "r_multiple": None,    # never stated in this channel
                "pnl_usd": pnl,
                "reason": rsn,
                "quote": content,
                "image_urls": images,
                "confidence": score_confidence(sym, setup, level, d, de, o, reason),
            })
    return rows


def main():
    with open(SRC, encoding="utf-8") as fh:
        messages = json.load(fh)
    rows = parse(messages)
    with open(OUT, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    kept = {r["msg_id"] for r in rows}
    print(f"messages={len(messages)} extracted_rows={len(rows)} "
          f"messages_hit={len(kept)} skipped={len(messages) - len(kept)}")
    for f in ("symbol", "direction", "setup", "level_name", "outcome", "reason"):
        print(f"  with_{f}={sum(1 for r in rows if r[f] is not None)}")
    print(f"  with_image={sum(1 for r in rows if r['image_urls'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
