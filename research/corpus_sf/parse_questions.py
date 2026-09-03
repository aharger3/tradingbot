"""
Deterministic rule-candidate miner for discord_data/questions.json.

SOURCE   : member Q&A channel. Members ask, mentors answer.
TARGET   : the mentors' ANSWERS only -- stated rules, not trades.
OUTPUT   : research/corpus_sf/questions.jsonl (one row per rule candidate sentence)

These are SCARFACE / Jdub / Mamba / Hayden / Neto / Lauren judgements.
They are NOT Austin's marks. Nothing here is ever written into an Austin corpus.

Method (no LLM anywhere in this file):
  1. keep only messages whose author is in MENTORS
  2. strip discord chrome (mentions, channel refs, emoji tags, urls, code fences)
  3. drop admin/support/logistics messages by blacklist
  4. split into sentences
  5. a sentence is a RULE CANDIDATE iff it carries
       (a) >= 1 trading-domain keyword  AND
       (b) >= 1 normative / mechanic marker
     and survives the sentence-level noise filters
  6. topic = argmax over per-topic keyword hit counts, priority tie-break
  7. structured fields (symbol/direction/setup/level/prices/R) are extracted only
     when the sentence literally says them; otherwise null.

Run:  python research/corpus_sf/parse_questions.py
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "discord_data", "questions.json")
OUT = os.path.join(HERE, "questions.jsonl")

# ---------------------------------------------------------------- mentors
# alerters + education hosts, cross-checked against the channels where only
# staff post: scarface-alerts (TonyMontana), jdub-alerts (Jdub),
# futures-alerts (MambaTrades), weekly-live-education (Jdub, Hayden),
# options-trade-reviews (Neto, Hayden, Lauren).
MENTORS = {
    "TonyMontana",                      # Scarface
    "Jdub",
    "MambaTrades",
    "Hayden",
    "Neto Moreno (Performance Coach)",
    "Lauren (lakatrades)",
}

# ---------------------------------------------------------------- cleaning
RE_MENTION = re.compile(r"<@[!&]?\d+>")
RE_CHANNEL = re.compile(r"<#\d+>")
RE_EMOJI_TAG = re.compile(r"<a?:\w+:\d+>")
RE_URL = re.compile(r"https?://\S+")
RE_CODEFENCE = re.compile(r"```.*?```", re.S)
RE_WS = re.compile(r"[ \t]+")
RE_UNICODE_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿️←-⇿⬀-⯿]"
)


def clean(text):
    t = RE_CODEFENCE.sub(" ", text or "")
    t = RE_URL.sub(" ", t)
    t = RE_MENTION.sub(" ", t)
    t = RE_CHANNEL.sub(" ", t)
    t = RE_EMOJI_TAG.sub(" ", t)
    t = RE_UNICODE_EMOJI.sub(" ", t)
    t = t.replace("’", "'").replace("‘", "'")
    t = t.replace("“", '"').replace("”", '"')
    t = t.replace("—", " - ").replace("–", " - ")
    t = RE_WS.sub(" ", t)
    return t.strip()


# ------------------------------------------------------- message blacklist
# v2: only HARD admin tokens kill the whole message. v1 killed the message on
# soft words ("scale ... risk tolerance" died because the message elsewhere said
# "upgrade"), which cost recall -- everything else moved to the sentence list.
MSG_BLACKLIST = re.compile(
    r"\b(whop|refund|invoice|billing|coupon|promo code|password|"
    r"log ?in|login|sign ?up|membership|renew\w*|"
    r"bootcamp|summit|giveaway|merch|affiliate|referral|"
    r"happy birthday|congrats|congratulations)\b",
    re.I,
)

# sentence-level kill list: logistics / pleasantries / platform support
SENT_BLACKLIST = re.compile(
    r"\b(whop|refund|invoice|billing|coupon|promo code|password|"
    r"log-? ?in|login|sign ?up|membership|renew\w*|"
    r"bootcamp|summit|giveaway|merch|affiliate|referral|"
    r"happy birthday|congrats|congratulations|"
    r"module\s*\d|the modules?\b|education vault|accelerator|"
    r"re-?watch|watch (the|our|his|those|any)|videos?\b|"
    r"check out the|go through the|"
    r"live session|weekly (outlook|recap|session)|workshop|webinar|"
    r"discord|zoom\b|replay|recording|uploaded|email\b|dm me|inbox|"
    r"time ?zone|utc\b|browser|wifi|app store|android|iphone\b|"
    r"account settings|base currency|hotkey|layout|widget|"
    r"support ticket|support structure|customer support|"
    r"mentoring|1-?on-?1|coaching|"
    r"level ?(2|two)\b|\barca\b|data feed|nyse\b|"
    r"good morning|good luck|thank you|thanks for|no worries|"
    r"lmk|let me know if|hope (this|that) helps|great question|"
    r"i'?ll (post|share|add)|coming soon|next week we|"
    r"subscri\w*|indicator|commission|platform fee)\b",
    re.I,
)

# not rules: arithmetic worked examples, capital facts, narration, pointers,
# platform-UI instructions, offers of help. (v3, from hand-check round 2.)
SENT_NOTRULE = re.compile(
    # "=" only counts as arithmetic when a digit is next to it -- a legend line
    # ("White = Marked on previous days 15m/1hr level") is a real level rule.
    r"(\d\s*=|=\s*\$?\d|\d\s*[\*x]\s*\d"        # "1 contract .3*100 =$30"
    r"|\bneed (around |about |roughly )?\$?\d+"  # "you only need around $20"
    r"|\bthe only reason (was|is)\b"
    r"|\bexplains the\b"
    r"|\bafford\b"
    # pointers to other material
    r"|\bwatch (as|him|her|them|it)\b|\bgo watch\b"
    r"|\bwatch\b[^.]{0,60}\b(video|module|session|review|replay|recap)"
    r"|\bthat should give you\b|\bunderstanding of how\b"
    r"|\btips? (&|and) tricks?\b"
    r"|\bi can (share|help|show)\b|\blet me know\b|\bsend me\b"
    r"|\b(they|he|she) shares?\b"
    # platform / UI instructions
    r"|\bclick\w*|\bdrop ?down\b|\bmenu\b|\bbutton\b|\bcheck ?box\b"
    r"|\btoggle\b|\bsettings\b|\bplatform\b|\baccount manager\b"
    r"|\bfancy\b|\bexpensive\b|\btools?\b"
    # v4: chart config, pointers, community chatter, worked-dollar narration
    r"|extended hours session|won'?t show up|chart is set to"
    r"|\bwalks? (you )?through\b|\bpre ?-? ?market prep\b"
    r"|\bexperience share\b|\bpaper trad\w+|\bfunded account\b"
    r"|\bwe don'?t share\b|\bchallenges?\b"
    r"|\bi always talk about\b|\bkeep the questions coming\b"
    r"|\bcommunity\b|\bsomething called\b|\banswer (those|these) questions\b"
    r"|\bto make \$\d+|\bwould have to move\b|\bonly went up\b"
    r"|\bwhy you only made\b"
    # v6: brokerage onboarding, support routing, "go read their posts"
    r"|\bapprov\w+|\bquestionn?aire\b|\bunder 21\b"
    r"|\bticket\b|\brecommend (checking|submitting|reaching)\b"
    r"|\bcheck(ing)? out\b|\bchecking (tony|jack|their|his)\b"
    r"|\b(they|he|she) (always |usually |often )?shares?\b"
    r")",
    re.I,
)

# a sentence that ends on a dangling function word is a truncated fragment
RE_DANGLING = re.compile(
    r"\b(to|for|and|but|with|the|a|an|of|on|in|at|is|are|that|my|your)\s*$",
    re.I,
)

# a member question that happens to lack a "?" is not a mentor rule
RE_QUESTION_START = re.compile(
    r"^(how|what|when|where|why|which|who|do you|did you|are you|can you|"
    r"could you|would you|is it|does|anyone|any of)\b",
    re.I,
)

# ---------------------------------------------------------------- lexicons
TOPIC_KW = {
    # order matters for tie-break (earlier wins)
    "stop": [
        r"stop ?loss(es)?", r"\bstops?\b", r"\bsl\b", r"stopped out",
        r"invalidat\w+", r"mental stop", r"hard stop", r"risk (is|was) defined",
        r"stop out", r"below the (low|candle)", r"above the (high|candle)",
        r"break ?even\b", r"\bbe stop", r"move (my|your|the) stop",
    ],
    "target": [
        r"\btargets?\b", r"take ?profit", r"\btp\d?\b", r"\bpt\d?\b",
        r"scale ?(out|off)", r"\btrim\w*", r"\brunner\w*", r"partial\w*",
        r"profit tak\w+", r"\bexit(s|ed|ing)?\b", r"\bsell (half|into)",
        r"first target", r"price target", r"\baim for\b",
        r"let (it|them|winners) (ride|run)", r"\bhold (on )?(to|for)\b",
    ],
    "entry": [
        r"\bentry\b", r"\bentries\b", r"\benter(s|ed|ing)?\b", r"\btrigger\w*",
        r"\bretest\w*", r"\breclaim\w*", r"84%", r"signal (bar|candle)",
        r"break (of|above|below|over|through)", r"\bbreaks?\b",
        r"\bbreakout\w*", r"\bpull ?back\w*", r"\bchase\w*",
        r"limit order", r"market order", r"\bfill(s|ed)?\b",
        r"candle (high|low|close)", r"over (the )?candle", r"one candle",
        r"\bocr\b", r"first (5|15) ?min", r"open(ing)? drive",
        r"\bbnr\b", r"\bb ?& ?r\b", r"\bbos\b",
    ],
    "level": [
        r"\blevels?\b", r"\bpivots?\b", r"\bpdh\b", r"\bpdl\b", r"\bpmh\b",
        r"\bpml\b", r"\bhod\b", r"\blod\b", r"premarket (high|low)",
        r"pre-?market\b", r"previous day", r"prior day", r"\bvwap\b",
        r"\bsupport\b(?!\s+(ticket|structure|team|staff))",
        r"resistance\b", r"\bhtf\b", r"higher time ?frame",
        r"daily level", r"gap ?fill", r"opening range", r"\bor high\b",
        r"\bor low\b", r"consolidat\w+", r"\bflag\b", r"\bwedge\b",
        r"trend ?line", r"red to green", r"\bath\b",
        r"\bdivergen\w+", r"relative (strength|weakness)", r"\bcorrelat\w+",
        r"\btrend(ing|s)?\b", r"\brange\b", r"\bchoppy\b",
        r"\bopening candle\b", r"\bfirst candle\b", r"\border ?block\b",
    ],
    "size": [
        r"\bsiz(e|ing)\b", r"position siz\w+", r"\bcontracts?\b",
        r"\bshares?\b", r"\br multiple\b", r"\b\d+r\b", r"\b1r\b",
        r"risk (per|on) (trade|position)", r"% of (your|the) account",
        r"account size", r"risk manage\w*", r"\bmax loss\b",
        r"\bbuying power\b", r"\bdelta\b", r"\bgreeks?\b", r"\bstrike\w*",
        r"\bexpir\w+", r"\bpremium\b",
    ],
    "grade": [
        r"a\+ setup", r"\ba\+\b", r"\bgrade[sd]?\b", r"\bconfluence\w*",
        r"\bconviction\b", r"best setups?", r"quality (of )?setup",
        r"\ba setup\b", r"clean setup", r"textbook", r"high probability",
        r"\bedge\b", r"criteria",
    ],
    "psychology": [
        r"psycholog\w+", r"disciplin\w+", r"\bpatien\w+", r"\bfomo\b",
        r"revenge trad\w*", r"\bemotion\w*", r"\bgreed\w*", r"\bfear\w*",
        r"overtrad\w*", r"\bjournal\w*", r"\bmindset\b", r"\btilt\w*",
        r"\bconfiden\w+", r"\bstress\w*", r"\bconsisten\w+",
        r"\bhabit\w*", r"\bdiscomfort\b", r"\brevenge\b",
    ],
}
TOPIC_ORDER = ["stop", "target", "entry", "level", "size", "grade", "psychology"]
TOPIC_RE = {k: [re.compile(p, re.I) for p in v] for k, v in TOPIC_KW.items()}

# domain keywords -- any hit qualifies as "about trading"
DOMAIN_RE = [r for pats in TOPIC_RE.values() for r in pats] + [
    re.compile(p, re.I)
    for p in (
        r"\btrade(s|d)?\b", r"\btrading\b", r"\bsetups?\b", r"\bchart\w*",
        r"\bcandles?\b", r"\bvolume\b", r"\bmarket\b", r"\bprice action\b",
        r"\blong\b", r"\bshort\b", r"\bcalls?\b", r"\bputs?\b",
        r"\btime ?frame\w*", r"\bbias\b", r"\bthesis\b",
    )
]

# normative / mechanic markers -- what makes a sentence a RULE
NORMATIVE_RE = [
    re.compile(p, re.I)
    for p in (
        r"\balways\b", r"\bnever\b", r"\bmust\b", r"\bshould\b",
        r"\bneed(s)? to\b", r"\bhave to\b", r"\bhas to\b", r"\bdon'?t\b",
        r"\bdo not\b", r"\bavoid\b", r"\bmake sure\b", r"\bonly\b",
        r"\bwait(ing)? for\b", r"\bwant to see\b", r"\blook(ing)? for\b",
        r"\bthe rule\b", r"\brule is\b", r"\bkey is\b", r"\bideal\w*",
        r"\bgenerally\b", r"\btypically\b", r"\busually\b", r"\bbest to\b",
        r"\bprefer\w*", r"\brecommend\w*", r"\brequire\w*", r"\bat least\b",
        r"\bi (use|enter|exit|take|trade|wait|want|look|set|cut|risk|size)\b",
        r"\bwe (use|enter|exit|take|trade|wait|want|look|set|cut|risk|size)\b",
        r"\byou (want|need|should|can'?t|shouldn'?t)\b",
        r"\bif .* then\b", r"\bonce .*,", r"\bas long as\b",
        r"\bis when\b", r"\bmeans\b", r"\bis called\b", r"\bcounts? as\b",
        r"\bvalid\w*", r"\binvalid\w*", r"\bconsider(s|ed)?\b",
        r"\bmy (rule|stop|entry|target|risk|size)\b",
        r"\bstick to\b", r"\bfocus on\b", r"\btry to\b", r"\bmake it a\b",
        r"\bsignals? a\b", r"\bindicates?\b", r"\bconfirms?\b",
        r"\bis a sign\b",
        r"\baim for\b", r"\bworks? (better|best|well)\b",
        r"\bi'?d (recommend|probably|keep|say|stick|aim|go|use|wait|want)\b",
        r"\blikes? to\b", r"\bis (very )?important\b",
    )
]

# STRONG markers -- v2 requires one of these, so vague self-report
# ("I try to keep it consistent as possible") no longer qualifies as a rule.
STRONG_RE = [
    re.compile(p, re.I)
    for p in (
        r"\balways\b", r"\bnever\b", r"\bmust\b", r"\bshould\b",
        r"\bneed(s)? to\b", r"\bhave to\b", r"\bhas to\b", r"\bdon'?t\b",
        r"\bdo not\b", r"\bavoid\b", r"\bmake sure\b", r"\bonly\b",
        r"\bwait(ing)? for\b", r"\blook(ing)? for\b", r"\brules?\b",
        r"\bideal\w*", r"\bprefer\w*", r"\brecommend\w*", r"\brequire\w*",
        r"\bat least\b", r"\bwant to see\b",
        r"\bi (personally |generally |usually |always |never |only )?"
        r"(enter|exit|use|take|risk|size|cut|target|trade|set|scale|"
        r"wait|want|look|focus|mark|draw)\b",
        r"\bwe (enter|exit|use|take|risk|size|cut|target|trade|set|scale|"
        r"wait|want|look|focus)\b",
        r"\byou (want|need|should|can'?t|shouldn'?t)\b",
        r"\bif (price|it|the stock|you|we|i|there|that|this)\b",
        r"\bis when\b", r"\bmeans\b", r"\bcounts? as\b",
        r"\bsignals? a\b", r"\bindicates?\b", r"\bconfirms?\b",
        r"\bmy (rule|stop|entry|target|risk|size|process)\b",
        r"\bbest to\b", r"\bkey is\b",
        # v5 recall adds, from the skipped-sentence hand-check
        r"\baim for\b", r"\bworks? (better|best|well)\b",
        r"\bi'?d (recommend|probably|keep|say|stick|aim|go|use|wait|want)\b",
        r"\blikes? to\b", r"\bis (very )?important\b", r"\bstick to\b",
    )
]

# ------------------------------------------------------------- extraction
TICKERS = {
    "NVDA", "TSLA", "AAPL", "SPCX", "MSFT", "MU", "INTC", "PLTR", "AMZN",
    "META", "AMD", "GOOGL", "GOOG", "ACHR", "NFLX", "ORCL", "QQQ", "SPY",
    "IWM", "SOFI", "COIN", "HOOD", "IREN", "AVGO", "UBER", "BABA", "CRM",
    "TSM", "MARA", "ES", "NQ", "MNQ", "MES", "RTY", "YM", "CL", "GC",
    "DIA", "VIX", "SMCI", "MSTR", "GME", "AMC", "BA", "NKE", "DIS", "SQ",
    "SHOP", "ROKU", "PYPL", "LULU", "COST", "WMT", "JPM", "XLF", "ARM",
}
RE_TICKER = re.compile(r"\b([A-Z]{2,5})\b")

RE_LONG = re.compile(r"\b(long|calls?|bullish|upside|buy(ing)? calls?)\b", re.I)
RE_SHORT = re.compile(r"\b(short|puts?|bearish|downside|buy(ing)? puts?)\b", re.I)

RE_BR = re.compile(r"\b(break ?(and|&|-)? ?retest|b ?& ?r|bnr|retest)\b", re.I)
RE_OCR = re.compile(r"\b(one ?candle( rule)?|ocr|signal (bar|candle)|"
                    r"over (the )?candle high|under (the )?candle low)\b", re.I)

LEVEL_NAMES = [
    ("or_high", re.compile(r"\b(or high|opening range high|open(ing)? range)\b", re.I)),
    ("pdh", re.compile(r"\b(pdh|previous day(?:'s)? high|prior day high)\b", re.I)),
    ("pdl", re.compile(r"\b(pdl|previous day(?:'s)? low|prior day low)\b", re.I)),
    ("pmh", re.compile(r"\b(pmh|pre-?market high)\b", re.I)),
    ("pml", re.compile(r"\b(pml|pre-?market low)\b", re.I)),
    ("hod", re.compile(r"\b(hod|high of (the )?day)\b", re.I)),
    ("lod", re.compile(r"\b(lod|low of (the )?day)\b", re.I)),
    ("other", re.compile(r"\b(pivot|support|resistance|vwap|daily level|"
                         r"htf level|gap fill)\b", re.I)),
]

RE_PRICE = re.compile(r"(?<![\w.])\$?(\d{1,5}\.\d{1,2})(?![\w%])")
RE_R = re.compile(r"\b(\d+(?:\.\d+)?)\s?r\b", re.I)
RE_OUTCOME_WIN = re.compile(r"\b(hit (my|the) target|worked out|winner|"
                            r"took profit)\b", re.I)
RE_OUTCOME_LOSS = re.compile(r"\b(stopped out|took the loss|loser)\b", re.I)
RE_OUTCOME_BE = re.compile(r"\b(break ?even|scratched)\b", re.I)

# sentence splitter: dumb and deterministic. abbreviations and single-letter
# initials are protected so "hold a small % (I.e. 20%)" stays one sentence.
RE_ABBREV_END = re.compile(
    r"(?:\b(?:i\.e|e\.g|etc|vs|approx|mr|mrs|dr|fig|u\.s|a\.m|p\.m)"
    r"|(?<![A-Za-z])[A-Za-z])\.$",
    re.I,
)
RE_SENT = re.compile(r"(?<=[.!?])\s+|\n+")


def split_sentences(text):
    out = []
    buf = ""
    for chunk in RE_SENT.split(text):
        c = chunk.strip(" -*>")
        if not c:
            continue
        buf = (buf + " " + c).strip() if buf else c
        # if this piece ends on a protected abbreviation, keep accumulating
        if RE_ABBREV_END.search(buf):
            continue
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return out


def n_hits(regexes, s):
    return sum(1 for r in regexes if r.search(s))


def topic_of(s):
    scores = {t: n_hits(TOPIC_RE[t], s) for t in TOPIC_ORDER}
    best = max(scores.values())
    if best == 0:
        return "other", 0
    for t in TOPIC_ORDER:
        if scores[t] == best:
            return t, best
    return "other", 0


def near(s, kw_re, num_re, window=45):
    """number that sits within `window` chars of a keyword match"""
    hits = list(kw_re.finditer(s))
    if not hits:
        return None
    for nm in num_re.finditer(s):
        for h in hits:
            if abs(nm.start() - h.start()) <= window:
                try:
                    return float(nm.group(1))
                except ValueError:
                    return None
    return None


RE_KW_ENTRY = re.compile(r"\b(entry|enter|entered|trigger|fill(ed)?|buy)\b", re.I)
RE_KW_STOP = re.compile(r"\b(stop|sl|risk to|invalidat)\w*", re.I)
RE_KW_TGT = re.compile(r"\b(target|tp\d?|pt\d?|take profit|sell)\w*", re.I)
RE_KW_LEVEL = re.compile(
    r"\b(level|pivot|pdh|pdl|pmh|pml|hod|lod|support|resistance|vwap)\w*", re.I)
# a level is often quoted as a whole number ("above the 180 level")
RE_PRICE_LVL = re.compile(r"(?<![\w.$])(\d{2,5}(?:\.\d{1,2})?)(?![\w%])")


def extract_symbol(s):
    for m in RE_TICKER.finditer(s):
        if m.group(1) in TICKERS:
            return m.group(1)
    return None


def extract_direction(s):
    lo, sh = bool(RE_LONG.search(s)), bool(RE_SHORT.search(s))
    if lo and not sh:
        return "long"
    if sh and not lo:
        return "short"
    return None


def extract_setup(s):
    br, ocr = bool(RE_BR.search(s)), bool(RE_OCR.search(s))
    if br and ocr:
        return "br_ocr"
    if br:
        return "break_retest"
    if ocr:
        return "one_candle"
    return None


def extract_level_name(s):
    for name, r in LEVEL_NAMES:
        if r.search(s):
            return name
    return None


def extract_outcome(s):
    if RE_OUTCOME_LOSS.search(s):
        return "loss"
    if RE_OUTCOME_BE.search(s):
        return "be"
    if RE_OUTCOME_WIN.search(s):
        return "win"
    return None


MIN_LEN = 35
MAX_LEN = 420


def is_rule_candidate(s):
    """returns (ok, domain_hits, norm_hits)"""
    if not (MIN_LEN <= len(s) <= MAX_LEN):
        return False, 0, 0
    if s.rstrip().endswith("?") or s.rstrip().endswith(":"):
        return False, 0, 0
    if RE_QUESTION_START.match(s) or RE_DANGLING.search(s):
        return False, 0, 0
    if SENT_BLACKLIST.search(s) or SENT_NOTRULE.search(s):
        return False, 0, 0
    # needs at least a few words
    if len(s.split()) < 7:
        return False, 0, 0
    d = n_hits(DOMAIN_RE, s)
    n = n_hits(NORMATIVE_RE, s)
    if d == 0 or n == 0:
        return False, d, n
    if not any(r.search(s) for r in STRONG_RE):
        return False, d, n
    return True, d, n


def survives_topic_floor(s, topic, d):
    """psychology is the loosest lexicon; demand more domain signal there."""
    if topic == "psychology" and d < 2:
        return False
    return True


def confidence(d, n, topic):
    if topic == "other":
        return "low"
    if d >= 3 and n >= 2:
        return "high"
    if d >= 2 and n >= 1:
        return "medium"
    return "low"


def main():
    with open(SRC, encoding="utf-8") as f:
        msgs = json.load(f)

    rows = []
    seen = set()
    stats = {
        "total": len(msgs),
        "mentor_msgs": 0,
        "after_msg_blacklist": 0,
        "sentences": 0,
        "emitted": 0,
        "dupes": 0,
    }

    for m in msgs:
        if m.get("author") not in MENTORS:
            continue
        stats["mentor_msgs"] += 1
        raw = m.get("content") or ""
        # v5: NO message-level kill. A long answer that mentions "membership"
        # in sentence 1 can still state a real risk rule in sentence 4 --
        # "Risk Per Trade - I stick to 1-2% of my total account per trade"
        # was being lost that way. Admin tokens now filter per sentence.
        stats["after_msg_blacklist"] += 1
        body = clean(raw)
        if not body:
            continue
        for sent in split_sentences(body):
            stats["sentences"] += 1
            ok, d, n = is_rule_candidate(sent)
            if not ok:
                continue
            topic, _ = topic_of(sent)
            if not survives_topic_floor(sent, topic, d):
                continue
            sym = extract_symbol(sent)
            if topic == "other" and not sym:
                # a topicless sentence is kept only when it names a ticker
                # ("I focus on SPY/QQQ" is a universe rule); otherwise drop.
                continue
            key = (m["author"], re.sub(r"\W+", "", sent.lower()))
            if key in seen:
                stats["dupes"] += 1
                continue
            seen.add(key)
            rows.append({
                "src": "discord_data/questions.json",
                "msg_id": m["id"],
                "ts": m["ts"],                     # export is already ET
                "author": m["author"],
                "rule": sent,
                "topic": topic,
                "symbol": sym,
                "direction": extract_direction(sent),
                "setup": extract_setup(sent),
                "level_price": near(sent, RE_KW_LEVEL, RE_PRICE_LVL, 25),
                "level_name": extract_level_name(sent),
                "entry": near(sent, RE_KW_ENTRY, RE_PRICE),
                "stop": near(sent, RE_KW_STOP, RE_PRICE),
                "target": near(sent, RE_KW_TGT, RE_PRICE),
                "outcome": extract_outcome(sent),
                "r_multiple": (float(RE_R.search(sent).group(1))
                               if RE_R.search(sent) else None),
                "quote": raw,
                "image_urls": list(m.get("attachments") or []),
                "confidence": confidence(d, n, topic),
            })
            stats["emitted"] += 1

    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(json.dumps(stats, indent=1))
    from collections import Counter
    print("topic:", Counter(r["topic"] for r in rows).most_common())
    print("author:", Counter(r["author"] for r in rows).most_common())
    print("conf:", Counter(r["confidence"] for r in rows).most_common())
    print("wrote", OUT, len(rows), "rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
