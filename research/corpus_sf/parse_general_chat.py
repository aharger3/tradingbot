"""Deterministic extractor: mentor rule-statements out of discord_data/general-chat.json.

NOT Austin's marks. These are Scarface (TonyMontana), Jdub, MambaTrades, Hayden and
Neto Moreno's statements. Output goes ONLY under research/corpus_sf/.

general-chat is a community/admin channel: expected yield is low. The parser is a
whitelist on author + a trading-substance gate + admin/promo/social vetoes.
Everything it emits is a *rule candidate* (a mentor saying how they trade), not a trade.

Usage:  python research/corpus_sf/parse_general_chat.py
Writes: research/corpus_sf/general_chat.jsonl
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "discord_data", "general-chat.json")
OUT = os.path.join(HERE, "general_chat.jsonl")

# Discord exports carry naive UTC timestamps (scarface-alerts peaks at 13-14Z,
# i.e. the 09:30-11:00 ET window). Convert, never assume.
ET = ZoneInfo("America/New_York")

# ---------------------------------------------------------------- authors
# Mentors, established by which channels they own:
#   TonyMontana  -> scarface-alerts, premarket-charts, module-*   (SCARFACE)
#   Jdub         -> jdub-alerts, jdub-trade-reviews, weekly-outlook, live-sessions
#   MambaTrades  -> futures-alerts, futures-trade-reviews
#   Hayden       -> pre-market-live, weekly-live-education
#   Neto Moreno  -> performance coach; daily plans + trade reviews
MENTORS = {
    "TonyMontana",
    "Jdub",
    "MambaTrades",
    "Hayden",
    "Neto Moreno (Performance Coach)",
}
# Deliberately excluded: "Apex Trader" (community manager, admin replies only),
# "QueenBee" (self-identifies as a new trader in this channel).

# ---------------------------------------------------------------- gates
# STRONG: methodology vocabulary. One hit is enough to keep the message.
STRONG = re.compile(
    r"""(?ix)
    \b(
      break[\s\-]*(?:and[\s\-]*)?re[\s\-]*test | break\s*retest\s*boom | b\s*&\s*r
    | one[\s\-]candle(?:\s*rule)? | \bocr\b | order[\s\-]?block
    | re[\s\-]?test(?:s|ed|ing)?
    | \bpdh\b | \bpdl\b | \bpmh\b | \bpml\b | \bpwh\b | \bpwl\b
    | pre[\s\-]?market\s+(?:high|low|level)
    | previous\s+day(?:'?s)?\s+(?:high|low)
    | opening\s+range | opening\s+print
    | \bhod\b | \blod\b | \bath'?s?\b
    | key\s+levels? | htf\s+level | market\s+structure
    | stop\s*loss | stopped?\s+out | daily\s+loss\s+limit
    | risk[\s/:\-]*(?:to[\s\-]*)?reward | \br\s*[:/]\s*r\b | risk\s+management
    | price\s+action | price\s+react\w* | candle\s+close | close(?:d|s)?\s+(?:above|below)
    | support\s+(?:turn|becom|flip)\w*\s+(?:in)?to\s+resistance
    | resistance\s+(?:turn|becom|flip)\w*\s+(?:in)?to\s+support
    | \bfvg\b | \bifvg\b | imbalance | liquidity
    | trade\s+management | trade\s+selection | position\s+siz\w+
    | scal(?:e|ing|ed)\s+(?:out|in|at) | trim(?:med|ming)?\s+(?:at|into)
    | entry\s+criteria | trading\s+plan | playbook
    | \b0\s*dte\b | one\s+strike\s+otm | \botm\b | \bitm\b
    | \d*\.?\d+\s*delta | delta\s+of\b
    )\b
    """
)

# WEAK: generic trading nouns. Three distinct hits keep a message that has no
# STRONG term at all (prose coaching often reads that way).
WEAK = re.compile(
    r"""(?ix)
    \b(
      entry | entries | enter\w* | exit\w* | stop\w* | target\w* | trim\w* | scal\w*
    | setups? | candles? | wicks? | reclaim\w* | rejection\w* | bounces?
    | volume | vwap | ema | consolidat\w* | trends? | confluences?
    | contracts? | calls? | puts? | strikes? | expiration | premium | underlying
    | tickers? | charts? | timeframes? | bullish | bearish
    | resistance | supports? | levels? | profits? | loss | losses | risk | reward
    | journal\w* | backtest\w* | execut\w* | position\w* | runners?
    )\b
    """
)

# Admin / logistics noise. A hit vetoes unless the rule content is thick (strong >= 3).
ADMIN = re.compile(
    r"""(?ix)
    (
      open\s+(?:up\s+)?a?\s*<\# | ticket\b | whop | zoom\b | \bstream\b | restarting
    | scam\w* | fake\s+account | friend\s+request | telegram | instagram | tiktok
    | membership | subscription | refund | invoice | bootcamp | webinar
    | accelerator | mastermind | traders\s+academy | traders\s+edge
    | welcome\s+<@ | get\s+started\s+in | familiarize | modules?\b | lesson\s*\d
    | discord\.com/channels | youtu\.?be
    | password | log\s*in | sign\s*up | promo | giveaway | merch
    )
    """
)

# Promotion / announcement / pointer. A hit vetoes unconditionally: these are
# broadcasts and redirects, not statements about how to trade.
PROMO = re.compile(
    r"""(?ix)
    (
      q\s*&\s*a | drop\s+your\s+\w*\s*questions?
    | let'?s\s+kick\s+off | join\s+(?:us|our|me)\b | see\s+you\s+(?:later|tomorrow|next)
    | i'?ll\s+(?:make|upload|post|share|do|be)\b | in\s+the\s+near\s+future
    | \bthe\s+lesson\b | give\s+it\s+a\s+try | feel\s+free\s+to\s+share
    | daily\s+(?:trades?\s+)?review\s+with | review\s+sessions?
    | community\s+based\s+on | developed\s+by\s+a\s+trader
    | @everyone | @here | good\s+luck
    | watch\s+(?:this|here|the)\b | check\s+(?:it\s+)?out\s+the
    )
    """
)

# First-person feeling / social chatter. Kept only when rule content is thick.
SOCIAL = re.compile(r"(?i)\bi'?m\s+feeling\b|\bnervous\b|\bcongrat\w*|\blmao\b|\bhaha\w*")

# A channel pointer <#123...> with thin rule content is a redirect, not a rule.
CHANNEL_REF = re.compile(r"<#\d+>")

# Broker/platform mechanics ("right click the strike, hit Place Order"). Real
# instructions, but about a GUI, not about how to trade. Hard veto.
PLATFORM = re.compile(
    r"""(?ix)
    (
      widgets? | right[\s\-]?click | click\s+on | order\s+entry | turbo\s+trader
    | place\s+order | options?\s+chain | watchlist | \bibkr\b | \btws\b
    | thinkorswim | tastytrade
    )
    """
)

# Travel / life logistics. "Delta" the airline once tripped the options-greek gate.
OFFTOPIC = re.compile(
    r"""(?ix)
    (
      flight | landing | airport | hotel | starlink | vacation | calendar
    | \bgolf\w* | dubai | \bdriving\b | \bflying\b
    | our\s+live\s+trading\s+sessions?
    )
    """
)

MIN_LEN = 40

# ---------------------------------------------------------------- symbols
TICKERS = set(
    """SPY QQQ IWM DIA ES NQ RTY YM SPX NDX VIX
    NVDA TSLA AAPL MSFT MU INTC PLTR AMZN META AMD GOOGL GOOG NFLX ORCL AVGO
    SOFI COIN HOOD IREN UBER BABA CRM TSM MARA ACHR SPCX SMCI RIOT NIO GME
    AMC BA DIS PYPL SQ SHOP ROKU SNAP ABNB RIVN LCID MSTR ARM DELL CRWD SNOW
    XOM CVX JPM BAC WMT COST LLY UNH PANW ANET MRVL QCOM TXN ADBE""".split()
)
TICKER_RE = re.compile(r"(?<![A-Za-z0-9$])\$?([A-Z]{1,5})(?![A-Za-z0-9])")

# Mentors also write "Nvda", "spy". Case-insensitive matching is only safe for the
# names that are not also English words, and only at length >= 3 (ES/NQ/BA/MU/SQ
# would eat prose).
_CI_UNSAFE = {"ARM", "COST", "DIS", "SNOW", "ALL", "ONE", "NOW", "ANET"}
TICKERS_CI = {t.lower(): t for t in TICKERS if len(t) >= 3 and t not in _CI_UNSAFE}
TICKER_CI_RE = re.compile(r"(?<![A-Za-z0-9$])\$?([A-Za-z]{3,5})(?![A-Za-z0-9])")

# ---------------------------------------------------------------- fields
SETUP_BR = re.compile(
    r"(?i)break[\s\-]*(?:and[\s\-]*)?re[\s\-]*test|break\s*retest\s*boom"
    r"|\bb\s*&\s*r\b|re[\s\-]?test(?:s|ed|ing)?\b"
)
SETUP_OCR = re.compile(r"(?i)one[\s\-]candle(?:\s*rule)?|\bocr\b|order[\s\-]?block")

LEVEL_PATTERNS = [
    ("pdh", r"(?i)\bpdh\b|previous\s+day(?:'?s)?\s+high|prior\s+day\s+high"),
    ("pdl", r"(?i)\bpdl\b|previous\s+day(?:'?s)?\s+low|prior\s+day\s+low"),
    ("pmh", r"(?i)\bpmh\b|pre[\s\-]?market\s+high"),
    ("pml", r"(?i)\bpml\b|pre[\s\-]?market\s+low"),
    ("or_high", r"(?i)opening\s+range\s+high|\bor\s+high\b|opening\s+print"),
    ("hod", r"(?i)\bhod\b|high\s+of\s+(?:the\s+)?day"),
    ("lod", r"(?i)\blod\b|low\s+of\s+(?:the\s+)?day"),
    # the schema has no or_low / pwh / pwl slot; they land in "other"
    (
        "other",
        r"(?i)opening\s+range\s+low|\bath'?s?\b|key\s+levels?|htf\s+level"
        r"|pre[\s\-]?market\s+level|\bpwh\b|\bpwl\b",
    ),
]
LEVEL_RE = [(name, re.compile(p)) for name, p in LEVEL_PATTERNS]

PRICE = r"\$?(\d{1,5}(?:\.\d{1,2})?)"
ENTRY_RE = re.compile(r"(?i)\b(?:entry|entered|enter|got in|filled)\b[^.\n]{0,25}?\bat\s+" + PRICE)
STOP_RE = re.compile(r"(?i)\bstop(?:\s*loss)?\b[^.\n]{0,20}?\bat\s+" + PRICE)
TARGET_RE = re.compile(r"(?i)\b(?:target|pt\d?|take profit|tp)\b[^.\n]{0,20}?\bat\s+" + PRICE)

# Outcome is only asserted first-person about a trade actually taken. Generic
# advice ("if you keep getting stopped out...") must stay null.
WIN_RE = re.compile(
    r"(?i)\bi\s+(?:took\s+profit|hit\s+(?:my\s+)?target|closed\s+(?:it\s+)?green"
    r"|was\s+(?:profitable|green))\b"
    r"|\bthe\s+trade\s+(?:worked\s+out|was\s+a\s+winner)\b"
)
LOSS_RE = re.compile(
    r"(?i)\bi\s+(?:personally\s+)?(?:lost\b|got\s+stopped\s+out\b|stopped\s+out\b"
    r"|took\s+the\s+loss\b|cut\s+it\b|was\s+red\b)"
)
BE_RE = re.compile(
    r"(?i)\bi\s+(?:scratched\b|took\s+it\s+(?:at\s+)?break\s*even|closed\s+(?:it\s+)?"
    r"(?:at\s+)?break\s*even)"
)

R_RE = re.compile(r"(?i)(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s*R\b(?!\w)")

# Direction is only asserted on an explicit trade-direction phrase. Bare
# "calls"/"puts"/"long"/"short" is instrument or adjective talk ("a long time",
# "short term") and must stay null.
LONG_RE = re.compile(
    r"(?i)(?:\b(?:bought|buying|took|taking|grabbed|holding|in)\s+(?:the\s+)?calls?\b"
    r"|\b(?:went|going|i'?m|im|stayed)\s+long\b"
    r"|\blong\s+(?:entry|setup|side|position|trade)\b"
    r"|\bcall\s+side\b)"
)
SHORT_RE = re.compile(
    r"(?i)(?:\b(?:bought|buying|took|taking|grabbed|holding|in)\s+(?:the\s+)?puts?\b"
    r"|\b(?:went|going|i'?m|im|stayed)\s+short\b"
    r"|\bshort\s+(?:entry|setup|side|position|trade)\b"
    r"|\bshort(?:ed|ing)\s+(?:the\s+)?(?:\$?[A-Z]{1,5}\b|it\b)"
    r"|\bput\s+side\b)"
)

MENTION = re.compile(r"<[@#][!&]?\d+>")


SMART = {
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", " ": " ",
}


def norm(text: str) -> str:
    """Fold typographic punctuation so the gates see plain ASCII.

    Neto writes with curly apostrophes; "I'll be around" never matched the PROMO
    veto until this existed.
    """
    for a, b in SMART.items():
        text = text.replace(a, b)
    return text


def to_et(ts: str) -> str:
    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.astimezone(ET).isoformat()


def find_symbol(text: str):
    # strip discord mentions and urls first so ids/codes cannot look like tickers
    t = MENTION.sub(" ", text)
    t = re.sub(r"https?://\S+", " ", t)
    hits = [m.group(1) for m in TICKER_RE.finditer(t) if m.group(1) in TICKERS]
    if not hits:
        hits = [
            TICKERS_CI[m.group(1).lower()]
            for m in TICKER_CI_RE.finditer(t)
            if m.group(1).lower() in TICKERS_CI
        ]
    if not hits:
        return None
    # first mention wins; the channel almost never discusses two names at once
    return hits[0]


def find_direction(text: str):
    lo = bool(LONG_RE.search(text))
    sh = bool(SHORT_RE.search(text))
    if lo and not sh:
        return "long"
    if sh and not lo:
        return "short"
    return None


def find_setup(text: str):
    br = bool(SETUP_BR.search(text))
    ocr = bool(SETUP_OCR.search(text))
    if br and ocr:
        return "br_ocr"
    if br:
        return "break_retest"
    if ocr:
        return "one_candle"
    return None


def find_level(text: str):
    for name, rx in LEVEL_RE:
        if rx.search(text):
            return name
    return None


def num(rx, text):
    m = rx.search(text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def find_outcome(text: str):
    if BE_RE.search(text):
        return "be"
    if LOSS_RE.search(text):
        return "loss"
    if WIN_RE.search(text):
        return "win"
    return None


def score(text: str):
    strong = len(set(m.group(0).lower() for m in STRONG.finditer(text)))
    weak = len(set(m.group(0).lower() for m in WEAK.finditer(text)))
    return strong, weak


def keep(msg):
    """Gate. Returns (keep_bool, strong, weak, admin_bool)."""
    if msg["author"] not in MENTORS:
        return False, 0, 0, False
    text = norm((msg.get("content") or "").strip())
    if len(text) < MIN_LEN:
        return False, 0, 0, False
    strong, weak = score(text)
    admin = bool(ADMIN.search(text))
    if PROMO.search(text) or PLATFORM.search(text) or OFFTOPIC.search(text):
        return False, strong, weak, admin
    if SOCIAL.search(text) and strong < 2:
        return False, strong, weak, admin
    if CHANNEL_REF.search(text) and strong < 2:
        return False, strong, weak, admin
    if strong == 0:
        return (weak >= 3 and not admin), strong, weak, admin
    if admin and strong < 3:
        return False, strong, weak, admin
    return True, strong, weak, admin


def confidence(strong, weak, setup, level):
    if strong >= 3 and (setup or level):
        return "high"
    if strong >= 2 or (strong >= 1 and (setup or level)):
        return "medium"
    return "low"


def main():
    with open(SRC, encoding="utf-8") as fh:
        msgs = json.load(fh)

    rows, skipped = [], []
    for m in msgs:
        ok, strong, weak, admin = keep(m)
        if not ok:
            skipped.append(m["id"])
            continue
        raw = (m.get("content") or "").strip()
        text = norm(raw)
        setup = find_setup(text)
        level = find_level(text)
        rows.append(
            {
                "src": "discord_data/general-chat.json",
                "msg_id": m["id"],
                "ts": to_et(m["ts"]),
                "author": m["author"],
                "symbol": find_symbol(text),
                "direction": find_direction(text),
                "setup": setup,
                "level_price": None,
                "level_name": level,
                "entry": num(ENTRY_RE, text),
                "stop": num(STOP_RE, text),
                "target": num(TARGET_RE, text),
                "outcome": find_outcome(text),
                "r_multiple": num(R_RE, text),
                "quote": raw,  # verbatim, un-normalised
                "image_urls": list(m.get("attachments") or []) + list(m.get("embeds") or []),
                "confidence": confidence(strong, weak, setup, level),
            }
        )

    with open(OUT, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"messages={len(msgs)} extracted={len(rows)} skipped={len(skipped)}", file=sys.stderr)
    return rows


if __name__ == "__main__":
    main()
