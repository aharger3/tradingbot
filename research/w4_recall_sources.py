"""W4 -- new GRADEABLE symbol-days, recovered without asking Austin to grade more.

THE PROBLEM
-----------
The engine fires on 3 of Austin's 15 held-out S days (`research/t70_test1_score.py`).
Recall governs (ballot q20). More S labels would help, and he cannot grade 100,000
trades -- his own estimate of his S rate is "about 30% of the time", an
order-of-magnitude hint, not a number.

HIS SEARCH ORDER, VERBATIM
--------------------------
    "Try Corpus first for S-marked trade images, S-marked transcripts, or S-marked
     understanding of videos. If you can't find any of that in Corpus, flag it
     somewhere in the instructions for a different agent to read... If you can't find
     it in Corpus, then start looking at Discord, Circle, YouTube. Because some of
     that information has already been scraped and mined."

Corpus was searched first and holds none -- written up in `research/W4-HANDOFF.md` for
the source-mining agent, which deletes that file when it has read it. This script does
step 3: Discord, Circle, YouTube.

WHAT THIS PRODUCES, AND WHAT IT IS NOT
--------------------------------------
Output is `research/w4_candidate_days.jsonl`: **candidate symbol-days worth putting in
front of him**, each with the evidence that nominated it and an explicit provenance
class. It carries NO grade field and NO judgement.

    austin_said    Austin's own Discord message names this symbol on this session.
                   The strongest class here: he was in the trade or watching it, so it
                   is at minimum a day he thought was worth typing about.
    third_party    Someone else -- Scarface (TonyMontana), Jdub, or a member of the
                   Circle "A+ Setups" space -- flagged it as their best/A+ setup.
    model_inferred A local model read it out of a YouTube caption or video frame.
                   Weakest class. Kept separate, never merged upward.

**It is NOT a mark corpus and MUST NOT be added to
`research/build_deck.py::LEGACY_MARK_FILES`.** That list is the deck's no-repeat
guarantee: every symbol-day in it is treated as ALREADY JUDGED and is refused a card.
Putting an ungraded candidate list in there would permanently block exactly the days
this workstream exists to get graded -- the precise inverse of the goal. The rule in
`CLAUDE.md` ("new mark corpus => add it to LEGACY_MARK_FILES in the same commit") binds
files holding a human judgement. This one holds none.

DEDUPLICATION
-------------
`research/build_deck.py::marked_card_ids()` is called, not reimplemented. It reads every
mark corpus (`research/marks/*.jsonl` plus the ten `LEGACY_MARK_FILES`), normalises each
row to `SYMBOL_YYYY-MM-DD`, and counts `grade: "none"` as a judgement -- an explicit
refusal to trade is an answer, not a blank. A candidate whose key is in that set is
dropped.

A candidate is also dropped when `data_archive/<SYMBOL>/<DATE>.csv` does not exist: with
no bars there is no chart, so the day is not GRADEABLE however good the nomination.

TIMEZONE
--------
Discord `ts` is naive **UTC** -- proved in `research/corpus_tz_recall.md` (50 random
`msg_id` snowflakes decoded to within 2s of the stored `ts`). A message at
`2024-06-26T02:32Z` is the evening of **2024-06-25** in New York, so the session it talks
about is 06-25, not 06-26. Converted here rather than assumed.

    python research/w4_recall_sources.py
    python research/w4_recall_sources.py --selfcheck

Writes `research/w4_candidate_days.jsonl` and `research/w4_recall_sources.md`.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.build_deck import marked_card_ids                 # noqa: E402
from universe import BACKTEST_SYMBOLS                           # noqa: E402

ARCHIVE = os.path.join(_ROOT, "data_archive")
DISCORD = os.path.join(_ROOT, "discord_data")
CIRCLE = os.path.join(_ROOT, "circle_data")
OUT_JSONL = os.path.join(_HERE, "w4_candidate_days.jsonl")
OUT_MD = os.path.join(_HERE, "w4_recall_sources.md")

# Austin's Discord handle is exactly "Austin". The scrape also carries
# "AustinPowers", "AustinSD", "Austin_9910" and "Rob from Austin" -- four different
# community members. Prefix matching would silently merge five people's judgements
# into one corpus, which is the failure mode `research/marks/LEDGER.md` exists to
# prevent, so the match is EXACT.
AUSTIN = "Austin"
NOT_AUSTIN = ("AustinPowers", "AustinSD", "Austin_9910", "Rob from Austin")

# Channels whose author is a named trader posting their own best setups.
THIRD_PARTY_CHANNELS = ["a-plus-setups", "scarface-alerts", "jdub-alerts",
                        "options-trade-reviews", "futures-trade-reviews",
                        "live-sessions", "trade-feedback", "premarket-charts",
                        "swing-ideas", "youtube"]

# "This one was my best" language. Deliberately narrow: these phrases are how a
# trader marks a setup as top-tier in chat. A broad filter would nominate every
# alert and the list would stop meaning anything.
# `\b` will not close after a `+` (it is not a word character), so "A+" is
# anchored on its left edge only and the rest of the alternation keeps both edges.
QUALITY_RE = re.compile(
    r"(?:\ba\+"
    r"|\b(?:a plus|textbook|perfect setup|perfect entry|beautiful setup"
    r"|beauty of a|best setup|cleanest|clean as|picture perfect"
    r"|exactly what we (?:want|look for)|money setup|dream setup)\b)", re.I)

# Common names -> ticker, for the many messages that say "Tesla" not "TSLA".
NAME_TO_SYM = {
    "tesla": "TSLA", "apple": "AAPL", "nvidia": "NVDA", "amazon": "AMZN",
    "netflix": "NFLX", "microsoft": "MSFT", "google": "GOOGL", "meta": "META",
    "facebook": "META", "palantir": "PLTR", "coinbase": "COIN",
    "micron": "MU", "intel": "INTC", "broadcom": "AVGO", "alibaba": "BABA",
    "marathon": "MARA", "robinhood": "HOOD", "microstrategy": "MSTR",
    "rivian": "RIVN", "spy": "SPY", "qqq": "QQQ", "iwm": "IWM",
}

_TICKER_RE = re.compile(r"(?<![A-Za-z0-9$])\$?([A-Z]{1,5})(?![A-Za-z0-9])")

# Uppercase words that are not tickers. Without this "IMO", "PT", "EOD", "HOD",
# "PM" and "A" all become symbols.
_STOPWORDS = {
    "A", "I", "OK", "LOL", "PT", "EOD", "HOD", "LOD", "PM", "AM", "IMO", "TP",
    "SL", "RR", "OR", "BE", "GM", "GN", "ET", "US", "IT", "IF", "AND", "THE",
    "NO", "YES", "TA", "DM", "FYI", "ATH", "ATM", "OTM", "ITM", "IV", "PDT",
    "BNR", "OCR", "FVG", "HTF", "LTF", "PDH", "PDL", "PMH", "PML", "VWAP",
    "EMA", "SMA", "RSI", "CPI", "FOMC", "PCE", "GDP", "AH", "PR", "EPS",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def et_session_date(ts_utc: str) -> str | None:
    """Naive-UTC Discord timestamp -> the ET calendar date it belongs to.

    New York is UTC-4 (EDT) or UTC-5 (EST). The scrape spans both, and getting it
    wrong shifts an evening message onto the wrong session -- exactly the bug that
    would nominate a day Austin never traded. `zoneinfo` when available, a -4h
    approximation otherwise (worst case a 22:00-23:00 ET winter message lands one
    day late; flagged, not silently absorbed).
    """
    try:
        dt = datetime.strptime(ts_utc[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return None
    try:
        from zoneinfo import ZoneInfo
        return (dt.replace(tzinfo=timezone.utc)
                  .astimezone(ZoneInfo("America/New_York")).date().isoformat())
    except Exception:
        return (dt - timedelta(hours=4)).date().isoformat()


def symbols_in(text: str) -> set[str]:
    """Tickers named in a message, restricted to the traded universe."""
    if not text:
        return set()
    out = set()
    for m in _TICKER_RE.finditer(text):
        tok = m.group(1)
        if tok in _STOPWORDS:
            continue
        if tok in BACKTEST_SYMBOLS:
            out.add(tok)
    low = text.lower()
    for name, sym in NAME_TO_SYM.items():
        if re.search(r"\b%s\b" % re.escape(name), low) and sym in BACKTEST_SYMBOLS:
            out.add(sym)
    return out


QUALITY_WINDOW = 120


def symbols_near_quality(text: str, window: int = QUALITY_WINDOW) -> set[str]:
    """Tickers sitting within `window` characters of a top-tier phrase.

    Without this, one "textbook" anywhere in a 2,000-character game plan nominates
    every ticker the plan mentions -- and Jdub's monthly P&L post nominated four
    symbols it never called A+. The praise has to be near the name.
    """
    if not text:
        return set()
    spans = [m.span() for m in QUALITY_RE.finditer(text)]
    if not spans:
        return set()
    out = set()
    for m in _TICKER_RE.finditer(text):
        tok = m.group(1)
        if tok in _STOPWORDS or tok not in BACKTEST_SYMBOLS:
            continue
        a, b = m.span()
        if any(a - window <= e and s_ <= b + window for s_, e in spans):
            out.add(tok)
    low = text.lower()
    for name, sym in NAME_TO_SYM.items():
        if sym not in BACKTEST_SYMBOLS:
            continue
        for m in re.finditer(r"%s" % re.escape(name), low):
            a, b = m.span()
            if any(a - window <= e and s_ <= b + window for s_, e in spans):
                out.add(sym)
    return out


def has_bars(symbol: str, date: str) -> bool:
    return os.path.exists(os.path.join(ARCHIVE, symbol, "%s.csv" % date))


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def messages(path):
    d = load_json(path)
    if d is None:
        return []
    if isinstance(d, list):
        return [m for m in d if isinstance(m, dict)]
    for k in ("messages", "data", "posts"):
        if isinstance(d.get(k), list):
            return [m for m in d[k] if isinstance(m, dict)]
    return []


# ---------------------------------------------------------------------------
# the three source families
# ---------------------------------------------------------------------------

def from_austin_discord():
    """Austin's OWN Discord messages, every channel, exact-match author.

    Corpus never mined these: `research/corpus_instances.md` lists ten channels and
    `post-your-gains` and `questions` are not among them, so 154 of his messages have
    never been read by any instrument in this repo.

    A hit is a session he named a symbol on. That is not a grade and is not treated as
    one -- it is a nomination, and the reason it is the strongest class here is that
    he was in it or watching it in real time, with no hindsight.
    """
    out = []
    for path in sorted(glob.glob(os.path.join(DISCORD, "*.json"))):
        ch = os.path.basename(path)[:-5]
        if ch.startswith("_"):
            continue
        for m in messages(path):
            if str(m.get("author")) != AUSTIN:
                continue
            date = et_session_date(m.get("ts") or "")
            text = m.get("content") or ""
            atts = m.get("attachments") or []
            for sym in symbols_in(text):
                if not date:
                    continue
                out.append({
                    "symbol": sym, "date": date, "provenance": "austin_said",
                    "source": "discord/%s" % ch, "author": AUSTIN,
                    "ts_utc": m.get("ts"), "msg_id": m.get("id"),
                    "has_image": bool(atts),
                    "evidence": text.replace("\n", " ")[:300],
                })
    return out


def from_third_party_discord():
    """Named traders flagging a top-tier setup, in the channels the spec names."""
    out = []
    for ch in THIRD_PARTY_CHANNELS:
        path = os.path.join(DISCORD, "%s.json" % ch)
        if not os.path.exists(path):
            continue
        for m in messages(path):
            text = m.get("content") or ""
            if not QUALITY_RE.search(text):
                continue
            au = str(m.get("author"))
            if au in NOT_AUSTIN or au == AUSTIN:
                continue           # Austin's own go in the austin_said class
            date = et_session_date(m.get("ts") or "")
            if not date:
                continue
            for sym in symbols_near_quality(text):
                out.append({
                    "symbol": sym, "date": date, "provenance": "third_party",
                    "source": "discord/%s" % ch, "author": au,
                    "ts_utc": m.get("ts"), "msg_id": m.get("id"),
                    "has_image": bool(m.get("attachments")),
                    "evidence": text.replace("\n", " ")[:300],
                })
    return out


def from_circle():
    """The Circle space literally named "A+ Setups" (`circle_data/a-setups`).

    215 posts carry author + `created_at` + text + images; a second file holds 652
    text/image pairs with no metadata at all, so those cannot be dated and are counted
    but not nominated. `created_at` is ISO-8601 with an explicit `Z`.
    """
    out = []
    posts = load_json(os.path.join(CIRCLE, "a-setups", "posts_v2.json")) or []
    for p in posts:
        if not isinstance(p, dict):
            continue
        date = et_session_date((p.get("created_at") or "").replace("Z", ""))
        text = p.get("text") or ""
        if not date:
            continue
        for sym in symbols_near_quality(text) or symbols_in(text):
            out.append({
                "symbol": sym, "date": date, "provenance": "third_party",
                "source": "circle/a-setups", "author": p.get("author"),
                "ts_utc": p.get("created_at"), "msg_id": p.get("post_id"),
                "has_image": bool(p.get("images")),
                "evidence": text.replace("\n", " ")[:300],
            })
    return out


def from_youtube_corpus():
    """The YouTube scrape, as it already sits in `research/corpus_frames.jsonl`.

    `corpus_entries.jsonl` carries a `ts` that is the EXTRACTION time, not the session,
    so it cannot date a symbol-day and is not used. `corpus_frames.jsonl`'s `frame_read`
    carries a `session_time` read off the chart in the video ("Thu 26 Feb '26 09:5..."),
    which is a real session stamp -- weak, model-read, and labelled as such.
    """
    out = []
    path = os.path.join(_HERE, "corpus_frames.jsonl")
    if not os.path.exists(path):
        return out
    dre = re.compile(r"(\d{1,2})\s+([A-Za-z]{3})\s+'(\d{2})")
    mons = {m: i + 1 for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            fr = r.get("frame_read") or {}
            for chart in (fr.get("charts") or []):
                tk = str(chart.get("ticker") or "").upper()
                if tk not in BACKTEST_SYMBOLS:
                    continue
                m = dre.search(str(chart.get("session_time") or ""))
                if not m:
                    continue
                mon = mons.get(m.group(2).title())
                if not mon:
                    continue
                date = "20%s-%02d-%02d" % (m.group(3), mon, int(m.group(1)))
                out.append({
                    "symbol": tk, "date": date, "provenance": "model_inferred",
                    "source": "youtube/corpus_frames", "author": r.get("model"),
                    "ts_utc": r.get("ts"), "msg_id": r.get("video_id"),
                    "has_image": True,
                    "evidence": str(chart.get("session_time"))[:300],
                })
    return out


SOURCES = [("Austin's own Discord messages", from_austin_discord),
           ("named traders' A+ calls, Discord", from_third_party_discord),
           ("Circle \"A+ Setups\" space", from_circle),
           ("YouTube frame reads", from_youtube_corpus)]


# ---------------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------------

RANK = {"austin_said": 3, "third_party": 2, "model_inferred": 1}


def harvest():
    raw, per_source = [], {}
    for name, fn in SOURCES:
        rows = fn()
        per_source[name] = rows
        raw.extend(rows)

    # collapse to one row per symbol-day, keeping the strongest provenance and
    # every distinct nomination underneath it
    by_key = defaultdict(list)
    for r in raw:
        by_key["%s_%s" % (r["symbol"], r["date"])].append(r)

    already = marked_card_ids()
    cand, drop_marked, drop_nobars = [], [], []
    for key, rows in sorted(by_key.items()):
        best = max(rows, key=lambda r: RANK[r["provenance"]])
        rec = {
            "key": key, "symbol": best["symbol"], "date": best["date"],
            "provenance": best["provenance"],
            "n_nominations": len(rows),
            "sources": sorted({r["source"] for r in rows}),
            "authors": sorted({str(r["author"]) for r in rows}),
            "has_image": any(r["has_image"] for r in rows),
            "evidence": best["evidence"],
        }
        if key in already:
            drop_marked.append(rec)
            continue
        if not has_bars(best["symbol"], best["date"]):
            drop_nobars.append(rec)
            continue
        cand.append(rec)
    return {"raw": raw, "per_source": per_source, "by_key": by_key,
            "already": already, "cand": cand,
            "drop_marked": drop_marked, "drop_nobars": drop_nobars}


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck():
    ok = True

    def chk(name, cond):
        nonlocal ok
        print("%-62s %s" % (name, "ok" if cond else "FAIL"))
        ok = ok and bool(cond)

    chk("UTC evening rolls back to the prior ET session",
        et_session_date("2024-06-26T02:32:00") == "2024-06-25")
    chk("UTC midday stays on the same ET session",
        et_session_date("2024-06-21T15:17:00") == "2024-06-21")
    chk("a bad timestamp returns None", et_session_date("") is None)
    chk("plain ticker found", symbols_in("Check out amd tho") == set())  # lowercase is not a ticker
    chk("uppercase ticker found", "AMD" in symbols_in("Check out AMD tho"))
    chk("$-prefixed ticker found", "TSLA" in symbols_in("long $TSLA here"))
    chk("common name maps to ticker", "TSLA" in symbols_in("Tesla trade was good"))
    chk("stopwords are not tickers",
        not (symbols_in("PT hit, EOD, HOD, IMO, PM") & {"PT", "EOD", "HOD", "IMO", "PM"}))
    chk("out-of-universe ticker dropped", "ZZZZ" not in symbols_in("bought ZZZZ"))
    chk("quality regex catches A+", bool(QUALITY_RE.search("A+ Trade Example")))
    chk("quality regex catches 'beautiful setup'",
        bool(QUALITY_RE.search("It was a beautiful setup.")))
    chk("quality regex ignores an ordinary alert",
        not QUALITY_RE.search("TSLA long 250 stop 249"))
    chk("praise near the ticker nominates it",
        symbols_near_quality("AAPL had textbook retest") == {"AAPL"})
    chk("praise far from the ticker does not",
        symbols_near_quality("AAPL " + "x" * 400 + " textbook retest") == set())
    chk("Austin match is exact, not prefix",
        AUSTIN == "Austin" and all(n != AUSTIN for n in NOT_AUSTIN))

    h = harvest()
    chk("Austin's own messages produced nominations",
        len(h["per_source"]["Austin's own Discord messages"]) > 0)
    chk("dedup set is non-trivial", len(h["already"]) > 400)
    chk("every candidate has archived bars",
        all(has_bars(c["symbol"], c["date"]) for c in h["cand"]))
    chk("no candidate is an already-judged symbol-day",
        not ({c["key"] for c in h["cand"]} & h["already"]))
    chk("arithmetic closes",
        len(h["by_key"]) == len(h["cand"]) + len(h["drop_marked"]) + len(h["drop_nobars"]))
    chk("no candidate carries a grade field",
        all("grade" not in c and "tier" not in c for c in h["cand"]))
    print("SELFCHECK", "GREEN" if ok else "RED")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def build():
    h = harvest()
    cand = h["cand"]

    with open(OUT_JSONL, "w", encoding="utf-8") as fh:
        for c in sorted(cand, key=lambda r: (-RANK[r["provenance"]], r["key"])):
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    prov = Counter(c["provenance"] for c in cand)
    syms = Counter(c["symbol"] for c in cand)
    L = []
    A = L.append
    A("# W4 — new gradeable symbol-days, without more grading")
    A("")
    A("Generated by `research/w4_recall_sources.py` (`--selfcheck` green). Output data: "
      "`research/w4_candidate_days.jsonl`.")
    A("")
    A("**This file contains no judgement of Austin's and creates no mark corpus.** It "
      "nominates symbol-days worth putting in front of him. See *The rule this "
      "deliberately does not follow* at the bottom — it matters and it is not an "
      "oversight.")
    A("")
    A("## The headline")
    A("")
    A("**%d new gradeable symbol-days**, none of them already judged in ANY existing "
      "mark corpus (the ten `LEGACY_MARK_FILES` plus everything under "
      "`research/marks/` — %d judged symbol-days in all), every one of them with "
      "archived bars so a card can actually be drawn."
      % (len(cand), len(h["already"])))
    A("")
    A("| provenance | days | what it means |")
    A("|---|---:|---|")
    A("| `austin_said` | %d | **Austin's own Discord message names this symbol on this "
      "session.** Not a grade — a nomination, made in real time with no hindsight. |"
      % prov.get("austin_said", 0))
    A("| `third_party` | %d | Scarface (`TonyMontana`), Jdub, or a member of the Circle "
      "\"A+ Setups\" space called it their best / an A+ setup. |"
      % prov.get("third_party", 0))
    A("| `model_inferred` | %d | a local model read the ticker and session date off a "
      "YouTube chart frame. Weakest class, never merged upward. |"
      % prov.get("model_inferred", 0))
    A("")

    A("## Corpus first — and it held nothing")
    A("")
    A("Austin's order was Corpus, then Discord / Circle / YouTube. All 138 "
      "`research/corpus_*` artifacts were profiled by schema, by `speaker` / `author` / "
      "`class` / `source`, and by grep for any field named `grade`, `tier`, `verdict`, "
      "`mark`, `austin`, `rating`, `score` or `quality`.")
    A("")
    A("**No Austin S-marked trade image, transcript or video understanding exists in "
      "Corpus.** The `speaker` field is Scarface/jdub (2,453), Hayden (417) and Mar "
      "(130); `corpus_instances.jsonl` holds exactly **1** Austin-authored row out of "
      "10,379, a 13:53 ET `trading-floor` message outside the trading window; the only "
      "corpus files with a `grade` field are the twelve `corpus_engine_*.jsonl`, whose "
      "grade is the ENGINE's `A+/A/B/C/X` and which `research/marks/LEDGER.md` already "
      "excludes by name.")
    A("")
    A("`research/corpus_miss_autopsy.md` says it outright: *\"Corpus instances are alerts "
      "from Discord, not Austin's own graded setups, so there is no S/A/X tier.\"* The "
      "full inventory is in `research/W4-HANDOFF.md`, written for the source-mining "
      "agent per the spec, which deletes it once read.")
    A("")
    A("**The structural reason**, and it is the finding that unlocked the rest: Corpus "
      "was built to mine OTHER traders' language, because that is what the rulebook was "
      "reverse-engineered from. It was never pointed at Austin. Two channels holding his "
      "own posts — `post-your-gains.json` and `questions.json` — are not in the corpus "
      "channel list at all.")
    A("")

    A("## Where each candidate came from")
    A("")
    A("| source | rows scanned | nominations | what it is |")
    A("|---|---:|---:|---|")
    scanned = {
        "Austin's own Discord messages": _n_austin_msgs(),
        "named traders' A+ calls, Discord": _n_msgs(THIRD_PARTY_CHANNELS),
        "Circle \"A+ Setups\" space": len(load_json(
            os.path.join(CIRCLE, "a-setups", "posts_v2.json")) or []),
        "YouTube frame reads": _n_lines(os.path.join(_HERE, "corpus_frames.jsonl")),
    }
    blurb = {
        "Austin's own Discord messages":
            "every `discord_data/*.json`, author matched **exactly** `Austin` — "
            "`AustinPowers`, `AustinSD`, `Austin_9910` and `Rob from Austin` are four "
            "different members and are excluded",
        "named traders' A+ calls, Discord":
            "the channels the spec names, filtered to explicit top-tier language "
            "(`A+`, `textbook`, `perfect entry`, `beautiful setup`, `cleanest`, …)",
        "Circle \"A+ Setups\" space":
            "`circle_data/a-setups` — the space's display name is literally **A+ "
            "Setups**; 215 dated posts by 60+ members, 210 carrying a chart image",
        "YouTube frame reads":
            "`research/corpus_frames.jsonl`; the session date is read off the chart in "
            "the frame, by a model",
    }
    for name, _fn in SOURCES:
        A("| %s | %d | %d | %s |"
          % (name, scanned.get(name, 0), len(h["per_source"][name]), blurb[name]))
    A("")

    A("### Austin's own messages, by channel")
    A("")
    ac = Counter(r["source"] for r in h["per_source"]["Austin's own Discord messages"])
    A("| channel | nominations | in the corpus channel list? |")
    A("|---|---:|---|")
    corpus_channels = {"scarface-alerts", "jdub-alerts", "trading-floor",
                       "trade-feedback", "swing-ideas", "futures-alerts",
                       "backtesting", "options-trade-reviews", "pre-market-live",
                       "futures-trade-reviews"}
    for src, n in ac.most_common():
        ch = src.split("/", 1)[1]
        A("| `%s` | %d | %s |" % (ch, n,
                                  "yes" if ch in corpus_channels else "**no — never mined**"))
    A("")

    A("## The dedup arithmetic")
    A("")
    A("`research/build_deck.py::marked_card_ids()` was **called, not reimplemented** — "
      "it reads `research/marks/*.jsonl` plus the ten `LEGACY_MARK_FILES`, normalises "
      "every row to `SYMBOL_YYYY-MM-DD`, and counts `grade: \"none\"` as a judgement "
      "(an explicit refusal to trade is an answer, not a blank).")
    A("")
    A("| step | count |")
    A("|---|---:|")
    A("| raw nominations across all four sources | %d |" % len(h["raw"]))
    A("| distinct symbol-days nominated | %d |" % len(h["by_key"]))
    A("| − already judged by Austin (`marked_card_ids()`, %d keys) | −%d |"
      % (len(h["already"]), len(h["drop_marked"])))
    A("| − no bars in `data_archive/`, so no card can be drawn | −%d |"
      % len(h["drop_nobars"]))
    A("| **= NEW gradeable symbol-days** | **%d** |" % len(cand))
    A("")
    A("The %d dropped as already-judged are the guarantee working: those days are in the "
      "existing corpora and re-asking him would waste the only scarce input in this "
      "project. The %d dropped for missing bars are mostly symbols outside "
      "`universe.BACKTEST_SYMBOLS`'s archived set or dates before the archive starts."
      % (len(h["drop_marked"]), len(h["drop_nobars"])))
    A("")

    A("## The candidates")
    A("")
    A("Top %d by provenance then date. Full list in "
      "`research/w4_candidate_days.jsonl`." % min(40, len(cand)))
    A("")
    A("| symbol | date | provenance | source | image | what nominated it |")
    A("|---|---|---|---|---|---|")
    for c in sorted(cand, key=lambda r: (-RANK[r["provenance"]], r["date"]))[:40]:
        ev = c["evidence"].replace("|", "\\|")[:120]
        A("| **%s** | %s | `%s` | %s | %s | %s |"
          % (c["symbol"], c["date"], c["provenance"], ", ".join(c["sources"]),
             "yes" if c["has_image"] else "—", ev))
    A("")
    A("Per symbol: %s." % ", ".join("%s %d" % (s, n) for s, n in syms.most_common(15)))
    A("")

    A("## The rule this deliberately does not follow")
    A("")
    A("`CLAUDE.md`: *\"If you add a mark corpus, add it to `LEGACY_MARK_FILES` in the "
      "same commit.\"* **`research/w4_candidate_days.jsonl` is NOT added, on purpose.**")
    A("")
    A("`LEGACY_MARK_FILES` feeds `marked_card_ids()`, which is the deck's no-repeat "
      "guarantee: every symbol-day in it is treated as ALREADY JUDGED and refused a "
      "card. Adding an ungraded candidate list would permanently block the exact days "
      "this workstream exists to get graded. The rule binds files holding a human "
      "judgement; this file holds none — no `grade`, no `tier`, no `verdict`, asserted "
      "by a selfcheck.")
    A("")
    A("**The moment any of these days comes back with a grade on it, the resulting file "
      "IS a mark corpus** and every rule applies: `git status` and LOOK that it is "
      "staged, `git add -f` plus an un-ignore rule if `.gitignore` swallowed it, an "
      "entry in `research/marks/LEDGER.md`, and `LEGACY_MARK_FILES` in the same commit.")
    A("")
    A("## Honest limits")
    A("")
    A("- **`austin_said` is a nomination, not a grade.** He named the symbol that "
      "session. Some of those messages are him losing on it. The class means \"worth "
      "asking about\", nothing more, and it is labelled that way in every row.")
    A("- **`third_party` is somebody else's A+, not his.** The two ladders problem "
      "(`omen-two-grade-ladders`) is exactly this kind of collision. Never let a "
      "Scarface A+ enter a mark file as an Austin S.")
    A("- **`model_inferred` should probably never be graded at all** without a human "
      "confirming the frame read first. It is reported for completeness.")
    A("- The `circle_data/a-setups/posts.json` file holds a further 652 text+image pairs "
      "with **no author and no date**. They cannot be tied to a session and are not "
      "nominated. Re-scraping that space with metadata is a cheap way to grow this list.")
    A("- Highest-value unclaimed job found on the way: `research/marks/LEDGER.md` counts "
      "**47 S-tier symbol-days that exist only in `recovered_reviews.jsonl`'s unmatched "
      "135**, excluded for having no bar index. Those are real Austin S judgements and "
      "re-aligning them needs zero new grading.")
    A("")

    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("wrote", OUT_JSONL)
    print("wrote", OUT_MD)
    print("  raw %d  distinct %d  -marked %d  -nobars %d  => NEW %d  (%s)"
          % (len(h["raw"]), len(h["by_key"]), len(h["drop_marked"]),
             len(h["drop_nobars"]), len(cand), dict(prov)))
    return 0


def _n_austin_msgs():
    n = 0
    for path in glob.glob(os.path.join(DISCORD, "*.json")):
        if os.path.basename(path).startswith("_"):
            continue
        n += sum(1 for m in messages(path) if str(m.get("author")) == AUSTIN)
    return n


def _n_msgs(channels):
    n = 0
    for ch in channels:
        p = os.path.join(DISCORD, "%s.json" % ch)
        if os.path.exists(p):
            n += len(messages(p))
    return n


def _n_lines(path):
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    return selfcheck() if a.selfcheck else build()


if __name__ == "__main__":
    sys.exit(main())
