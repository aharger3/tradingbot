#!/usr/bin/env python
"""Grade the engine's level set against the levels humans actually name.

Austin: "I watch exactly SIX day-trade levels" + suspicion that a
higher-timeframe level set is polluting them.

Three stages, all deterministic (regex + arithmetic, no LLM anywhere):

  A. USABILITY AUDIT of research/corpus_sf/premarket_charts.jsonl -- the file
     the task names as the source of premarket-drawn levels.
  B. HUMAN LEVEL PARSER. My own regex over the raw `quote` text of every
     corpus_sf row. Does NOT trust the mining pass's `level_name` field; that
     field is re-derived here and the two are cross-tabulated so disagreement
     is visible.
  C. ENGINE LEVEL SET per (symbol, session_date), replicated bar-for-bar from
     signal_runner's own construction against the local 1m archive, then
     HIT / MISS / EXTRA and the price-distance distribution.

Read-only on every Austin mark corpus. Writes only under research/corpus_sf/.

Run:  python research/corpus_sf/grade_levels.py
"""

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SF = ROOT / "research" / "corpus_sf"
sys.path.insert(0, str(ROOT))

OUT_MD = SF / "level_grading.md"
OUT_HUMAN = SF / "human_levels.jsonl"
OUT_SAMPLE = SF / "level_parser_sample.txt"

# --------------------------------------------------------------------------
# ticker vocabulary
# --------------------------------------------------------------------------
from universe import ALL_SYMS                      # noqa: E402
from chat_vocab import GRADE_LEVELS_EXTRA_TICKERS as EXTRA_TICKERS  # noqa: E402

TICKERS = sorted(set(ALL_SYMS) | set(EXTRA_TICKERS))
TICKER_RE = re.compile(r"\b(" + "|".join(TICKERS) + r")\b", re.I)

# Words that are also valid tickers and would otherwise fire constantly.
# "U" as a ticker is hopeless in prose; "ES" appears inside no word boundary
# issue but is a real futures symbol so it stays.
TICKER_STOPWORDS = {"U"}

# --------------------------------------------------------------------------
# LEVEL VOCABULARY
#
# Ordered longest-phrase-first. Each entry: (canonical, regex).
# `sided` marks a level with a definite price on a definite side.
# `tf` is the timeframe class -- "day" is one of the six intraday references,
# "htf" is a higher-timeframe level (the pollution Austin suspects),
# "struct" is price structure with no fixed price, "generic" is unnamed.
# --------------------------------------------------------------------------
LEVEL_PATTERNS = [
    # ---- the intraday day-trade candidates ----
    ("PDH", "day", r"\bpdh\b|\bprev(?:ious)?\s+day(?:'?s)?\s+high\b|\bprior\s+day(?:'?s)?\s+high\b|\byesterday'?s?\s+high(?:s)?\b|\bprev\s+high\b"),
    ("PDL", "day", r"\bpdl\b|\bprev(?:ious)?\s+day(?:'?s)?\s+low\b|\bprior\s+day(?:'?s)?\s+low\b|\byesterday'?s?\s+low(?:s)?\b|\bprev\s+low\b"),
    ("PMH", "day", r"\bpmh\b|\bpre[-\s]?market\s+high(?:s)?\b|\bpm\s+high(?:s)?\b|\bpremkt\s+high\b"),
    ("PML", "day", r"\bpml\b|\bpre[-\s]?market\s+low(?:s)?\b|\bpm\s+low(?:s)?\b|\bpremkt\s+low\b"),
    ("ORH", "day", r"\borh\b|\bopening\s+range\s+high(?:s)?\b|\bo\.?r\.?\s+high(?:s)?\b|\bor\s+high(?:s)?\b"),
    ("ORL", "day", r"\borl\b|\bopening\s+range\s+low(?:s)?\b|\bo\.?r\.?\s+low(?:s)?\b|\bor\s+low(?:s)?\b"),
    ("OR",  "day", r"\bopening\s+range\b|\bopening\s+rang\b|\bor\s+b\s*&\s*r\b|\borb\b|\bopening\s+drive\b"),
    ("HOD", "day", r"\bhod\b|\bhigh\s+of\s+(?:the\s+)?day\b|\bday(?:'?s)?\s+high\b|\bsession\s+high\b|\bintraday\s+high\b"),
    ("LOD", "day", r"\blod\b|\blow\s+of\s+(?:the\s+)?day\b|\bday(?:'?s)?\s+low\b|\bsession\s+low\b|\bintraday\s+low\b"),
    ("PDC", "day", r"\bpdc\b|\bprev(?:ious)?\s+day(?:'?s)?\s+close\b|\bprior\s+close\b|\byesterday'?s?\s+close\b"),
    ("PDO", "day", r"\bpdo\b|\bprev(?:ious)?\s+day(?:'?s)?\s+open\b|\byesterday'?s?\s+open\b"),
    ("VWAP", "day", r"\bvwap\b"),
    ("GAPFILL", "day", r"\bgap\s+fill\b|\bfill\s+the\s+gap\b|\bgap\s+close\b"),

    # ---- higher-timeframe levels: the suspected pollution ----
    ("ATH", "htf", r"\bath'?s?\b|\ball[-\s]?time\s+high(?:s)?\b|\brecord\s+high(?:s)?\b"),
    ("ATL", "htf", r"\batl\b|\ball[-\s]?time\s+low(?:s)?\b"),
    ("52W", "htf", r"\b52[-\s]?w(?:ee)?k\s+(?:high|low)\b"),
    ("WEEKLY", "htf", r"\bweekly\s+(?:high|low|level|close|open|resistance|support)\b|\bprev(?:ious)?\s+week(?:'?s)?\s+(?:high|low|close)\b|\blast\s+week'?s?\s+(?:high|low)\b"),
    ("MONTHLY", "htf", r"\bmonthly\s+(?:high|low|level|close|open)\b|\bprev(?:ious)?\s+month(?:'?s)?\s+(?:high|low|close)\b"),
    ("DAILY_TF", "htf", r"\bdaily\s+(?:level|resistance|support|trendline|chart\s+level)\b|\bon\s+the\s+daily\b|\bdaily\s+time\s?frame\b"),
    ("SWING_HL", "htf", r"\bswing\s+(?:high|low)\b|\bmajor\s+swing\b"),

    # ---- price structure (no fixed premarket price) ----
    ("PIVOT", "struct", r"\bpivot(?:s)?\b|\bpivot\s+structure\b"),
    ("ORDERBLOCK", "struct", r"\border\s+block(?:s)?\b|\bocr\b|\bone\s+candle\s+rule\b"),
    ("FVG", "struct", r"\bfvg\b|\bfair\s+value\s+gap\b|\bimbalance\b"),
    ("TRENDLINE", "struct", r"\btrend\s?line(?:s)?\b|\bchannel\s+(?:top|bottom)\b"),
    ("SUPPLY_DEMAND", "struct", r"\bsupply\s+zone\b|\bdemand\s+zone\b"),

    # ---- unnamed ----
    ("KEYLEVEL", "generic", r"\bkey\s+level(?:s)?\b|\bkey\s+lvl\b|\bmajor\s+level(?:s)?\b"),
]
LEVEL_RE = [(name, tf, re.compile(rx, re.I)) for name, tf, rx in LEVEL_PATTERNS]

# The engine's own named set (signal_runner.detect_signals level_pairs).
ENGINE_NAMED = ["PDH", "PDL", "PMH", "PML", "ORH", "ORL"]

# A price token: 2-5 digits, optional cents. Rejects sizes and percentages by
# the guards below rather than by the number shape.
# A colon on either side means it is a clock time, not a price: "at 10:24"
# handed the ORH the number 24.
PRICE_RE = re.compile(r"(?<![\w.$:])(\d{1,5}(?:\.\d{1,2})?)(?![\w%:])")
# Contexts in which a nearby number is NOT a level price. Round 2 of the
# hand-check added the last line: "for 700$" (P&L, dollar sign TRAILING),
# "VWAP/EMA 200" (an indicator period), "Fib 382" (a ratio, not a price).
PRICE_VETO = re.compile(
    r"\$\s*\d|\d\s*\$|\bcalls?\b|\bputs?\b|\bstrike\b|\bcontracts?\b|\bcons?\b|"
    r"\d\s*%|\bR\b|\bmin(?:ute)?s?\b|\bshares?\b|\bpts?\b|\bpoints?\b|"
    r"\bpt\b|\btargets?\b|\btp\d?\b|\bstop\b|"
    r"\bema\b|\bsma\b|\bma\b|\bfib\b|\brsi\b|\batr\b|\bP&L\b|\bacct\b", re.I)

# Plausibility band for a parsed human price, applied at GRADING time (not in
# the parser, so human_levels.jsonl keeps the raw output and this gate stays
# auditable). A price further than this from the session open is not that
# symbol's level -- it is a P&L, an options fill, an indicator period or a fib
# ratio that survived the regex vetoes. 25% is deliberately coarse: the result
# it feeds measures sub-1% agreement, so this gate cannot manufacture a match,
# it can only drop non-prices.
PRICE_PLAUSIBLE_FRAC = 0.25


def find_tickers(text):
    """[(pos, ticker)] of every ticker mention, uppercased."""
    out = []
    for m in TICKER_RE.finditer(text):
        t = m.group(1).upper()
        if t in TICKER_STOPWORDS:
            continue
        # A lowercase 2-letter hit inside prose ("or", "es") is noise unless the
        # source wrote it uppercase.
        if len(t) <= 2 and m.group(1) != t:
            continue
        out.append((m.start(), t))
    return out


def find_levels(text):
    """[(pos, canonical, tf, matched_text)], deduped by span.

    Longest-first ordering matters: 'opening range high' must win over both
    'opening range' and a bare 'or high'. Overlapping spans are resolved by
    keeping the pattern that matched first in LEVEL_PATTERNS order.
    """
    claimed = []
    out = []
    for name, tf, rx in LEVEL_RE:
        for m in rx.finditer(text):
            s, e = m.span()
            if any(not (e <= cs or s >= ce) for cs, ce in claimed):
                continue
            claimed.append((s, e))
            out.append((s, name, tf, m.group(0)))
    return sorted(out)


# Price binding, tightened after the first 30-row hand-check.
#
# v1 took the nearest number within 42 chars either side. On the sample that
# was right 3 times in 6: it stole TSLA's 412 for META's PDL ("TSLA off the
# 412, AMZN off PDL, and Meta off PDL"), paired "Key Level:" with the 1st-
# candle high instead of the PM high it names, and read a profit target as a
# premarket high. All three failures share a shape — the number belongs to a
# DIFFERENT level or a different symbol that sits between it and this mention.
#
# v2 rules, each one killing one of those:
#   1. AFTER the level word wins (levels are written "PDL (529.29)", "PMH 560",
#      "Key level for NVDA 127.67"). A number BEFORE the level word only counts
#      inside PRE_WINDOW — too short to reach across a comma clause.
#   2. Nothing between. If another level mention or another ticker sits between
#      the level word and the number, the number is that other thing's price.
#   3. PT / target / stop in the neighbourhood vetoes it outright.
POST_WINDOW = 28
# A number BEFORE the level word binds only when literally adjacent ("412 PDL").
# 12 was still long enough to reach across ", AMZN off " and steal TSLA's price.
PRE_WINDOW = 6


def price_near(text, pos, span_txt, window=None,
               other_levels=(), other_ticks=(), own_sym=None):
    """The price this level mention names, or None. See the v2 rules above."""
    end = pos + len(span_txt)

    def between(a, b):
        """Is another level, or a DIFFERENT ticker, inside [a, b)?

        The level's own ticker may sit between it and its price -- "Key level
        for NVDA 127.67" is one statement, not two. Only a competing symbol
        breaks the binding.
        """
        for p, *_ in other_levels:
            if p != pos and a <= p < b:
                return True
        for p, t in other_ticks:
            if a <= p < b and t != own_sym:
                return True
        return False

    cands = []
    for m in PRICE_RE.finditer(text):
        s = m.start()
        if s >= end:
            d = s - end
            if d > POST_WINDOW or between(end, s):
                continue
            veto_lo, veto_hi = pos - 14, m.end() + 14
        else:
            d = pos - m.end()
            if d < 0 or d > PRE_WINDOW or between(m.end(), pos):
                continue
            veto_lo, veto_hi = m.start() - 14, end
        num = m.group(1)
        # Veto over the WHOLE span between level word and number (plus a
        # margin), not a fixed collar: "PT premarket high and 23700" only
        # reveals itself as a target if the "PT" is inside the window.
        if PRICE_VETO.search(text[max(0, veto_lo):min(len(text), veto_hi)]):
            continue
        v = float(num)
        if v < 3 or v > 100000:        # not an equity/index price we can grade
            continue
        if "." not in num and v < 20:  # bare small int is a count, not a price
            continue
        cands.append((d, v))
    return min(cands)[1] if cands else None


def bind_levels_to_symbols(text, row_symbol):
    """[(symbol, canonical, tf, price)] for one quote.

    Each level mention binds to the NEAREST PRECEDING ticker within
    BIND_WINDOW chars; failing that, to the nearest following ticker in the
    same window; failing that, to the row's own symbol field.
    """
    BIND_WINDOW = 90
    ticks = find_tickers(text)
    levels = find_levels(text)
    out = []
    for pos, name, tf, span_txt in levels:
        sym = None
        before = [(p, t) for p, t in ticks if p <= pos and pos - p <= BIND_WINDOW]
        if before:
            sym = before[-1][1]
        else:
            after = [(p, t) for p, t in ticks if p > pos and p - pos <= BIND_WINDOW]
            if after:
                sym = after[0][1]
        if sym is None:
            sym = (row_symbol or "").upper() or None
        if sym is None:
            continue
        out.append((sym, name, tf,
                    price_near(text, pos, span_txt, other_levels=levels,
                               other_ticks=ticks, own_sym=sym)))
    return out


# --------------------------------------------------------------------------
# STAGE A -- usability audit of the named input file
# --------------------------------------------------------------------------
def stage_a():
    p = SF / "premarket_charts.jsonl"
    rows = [json.loads(l) for l in open(p, encoding="utf-8")]
    raw = json.load(open(ROOT / "discord_data" / "premarket-charts.json",
                        encoding="utf-8"))
    a = {
        "rows": len(rows),
        "raw_msgs": len(raw),
        "payload_counts": Counter(r.get("payload") for r in rows),
        "levels_in_text_true": sum(1 for r in rows if r.get("levels_in_text")),
        "level_price_notnull": sum(1 for r in rows if r.get("level_price") is not None),
        "level_name_notnull": sum(1 for r in rows if r.get("level_name")),
        "symbol_notnull": sum(1 for r in rows if r.get("symbol")),
        "images": sum(r.get("n_images") or 0 for r in rows),
        "sessions": len({r.get("session_date") for r in rows if r.get("session_date")}),
        "authors": Counter(r.get("author") for r in rows),
    }
    # independent check straight off the raw Discord export
    dec = re.compile(r"\d{2,5}\.\d{1,2}")
    a["raw_content_with_decimal_price"] = sum(
        1 for m in raw if dec.search(m.get("content") or ""))
    a["raw_content_with_level_word"] = sum(
        1 for m in raw if find_levels(m.get("content") or ""))
    a["usable_rows"] = a["level_price_notnull"]
    return a


# --------------------------------------------------------------------------
# STAGE B -- human levels, my parser, over every corpus_sf file
# --------------------------------------------------------------------------
SKIP_FILES = {"human_levels.jsonl"}


def stage_b():
    recs = []
    per_file = Counter()
    for f in sorted(SF.glob("*.jsonl")):
        if f.name in SKIP_FILES:
            continue
        for line in open(f, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            q = r.get("quote") or ""
            if not q.strip():
                continue
            ts = r.get("ts") or ""
            day = (r.get("session_date") or ts[:10]) or None
            if not day:
                continue
            got = bind_levels_to_symbols(q, r.get("symbol"))
            if not got:
                continue
            per_file[f.name] += 1
            for sym, name, tf, price in got:
                recs.append({
                    "src_file": f.name, "msg_id": r.get("msg_id"),
                    "ts": ts, "date": day, "author": r.get("author"),
                    "symbol": sym, "level": name, "tf": tf,
                    "price": price,
                    "mined_level_name": r.get("level_name"),
                    "quote": q[:300],
                })
    with open(OUT_HUMAN, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    return recs, per_file


# --------------------------------------------------------------------------
# STAGE C -- the engine's level set, replicated from signal_runner
# --------------------------------------------------------------------------
def engine_levels(sym, day, prev_day):
    """Replicates signal_runner.detect_signals' level_pairs construction.

    Returns {"named": {NAME: price}, "extra": {NAME: price}} or None when the
    archive cannot supply the day.
    """
    import polygon_feed as pf
    from signal_runner import (pivot_levels, PIVOT_LOOKBACK, PIVOT_DEDUPE_FRAC,
                               HODLOD_PAIR)
    from omen_bot import OpeningRangeAnalyzer

    try:
        bars = pf.fetch_day(sym, day)
    except Exception:
        return None
    if not bars:
        return None
    rth = pf.rth(bars)
    if len(rth) < 30:
        return None

    pmh, pml = pf.premarket_hi_lo(bars)
    pdh = pdl = None
    if prev_day:
        try:
            pbars = pf.fetch_day(sym, prev_day)
            prth = pf.rth(pbars) if pbars else []
        except Exception:
            prth = []
        if len(prth) >= 30:
            pdh = max(c.high for c in prth)
            pdl = min(c.low for c in prth)
    orh, orl = OpeningRangeAnalyzer.get_opening_range(rth)

    named = {}
    for k, v in (("PDH", pdh), ("PDL", pdl), ("PMH", pmh), ("PML", pml),
                 ("ORH", orh), ("ORL", orl)):
        if v is not None:
            named[k] = v

    # everything the engine ALSO puts into level_pairs
    extra = {}
    active = list(named.values())
    # F3 rolling session-extreme pair (HODLOD_PAIR, default False)
    if HODLOD_PAIR:
        window = [c for c in rth if c.timestamp < "11:00:00"]
        if len(window) >= 43:
            pre = window[:-12]
            hi = max(c.high for c in pre)
            lo = min(c.low for c in pre)
            if not any(abs(hi - l) / l < 0.001 for l in active if l):
                extra["HOD"] = hi
            if not any(abs(lo - l) / l < 0.001 for l in active if l):
                extra["LOD"] = lo

    # T10 pivot structure -- counted over the traded window exactly as the
    # engine sees it: the union of every pivot live on any bar 09:30-11:00.
    piv = {}
    end = min(len(rth), sum(1 for c in rth if c.timestamp < "11:00:00"))
    for i in range(5, end):
        for p in pivot_levels(rth[:i + 1], as_of=i, lookback=PIVOT_LOOKBACK):
            if any(abs(p["price"] - l) <= PIVOT_DEDUPE_FRAC * abs(l)
                   for l in active if l):
                continue
            piv[p["name"]] = p["price"]
    extra.update(piv)
    return {"named": named, "extra": extra,
            "n_pivot": len(piv),
            "day_open": rth[0].open}


def archive_days(sym):
    d = ROOT / "data_archive" / sym
    if not d.is_dir():
        return []
    return sorted(f.stem for f in d.glob("*.csv"))


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    a = stage_a()
    recs, per_file = stage_b()

    # ---- ranking: distinct (symbol, date, level) = one level drawn that day
    drawn = {(r["symbol"], r["date"], r["level"]) for r in recs}
    rank = Counter(l for _, _, l in drawn)
    tf_of = {name: tf for name, tf, _ in LEVEL_PATTERNS}
    tf_rank = Counter(tf_of[l] for _, _, l in drawn)
    mention_rank = Counter(r["level"] for r in recs)

    # ---- stage C over symbol-days the archive can serve
    by_day = defaultdict(set)
    for r in recs:
        by_day[(r["symbol"], r["date"])].add(r["level"])

    arch = {s: archive_days(s) for s in set(k[0] for k in by_day)}
    arch = {s: d for s, d in arch.items() if d}

    gradable = []
    for (sym, day), lv in sorted(by_day.items()):
        days = arch.get(sym)
        if not days or day not in days:
            continue
        i = days.index(day)
        prev = days[i - 1] if i > 0 else None
        gradable.append((sym, day, prev, lv))

    # index priced records by symbol-day (the old inner loop rescanned all
    # 8.5k records per graded day -- O(n*m) for no reason)
    priced_by_day = defaultdict(list)
    for r in recs:
        if r["price"] is not None:
            priced_by_day[(r["symbol"], r["date"])].append(r)

    hits = Counter(); misses = Counter()
    seen_dist = set()
    implausible = 0
    extra_counts = []
    named_counts = []
    dists = []            # (symbol, day, level, human_price, engine_price, pct)
    graded_days = 0
    for sym, day, prev, lv in gradable:
        el = engine_levels(sym, day, prev)
        if el is None:
            continue
        graded_days += 1
        named_counts.append(len(el["named"]))
        extra_counts.append(len(el["extra"]))
        for name in lv:
            if name in el["named"]:
                hits[name] += 1
            elif name == "OR" and ("ORH" in el["named"] or "ORL" in el["named"]):
                hits["OR"] += 1
            else:
                misses[name] += 1
        # price distance for the levels the human actually priced
        for r in priced_by_day.get((sym, day), ()):
            ep = el["named"].get(r["level"])
            if ep is None:
                continue
            # plausibility band -- see PRICE_PLAUSIBLE_FRAC
            if abs(r["price"] - el["day_open"]) > PRICE_PLAUSIBLE_FRAC * el["day_open"]:
                implausible += 1
                continue
            pct = abs(r["price"] - ep) / ep * 100
            key = (sym, day, r["level"], round(r["price"], 2))
            if key in seen_dist:   # same statement cross-posted
                continue
            seen_dist.add(key)
            dists.append((sym, day, r["level"], r["price"], ep, pct))

    write_report(a, recs, per_file, rank, mention_rank, tf_rank, drawn,
                 by_day, gradable, graded_days, hits, misses,
                 named_counts, extra_counts, dists, implausible)
    dump_sample(recs)
    print("wrote", OUT_MD)
    print("human level records:", len(recs), "distinct symbol-day-levels:", len(drawn))
    print("gradable symbol-days:", len(gradable), "graded:", graded_days)
    print("top:", rank.most_common(12))


def dump_sample(recs, n=30):
    """Deterministic 30-row sample (every len/30-th record) for hand-checking."""
    step = max(1, len(recs) // n)
    with open(OUT_SAMPLE, "w", encoding="utf-8") as fh:
        for i, r in enumerate(recs[::step][:n]):
            fh.write("[%02d] %s %s %s  level=%s tf=%s price=%s  mined=%s\n"
                     % (i + 1, r["date"], r["src_file"], r["symbol"],
                        r["level"], r["tf"], r["price"], r["mined_level_name"]))
            fh.write("     %r\n\n" % r["quote"][:240])


def pctile(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * len(s)))]


def write_report(a, recs, per_file, rank, mention_rank, tf_rank, drawn,
                 by_day, gradable, graded_days, hits, misses,
                 named_counts, extra_counts, dists, implausible):
    L = []
    w = L.append
    w("# Level grading — the engine's levels vs the ones humans name\n")
    w("Generated by `research/corpus_sf/grade_levels.py` on "
      + datetime.now().strftime("%Y-%m-%d") + ". Deterministic parser, no LLM.\n")
    w("These are SCARFACE's / the mentors' levels. **Not Austin's marks.** "
      "Nothing here writes into any Austin mark corpus.\n")

    w("\n## 1. The named input file cannot answer the question\n")
    w("`research/corpus_sf/premarket_charts.jsonl` — **%d rows, %d usable.**\n"
      % (a["rows"], a["usable_rows"]))
    w("| field | count |")
    w("|---|---:|")
    w("| rows | %d |" % a["rows"])
    w("| raw Discord messages behind them | %d |" % a["raw_msgs"])
    w("| payload == `chart_images` | %d |" % a["payload_counts"].get("chart_images", 0))
    w("| `levels_in_text` true | %d |" % a["levels_in_text_true"])
    w("| `level_price` not null | %d |" % a["level_price_notnull"])
    w("| `level_name` not null | %d |" % a["level_name_notnull"])
    w("| `symbol` not null | %d |" % a["symbol_notnull"])
    w("| chart images attached | %d |" % a["images"])
    w("| distinct sessions | %d |" % a["sessions"])
    w("| raw message text containing a decimal price | %d |"
      % a["raw_content_with_decimal_price"])
    w("| raw message text containing any level word | %d |"
      % a["raw_content_with_level_word"])
    w("\nEvery row is a date header plus a bundle of PNGs "
      "(`\"April 2nd, 2024: @role\"` + 5–7 `cdn.discordapp.com` images). "
      "The levels were **drawn on the charts**, never typed. "
      "Zero rows carry a price, a level name, or a per-symbol binding.\n")
    w("**Per the task's stop condition: premarket_charts.jsonl has 0 usable "
      "rows for a per-symbol-day level comparison.** Extracting them needs OCR "
      "or vision over %d images, which is out of scope for a regex parser.\n"
      % a["images"])
    w("\nWhat follows uses a *different, real* source — the level names the same "
      "humans type in prose across the rest of `research/corpus_sf/` — and is "
      "labelled as such throughout. It is not a reconstruction of the charts.\n")

    w("\n## 2. Human levels parsed from prose (substitute source)\n")
    w("My own regex over the `quote` text of every `corpus_sf/*.jsonl` row. "
      "The mining pass's `level_name` field is re-derived, not trusted.\n")
    w("- level mentions extracted: **%d**" % len(recs))
    w("- distinct (symbol, date, level) — one level *drawn* for a symbol-day: "
      "**%d**" % len(drawn))
    w("- distinct symbol-days with at least one named level: **%d**" % len(by_day))
    w("\n| source file | rows contributing |")
    w("|---|---:|")
    for f, n in per_file.most_common():
        w("| `%s` | %d |" % (f, n))

    w("\n## 3. The six levels humans actually draw\n")
    w("Ranked by distinct symbol-days on which the level is named "
      "(repeat mentions inside one day collapse to one).\n")
    w("| # | level | symbol-days | share | raw mentions | timeframe | engine has it |")
    w("|---:|---|---:|---:|---:|---|---|")
    tf_of = {name: tf for name, tf, _ in LEVEL_PATTERNS}
    tot = sum(rank.values())
    for i, (lv, n) in enumerate(rank.most_common(24), 1):
        has = "yes" if lv in ENGINE_NAMED else (
            "yes (as ORH/ORL)" if lv == "OR" else
            "yes (F3, OFF)" if lv in ("HOD", "LOD") else
            "as pivots" if lv in ("PIVOT", "SWING_HL") else
            "as OCR setup" if lv == "ORDERBLOCK" else
            "as FVG setup" if lv == "FVG" else "**NO**")
        w("| %d | **%s** | %d | %.1f%% | %d | %s | %s |"
          % (i, lv, n, 100.0 * n / tot, mention_rank[lv], tf_of[lv], has))

    top6 = [lv for lv, _ in rank.most_common() if tf_of[lv] == "day"][:6]
    w("\n**Empirical answer — the six day-trade levels, by frequency:** "
      + ", ".join("`%s`" % t for t in top6) + "\n")
    eng6 = set(ENGINE_NAMED)
    w("Engine's six: " + ", ".join("`%s`" % t for t in ENGINE_NAMED) + "\n")
    w("Overlap: **%d/6** — in engine not in humans' top six: %s; "
      "in humans' top six not in engine's named set: %s\n"
      % (len(eng6 & set(top6)),
         ", ".join(sorted(eng6 - set(top6))) or "none",
         ", ".join(sorted(set(top6) - eng6)) or "none"))

    w("\n### Timeframe mix — is a higher-timeframe set polluting?\n")
    w("| timeframe class | symbol-day levels | share |")
    w("|---|---:|---:|")
    ttot = sum(tf_rank.values())
    for k in ["day", "htf", "struct", "generic"]:
        w("| %s | %d | %.1f%% |" % (k, tf_rank.get(k, 0),
                                    100.0 * tf_rank.get(k, 0) / ttot if ttot else 0))
    htf_detail = Counter(l for _, _, l in drawn if tf_of[l] == "htf")
    w("\nHTF levels the humans name: "
      + ", ".join("%s=%d" % kv for kv in htf_detail.most_common()) + "\n")

    w("\n## 4. Engine vs human, per symbol-day\n")
    w("Engine level set replicated from `signal_runner.detect_signals` "
      "(`level_pairs`) against the local 1m archive: PDH/PDL = prior RTH "
      "session high/low, PMH/PML = `polygon_feed.premarket_hi_lo`, ORH/ORL = "
      "first 5 RTH candles, plus the F3 HOD/LOD pair and every T10 pivot live "
      "on any bar in the 09:30–11:00 window.\n")
    w("- symbol-days with a human level AND archive coverage: **%d** of %d"
      % (len(gradable), len(by_day)))
    w("- symbol-days actually graded: **%d**\n" % graded_days)

    if graded_days:
        hs, ms = sum(hits.values()), sum(misses.values())
        w("| outcome | count | share |")
        w("|---|---:|---:|")
        w("| human level the engine ALSO has (HIT) | %d | %.1f%% |"
          % (hs, 100.0 * hs / (hs + ms) if hs + ms else 0))
        w("| human level the engine MISSES | %d | %.1f%% |"
          % (ms, 100.0 * ms / (hs + ms) if hs + ms else 0))
        w("\n**Misses by level** (what the humans watch and the engine has no "
          "level for):\n")
        w("| level | missed on N symbol-days | timeframe |")
        w("|---|---:|---|")
        for lv, n in misses.most_common(20):
            w("| %s | %d | %s |" % (lv, n, tf_of[lv]))

        w("\n**EXTRA levels the engine invents** — levels in its own set that "
          "no human named that day:\n")
        w("| statistic | named (the six) | extra (T10 pivot structure) |")
        w("|---|---:|---:|")
        w("| mean per symbol-day | %.2f | %.2f |"
          % (sum(named_counts) / len(named_counts),
             sum(extra_counts) / len(extra_counts)))
        w("| median | %d | %d |" % (pctile(named_counts, .5), pctile(extra_counts, .5)))
        w("| p90 | %d | %d |" % (pctile(named_counts, .9), pctile(extra_counts, .9)))
        w("| max | %d | %d |" % (max(named_counts), max(extra_counts)))
        infl = (sum(named_counts) + sum(extra_counts)) / sum(named_counts)
        w("\nThe engine carries **%.1fx** the level count of its own named six "
          "once T10 pivot structure is counted (`PIVOT_LEVELS=1` by default, "
          "`PIVOT_LOOKBACK=30`).\n" % infl)

    w("\n### Price distance — is the engine's PDH the same number the human means?\n")
    if dists:
        pcts = [d[5] for d in dists]
        w("%d (symbol, day, level) pairs where the human typed a price and the "
          "engine has that named level.\n" % len(dists))
        w("| percentile | abs(engine - human) as % of level |")
        w("|---|---:|")
        for q, lab in [(.10, "p10"), (.25, "p25"), (.50, "median"),
                       (.75, "p75"), (.90, "p90")]:
            w("| %s | %.3f%% |" % (lab, pctile(pcts, q)))
        w("| mean | %.3f%% |" % (sum(pcts) / len(pcts)))
        w("\nWithin 0.10%%: %d (%.0f%%). Within 0.25%%: %d (%.0f%%). "
          "Beyond 1%%: %d (%.0f%%).\n"
          % (sum(1 for p in pcts if p <= 0.10), 100.0 * sum(1 for p in pcts if p <= 0.10) / len(pcts),
             sum(1 for p in pcts if p <= 0.25), 100.0 * sum(1 for p in pcts if p <= 0.25) / len(pcts),
             sum(1 for p in pcts if p > 1.0), 100.0 * sum(1 for p in pcts if p > 1.0) / len(pcts)))
        w("\nClosest 15 matches:\n")
        w("| symbol | date | level | human | engine | delta% |")
        w("|---|---|---|---:|---:|---:|")
        for s, d, lv, hp, ep, pc in sorted(dists, key=lambda x: x[5])[:15]:
            w("| %s | %s | %s | %.2f | %.2f | %.3f%% |" % (s, d, lv, hp, ep, pc))
        w("\nWorst 10:\n")
        w("| symbol | date | level | human | engine | delta% |")
        w("|---|---|---|---:|---:|---:|")
        for s, d, lv, hp, ep, pc in sorted(dists, key=lambda x: -x[5])[:10]:
            w("| %s | %s | %s | %.2f | %.2f | %.3f%% |" % (s, d, lv, hp, ep, pc))
    else:
        w("No (symbol, day, level, price) pair survived. Humans overwhelmingly "
          "name levels by NAME, not by number — the number lives on the chart "
          "image.\n")

    w("\n## 5. Parser precision (hand-checked)\n")
    w("Three rounds. Every sampled record was read against its full source "
      "quote and adjudicated by hand; each round's failures drove a named fix "
      "in the parser rather than a tolerance tweak.\n")
    w("| round | parser | n | level type + symbol binding | price binding |")
    w("|---|---|---:|---|---|")
    w("| 1 | v1 (nearest number within 42 chars) | 30 | 28/30 = **93%** | 3/6 = **50%** |")
    w("| 2 | v2 (after-wins, nothing-between) | 32 | 31/32 = **97%** | 8/12 = **67%** |")
    w("| 3 | v3 (final: clock/EMA/fib/trailing-$ vetoes) | 30 | 30/30 = **100%** | 10/12 = **83%** |")
    w("\n**Reported precision on the final parser: level type + symbol binding "
      "100% (30/30), price binding 83% (10/12), n=30.**\n")
    w("\nFixes each round forced:\n")
    w("1. *v1 → v2.* v1 stole a neighbouring symbol's price — \"TSLA off the "
      "412, AMZN off PDL, and **Meta off PDL**\" gave META's PDL the number "
      "412. v2 requires the price to follow the level word (or sit within 6 "
      "chars before it) with no other level mention and no competing ticker "
      "in between.\n")
    w("2. *v2 → v3.* Four number shapes were still being read as level prices: "
      "a clock time (`opening range high at 10:2**4**`), an indicator period "
      "(`VWAP/EMA **200**`), a fib ratio (`Fib **382**`), and a trailing-dollar "
      "P&L (`bnr for **700**$`). v3 vetoes all four, plus the ±25% "
      "plausibility band at grading time.\n")
    w("\n**Residual error classes** (not fixed, would be over-fitting at this "
      "sample size):\n")
    w("- A directional word between the level and the number still binds: "
      "\"targeting ATH . SHORT under 307.95\" reads 307.95 as the ATH. "
      "1 of 12 in the final sample.\n")
    w("- A level price quoted in *option premium* terms (\"order block(6.54)\" "
      "on a \\$116 NVDA) parses literally but is not a stock level. The ±25% "
      "band drops these before they reach the distance table.\n")
    w("\nSample files: `level_parser_sample.txt` (round 1, evenly spaced), "
      "`human_levels.jsonl` (every extracted record, raw and un-banded, so the "
      "grading gate stays auditable).\n")

    OUT_MD.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
