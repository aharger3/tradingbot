"""Deterministic parser for discord_data/scarface-alerts.json.

Scarface (author "TonyMontana") posts real-time entries, level calls and
outcomes in #scarface-alerts. This turns those messages into structured rows.

NOT Austin's marks. Output lives only under research/corpus_sf/.

Rules of the road:
  * regex + heuristics only, no model in the loop
  * never invent a value: a field the message does not state stays null
  * `quote` is the verbatim message content
  * timestamps in the export are naive UTC; we emit ISO8601 America/New_York

Usage:
    python research/corpus_sf/parse_scarface_alerts.py \
        [--src discord_data/scarface-alerts.json] \
        [--out research/corpus_sf/scarface_alerts.jsonl]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = timezone.utc

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SRC = os.path.join(REPO, "discord_data", "scarface-alerts.json")
DEFAULT_OUT = os.path.join(REPO, "research", "corpus_sf", "scarface_alerts.jsonl")

sys.path.insert(0, REPO)
from universe import ALL_SYMS  # noqa: E402
from chat_vocab import SCARFACE_EXTRA_SYMS as EXTRA_SYMS  # noqa: E402

# ---------------------------------------------------------------------------
# symbols
# ---------------------------------------------------------------------------
# Whitelist, not "any uppercase token" -- the channel is written in prose and a
# bare-token heuristic pulls in TO/FOR/THE/NOW/ONE.  Base list is universe.py;
# the extras are tickers that actually appear in this channel and are not in the
# engine universe.  Ambiguous English words that are also real tickers (NOW, U,
# V, AI, SHOP, COST, ARM) are deliberately excluded.
SYM_ALIAS = {"APPL": "AAPL", "TSLAA": "TSLA", "GOOGLE": "GOOGL", "QQQQ": "QQQ",
             "NVIDIA": "NVDA", "APPLE": "AAPL", "TESLA": "TSLA"}
SYMBOLS = set(ALL_SYMS) | set(EXTRA_SYMS)
_SYM_ORDER = sorted(SYMBOLS | set(SYM_ALIAS), key=len, reverse=True)
SYM_RE = re.compile(r"\b(" + "|".join(_SYM_ORDER) + r")\b", re.I)

# ---------------------------------------------------------------------------
# levels
# ---------------------------------------------------------------------------
NAMED_LEVELS = ("pdh", "pdl", "pmh", "pml", "hod", "lod", "or_high")

LEVEL_PATTERNS = [
    ("pdh", r"\bPDH\b|\bprev(?:ious)?\s+day(?:'?s)?\s+highs?\b"
            r"|\bprior\s+day(?:'?s)?\s+highs?\b|\byesterday(?:'?s)?\s+highs?\b"),
    ("pdl", r"\bPDL\b|\bprev(?:ious)?\s+day(?:'?s)?\s+lows?\b"
            r"|\bprior\s+day(?:'?s)?\s+lows?\b|\byesterday(?:'?s)?\s+lows?\b"),
    ("pmh", r"\bPMH\b|\bpre[\s-]?market\s+highs?\b|\bPM\s+highs?\b"),
    ("pml", r"\bPML\b|\bpre[\s-]?market\s+lows?\b|\bPM\s+lows?\b"),
    ("hod", r"\bHOD\b|\bhighs?\s+of\s+(?:the\s+)?day\b"),
    ("lod", r"\bLOD\b|\blows?\s+of\s+(?:the\s+)?day\b"),
    # the schema has or_high but no or_low; an opening-range low lands in "other"
    ("or_high", r"\b(?:OR|opening\s+range|ORB|[15]\s*min(?:ute)?s?)"
                r"(?:\s+range)?\s+highs?\b"
                r"|\bopening\s+range\s+break\s+(?:above|up)\b"),
    ("other", r"\b(?:OR|opening\s+range|ORB|[15]\s*min(?:ute)?s?)"
              r"(?:\s+range)?\s+lows?\b"
              r"|\bkey\s+levels?\b|\bPDC\b|\bgap\s+fill\b|\bdaily\s+levels?\b"
              r"|\ball[\s-]time\s+highs?|\bATH\b|\bthis\s+levels?\b"
              r"|\bthat\s+levels?\b|\bnext\s+levels?\b|\bthese\s+levels?\b"
              r"|\b[15]\s*min(?:ute)?s?\s+(?:range|level)\b"
              r"|\bpivot\s+(?:high|low)\b|\bhtf\s+levels?\b|\bthe\s+[15]\s*min\b"),
]
LEVEL_RE = [(name, re.compile(pat, re.I)) for name, pat in LEVEL_PATTERNS]

# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------
RETEST_RE = re.compile(r"\bre[\s-]?test(?:s|ed|ing)?\b|\bb\s*&\s*r\b"
                       r"|\bbreak\s+(?:and|&)\s+re[\s-]?test\b", re.I)
OCR_RE = re.compile(r"\bone\s*-?\s*candle(?:\s+rule)?\b|\b1\s+candle(?:\s+rule)?\b"
                    r"|\bOCR\b|\bcandle\s+rule\b", re.I)
OTHER_SETUP_RE = re.compile(
    r"\breclaim(?:s|ed|ing)?\b|\bbreak(?:s|ing)?\s+(?:above|below|of|out|down)\b"
    r"|\bbreakout\b|\bbreakdown\b|\bkey\s+levels?\b|\bopening\s+range\b|\bORB\b"
    r"|\bflag\b|\bdowntrend\b|\buptrend\b|\bconsolidat|\b84\s*%"
    r"|\bOB\b", re.I)  # OB = order block, Scarface's term

# ---------------------------------------------------------------------------
# direction
# ---------------------------------------------------------------------------
# "call it a week", "call out" are not option contracts -- that false positive
# put a long on a Friday sign-off message.
CALLS_RE = re.compile(r"\bcalls?\b(?!\s+(?:it|out|this|that|the)\b)"
                      r"|\bcals\b", re.I)
PUTS_RE = re.compile(r"\bputs?\b(?!\s+(?:us|me|you|it|him|her|them)\b)", re.I)
# "as long as we break PM high" is not a long -- exclude that idiom
LONG_STRONG = re.compile(r"(?<!as\s)\blong(?:s|ing)?\b|\bto\s+the\s+upside\b"
                         r"|\bbreak\s+above\b.{0,25}\bfor\s+entry\b"
                         r"|\bneeds?\s+(?:a\s+|to\s+)?break\s+above\b", re.I)
SHORT_STRONG = re.compile(r"\bshort(?:s|ing)?\b|\bto\s+the\s+downside\b"
                          r"|\bbreak\s+below\b.{0,25}\bfor\s+entry\b"
                          r"|\bneeds?\s+(?:a\s+|to\s+)?break\s+below\b", re.I)
LONG_WEAK = re.compile(r"\b(?:for|target(?:ing|s)?)\s+(?:the\s+)?HOD\b"
                       r"|\bHOD\s+(?:is\s+)?(?:my\s+|the\s+)?(?:first\s+)?target\b"
                       r"|\blooking\s+for\s+(?:new\s+)?highs?\b"
                       r"|\bbuyers?\s+(?:step|stepp|stepped|coming|are\s+in)"
                       r"|\b(?:big|strong|aggressive|nice)\s+buyers?\b"
                       r"|\bpush\s+(?:in)?to\s+(?:the\s+)?highs?\b"
                       r"|\bnew\s+highs?\b|\bupside\b|\bbounc(?:e|ed|ing)\b", re.I)
SHORT_WEAK = re.compile(r"\b(?:for|target(?:ing|s)?)\s+(?:the\s+)?LOD\b"
                        r"|\bLOD\s+(?:is\s+)?(?:my\s+|the\s+)?(?:first\s+)?target\b"
                        r"|\blooking\s+for\s+(?:new\s+)?lows?\b"
                        r"|\bsellers?\s+(?:step|stepp|stepped|coming|are\s+in)"
                        r"|\b(?:big|strong|aggressive)\s+sellers?\b"
                        r"|\bpush\s+(?:in)?to\s+(?:the\s+)?lows?\b"
                        r"|\bnew\s+lows?\b|\bdownside\b|\breject(?:ion|ed|ing|s)?\b"
                        r"|\bmove\s+down\b|\bbreakdown\b", re.I)

# ---------------------------------------------------------------------------
# outcome
# ---------------------------------------------------------------------------
BE_RE = re.compile(r"\bbreak\s*-?\s*even\b|\bbreakeven\b|\bB\.?E\.?\s+stop\b"
                   r"|\bstop\s+to\s+BE\b|\bmoved?\s+(?:my\s+)?stop\s+to\s+break"
                   r"|\bmoved?\s+(?:to|at)\s+BE\b|\bcut\s+.{0,20}breakeven", re.I)
LOSS_RE = re.compile(r"\bstopped\b|\bstop(?:ped)?\s+out\b|\bstop\s+out\b"
                     r"|\btook\s+(?:a|the)\s+loss\b|\bcut\s+(?:the\s+)?rest\b"
                     r"|\bfull\s+stop\b|\bwas\s+a\s+loss\b"
                     r"|\bended\s+up\s+being\s+a\s+loss\b"
                     r"|\b(?:a|1|one)\s+loss\b|\bloser\b|\bred\s+day\b"
                     r"|\blost\s+(?:my\s+|the\s+|first\s+|this\s+|that\s+)*"
                     r"\w{0,6}\s*trade\b"
                     # "PLTR loss | TSLA nice trade" -- a per-name verdict
                     r"|\b(?:" + "|".join(sorted(SYMBOLS)) + r")\s+loss(?:es)?\b",
                     re.I)
# "if we don't hold will stop out the rest" is a plan, not a result
CONDITIONAL_HEAD = re.compile(r"(?:\bif\b|\bunless\b|\bwill\b|\bwould\b|\bgonna\b"
                              r"|\bgoing\s+to\b|\bmay\b|\bmight\b|'ll|\bll\b)"
                              r"[^.!?]{0,40}$", re.I)
WIN_RE = re.compile(r"\b(?:took|taking|take)\s+(?:some|profit|partial)s?"
                    r"(?:\s+more)?\s+off\b"
                    r"|\bscaled?\s+(?:out|off|some|\d)"
                    r"|\btook\s+\d{1,3}\s*%\s*off\b|\bout\s+full\b"
                    r"|\bout\s+(?:of\s+)?full\s+position\b|\bsold\b"
                    r"|\bin\s+profit\b|\blocked?\s+in\s+profit"
                    r"|\b(?:nice|solid|great|good|clean)\s+trade\b"
                    r"|\bworked\s+out\b|\bwinner\b|\btook\s+profits?\b"
                    r"|\bhit\s+(?:my\s+)?(?:target|pt|first\s+scale)\b"
                    r"|\b(?:HOD|LOD)\s+scale\b|\bscales?\s+(?:now|here|there)\b"
                    r"|\btook\s+(?:my\s+|a\s+)?(?:first\s+|small\s+)?"
                    r"(?:scales?|partials?)\b"
                    r"|\bfinal\s+pt\s+hit\b|\brisk\s+free\b"
                    r"|\$[\d,]+(?:\.\d+)?\s*k?\s*(?:day|profit)\b"
                    r"|\$[\d,]+(?:\.\d+)?\s*k?\s+\w{0,6}\s*trade\b"
                    r"|\b(?:solid|good|great|green|nice|big|profitable)\s+day\b", re.I)

# ---------------------------------------------------------------------------
# prices
# ---------------------------------------------------------------------------
P = r"(\d{1,4}(?:\.\d{1,2})?)"
MONTHS = (r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february"
          r"|march|april|june|july|august|september|october|november|december")

STOP_PATS = [
    re.compile(r"stop(?:\s*loss)?\s*(?:is)?\s*(?:the\s*)?(?:a\s*)?(?:break\s*)?"
               r"(?:of\s*)?(?:the\s*)?(?:candle\s*)?(?:close\s*)?(?:break\s*)?"
               r"(?:below|above|under|over|at|@|:|of)\s*(?:the\s*)?(?:entry\s*)?"
               r"\$?" + P, re.I),
    re.compile(r"\bSL\s*(?:below|above|under|over|at|@|:|is)?\s*\$?" + P, re.I),
    re.compile(r"\brisk\s*(?:is\s*)?(?:below|above|under|over|to|at|@|:)\s*\$?"
               + P, re.I),
    re.compile(r"\bstopped?\s*(?:at|@)\s*\$?" + P, re.I),
    re.compile(r"\bcut(?:ting)?\s*(?:below|above)\s*\$?" + P, re.I),
    re.compile(P + r"\s*(?:is\s+(?:my\s+|the\s+)?)?(?:SL|stop)\b", re.I),
    re.compile(r"\bstop\s+(?:on\s+\w{1,5}\s+)?\$?" + P + r"\b", re.I),
]
TARGET_PATS = [
    # the optional ordinal digit needs \b or "pt 190.71" reads as target 90.71
    re.compile(r"\b(?:profit\s+)?targets?\s*(?:\d\b)?\s*(?:is|are|at|@|:)?\s*\$?"
               + P, re.I),
    re.compile(r"\b(?:first\s+|final\s+|next\s+|1st\s+|2nd\s+)?PT\s*(?:\d\b)?\s*"
               r"(?:is|at|@|:)?\s*\$?" + P, re.I),
    re.compile(r"\btaking\s+profits?\s+(?:at|@)\s*\$?" + P, re.I),
    re.compile(P + r"\s+(?:is|was)\s+(?:the\s+)?(?:next\s+|first\s+|final\s+)?"
               r"targets?\b", re.I),
]
ENTRY_PATS = [
    re.compile(r"\bentry\s*(?:is|was|at|@|:|price)?\s*\$?" + P, re.I),
    re.compile(r"\bentered?\s*(?:at|@|:)\s*\$?" + P, re.I),
    re.compile(r"\b(?:got\s+)?in\s*(?:at|@)\s*\$?" + P, re.I),
    re.compile(r"\bfilled\s*(?:at|@|:)?\s*\$?" + P, re.I),
]
# A price tied to a level Scarface names (PDH/HOD/...).
NAMED_LEVEL_PRICE_PATS = [
    re.compile(r"\b(?:PDH|PDL|PMH|PML|HOD|LOD|PDC)\s*(?:is|at|@|of|:|=)?\s*\$?"
               + P, re.I),
    re.compile(P + r"\s*(?:is\s*(?:the\s*)?)?(?:PDH|PDL|PMH|PML|HOD|LOD|PDC)\b",
               re.I),
]
# A price tied to a generic "level" / "hold above X".  Tracked separately so
# level_name is never pinned to a price that belongs to a different level.
GENERIC_LEVEL_PRICE_PATS = [
    re.compile(r"\b(?:next\s+|key\s+|new\s+)*levels?\s+(?:is|at|@|of|:|=)?\s*"
               r"(?:for\s+\w+\s+)?\$?" + P, re.I),
    re.compile(P + r"\s+(?:which\s+)?(?:is|was)\s+(?:the\s+)?"
               r"(?:next\s+|key\s+)*levels?\b", re.I),
    re.compile(P + r"\s+(?:the\s+)?(?:next\s+|key\s+)+levels?\b", re.I),
    re.compile(r"\b(?:hold|holds|holding|reclaim|reclaims|above|below)\s+\$?"
               + P + r"\b", re.I),
]

# things that look like a price but are not one
BAD_PRICE_AFTER = re.compile(
    r"^\s*(?:%|k\b|min\b|minute|hour|hr\b|am\b|pm\b|est\b|et\b|cons?\b"
    r"|contracts?\b|c\b|p\b|calls?\b|puts?\b|exp\b|dte\b|r\b|:\d\d"
    r"|st\b|nd\b|rd\b|th\b|weeks?\b|days?\b|shares?\b)", re.I)
BAD_PRICE_BEFORE = re.compile(r"(?:" + MONTHS + r"|\$|\btop\s|\blast\s)\s*$", re.I)
STRIKE_AFTER = re.compile(r"^\s*(?:c\b|p\b|calls?\b|puts?\b)", re.I)

R_MULT_RE = re.compile(r"\b(\d{1,2}(?:\.\d{1,2})?)\s*R\b(?!\w)")

# promo / education / housekeeping with no trade content
NOISE_RE = re.compile(
    r"youtu\.?be|youtube\.com|discord\.gg|subscribe|testimonial|giveaway"
    r"|good\s+morning\s+guys|welcome\s+to|reminder\s+as\s+always", re.I)


def _clean(text: str) -> str:
    """Strip discord mention/channel markup for matching (quote stays raw)."""
    t = re.sub(r"<[@#!&:][^>]*>", " ", text)
    t = t.replace("@everyone", " ").replace("@here", " ")
    t = t.replace("’", "'").replace("‘", "'")
    t = t.replace("“", '"').replace("”", '"')
    return t


def _num_ok(text: str, m: re.Match) -> bool:
    val = float(m.group(1))
    if not (0.5 <= val <= 5000):
        return False
    tail = text[m.end(1):m.end(1) + 12]
    head = text[max(0, m.start(1) - 14):m.start(1)]
    if BAD_PRICE_AFTER.match(tail):
        return False
    if BAD_PRICE_BEFORE.search(head):
        return False
    return True


def _first_price(text, pats, reject_strike=True):
    best = None
    for pat in pats:
        for m in pat.finditer(text):
            if not _num_ok(text, m):
                continue
            if reject_strike and STRIKE_AFTER.match(text[m.end(1):m.end(1) + 8]):
                continue
            if best is None or m.start() < best[0]:
                best = (m.start(), float(m.group(1)))
    return None if best is None else best[1]


def find_symbols(text: str):
    out = []
    for m in SYM_RE.finditer(text):
        s = SYM_ALIAS.get(m.group(1).upper(), m.group(1).upper())
        if s not in out:
            out.append(s)
    return out


def find_level(text: str):
    hits = []
    for name, rx in LEVEL_RE:
        m = rx.search(text)
        if m:
            hits.append((m.start(), name))
    if not hits:
        return None
    hits.sort()
    named = [h for h in hits if h[1] != "other"]
    return (named or hits)[0][1]


def find_setup(text: str):
    r = bool(RETEST_RE.search(text))
    o = bool(OCR_RE.search(text))
    if r and o:
        return "br_ocr"
    if r:
        return "break_retest"
    if o:
        return "one_candle"
    if OTHER_SETUP_RE.search(text):
        return "other"
    return None


def find_direction(text: str):
    """-> (direction, strength) with strength in {"strong", "weak", None}."""
    c, p = bool(CALLS_RE.search(text)), bool(PUTS_RE.search(text))
    if c and not p:
        return "long", "strong"
    if p and not c:
        return "short", "strong"
    if c and p:
        return None, None  # "for PUTS: X / for CALLS: Y" -- genuinely both
    ls, ss = bool(LONG_STRONG.search(text)), bool(SHORT_STRONG.search(text))
    if ls and not ss:
        return "long", "strong"
    if ss and not ls:
        return "short", "strong"
    lw, sw = bool(LONG_WEAK.search(text)), bool(SHORT_WEAK.search(text))
    if lw and not sw:
        return "long", "weak"
    if sw and not lw:
        return "short", "weak"
    return None, None


def _real_hit(rx, text):
    """First match of rx that is not inside a conditional / future clause."""
    for m in rx.finditer(text):
        head = text[max(0, m.start() - 45):m.start()]
        if CONDITIONAL_HEAD.search(head):
            continue
        return m
    return None


def find_outcome(text: str):
    if _real_hit(BE_RE, text):
        return "be"
    if _real_hit(LOSS_RE, text):
        # "took some off ... then stopped the rest" -- the position ended stopped
        return "loss"
    if _real_hit(WIN_RE, text):
        return "win"
    return None


def image_urls(msg) -> list:
    urls = []
    for u in msg.get("attachments") or []:
        if isinstance(u, str):
            urls.append(u)
    for u in msg.get("embeds") or []:
        if isinstance(u, str) and re.search(r"\.(png|jpe?g|gif|webp)(\?|$)", u, re.I):
            urls.append(u)
    return urls


def parse(messages):
    by_id = {m["id"]: m for m in messages}
    rows = []
    last_sym = None
    last_sym_dt = None

    for msg in messages:
        raw = msg.get("content") or ""
        text = _clean(raw)
        dt_et = datetime.fromisoformat(msg["ts"]).replace(tzinfo=UTC).astimezone(ET)

        syms = find_symbols(text)
        setup = find_setup(text)
        level_name = find_level(text)
        direction, dstrength = find_direction(text)
        outcome = find_outcome(text)

        stop = _first_price(text, STOP_PATS, reject_strike=False)
        target = _first_price(text, TARGET_PATS)
        entry = _first_price(text, ENTRY_PATS)
        lp_named = _first_price(text, NAMED_LEVEL_PRICE_PATS)
        lp_generic = _first_price(text, GENERIC_LEVEL_PRICE_PATS)
        level_price = lp_named if lp_named is not None else lp_generic
        # one price fills one role; stop/target/entry outrank level_price
        for claimed in (stop, target, entry):
            if claimed is not None and level_price == claimed:
                level_price = None
                break
        if (level_price is not None and lp_named is None
                and level_name in NAMED_LEVELS):
            # the price belongs to a generic "level", not to the named level the
            # message also mentions -- do not pin the two together
            level_name = "other"

        rm = R_MULT_RE.search(text)
        r_multiple = float(rm.group(1)) if rm else None

        sym = syms[0] if syms else None
        sym_inferred = False
        if sym is None:
            parent = by_id.get(msg.get("reply_to") or "")
            if parent:
                psyms = find_symbols(_clean(parent.get("content") or ""))
                if psyms:
                    sym, sym_inferred = psyms[0], True
            # Rolling context only for messages that read as an update to a
            # live position ("STOPPED ON REST", "took my first scales now").
            # Applying it to generic market commentary attributed whole-market
            # talk to whatever ticker happened to be mentioned last.
            position_update = outcome is not None or any(
                v is not None for v in (entry, stop, target, level_price))
            if sym is None and last_sym is not None and position_update:
                gap = (dt_et - last_sym_dt).total_seconds()
                if 0 <= gap <= 45 * 60 and dt_et.date() == last_sym_dt.date():
                    sym, sym_inferred = last_sym, True
        if syms:
            last_sym, last_sym_dt = syms[0], dt_et

        signal = any(v is not None for v in
                     (setup, level_name, direction, stop, target, entry,
                      level_price, outcome))
        if sym is None or not signal:
            continue
        # Promo/greeting text only kills a message that carries nothing else --
        # "Good Morning Guys! ... main watch is NVDA PDH retest" is a gameplan.
        if (NOISE_RE.search(text) and outcome is None and stop is None
                and entry is None and setup is None and level_name is None):
            continue

        if sym_inferred:
            conf = "medium" if msg.get("reply_to") else "low"
        elif (outcome or stop is not None or entry is not None
              or (dstrength == "strong" and (setup or level_name))):
            conf = "high"
        elif dstrength == "weak" and setup is None and level_name is None:
            conf = "low"
        else:
            conf = "medium"

        rows.append({
            "src": "discord_data/scarface-alerts.json",
            "msg_id": msg["id"],
            "ts": dt_et.isoformat(),
            "author": msg.get("author"),
            "symbol": sym,
            "direction": direction,
            "setup": setup,
            "level_price": level_price,
            "level_name": level_name,
            "entry": entry,
            "stop": stop,
            "target": target,
            "outcome": outcome,
            "r_multiple": r_multiple,
            "quote": raw,
            "image_urls": image_urls(msg),
            "confidence": conf,
            "_dt": dt_et,
            "_threaded": False,
        })

    n_threaded = thread_outcomes(rows)
    for r in rows:
        r.pop("_dt", None)
        r.pop("_threaded", None)
    return rows, n_threaded


def thread_outcomes(rows):
    """Carry a later outcome back onto the alert row that opened the position.

    Conservative on purpose: same symbol, same ET calendar day, the alert must
    look like a position (a direction plus an entry/stop price, a setup or a
    level), and the first unclaimed outcome row after it wins.  Nothing crosses
    a day boundary and an alert that states its own outcome is untouched.
    """
    n = 0
    for i, r in enumerate(rows):
        if r["outcome"] is not None or r["direction"] is None:
            continue
        if not (r["entry"] is not None or r["stop"] is not None
                or r["setup"] is not None or r["level_name"] is not None):
            continue
        for j in range(i + 1, len(rows)):
            o = rows[j]
            if o["_dt"].date() != r["_dt"].date():
                break
            if o["symbol"] != r["symbol"] or o["outcome"] is None or o["_threaded"]:
                continue
            r["outcome"] = o["outcome"]
            if r["r_multiple"] is None and o["r_multiple"] is not None:
                r["r_multiple"] = o["r_multiple"]
            if r["confidence"] == "high":
                r["confidence"] = "medium"
            r["_threaded"] = True
            n += 1
            break
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args()

    msgs = json.load(open(a.src, encoding="utf-8"))
    rows, n_threaded = parse(msgs)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def n(k):
        return sum(1 for r in rows if r.get(k) is not None)

    print("messages       %d" % len(msgs))
    print("extracted      %d" % len(rows))
    print("symbol         %d" % n("symbol"))
    print("direction      %d" % n("direction"))
    print("setup          %d" % n("setup"))
    print("level_name     %d" % n("level_name"))
    print("level_price    %d" % n("level_price"))
    print("entry          %d" % n("entry"))
    print("stop           %d" % n("stop"))
    print("target         %d" % n("target"))
    print("outcome        %d  (threaded onto alerts: %d)" % (n("outcome"), n_threaded))
    print("r_multiple     %d" % n("r_multiple"))
    print("with image     %d" % sum(1 for r in rows if r["image_urls"]))
    print("date range     %s .. %s" % (min(r["ts"] for r in rows),
                                       max(r["ts"] for r in rows)))
    print("out            %s" % a.out)


if __name__ == "__main__":
    main()
