"""G7.1 adversarial verify (scarface). Real title parser over the 4 'trade review' channels.
Tests: 'the review channels contain no trade reviews; any text pipeline returns nothing.'
Read-only; stdout only."""
import json,re,sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
ROOT=Path(r"C:\Users\aharg\Desktop\Projects\tradingbot"); D=ROOT/"discord_data"
FILES=["options-trade-reviews","futures-trade-reviews","scarface-trade-reviews","jdub-trade-reviews"]
UNI=set(re.findall(r"['\"]([A-Z]{1,5})['\"]",(ROOT/"universe.py").read_text(encoding='utf-8')))
FUT={"NQ","ES","MNQ","MES","RTY","YM","CL","GC","MYM","M2K","SPX","NDX"}
EXTRA={"AMD","GME","BA","DIS","SHOP","NFLX","LCID","XLK","ARM","APP","NOW","ANET"}
SYMS=UNI|FUT|EXTRA
MON=r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)'
RE_MD=re.compile(MON+r'\s+(\d{1,2})(?:st|nd|rd|th)?',re.I)
RE_SLASH=re.compile(r'\b\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?\b')
RE_USD=re.compile(r'(-|\+|lost\s+|loss\s+|made\s+|profit[: ]+|down\s+)?\$\s?\d[\d,\.]*\s?[kK]?',re.I)
RE_NEG=re.compile(r'(-\s?\$|\blost\b|\bloss\b|\bred\b|\bdown\b)',re.I)
RE_SETUP=re.compile(r'break\s*(?:and|&|n)?\s*retest|retest|reclaim|pdh|pdl|pwh|pwl|vwap|one\s*candle',re.I)
RE_VID=re.compile(r'(zoom\.us|youtube\.com|youtu\.be|vimeo)',re.I)
RE_SYM=re.compile(r'\b[A-Z]{1,5}\b')
c={f:dict(n=0,vid=0,date=0,sym=0,usd=0,setup=0,d_s=0,d_u=0,d_s_u=0,loss=0) for f in FILES}
ex=[]
for fn in FILES:
    for m in json.load(open(D/(fn+".json"),encoding='utf-8')):
        raw=m.get("content","") or ""
        emb=" ".join(json.dumps(e) for e in (m.get("embeds") or []))
        t=re.sub(r'https?://\S+',' ',raw)
        k=c[fn]; k["n"]+=1
        k["vid"]+=bool(RE_VID.search(raw) or RE_VID.search(emb))
        dt=bool(RE_MD.search(t) or RE_SLASH.search(t))
        sy=[x for x in RE_SYM.findall(t) if x in SYMS]
        us=bool(RE_USD.search(t)); st=bool(RE_SETUP.search(t))
        k["date"]+=dt; k["sym"]+=bool(sy); k["usd"]+=us; k["setup"]+=st
        k["loss"]+=bool(RE_NEG.search(t)) and us
        k["d_s"]+=dt and bool(sy); k["d_u"]+=dt and us; k["d_s_u"]+=dt and bool(sy) and us
        if dt and sy and us: ex.append((fn,m["ts"][:10],sy[:3],t.strip().replace("\n"," ")[:110]))
h=f"{'channel':26s}{'n':>5}{'vid':>5}{'date':>6}{'sym':>5}{'$pnl':>6}{'setup':>6}{'D+S':>5}{'D+$':>5}{'D+S+$':>7}{'lossPnL':>8}"
print(h); print("-"*len(h))
T=dict(n=0,vid=0,date=0,sym=0,usd=0,setup=0,d_s=0,d_u=0,d_s_u=0,loss=0)
for fn in FILES:
    k=c[fn]
    for q in T: T[q]+=k[q]
    print(f"{fn:26s}{k['n']:>5}{k['vid']:>5}{k['date']:>6}{k['sym']:>5}{k['usd']:>6}{k['setup']:>6}{k['d_s']:>5}{k['d_u']:>5}{k['d_s_u']:>7}{k['loss']:>8}")
print("-"*len(h))
print(f"{'TOTAL 4 review channels':26s}{T['n']:>5}{T['vid']:>5}{T['date']:>6}{T['sym']:>5}{T['usd']:>6}{T['setup']:>6}{T['d_s']:>5}{T['d_u']:>5}{T['d_s_u']:>7}{T['loss']:>8}")
print("\n-- DATE+SYM+$PNL rows (all) --")
for r in ex: print("  ",r[0][:22],r[1],r[2],"|",r[3])
