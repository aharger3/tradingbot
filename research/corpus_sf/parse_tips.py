#!/usr/bin/env python3
"""Deterministic parser for the three "tips" channels.

    discord_data/member-tips-tricks.json   498 messages
    discord_data/scarface-tips.json          2 messages
    discord_data/books.json                  2 messages

WHAT THESE CHANNELS ACTUALLY ARE
--------------------------------
member-tips-tricks is NOT an alert channel.  It is a peer-support channel: 498
messages, 249 distinct authors, median content length 88 chars, 28 messages with
no text at all (image-only).  The dominant traffic is

  * charting-platform how-to (TradingView / ThinkOrSwim / IBKR TWS / Webull),
  * indicator recommendations (key-levels scripts that draw PDH/PDL/PMH/PML),
  * options position-sizing arithmetic (delta x distance x contracts x 100),
  * course/subscription/Whop access logistics and anti-scam PSAs,
  * one-line psychology maxims.

There are essentially no trade calls.  Across all 502 messages there is not one
message that states a symbol together with an entry, a stop and a target.  A
parser that fills entry/stop/target here would be inventing them, so this one
gates those fields hard (see PRICE GATE below) and they come out null.

What IS here, and what this parser is for, is RULE CANDIDATES: declarative
statements about how to trade -- stop placement, exit discipline, level
selection, risk sizing, session hygiene.  Those are the rows worth keeping.

WHAT IS EXTRACTED vs SKIPPED
----------------------------
A message is emitted only if it clears three tests, in order:

  1. it has >= MIN_CHARS of real text after mentions/emoji/urls are stripped;
  2. it is not pure courtesy ("thanks", "following", "you're welcome") and not
     pure platform-access logistics (Whop / modules / subscription / discord
     privacy settings) with zero trading vocabulary;
  3. it hits at least one SUBSTANCE category -- setup, level, exit/stop, risk
     sizing, indicator, session, or psychology.

Everything that fails is written to tips_skipped.jsonl with the reason, so the
recall check is auditable rather than assumed.

PRICE GATE
----------
entry / stop / target / level_price are filled ONLY when the message names a
symbol from universe.py AND names a setup or a level.  Without that anchor the
decimals in this channel are option premiums ($1.22), deltas (0.342), risk
percentages (13.15%) and account sizes ($25,000) -- never chart levels.  The
gate is why those four fields are null on every row: that is the correct value,
not a parser failure.

Output: research/corpus_sf/tips.jsonl        (extracted)
        research/corpus_sf/tips_skipped.jsonl (audit trail)
Run:    python research/corpus_sf/parse_tips.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRCS = [
    "member-tips-tricks.json",
    "scarface-tips.json",
    "books.json",
]
OUT = os.path.join(REPO, "research", "corpus_sf", "tips.jsonl")
OUT_SKIP = os.path.join(REPO, "research", "corpus_sf", "tips_skipped.jsonl")

MIN_CHARS = 25

# ---------------------------------------------------------------- ticker vocab
# universe.py is the single source of truth for symbols (see
# research/test_universe_single_source.py).  Never inline a ticker list here.
try:
    sys.path.insert(0, REPO)
    import universe  # noqa: E402

    KNOWN = set(getattr(universe, "ALL_SYMS", []))
except Exception:
    KNOWN = set()

RE_MENTION = re.compile(r"<@[!&#]?\d+>")
RE_CHANNEL = re.compile(r"<#\d+>")
RE_EMOJI_TAG = re.compile(r"<a?:\w+:\d+>")
RE_URL = re.compile(r"https?://\S+")
RE_TICKER_CAND = re.compile(r"\b[A-Z]{2,5}\b")

IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".bmp")

# ------------------------------------------------------------------ vocabulary
# Every regex below is keyed to text that actually occurs in these three files.

RE_SETUP_BR = re.compile(
    r"\b(break[\s-]*(?:and|&|\+|/|n)?[\s-]*re[\s-]?test|breakout\s+and\s+retest|"
    r"\bbnr\b|\bb\s*&\s*r\b|\bb/r\b|\bb&r\b|break/retest|break\s*-\s*retest)\b",
    re.I,
)
RE_SETUP_OCR = re.compile(r"\b(one[\s-]?candle(?:\s+rule)?|\bocr\b|1[\s-]?candle)\b", re.I)
# other named setups this channel talks about
RE_SETUP_OTHER = {
    "orb": re.compile(r"\b(orb|opening\s+range(?:\s+break(?:out)?)?)\b", re.I),
    "three_bar": re.compile(r"\b(3[\s-]?bar|three[\s-]?bar)\b", re.I),
    "reversal": re.compile(r"\breversal\b", re.I),
    "hammer": re.compile(r"\bhammer\b", re.I),
    "fvg": re.compile(r"\b(fvg|fair\s+value\s+gap)\b", re.I),
    "gap_fill": re.compile(r"\bgap\s*fill\b", re.I),
    "reclaim": re.compile(r"\breclaim\b", re.I),
    "84_rule": re.compile(r"\b84\s*%?\s*rule\b", re.I),
    "inside_bar": re.compile(r"\b(inside\s+bar|\bib\b)\b", re.I),
}

# NOTE: the bare "OR high" abbreviation is matched CASE-SENSITIVELY.  Lower-case
# "or high" is the English conjunction -- "working or high interest strikes"
# produced a phantom or_high level before this was tightened.
LEVEL_WORDS = [
    (re.compile(r"\bOR[\s_-]?(?i:high)\b|(?i:\bopening\s+range\s+high\b)"), "or_high"),
    (re.compile(r"\bOR[\s_-]?(?i:low)\b|(?i:\bopening\s+range\s+low\b)"), "or_low"),
    # NOTE the trailing (?:s)? on every high/low: "yesterdays highs / lows" and
    # "premarket highs / lows" are how the key-levels indicator posts are
    # written, and a \b straight after "high" threw all four of them away.
    (re.compile(r"\b(pdh|prev(?:ious)?\s+day(?:'?s)?\s+highs?|"
                r"prior\s+day(?:'?s)?\s+highs?|yesterdays?'?\s+highs?)\b", re.I), "pdh"),
    (re.compile(r"\b(pdl|prev(?:ious)?\s+day(?:'?s)?\s+lows?|"
                r"prior\s+day(?:'?s)?\s+lows?|yesterdays?'?\s+lows?)\b", re.I), "pdl"),
    (re.compile(r"\b(pmh|pre[\s-]?market\s+highs?)\b", re.I), "pmh"),
    (re.compile(r"\b(pml|pre[\s-]?market\s+lows?)\b", re.I), "pml"),
    (re.compile(r"\b(hod|highs?\s+of\s+(?:the\s+)?day|"
                r"highs?\s*(?:&|and|/)\s*lows?\s+of\s+(?:the\s+)?day)\b", re.I), "hod"),
    (re.compile(r"\b(lod|lows?\s+of\s+(?:the\s+)?day|"
                r"highs?\s*(?:&|and|/)\s*lows?\s+of\s+(?:the\s+)?day)\b", re.I), "lod"),
]
# level vocabulary that is real but does not map onto one of the six day-trade
# levels -> level_name "other"
RE_LEVEL_OTHER = re.compile(
    r"\b(key\s+levels?|support|resistance|swing\s+high|swing\s+low|order\s+block|"
    r"round\s+number|psychological\s+level|liquidity\s+zone|previous\s+day\s+close|"
    r"\bpdc\b|\bath\b|all[\s-]time\s+high|market\s+structure|\bbos\b|\bmss\b|"
    r"\bchoch\b|trend\s*line|fibonacci|retracement|volume\s+profile)\b",
    re.I,
)

# Direction words are the single biggest false-positive source in a chat channel:
# "put my TP/SL chart", "long story short", "hop on a call", "short term".  Only
# the unambiguous forms count.
RE_LONG = re.compile(
    r"\b(?:longing|bullish|to\s+the\s+upside|calls\b|call\s+(?:option|contract|side)s?)\b"
    r"|\blong\b(?!\s+(?:story|term|run|time|way|enough|ago))"
    r"(?<!as\slong)(?<!how\slong)",
    re.I,
)
RE_SHORT = re.compile(
    r"\b(?:shorting|bearish|to\s+the\s+downside|puts\b|put\s+(?:option|contract|side)s?)\b"
    r"|\bshort\b(?!\s+(?:term|story|of|on|period))(?<!long\sstory\sshort)(?<!in\sshort)",
    re.I,
)

RE_EXIT = re.compile(
    r"\b(stop[\s-]?loss(?:es)?|\bsl\b|\bstp\b|stop\s+out|stopped\s+out|"
    r"take[\s-]?profit|\btp\b|profit\s+target|trailing\s+stop|scale\s+out|"
    r"break\s*even|\bpt\d?\b|ride\s+the\s+nine|trail)\b",
    re.I,
)
RE_RISK = re.compile(
    r"\b(risk[\s-]?(?:management|reward|per\s+trade|%|amount)|position\s+siz|"
    r"\brr\b|r[\s:/]+r\b|max\s+loss|1\s*%|delta|lot\s+size|contracts?|"
    r"account\s+size|\bpdt\b|drawdown|sizing)\b",
    re.I,
)
RE_INDICATOR = re.compile(
    r"\b(\d{1,3}\s*ema|ema\s*\d{1,3}|\bema\b|\bvwap\b|\bsma\b|moving\s+average|"
    r"\batr\b|9\s*ema\s*cloud|ema\s+cloud|relative\s+strength)\b",
    re.I,
)
RE_SESSION = re.compile(
    r"\b(pre[\s-]?market|premarket|market\s+open|9:2\d|9:3\d|10:\d\d|11\s*am|"
    r"first\s+bar|opening\s+candle|0dte|choppy\s+day|friday\s+rule|cut\s*off\s+trading)\b",
    re.I,
)
RE_PSYCH = re.compile(
    r"\b(discipline[d]?|patien(?:t|ce)|revenge|overtrading|over[\s-]trading|"
    r"emotion(?:s|al)?|journal(?:ing)?|mindset|greed|fear\b|base\s+hits|"
    r"losing\s+is\s+part|stick\s+to\s+your|consistency)\b",
    re.I,
)
# Timeframe / marking rules -- "mark your levels on the 15-min".  A bare
# "15 minute" needs charting context or it catches "a 15 minute data delay".
RE_TF_UNIT = re.compile(
    r"\b\d{1,3}\s*[-]?\s*min(?:ute)?s?\b|\b\d\s*[-]?\s*h(?:our|r)?\b|"
    r"\b(?:1m|5m|15m|30m|1h|4h|1d)\b|\bdaily\s+chart\b|\bweekly\s+chart\b",
    re.I,
)
RE_TF_CTX = re.compile(
    r"\b(mark(?:ing)?\b|levels?\b|zones?\b|chart(?:ing)?\b|scalp(?:ing)?\b|"
    r"candle\b|draw\b|opening\s+range\b|thesis\b|bias\b)",
    re.I,
)
RE_TF_EXPLICIT = re.compile(
    r"\btime\s*frames?\b|\bhtf\b|\bltf\b|higher\s+time|"
    r"\b(?:daily|weekly|market|directional)\s+(?:trading\s+)?bias\b",
    re.I,
)

# Chat about which button to click is not a trading rule.  When a message is
# written in UI vocabulary and its only substance is one weak tag, it is
# platform support, and it gets skipped rather than emitted as a rule.
RE_UI = re.compile(
    r"\b(click|button|icon|settings?|menu|\btab\b|watermark|download|install|"
    r"locked|drop\s*down|window|layout|screen|monitor|widget|wrench|toolbar|"
    r"sync|template|log\s*in|sign\s*in|right[\s-]click|redraw|pop[\s-]?up|"
    r"subscription|app\b)\b",
    re.I,
)
WEAK_ALONE = {"risk", "exit", "timeframe", "indicator"}

# A request for help is not an instruction, however many "always"es it contains.
RE_HELP_REQUEST = re.compile(
    r"\b(pl(?:s|ease)\s+help|help\s+me|can\s+anyone\s+(?:help|explain)|"
    r"how\s+(?:can|do)\s+i\b|i'?m\s+confused|any\s+help)\b",
    re.I,
)

# Order-mechanics substance: which order type, what offset, how a fill happens.
RE_EXEC = re.compile(
    r"\b(limit\s+orders?|market\s+orders?|order\s+type|stop\s+limit|stp\s+lmt|"
    r"conditional\s+order|bracket\s+order|trailing\s+stop|offset|slippage|"
    r"time[\s-]in[\s-]force|\bgtc\b)\b",
    re.I,
)

RE_DIRECTIVE = re.compile(
    r"\b(do\s+not|don'?t|never|always|make\s+sure|you\s+should|must\b|"
    r"be\s+sure|remember\s+to|avoid\b|place\s+(?:your\s+)?stops?|"
    r"use\s+\d|it'?s\s+best\s+to|recommend)\b",
    re.I,
)
# "I don't like a ton of lines", "I never found one", "I always used to" are
# personal statements, not instructions.  A first-person subject cancels them.
RE_FIRST_PERSON_DIRECTIVE = re.compile(
    r"\b(?:i|we|he|she|they|tony|jack|jdub|hayden)\s+(?:do\s+not|don'?t|never|always)\b",
    re.I,
)
RE_SENT_SPLIT = re.compile(r"[.!?\n;]+")

# pure-courtesy / pure-logistics detectors ------------------------------------
RE_COURTESY_ONLY = re.compile(
    r"^(?:(?:thanks?|thank\s+you|thx|ty|tks|cheers|welcome|you'?re\s+welcome|"
    r"no\s+problem|appreciate\s+(?:it|you|the\s+help)|following|awesome|nice|"
    r"great|super\s+useful|this\s+is\s+(?:fantastic|awesome)|love\s+this|"
    r"got\s+it|ok(?:ay)?|yes|no|hi|hello|hey|good\s+(?:morning|luck)|"
    r"glad\s+i\s+could\s+help|much\s+appreciated|my\s+friend|you\s+the\s+best|"
    r"congratulations|will\s+check\s+it\s+out|i'?ll\s+try\s+this)\W*)+$",
    re.I,
)
RE_ADMIN = re.compile(
    r"\b(whop|accelerator|module[s]?\b|subscription|lifetime|membership|"
    r"discount\s+code|affiliate|refer\s+friends|scammer|spam|dm'?s?\b|"
    r"privacy\s+settings|friend\s+request|watermark|zoom\s+link|"
    r"trading\s+floor|live\s+session|coaching|education\s+vault|"
    r"log\s+in|sign\s+in|password|billing|renewal|paper\s+account\s+setup)\b",
    re.I,
)

RE_R = re.compile(r"(?<![\w.])([+-]?\d{1,2}(?:\.\d{1,2})?)\s*R\b(?![\w:])")
RE_PNL = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(k\b)?", re.I)
RE_LOST = re.compile(r"\bi\s+lost\b|\blost\s+\$", re.I)
# "I made a breakthrough" is not a win.  A win needs money or a target.
RE_WON = re.compile(
    r"\bi\s+(?:made|profited)\s+\$|\bhit\s+(?:my\s+)?(?:pt\d?|target|profit\s+target)\b",
    re.I,
)

# tokens that look like tickers but never are, in this corpus
TICKER_STOP = {
    "AM", "PM", "ET", "EST", "EDT", "UTC", "OK", "THE", "AND", "FOR", "YOU",
    "ALL", "NEW", "PRE", "TV", "TOS", "IBKR", "TWS", "SL", "TP", "RR", "ATR",
    "EMA", "SMA", "VWAP", "ORB", "BNR", "BOS", "MSS", "OB", "HOD", "LOD",
    "PDH", "PDL", "PMH", "PML", "PDC", "ATH", "HTF", "LTF", "TSL", "PDT",
    "ITM", "OTM", "ATM", "DTE", "IV", "PNL", "CSV", "PDF", "HTML", "API",
    "USD", "US", "UK", "CEO", "FYI", "IMO", "LOL", "FAQ", "GAN", "FAN",
    "CHOCH", "MTF", "IB", "SPX", "DTE", "AI", "PC", "TVS",
}


CURLY = {"’": "'", "‘": "'", "“": '"', "”": '"',
         "–": "-", "—": "-", "＜": "<", "＞": ">"}


def clean(text: str) -> str:
    # Discord clients smart-quote as you type: "Previous Day's High" arrives
    # with U+2019, and a regex written with a straight apostrophe misses it.
    for a, b in CURLY.items():
        text = text.replace(a, b)
    t = RE_MENTION.sub(" ", text)
    t = RE_CHANNEL.sub(" ", t)
    t = RE_EMOJI_TAG.sub(" ", t)
    t = RE_URL.sub(" ", t)
    t = t.replace("@everyone", " ").replace("@here", " ")
    return re.sub(r"\s+", " ", t).strip()


RE_EXAMPLE = re.compile(r"\b(for\s+example|e\.?g\.?|such\s+as|for\s+instance)\b", re.I)


def parse_symbol(text: str):
    """Only a ticker that is literally written, in caps, and in universe.py.

    A ticker used as a worked example -- "type the ticker of the underlying
    (TSLA for example)" -- is not the symbol of a trade, so an example marker
    immediately after the token (20 chars) or immediately before it (12 chars,
    for "e.g. TSLA") disqualifies it.  The before-window is deliberately short:
    "For example today I entered AMZN" IS a real fill, and a 30-char window
    swallowed it.
    """
    for m in RE_TICKER_CAND.finditer(text):
        tok = m.group(0)
        if tok in TICKER_STOP or tok not in KNOWN:
            continue
        if RE_EXAMPLE.search(text[max(0, m.start() - 12): m.start()]):
            continue
        if RE_EXAMPLE.search(text[m.end(): m.end() + 20]):
            continue
        return tok
    return None


def parse_level_names(text: str):
    """Every named level in the message, in the canonical order. A key-levels
    indicator post names four at once; keeping only the first would throw three
    away, so level_name carries the first and level_names carries all."""
    found = [name for rx, name in LEVEL_WORDS if rx.search(text)]
    if not found and RE_LEVEL_OTHER.search(text):
        found = ["other"]
    return found


def parse_level_name(text: str):
    names = parse_level_names(text)
    return names[0] if names else None


def parse_setup(text: str):
    """Returns (setup, setup_raw). setup_raw names which 'other' setup matched."""
    br, ocr = bool(RE_SETUP_BR.search(text)), bool(RE_SETUP_OCR.search(text))
    if br and ocr:
        return "br_ocr", None
    if br:
        return "break_retest", None
    if ocr:
        return "one_candle", None
    hits = [k for k, rx in RE_SETUP_OTHER.items() if rx.search(text)]
    if hits:
        return "other", ",".join(sorted(hits))
    return None, None


def parse_direction(text: str, anchored: bool):
    """Direction is only meaningful when the message is about a trade or a
    level.  Un-anchored 'the market is bearish' chatter returns null."""
    if not anchored:
        return None
    lo, sh = bool(RE_LONG.search(text)), bool(RE_SHORT.search(text))
    if lo and not sh:
        return "long"
    if sh and not lo:
        return "short"
    return None


def price_after(text: str, anchor_rx):
    m = anchor_rx.search(text)
    if not m:
        return None
    tail = text[m.end(): m.end() + 20]
    n = re.search(r"(\d{1,6}(?:\.\d{1,4})?)", tail)
    return float(n.group(1)) if n else None


RE_ENTRY_A = re.compile(r"\b(entry|entered|enter)\b\s*(?:at|@|:|-)?\s*\$?", re.I)
RE_STOP_A = re.compile(r"\b(stop\s*loss|stop|sl)\b\s*(?:at|@|:|-)?\s*\$?", re.I)
RE_TARGET_A = re.compile(r"\b(target|pt\d?|tp\d?|take\s*profit)\b\s*(?:at|@|:|-)?\s*\$?", re.I)


def usd_amounts(text: str):
    """Every dollar figure literally written. In this channel these are risk
    budgets, account minimums and contract premiums -- almost never P&L -- so
    they are reported raw and pnl_usd is filled only alongside an outcome."""
    out = []
    for m in RE_PNL.finditer(text):
        val = float(m.group(1).replace(",", ""))
        if m.group(2):
            val *= 1000.0
        out.append(val)
    return out


def parse_pnl_usd(text: str, outcome):
    """A dollar figure is P&L only when it sits in the same clause as the
    result verb that set the outcome."""
    if outcome is None:
        return None
    rx = RE_LOST if outcome == "loss" else RE_WON
    m = rx.search(text)
    if not m:
        return None
    clause = text[m.start(): m.start() + 60]
    n = RE_PNL.search(clause)
    if not n:
        return None
    val = float(n.group(1).replace(",", ""))
    if n.group(2):
        val *= 1000.0
    return -val if outcome == "loss" else val


def is_directive(text: str) -> bool:
    """True only for a sentence that instructs AND carries trading vocabulary.

    Without the sentence scope, "I have wished for X but never found one" and
    "I don't like a ton of lines on my chart" both read as rules.  Without the
    first-person cancel, "I don't really have the sizing issues you described"
    reads as a sizing rule.
    """
    if RE_HELP_REQUEST.search(text):
        return False
    for sent in RE_SENT_SPLIT.split(text):
        if not RE_DIRECTIVE.search(sent):
            continue
        if RE_FIRST_PERSON_DIRECTIVE.search(sent):
            continue
        if (RE_EXIT.search(sent) or RE_RISK.search(sent) or RE_SETUP_BR.search(sent)
                or RE_SETUP_OCR.search(sent) or parse_level_name(sent)
                or RE_EXEC.search(sent) or RE_PSYCH.search(sent)):
            return True
    return False


def parse_outcome(text: str, symbol):
    """Outcome only when a first-person result verb sits with a named symbol.
    'Losing is part of profitability' is a maxim, not a loss."""
    if not symbol:
        return None
    if RE_LOST.search(text):
        return "loss"
    if RE_WON.search(text):
        return "win"
    return None


def parse_r_multiple(text: str, anchored: bool):
    if not anchored:
        return None
    m = RE_R.search(text)
    return float(m.group(1)) if m else None


def substance(text: str):
    """Which trading-substance categories this message hits."""
    tags = []
    if RE_SETUP_BR.search(text) or RE_SETUP_OCR.search(text):
        tags.append("setup")
    else:
        for k, rx in RE_SETUP_OTHER.items():
            if rx.search(text):
                tags.append("setup")
                break
    if parse_level_name(text):
        tags.append("level")
    if RE_EXIT.search(text):
        tags.append("exit")
    if RE_RISK.search(text):
        tags.append("risk")
    if RE_INDICATOR.search(text):
        tags.append("indicator")
    if RE_SESSION.search(text):
        tags.append("session")
    if RE_PSYCH.search(text):
        tags.append("psychology")
    if RE_EXEC.search(text):
        tags.append("execution")
    if RE_TF_EXPLICIT.search(text) or (RE_TF_UNIT.search(text) and RE_TF_CTX.search(text)):
        tags.append("timeframe")
    return sorted(set(tags))


def classify_kind(tags, directive: bool):
    """One label, most-specific-wins, off the substance tags actually present."""
    if "setup" in tags or "level" in tags or "timeframe" in tags:
        return "setup_rule" if directive else "setup_note"
    if "exit" in tags or "risk" in tags:
        return "risk_rule" if directive else "risk_note"
    if "execution" in tags:
        return "execution_rule" if directive else "execution_note"
    if "indicator" in tags:
        return "tooling"
    if "session" in tags:
        return "session_note"
    if "psychology" in tags:
        return "psychology"
    if "resource" in tags:
        return "resource"
    return "other"


def confidence_for(tags, directive: bool, question: bool):
    if question:
        return "low"
    if len(tags) >= 3 and directive:
        return "high"
    if len(tags) >= 2 or directive:
        return "medium"
    return "low"


BOOK_TITLE = re.compile(r"/([A-Za-z0-9_\-%.]+)\.(pdf|epub)\b", re.I)


def doc_titles(attachments):
    out = []
    for a in attachments:
        m = BOOK_TITLE.search(a.split("?")[0])
        if m:
            t = re.sub(r"[_\-]+", " ", m.group(1)).strip()
            t = re.sub(r"\s+\d+(\s+\d+)*$", "", t)
            out.append(t)
    return out


def main():
    rows, skipped = [], []
    for fname in SRCS:
        path = os.path.join(REPO, "discord_data", fname)
        with open(path, encoding="utf-8") as fh:
            msgs = json.load(fh)

        for m in msgs:
            raw = m.get("content") or ""
            txt = clean(raw)
            ts_utc = datetime.fromisoformat(m["ts"]).replace(tzinfo=timezone.utc)
            ts = ts_utc.astimezone(ET)
            atts = m.get("attachments") or []
            imgs = [a for a in atts if a.split("?")[0].lower().endswith(IMG_EXT)]
            files = [a for a in atts if a not in imgs]
            base_skip = {
                "src": fname, "msg_id": m["id"], "ts": ts.isoformat(),
                "author": m.get("author"), "quote": raw,
            }

            docs = doc_titles(atts)
            if len(txt) < MIN_CHARS and not docs:
                base_skip["skip_reason"] = "no_text" if not txt else "too_short"
                skipped.append(base_skip)
                continue
            if RE_COURTESY_ONLY.match(txt):
                base_skip["skip_reason"] = "courtesy_only"
                skipped.append(base_skip)
                continue

            tags = substance(txt)
            # books.json is two messages whose whole payload is the attached
            # PDFs ("Book I Have Read & Recommend To Read:").  The caption
            # carries no trading vocabulary, so without this the reading list
            # is dropped on the floor.
            if docs:
                tags = sorted(set(tags + ["resource"]))
            if not tags:
                base_skip["skip_reason"] = "no_trading_substance"
                skipped.append(base_skip)
                continue
            if RE_ADMIN.search(txt) and tags == ["session"]:
                # "trading floor"/"live session" logistics with nothing else
                base_skip["skip_reason"] = "admin_logistics"
                skipped.append(base_skip)
                continue
            if (len(tags) == 1 and tags[0] in WEAK_ALONE
                    and RE_UI.search(txt) and not is_directive(txt)):
                base_skip["skip_reason"] = "platform_ui"
                skipped.append(base_skip)
                continue

            symbol = parse_symbol(txt)
            setup, setup_raw = parse_setup(txt)
            level_names = parse_level_names(txt)
            level_name = level_names[0] if level_names else None
            anchored = bool(symbol) and bool(setup or level_name)
            directive = is_directive(txt)

            level_price = entry = stop = target = None
            if anchored:  # PRICE GATE -- see module docstring
                level_price = price_after(txt, LEVEL_WORDS[0][0]) if level_name else None
                entry = price_after(txt, RE_ENTRY_A)
                stop = price_after(txt, RE_STOP_A)
                target = price_after(txt, RE_TARGET_A)

            # "?" from a URL query string (?si=, ?usp=) is not a question --
            # ask the cleaned text, which has the URLs stripped out.
            is_question = "?" in txt
            outcome = parse_outcome(txt, symbol)
            rows.append({
                "src": fname,
                "msg_id": m["id"],
                "ts": ts.isoformat(),
                "author": m.get("author"),
                "symbol": symbol,
                "direction": parse_direction(txt, bool(symbol) or bool(setup) or bool(level_name)),
                "setup": setup,
                "level_price": level_price,
                "level_name": level_name,
                "entry": entry,
                "stop": stop,
                "target": target,
                "outcome": outcome,
                "r_multiple": parse_r_multiple(txt, anchored),
                "quote": raw,
                "image_urls": imgs,
                "confidence": confidence_for(tags, directive, is_question),
                # ---- extra fields (peer parsers in corpus_sf do the same) ----
                "kind": classify_kind(tags, directive),
                "topic_tags": tags,
                "level_names": level_names,
                "setup_raw": setup_raw,
                "is_question": is_question,
                "is_directive": directive,
                "pnl_usd": parse_pnl_usd(txt, outcome),
                "usd_amounts": usd_amounts(txt),
                "file_urls": files,
                "link_urls": RE_URL.findall(raw),
                "doc_titles": docs,
                "reply_to": m.get("reply_to"),
            })

    rows.sort(key=lambda r: (r["ts"], r["msg_id"]))
    with open(OUT, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_SKIP, "w", encoding="utf-8") as fh:
        for r in skipped:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("extracted %d  skipped %d  total %d" % (len(rows), len(skipped), len(rows) + len(skipped)))
    from collections import Counter
    print("kind:", Counter(r["kind"] for r in rows).most_common())
    print("skip_reason:", Counter(r["skip_reason"] for r in skipped).most_common())


if __name__ == "__main__":
    main()
