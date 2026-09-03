"""G7.1 adversarial verify (scarface): does review-channel TEXT carry parseable trade info?
Read-only. Writes nothing but stdout."""
import json,re
from pathlib import Path
D=Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\discord_data")
FILES=["options-trade-reviews","futures-trade-reviews","scarface-trade-reviews","jdub-trade-reviews"]
# open-vocabulary ticker: uppercase 1-5 letters, not a stopword
STOP=set("""A I AM PM ET EST EDT UTC AND THE FOR NEW OK NO YES ALL BUY SELL LONG SHORT CALL PUT CALLS PUTS
TRADE REVIEW RECAP LIVE ZOOM VIDEO PASSCODE EVERYONE HERE DAY WEEK JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC
MON TUE WED THU FRI TODAY GM GN LOL WTF FYI TL DR US UK AI CEO CPI FOMC PPI NFP GDP OPEX EOD BE PT TP SL HOD LOD
PDH PDL VWAP EMA SMA RSI ATR OTM ITM ATM DTE IV OI ES NQ RTY YM CL GC MNQ MES MYM M2K""".split())
TICK=re.compile(r'\b[A-Z]{1,5}\b')
DIRW=re.compile(r'\b(call|put|calls|puts|long|short|bull|bear|bullish|bearish)\b',re.I)
DATEW=re.compile(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(st|nd|rd|th)?\b',re.I)
DATEW2=re.compile(r'\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b')
VID=re.compile(r'(zoom\.us|youtube\.com|youtu\.be|vimeo)',re.I)
for fn in FILES:
    d=json.load(open(D/(fn+".json"),encoding='utf-8'))
    n=len(d); nvid=0; ntick=0; ndir=0; ndate=0; ntrio=0; nonvid=0; nonvid_trio=0
    nonvid_text=0
    for m in d:
        c=m.get("content","") or ""
        emb=" ".join(json.dumps(e) for e in (m.get("embeds") or []))
        v=bool(VID.search(c) or VID.search(emb))
        tk=[t for t in TICK.findall(c) if t not in STOP]
        # strip the zoom URL before ticker scan (URLs contain caps)
        c2=re.sub(r'https?://\S+','',c)
        tk=[t for t in TICK.findall(c2) if t not in STOP]
        dr=bool(DIRW.search(c2)); dt=bool(DATEW.search(c2) or DATEW2.search(c2))
        nvid+=v; ntick+=bool(tk); ndir+=dr; ndate+=dt
        trio=bool(tk) and dr and dt
        ntrio+=trio
        if not v:
            nonvid+=1; nonvid_trio+=trio
            if len(re.sub(r'\s+','',c2))>40: nonvid_text+=1
    print(f"{fn:28s} n={n:4d} vid={nvid:4d} nonvid={nonvid:4d} | tick={ntick:4d} dir={ndir:4d} date={ndate:4d} TICK+DIR+DATE={ntrio:4d} | nonvid_with_40+chars_text={nonvid_text:4d} nonvid_trio={nonvid_trio:3d}")
