import os,re,glob
os.chdir(r"C:\Users\aharg\Desktop\Projects\tradingbot")
for f in ["research/build_deck.py"]+glob.glob("research/*deck*.py")[:20]:
    try: s=open(f,encoding="utf-8").read()
    except: continue
    hits=[l.strip()[:200] for l in s.splitlines() if re.search(r"truncat|n_bars|blind|hindsight|cut_at|bars_until|up to the|11:00",l,re.I)]
    if hits: print("==",f); [print("  ",h) for h in hits[:15]]
