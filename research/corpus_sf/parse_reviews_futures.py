#!/usr/bin/env python
"""Deterministic parser for discord_data/futures-trade-reviews.json.

MambaTrades' futures trade-review channel: mostly YouTube review posts carrying
symbol + dollar P&L, two premarket gameplans carrying numeric levels/targets,
and one live-commentary session (2025-05-12, 2025-10-31).

NOT Austin's marks. Output lives only under research/corpus_sf/.

Emits:
  research/corpus_sf/reviews_futures.jsonl  - one row per extracted trade item
  research/corpus_sf/maxims_futures.jsonl   - process/psychology one-liners that
                                              carry no trade fields (side file)
  research/corpus_sf/_skipped_futures.jsonl - audit trail of every skipped msg

Three keys beyond the requested schema (the channel's dominant payload is
dollars and a video link, which the requested schema cannot hold):
  pnl_usd, video_url, trade_date
r_multiple is always null: the channel never speaks in R.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

SRC = "discord_data/futures-trade-reviews.json"
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, "research", "corpus_sf")

# ---------------------------------------------------------------- time
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    ET = timezone(timedelta(hours=-4))


def to_et(ts):
    """Export stamps are naive UTC (13:17 UTC on a premarket gameplan = 09:17 ET)."""
    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.astimezone(ET).isoformat()


# ---------------------------------------------------------------- symbols
SYMBOL_RE = re.compile(r"\b(MNQ|NQ|MES|ES|YM|RTY|CL|GC)\b")
GOLD_RE = re.compile(r"\bgold\b", re.I)
# plausible price bands, used to reject percentages, volumes, dates, typos
BANDS = {
    "NQ": (10000, 40000), "MNQ": (10000, 40000),
    "ES": (3000, 9000), "MES": (3000, 9000),
    "YM": (25000, 60000), "RTY": (1000, 4000),
    "CL": (20, 200), "GC": (1000, 6000),
}


def find_symbols(text):
    """Symbols in order of first appearance; 'Gold Futures ... with NQ Recap' -> GC first."""
    hits = [(m.start(), m.group(1)) for m in SYMBOL_RE.finditer(text)]
    g = GOLD_RE.search(text)
    if g and not any(sym == "GC" for _, sym in hits):
        hits.append((g.start(), "GC"))
    hits.sort()
    out = []
    for _, sym in hits:
        if sym not in out:
            out.append(sym)
    return out


# ---------------------------------------------------------------- direction
# "think long term" / "long run" are not a direction
LONG_RE = re.compile(r"\b(longs?(?!\s+(?:term|run|haul))|buy setups?|bullish)\b", re.I)
SHORT_RE = re.compile(r"\b(shorts?|sell setups?|bearish)\b", re.I)
NEG_LONG = re.compile(r"\b(no|not|never|dont|don't|avoid)\b[^.!?\n]{0,34}\blongs?\b", re.I)
NEG_SHORT = re.compile(r"\b(no|not|never|dont|don't|avoid)\b[^.!?\n]{0,34}\bshorts?\b", re.I)


def direction_of(text):
    has_l = bool(LONG_RE.search(text)) and not NEG_LONG.search(text)
    has_s = bool(SHORT_RE.search(text)) and not NEG_SHORT.search(text)
    if has_l and not has_s:
        return "long"
    if has_s and not has_l:
        return "short"
    return None


# ---------------------------------------------------------------- setup
BR_RE = re.compile(r"\bre-?test|\bpull ?backs?\b|\bbounce\b|\breclaim|\bretrace", re.I)
OCR_RE = re.compile(r"\bone[- ]candle\b|\bOCR\b|\b\d+m close\b|\bdisplacement\b|\bstrong close\b", re.I)
OTHER_SETUP_RE = re.compile(
    r"\bdivergence\b|\bswept?\b|\bsweep\b|\bgap\b|\btrend above\b|\btrend below\b"
    r"|\b(?:buy|sell|longs?|shorts?|trade|this)\s+setups?\b"
    r"|\bsetups?\s+(?:above|below|over|under|at|@)\b", re.I)


def setup_of(text):
    br = bool(BR_RE.search(text))
    ocr = bool(OCR_RE.search(text))
    if br and ocr:
        return "br_ocr"
    if br:
        return "break_retest"
    if ocr:
        return "one_candle"
    if OTHER_SETUP_RE.search(text):
        return "other"
    return None


# ---------------------------------------------------------------- levels
LEVEL_NAMES = [
    (re.compile(r"\bpre[- ]?market highs?\b|\bpremkt highs?\b|\bPMH\b", re.I), "pmh"),
    (re.compile(r"\bpre[- ]?market lows?\b|\bpremkt lows?\b|\bPML\b", re.I), "pml"),
    (re.compile(r"\b(previous|prior|prev)\s+day'?s?\s+highs?\b|\bPDH\b", re.I), "pdh"),
    (re.compile(r"\b(previous|prior|prev)\s+day'?s?\s+lows?\b|\bPDL\b", re.I), "pdl"),
    (re.compile(r"\bopening range highs?\b|\bOR high\b|\bORH\b", re.I), "or_high"),
    (re.compile(r"\bhigh of (the )?day\b|\bHOD\b", re.I), "hod"),
    (re.compile(r"\blow of (the )?day\b|\bLOD\b", re.I), "lod"),
    (re.compile(r"\bovernight (highs?|lows?)\b|\basia (highs?|lows?)\b|\blondon (highs?|lows?)\b"
                r"|\bsession (highs?|lows?)\b|\bmidpoint\b|\bOP\b|\blevels?\b", re.I), "other"),
]


def level_name_of(text):
    for rx, name in LEVEL_NAMES:
        if rx.search(text):
            return name
    return None


NUM_RE = re.compile(r"(?<![\w.$])(\d{2,6}(?:\.\d{1,2})?)(?![\w%])")


def numbers_in(text, sym):
    """Plausible price levels for `sym`, in order of appearance."""
    lo, hi = BANDS.get(sym, (0, 10 ** 9))
    out = []
    for m in NUM_RE.finditer(text):
        raw = m.group(1)
        # reject volumes ("394k"), percentages handled by the lookahead
        if text[m.end():m.end() + 1].lower() == "k":
            continue
        v = float(raw)
        if lo <= v <= hi:
            out.append(v)
    return out


TARGET_RE = re.compile(r"\b(?:target|targets|PT\d?|TP)\b[^\n]*", re.I)
TRIGGER_RE = re.compile(r"\b(?:over|above|below|under|bounce\s*@|bounce at|@|reject[s]?|trend above|trend below)\b[^\n]*", re.I)


def levels_for(text, sym, strict=False):
    """(level_price, target) using trigger/target phrasing, band-filtered.

    strict=True (no symbol known, so no band to filter on): take a number only
    when an explicit trigger/target phrase introduces it, never the fallback.
    """
    target = None
    tm = TARGET_RE.search(text)
    if tm:
        nums = numbers_in(tm.group(0), sym)
        if nums:
            target = nums[0]
    level = None
    head = text[:tm.start()] if tm else text
    trg = TRIGGER_RE.search(head)
    if trg:
        nums = numbers_in(trg.group(0), sym)
        if nums:
            level = nums[0]
    if level is None and not strict:
        nums = [n for n in numbers_in(head, sym)]
        if nums:
            level = nums[0]
    if level is not None and level == target:
        level = None
    return level, target


# ---------------------------------------------------------------- outcome / money
LOST_RE = re.compile(r"\blost\s*\$?\s*([\d,]+)", re.I)
MONEY_RE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)")
MADE_BARE_RE = re.compile(r"\bMade\s+([\d,]{3,7})\b")
RED_RE = re.compile(r"\bred day\b", re.I)
WIN_WORD_RE = re.compile(r"\bprofits?\b|\bmade\b|\bwinner\b|\bgreen day\b", re.I)


def money_outcome(text):
    """(outcome, pnl_usd). 'Lost $X yesterday. Made $Y today' -> win, Y."""
    lost = [m.group(0) for m in LOST_RE.finditer(text)]
    scrubbed = text
    for l in lost:
        scrubbed = scrubbed.replace(l, " ")
    vals = [float(v.replace(",", "")) for v in MONEY_RE.findall(scrubbed)]
    if not vals:
        vals = [float(v.replace(",", "")) for v in MADE_BARE_RE.findall(scrubbed)]
    vals = [v for v in vals if v >= 50]  # a review P&L, not a price fragment
    if vals:
        return "win", vals[0]
    if re.search(r"\bwinner\b|\bgreen day\b", text, re.I):
        return "win", None
    if RED_RE.search(text):
        return "loss", None
    if lost and not WIN_WORD_RE.search(scrubbed):
        v = float(LOST_RE.search(text).group(1).replace(",", ""))
        return "loss", v
    return None, None


# ---------------------------------------------------------------- misc
YT_RE = re.compile(r"https?://(?:youtu\.be/[\w-]+|(?:www\.)?youtube\.com/watch\?v=[\w-]+)")
# slash form may omit the year ("8/15"); dash form must carry one ("3-17-25"),
# otherwise "2-3 high quality trades per week" reads as a date
DATE_RE = re.compile(r"\b(?:(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?|(\d{1,2})-(\d{1,2})-(\d{2,4}))\b")
UPLOAD_RE = re.compile(r"upload|sent the wrong link|just sent an updated", re.I)
MAXIM_RE = re.compile(
    r"\bdiscipline\b|\bprocess\b|\bpatience\b|\bpsychology\b|\brules?\b|\bgameplan\b|\bedge\b|"
    r"\bbad trade\b|\bchop\b|\bprotecting profits\b|\bmarathon\b|\bA\+ setups?\b|\bwait for\b|"
    r"\bdont get married\b|\bdon't get married\b", re.I)
# a stated reason for standing down / staying out: no trade fields, but it is a
# mentor judgement, so it belongs in the maxims side file rather than in nothing
REASON_RE = re.compile(
    r"\bdon'?t love\b|\bnot (?:super )?interested\b|\bhigher tf\b|\buptrend\b|\bdowntrend\b"
    r"|\btoo choppy\b|\bno positions\b|\bno entries\b|\bnot much entries\b", re.I)
IMG_RE = re.compile(r"\.(png|jpe?g|gif|webp)(\?|$)", re.I)


def trade_date_of(text, et_iso):
    """Explicit date in the title, e.g. 'NQ Trade Review $4179 (7/7/26)'."""
    yr = int(et_iso[:4])
    for m in DATE_RE.finditer(text):
        mm, dd, yy = (m.group(1), m.group(2), m.group(3)) if m.group(1) \
            else (m.group(4), m.group(5), m.group(6))
        mm, dd = int(mm), int(dd)
        if not (1 <= mm <= 12 and 1 <= dd <= 31):
            continue
        if yy:
            y = int(yy)
            y = y + 2000 if y < 100 else y
        else:
            y = yr
        try:
            return datetime(y, mm, dd).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def image_urls(msg):
    return [u for u in msg.get("attachments", []) if IMG_RE.search(u)] or \
           [u for u in msg.get("attachments", [])]


# ---------------------------------------------------------------- watchlist rows
WATCHLIST_HDR = re.compile(r"^\s*watchlist\s*$", re.I | re.M)


def watchlist_lines(content):
    m = WATCHLIST_HDR.search(content)
    if not m:
        return []
    body = content[m.end():]
    rows, cur, cur_dir = [], None, None
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("@"):
            continue
        syms = find_symbols(line)
        if syms:
            cur = syms[0]
            cur_dir = direction_of(line)
            rows.append((cur, cur_dir, line))
        elif line.startswith("-") and cur:
            rows.append((cur, direction_of(line) or cur_dir, line))
        elif cur and re.search(r"\bsetups?\b|\btarget\b|\bopen to\b", line, re.I):
            # a bare continuation line ("open to shorts") names no symbol and the
            # last-seen one is often the wrong one -- leave symbol null
            rows.append((None, direction_of(line) or cur_dir, line))
    return rows


# ---------------------------------------------------------------- main
def parse(msg):
    """-> (rows, maxims, skip_reason)"""
    content = msg.get("content", "") or ""
    text = content.strip()
    et = to_et(msg["ts"])
    base = dict(src=os.path.basename(SRC), msg_id=msg["id"], ts=et, author=msg["author"])
    imgs = image_urls(msg)
    yt = YT_RE.search(content)
    video = yt.group(0) if yt else (msg.get("embeds") or [None])[0]

    if not text:
        if imgs:
            return [dict(base, symbol=None, direction=None, setup=None,
                         level_price=None, level_name=None, entry=None, stop=None,
                         target=None, outcome=None, r_multiple=None, quote="",
                         image_urls=imgs, confidence="low", pnl_usd=None,
                         video_url=None, trade_date=et[:10])], [], None
        return [], [], "empty_content"
    if UPLOAD_RE.search(text) and len(text) < 90:
        return [], [], "upload_notice"

    rows = []
    wl = watchlist_lines(content)
    if wl:
        # premarket gameplan: one row per watchlist setup line
        for sym, d, line in wl:
            lvl, tgt = levels_for(line, sym, strict=(sym is None))
            conf = "high" if (sym and d and (lvl is not None or tgt is not None)) else \
                   ("medium" if sym or d else "low")
            rows.append(dict(base, symbol=sym, direction=d, setup=setup_of(line),
                             level_price=lvl, level_name=level_name_of(line),
                             entry=None, stop=None, target=tgt,
                             outcome=None, r_multiple=None,
                             quote=line, image_urls=imgs, confidence=conf,
                             pnl_usd=None, video_url=video,
                             trade_date=trade_date_of("", et) or et[:10]))
        return rows, [], None

    syms = find_symbols(text)
    outcome, pnl = money_outcome(text)
    direction = direction_of(text)
    setup = setup_of(text)
    lname = level_name_of(text)
    sym = syms[0] if syms else None
    lvl, tgt = levels_for(text, sym, strict=(sym is None))
    if outcome is not None:
        lvl, tgt = None, None  # review titles carry P&L, not levels

    informative = any([sym, direction, outcome, lname, video])
    if not informative:
        if MAXIM_RE.search(text) or REASON_RE.search(text) or len(text) > 60:
            return [], [dict(base, quote=text, image_urls=imgs)], "maxim_no_trade_fields"
        return [], [], "chatter_no_fields"

    filled = sum(x is not None for x in (sym, direction, outcome, lvl, tgt, lname))
    if outcome is not None and sym:
        conf = "high"
    elif filled >= 3:
        conf = "medium" if not sym else "high"
    elif filled >= 2:
        conf = "medium"
    else:
        conf = "low"

    rows.append(dict(base, symbol=sym, direction=direction, setup=setup,
                     level_price=lvl, level_name=lname,
                     entry=None, stop=None, target=tgt,
                     outcome=outcome, r_multiple=None,
                     quote=text, image_urls=imgs, confidence=conf,
                     pnl_usd=pnl, video_url=video,
                     trade_date=trade_date_of(text, et) or (et[:10] if video else None)))
    return rows, [], None


def main():
    path = os.path.join(REPO, SRC)
    msgs = json.load(open(path, encoding="utf-8"))
    rows, maxims, skipped = [], [], []
    for m in msgs:
        r, mx, why = parse(m)
        rows.extend(r)
        maxims.extend(mx)
        if why:
            skipped.append(dict(msg_id=m["id"], ts=to_et(m["ts"]), reason=why,
                                quote=(m.get("content") or "")[:400]))
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, data in (("reviews_futures.jsonl", rows),
                       ("maxims_futures.jsonl", maxims),
                       ("_skipped_futures.jsonl", skipped)):
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
            for o in data:
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print(f"messages={len(msgs)} extracted={len(rows)} maxims={len(maxims)} skipped={len(skipped)}")
    for k in ("symbol", "direction", "setup", "level_name", "outcome", "level_price",
              "target", "pnl_usd", "video_url", "trade_date"):
        print(f"  with_{k}={sum(1 for r in rows if r.get(k) is not None)}")
    from collections import Counter
    print("  conf:", Counter(r["confidence"] for r in rows).most_common())
    print("  skip reasons:", Counter(s["reason"] for s in skipped).most_common())
    print("  symbols:", Counter(r["symbol"] for r in rows).most_common())


if __name__ == "__main__":
    main()
