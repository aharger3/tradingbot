"""Discord scraper v2 — full-history archive via Discord's own API, using the
token from YOUR logged-in Chrome session (personal archive of servers you're in).

v1 scrolled the DOM (500-msg cap, months at best). v2 paginates the REST API:
years of history, clean attachment URLs, incremental resume.

USAGE:
  1. Start Chrome with remote debugging and log into Discord web:
     Start-Process chrome "https://discord.com/channels/@me --remote-debugging-port=9222 --user-data-dir=C:/Users/aharg/circle-profile"

  2. Discover channels (prints every channel in the server, grouped by category):
     python discord_scraper.py --discover

  3. Scrape (full history first run, only-new afterwards):
     python discord_scraper.py                # all channels in CHANNEL_IDS
     python discord_scraper.py youtube        # just named channel(s)

Saves discord_data/<channel>.json (id-keyed messages) + images/<channel>/.
State in discord_data/_state.json -> reruns resume instead of refetching.
"""

import json, re, sys, time
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

DATA_DIR = Path("discord_data")
CDP = "http://localhost:9222"
API = "https://discord.com/api/v9"

SERVER_ID = "1218766394997346395"  # The Accelerator (Scarface Trades)

# name -> channel_id. Austin 2026-07-05: all coaching/education channels except
# zoom links, plus #youtube (every upload posted there = free video index).
# Run --discover to find IDs for channels not listed yet.
CHANNEL_IDS = {
    "premarket-charts": "1222970013602807909",
    "trading-floor": "1219022414239764520",
    "swing-ideas": "1282826052405559417",
    "trade-feedback": "1219021113686888478",
    "backtesting": "1272975902631788726",
    "scarface-trade-reviews": "1219022089252503632",
    "jdub-trade-reviews": "1222648559682457650",
    "futures-trade-reviews": "1339692914573312000",
    "options-trade-reviews": "1340175319000154143",
    # coaching education (Austin: everything except zoom-links)
    "weekly-live-education": "1222375088318447637",
    "pre-market-live": "1239709794642825266",
    "live-sessions": "1222650780738129950",
    "a-plus-setups": "1222374921561182262",
    "weekly-outlook": "1222375186964156527",
    "scarface-tips": "1222375001332645899",
    # youtube: every upload posted here -> feeds youtube_scraper
    "youtube": "1218991923218350160",
    # education vault
    "module-1": "1222378248290435072",
    "module-2": "1222378248802144347",
    "module-3": "1222378249200472095",
    "module-4": "1222378249867231292",
    "module-5": "1222378250475540500",
    "module-6": "1222378266942373989",
    "module-7": "1222378267542159421",
    "module-8": "1222378268230025257",
    "module-9": "1222378268703985665",
    "module-10": "1222378269576400949",
    "books": "1219022145296797737",
    # coach alert history (real trade calls = backtest ground truth)
    "scarface-alerts": "1222377337975210064",
    "jdub-alerts": "1222377361895460934",
    "futures-alerts": "1339691315851427922",
}

REQUEST_SLEEP = 0.6  # seconds between API calls; gentle on rate limits
MIN_IMG_BYTES = 5000


def log(msg):
    print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)


def sniff_token() -> str:
    """Grab the Authorization header from the logged-in Discord tab's own requests."""
    token = {}
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.on("request", lambda req: token.update(t=req.headers["authorization"])
                if req.headers.get("authorization") else None)
        page.goto("https://discord.com/channels/@me", wait_until="domcontentloaded",
                  timeout=30000)
        for _ in range(60):
            if token.get("t"):
                break
            page.wait_for_timeout(500)
        page.close()
        browser.close()
    if not token.get("t"):
        raise RuntimeError("No Discord token seen — is Discord web logged in in the debug Chrome?")
    return token["t"]


def api_get(session, path, params=None):
    while True:
        r = session.get(f"{API}{path}", params=params, timeout=20)
        if r.status_code == 429:
            wait = r.json().get("retry_after", 5)
            log(f"    rate limited, sleeping {wait}s")
            time.sleep(float(wait) + 1)
            continue
        if r.status_code != 200:
            log(f"    HTTP {r.status_code} on {path}")
            return None
        return r.json()


def discover(session):
    chans = api_get(session, f"/guilds/{SERVER_ID}/channels")
    if chans is None:
        log("Could not list channels (missing permission?) — falling back to known list only.")
        return
    cats = {c["id"]: c["name"] for c in chans if c["type"] == 4}
    by_cat = {}
    for c in sorted(chans, key=lambda c: (c.get("parent_id") or "", c.get("position", 0))):
        if c["type"] in (0, 5, 15):  # text / announcement / forum
            by_cat.setdefault(cats.get(c.get("parent_id"), "(no category)"), []).append(c)
    for cat, cs in by_cat.items():
        log(f"\n[{cat}]")
        for c in cs:
            mark = " <- configured" if c["id"] in CHANNEL_IDS.values() else ""
            log(f'    "{c["name"]}": "{c["id"]}",{mark}')


def msg_slim(m) -> dict:
    return {
        "id": m["id"],
        "ts": m["timestamp"][:19],
        "author": m["author"].get("global_name") or m["author"]["username"],
        "content": m.get("content", ""),
        "attachments": [a["url"] for a in m.get("attachments", [])],
        "embeds": [e.get("url") or e.get("image", {}).get("url", "")
                   for e in m.get("embeds", []) if e.get("url") or e.get("image")],
        "reply_to": (m.get("referenced_message") or {}).get("id"),
    }


def fetch_page(session, channel_id, **params):
    return api_get(session, f"/channels/{channel_id}/messages",
                   params={"limit": 100, **params})


def scrape_channel(session, name, channel_id, state):
    fpath = DATA_DIR / f"{name}.json"
    msgs = {}
    if fpath.exists():
        msgs = {m["id"]: m for m in json.loads(fpath.read_text(encoding="utf-8"))}
    st = state.setdefault(channel_id, {})
    added = 0

    def save():
        ordered = sorted(msgs.values(), key=lambda m: int(m["id"]))
        fpath.write_text(json.dumps(ordered, indent=1, ensure_ascii=False), encoding="utf-8")

    # 1. new messages since last run (or from present if first run)
    before = None
    while True:
        page = fetch_page(session, channel_id, **({"before": before} if before else {}))
        time.sleep(REQUEST_SLEEP)
        if page is None:
            break  # API error; state untouched, next run resumes
        if not page:
            st["backfill_done"] = True  # walked past the first message ever
            break
        for m in page:
            if m["id"] not in msgs:
                msgs[m["id"]] = msg_slim(m)
                added += 1
        before = page[-1]["id"]
        newest_known = st.get("newest")
        if newest_known and int(before) <= int(newest_known) and st.get("backfill_done"):
            break  # reached previously-archived region and history below is complete
        if len(page) < 100:
            st["backfill_done"] = True
            break
        if added and added % 1000 == 0:
            log(f"    ...{added} new so far (at {page[-1]['timestamp'][:10]})")
            save()

    if msgs:
        ids = sorted(msgs, key=int)
        st["oldest"], st["newest"] = ids[0], ids[-1]
    save()
    log(f"  {name}: +{added} new, {len(msgs)} total"
        + (f" (back to {msgs[min(msgs, key=int)]['ts'][:10]})" if msgs else ""))
    return msgs


def download_images(name, msgs):
    img_dir = DATA_DIR / "images" / name
    img_dir.mkdir(parents=True, exist_ok=True)
    have = {p.stem.rsplit("_", 1)[0] for p in img_dir.iterdir()}
    n = 0
    for m in msgs.values():
        if m["id"] in have:
            continue
        for i, url in enumerate(m["attachments"] + [u for u in m["embeds"] if u]):
            if not re.search(r"\.(png|jpe?g|webp|gif)(\?|$)", url, re.I):
                continue
            ext = re.search(r"\.(png|jpe?g|webp|gif)", url, re.I).group(1).lower()
            try:
                r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200 and len(r.content) >= MIN_IMG_BYTES:
                    (img_dir / f"{m['id']}_{i}.{ext}").write_bytes(r.content)
                    n += 1
                    time.sleep(0.2)
            except Exception:
                pass
    if n:
        log(f"  {name}: {n} images downloaded")


def main():
    token = sniff_token()
    log("Token acquired from browser session.")
    session = requests.Session()
    session.headers.update({"Authorization": token, "User-Agent": "Mozilla/5.0"})

    if "--discover" in sys.argv:
        discover(session)
        return

    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    targets = {n: c for n, c in CHANNEL_IDS.items() if not only or n in only}
    DATA_DIR.mkdir(exist_ok=True)
    state_path = DATA_DIR / "_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}

    for name, cid in targets.items():
        log(f"\nScraping #{name}...")
        try:
            msgs = scrape_channel(session, name, cid, state)
            download_images(name, msgs)
        except Exception as e:
            log(f"  FAILED: {e}")
        state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")

    log("\nDone.")


if __name__ == "__main__":
    main()
