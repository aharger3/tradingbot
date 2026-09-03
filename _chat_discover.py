"""Discover chat backwards-pagination param + participant batch author lookup.
Write JSON to file (console can't print emoji under cp1252)."""
import json, time, requests, websocket  # type: ignore
CDP_URL = "http://localhost:9222"; COMMUNITY = "traders-lab.circle.so"
UUID = "18763e1d-2730-4483-975d-c49528ba0b8c"
t = requests.put(f"{CDP_URL}/json/new", timeout=10).json()
ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=30, suppress_origin=True)
mid=[0]
def cmd(method, params=None):
    mid[0]+=1; i=mid[0]
    ws.send(json.dumps({"id":i,"method":method,"params":params or {}}))
    ws.settimeout(30)
    while True:
        m=json.loads(ws.recv())
        if m.get("id")==i: return m
cmd("Page.enable"); cmd("Network.enable"); cmd("Runtime.enable")
cmd("Page.navigate",{"url":f"https://{COMMUNITY}/c/traders-lab-chat"}); time.sleep(6)
def fetch(url):
    expr=f"(async()=>{{const r=await fetch({json.dumps(url)},{{credentials:'include',headers:{{'Accept':'application/json'}}}});const t=await r.text();return JSON.stringify({{status:r.status,body:t}});}})()"
    m=cmd("Runtime.evaluate",{"expression":expr,"awaitPromise":True,"returnByValue":True})
    val=m.get("result",{}).get("result",{}).get("value")
    return json.loads(json.loads(val)["body"])
out={}
# page 1 (latest)
p1=fetch(f"https://{COMMUNITY}/internal_api/chat_rooms/{UUID}/messages?previous_per_page=20&next_per_page=0")
out["p1_keys"]=list(p1.keys())
out["p1_total"]=p1.get("total_count"); out["p1_has_prev"]=p1.get("has_previous_page")
out["p1_first_id"]=p1.get("first_id"); out["p1_last_id"]=p1.get("last_id")
out["p1_rec0"]=p1["records"][0]
# try backwards with before=first_id
import urllib.parse
fid=p1["first_id"]
for variant in [
    f"previous_per_page=20&next_per_page=0&before={fid}",
    f"previous_per_page=20&next_per_page=0&previous_to={fid}",
    f"previous_per_page=20&next_per_page=0&max_id={fid}",
    f"previous_per_page=20&next_per_page=0&cursor={fid}",
]:
    try:
        d=fetch(f"https://{COMMUNITY}/internal_api/chat_rooms/{UUID}/messages?{variant}")
        ok = d.get("has_previous_page") is not None and d.get("records")
        moved = d.get("last_id")!=p1["last_id"] if d.get("last_id") else False
        out[f"variant_{variant[:20]}"]={"ok":bool(ok),"moved_back":bool(moved),"first_id":d.get("first_id"),"last_id":d.get("last_id"),"n":len(d.get('records',[])),"status":"ok"}
    except Exception as e:
        out[f"variant_{variant[:20]}"]=str(e)[:120]
# participant batch lookup
pid=p1["records"][0]["chat_room_participant_id"]
try:
    p=fetch(f"https://{COMMUNITY}/internal_api/chat_rooms/{UUID}/participants?ids[]={pid}")
    out["participants_batch"]=p
except Exception as e:
    out["participants_batch"]=str(e)[:200]
open(r"C:\Users\aharg\Desktop\Projects\tradingbot\_chat_discover_out.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2))
print("written; keys:", list(out.keys()))
ws.close(); requests.get(f"{CDP_URL}/json/close/{t['id']}",timeout=5)
