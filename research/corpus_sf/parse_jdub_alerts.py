"""Deterministic parser for discord_data/jdub-alerts.json (mentor "Jdub" alert channel).

NOT Austin marks. Output lands in research/corpus_sf/ only; every Austin mark
corpus is read-only to this script.

Approach: regex + keyword heuristics, no LLM anywhere. One JSONL row per
extracted item. A field is emitted only when the message literally states it;
otherwise null. Nothing is inferred from neighbouring messages -- a management
line like "Out 70% here" that never names the ticker keeps symbol=null.

Message shapes in this channel (4,274 msgs, 2024-04 .. 2026-08):
  * premarket chart drops: bare ticker(s) + a chart image          -> one row per ticker
  * short alerts:          "AMD Puts 870 @2.5 / Stop above 177.80" -> one row
  * management/outcome:    "Stopped out the rest on TSLA"          -> one row
  * long prose / gameplan: multi-symbol daily bias                 -> one row per sentence
  * noise:                 zoom + youtube links, promos, headers   -> skipped

Usage:
    python research/corpus_sf/parse_jdub_alerts.py
    python research/corpus_sf/parse_jdub_alerts.py --sample 42   # stratified audit print
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_REL = "discord_data/jdub-alerts.json"
SRC = os.path.join(REPO, "discord_data", "jdub-alerts.json")
OUT = os.path.join(REPO, "research", "corpus_sf", "jdub_alerts.jsonl")
SKIP_OUT = os.path.join(REPO, "research", "corpus_sf", "jdub_alerts_skipped.jsonl")
ET = ZoneInfo("America/New_York")

# ---------------------------------------------------------------- vocabulary

# Whitelist. All-caps alone is not enough -- PDH/HOD/FOMC/EST are all-caps too.
TICKERS = {
    # universe.py
    "NVDA", "TSLA", "AAPL", "SPCX", "MSFT", "MU", "INTC", "PLTR", "AMZN",
    "META", "AMD", "GOOGL", "ACHR", "NFLX", "ORCL", "QQQ", "SPY", "IWM",
    "GOOG", "SOFI", "COIN", "HOOD", "IREN", "AVGO", "UBER", "BABA", "CRM",
    "TSM", "MARA",
    # seen in this channel, outside universe.py
    "ES", "NQ", "RTY", "SPX", "SMH", "SNDK", "WDC", "MRVL", "NBIS", "CRWV",
    "ARM", "MSTR", "COST", "DELL", "STX", "HIMS", "RDDT", "BTC", "DIA", "XLK",
    "ADBE", "PANW", "SHOP", "LLY", "CVNA", "AFRM", "APP", "RKLB", "OKLO",
}
TICKER_ALIAS = {"APPL": "AAPL", "TELSA": "TSLA", "TESLA": "TSLA", "GOOGLE": "GOOG",
                "SPX": "SPX"}

MONTHS = ("january|february|march|april|may|june|july|august|september|"
          "october|november|december|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec")

RE_NOISE = re.compile(
    r"^(?:pre[\s-]*market\s*(?:charts?|prep|live|gameplan|game\s*plan)?"
    r"|live\s*trading(?:\s*session)?|executions?|weekly\s*(?:recap|outlook))\b", re.I)
RE_PROMO = re.compile(
    r"just uploaded|youtube\.com/live|youtu\.be/|zoom\.us/|tradingview\.com/chart"
    r"|discord\.com/channels|/watch\?v=|youtube\.com/channel", re.I)
RE_GAMEPLAN = re.compile(rf"^(?:pre\s*market\s*)?game\s*plan\b|^(?:{MONTHS})\s+\d{{1,2}}"
                         rf"(?:st|nd|rd|th)?\s+game\s*plan", re.I)

PRICE = r"(\d{1,6}(?:\.\d{1,4})?)"
RE_PCT = re.compile(r"\d\s*%")

RE_ENTRY_VERB = re.compile(
    r"\b(?:bought|buying|buy|took|taking|picked up|picking up|added|adding|"
    r"i'?m in\b|entered|entering|re[\s-]?entered|long|short|shorting|starter|"
    r"loaded|loading|scaling in|filled|in the)\b", re.I)
RE_MANAGE = re.compile(
    r"\b(?:stop|stopped|trim|trimmed|scaled|scaling|sold|sell|profits|partial|"
    r"breakeven|break even|risking|risk off|holding|hold|cut(?:ting|s)?|closed|out \d|"
    r"took some|took a few|off here)\b", re.I)
RE_OUTCOME_WORD = re.compile(r"\btargets?\b|\bstopped\b|\bbreak\s*even\b|\bPT\d?\b", re.I)
RE_INTENT = re.compile(
    r"\b(?:looking for|looking to|interested in|watch(?:es|ing|list)?|want to see|"
    r"would like to see|will look for|i like\b|top watch|main watch|in play|"
    r"trade of the day|expecting|keep an eye)\b", re.I)
RE_LEVELWORD = re.compile(
    r"\b(?:PDH|PDL|PMH|PML|PDC|HOD|LOD|PWH|PWL|ATHs?|ATH'?s|all[\s-]?time highs?|"
    r"opening range|high of (?:the )?day|low of (?:the )?day|"
    r"previous day'?s? (?:high|low|close)|pre[\s-]?market (?:high|low))\b", re.I)

RE_SETUP_BR = re.compile(
    r"\bbreak\b[^.\n]{0,40}\bretest\b|\bretest\b[^.\n]{0,40}\bbreak\b|"
    r"\bbreak\s*(?:and|&|/|-)\s*retest\b|\bb\s*(?:&|and|n)\s*r\b|\bbnr\b", re.I)
RE_SETUP_OCR = re.compile(r"\bone[\s-]?candle(?:\s*rule)?\b|\bocr\b|\b1\s*candle\b", re.I)
RE_SETUP_OTHER = re.compile(
    r"\bpullback\b|\bscalp(?:ing)?\b|\bbreakout\b|\bgap\s*fill\b|\breclaim\b|"
    # "continuation" and "flip" describe direction of travel, not a setup -- excluded.
    r"\bswing\b|\binside\s*bar\b|\bflat\s*top\b|\bdip and rip\b|\bbear flag\b|"
    r"\bbull flag\b|\bwedge\b|\bH&S\b|\bdouble top\b|\bdouble bottom\b", re.I)

LEVEL_MAP = [
    (r"opening range high|\bOR\s*high\b|\bORH\b", "or_high"),
    (r"\bPDH\b|previous day'?s? high", "pdh"),
    (r"\bPDL\b|previous day'?s? low", "pdl"),
    (r"\bPMH\b|pre[\s-]?market high", "pmh"),
    (r"\bPML\b|pre[\s-]?market low", "pml"),
    (r"\bHOD\b|high of (?:the )?day|new highs?\b", "hod"),
    (r"\bLOD\b|low of (?:the )?day|new lows?\b", "lod"),
    (r"\bATHs?\b|ATH'?s|all[\s-]?time high|\bPWH\b|\bPWL\b|\bPDC\b|"
     r"previous day'?s? close|previous week'?s? (?:high|low)", "other"),
]

RE_WIN = re.compile(
    r"\btargets?\s*(?:hit|reached|tagged)\b|\bhit\s+(?:the\s+|my\s+|our\s+)?"
    r"(?:first|next|main|final|1st|2nd)?\s*targets?\b|"
    r"\b(?:first|next|main|final)\s+target\s+(?:hit|LOD|HOD)\b|"
    # dollar P&L statements: "+5K on TSLA", "Up $22K on AMD"
    r"(?:^|\s)\+\s?\$?\d+(?:\.\d+)?\s*[Kk]\b|\bup\s+\$\s?\d|\bup\s+\d+(?:\.\d+)?\s*[Kk]\b", re.I)
RE_LOSS = re.compile(r"\bstopped\s*(?:out|on|off)?\b|\btook the loss\b|\bfor an L\b|"
                     r"\blost\s+\$?\s?\d+(?:\.\d+)?\s*[Kk]?\b|"
                     r"(?:^|\s)-\s?\$?\d+(?:\.\d+)?\s*[Kk]\b", re.I)
RE_BE = re.compile(r"(?i:\bbreak\s*even\b|\bbreakeven\b)|\bBE\b")

CHART_TAIL = re.compile(
    r"^(?:daily|weekly|monthly|1\s*hr|1hr|hourly|4\s*hr|4hr|15\s*m(?:in)?|"
    r"5\s*m(?:in)?|1\s*m(?:in)?|chart|charts|levels?|level|setup|update|htf|"
    r"timeframe|tf|d|w|and)$", re.I)


# ---------------------------------------------------------------- helpers

def clean(content: str) -> str:
    t = re.sub(r"<@[&!]?\d+>", " ", content)
    t = re.sub(r"<#\d+>", " ", t)
    t = re.sub(r"@everyone|@here", " ", t)
    return re.sub(r"[ \t]+", " ", t).strip()


def to_et(ts: str) -> str:
    return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc).astimezone(ET).isoformat()


def symbol_hits(text: str):
    """[(pos, TICKER)] in order of appearance. Source token must be upper-case."""
    hits = []
    for m in re.finditer(r"\$?\b([A-Za-z]{1,5})\b", text):
        tok = m.group(1)
        if not tok.isupper():
            continue
        u = TICKER_ALIAS.get(tok, tok)
        if u in TICKERS:
            hits.append((m.start(1), u))
    return hits


def find_symbols(text: str):
    out = []
    for _, s in symbol_hits(text):
        if s not in out:
            out.append(s)
    return out


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _is_pct(text: str, end: int) -> bool:
    return bool(re.match(r"\s*%", text[end:end + 3]))


def direction_of(text: str):
    short = re.search(r"\bputs?\b|\bshort(?:ing|ed|s)?\b|\bbearish\b|\bdownside\b", text, re.I)
    long_ = re.search(r"\bcalls?\b|\blong(?:ing|ed)?\b|\bbullish\b|\bbuy the dip\b|"
                      r"\bupside\b", text, re.I)
    if short and long_:
        return None
    return "short" if short else ("long" if long_ else None)


def setup_of(text: str):
    br, ocr = bool(RE_SETUP_BR.search(text)), bool(RE_SETUP_OCR.search(text))
    if br and ocr:
        return "br_ocr"
    if br:
        return "break_retest"
    if ocr:
        return "one_candle"
    return "other" if RE_SETUP_OTHER.search(text) else None


def level_name_of(text: str):
    hits = []
    for pat, name in LEVEL_MAP:
        m = re.search(pat, text, re.I)
        if m:
            hits.append((m.start(), name))
    if not hits:
        return None
    hits.sort()
    return hits[0][1]


def _price_after(text: str, pat: str):
    for m in re.finditer(pat, text, re.I):
        if _is_pct(text, m.end(1)):
            continue
        return _f(m.group(1)), m.span(1)
    return None, None


def stop_of(text: str):
    v, _ = _price_after(text, r"\bstop(?:\s*(?:loss|will be|is|for me is|for me|at|:))?\s*"
                              r"(?:above|below|under|over|at|off|of)?\s*\$?" + PRICE)
    if v is not None:
        return v
    v, _ = _price_after(text, r"\brisk(?:ing)?\s*(?:it\s*)?(?:off|below|above|at|under|over)?"
                              r"\s*\$?" + PRICE)
    return v


def target_of(text: str):
    v, _ = _price_after(text, r"\btarget(?:s|ing)?\s*(?:will be|is|of|at|:)?\s*\$?" + PRICE)
    if v is not None:
        return v
    v, _ = _price_after(text, PRICE + r"\s+(?:is\s+)?(?:the\s+)?"
                                      r"(?:next\s+|first\s+|main\s+|final\s+)?target")
    return v


def entry_of(text: str, direction):
    """Stated fill. Option alerts quote a premium ("495 calls @3.9" -> 3.9, the
    495 is a strike and the schema has no strike field). Futures/equity alerts
    quote the underlying ("Short NQ 18210" -> 18210)."""
    v, _ = _price_after(text, r"(?:calls?|puts?)[^\n@]{0,30}@\s*\$?" + PRICE)
    if v is not None:
        return v
    if re.search(r"\bcalls?\b|\bputs?\b|\bcontracts?\b", text, re.I):
        v, _ = _price_after(text, r"@\s*\$?" + PRICE + r"\b")
        if v is not None:
            return v
    if direction:
        # Case-SENSITIVE on purpose: the optional slot is a ticker, and matching it
        # case-insensitively let "short under 382" read 382 as a fill when 382 is
        # really the trigger level.
        m = re.search(r"\b(?:[Ll]ong|[Ss]hort)\s+(?:\$?[A-Z]{1,5}\s+)?\$?" + PRICE + r"\b", text)
        if m and not _is_pct(text, m.end(1)):
            return _f(m.group(1))
    return None


LEVEL_PRICE_PATS = (
    r"\b(?:above|below|over|under|off(?: of)?|break(?:s|ing)? (?:above|below)|"
    r"reclaim(?:s|ing)?|hold(?:s|ing)? (?:above|below)|defend(?:ing)?)\s*"
    r"(?:the\s+)?\$?" + PRICE,
    r"\bmaintain(?:ing)?\s*(?:above|below)?\s*(?:the\s+)?\$?" + PRICE,
    r"\b(?:hold|reaction|retest|test|bounce)\s+(?:of|off|at)\s+(?:the\s+)?\$?" + PRICE,
)


def level_price_of(text: str):
    """A price bound to a trigger word -- never one already claimed by stop/target/entry."""
    for pat in LEVEL_PRICE_PATS:
        for m in re.finditer(pat, text, re.I):
            if _is_pct(text, m.end(1)):
                continue
            pre = text[max(0, m.start() - 24):m.start()].lower()
            if "stop" in pre or "risk" in pre or "target" in pre or "@" in pre[-3:]:
                continue
            return _f(m.group(1))
    return None


def outcome_of(text: str):
    be, win, loss = RE_BE.search(text), RE_WIN.search(text), RE_LOSS.search(text)
    if loss and be:
        return "be"
    if loss and not win:
        return "loss"
    if win and not loss:
        return "win"
    if be and not win:
        return "be"
    return None


def r_multiple_of(text: str):
    if re.search(r"\bRR\b", text):
        return None
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*R\b(?!\w)", text)
    return _f(m.group(1)) if m else None


def images_of(msg):
    urls = [u for u in (msg.get("attachments") or [])]
    for e in msg.get("embeds") or []:
        if isinstance(e, str) and re.search(r"\.(png|jpe?g|gif|webp)(\?|$)", e, re.I):
            urls.append(e)
    return urls


# ---------------------------------------------------------------- row build

FIELD_ORDER = ["src", "msg_id", "ts", "author", "symbol", "direction", "setup",
               "level_price", "level_name", "entry", "stop", "target", "outcome",
               "r_multiple", "quote", "image_urls", "confidence"]


def build(msg, scope_text, symbol, level_price=None, chart=False, quote=None):
    """scope_text = the span the fields are read from (whole message, one sentence,
    or one symbol's segment of a multi-symbol sentence). `quote` is verbatim source
    text -- the whole message, or for a sentence-level row that sentence."""
    if chart:
        fields = dict(direction=None, setup=None, level_price=None, level_name=None,
                      entry=None, stop=None, target=None, outcome=None, r_multiple=None)
        conf = "low"
    else:
        direction = direction_of(scope_text)
        entry = entry_of(scope_text, direction)
        stop = stop_of(scope_text)
        target = target_of(scope_text)
        lvl = level_price if level_price is not None else level_price_of(scope_text)
        if lvl is not None and lvl in {entry, stop, target}:
            lvl = None
        fields = dict(direction=direction, setup=setup_of(scope_text),
                      level_price=lvl, level_name=level_name_of(scope_text),
                      entry=entry, stop=stop, target=target,
                      outcome=outcome_of(scope_text), r_multiple=r_multiple_of(scope_text))
        hard = sum(1 for k in ("entry", "stop", "target", "outcome") if fields[k] is not None)
        if symbol and direction and hard >= 2:
            conf = "high"
        elif symbol and (hard >= 1 or fields["level_price"] is not None):
            conf = "medium"
        else:
            conf = "low"
    out = {"src": SRC_REL, "msg_id": msg["id"], "ts": to_et(msg["ts"]),
           "author": msg.get("author"), "symbol": symbol, **fields,
           "quote": quote if quote is not None else (msg.get("content") or ""),
           "image_urls": images_of(msg), "confidence": conf}
    return {k: out[k] for k in FIELD_ORDER}


# ---------------------------------------------------------------- classify

def is_chart_post(text: str, syms) -> bool:
    """Ticker(s) plus at most timeframe/chart words -- a premarket chart drop."""
    if not syms:
        return False
    rest = text
    for s in syms + [k for k in TICKER_ALIAS if TICKER_ALIAS[k] in syms]:
        rest = re.sub(rf"\$?\b{s}\b", " ", rest)
    rest = re.sub(r"[^A-Za-z0-9 ]", " ", rest)
    words = [w for w in rest.split() if w]
    return all(CHART_TAIL.match(w) for w in words)


# Bias / result words that make a ticker mention a statement about that ticker.
# ("Pnl on TSLA Today", "AAPL, MRVL Upside" were both being dropped without these.)
RE_BIAS = re.compile(
    r"\bP\s?&\s?L\b|\bPNL\b|\bupside\b|\bdownside\b|\bstrength\b|\bweak(?:ness)?\b|"
    r"\bheavy\b|\blooks? good\b|\bleading\b|\blagging\b|\bon watch\b|\bsolid\b", re.I)


def has_trade_lexicon(t: str) -> bool:
    return bool(RE_ENTRY_VERB.search(t) or RE_MANAGE.search(t) or RE_OUTCOME_WORD.search(t)
                or RE_INTENT.search(t) or RE_LEVELWORD.search(t) or RE_BIAS.search(t))


def strong_action(t: str) -> bool:
    """Trade action explicit enough to keep even with no ticker named."""
    if RE_OUTCOME_WORD.search(t) and (RE_WIN.search(t) or RE_LOSS.search(t) or RE_BE.search(t)):
        return True
    if RE_ENTRY_VERB.search(t) and re.search(r"@\s*\d|\bcalls?\b|\bputs?\b|\bcontracts?\b", t, re.I):
        return True
    return bool(re.search(r"\b(?:out|off|trim(?:med)?|scaled|sold)\b[^.\n]{0,20}"
                          r"(?:\d{1,3}\s*%|here|rest|remaining|position)", t, re.I))


SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


FILLER = (r"(?:(?:above|below|under|over|off|of|the|a|at|around|near|to|be|is|"
          r"going|reaction|hold|holds|holding|break|breaks|breaking|reclaim|"
          r"retest|test|bounce|defend|defends|dip|push|back|towards|and|for|"
          r"from|watch|watching|level|levels|key)\s+){0,4}")


def _level_for(sym, seg, sent):
    """Price attributable to THIS ticker, most explicit binding first."""
    # a) "the 688.5 on the SPY" -- an explicit "on/for <ticker>" binding beats mere
    #    adjacency, and must be tried first: in "off the 602.5 on the QQQ and the
    #    665.5 on the SPY" the QQQ segment still *contains* the SPY number.
    m = re.search(PRICE + rf"\s+(?:on|for)\s+(?:the\s+)?\$?{sym}\b", sent, re.I)
    if m and not _is_pct(sent, m.end(1)):
        return _f(m.group(1))
    # b) "MU above 1200" / "WDC 730" / "TSLA under 410"
    m = re.search(rf"\b{sym}\b[^0-9A-Za-z]{{0,3}}{FILLER}\$?" + PRICE, seg, re.I)
    if m and not _is_pct(seg, m.end(1)):
        return _f(m.group(1))
    # c) any trigger-bound price inside this ticker's own segment
    return level_price_of(seg)


def sentence_rows(msg, text):
    """Long prose (gameplans, multi-symbol commentary): one row per ticker per
    sentence. Each ticker owns the segment running from the previous ticker to
    the next one, so "SPY 686.5 and the QQQ 618" cannot cross-assign levels."""
    rows = []
    for sent in SENT_SPLIT.split(text):
        sent = sent.strip()
        if len(sent) < 8:
            continue
        hits = symbol_hits(sent)
        if not hits:
            continue
        if not (has_trade_lexicon(sent) or re.search(r"\d", sent)):
            continue
        single = len({s for _, s in hits}) == 1
        seen = set()
        for i, (pos, sym) in enumerate(hits):
            if sym in seen:
                continue
            seen.add(sym)
            if single:
                seg = sent
            else:
                # Forward-only: a ticker owns the text from itself to the next
                # ticker. Starting the segment at the PREVIOUS ticker instead
                # handed "TSLA off 475, NVDA off Tuesdays lows" -> 475 to NVDA.
                end = hits[i + 1][0] if i + 1 < len(hits) else len(sent)
                seg = sent[pos:end]
            rows.append(build(msg, seg, sym,
                              level_price=_level_for(sym, seg, sent), quote=sent))
    return rows


def parse(msg):
    """-> (rows, skip_reason|None)"""
    text = clean(msg.get("content") or "")
    imgs = images_of(msg)

    if not text:
        return [], ("image_only_no_text" if imgs else "empty")
    if RE_PROMO.search(text) and not strong_action(text):
        return [], "promo_or_stream_link"

    syms = find_symbols(text)
    body = re.sub(RE_GAMEPLAN.pattern, "", text, count=1, flags=re.I).strip()
    gameplan = bool(RE_GAMEPLAN.match(text))

    if not syms and RE_NOISE.match(text) and not strong_action(text):
        return [], "section_header"

    if is_chart_post(text, syms):
        return [build(msg, text, s, chart=True) for s in syms], None

    # long prose / gameplan -> sentence level
    if gameplan or len(text) > 180:
        rows = sentence_rows(msg, body if gameplan else text)
        if rows:
            return rows, None
        if syms and has_trade_lexicon(text):
            return [build(msg, text, syms[0])], None
        if strong_action(text):
            return [build(msg, text, None)], None
        return [], ("gameplan_no_symbol_sentence" if gameplan else "prose_no_signal")

    if syms and (has_trade_lexicon(text) or re.search(r"\d", text)):
        # A short watchlist-with-a-view ("AAPL, MRVL Upside") is one item per
        # ticker. A short message that reports a trade result ("Stopped on NVDA
        # with the NQ drop") is ONE item -- the outcome belongs to one ticker,
        # so it stays on the first-named one rather than being copied around.
        if len(syms) > 1 and not any((outcome_of(text), stop_of(text), target_of(text))):
            rows = sentence_rows(msg, text)
            if rows:
                return rows, None
        return [build(msg, text, syms[0])], None
    if not syms and strong_action(text):
        return [build(msg, text, None)], None
    return [], ("no_symbol_no_action" if not syms else "no_trade_lexicon")


# ---------------------------------------------------------------- main

def main():
    msgs = json.load(open(SRC, encoding="utf-8"))
    rows, skipped = [], []
    for m in msgs:
        rs, why = parse(m)
        if rs:
            rows.extend(rs)
        else:
            skipped.append({"msg_id": m["id"], "ts": m["ts"], "reason": why,
                            "content": m.get("content", "")})
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(SKIP_OUT, "w", encoding="utf-8") as f:
        for s in skipped:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    cnt = lambda k: sum(1 for r in rows if r[k] is not None)
    msg_ids = {r["msg_id"] for r in rows}
    print(f"messages={len(msgs)} rows={len(rows)} messages_with_rows={len(msg_ids)} "
          f"messages_skipped={len(skipped)}")
    print(f"symbol={cnt('symbol')} direction={cnt('direction')} setup={cnt('setup')} "
          f"level_name={cnt('level_name')} level_price={cnt('level_price')} "
          f"entry={cnt('entry')} stop={cnt('stop')} target={cnt('target')} "
          f"outcome={cnt('outcome')} r_multiple={cnt('r_multiple')} "
          f"image={sum(1 for r in rows if r['image_urls'])}")
    print("confidence", Counter(r["confidence"] for r in rows).most_common())
    print("outcome", Counter(r["outcome"] for r in rows if r["outcome"]).most_common())
    print("setup", Counter(r["setup"] for r in rows if r["setup"]).most_common())
    print("level_name", Counter(r["level_name"] for r in rows if r["level_name"]).most_common())
    print("top symbols", Counter(r["symbol"] for r in rows if r["symbol"]).most_common(12))
    print("skip reasons", Counter(s["reason"] for s in skipped).most_common())
    print("ts range", min(r["ts"] for r in rows), max(r["ts"] for r in rows))

    if "--sample" in sys.argv:
        i = sys.argv.index("--sample")
        seed = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 42
        random.seed(seed)
        rich = [r for r in rows if r["confidence"] != "low" or r["level_price"] is not None]
        chart = [r for r in rows if r not in rich]
        pick = random.sample(rich, 22) + random.sample(chart, 8)
        print("\n=== 30 EXTRACTED (22 informative + 8 chart-post) ===")
        for r in pick:
            print(json.dumps({k: v for k, v in r.items() if k != "image_urls"},
                             ensure_ascii=False)[:700])
        print("\n=== 15 SKIPPED ===")
        for s in random.sample(skipped, 15):
            print(s["reason"], "|", s["content"].replace("\n", " / ")[:230])


if __name__ == "__main__":
    main()
