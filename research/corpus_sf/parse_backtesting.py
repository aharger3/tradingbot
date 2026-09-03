"""Deterministic parser for discord_data/backtesting.json -> research/corpus_sf/backtesting.jsonl

NOT Austin's marks. These are community/mentor backtest reports and rule
statements from the trading-room #backtesting channel. Read-only on every
Austin mark corpus; this script writes only under research/corpus_sf/.

Shape of the source export: list of dicts
    {id, ts (UTC, naive ISO), author, content, attachments[], embeds[], reply_to}

ts is UTC. Verified against discord_data/scarface-alerts.json, whose alert
volume peaks at 13:00-14:00 in the file = 09:00-10:00 ET. Output ts is ET.

Design: regex + whitelists only. No model calls. A field stays null unless the
message literally says it.
"""

import json
import os
import re
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "discord_data", "backtesting.json")
OUT = os.path.join(HERE, "backtesting.jsonl")

# --------------------------------------------------------------------------
# timezone: UTC -> America/New_York, DST by US rule (2nd Sun Mar .. 1st Sun Nov)
# --------------------------------------------------------------------------


def _nth_dow(year, month, dow, n):
    d = datetime(year, month, 1)
    while d.weekday() != dow:
        d += timedelta(days=1)
    return d + timedelta(weeks=n - 1)


def to_et(ts_utc):
    dt = datetime.strptime(ts_utc, "%Y-%m-%dT%H:%M:%S")
    y = dt.year
    dst_start = _nth_dow(y, 3, 6, 2).replace(hour=7)   # 2am ET = 07:00 UTC
    dst_end = _nth_dow(y, 11, 6, 1).replace(hour=6)    # 2am EDT = 06:00 UTC
    off = -4 if dst_start <= dt < dst_end else -5
    stamp = (dt + timedelta(hours=off)).strftime("%Y-%m-%dT%H:%M:%S")
    return stamp + ("-04:00" if off == -4 else "-05:00")


# --------------------------------------------------------------------------
# symbols
# --------------------------------------------------------------------------
# Case-insensitive: tickers people type lowercase in chat that do not collide
# with English words.
SYM_CI = [
    "QQQ", "SPY", "IWM", "TSLA", "NVDA", "AAPL", "AMZN", "MSFT", "GOOGL",
    "NFLX", "AVGO", "PLTR", "SOFI", "COIN", "HOOD", "IREN", "MSTR", "ORCL",
    "SPX", "NDX", "MNQ", "MES", "TQQQ", "SQQQ", "BABA", "UBER", "SMCI",
]
# Uppercase-exact only: short tokens that are also words/abbreviations.
SYM_CS = [
    "AMD", "META", "INTC", "MU", "GOOG", "TSM", "MARA", "CRM", "ACHR",
    "NQ", "ES", "RTY", "YM", "GC", "CL", "SPCX", "VST", "C",
]
# Spelled-out names.
SYM_NAME = {
    r"\btesla\b": "TSLA",
    r"\bnvidia\b": "NVDA",
    r"\bnvida\b": "NVDA",
    r"\bapple\b": "AAPL",
    r"\bappl\b": "AAPL",
    r"\bamazon\b": "AMZN",
    r"\bmicrosoft\b": "MSFT",
    r"\bnetflix\b": "NFLX",
    r"\bgoogle\b": "GOOGL",
    r"\bcitigroup\b": "C",
    r"\bmeta\b": "META",
}
# Tokens that look like tickers but are jargon in this room.
NOT_SYM = {
    "ORB", "PDH", "PDL", "PMH", "PML", "HOD", "LOD", "HTF", "MTF", "LTF",
    "RR", "OB", "SL", "TP", "PT", "BE", "FVG", "VWAP", "EST", "CST", "PST",
    "PA", "OR", "ORH", "ORL", "TF", "TOS", "NY", "AM", "PM", "PDF", "DM",
    "IMO", "TBH", "LOL", "EMA", "SMA", "ATM", "OTM", "ITM", "CEO", "TZ",
    "IBKR", "CBOE", "ASAP", "GTA", "WOW", "EDIT", "TPT", "MM", "EOD", "RH",
    "ND", "OP", "GJ", "ED", "AI", "US", "UK", "ETF", "API", "PC", "TV",
}

_ci_re = re.compile(r"\b(" + "|".join(SYM_CI) + r")\b", re.I)
_cs_re = re.compile(r"\b(" + "|".join(SYM_CS) + r")\b")


# "Im assuming this was on NQ or QQQ?" names no symbol -- it guesses two.
_SYM_ALT = r"[A-Za-z]{1,5}"
RE_SPEC_ALT = re.compile(
    r"(?i)(?:assum\w+|guess\w+|maybe|not sure|which|was it|is it|either)\b[^.?!\n]{0,60}?"
    r"\b(" + _SYM_ALT + r")\s+or\s+(" + _SYM_ALT + r")\b[^.?!\n]{0,40}\?"
)


def _speculative(text):
    """Symbols named only as alternatives inside a question."""
    out = set()
    for m in RE_SPEC_ALT.finditer(text):
        out.add(m.group(1).upper())
        out.add(m.group(2).upper())
    return out


def find_symbols(text):
    """Ordered, de-duplicated list of tickers the message actually names."""
    hits = []
    for m in _ci_re.finditer(text):
        hits.append((m.start(), m.group(1).upper()))
    for m in _cs_re.finditer(text):
        if m.group(1) not in NOT_SYM:
            hits.append((m.start(), m.group(1)))
    for pat, sym in SYM_NAME.items():
        for m in re.finditer(pat, text, re.I):
            hits.append((m.start(), sym))
    spec = _speculative(text)
    out = []
    for _, s in sorted(hits):
        if s not in out and s not in spec:
            out.append(s)
    return out


# --------------------------------------------------------------------------
# setup
# --------------------------------------------------------------------------
RE_BR = re.compile(
    r"(?i)break[\s\-]?(?:and|n|&)?[\s\-]?retest|\bb\s?&\s?r\b|\bbnr\b|\borbnr\b|"
    r"\bor[\s\-]?br\b|\borb[\s\-]?br\b|"
    r"\bretest(?:ed|s|ing)?\b|\breclaim(?:ed|s|ing)?\b|"
    r"\b84\s*%|\b84\s*rule\b|\bdip\s?&\s?rip\b|\bdip and rip\b"
)
RE_OCR = re.compile(r"(?i)one[\s\-]?candle(?:\s?rule)?\b|\bocr\b|\b1[\s\-]candle rule\b")


def find_setup(text):
    br = bool(RE_BR.search(text))
    ocr = bool(RE_OCR.search(text))
    if br and ocr:
        return "br_ocr"
    if br:
        return "break_retest"
    if ocr:
        return "one_candle"
    # "OR" only counts as the opening range when it is uppercase or carries a
    # timeframe. Case-insensitive "or high|or low" fired on the English "above
    # the previous high or low".
    if re.search(r"(?i)\borb\b|\borbnr\b|opening range|\border\s?block\b|"
                 r"\b\d+\s?m(?:in(?:ute)?s?)?\s+OR\b|\bor\s?\d+\s?min\b", text) \
            or re.search(r"\bOR\s+(?:high|low|High|Low)\b|\bORH\b|\bORL\b", text):
        return "other"
    return None


# --------------------------------------------------------------------------
# levels
# --------------------------------------------------------------------------
LEVEL_PATS = [
    ("pdh", r"(?i)\bpdh\b|previous day(?:'s)? high|prev(?:ious)? day high|\bpd high\b"),
    ("pdl", r"(?i)\bpdl\b|previous day(?:'s)? low|prev(?:ious)? day low|\bpd low\b"),
    ("pmh", r"(?i)\bpmh\b|pre[\s\-]?market high|premarket high"),
    ("pml", r"(?i)\bpml\b|pre[\s\-]?market low|premarket low"),
    ("hod", r"(?i)\bhod\b|high of (?:the )?day"),
    ("lod", r"(?i)\blod\b|low of (?:the )?day"),
    # bare "or high" is excluded: it fires on the English "the previous high or
    # low". A timeframe or the word "opening" has to be attached.
    ("or_high", r"(?i)\borh\b|\bopening range high\b|"
                r"\b\d+\s?min(?:ute)?s?\s+(?:opening\s+)?range high\b|"
                r"\b\d+\s?m(?:in(?:ute)?s?)?\s+or high\b"),
]
# Combined forms: the author named both sides of a pair, so neither side alone
# is what he said.
RE_COMBINED = re.compile(
    r"(?i)\b(?:pdh|pmh|hod)\s*(?:/|\bor\b|\band\b)\s*(?:pdl|pml|lod|l|low)\b|"
    r"\b(?:pdl|pml|lod)\s*(?:/|\bor\b|\band\b)\s*(?:pdh|pmh|hod|h|high)\b|"
    r"\bpdh\s+pdl\b|\bpmh\s+pml\b|\bhod\s+lod\b|"
    r"\bhigh\s*/\s*low of (?:the )?day\b|"
    r"\b(?:previous day|prev day|pre[\s\-]?market|premarket)\s+levels?\b"
)
RE_OR_GENERIC = re.compile(
    r"(?i)\borb\b|\borbnr\b|\bopening range\b|"
    r"\b\d+\s?min(?:ute)?s?\s+(?:opening\s+)?range\b|"
    r"\b\d+\s?m(?:in(?:ute)?s?)?\s+OR\b|\bor\s?\d+\s?min\b"
)


def find_level(text):
    """level_name, or 'other' when the message names an opening range without a
    side, or names more than one level.

    The opening range is a candidate level in its own right, competing on text
    position with the named levels. Without that, "1 min opening range BnR ...
    played to HOD" scored level=hod, which is the target, not the level."""
    if RE_COMBINED.search(text):
        return "other"
    hits = []
    for name, pat in LEVEL_PATS:
        m = re.search(pat, text)
        if m:
            hits.append((m.start(), name))
    m = RE_OR_GENERIC.search(text)
    if m and not any(n == "or_high" for _, n in hits):
        hits.append((m.start(), "other"))
    if not hits:
        return None
    hits.sort()
    if len({n for _, n in hits}) > 1:
        return "other"
    return hits[0][1]


# --------------------------------------------------------------------------
# direction
# --------------------------------------------------------------------------
RE_LONG = re.compile(
    r"(?i)\blong(?:s|ed|ing)?\b|\bcalls?\b|\bbullish\b|\bupside\b|\blongside\b"
)
RE_LONG_FALSE = re.compile(
    r"(?i)as long as|long[\s\-]term|long time|how long|so long|long run|"
    r"long story|call it|phone call|call out|long enough|long way|all day long|"
    r"calls? (?:it|me|you|him|her|them|this|that)\b"
)
RE_SHORT = re.compile(
    r"(?i)\bshort(?:s|ed|ing)?\b|\bputs?\b|\bbearish\b|\bdownside\b|\bshortside\b"
)
RE_SHORT_FALSE = re.compile(
    r"(?i)short[\s\-]term|in short|shortly|short line|short answer|short of|"
    r"short on time|short period|of Puts|puts? (?:in|it|the|me|you|us)\b"
)


# Phrases that name both sides at once. "entering on good PA to the up or
# downside" used to score short, because only "downside" is a whole word.
RE_BOTH_SIDES = re.compile(
    r"(?i)\bup\s*(?:or|/|and)\s*down(?:side)?\b|\bdown\s*(?:or|/|and)\s*up(?:side)?\b|"
    r"\babove\s*(?:or|/)\s*below\b|\bbelow\s*(?:or|/)\s*above\b|"
    r"\blong\s*(?:or|/)\s*short\b|\bshort\s*(?:or|/)\s*long\b|"
    r"\bhigh\s*(?:or|/)\s*low\b|\blow\s*(?:or|/)\s*high\b|"
    r"\bcalls?\s*(?:or|/|and)\s*puts?\b|\bputs?\s*(?:or|/|and)\s*calls?\b|"
    r"\bupside\s*(?:or|/|and)\s*downside\b|\beither\s+(?:way|direction)\b"
)


def _side(text, re_pos, re_false):
    return bool(re_pos.search(re_false.sub(" ", text)))


def find_direction(text):
    if RE_BOTH_SIDES.search(text):
        return None
    lo = _side(text, RE_LONG, RE_LONG_FALSE)
    sh = _side(text, RE_SHORT, RE_SHORT_FALSE)
    if lo and not sh:
        return "long"
    if sh and not lo:
        return "short"
    return None


# --------------------------------------------------------------------------
# outcome (single-trade only; an aggregate win rate is not an outcome)
# --------------------------------------------------------------------------
RE_AGG = re.compile(
    r"(?i)win\s?rate|winrate|%\s?win|win\s?%|\bwins\b|profit factor|"
    r"\d+\s*(?:trades|setups)\b|win percent"
)
RE_LOSS = re.compile(
    r"(?i)\bstopped out\b|\bgot stopped\b|would(?:'ve| have| ve)? (?:been |got )?stopped|"
    r"\bhit my stop\b|\bhit the stop\b|\btook the loss\b|\bwas a los(?:er|s)\b|"
    r"\bstopped me out\b|\bfull loss\b|\btrade failed\b"
)
RE_WIN = re.compile(
    r"(?i)\bhit (?:my |the )?(?:target|pt\d?|tp\d?|profit target)\b|"
    r"\bwas a winner\b|\bfull win\b|\btook the win\b|\breached (?:my |the )?target\b|"
    r"\btarget (?:was )?hit\b|\bworked (?:out )?perfectly\b|\bplayed out perfectly\b|"
    r"\bwould(?:'ve| have| ve)? worked (?:out )?perfectly\b"
)
RE_BE = re.compile(
    r"(?i)\bbreak\s?even\b|\bbreakeven\b|\bmoved to be\b|\bscratched\b|\bstopped at be\b"
)


def find_outcome(text):
    if RE_AGG.search(text):
        return None
    flags = [bool(RE_LOSS.search(text)), bool(RE_WIN.search(text)), bool(RE_BE.search(text))]
    if sum(flags) != 1:
        return None
    return ["loss", "win", "be"][flags.index(True)]


# --------------------------------------------------------------------------
# r-multiple
# --------------------------------------------------------------------------
RE_R = re.compile(r"(?<![:\d.])(-?\d+(?:\.\d+)?)\s*[rR]\b(?![rR])")
RE_R_CONTEXT = re.compile(
    r"(?i)backtest|back test|win\s?rate|winrate|\btrade[sd]?\b|stopped|target|"
    r"\bTP\b|\bPT\b|average|avg|expect|\bentry\b|\bentered\b|\bexit(?:ed)?\b|"
    r"\bheld\b|\bgifted\b|\bsetup\b|\bposition\b"
)


# A modal in the same sentence means the R is a plan or a target, not a result.
# "If the high of day hits before the 2R I will sell half" is not a 2R trade.
RE_MODAL = re.compile(r"(?i)\b(?:will|would|should|could|if|when|plan|aim|"
                      r"targets?|looking for|go for)\b")


def find_r(text):
    hits = list(RE_R.finditer(text))
    if not hits:
        return None
    vals = {float(m.group(1)) for m in hits}
    # "-1 = 1R, -2 = 2R, -3 = 3R" is a tutorial, not a result.
    if len(vals) >= 3:
        return None
    if not RE_R_CONTEXT.search(text):
        return None
    m = hits[0]
    sent = text[max(0, text.rfind(".", 0, m.start()) + 1):]
    sent = sent[:sent.find(".") + 1 or len(sent)]
    if RE_MODAL.search(sent):
        return None
    return float(m.group(1))


# --------------------------------------------------------------------------
# prices (this channel almost never quotes one; keep the extractor honest)
# --------------------------------------------------------------------------
PRICE = r"(\d{1,5}\.\d{1,2})"


def _price_after(text, kw):
    m = re.search(r"(?i)\b(?:" + kw + r")\b[^.\n]{0,25}?(?:at|@|of|around|near)?\s*\$?"
                  + PRICE + r"\b(?!\s*%)", text)
    return float(m.group(1)) if m else None


def find_prices(text):
    return (
        _price_after(text, r"entry|entered|enter"),
        _price_after(text, r"stop\s?loss|stop|SL"),
        _price_after(text, r"target|PT\d?|TP\d?"),
    )


IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def images(msg):
    return [u for u in msg.get("attachments", [])
            if u.split("?")[0].lower().endswith(IMG_EXT)]


# --------------------------------------------------------------------------
# noise gate + confidence
# --------------------------------------------------------------------------
RE_BACKTEST_WORD = re.compile(r"(?i)back\s?test(?:ed|ing|s)?\b")
RE_STATS = re.compile(
    r"(?i)\d+(?:\.\d+)?\s?%|\b\d\s?:\s?\d\b|\b\d\s*to\s*\d\s*RR\b|win\s?rate|"
    r"winrate|profit factor|\b\d+\s+trades?\b|\b\d+\s+(?:wins|losses|setups)\b"
)


def score_confidence(rec, text):
    """high   = a concrete result: symbol + setup + (outcome | R | stat)
       medium = two structural fields, or a setup plus a stat
       low    = one weak field only"""
    has_stat = bool(RE_STATS.search(text))
    strong = sum(x is not None for x in (rec["symbol"], rec["setup"], rec["level_name"]))
    result = rec["outcome"] is not None or rec["r_multiple"] is not None or has_stat
    if rec["symbol"] and rec["setup"] and result:
        return "high"
    if strong >= 2 or (rec["setup"] and result):
        return "medium"
    return "low"


def parse(msg):
    """0..n records for one message: one per named symbol, or one with
    symbol=null when the message is about the method rather than a ticker."""
    text = msg["content"] or ""
    clean = re.sub(r"<@[&!]?\d+>", " ", text)      # mention ids are not prices
    clean = re.sub(r"https?://\S+", " ", clean)    # urls are not tickers

    syms = find_symbols(clean)
    setup = find_setup(clean)
    level = find_level(clean)
    direction = find_direction(clean)
    outcome = find_outcome(clean)
    r = find_r(clean)
    entry, stop, target = find_prices(clean)

    substantive = bool(
        setup or level or r is not None
        or (syms and (RE_BACKTEST_WORD.search(clean) or RE_STATS.search(clean) or outcome))
    )
    if not substantive:
        return []

    base = {
        "src": "discord_data/backtesting.json",
        "msg_id": msg["id"],
        "ts": to_et(msg["ts"]),
        "author": msg["author"],
        "symbol": None,
        "direction": direction,
        "setup": setup,
        "level_price": None,
        "level_name": level,
        "entry": entry,
        "stop": stop,
        "target": target,
        "outcome": outcome,
        "r_multiple": r,
        "quote": text,
        "image_urls": images(msg),
        "confidence": "low",
    }
    recs = []
    for s in (syms or [None]):
        rec = dict(base)
        rec["symbol"] = s
        rec["confidence"] = score_confidence(rec, clean)
        recs.append(rec)
    return recs


def main():
    with open(SRC, encoding="utf-8") as f:
        msgs = json.load(f)
    rows, kept = [], set()
    for m in msgs:
        rs = parse(m)
        if rs:
            kept.add(m["id"])
        rows.extend(rs)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("messages=%d kept_messages=%d rows=%d -> %s" % (len(msgs), len(kept), len(rows), OUT))
    return rows


if __name__ == "__main__":
    main()
