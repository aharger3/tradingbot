import os,sys,inspect
os.chdir(r"C:\Users\aharg\Desktop\Projects\tradingbot")
sys.path.insert(0,"research")
import marks_pool as mp, build_deck as bd
for f in [mp.row_grade, mp._judgement_key, mp.build_pool, bd._judgement_key]:
    print("=====",f.__name__); print(inspect.getsource(f)[:3500])
