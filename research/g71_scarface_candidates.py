"""G7.1/scarface: build candidate trade-review records from discord alert channels.

These are SCARFACE'S (and other coaches') judgements, NOT Austin's. They are written
to research/g71_scarface_candidates.jsonl and must NEVER be pooled into any Austin
mark corpus without him saying so. Read-only over discord_data/ and the mark corpora.

Unit = (date, symbol). Tiering:
  T1 text-complete : direction + numeric level parsed from the message text
  T2 text-direction: direction only, level lives on the attached chart image
  T3 chart-only    : symbol + chart, no direction in text
Outcome is NOT taken from the text (only 83/1129 state one). It is computed later by
replaying bars through stop_rule.stop_fill_price(), the way align_reviews_v2.py does.
"""
import json, re, sys
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timedelta

ROOT = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot")
DATA = ROOT/"discord_data"
IMGS = DATA/"images"
sys.path.insert(0, str(ROOT/"research")); sys.path.insert(0, str(ROOT))
from build_deck import marked_card_ids
import universe as U

SYMS = set(U.ALL_SYMS) | set(U.BACKTEST_SYMBOLS)
TICK = re.compile(r'\b(' + '|'.join(sorted(SYMS, key=len, reverse=True)) + r')\b', re.I)
ENTRY= re.compile(r'\b(took|taking|in\s+at|entered|entry|bought|buying|grabbed|added|'
                  r'\d+(?:\.\d+)?\s*(?:calls?|puts?)|long\s+here|short\s+here|filled)\b', re.I)
STOPPED=re.compile(r'\b(stopped|stop\s*out|full\s+stop)\b', re.I)
WINTXT=re.compile(r'\b(out\s+full|took\s+profit|trimmed|pt\s*[12]|target\s+hit)\b', re.I)
DOLLAR=re.compile(r'\$\s?([\d,]+(?:\.\d+)?)\s*(k?)\b', re.I)
LEVEL= re.compile(r'\b(\d{2,4}\.\d{1,2})\b')
# CRITICAL: alert text carries the option STRIKE far more often than the chart LEVEL.
# 481 scarface messages match a strike; only 49 state a level in context. A strike is
# NOT a break-and-retest level -- it is the contract, usually slightly OTM, so it sits
# just outside the day's range. Split them or the backtest is fed garbage.
STRIKE=re.compile(r'(\d{2,4}(?:\.\d{1,2})?)\s*(?:strike\s*)?(?:calls?|puts?)\b',re.I)
LVLCTX=re.compile(r'(?:level|retest|reclaim|pdh|pdl|hod|lod|above|below|holds?|break)\D{0,18}(\d{2,4}\.\d{1,2})',re.I)
DIRC = re.compile(r'\b(calls?|long|bull(?:ish)?|reclaim|buyers)\b', re.I)
DIRP = re.compile(r'\b(puts?|short|bear(?:ish)?|sellers|reject)\b', re.I)
SETUP= re.compile(r'\b(retest|break\s*and\s*retest|b&r|reclaim|orb|pdh|pdl|hod|lod|'
                  r'premarket\s+high|premarket\s+low|pm\s+high|pm\s+low|key\s+level)\b', re.I)
IMGEXT=re.compile(r'\.(png|jpe?g|gif|webp)(\?|$)', re.I)

CHANNELS = [("scarface-alerts.json","TonyMontana","Scarface"),
            ("jdub-alerts.json","Jdub","Jdub"),
            ("futures-alerts.json",None,"futures"),
            ("trade-feedback.json",None,"members"),
            ("swing-ideas.json",None,"swing"),
            ("backtesting.json",None,"backtesting"),
            ("trading-floor.json",None,"floor")]

def has_chart(m):
    for x in (m.get("attachments") or []) + (m.get("embeds") or []):
        s = x if isinstance(x,str) else json.dumps(x)
        if IMGEXT.search(s): return True
    return False

def et(ts):
    t = datetime.fromisoformat(ts); off = 4 if 3 <= t.month <= 10 else 5
    return t - timedelta(hours=off)

def in_window(ts):
    e = et(ts); m = e.hour*60+e.minute
    return 9*60+30 <= m <= 11*60

def build():
    marked = set(marked_card_ids())
    out, stats = [], Counter()
    for fname, auth, tag in CHANNELS:
        p = DATA/fname
        if not p.exists(): continue
        d = json.load(open(p, encoding='utf-8'))
        if auth: d = [m for m in d if auth in (m.get("author") or "")]
        seqs, last = defaultdict(list), {}
        for m in sorted(d, key=lambda x: x.get("ts","")):
            ts = m.get("ts") or ""
            if not ts: continue
            c = m.get("content") or ""; day = ts[:10]
            hit = TICK.findall(c)
            sym = hit[0].upper() if hit else last.get(day)
            if hit: last[day] = sym
            if not sym: continue
            seqs[(day,sym)].append(m)
        for (day,sym), msgs in seqs.items():
            wmsgs = [m for m in msgs if in_window(m["ts"])]
            if not wmsgs: continue
            txt = "\n".join((m.get("content") or "") for m in wmsgs)
            nc, np_ = len(DIRC.findall(txt)), len(DIRP.findall(txt))
            direction = "call" if nc>np_ else ("put" if np_>nc else None)
            strikes = sorted({float(x) for x in STRIKE.findall(txt)})
            lvlctx  = sorted({float(x) for x in LVLCTX.findall(txt)})
            lvls = [x for x in sorted({float(x) for x in LEVEL.findall(txt)})
                    if x not in strikes]
            charts = sum(1 for m in wmsgs if has_chart(m))
            cid = f"{sym}_{day}"
            # T1 now requires a LEVEL IN CONTEXT, not any number: a strike is not a level.
            tier = ("T1" if (direction and lvlctx) else
                    "T2" if (direction and charts) else
                    "T3" if charts else "T4")
            claimed = ("loss" if STOPPED.search(txt) else
                       "win" if WINTXT.search(txt) else None)
            rec = dict(card_id=cid, symbol=sym, day=day, source=tag, channel=fname,
                       tier=tier, direction=direction,
                       level_in_context=lvlctx[:6], option_strikes=strikes[:6],
                       bare_numbers=lvls[:6],
                       setup_words=sorted(set(w.lower() for w in SETUP.findall(txt)))[:6],
                       n_msgs=len(wmsgs), n_charts=charts,
                       claimed_outcome=claimed,
                       first_ts=wmsgs[0]["ts"], last_ts=wmsgs[-1]["ts"],
                       msg_ids=[m.get("id") for m in wmsgs][:40],
                       already_marked_by_austin=cid in marked,
                       in_backtest_universe=sym in set(U.BACKTEST_SYMBOLS),
                       judged_by="scarface_or_coach_NOT_austin")
            out.append(rec)
            stats[f"{tag}:{tier}"]+=1
            stats[f"{tag}:ALL"]+=1
            if cid in marked: stats[f"{tag}:overlap"]+=1
    return out, stats

if __name__ == "__main__":
    recs, stats = build()
    dst = ROOT/"research"/"g71_scarface_candidates.jsonl"
    with open(dst,"w",encoding="utf-8") as f:
        for r in recs: f.write(json.dumps(r)+"\n")
    print(f"wrote {dst}  n={len(recs)}")
    marked_hits = sum(1 for r in recs if r["already_marked_by_austin"])
    uniq = {r["card_id"] for r in recs}
    new  = {r["card_id"] for r in recs if not r["already_marked_by_austin"]}
    print(f"distinct symbol-days={len(uniq)}  NEW (not in Austin's 1147)={len(new)}  overlap={len(uniq)-len(new)}")
    for t in ("T1","T2","T3","T4"):
        n = sum(1 for r in recs if r["tier"]==t)
        nn= len({r['card_id'] for r in recs if r['tier']==t and not r['already_marked_by_austin']})
        print(f"  {t}: rows={n:5d}  distinct NEW={nn:5d}")
    print("\nby channel:")
    for k in sorted(stats): print(f"  {k:28s} {stats[k]}")
