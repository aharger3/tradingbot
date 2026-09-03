"""G7.1/scarface: reconstruct day-symbol trade sequences from alert channels.
Unit is (date, symbol), not message: an alert chain is entry -> manage -> exit.
Read-only over discord_data. Prints counts only."""
import json, re, sys
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timedelta

DATA = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\discord_data")

SYMS = ("SPY QQQ IWM AAPL TSLA NVDA AMD AMZN META MSFT GOOGL GOOG NFLX COIN HOOD PLTR "
        "SMCI MSTR AVGO MU BABA SHOP CRM UBER DIS BA INTC GME SOFI RIVN LCID").split()
TICK = re.compile(r'\b(' + '|'.join(SYMS) + r')\b', re.I)

ENTRY = re.compile(r'\b(took|taking|in\s+at|entered|entry|bought|buying|grabbed|added|'
                   r'\d+(?:\.\d+)?\s*(calls?|puts?)|long\s+here|short\s+here|filled)\b', re.I)
EXIT  = re.compile(r'\b(out\b|sold|selling|stopped|stop\s*out|trimmed|trimming|scaled|'
                   r'took\s+profit|closed|flat\b|pt\s*1|pt\s*2|runner)\b', re.I)
STOPPED = re.compile(r'\b(stopped|stop\s*out|stopped\s+out|full\s+stop)\b', re.I)
WIN   = re.compile(r'\b(out\s+full|took\s+profit|trimmed|pt\s*[12]|target\s+hit|\$\s?[\d,.]+k?)\b', re.I)
DOLLAR= re.compile(r'\$\s?([\d,]+(?:\.\d+)?)\s*k?\b', re.I)
LEVEL = re.compile(r'\b(\d{2,4}\.\d{1,2}|\d{3,4})\b')
DIRC  = re.compile(r'\b(call|calls|long|bull)\b', re.I)
DIRP  = re.compile(r'\b(put|puts|short|bear)\b', re.I)
IMGEXT= re.compile(r'\.(png|jpe?g|gif|webp)(\?|$)', re.I)

def chart(m):
    for x in (m.get("attachments") or []) + (m.get("embeds") or []):
        s = x if isinstance(x,str) else json.dumps(x)
        if IMGEXT.search(s): return True
    return False

def window(ts):
    """UTC ts -> is it inside OMEN 09:30-11:00 ET? EDT=UTC-4, EST=UTC-5."""
    t = datetime.fromisoformat(ts)
    mo = t.month
    off = 4 if 3 <= mo <= 10 else 5   # coarse DST
    et = t - timedelta(hours=off)
    m = et.hour*60 + et.minute
    return 9*60+30 <= m <= 11*60, et

def run(fname, author_filter=None):
    d = json.load(open(DATA/fname, encoding='utf-8'))
    if author_filter:
        d = [m for m in d if author_filter in (m.get("author") or "")]
    # carry-forward symbol: alerts often say "this level" after naming the symbol
    seqs = defaultdict(list)
    last_sym = {}
    for m in sorted(d, key=lambda x: x.get("ts","")):
        ts = m.get("ts") or ""
        if not ts: continue
        c = m.get("content") or ""
        day = ts[:10]
        hit = TICK.findall(c)
        if hit:
            sym = hit[0].upper()
            last_sym[day] = sym
        else:
            sym = last_sym.get(day)
        if not sym: continue
        seqs[(day, sym)].append(m)
    return seqs

def classify(msgs):
    txt = " \n ".join((m.get("content") or "") for m in msgs)
    has_entry = bool(ENTRY.search(txt))
    has_exit  = bool(EXIT.search(txt))
    has_lvl   = bool(LEVEL.search(txt))
    ncall = len(DIRC.findall(txt)); nput = len(DIRP.findall(txt))
    direction = "call" if ncall>nput else ("put" if nput>ncall else None)
    if STOPPED.search(txt): outcome="loss"
    elif WIN.search(txt):   outcome="win"
    else:                   outcome=None
    dol = DOLLAR.findall(txt)
    nchart = sum(1 for m in msgs if chart(m))
    inwin = any(window(m["ts"])[0] for m in msgs)
    return dict(entry=has_entry, exit=has_exit, level=has_lvl, direction=direction,
                outcome=outcome, dollars=dol, charts=nchart, in_window=inwin, n=len(msgs))

if __name__ == "__main__":
    for fname, auth in [("scarface-alerts.json","TonyMontana"),
                        ("jdub-alerts.json","Jdub"),
                        ("futures-alerts.json",None),
                        ("swing-ideas.json",None),
                        ("trade-feedback.json",None)]:
        seqs = run(fname, auth)
        C = Counter()
        usable=[]
        for k,v in seqs.items():
            c = classify(v)
            C["daysym"]+=1
            C["w_entry"]+= c["entry"]
            C["w_exit"] += c["exit"]
            C["w_lvl"]  += c["level"]
            C["w_dir"]  += c["direction"] is not None
            C["w_out"]  += c["outcome"] is not None
            C["w_chart"]+= c["charts"]>0
            C["in_win"] += c["in_window"]
            full = bool(c["entry"] and c["level"] and c["direction"] and c["outcome"])
            C["FULL"] += full
            C["FULL_win"] += bool(full and c["in_window"])
            if full and c["in_window"]: usable.append((k,c))
        print(f"{fname:24s} daysym={C['daysym']:5d} entry={C['w_entry']:5d} exit={C['w_exit']:5d} "
              f"lvl={C['w_lvl']:5d} dir={C['w_dir']:5d} outcome={C['w_out']:5d} chart={C['w_chart']:5d} "
              f"inWindow={C['in_win']:5d} | FULL(sym+dir+lvl+outcome)={C['FULL']:4d} "
              f"FULL&inWindow={C['FULL_win']:4d}")

def overlap_report():
    import sys; sys.path.insert(0,'research')
    from build_deck import marked_card_ids
    marked = set(marked_card_ids())
    import universe as U
    uni = set(getattr(U,'SYMBOLS',None) or getattr(U,'UNIVERSE',None) or [])
    print(f"\nAustin marked symbol-days: {len(marked)}   universe symbols: {len(uni)}")
    for fname, auth in [("scarface-alerts.json","TonyMontana"),
                        ("jdub-alerts.json","Jdub"),
                        ("trade-feedback.json",None),
                        ("futures-alerts.json",None),
                        ("swing-ideas.json",None)]:
        seqs = run(fname, auth)
        setup=0; setup_win=0; new=0; new_uni=0; withchart=0; overlap=0
        for (day,sym),v in seqs.items():
            c = classify(v)
            # a SETUP CALL = symbol + direction + a level. outcome comes from bars.
            if not (c["direction"] and c["level"]): continue
            setup+=1
            if not c["in_window"]: continue
            setup_win+=1
            cid = f"{sym}_{day}"
            if cid in marked: overlap+=1
            else:
                new+=1
                if not uni or sym in uni: new_uni+=1
            if c["charts"]: withchart+=1
        print(f"{fname:24s} setupCalls={setup:5d} inWindow={setup_win:5d} "
              f"alreadyMarkedByAustin={overlap:4d} NEW={new:5d} NEW&inUniverse={new_uni:5d} withChart={withchart:5d}")

overlap_report()
