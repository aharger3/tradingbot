#!/usr/bin/env python3
"""Deterministic parser for the 'misc' Discord channels.

Sources: discord_data/{trade-feedback,swing-ideas,trading-floor,youtube,
a-plus-setups,module-*}.json  (introduce-yourself is skipped: pure social).

These are SCARFACE / mentor / member judgements. They are NOT Austin's marks.
Output goes to research/corpus_sf/misc.jsonl ONLY. Nothing here ever writes
into an Austin mark corpus.

No LLM. Regex + heuristics only.

Timestamps in the export are naive UTC (verified: the trading-floor hour
histogram peaks at 13-16h raw, i.e. 09-12 ET). They are converted to
America/New_York and emitted with an offset.

Enum note: the schema's level_name has no "or_low"; opening-range LOW and
VWAP/other named levels are emitted as "other".
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(REPO, "discord_data")
OUT = os.path.join(HERE, "misc.jsonl")

SRC_FILES = [
    "a-plus-setups.json",
    "trade-feedback.json",
    "swing-ideas.json",
    "trading-floor.json",
    "youtube.json",
] + ["module-%d.json" % i for i in range(1, 11)]

UTC = ZoneInfo("UTC")
ET = ZoneInfo("America/New_York")

# --------------------------------------------------------------------------
# symbols
# --------------------------------------------------------------------------
# case-insensitive: unambiguous tickers that are also written lowercase a lot
SYMS_CI = [
    "NVDA", "TSLA", "AAPL", "APPL", "SPY", "QQQ", "IWM", "AMD", "AMZN", "META",
    "MSFT", "GOOGL", "GOOG", "PLTR", "INTC", "AVGO", "SOFI", "IREN", "UBER",
    "BABA", "TSM", "MARA", "NFLX", "ORCL", "ACHR", "SPCX", "SMCI", "MSTR",
    "HIMS", "SNDK", "TSLL", "SPX", "HOOD", "CRM", "UNH", "SOUN", "RIVN",
    "LCID", "COST", "LULU", "DELL", "CRWD", "SNOW", "ABNB", "SHOP", "PYPL",
    "DKNG", "CVNA", "AFRM", "RBLX", "MRVL", "QCOM", "TXN", "BAC", "JPM",
    "GME", "AMC", "BYND", "NIO", "XPEV", "LI", "F", "GS", "WMT", "DIS",
    "BA", "NKE", "SBUX", "CMG", "TGT", "ROKU", "ZM", "DOCU", "TTD", "NET",
    "DDOG", "PANW", "ANET", "VRT", "APP", "OKLO", "RKLB", "ASTS", "JOBY",
    "LUNR", "QBTS", "IONQ", "RGTI", "BBAI", "CRCL", "CRWV",
]
# uppercase-only: real tickers whose lowercase form is a common English word
SYMS_CS = ["MU", "COIN", "ARM", "ES", "NQ", "MES", "MNQ", "RTY", "GM", "KO",
           "CAT", "PM", "ON", "IT", "ALL", "SO", "DE", "MA", "V", "T"]
# ...but these uppercase-only ones are still too noisy in chat prose. Drop.
SYMS_CS = ["MU", "COIN", "ARM", "NQ", "MNQ", "MES", "RTY", "CAT", "KO"]

SYM_ALIAS = {"APPL": "AAPL", "GOG": "GOOGL", "TESLA": "TSLA", "NVIDIA": "NVDA",
             "APPLE": "AAPL", "AMAZON": "AMZN", "GOOGLE": "GOOGL",
             "MICROSOFT": "MSFT", "NETFLIX": "NFLX", "PALANTIR": "PLTR",
             "MICRON": "MU", "INTEL": "INTC", "ROBINHOOD": "HOOD",
             "COINBASE": "COIN", "BROADCOM": "AVGO", "ORACLE": "ORCL"}

# spelled-out company names members actually use
SYMS_NAME = ["TESLA", "NVIDIA", "APPLE", "AMAZON", "GOOGLE", "MICROSOFT",
             "NETFLIX", "PALANTIR", "MICRON", "INTEL", "ROBINHOOD", "COINBASE",
             "BROADCOM", "ORACLE", "GOG"]

# NOTE: the lookahead must allow a trailing sentence period ("... on PLTR.")
# but not a decimal point or a domain ("PLTR.com", "1.5"). Before 2026-08-29
# it was (?![A-Za-z0-9.]) and silently dropped every ticker that ended a
# sentence -- the single biggest recall hole in the first pass.
_TAIL = r"(?![A-Za-z0-9]|\.[A-Za-z0-9])"
RE_SYM_CI = re.compile(r"(?<![A-Za-z0-9$.])(" + "|".join(SYMS_CI + SYMS_NAME)
                       + r")" + _TAIL, re.I)
RE_SYM_CS = re.compile(r"(?<![A-Za-z0-9$.])(" + "|".join(SYMS_CS) + r")" + _TAIL)


def find_symbols(text: str):
    """Ordered, de-duplicated ticker list for a chunk of text."""
    hits = []
    for m in RE_SYM_CI.finditer(text):
        hits.append((m.start(), SYM_ALIAS.get(m.group(1).upper(), m.group(1).upper())))
    for m in RE_SYM_CS.finditer(text):
        hits.append((m.start(), m.group(1)))
    hits.sort()
    out = []
    for _, s in hits:
        if s not in out:
            out.append(s)
    return out


# --------------------------------------------------------------------------
# setup
# --------------------------------------------------------------------------
RE_HR = re.compile(r"\b(?:pdh|pdl|pmh|pml)r\b|\b\d?\s?m[hl]r\b", re.I)
RE_BR = re.compile(
    r"break(?:s|ing|out)?\s*(?:and|&|\+|/)\s*re[- ]?test"
    r"|b\s*(?:&|and|n)\s*rs?(?![a-z])"
    r"|\bbnrs?\b"
    r"|\b(?:pdh|pdl|pmh|pml)r\b|\b\d\s?m[hl]r\b"
    r"|b\s*&\s*re-?test"
    r"|break\s*(?:and|&)\s*retested",
    re.I)
RE_OCR = re.compile(r"one[- ]candle(?:\s+rule)?|1[- ]candle\s+rule|\bocr\b", re.I)
RE_RETEST = re.compile(r"re[- ]?test(?:s|ed|ing)?\b|reclaim(?:s|ed|ing)?\b", re.I)
RE_OTHER_SETUP = re.compile(
    r"\bopening drive\b|\binside bar\b|\bgap (?:fill|up|down|and go)\b"
    r"|\bbreak(?:s|ing)? and hold\b"
    r"|\border ?block\b|\bfvg\b|\bunicorn\b|\bopening range breakout\b", re.I)


def classify_setup(t: str):
    br = bool(RE_BR.search(t))
    ocr = bool(RE_OCR.search(t))
    if br and ocr:
        return "br_ocr", True
    if br:
        return "break_retest", True
    if ocr:
        return "one_candle", True
    if RE_RETEST.search(t):
        return "break_retest", False   # bare "retest"/"reclaim" -> inferred
    if RE_OTHER_SETUP.search(t):
        return "other", True
    return None, False


# --------------------------------------------------------------------------
# levels
# --------------------------------------------------------------------------
LEVEL_RES = [
    ("or_high", re.compile(
        r"\borh\b|\b\d\s?mhr\b"
        r"|\b(?:or|orb|opening range|opening candle|open(?:ing)? \d+ ?min(?:ute)?)"
        r"[\s\-]*(?:5 ?min ?)?highs?\b"
        r"|\bopening \d+ ?min(?:ute)? highs?\b", re.I)),
    ("pdh", re.compile(
        r"\bpdhr?\b|\bnpdh\b|\bprev(?:ious)?[\s\-]*day[\s\-]*highs?\b"
        r"|\bprior[\s\-]*day[\s\-]*highs?\b|\byesterday'?s?[\s\-]*highs?\b", re.I)),
    ("pdl", re.compile(
        r"\bpdlr?\b|\bprev(?:ious)?[\s\-]*day[\s\-]*lows?\b"
        r"|\bprior[\s\-]*day[\s\-]*lows?\b|\byesterday'?s?[\s\-]*lows?\b", re.I)),
    ("pmh", re.compile(
        r"\bpmhr?\b|\bpre[\s\-]?market[\s\-]*highs?\b|\bpm[\s\-]*highs?\b", re.I)),
    ("pml", re.compile(
        r"\bpmlr?\b|\bpre[\s\-]?market[\s\-]*lows?\b|\bpm[\s\-]*lows?\b", re.I)),
    ("hod", re.compile(r"\bn?hod\b|\bhighs? of (?:the )?day\b", re.I)),
    ("lod", re.compile(r"\bn?lod\b|\blows? of (?:the )?day\b", re.I)),
    ("other", re.compile(
        r"\borl\b|\b\d\s?mlr\b|\b(?:or|orb|opening range|opening candle)[\s\-]*lows?\b"
        r"|\bvwap\b|\bopening range\b|\borb\b"
        r"|\bpwh\b|\bpwl\b|\bath\b|\bydh\b|\bydl\b|\bpdc\b|\bpdo\b", re.I)),
]

RE_SETUP_ANCHOR = re.compile(
    r"re[- ]?test|break|reclaim|above|below|hold|reject|bounce|one[- ]candle", re.I)


def classify_level(t: str):
    """Return (level_name, match_span) picking the level nearest a setup anchor."""
    found = []
    for name, rx in LEVEL_RES:
        for m in rx.finditer(t):
            found.append((m.start(), m.end(), name))
    if not found:
        return None, None
    # de-dup overlapping spans, preferring the specific name over "other"
    found.sort(key=lambda x: (x[0], x[2] == "other"))
    kept = []
    for s, e, n in found:
        if any(s < ke and e > ks for ks, ke, _ in kept):
            continue
        kept.append((s, e, n))
    anchors = [m.start() for m in RE_SETUP_ANCHOR.finditer(t)]
    if anchors:
        s, e, n = min(kept, key=lambda x: min(abs(x[0] - a) for a in anchors))
    else:
        s, e, n = kept[0]
    return n, (s, e)


# --------------------------------------------------------------------------
# direction
# --------------------------------------------------------------------------
RE_SHORT_NOISE = re.compile(
    r"short[\s\-]term|shortly|short squeeze|short cover|short interest|shortcoming",
    re.I)
RE_LONG_NOISE = re.compile(r"long[\s\-]term|as long as|long time|long run|how long",
                           re.I)

RE_LONG_STRONG = re.compile(
    r"\blong(?:s|ed|ing)?\b|\bcalls\b|\bcall option|\bbullish\b|\bgo long\b"
    r"|\b(?:a|an|the|my|some|few|more|another)\s+(?:\w+\s+){0,2}calls?\b", re.I)
RE_SHORT_STRONG = re.compile(
    r"\bshort(?:s|ed|ing)?\b|\bputs\b|\bput option|\bbearish\b|\bgo short\b"
    r"|\b(?:a|an|the|my|some|few|more|another)\s+(?:\w+\s+){0,2}puts?\b", re.I)
RE_LONG_WEAK = re.compile(r"\bupside\b|\bbreak(?:s|ing)? above\b|\bto the upside\b", re.I)
RE_SHORT_WEAK = re.compile(r"\bdownside\b|\bbreak(?:s|ing)? below\b|\bto the downside\b",
                           re.I)


RE_NEG = re.compile(
    r"\b(?:don'?t|do not|didn'?t|wouldn'?t|won'?t|not|never|avoid|stay away"
    r"|steer clear|instead of|rather than|missed|skip(?:ped)?)\b", re.I)
RE_EXITV = re.compile(
    r"\bexit(?:ed|ing)?\b|\bclosed out\b|\bsold out\b|\btook off\b", re.I)


RE_CLAUSE = re.compile(r"[.!?;\n]|,\s+(?:but|and|so|then)\b")


def _negated(text, pos):
    """Negation anywhere earlier in the SAME clause suppresses the cue.

    "You dont want to mess with NVDA now with PUTS" -- 'dont' is 40 chars back,
    so a fixed window missed it.
    """
    start = 0
    for m in RE_CLAUSE.finditer(text[:pos]):
        start = m.end()
    return bool(RE_NEG.search(text[start:pos]))


def _polar(rx, text):
    """True if the pattern fires at least once un-negated."""
    return any(not _negated(text, m.start()) for m in rx.finditer(text))


def classify_direction(t: str, level_span):
    s = RE_SHORT_NOISE.sub(" ", t)
    s = RE_LONG_NOISE.sub(" ", s)
    lo = _polar(RE_LONG_STRONG, s)
    sh = _polar(RE_SHORT_STRONG, s)
    if lo and not sh:
        return "long"
    if sh and not lo:
        return "short"
    if lo and sh:
        return None
    if RE_EXITV.search(s):
        return None          # "exited when 185 broke to the downside" is a close
    lo = _polar(RE_LONG_WEAK, s)
    sh = _polar(RE_SHORT_WEAK, s)
    if lo and not sh:
        return "long"
    if sh and not lo:
        return "short"
    # "above/below <level>" as a last resort
    if level_span:
        pre = t[max(0, level_span[0] - 24):level_span[0]].lower()
        if RE_NEG.search(pre):
            return None
        a, b = "above" in pre, "below" in pre
        if a and not b:
            return "long"
        if b and not a:
            return "short"
    return None


# --------------------------------------------------------------------------
# prices
# --------------------------------------------------------------------------
NUM = r"\$?\d{1,6}(?:\.\d{1,2})?"
RE_NUM_ANY = re.compile(NUM)
BAD_AFTER = re.compile(
    r"^\s*(?:%|k\b|m\b|min|mins|minute|sec|am\b|pm\b|est\b|et\b|cst\b|r\b|rr\b"
    r"|cons?\b|contracts?\b|shares?\b|dte\b|c\b|p\b|calls?\b|puts?\b|strike"
    r"|sma\b|ema\b|day|days|bucks?|dollars?)", re.I)


def clean_num(text: str, m):
    """Validate a numeric match as a price. Return float or None."""
    raw = m.group(0)
    s, e = m.span()
    if s > 0 and text[s - 1] in ":/-0123456789":
        return None
    if e < len(text) and text[e] in ":/0123456789":
        return None
    if e < len(text) and text[e].isalpha():
        return None          # "5MH", "210c", "3.39pm" -- glued, not a price
    if BAD_AFTER.match(text[e:e + 12]):
        return None
    v = float(raw.lstrip("$"))
    if "." not in raw and 1900 <= v <= 2100:
        return None          # a year
    if v < 0.5 or v > 100000:
        return None
    if "." not in raw and v < 5:
        return None          # counts, not prices
    return v


def grab_after(text: str, kw_rx, window=26):
    """First plausible price within `window` chars after a keyword hit."""
    for km in kw_rx.finditer(text):
        tail = text[km.end():]
        for nm in RE_NUM_ANY.finditer(tail):
            if nm.start() > window:
                break
            v = clean_num(tail, nm)   # scan the full tail: never split a number
            if v is not None:
                return v
    return None


RE_KW_ENTRY = re.compile(
    r"entry(?:\s*point)?(?:\s*price)?\s*(?:at|@|:|is|was|of|-|=)?"
    r"|enter(?:ed|ing)?\s*(?:at|@|:|around|on)"
    r"|got in (?:at|@|around)|filled (?:at|@)|bought (?:at|@)|entries? at", re.I)
RE_KW_STOP = re.compile(
    r"stop[\s\-]*loss\s*(?:at|@|:|is|was|of|-|=)?|\bsl\s*(?:at|@|:|=|-)?"
    r"|\bstop\s*(?:at|@|:|is|was|of|=|-|under|below|above)", re.I)
RE_KW_TGT = re.compile(
    r"target(?:s)?\s*(?:at|@|:|is|was|of|-|=)?|price target\s*(?:at|@|:|of)?"
    r"|\bpt\d?\s*(?:at|@|:|is|of|-|=)?|\btp\d?\s*(?:at|@|:|is|of|-|=)?"
    r"|take profit\s*(?:at|@|:)?", re.I)
RE_KW_LEVEL = re.compile(
    r"re[- ]?test(?:s|ed|ing)?\s*(?:of|at|@|the)?|reclaim(?:s|ed|ing)?\s*(?:of|the)?"
    r"|b\s*(?:&|and|n)\s*r\s*(?:of|at|@)?|\bbnr\s*(?:of|at|@)?"
    r"|break(?:s|ing)?\s*(?:of|above|below|over|under)?"
    r"|\babove\b|\bbelow\b|\bover\b|\bunder\b|level (?:at|of)?|\bzone (?:at|of)?", re.I)


def grab_level_price(text: str, level_span):
    """A price attached to the level: next to the level token, else after a
    break/retest/above/below keyword."""
    if level_span:
        s, e = level_span
        after = text[e:]
        for nm in RE_NUM_ANY.finditer(after):
            if nm.start() > 16:
                break
            v = clean_num(after, nm)
            if v is not None:
                return v
        before = text[max(0, s - 16):s]
        cands = [clean_num(before, nm) for nm in RE_NUM_ANY.finditer(before)]
        cands = [c for c in cands if c is not None]
        if cands:
            return cands[-1]
    return grab_after(text, RE_KW_LEVEL, window=16)


# --------------------------------------------------------------------------
# outcome / R
# --------------------------------------------------------------------------
RE_WIN = re.compile(
    r"\bhit (?:my |the )?(?:pt\d?|tp\d?|target|first target|full target)\b"
    r"|\btook profits?\b|\btp'?d\b|\bprofit target\b|\bwinner\b|\bit ripped\b"
    r"|\bclosed green\b|\bgreen (?:day|trade)\b|\bworked (?:out|perfectly)\b"
    r"|\bhit target\b|\bpaid (?:me )?out\b|\bran to (?:my )?target\b", re.I)
RE_LOSS = re.compile(
    r"\bstopped out\b|\bgot stopped\b|\bstop(?:ped)? me out\b|\bhit my stop\b"
    r"|\bstop (?:got )?hit\b|\btook a loss\b|\blosing trade\b|\bloser\b"
    r"|\bclosed red\b|\bred (?:day|trade)\b|\bfull loss\b|\bcut for a loss\b"
    r"|\bstop[\s\-]?loss hunted\b", re.I)
RE_BE = re.compile(
    r"\bbreak\s?even\b|\bbreakeven\b|\bscratch(?:ed)? (?:the )?trade\b"
    r"|\bout at be\b|\bstopped (?:out )?at be\b|\bmoved to be and\b"
    r"|\bstopped at breakeven\b", re.I)

RE_R = re.compile(r"(?<![\w.$])([+-]?\d{1,2}(?:\.\d{1,2})?)\s*[Rr](?![\w:/])")


RE_HEDGE = re.compile(
    r"\b(?:about to|about|almost|nearly|hoping|hope|if|could|should|would|might"
    r"|may|going to|gonna|will|want(?:ed)? to|waiting (?:for|to)|looking to"
    r"|trying to|need(?:s|ed)? to|before|until|unless|didn'?t|don'?t|never"
    r"|shouldve|should'?ve|would'?ve|could'?ve)\b", re.I)


RE_INFIN = re.compile(r"\bto\s+$")


def _unhedged(rx, t):
    out = []
    for m in rx.finditer(t):
        pre = t[max(0, m.start() - 34):m.start()]
        if RE_HEDGE.search(pre) or RE_INFIN.search(pre):
            continue
        out.append(m)
    return bool(out)


def classify_outcome(t: str):
    w, l, b = _unhedged(RE_WIN, t), _unhedged(RE_LOSS, t), _unhedged(RE_BE, t)
    if b and not (w or l):
        return "be"
    if w and not l:
        return "win"
    if l and not w:
        return "loss"
    return None


def grab_r(t: str):
    for m in RE_R.finditer(t):
        pre = t[max(0, m.start() - 12):m.start()].lower()
        if "r:" in pre or "r/" in pre:
            continue
        try:
            v = float(m.group(1))
        except ValueError:
            continue
        if -20 <= v <= 60:
            return v
    return None


# --------------------------------------------------------------------------
# misc
# --------------------------------------------------------------------------
RE_MENTION = re.compile(r"<@[!&]?\d+>|<#\d+>")
RE_APIKEY = re.compile(r"(apiKey|api_key)=[A-Za-z0-9_\-]+", re.I)
IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")

BOT_AUTHORS = {"Pingcord"}


SMART = {0x2018: "'", 0x2019: "'", 0x201c: '"', 0x201d: '"', 0x2013: "-",
         0x2014: "-", 0x00a0: " "}


def norm_quotes(s: str) -> str:
    """Discord text is full of curly quotes; every don't/wouldn't rule died on
    them until 2026-08-29."""
    return s.translate(SMART)


def scrub(s: str) -> str:
    return RE_APIKEY.sub(r"\1=REDACTED", s)


def norm_ts(raw: str) -> str:
    dt = datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    return dt.astimezone(ET).isoformat()


def images(msg):
    out = [u for u in msg.get("attachments") or [] if isinstance(u, str)]
    for u in msg.get("embeds") or []:
        if isinstance(u, str) and u.lower().split("?")[0].endswith(IMG_EXT):
            out.append(u)
    return [scrub(u) for u in out]


def analyse(text: str):
    """All field extraction for one chunk of text."""
    setup, explicit = classify_setup(text)
    level, span = classify_level(text)
    d = {
        "direction": classify_direction(text, span),
        "setup": setup,
        "level_name": level,
        "level_price": grab_level_price(text, span),
        "entry": grab_after(text, RE_KW_ENTRY),
        "stop": grab_after(text, RE_KW_STOP),
        "target": grab_after(text, RE_KW_TGT),
        "outcome": classify_outcome(text),
        "r_multiple": grab_r(text),
    }
    return d, explicit


def confidence(d, explicit, n_sym):
    score = 0
    if explicit and d["setup"]:
        score += 2
    elif d["setup"]:
        score += 1
    if d["level_name"] and d["level_name"] != "other":
        score += 1
    if d["direction"]:
        score += 1
    if any(d[k] is not None for k in ("entry", "stop", "target", "level_price")):
        score += 1
    if d["outcome"] or d["r_multiple"] is not None:
        score += 1
    if n_sym > 3:
        score -= 1
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def has_signal(d):
    if d["setup"] == "other" and not (
            d["level_name"] or d["direction"] or d["outcome"]
            or d["r_multiple"] is not None
            or any(d[k] is not None for k in ("entry", "stop", "target",
                                              "level_price"))):
        return False
    return (d["setup"] is not None or d["level_name"] is not None
            or d["direction"] is not None or d["outcome"] is not None
            or d["r_multiple"] is not None
            or any(d[k] is not None for k in ("entry", "stop", "target",
                                              "level_price")))


RE_ATTR_ANCHOR = re.compile(
    r"re[- ]?test|reclaim|b\s*&\s*r|\bbnr\b|break|one[- ]candle|pdh|pdl|pmh|pml"
    r"|\bhod\b|\blod\b|opening range|\borb\b|calls?\b|puts?\b|long|short",
    re.I)


def primary_symbol(text: str):
    """Multi-ticker text: the ticker nearest a setup/level/direction anchor.

    "we are all watching amd as aapl took a nice BNR" -> AAPL, not AMD.
    """
    hits = []
    for m in RE_SYM_CI.finditer(text):
        hits.append((m.start(),
                     SYM_ALIAS.get(m.group(1).upper(), m.group(1).upper())))
    for m in RE_SYM_CS.finditer(text):
        hits.append((m.start(), m.group(1)))
    hits.sort()
    if not hits:
        return None
    anchors = [m.start() for m in RE_ATTR_ANCHOR.finditer(text)]
    if not anchors or len(hits) == 1:
        return hits[0][1]
    return min(hits, key=lambda h: min(abs(h[0] - a) for a in anchors))[1]


def rows_for(msg, src):
    content = msg.get("content") or ""
    if not content.strip():
        return []
    if msg.get("author") in BOT_AUTHORS:
        return []
    body = norm_quotes(RE_MENTION.sub(" ", content))
    body = re.sub(r"https?://\S+", " ", body)
    if not find_symbols(body):
        return []

    lines = []
    for ln in body.split("\n"):
        if not ln.strip():
            continue
        # a single line naming several tickers AND several levels is a
        # watchlist: each comma clause is its own item
        if len(find_symbols(ln)) >= 2 and len(
                {classify_level(seg)[0] for seg in ln.split(",")
                 if classify_level(seg)[0]}) >= 2:
            lines.extend([seg for seg in ln.split(",") if seg.strip()])
        else:
            lines.append(ln)
    sym_lines = [ln for ln in lines if find_symbols(ln)]
    distinct = {tuple(find_symbols(ln)) for ln in sym_lines}
    multi = len(sym_lines) >= 2 and len(distinct) >= 2

    chunks = []
    if multi:
        for ln in sym_lines:
            syms = find_symbols(ln)
            chunks.append((syms[0] if len(syms) == 1 else primary_symbol(ln),
                           ln, ln))
    else:
        chunks.append((primary_symbol(body), body, content))

    if multi and not any(has_signal(analyse(c[1])[0]) for c in chunks):
        multi = False
        chunks = [(primary_symbol(body), body, content)]

    ts = norm_ts(msg["ts"])
    imgs = images(msg)
    out = []
    for sym, text, quote in chunks:
        d, explicit = analyse(text)
        if not multi:
            pass
        else:
            # a bare watchlist line ("NVDA above PDH") is still an item; a line
            # with nothing but a ticker is not
            if not has_signal(d):
                continue
        if not has_signal(d):
            continue
        row = {
            "src": src,
            "msg_id": msg["id"],
            "ts": ts,
            "author": msg.get("author"),
            "symbol": sym,
            "direction": d["direction"],
            "setup": d["setup"],
            "level_price": d["level_price"],
            "level_name": d["level_name"],
            "entry": d["entry"],
            "stop": d["stop"],
            "target": d["target"],
            "outcome": d["outcome"],
            "r_multiple": d["r_multiple"],
            "quote": scrub(quote),
            "image_urls": imgs,
            "confidence": confidence(d, explicit, len(find_symbols(text))),
        }
        out.append(row)
    return out


def main():
    total = 0
    written = 0
    per_src = {}
    with open(OUT, "w", encoding="utf-8") as fh:
        for fn in SRC_FILES:
            p = os.path.join(DATA, fn)
            if not os.path.exists(p):
                continue
            msgs = json.load(open(p, encoding="utf-8"))
            total += len(msgs)
            n = 0
            for m in msgs:
                for row in rows_for(m, fn):
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n += 1
            per_src[fn] = (len(msgs), n)
            written += n
    print("messages scanned:", total)
    print("rows written    :", written)
    for k, (a, b) in per_src.items():
        print("  %-22s %6d msgs -> %5d rows" % (k, a, b))
    print("out:", OUT)


if __name__ == "__main__":
    main()
