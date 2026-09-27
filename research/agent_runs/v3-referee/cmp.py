import json
a=json.load(open("an_spx_before.json")); b=json.load(open(r"..\v3-t-options-spx\an.json"))
print(type(a).__name__, len(a))
for k in ("B1030|flat2R|base","B1030|flat2R|stress","M1030|flat2R|base","A1030|flat2R|base"):
    for nm,d in (("before",a),("now",b)):
        r=d.get(k,{}); o=r.get("opt") or {}
        print(k,nm,"cover",r.get("cover"),"opt n",o.get("n"),"R",o.get("mean"),"H1",(r.get("H1") or {}).get("mean"),"H2",(r.get("H2") or {}).get("mean"),"p",r.get("shuf_p"))
