import os,glob
os.chdir(r"C:\Users\aharg\Desktop\Projects\tradingbot\research")
for f in ["g83_futures_arm.md","g171_futures_proxy_arms.md","propfirm_overlay_search.md","edge_slices_2026-09-26.md","r1_referee.md","g213_instruments.md","tape/nightly.md","g86_honest_ceiling.md","g85_honest_book.md"]:
    try: s=open(f,encoding="utf-8",errors="ignore").read()
    except Exception as e: print("MISSING",f); continue
    print("=====",f,len(s)); print(s[:1800])
print("===== orb-ish files", [f for f in glob.glob("**/*",recursive=True) if any(k in f.lower() for k in ("orb","opening_range","es_","nq_","futures")) and "agent_runs" not in f][:60])
