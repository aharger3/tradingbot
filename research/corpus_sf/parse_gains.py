"""Deterministic parser for discord_data/post-your-gains.json -> gains.jsonl.

NOT AUSTIN'S MARKS. These are member P&L posts from the Discord `post-your-gains`
channel (mentors and members alike). Output lives only under research/corpus_sf/
and is never merged into any Austin mark corpus.

Gate: a row is emitted only when symbol AND direction AND outcome are all present
in the text. Everything else is left on the floor -- most posts in this channel
are screenshots with no text, or text with no stated direction.

Design: clause-level extraction. A message is split into clauses (newline /
sentence / comma when multi-symbol) so that "appl loss long, msft loss short,
goog loss long" yields three rows. A message-level fallback fires only when no
clause matched; with several symbols in play it attaches the row to the symbol
nearest the direction cue.

v2 changes (after hand-checking 30 extracted + 15 skipped):
  * "be" the English verb was matching /b\\/?e/ and inventing breakeven outcomes.
  * "- 5 min" / "- 50 contracts" (dash, space, digit) was read as a negative P&L.
  * hypothetical and question posts ("I was supposed to short QQQ at the PDH")
    were being booked as trades.
  * mixed win+loss narratives now resolve only on an explicit signed figure.
  * bullish/bearish dropped as a direction source (they describe the tape).
  * level_price rejected timeframes ("5 min OR") and contract counts ("3 cons").

Usage:  python research/corpus_sf/parse_gains.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "discord_data", "post-your-gains.json")
OUT = os.path.join(HERE, "gains.jsonl")
ET = ZoneInfo("America/New_York") if ZoneInfo else None

# ---------------------------------------------------------------------------
# Symbols
# ---------------------------------------------------------------------------
# Case-insensitive tickers: no common English word collides with these.
TICKERS_CI = {
    "TSLA", "NVDA", "AAPL", "AMZN", "MSFT", "GOOGL", "GOOG", "NFLX", "PLTR",
    "AMD", "INTC", "AVGO", "SOFI", "MSTR", "SNDK", "SMCI", "ORCL", "IWM",
    "SPY", "QQQ", "SPX", "TQQQ", "TSLL", "SMH", "UNH", "ACHR", "IREN", "BABA",
    "TSM", "SOUN", "GME", "UVXY", "NDX", "DIA",
}
# Uppercase-only tickers: the lowercase form is an ordinary English word.
TICKERS_UPPER = {
    "MU", "COIN", "MARA", "CRM", "UBER", "NQ", "MNQ", "ES", "MES", "GC", "RTY",
    "YM", "M2K", "SI",
}
# Company names and observed misspellings -> ticker.
ALIASES = {
    "tesla": "TSLA", "amazon": "AMZN", "apple": "AAPL", "appl": "AAPL",
    "nvidia": "NVDA", "nvdia": "NVDA", "nvida": "NVDA", "google": "GOOGL",
    "netflix": "NFLX", "palantir": "PLTR", "microsoft": "MSFT",
    "robinhood": "HOOD", "hood": "HOOD", "coinbase": "COIN", "oracle": "ORCL",
    "alibaba": "BABA", "broadcom": "AVGO", "micron": "MU", "intel": "INTC",
    "meta": "META", "facebook": "META", "sandisk": "SNDK",
    "microstrategy": "MSTR", "nasdaq": "NQ", "russell": "RTY",
    "tlsa": "TSLA", "tlsla": "TSLA", "aaple": "AAPL", "goolg": "GOOGL",
    "gogl": "GOOGL", "nvdaa": "NVDA",
}
from chat_vocab import GAINS_NOT_TICKERS as NOT_TICKERS  # noqa: E402

_ci_alt = "|".join(sorted(TICKERS_CI | set(ALIASES), key=len, reverse=True))
RE_SYM_CI = re.compile(r"(?<![A-Za-z0-9$])(" + _ci_alt + r")(?![A-Za-z0-9])", re.I)
RE_SYM_UP = re.compile(
    r"(?<![A-Za-z0-9$])(" + "|".join(sorted(TICKERS_UPPER)) + r")(?![A-Za-z0-9])")
RE_SYM_CASH = re.compile(r"\$([A-Za-z]{1,5})(?![A-Za-z0-9])")
# "meta" is only a ticker when it is not the prefix of metaverse/metadata/...
RE_META_BAD = re.compile(r"\bmeta(verse|data|physic\w*|phor\w*|bolic\w*)\b", re.I)


def find_symbols(text: str):
    """[(symbol, start, end)] in order of first appearance, de-duplicated."""
    if not text:
        return []
    clean = RE_META_BAD.sub(" ", text)
    hits = []
    for m in RE_SYM_CI.finditer(clean):
        w = m.group(1).lower()
        hits.append((ALIASES.get(w, w.upper()), m.start(), m.end()))
    for m in RE_SYM_UP.finditer(clean):
        hits.append((m.group(1), m.start(), m.end()))
    for m in RE_SYM_CASH.finditer(clean):
        tok = m.group(1).upper()
        if tok in NOT_TICKERS or len(tok) < 2:
            continue
        hits.append((ALIASES.get(tok.lower(), tok), m.start(), m.end()))
    seen, out = set(), []
    for sym, pos, end in sorted(hits, key=lambda h: h[1]):
        if sym in NOT_TICKERS or sym in seen:
            continue
        seen.add(sym)
        out.append((sym, pos, end))
    return out


# ---------------------------------------------------------------------------
# Direction
# ---------------------------------------------------------------------------
# bullish/bearish are deliberately NOT direction cues: in this channel they
# almost always describe the tape or the higher timeframe, not the trade taken.
RE_CALLS = re.compile(
    r"\bcalls\b|\bcall\s+(option|contract|side|spread|debit|credit)|"
    r"\b\d{1,3}\s?c\b(?![\w])", re.I)
RE_CALL1 = re.compile(
    r"(?:bought|sold|took|grabbed|scalped|my|the|a|some|\d+)\s+"
    r"(?:\d+(?:\.\d+)?\s+)?calls?\b", re.I)
# "call" is a noun here only sometimes: "awesome call", "call it a day" and
# "called out" are not option trades.
RE_CALL_BAD = re.compile(
    r"(?:awesome|great|nice|good|amazing|solid|perfect|sick|beautiful|"
    r"excellent|fantastic|killer|clutch|close|tough|bad|wrong|right|judg\w*|"
    r"conference|margin|phone|video|sales|wake-?up|his|her|their|your|"
    r"tony'?s?|jack'?s?|jdub'?s?|neto'?s?)\s+calls?|"
    r"call\s+(?:out|it|me|you|him|her|us|back|the day|the shots)|"
    r"call(?:ed|ing)|call-?outs?", re.I)
RE_PUTS = re.compile(r"\bputs\b|\bput\s+(option|contract|side|spread|debit|credit)", re.I)
RE_PUT1 = re.compile(
    r"(?:bought|sold|took|grabbed|scalped|my|the|a|some|\d+)\s+"
    r"(?:\d+(?:\.\d+)?\s+)?put\b", re.I)
RE_LONG = re.compile(r"\b(long|longed|longs)\b", re.I)
RE_LONG_BAD = re.compile(
    r"\b(?:as|how|so|too|for|takes?|taking|took|been|not|its|it's)\s+long\b|"
    r"\blong[- ](?:term|run|time|way|haul|since|overdue)\b|"
    r"\bno longer\b|\balong\b|\blong time\b|\blong enough\b|\blong story\b", re.I)
RE_SHORT = re.compile(r"\b(short|shorted|shorts|shorting)\b", re.I)
RE_SHORT_BAD = re.compile(
    r"\bshort[- ](?:term|lived|squeeze|while|period|stint|cut|sighted)\b|"
    r"\bshort of\b|\ba short (break|day|session|walk|nap)\b|\bfell short\b|"
    r"\bshortly\b|\bshort side of\b|"
    # "had to cut them short" is an idiom, not a short trade
    r"\bcut\s+(?:it|them|him|her|us|that|the\s+\w+)?\s*short\b|"
    r"\bsold\s+\w+\s+short\s+of\b|\bsells?\s+\w+\s+short\b(?=\s+of)", re.I)


def direction_of(text: str):
    """'long' | 'short' | None.  None when both fire or neither does."""
    long_hit = bool(RE_CALLS.search(text)) or (
        bool(RE_CALL1.search(text)) and not RE_CALL_BAD.search(text))
    short_hit = bool(RE_PUTS.search(text)) or bool(RE_PUT1.search(text))
    if RE_LONG.search(text) and not RE_LONG_BAD.search(text):
        long_hit = True
    if RE_SHORT.search(text) and not RE_SHORT_BAD.search(text):
        short_hit = True
    if long_hit and not short_hit:
        return "long"
    if short_hit and not long_hit:
        return "short"
    return None


RE_DIR_ANY = re.compile(
    r"\bcalls?\b|\bputs?\b|\blong\w*\b|\bshort\w*\b|\b\d{1,3}\s?c\b", re.I)


# ---------------------------------------------------------------------------
# Outcome
# ---------------------------------------------------------------------------
# A sign must be glued to its digits. "Setup - 5 Min High Retest" and
# "TSLA calls - 50 contracts" are not negative P&L.
RE_WIN = re.compile(
    r"(?<![\w.:/-])\+\$?\d|"
    r"\bgreen\b|\bwins?\b|\bwon\b|\bwinner\b|\bprofit\w*|\bgains?\b|"
    r"\bbanger\b|\bbagger\b|\btook profit|\bpaid (?:me|out)\b|"
    r"\bmade\s+\$?\d|\bup\s+\$?\d|\$?\d[\d,.]*\s?k?\s+up\b|"
    r"\bnice (?:win|trade|day|scalp)\b|"
    # "ended up cutting it early" is not a result: require money or a colour
    r"\bfinish\w*\s+(?:the day\s+)?(?:up\s+\$?\d|green)\b|"
    r"\bend\w*\s+(?:the day\s+|the week\s+)?(?:up\s+\$?\d|green|on green|in the green)\b|"
    r"\bi'?ll take (?:the win|it|the)\b|\bill take (?:the|it)\b", re.I)
RE_WIN_BAD = re.compile(
    r"\b(?:no|not|zero|without|any|didn'?t|couldn'?t|can'?t|cannot|won'?t|"
    r"never|hardly|barely|missed?|lack of)\s+"
    r"(?:\w+\s+){0,3}(gains?|profit\w*|win\w*|green|money)\b|"
    # sign-offs, not results
    r"\bstay\s+green\b|\bkeep\s+(?:it\s+)?green\b|\bstay\s+profitable\b|"
    r"\bgood\s+luck\b|\bhappy\s+trading\b", re.I)
RE_LOSS = re.compile(
    r"(?<![\w.:/-])(?<!\d\s)-\$?\d|"
    r"\bloss(?:es)?\b|\blost\b|\blosing\b|\bloser\b|"
    # bare "red" is a candle, the market, or a red-folder news event far more
    # often than it is this poster's P&L. Only these phrasings are a result.
    r"\bred\s+(?:day|today|month|week)\b|\bin the red\b|"
    r"\b(?:ended?|finish\w*|clos\w*|went)\s+red\b|"
    r"\bstopped\s+out\b|\bstop\s+out\b|\bgot\s+stopped\b|"
    r"\btook\s+(?:a|an)\s+(?:l|loss)\b|\bdown\s+\$?\d|\bgave\s+back\b|"
    r"\bchopped\s+up\b|\bwicked\s+out\b|\bturn\w*\s+red\b|\bround\s?trip\w*\b", re.I)
RE_LOSS_BAD = re.compile(
    r"\b(?:no|not|zero|without|avoid\w*|cut the)\s+loss(?:es)?\b|\bstop\s?loss\b|"
    r"\bred to green\b|\balmost\s+(?:got\s+)?stopped\b|\bnearly\s+stopped\b|"
    r"\bred\s+candle\b", re.I)
# "be" the English verb is not breakeven. Require an unambiguous token, and
# reject stop-management phrasing, which describes the stop and not the result.
RE_BE = re.compile(
    r"\bbreak\s?even\b|\bbroke\s+even\b|\bb/e\b|\bscratch(?:ed)?\b|"
    r"\b(?:finish\w*|end\w*|clos\w*|exit\w*)\s+(?:the day\s+)?flat\b|"
    r"\bflat on the day\b", re.I)
RE_BE_UP = re.compile(r"(?<![A-Za-z])BE(?![A-Za-z])")
RE_BE_BAD = re.compile(
    r"\b(?:stop\w*|sl|trail\w*|move[ds]?|moving|risk[- ]free|protect\w*|"
    r"rest|runner\w*|remaining)\b[^.\n]{0,24}?\b(?:break\s?even|b/e|BE)\b|"
    r"\b(?:break\s?even|b/e|BE)\b[^.\n]{0,16}?\b(?:stop|sl)\b", re.I)
RE_SIGNED = re.compile(r"(?<![\w.:/-])([-+])\$?(\d[\d,]*(?:\.\d+)?)\s?([kK])?")


def outcome_of(text: str):
    """'win' | 'loss' | 'be' | None.  None whenever the text is ambiguous."""
    be = bool(RE_BE.search(text)) or bool(RE_BE_UP.search(text))
    if be and RE_BE_BAD.search(text):
        be = False
    win = bool(RE_WIN.search(text)) and not RE_WIN_BAD.search(text)
    loss = bool(RE_LOSS.search(text)) and not RE_LOSS_BAD.search(text)
    if win and loss:
        # mixed narrative ("profit in the morning ... EOD -$607"). Only an
        # explicit, unanimous signed figure resolves it; otherwise drop the row.
        signs = {m.group(1) for m in RE_SIGNED.finditer(text)}
        if signs == {"+"}:
            return "win"
        if signs == {"-"}:
            return "loss"
        return None
    if be and not (win or loss):
        return "be"
    if win:
        return "win"
    if loss:
        return "loss"
    return None


# This channel's house format is one line per trade, scored with a bare letter:
#   "Pltr Calls L"  /  "QQQ Puts ChoCh 10:10 entry-L"  /  "+5MIRL W"
# A lone W/L is only trusted inside a short clause, and never where P/L or P&L
# could supply the letter.
RE_TOK_W = re.compile(r"(?<![A-Za-z0-9/&])W(?![A-Za-z0-9])")
RE_TOK_L = re.compile(r"(?<![A-Za-z0-9/&])L(?![A-Za-z0-9])")
RE_PL_NOISE = re.compile(r"P\s?[/&]\s?L|PNL|P&L", re.I)


def outcome_of_clause(seg: str):
    """outcome_of, plus the bare-letter scoring used in short one-line posts."""
    o = outcome_of(seg)
    if o is not None:
        return o
    if len(seg.strip()) <= 60 and not RE_PL_NOISE.search(seg):
        w, l = bool(RE_TOK_W.search(seg)), bool(RE_TOK_L.search(seg))
        if w != l:
            return "win" if w else "loss"
    return None


RE_OUT_EXPLICIT = re.compile(
    r"(?<![\w.:/-])[-+]\$?\d|\bloss\b|\blost\b|\bwins?\b|\bwon\b|\bgreen\b|"
    r"\bprofit\w*|\bstopped out\b|\bbreak\s?even\b|\bgains?\b", re.I)


# ---------------------------------------------------------------------------
# Hypothetical / question guard
# ---------------------------------------------------------------------------
RE_HYPO = re.compile(
    r"\bsupposed to\b|\bshould(?:'?ve| have)\b|\bwould(?:'?ve| have)\b|"
    r"\bshoulda\b|\bwoulda\b|\bcoulda\b|\bif it\b|\bif we\b|\bif i\b|"
    r"\balmost\b|\bnearly\b|\bmissed (?:the|out|my|that|it|a)\b|"
    r"\bdidn'?t (?:take|enter|get|pull|trade)\b|\bnext time\b|"
    r"\bplan(?:ning)? to\b|\blooking to (?:take|enter|short|go|buy)\b|"
    r"\bwaiting (?:for|until|on)\b|\bwhat (?:is|was|do|would|are) (?:your|you)\b|"
    r"\bwish i\b|\bhypothetical\b|\bwatch(?:ing|ed) for\b|\bwould be\b|"
    r"\bhad i\b|\bcould have\b|\bpaper trade\b|"
    # trades deliberately not taken
    r"\bheld\s+(?:myself|off|back)\b|\bkept\s+myself\b|\btalked\s+myself\s+out\b|"
    r"\bpassed\s+on\b|\bstayed\s+(?:out|away)\b|\bsat\s+(?:it\s+)?out\b|"
    r"\bno\s+trade\b|\bdid\s+not\s+(?:take|enter)\b", re.I)


def hypothetical(text: str) -> bool:
    """True when the clause narrates a trade NOT taken, or asks a question."""
    return bool("?" in text or RE_HYPO.search(text))


# ---------------------------------------------------------------------------
# Setup / level / prices / R
# ---------------------------------------------------------------------------
RE_BR = re.compile(
    r"\bbreak(?:out)?\s*(?:and|&|n|\+|/)?\s*re-?tests?\b|\bb\s?&\s?r\b|\bbnr\b|"
    r"\bbreak\s+and\s+re-?test\b", re.I)
RE_BREAK = re.compile(r"\bbroke\b|\bbreak(?:out|ing|s)?\b", re.I)
RE_RETEST = re.compile(r"\bre-?tests?(?:ed|ing)?\b", re.I)
RE_OCR = re.compile(
    r"\bone[\s-]candle(?:\s+rule)?\b|\b1\s?candle\s+rule\b|(?<![A-Za-z])OCR(?![A-Za-z])",
    re.I)
RE_OTHER_SETUP = re.compile(
    r"\borb\b|\breclaim\w*|\bfvg\b|\bdouble\s+(?:top|bottom)\b|"
    r"\bfailed\s+breakdown\b|\bpull\s?back\b|\bflag\b|\bwedge\b|"
    r"\bgap\s+(?:fill|down|up)\b|\bvwap\s+bounce\b|\border\s?block\b", re.I)

LEVELS = [
    ("or_high", r"\b(?:or\s?high|orh|opening\s+range\s+high|5\s?min(?:ute)?\s+(?:opening\s+)?range\s+high|5\s?m(?:in)?\s+high)\b"),
    ("or_low", r"\b(?:or\s?low|orl|opening\s+range\s+low|5\s?m(?:in)?\s+low)\b"),
    ("pmh", r"\b(?:pmh|pmhr|pre-?\s?market\s+high|premarket\s+high|pm\s+high)\b"),
    ("pml", r"\b(?:pml|pre-?\s?market\s+low|premarket\s+low|pm\s+low)\b"),
    ("pdh", r"\b(?:pdh|pdhr|previous\s+day(?:'?s)?\s+high|prev(?:ious)?\s+high|prior\s+day\s+high|yesterday'?s?\s+high)\b"),
    ("pdl", r"\b(?:pdl|previous\s+day(?:'?s)?\s+low|prev(?:ious)?\s+low|prior\s+day\s+low|yesterday'?s?\s+low)\b"),
    ("hod", r"\b(?:hod|high\s+of\s+(?:the\s+)?day)\b"),
    ("lod", r"\b(?:lod|low\s+of\s+(?:the\s+)?day)\b"),
    ("other", r"\b(?:opening\s+range|orb|vwap|key\s+level|kl|pwh|pwl|pdc|round\s+number)\b"),
]
LEVEL_RES = [(name, re.compile(p, re.I)) for name, p in LEVELS]

RE_STOP = re.compile(
    r"\b(?:stop(?:\s?loss)?|sl)\s*(?:at|@|=|:|of|below|above)?\s*\$?(\d{1,4}(?:\.\d{1,2})?)\b",
    re.I)
RE_TARGET = re.compile(
    r"\b(?:target|tp\d?|pt\d?)\s*(?:at|@|=|:|of)?\s*\$?(\d{1,4}(?:\.\d{1,2})?)\b", re.I)
RE_ENTRY = re.compile(
    r"\bentry\s*(?:at|@|=|:|of|was|around|near)?\s*\$?(\d{1,4}(?:\.\d{1,2})?)\b|"
    r"\b(?:entered|got in|filled|bought in)\s+(?:at|@|around|near|off of|off)\s*"
    r"\$?(\d{1,4}(?:\.\d{1,2})?)\b", re.I)
RE_R = re.compile(r"(?<![\w.])([-+]?\d{1,2}(?:\.\d{1,2})?)\s*R\b(?!:|R)", re.I)

TIMEFRAME_INTS = {1, 2, 3, 4, 5, 10, 15, 30, 60}
RE_PRICE_ANCHORED = re.compile(
    r"(?:at|@|of|around|near|above|below|off|~|to)\s*\$?(\d{1,4}(?:\.\d{1,2})?)(?![\w%])|"
    r"\$(\d{1,4}(?:\.\d{1,2})?)(?![\w%])|"
    r"(?<![\w$.])(\d{2,4}\.\d{1,2})(?![\w%])", re.I)
RE_UNIT_AFTER = re.compile(
    r"^\s*(?:min\w*|m\b|sec\w*|s\b|cons?\b|contracts?\b|%|/|:|r\b|x\b)", re.I)


def setup_of(text: str):
    br = bool(RE_BR.search(text)) or (
        bool(RE_BREAK.search(text)) and bool(RE_RETEST.search(text)))
    ocr = bool(RE_OCR.search(text))
    if br and ocr:
        return "br_ocr"
    if br:
        return "break_retest"
    if ocr:
        return "one_candle"
    if RE_OTHER_SETUP.search(text) or RE_RETEST.search(text):
        return "other"
    return None


def level_of(text: str):
    """(level_name, level_price); price only when a number is anchored to it.

    A bare integer beside a level token is usually a timeframe ("5 min OR") or a
    contract count ("3 cons"), not a price; those are rejected outright.
    """
    for name, rx in LEVEL_RES:
        m = rx.search(text)
        if not m:
            continue
        window = text[max(0, m.start() - 16): m.end() + 18]
        price = None
        for pm in RE_PRICE_ANCHORED.finditer(window):
            raw = pm.group(1) or pm.group(2) or pm.group(3)
            if raw is None:
                continue
            if RE_UNIT_AFTER.match(window[pm.end():]):
                continue
            try:
                v = float(raw)
            except ValueError:
                continue
            if not (1.0 <= v <= 9999.0):
                continue
            if "." not in raw and int(v) in TIMEFRAME_INTS:
                continue
            price = v
            break
        return name, price
    return None, None


def _num(m):
    if not m:
        return None
    for g in m.groups():
        if g:
            try:
                return float(g)
            except (ValueError, TypeError):
                return None
    return None


def r_multiple_of(text: str):
    """Signed only when the text signs it. Never inferred from the outcome."""
    m = RE_R.search(text)
    if not m:
        return None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    return None if abs(v) > 50 else v


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------
RE_SEG = re.compile(r"[\n\r]+|(?<=[a-zA-Z0-9\)\]])[.!?;]+\s")
RE_SUBSEG = re.compile(r",(?!\d)|\s+&\s+|\s+then\s+", re.I)
RE_MENTION = re.compile(r"<[@#!&:][^>]*>")
RE_URL = re.compile(r"https?://\S+")

# Discord posts are full of smart punctuation. Un-normalised, every guard that
# contains an apostrophe ("didn't enter", "should've") silently fails to fire.
SMART = {
    "’": "'", "‘": "'", "ʼ": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-", " ": " ", "…": "...",
}
_SMART_RE = re.compile("|".join(map(re.escape, SMART)))


def normalize(text: str) -> str:
    return _SMART_RE.sub(lambda m: SMART[m.group(0)], text)


def segments(text: str):
    """Clauses; a clause holding >1 symbol is split again on commas."""
    out = []
    for seg in RE_SEG.split(text):
        if not seg or not seg.strip():
            continue
        if len(find_symbols(seg)) > 1:
            parts = [p for p in RE_SUBSEG.split(seg) if p and p.strip()]
            out.extend(parts if len(parts) > 1 else [seg])
        else:
            out.append(seg)
    return out


# ---------------------------------------------------------------------------
# Row assembly
# ---------------------------------------------------------------------------
def to_et(ts_utc: str):
    """Export timestamps are UTC (verified against scarface-alerts' 13:30 UTC
    open cluster). Emit ET, which is the only clock this project reasons in."""
    try:
        dt = datetime.strptime(ts_utc[:19], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return ts_utc
    return dt.astimezone(ET).isoformat() if ET else dt.isoformat()


def build_row(msg, src, symbol, direction, outcome, scope, quote, conf):
    lname, lprice = level_of(scope)
    return {
        "src": src,
        "msg_id": msg["id"],
        "ts": to_et(msg["ts"]),
        "author": msg.get("author"),
        "symbol": symbol,
        "direction": direction,
        "setup": setup_of(scope),
        "level_price": lprice,
        "level_name": lname,
        "entry": _num(RE_ENTRY.search(scope)),
        "stop": _num(RE_STOP.search(scope)),
        "target": _num(RE_TARGET.search(scope)),
        "outcome": outcome,
        "r_multiple": r_multiple_of(scope),
        "quote": quote,
        "image_urls": list(msg.get("attachments") or []) + [
            u for u in (msg.get("embeds") or []) if isinstance(u, str)],
        "confidence": conf,
    }


RE_OUT_ANY = re.compile(
    "|".join([RE_WIN.pattern, RE_LOSS.pattern, RE_BE.pattern]), re.I)


def _nearest(text, syms, rx):
    cues = [m.start() for m in rx.finditer(text)]
    if not cues:
        return None
    return min(syms, key=lambda s: min(abs(s[1] - c) for c in cues))[0]


RE_COORD_SEP = re.compile(r"^[\s,&/+]*(?:and|&|\+|,|/)?[\s,&/+]*$", re.I)


def _coordinated(text, syms):
    """True when the symbols form a bare list that the direction cue governs.

    'Puts on PLTR & NVDA +$5.85k' shares one direction and one outcome across
    both names. 'I usually trade 1 or 2 dte on spy / qqq when trading indices'
    does not -- the direction cue is sentences away, so distance is capped.
    """
    if len(syms) < 2:
        return False
    for (_a, _pa, ea), (_b, pb, _eb) in zip(syms, syms[1:]):
        if not RE_COORD_SEP.match(text[ea:pb]):
            return False
    lo, hi = syms[0][1], syms[-1][2]
    cues = [m.start() for m in RE_DIR_ANY.finditer(text)]
    if not cues:
        return False
    return min(max(lo - c, c - hi, 0) for c in cues) <= 40


def _attributed_symbol(text, syms):
    """The trade's subject in a multi-symbol message.

    Both the direction cue AND the outcome cue must sit nearest the same symbol.
    Without this, "QQQ +$150 done. NVDA in on 134c @ 2.65" books QQQ's +$150
    onto the still-open NVDA position.
    """
    d = _nearest(text, syms, RE_DIR_ANY)
    o = _nearest(text, syms, RE_OUT_ANY)
    return d if (d is not None and d == o) else None


def parse_message(msg, src):
    """(rows, skip_reason_or_None)."""
    raw = normalize(msg.get("content") or "")
    text = RE_URL.sub(" ", RE_MENTION.sub(" ", raw))
    if not text.strip():
        return [], "no_text"

    rows = []
    for seg in segments(text):
        syms = find_symbols(seg)
        if len(syms) != 1 or hypothetical(seg):
            continue
        d = direction_of(seg)
        o = outcome_of_clause(seg) if d else None
        if not (d and o):
            continue
        conf = "high" if RE_OUT_EXPLICIT.search(seg) else "medium"
        rows.append(build_row(msg, src, syms[0][0], d, o, seg, seg.strip(), conf))
    if rows:
        return rows, None

    # message-level fallback -- only for messages that are unambiguous as a whole
    syms = find_symbols(text)
    if syms and not hypothetical(text):
        d = direction_of(text)
        o = outcome_of(text) if d else None
        if d and o:
            conf = "medium" if RE_OUT_EXPLICIT.search(text) else "low"
            if len(syms) == 1:
                return [build_row(msg, src, syms[0][0], d, o, text, raw.strip(), conf)], None
            # "QQQ & SPY calls" -- one direction and one outcome shared by a
            # coordinated list of symbols. Only a bare separator may sit between
            # them; any other words and the sharing is not established.
            if _coordinated(text, syms):
                return [build_row(msg, src, s[0], d, o, text, raw.strip(), "low")
                        for s in syms], None
            sym = _attributed_symbol(text, syms)
            if sym:
                return [build_row(msg, src, sym, d, o, text, raw.strip(), conf)], None

    if not syms:
        return [], "no_symbol"
    if hypothetical(text):
        return [], "hypothetical_or_question"
    if not direction_of(text):
        return [], "no_direction"
    if not outcome_of(text):
        return [], "no_outcome"
    return [], "ambiguous"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    msgs = json.load(open(args.src, encoding="utf-8"))
    src_name = os.path.basename(args.src)

    rows, reasons = [], {}
    image_only = text_and_image = 0
    for m in msgs:
        content = (m.get("content") or "").strip()
        media = bool(m.get("attachments") or m.get("embeds"))
        if media and not content:
            image_only += 1
        elif media:
            text_and_image += 1
        rs, why = parse_message(m, src_name)
        rows.extend(rs)
        if why:
            reasons[why] = reasons.get(why, 0) + 1

    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def cnt(field):
        return sum(1 for r in rows if r.get(field) is not None)

    stats = {
        "total_messages": len(msgs),
        "image_only_no_text": image_only,
        "text_plus_image": text_and_image,
        "extracted_rows": len(rows),
        "messages_with_rows": len({r["msg_id"] for r in rows}),
        "with_symbol": cnt("symbol"),
        "with_direction": cnt("direction"),
        "with_outcome": cnt("outcome"),
        "with_setup": cnt("setup"),
        "with_level_name": cnt("level_name"),
        "with_level_price": cnt("level_price"),
        "with_entry": cnt("entry"),
        "with_stop": cnt("stop"),
        "with_target": cnt("target"),
        "with_r_multiple": cnt("r_multiple"),
        "with_image": sum(1 for r in rows if r["image_urls"]),
        "confidence": {c: sum(1 for r in rows if r["confidence"] == c)
                       for c in ("high", "medium", "low")},
        "outcome_mix": {o: sum(1 for r in rows if r["outcome"] == o)
                        for o in ("win", "loss", "be")},
        "direction_mix": {d: sum(1 for r in rows if r["direction"] == d)
                          for d in ("long", "short")},
        "skip_reasons": reasons,
        "date_min": min((r["ts"] for r in rows), default=None),
        "date_max": max((r["ts"] for r in rows), default=None),
    }
    with open(os.path.join(HERE, "gains_stats.json"), "w") as f:
        json.dump(stats, f, indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
