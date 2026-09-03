"""Deterministic parser for discord_data/futures-alerts.json (MambaTrades futures room).

These are mentor judgements, NOT Austin marks. Output namespace: research/corpus_sf/ only.
Regex + heuristics, no LLM. One JSONL row per extracted trade-ish item.
"""
import json, re, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "discord_data", "futures-alerts.json")
OUT = os.path.join(ROOT, "research", "corpus_sf", "futures_alerts.jsonl")
ET = ZoneInfo("America/New_York")

# ---------------------------------------------------------------- symbols
SYMBOLS = {
    "NQ": "NQ", "MNQ": "MNQ", "ES": "ES", "MES": "MES",
    "RTY": "RTY", "M2K": "M2K", "YM": "YM", "MYM": "MYM",
    "NASDAQ": "NQ", "NAS": "NQ",
}
SYM_RE = re.compile(r"\b(MNQ|MES|MYM|M2K|NQ|ES|RTY|YM|NASDAQ)\b", re.I)

PLAUSIBLE = {  # rough contract price bands, used to reject non-price numbers
    "ES": (3000, 12000), "MES": (3000, 12000),
    "NQ": (10000, 60000), "MNQ": (10000, 60000),
    "RTY": (1500, 4000), "M2K": (1500, 4000),
    "YM": (30000, 70000), "MYM": (30000, 70000),
}
ANY_BAND = (1500, 70000)

# ---------------------------------------------------------------- direction
# "bullish gap" / "bearish signal" name an object; they are not a directional call
OBJ_EXCL = r"\b%s\b(?!\s+(?:gap|gaps|structure|order block|imbalance|candle|fvg|signal|divergence))"
LONG_CUES = [
    r"\bbuy setup\b", r"\bfor longs?\b", r"\blongs?\b", r"\bbuying\b", OBJ_EXCL % "bullish",
    r"\bbounce\b", r"\bbouncing\b", r"\breclaim\b", r"\bacceptance (?:above|over)\b",
    r"\bbuys\b", r"\bbuy order\b",
    r"\btrend(?:ing)? (?:above|over)\b", r"\bbreak (?:above|over)\b", r"\bupside\b",
    r"✅", r"\U0001F7E2",
]
SHORT_CUES = [
    r"\bsell setup\b", r"\bfor shorts?\b", r"\bshorts?\b", r"\bselling\b", OBJ_EXCL % "bearish",
    r"\breject(?:ion|s|ed)?\b", r"\bacceptance (?:below|under)\b", r"\bfade\b",
    r"\bsells\b", r"\bsell order\b",
    r"\btrend(?:ing)? (?:below|under)\b", r"\bdownside\b", r"\bpop and fade\b",
    r"\U0001F534",
]
LONG_STRONG = re.compile(r"\bbuy setup\b|\bfor longs?\b|\U0001F7E2|\bbuy signal\b", re.I)
SHORT_STRONG = re.compile(r"\bsell setup\b|\bfor shorts?\b|\U0001F534|\bsell signal\b", re.I)
LONG_RE = re.compile("|".join(LONG_CUES), re.I)
SHORT_RE = re.compile("|".join(SHORT_CUES), re.I)

# ---------------------------------------------------------------- setup
BR_RE = re.compile(r"\bbreak(?:\s|-)?(?:and|&|\+)?(?:\s|-)?retest\b|\bB&R\b", re.I)
OCR_RE = re.compile(r"\bone[\s-]?candle\b|\b1[\s-]?candle\b|\bOCR\b", re.I)
OTHER_SETUP_RE = re.compile(
    r"\b(?:buy|sell) setup\b|\bdiverg\w*\b|\bsweep\b|\bpop and fade\b|\blevel (?:reject|bounce)\b"
    r"|\bdisplacement\b|\bfailure setup\b|\bflag\b|\bacceptance\b|\breject\w*\b|\bbounce\b"
    r"|\bgap fill\b|\bretrace\w*\b|\bpullback\b", re.I)

# ---------------------------------------------------------------- levels
LEVEL_PATTERNS = [
    ("pdh", r"\b(?:PDH|previous day (?:high|highs)|prev(?:ious)? day high|yesterday'?s? high)\b"),
    ("pdl", r"\b(?:PDL|previous day (?:low|lows)|prev(?:ious)? day low|yesterday'?s? low)\b"),
    ("pmh", r"\b(?:PMH|pre-?market high|premarket highs?|PM high)\b"),
    ("pml", r"\b(?:PML|pre-?market low|premarket lows?|PM low)\b"),
    ("hod", r"\b(?:HOD|high of (?:the )?day|day high)\b"),
    ("lod", r"\b(?:LOD|low of (?:the )?day|day low)\b"),
    ("or_high", r"\b(?:opening range high|OR high|ORH)\b"),
]
LEVEL_RES = [(n, re.compile(p, re.I)) for n, p in LEVEL_PATTERNS]
# room-specific named levels -> schema "other", raw label preserved in level_name_raw
RAW_LEVEL_RES = [
    ("opening_print", re.compile(r"\bopening print\b|\bOP\b")),
    ("london_high", re.compile(r"\blondon (?:high|highs)\b", re.I)),
    ("london_low", re.compile(r"\blondon (?:low|lows)\b", re.I)),
    ("asia_high", re.compile(r"\basia(?:n)? (?:high|highs)\b", re.I)),
    ("asia_low", re.compile(r"\basia(?:n)? (?:low|lows)\b", re.I)),
    ("overnight_high", re.compile(r"\bovernight (?:high|highs)\b", re.I)),
    ("overnight_low", re.compile(r"\bovernight (?:low|lows)\b", re.I)),
    ("ath", re.compile(r"\bATH\b|\ball[- ]time high\b", re.I)),
    ("gap", re.compile(r"\b(?:\d+\s*(?:m|min|hr|h|hour)\s*)?(?:bearish |bullish )?gap(?: fill)?\b|\bNWOG\b|\bnew week opening gap\b", re.I)),
    ("session_high", re.compile(r"\bsession (?:high|highs)\b|\brange high\b", re.I)),
    ("session_low", re.compile(r"\bsession (?:low|lows)\b|\brange low\b", re.I)),
    ("data_high", re.compile(r"\bdata high\b|\bnews high\b", re.I)),
    ("data_low", re.compile(r"\bdata low\b|\bnews low\b", re.I)),
    ("psych", re.compile(r"\bpsych(?:ological)? (?:number|level)\b", re.I)),
]

# ---------------------------------------------------------------- numbers
NUM = r"\d{1,2},?\d{3}(?:\.\d{1,2})?"
NUM_RE = re.compile(NUM)
BAD_SUFFIX = re.compile(r"^\s*(?:%|k\b|pts?\b|points?\b|am\b|pm\b|EST|ET|m\b|min|hr|R\b|contracts?)", re.I)
BAD_PREFIX = re.compile(r"(?:\$|#)\s*$")

TARGET_RE = re.compile(
    r"\b(?:targets?|targeting|PT|TP|take profit|aim(?:ing)? for|draws? (?:to|at)"
    r"|go(?:ing|es)? for|we can see|could see|room to)\b[^\n]{0,90}"
    r"|(?<!want )(?<!like )(?<!hope )(?<!need )\bto see\b[^\n]{0,90}", re.I)
# "25880 next target", "20337 is the draw" -- number stated before the keyword
REV_TARGET_RE = re.compile(
    r"(" + NUM + r")\b[\s,]*"
    r"(?:[^\n]{0,40}?\b(?:is|was|would be|can (?:also )?be|as|remains)\s+"
    r"(?:\w+ ){0,3})?\b(?:next target|target|draw)\b", re.I)
STOP_RE = re.compile(r"\b(?:stop(?:\s*loss)?|SL)\b\s*(?:is|at|@|=|:)?\s*(" + NUM + r")", re.I)
ENTRY_RE = re.compile(
    r"\b(?:entry|entered|filled|got in|in at|took (?:a )?(?:long|short)"
    r"|(?:buy|sell|limit) order)\b[^\n]{0,25}?[@:]?\s*(" + NUM + r")", re.I)

# ---------------------------------------------------------------- outcome
WIN_RE = re.compile(
    r"\btargets? (?:1 |2 |one |two )?(?:hit|reached|tagged)\b|\bhit (?:first |1st |2nd |final )?target\b"
    r"|\btook out (?:first |1st |the )?target\b|\bfull target\b|\bnice winner\b|\bgreen day\b"
    r"|\bwinner\b|\bbanked\b|\btook profits?\b|\btaking profits?\b|\btook partials?\b"
    r"|\bscaled out\b|\btrimmed\b", re.I)
LOSS_RE = re.compile(
    r"\btook (?:a|the|my) (?:\d*\.?\d*\s*R\s*)?(?:stop|loss)\b|\bstopped out\b|\bstopped me out\b"
    r"|\beat (?:a|the) stop\b|\bred day\b|\bloss on the day\b|\bdown [\d.]+\s*R\b|\btook a stop\b"
    r"|\b\d*\.?\d*R loss\b", re.I)
BE_RE = re.compile(r"\bstopped (?:out )?(?:at|for|@) ?BE\b|\bbreak\s?even\b|\bstops? (?:at|for) BE\b|\bBE stop\b", re.I)
R_RE = re.compile(r"(?<![\w.])(\d{1,2}(?:\.\d{1,2})?|\.\d{1,2})\s*R\b(?![\w])")

MENTION_RE = re.compile(r"<[@#]!?&?\d+>|@everyone|@here", re.I)
URL_RE = re.compile(r"https?://\S+")
# single-name equities discussed in passing -- not futures, drop when no contract is named
EQUITY_RE = re.compile(
    r"\b(?:TSLA|NVDA|AAPL|MSFT|AMZN|META|GOOGL?|SPY|QQQ|IWM|AMD|NFLX|PLTR|AVGO|COIN|MSTR|SMCI)\b", re.I)

PLAN_HINT = re.compile(
    r"\b(?:buy setup|sell setup|watchlist|targets?|PT\b|reject|acceptance|bounce"
    r"|trend (?:above|below|under|over|lower|higher)|we can see|could see|go(?:ing)? for"
    r"|for longs?|for shorts?)|[\U0001F7E2\U0001F534\U0001F680✅☑]", re.I)

# negation guard: "not looking for shorts", "shorts off table", "no longs today"
NEG_RE = re.compile(
    r"\b(?:not|no|dont|don't|doesn't|isn't|aren't|never|avoid|avoiding|without|hard to|unless)\b",
    re.I)
OFF_TABLE_RE = re.compile(r"\b(?:off (?:the )?table|not on the table|off charts)\b", re.I)
AMBIG_RE = re.compile(
    r"\b(?:either way|either direction|either side|both sides|both directions"
    r"|or go (?:lower|higher)|or lower|or higher|go either)\b", re.I)
# a directional word strong enough that its presence on the opposite side kills the call
LONG_TRADE_RE = re.compile(r"\b(?:longs?|buys|buying|buy setup|buy signal|buy order)\b", re.I)
SHORT_TRADE_RE = re.compile(r"\b(?:shorts?|sells|selling|sell setup|sell signal|sell order)\b", re.I)


def to_et(ts):
    return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc).astimezone(ET).isoformat()


def clean(t):
    return MENTION_RE.sub(" ", URL_RE.sub(" ", t))


def parse_num(s):
    return float(s.replace(",", ""))


def price_at(text, m):
    tail = text[m.end():m.end() + 12]
    head = text[max(0, m.start() - 3):m.start()]
    if BAD_SUFFIX.match(tail) or BAD_PREFIX.search(head):
        return None
    v = parse_num(m.group(0))
    if not (ANY_BAND[0] <= v <= ANY_BAND[1]):
        return None
    if 2020 <= v <= 2035 and "." not in m.group(0) and "," not in m.group(0):
        return None  # bare year
    return v


def prices_in(text, symbol=None):
    out = []
    for m in NUM_RE.finditer(text):
        v = price_at(text, m)
        if v is None:
            continue
        if symbol and symbol in PLAUSIBLE:
            lo, hi = PLAUSIBLE[symbol]
            if not (lo <= v <= hi):
                continue
        out.append((m.start(), v))
    return out


def find_symbol(text):
    m = SYM_RE.search(text)
    return SYMBOLS[m.group(1).upper()] if m else None


def _negated(text, m):
    """True if a negation governs the cue match `m` (within 45 chars before it)."""
    if m is None:
        return False
    window = text[max(0, m.start() - 45):m.start()]
    if NEG_RE.search(window):
        return True
    return bool(OFF_TABLE_RE.search(text[m.start():m.start() + 40]))


def find_direction(text):
    if AMBIG_RE.search(text):
        return None, None
    lm, sm = LONG_STRONG.search(text), SHORT_STRONG.search(text)
    ls, ss = (lm is not None and not _negated(text, lm)), (sm is not None and not _negated(text, sm))
    ltm, stm = LONG_TRADE_RE.search(text), SHORT_TRADE_RE.search(text)
    lt = ltm is not None and not _negated(text, ltm)
    st = stm is not None and not _negated(text, stm)
    if ls and ss:
        return None, None
    # a strong call on one side is void if the other side is named as a trade too
    if ls:
        return (None, None) if st else ("long", "strong")
    if ss:
        return (None, None) if lt else ("short", "strong")
    lw, sw = LONG_RE.search(text), SHORT_RE.search(text)
    lwk = lw is not None and not _negated(text, lw)
    swk = sw is not None and not _negated(text, sw)
    if lwk and not swk:
        return "long", "weak"
    if swk and not lwk:
        return "short", "weak"
    return None, None


def find_setup(text):
    br, ocr = bool(BR_RE.search(text)), bool(OCR_RE.search(text))
    if br and ocr:
        return "br_ocr"
    if br:
        return "break_retest"
    if ocr:
        return "one_candle"
    return "other" if OTHER_SETUP_RE.search(text) else None


def level_hits(text):
    """All named-level mentions in `text` as (pos, level_name, level_name_raw)."""
    hits = []
    for n, rx in LEVEL_RES:
        for m in rx.finditer(text):
            hits.append((m.start(), n, n))
    for n, rx in RAW_LEVEL_RES:
        for m in rx.finditer(text):
            hits.append((m.start(), "other", n))
    hits.sort()
    return hits


def find_level(text):
    hits = level_hits(text)
    if not hits:
        return None, None, None
    pos, n, raw = hits[0]
    return n, raw, pos


def target_price(text, symbol):
    """First stated target price and the span of the clause that stated it."""
    m = TARGET_RE.search(text)
    if m:
        ps = prices_in(m.group(0), symbol)
        if ps:
            return ps[0][1], m.span()
    rm = REV_TARGET_RE.search(text)
    if rm:
        v = parse_num(rm.group(1))
        if ANY_BAND[0] <= v <= ANY_BAND[1] and not (2020 <= v <= 2035 and "." not in rm.group(1)):
            if not symbol or symbol not in PLAUSIBLE or PLAUSIBLE[symbol][0] <= v <= PLAUSIBLE[symbol][1]:
                return v, rm.span()
    return None, (m.span() if m else None)


def find_outcome(text):
    if BE_RE.search(text):
        return "be"
    win, loss = bool(WIN_RE.search(text)), bool(LOSS_RE.search(text))
    if win and not loss:
        return "win"
    if loss and not win:
        return "loss"
    return None


def find_r(text, outcome):
    m = R_RE.search(text)
    if not m:
        return None
    v = float(m.group(1))
    if v > 20:
        return None
    window = text[max(0, m.start() - 25):m.start() + 12]
    neg = re.search(r"\b(?:down|lost|lose|losing|loss|took (?:a|the|my))\b", window, re.I)
    if outcome == "loss" or (neg and outcome != "win"):
        return -v
    return v


def parse_message(msg):
    raw = msg.get("content") or ""
    text = clean(raw)
    if not text.strip():
        return []
    rows = []
    lines = [l for l in text.split("\n") if l.strip()]
    multi = len(lines) > 1 and sum(
        1 for l in lines if PLAN_HINT.search(l) or find_direction(l)[0]) >= 2
    units = []
    if multi:
        ctx_sym = None
        for l in lines:
            s = find_symbol(l)
            if s:
                ctx_sym = s
            if PLAN_HINT.search(l) or find_direction(l)[0]:
                units.append((l, ctx_sym, bool(s)))
    else:
        units.append((text, find_symbol(text), True))

    for unit, sym, sym_explicit in units:
        d, dstr = find_direction(unit)
        # a weak cue inside long prose is commentary, not a directional call
        if dstr == "weak" and len(unit) > 180:
            d, dstr = None, None
        setup = find_setup(unit)
        tgt, tspan = target_price(unit, sym)
        # everything from the first target keyword on is about the target, not the
        # entry level -- in this room the target clause always closes the sentence
        masked = list(unit)
        cut = len(unit)
        tm = TARGET_RE.search(unit)
        if tm:
            cut = tm.start()
        for i in range(cut, len(unit)):
            masked[i] = " "
        if tspan:
            for i in range(*tspan):
                masked[i] = " "
        masked = "".join(masked)
        lprice = lpos = None
        for start, v in prices_in(masked, sym):
            lprice, lpos = v, start
            break
        if tgt is not None and lprice == tgt:
            lprice = lpos = None
        # bind the level NAME to the level price when one is adjacent (<=25 chars),
        # otherwise fall back to the first level named outside any target clause
        hits = level_hits(masked)
        lname = lraw = None
        if hits:
            if lpos is not None:
                lend = lpos + len(str(lprice))
                near = [h for h in hits
                        if -12 <= h[0] - lend <= 12 or -12 <= lpos - h[0] <= 12]
                if near:
                    lname, lraw = near[0][1], near[0][2]
            else:
                lname, lraw = hits[0][1], hits[0][2]
        stop = None
        ms = STOP_RE.search(unit)
        if ms:
            v = parse_num(ms.group(1))
            if ANY_BAND[0] <= v <= ANY_BAND[1]:
                stop = v
        entry = None
        me = ENTRY_RE.search(unit)
        if me:
            v = parse_num(me.group(1))
            if ANY_BAND[0] <= v <= ANY_BAND[1]:
                entry = v
        if lprice is not None and lprice in (entry, stop):
            lprice = lpos = None
        outcome = find_outcome(unit)
        r = find_r(unit, outcome)

        if sym is None and EQUITY_RE.search(unit) and outcome is None and r is None:
            continue
        keep = (bool(d) or outcome or r is not None
                or tgt is not None or lprice is not None
                or stop is not None or entry is not None
                or lname is not None)
        if not keep:
            continue

        if dstr == "strong" and sym and sym_explicit and (tgt or lprice):
            conf = "high"
        elif outcome and r is not None:
            conf = "high"
        elif (d and sym) or outcome or (sym and tgt):
            conf = "medium"
        else:
            conf = "low"
        if d and not sym_explicit and conf == "medium":
            conf = "low"

        rows.append({
            "src": "discord_data/futures-alerts.json",
            "msg_id": msg["id"],
            "ts": to_et(msg["ts"]),
            "author": msg["author"],
            "instrument": "futures",
            "symbol": sym,
            "direction": d,
            "setup": setup,
            "level_price": lprice,
            "level_name": lname,
            "level_name_raw": lraw,
            "entry": entry,
            "stop": stop,
            "target": tgt,
            "outcome": outcome,
            "r_multiple": r,
            "quote": (unit.strip() if multi else raw),
            "image_urls": list(msg.get("attachments") or []),
            "confidence": conf,
        })
    return rows


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    out, skipped = [], []
    for m in data:
        rs = parse_message(m)
        if rs:
            out.extend(rs)
        else:
            skipped.append(m["id"])
    with open(OUT, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("messages=%d rows=%d msgs_with_rows=%d skipped=%d" % (
        len(data), len(out), len(data) - len(skipped), len(skipped)))
    return out, skipped


if __name__ == "__main__":
    main()
