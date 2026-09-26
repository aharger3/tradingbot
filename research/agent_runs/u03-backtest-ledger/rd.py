import re,glob,os
os.chdir(r"C:\Users\aharg\Desktop\Projects\tradingbot\research")
L=open("g88_level_limit.py",encoding="utf-8").read().splitlines()
print("\n".join(L[115:235]))
for f in glob.glob("g80_*.py"):
    s=open(f,encoding="utf-8").read()
    for fn in ("def limit_touch","def run_trade","def price("):
        i=s.find(fn)
        if i>=0: print("=====",f,fn); print(s[i:i+2200])
