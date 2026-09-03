"""Raw CDP token capture via websocket-client (playwright is broken on Chrome 151).

Launches nothing itself — assumes Chrome is already running on :9222 with
--remote-allow-origins=*. Grabs the Authorization header from Discord's own
API requests and prints the bare token (no Bearer prefix), or NO_TOKEN.
"""
import json, time, urllib.request, sys
import websocket

CDP = "http://localhost:9222"

def main():
    ver = json.loads(urllib.request.urlopen(f"{CDP}/json/version", timeout=5).read())
    ws_url = ver["webSocketDebuggerUrl"]
    ws = websocket.create_connection(ws_url, timeout=30)
    mid = 1

    ws.send(json.dumps({"id": mid, "method": "Network.enable", "params": {}})); mid += 1
    ws.send(json.dumps({"id": mid, "method": "Page.enable", "params": {}})); mid += 1
    ws.send(json.dumps({"id": mid, "method": "Page.navigate",
                        "params": {"url": "https://discord.com/channels/@me"}})); mid += 1

    ws.timeout = 30
    token = None
    deadline = time.time() + 25
    while time.time() < deadline:
        try:
            raw = ws.recv()
        except Exception:
            break
        evt = json.loads(raw)
        if evt.get("method") == "Network.requestWillBeSent":
            hdrs = evt["params"]["request"].get("headers", {})
            auth = hdrs.get("Authorization") or hdrs.get("authorization")
            if auth and "bearer" in auth.lower():
                token = auth.split(" ", 1)[-1] if " " in auth else auth
                break
    ws.close()
    if token:
        print(token)
    else:
        print("NO_TOKEN")

if __name__ == "__main__":
    main()
