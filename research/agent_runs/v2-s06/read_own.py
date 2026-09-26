# v2-s06: read-only look at Austin's own Discord signal channel(s). Prints no secrets.
import os, json, requests, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
env = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\.env")
for l in env.read_text(encoding="utf-8", errors="ignore").splitlines():
    if l.strip() and not l.startswith("#") and "=" in l:
        k, v = l.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
tok = os.getenv("DISCORD_BOT_TOKEN"); chan = os.getenv("DISCORD_CHANNEL_ID")
print("have_token", bool(tok), "have_chan", bool(chan), "have_webhook", bool(os.getenv("DISCORD_WEBHOOK_URL")))
if not (tok and chan): sys.exit()
H = {"Authorization": f"Bot {tok}", "User-Agent": "DiscordBot (omen, 1.0)"}
B = "https://discord.com/api/v10"
c = requests.get(f"{B}/channels/{chan}", headers=H, timeout=10).json()
print("channel:", c.get("name"), "guild_tail", str(c.get("guild_id"))[-4:])
g = c.get("guild_id")
chs = requests.get(f"{B}/guilds/{g}/channels", headers=H, timeout=10)
out = {"channels": [], "pins": {}, "msgs": {}}
if chs.ok:
    for x in chs.json():
        if x.get("type") == 0: out["channels"].append((x["id"], x["name"]))
print("text channels:", [n for _, n in out["channels"]])
for cid, name in out["channels"]:
    p = requests.get(f"{B}/channels/{cid}/pins", headers=H, timeout=10)
    if p.ok and p.json(): out["pins"][name] = p.json()
    m = requests.get(f"{B}/channels/{cid}/messages?limit=100", headers=H, timeout=10)
    if m.ok: out["msgs"][name] = m.json()
    else: print(name, "msgs HTTP", m.status_code)
    # oldest messages too
    o = requests.get(f"{B}/channels/{cid}/messages?after=0&limit=100", headers=H, timeout=10)
    if o.ok: out["msgs"][name + "__oldest"] = o.json()
Path(__file__).with_name("own_server_msgs.json").write_text(json.dumps(out, default=str), encoding="utf-8")
for k, v in out["msgs"].items(): print(k, len(v))
print("pins:", {k: len(v) for k, v in out["pins"].items()})
