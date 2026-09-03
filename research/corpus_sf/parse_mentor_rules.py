#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
parse_mentor_rules.py -- deterministic rule-candidate extractor.

Pools mentor-authored didactic sentences out of the corpus_sf mining outputs,
splits them to sentences, filters to normative statements, buckets them by
topic, and clusters near-identical restatements.

NOT an Austin mark corpus. Read-only on everything under research/ except
research/corpus_sf/.

Output: research/corpus_sf/mentor_rules.jsonl
"""
from __future__ import annotations
import json, re, os, sys, unicodedata, collections

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "mentor_rules.jsonl")

# ---------------------------------------------------------------- mentors
MENTORS = {
    "Jdub": "Jdub",
    "TonyMontana": "Scarface",
    "Neto Moreno (Performance Coach)": "Neto",
    "Lauren (lakatrades)": "Lauren",
    "MambaTrades": "Mamba",
    "Hayden": "Hayden",
    "QueenBee": "QueenBee",
}

# source file -> (text fields to mine, mentors_only?)
SOURCES = [
    ("questions.jsonl",       ["rule"],            True,  False),
    ("general_chat.jsonl",    ["quote"],           True,  False),
    ("tips.jsonl",            ["quote"],           False, False),
    ("maxims_futures.jsonl",  ["quote"],           True,  False),
    ("reviews_options.jsonl", ["reason", "quote"], True,  False),
    ("reviews_futures.jsonl", ["quote"],           True,  False),
    ("reviews_jdub.jsonl",    ["quote"],           True,  False),
    ("misc.jsonl",            ["quote"],           True,  False),
    ("backtesting.jsonl",     ["quote"],           True,  False),
    ("scarface_alerts.jsonl", ["quote"],           True,  True),
    ("jdub_alerts.jsonl",     ["quote"],           True,  True),
    ("live_sessions.jsonl",   ["quote"],           True,  True),
    ("pre_market_live.jsonl", ["quote"],           True,  True),
]
# DELIBERATELY EXCLUDED: scarface_alerts.jsonl, jdub_alerts.jsonl,
# pre_market_live.jsonl, premarket_charts.jsonl, live_sessions.jsonl.
# v1 pulled 835 sentences from those and a hand-check of 30 put precision at
# 27%: they are live per-symbol commentary ("I want to see TSLA hold PDH"),
# situational calls rather than reusable rules. The task's named sources are
# questions / general-chat / tips / review reason fields; misc carries the
# mentor rows of trading-floor + trade-feedback, which ARE didactic.

# ---------------------------------------------------------------- cleaning
URL_RE      = re.compile(r"https?://\S+")
MENTION_RE  = re.compile(r"<@[!&]?\d+>|<#\d+>|<:[^>]+>|@everyone|@here")
APIKEY_RE   = re.compile(r"(?i)(apikey|api_key|polygon[_-]?api[_-]?key)\s*[=:]\s*\S+")
WS_RE       = re.compile(r"\s+")
MD_RE       = re.compile(r"[*_`~]{1,3}")

def clean(t: str) -> str:
    if not t:
        return ""
    t = unicodedata.normalize("NFKC", t)
    t = APIKEY_RE.sub("[REDACTED]", t)
    t = URL_RE.sub(" ", t)
    t = MENTION_RE.sub(" ", t)
    t = MD_RE.sub("", t)
    t = "".join(ch for ch in t if ch.isprintable() or ch in "\n\t")
    return WS_RE.sub(" ", t).strip()

# sentence split: terminal punctuation, newlines, bullet leads, semicolons
SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\s*\n+\s*|\s+[-•]\s+|;\s+")

def sentences(t: str):
    for s in SPLIT_RE.split(t):
        s = s.strip(" \t-•*.,")
        if s:
            yield s

# ---------------------------------------------------------------- filters
# normative / instructional markers -- a rule tells you what to do
NORM = [
    r"\balways\b", r"\bnever\b", r"\bmust\b", r"\bshould\b", r"\bshouldn'?t\b",
    r"\bneed to\b", r"\bneeds to\b", r"\bhave to\b", r"\bhas to\b", r"\bgot to\b",
    r"\bdon'?t\b", r"\bdo not\b", r"\bavoid\b", r"\bstay away\b", r"\bstop\b",
    r"\bwait for\b", r"\bwait until\b", r"\bonly\b", r"\bmake sure\b", r"\bensure\b",
    r"\bthe (?:key|rule|goal|point|trick|idea|whole point) is\b", r"\bmy rule\b",
    r"\bi (?:always|never|only|usually|typically|generally|like to|prefer|aim|want|use|wait|look for|need)\b",
    r"\bwe (?:always|never|only|usually|want|need|wait|look for|use)\b",
    r"\byou (?:want|need|should|have to|dont|don'?t|never|always|can'?t|cannot)\b",
    r"\bbest to\b", r"\bimportant\b", r"\bcrucial\b", r"\bkey\b", r"\brule of thumb\b",
    r"\bif .{4,60}? (?:then|dont|don'?t|you|i|we|its|it'?s)\b",
    r"\bbetter to\b", r"\bno (?:trade|trades|entry|reason|edge|point)\b",
    r"\bdiscipline\b", r"\bstick to\b", r"\bcut\b", r"\blet .{0,20}run\b",
    r"\btake (?:profit|profits|partials|half|some off)\b", r"\bscale (?:out|in)\b",
    r"\bdo(?:es)? not (?:enter|trade|chase)\b", r"\bnot worth\b", r"\bhigher chance\b",
    r"\bmore likely\b", r"\bless likely\b", r"\bprobability\b", r"\bconfirmation\b",
]
NORM_RE = re.compile("|".join(NORM), re.I)

# trading domain vocabulary -- a rule is about trading, not about life
DOMAIN = [
    r"\bcandle", r"\bclose", r"\bwick", r"\bbody\b", r"\bentry\b", r"\benter",
    r"\bexit", r"\bstop\b", r"\bstop ?loss", r"\bsl\b", r"\btarget", r"\btp\d?\b",
    r"\bprofit", r"\brisk", r"\br:?r\b", r"\b\d+r\b", r"\breward",
    r"\blevel", r"\bsupport", r"\bresistance", r"\bpmh\b", r"\bpml\b", r"\bpdh\b",
    r"\bpdl\b", r"\bhod\b", r"\blod\b", r"\bvwap\b", r"\bopening range\b", r"\borb\b",
    r"\bpremarket\b", r"\bpre.?market\b", r"\bgap\b", r"\bretest", r"\bbreak",
    r"\btrend", r"\bstructure", r"\bpivot", r"\bconsolidat", r"\bchop",
    r"\bdisplacement\b", r"\bvolume\b", r"\bliquidity\b", r"\bmomentum\b",
    r"\bprice action\b", r"\bpa\b", r"\bsetup", r"\bconfluence\b", r"\bbias\b",
    r"\bcontract", r"\bposition", r"\bsize\b", r"\bsizing\b", r"\bshares\b",
    r"\boption", r"\bcall\b", r"\bput\b", r"\bstrike\b", r"\bpremium\b",
    r"\btheta\b", r"\bdelta\b", r"\bgreeks\b", r"\b0dte\b", r"\bexpir",
    r"\btrade\b", r"\btrades\b", r"\btrading\b", r"\bscalp", r"\bswing\b",
    r"\bwin ?rate\b", r"\bloss", r"\bwinner", r"\bloser", r"\bgreen\b", r"\bred\b",
    r"\bmarket\b", r"\bticker", r"\bsymbol", r"\bchart", r"\btimeframe\b",
    r"\b\d+ ?min", r"\b1m\b", r"\b5m\b", r"\bdaily\b", r"\bhourly\b",
    r"\b9:?3\d\b", r"\b10:?\d\d\b", r"\b11:?\d\d\b", r"\bopen\b", r"\bbell\b",
    r"\bfomc\b", r"\bcpi\b", r"\bnews\b", r"\bearnings\b", r"\bcatalyst\b",
    r"\bbreakeven\b", r"\bbreak.?even\b", r"\bpartial", r"\brunner",
    r"\bfvg\b", r"\bimbalance\b", r"\border block\b", r"\bocr\b", r"\bone candle\b",
    r"\bflag\b", r"\bwedge\b", r"\bdowntrend\b", r"\buptrend\b", r"\bbullish\b",
    r"\bbearish\b", r"\bfill\b", r"\bslippage\b", r"\bspread\b", r"\baccount\b",
    r"\bcapital\b", r"\bdrawdown\b", r"\bpsycholog", r"\bemotion", r"\brevenge\b",
    r"\bovertrad", r"\bfomo\b", r"\bjournal", r"\bbacktest", r"\bplan\b",
]
DOMAIN_RE = re.compile("|".join(DOMAIN), re.I)

# hard rejects -- alert chatter, P&L brags, logistics, greetings
REJECT = [
    r"^\s*(?:gm|gn|good morning|good luck|gl|thanks|thank you|ty|congrats|lol|lmao|yes|no|yep|nope|ok|okay)\b",
    r"\b(?:zoom|passcode|recording|playlist|youtube|link to|recap|modules?|webinar|replay)\b",
    r"\bwelcome\b", r"\bdm me\b", r"\bjoin\b.{0,20}\b(?:call|room|discord)\b",
    r"\bi(?:'m| am) (?:up|down) \$", r"^\+?\$?\d[\d,\.]*\s*(?:k|usd)?\s*$",
    r"\bhappy (?:birthday|holidays|new year|thanksgiving|friday)\b",
    r"\btrade recap\b", r"\bsee (?:yall|you) (?:tomorrow|monday)\b",
    r"\b(?:filled|trimmed|stopped out|out at|in at|adding|closed) \d",
    r"^\s*(?:buying|selling|long|short|bought|sold)\b.{0,40}\b\d+\.\d+\s*$",
    r"\bcongratulations\b", r"\bsubscribe\b", r"\bpdf\b", r"\bbook\b.{0,15}\brecommend\b",
]
REJECT_RE = re.compile("|".join(REJECT), re.I)

# ------------------------------------------------- situational, not a rule
# A rule is reusable. A sentence naming a ticker, a price level, or "today" is
# a call about one chart on one morning. This filter is what took hand-checked
# precision from 27% to the number reported in mentor_rules.md.

# acronyms that look like tickers but are vocabulary
ACRONYMS = set("""PMH PML PDH PDL PMHOD HOD LOD VWAP ORB ORH ORL OR FVG OCR BR RR RRR SL TP TP1
TP2 PA HTF LTF ATR EMA SMA MA RSI IV DTE ITM OTM ATM PNL PL BE MFE MAE CPI FOMC PPI NFP GDP AH PM
AM ET EST EOD EOW IB OB OTF DOM VOL AVG USD RTH ADR ADX MACD VWMA TF PDC PMC LOTD HOTD NY US
A B C D E F G H I J K L M N O P Q R S T U V W X Y Z AI CEO CFO IPO ETF FED SEC EPS PE YTD QOQ YOY
OK NO YES ID TV PC PDT ATH ATL WTF IMO IMHO FYI TLDR EOM MOC LOC GTC AON FOK IOC DCA""".split())
TICKER_RE = re.compile(r"\$[A-Za-z]{1,5}\b|(?<![A-Za-z])([A-Z]{2,5})(?![A-Za-z])")

# a bare 3-5 digit number with no $ and no unit is a price level
PRICE_RE = re.compile(
    r"(?<![\$\d\.])\b\d{2,5}\.\d{1,2}\b(?!\s*%)"          # 185.38
    r"|(?<![\$\d\.\:])\b[1-9]\d{2,4}\b(?!\s*(?:%|k\b|r\b|R\b|sh|contract|share|dollar|usd|\$))"
)

# lowercase tickers leak past the ALL-CAPS test ("only if qqq can hold pmh")
LC_TICKER_RE = re.compile(r"(?<![a-z])(?:spy|qqq|iwm|tsla|nvda|aapl|amzn|msft|meta|goog|googl|amd|"
    r"netflix|nflx|coin|mstr|pltr|intc|avgo|crm|hood|smci|baba|dia|spx|ndx|es|nq|"
    r"soxl|tqqq|sqqq|uvxy|vix|gme|amc|riot|mara|sofi|lcid|rivn|nio|dis|ba|jpm|xom)(?![a-z])", re.I)

# a sentence about a named person is chatter, not a rule
PERSON_RE = re.compile(r"\b(?:jdub|scarface|tony|neto|lauren|mamba|hayden|queenbee|viper|"
    r"jatin|austin|lakatrades)\b", re.I)

# an embedded question with no "?" is still a question
QSTART_RE = re.compile(r"^\s*(?:is|are|was|were|do|does|did|can|could|should|would|will|"
    r"what|why|how|when|where|who|which|whats|any|anyone|anybody)\b", re.I)

DEIXIS_RE = re.compile(
    r"\b(?:today|tomorrow|yesterday|right now|this morning|this afternoon|as shown|"
    r"top watch(?:es)?|main watch|my watch|watchlist|into (?:the )?open|"
    r"pre ?market (?:today|now)|so far|last week|this week|next week|"
    r"currently|at the moment|earlier today|just now|this one|that one)\b", re.I)

def is_situational(s: str) -> bool:
    if DEIXIS_RE.search(s):
        return True
    if LC_TICKER_RE.search(s):
        return True
    if PERSON_RE.search(s):
        return True
    if PRICE_RE.search(s):
        return True
    for m in TICKER_RE.finditer(s):
        tok = (m.group(1) or m.group(0)).lstrip("$").upper()
        if tok not in ACRONYMS:
            return True
    return False

# ---- strict mode, for the live-alert channels ----------------------------
# Scarface's and Jdub's alert channels are 40% precise under the normal filter
# (hand-checked, 25 samples): they are running commentary with real teaching
# embedded in it. Strict mode keeps only sentences that are habitual in form
# and rejects live position-management chatter.
HABITUAL_RE = re.compile(
    r"\balways\b|\bnever\b|\bmust\b|\bshould\b|\bneed to\b|\bneeds to\b|"
    r"\bhave to\b|\bhas to\b|\bideally\b|\bgenerally\b|\busually\b|"
    r"\btypically\b|\bevery time\b|\banytime\b|\bmy rule\b|\bpreach\b|"
    r"\bthe (?:key|rule|goal|point|whole point) is\b|\brule of thumb\b|"
    r"\bonly (?:trade|enter|take|way|thing|time)\b|\bin general\b|"
    r"\bbest thing\b|\bwe know\b|\byou want to\b|\byou need\b|"
    r"\bdon'?t (?:ever|chase|trade)\b|\bwe (?:always|never|only|want|wait)\b", re.I)
LIVE_MGMT_RE = re.compile(
    r"\b(?:holding|cut rest|cut the rest|take some off|took some off|"
    r"lock(?:ing)? in|trimmed|trimming|scaling out here|adding here|added here|"
    r"stop will be|stop is now|moved? (?:my )?stop|got filled|"
    r"all out|flat here|rest of (?:the )?(?:cons|runner|position))\b", re.I)

# broker / platform mechanics are how-to, not trading rules
BROKER_RE = re.compile(r"\b(?:quote panel|order type|advanced order|stop.?limit|bracket order|confirm the order|thinkorswim|tastytrade|webull|robinhood|interactive brokers|tos platform|click|button|drop.?down|tab of the|enter the (?:stop|limit) price|order entry|quantity of contracts|operator <|platform|app )", re.I)

# ---- residual failure classes found in hand-check round 3 --------------
# a mid-sentence question ('I know X but how can I know Y') is still a question
MIDQ_RE = re.compile(r"\b(?:how (?:can|do|would|should) (?:i|you|we)|can (?:i|you|we) (?:still|also|just)?\s*(?:do|use|set|get|know)|(?:any|some)one know|my question|question is)", re.I)
# past-tense first-person narrative is a trade story, not a rule -- unless it
# also carries a habitual marker ('I always cut at ...')
PAST_NARR_RE = re.compile(r"\bi (?:had|decided|made sure|took|got|ended up|was|were|went|closed|opened|sold|bought|entered|exited|scaled|trimmed|lost|won|added|noticed|realized|realised|figured)\b", re.I)
# a demonstrative with no referent in the sentence is a fragment of a thread
VACUOUS_RE = re.compile(r"^(?:this|these|those|that|it|they)\s+\w+\s+(?:is|are|was|were)\b|\b(?:these tools|this step|this process|this method|these indicators|i use these|i use this|these are|in past reviews|this review|the review|repeat steps?|operator)\b", re.I)

MIN_LEN, MAX_LEN = 40, 320
MIN_WORDS = 8
MIN_DOMAIN_HITS = 2

def is_rule(s: str, strict: bool = False) -> bool:
    if strict:
        if LIVE_MGMT_RE.search(s):
            return False
        if not HABITUAL_RE.search(s):
            return False
    if not (MIN_LEN <= len(s) <= MAX_LEN):
        return False
    if s.rstrip().endswith("?"):
        return False
    if QSTART_RE.match(s):
        return False
    if REJECT_RE.search(s):
        return False
    if BROKER_RE.search(s):
        return False
    if MIDQ_RE.search(s):
        return False
    if VACUOUS_RE.search(s):
        return False
    if PAST_NARR_RE.search(s) and not HABITUAL_RE.search(s):
        return False
    if is_situational(s):
        return False
    if not NORM_RE.search(s):
        return False
    if len({m.group(0).lower() for m in DOMAIN_RE.finditer(s)}) < MIN_DOMAIN_HITS:
        return False
    # kill sentences that are >35% digits/symbols (price prints)
    alpha = sum(ch.isalpha() for ch in s)
    if alpha / max(len(s), 1) < 0.6:
        return False
    # need at least 6 words
    if len(s.split()) < MIN_WORDS:
        return False
    return True

# ---------------------------------------------------------------- topics
TOPIC_PATTERNS = [
    ("stop", [
        r"\bstop ?loss", r"\bstop\b(?!.*\btrading\b)", r"\bsl\b", r"\bbreak.?even\b",
        r"\bbe stop\b", r"\binvalidat", r"\bcut (?:the )?loss", r"\bstopped out\b",
        r"\brisk (?:is|goes|below|above|under|over)\b", r"\bwhere .{0,15}stop\b",
    ]),
    ("target", [
        r"\btarget", r"\btake profit", r"\btp\d?\b", r"\bscale (?:out|off)\b",
        r"\bpartial", r"\btrim", r"\brunner", r"\b\d+ ?r\b", r"\br:?r\b",
        r"\brisk.?to.?reward", r"\breward", r"\bprofit tak", r"\bhold for\b",
        r"\blet .{0,20}run\b", r"\bexit", r"\bsell half\b", r"\btake .{0,10}off\b",
    ]),
    ("size", [
        r"\bsize\b", r"\bsizing\b", r"\bcontracts?\b", r"\bposition size",
        r"\brisk \d", r"\b\d+ ?% of\b", r"\bper trade\b", r"\bbuying power\b",
        r"\baccount\b", r"\bcapital\b", r"\bstrike\b", r"\bpremium\b",
        r"\bitm\b", r"\botm\b", r"\bdte\b", r"\btheta\b", r"\bgreeks\b",
        r"\bdrawdown\b", r"\bprop firm\b",
    ]),
    ("level", [
        r"\blevel", r"\bpmh\b", r"\bpml\b", r"\bpdh\b", r"\bpdl\b", r"\bhod\b",
        r"\blod\b", r"\bvwap\b", r"\bopening range\b", r"\borb\b", r"\bsupport\b",
        r"\bresistance\b", r"\bpremarket (?:high|low|level)", r"\bkey level",
        r"\bold (?:high|low)", r"\bdaily level", r"\bgap fill\b", r"\bmark(?:ed|ing)? .{0,10}level",
    ]),
    ("entry", [
        r"\bentry\b", r"\benter", r"\bconfirmation\b", r"\bretest", r"\bbreak.?and.?retest",
        r"\bcandle close", r"\bclose (?:above|below|through)", r"\bwait for\b",
        r"\bdisplacement\b", r"\bsignal bar\b", r"\btrigger", r"\bchase\b",
        r"\bfill\b", r"\bocr\b", r"\bone candle\b", r"\border block\b",
        r"\bpullback\b", r"\bfvg\b", r"\bimbalance\b",
    ]),
    ("grade", [
        r"\ba\+? setup", r"\bgrade", r"\bquality\b", r"\bclean(?:est)?\b",
        r"\bhigh (?:probability|prob)\b", r"\bprobability\b", r"\bconfluence\b",
        r"\btextbook\b", r"\bbest setups?\b", r"\bcriteria\b", r"\bchecklist\b",
    ]),
    ("when_not", [
        r"\bchop", r"\bno trade", r"\bdon'?t trade\b", r"\bstay (?:out|flat)\b",
        r"\bsit (?:on|out)\b", r"\bwait\b.{0,20}\b(?:news|fomc|cpi)\b",
        r"\bfomc\b", r"\bcpi\b", r"\bnews\b", r"\bearnings\b", r"\bavoid\b",
        r"\bno (?:clear )?edge\b", r"\bcall it a day\b", r"\bdone for the day\b",
        r"\bstop trading\b", r"\bafter \d{1,2}(?::\d\d)?\s*(?:am|oclock|o'clock)?\b",
        r"\blow volume\b", r"\bholiday\b", r"\bhalf day\b", r"\bmidday\b",
        r"\blunch\b", r"\btoo (?:late|early|choppy|wide)\b", r"\bnot worth\b",
    ]),
    ("psychology", [
        r"\bpsycholog", r"\bemotion", r"\brevenge\b", r"\bovertrad", r"\bfomo\b",
        r"\bdiscipline\b", r"\bpatien", r"\bgreed", r"\bfear\b", r"\btilt\b",
        r"\bjournal", r"\bmindset\b", r"\bconfiden", r"\bprocess\b", r"\bplan\b",
        r"\bstick to\b", r"\brules?\b(?!.*\blevel\b)", r"\bwalk away\b",
        r"\bstep away\b", r"\bbreathe\b", r"\bpressure\b", r"\bfrustrat",
    ]),
]
TOPIC_RE = [(name, re.compile("|".join(p), re.I)) for name, p in TOPIC_PATTERNS]
# priority order when several match: the most specific mechanic wins
TOPIC_PRIORITY = ["stop", "target", "size", "when_not", "level", "entry", "grade", "psychology"]

def topic_of(s: str) -> str:
    hits = {}
    for name, rx in TOPIC_RE:
        n = len(rx.findall(s))
        if n:
            hits[name] = n
    if not hits:
        return "other"
    best = max(hits.values())
    tied = [k for k, v in hits.items() if v == best]
    for t in TOPIC_PRIORITY:
        if t in tied:
            return t
    return tied[0]

# ---------------------------------------------------------------- clustering
STOP_WORDS = set("""a an the and or but if then of to in on at for with from by as is are was were
be been being it its it's this that these those i you we they he she my your our their me us them
do does did doing done have has had will would can could should shall may might must not no yes so
very just really much more most some any all one two get got go going gonna about into out up down
than there here what which who when where how why also too own same s t don dont im ive youre thats
like want need know think see look looking say said thing things way lot really actually""".split())

WORD_RE = re.compile(r"[a-z0-9]+")

def norm_tokens(s: str):
    toks = WORD_RE.findall(s.lower())
    out = set()
    for w in toks:
        if w in STOP_WORDS or len(w) < 3:
            continue
        # crude stem
        for suf in ("ing", "ies", "ed", "es", "s"):
            if len(w) > 4 and w.endswith(suf):
                w = w[: -len(suf)]
                break
        out.add(w)
    return out

def jaccard(a, b):
    """Blend of Jaccard and overlap coefficient. Overlap lets a terse
    restatement pool with a longer one that says the same thing; the 0.8
    discount stops a 3-token fragment swallowing everything it sits inside."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return max(inter / len(a | b), 0.8 * inter / min(len(a), len(b)))

CLUSTER_T = 0.42

def clarity(s: str) -> float:
    """Pick the clearest verbatim: normative density, mid length, few pronouns."""
    n = len(NORM_RE.findall(s)) + len(DOMAIN_RE.findall(s))
    L = len(s)
    # 60..180 chars is the sweet spot
    length_pen = 0.0 if 55 <= L <= 190 else (abs(L - 120) / 200.0)
    vague = len(re.findall(r"\b(?:this|that|it|there|thing|stuff|kinda|maybe|probably)\b", s, re.I))
    return n - length_pen * 3 - vague * 0.7


# --------------------------------------------------- corpus-wide frequency
# The filtered pool is deliberately narrow. Frequency is signal, so count how
# often each clustered rule is RESTATED anywhere a mentor speaks -- across all
# channels including the live-alert ones -- without letting those looser
# sentences into the rulebook itself.
FREQ_SOURCES = ["questions.jsonl", "general_chat.jsonl", "tips.jsonl",
                "maxims_futures.jsonl", "reviews_options.jsonl",
                "reviews_futures.jsonl", "reviews_jdub.jsonl", "misc.jsonl",
                "backtesting.jsonl", "scarface_alerts.jsonl",
                "jdub_alerts.jsonl", "live_sessions.jsonl",
                "pre_market_live.jsonl"]

def build_freq_pool():
    pool = []
    for fname in FREQ_SOURCES:
        path = os.path.join(HERE, fname)
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("author") not in MENTORS:
                continue
            for f in ("rule", "reason", "quote"):
                txt = clean(d.get(f) or "")
                if not txt:
                    continue
                for s in sentences(txt):
                    if len(s.split()) < 5:
                        continue
                    pool.append((norm_tokens(s), MENTORS[d["author"]], s, fname))
    return pool

# Frequency uses PURE Jaccard with a hard floor on shared content tokens.
# The overlap-coefficient blend used for clustering is far too generous here:
# at 0.40 it scored "Need to see buyers step up into market open" as restated
# 303 times, because sharing "key/level/market" with a long sentence was enough.
FREQ_T = 0.45
FREQ_MIN_SHARED = 5

def freq_match(a, b):
    if not a or not b:
        return False
    inter = len(a & b)
    if inter < FREQ_MIN_SHARED:
        return False
    return inter / len(a | b) >= FREQ_T

# ---------------------------------------------------------------- main
def main():
    seen_text = set()
    exact_dupes = collections.Counter()
    cands = []
    src_counts = collections.Counter()
    raw_counts = collections.Counter()

    for fname, fields, mentors_only, strict in SOURCES:
        path = os.path.join(HERE, fname)
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            author = d.get("author")
            if mentors_only and author not in MENTORS:
                continue
            raw_counts[fname] += 1
            for f in fields:
                txt = clean(d.get(f) or "")
                if not txt:
                    continue
                for s in sentences(txt):
                    if not is_rule(s, strict):
                        continue
                    key = " ".join(WORD_RE.findall(s.lower()))
                    if key in seen_text:
                        exact_dupes[key] += 1
                        continue
                    seen_text.add(key)
                    cands.append({
                        "text": s,
                        "key": key,
                        "author": MENTORS.get(author, author),
                        "author_raw": author,
                        "src_file": fname,
                        "src_channel": d.get("src"),
                        "msg_id": d.get("msg_id"),
                        "ts": d.get("ts"),
                        "field": f,
                        "is_mentor": author in MENTORS,
                        "strict": strict,
                        "topic": topic_of(s),
                        "tokens": norm_tokens(s),
                    })
                    src_counts[fname] += 1

    # cluster within topic
    by_topic = collections.defaultdict(list)
    for c in cands:
        by_topic[c["topic"]].append(c)

    clusters = []
    for topic, rows in by_topic.items():
        rows.sort(key=lambda r: -clarity(r["text"]))
        assigned = [None] * len(rows)
        heads = []
        for i, r in enumerate(rows):
            if assigned[i] is not None:
                continue
            hid = len(heads)
            heads.append({"topic": topic, "members": [r], "tokens": set(r["tokens"])})
            assigned[i] = hid
            for j in range(i + 1, len(rows)):
                if assigned[j] is not None:
                    continue
                if jaccard(r["tokens"], rows[j]["tokens"]) >= CLUSTER_T:
                    assigned[j] = hid
                    heads[hid]["members"].append(rows[j])
        clusters.extend(heads)

    # corpus-wide restatement frequency
    pool = build_freq_pool()
    print("frequency pool (mentor sentences, all channels): %d" % len(pool))
    for c in clusters:
        ctoks = set()
        for m in c["members"]:
            ctoks |= m["tokens"]
        head_toks = max(c["members"], key=lambda m: clarity(m["text"]))["tokens"]
        hits = []
        for ptoks, pauth, ptext, pfile in pool:
            if freq_match(head_toks, ptoks):
                hits.append((pauth, ptext, pfile))
        c["restated"] = hits
        c["exact_dupes"] = sum(exact_dupes.get(m["key"], 0) for m in c["members"])

    clusters.sort(key=lambda c: (-(len(c["members"]) + len(c["restated"])), c["topic"]))

    with open(OUT, "w", encoding="utf-8") as fh:
        for k, c in enumerate(clusters):
            mem = c["members"]
            head = max(mem, key=lambda m: clarity(m["text"]))
            rec = {
                "cluster_id": "SF%03d" % k,
                "topic": c["topic"],
                "count": len(mem),
                "restated_corpus_wide": len(c["restated"]),
                "exact_duplicate_posts": c["exact_dupes"],
                "frequency": len(mem) + len(c["restated"]) + c["exact_dupes"],
                "restated_by": dict(collections.Counter(a for a, _, _ in c["restated"])),
                "restated_samples": [
                    {"author": a, "text": t, "src_file": f}
                    for a, t, f in c["restated"][:8]
                ],
                "verbatim": head["text"],
                "authors": sorted({m["author"] for m in mem}),
                "mentor_count": sum(1 for m in mem if m["is_mentor"]),
                "author_counts": dict(collections.Counter(m["author"] for m in mem)),
                "first_ts": min((m["ts"] or "") for m in mem),
                "last_ts": max((m["ts"] or "") for m in mem),
                "head_msg_id": head["msg_id"],
                "head_src": head["src_channel"],
                "restatements": [
                    {"text": m["text"], "author": m["author"], "ts": m["ts"],
                     "msg_id": m["msg_id"], "src": m["src_channel"]}
                    for m in sorted(mem, key=lambda m: -clarity(m["text"]))
                ],
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    tc = collections.Counter(c["topic"] for c in clusters)
    mc = collections.Counter()
    for c in clusters:
        for m in c["members"]:
            mc[m["author"]] += 1
    print("candidate sentences: %d" % len(cands))
    print("clusters:            %d" % len(clusters))
    print("multi-member:        %d" % sum(1 for c in clusters if len(c["members"]) > 1))
    print("per source:", dict(src_counts))
    print("per topic (clusters):", dict(tc))
    print("per author (sentences):", dict(mc))
    print("wrote", OUT)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
