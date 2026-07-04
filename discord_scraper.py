"""Discord scraper — reads messages from your logged-in browser session.
No bot needed. Piggybacks your existing Chrome where you're logged into Discord.

USAGE:
  1. Chrome with remote debugging (the same window you use for Circle):
     Make sure you're logged into Discord web in that Chrome window.
     Navigate to the Discord server/channel you want to scrape.

  2. Run python discord_scraper.py --discover to find server/channel IDs.

  3. Edit SERVER_ID and CHANNEL_IDS in this file.

  4. Run python discord_scraper.py to scrape.

Saves discord_data/<channel-name>.json + images/
"""

import json, re, sys, time
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

DATA_DIR = Path("discord_data")
CDP = "http://localhost:9222"
DISCORD_BASE = "https://discord.com"

# === CONFIGURE THESE ===
SERVER_ID = 1218766394997346395  # The Accelerator (Scarface Trades)
CHANNEL_IDS = {                  # name -> channel_id
    "premarket-charts": 1222970013602807909,
    "trading-floor": 1219022414239764520,
    "swing-ideas": 1282826052405559417,
    "trade-feedback": 1219021113686888478,
    "backtesting": 1272975902631788726,
    "scarface-trade-reviews": 1219022089252503632,
    "jdub-trade-reviews": 1222648559682457650,
    "futures-trade-reviews": 1339692914573312000,
    "options-trade-reviews": 1340175319000154143,
}
MESSAGE_LIMIT = 500       # Per channel


def log(msg):
    safe = msg.encode('ascii', errors='replace').decode('ascii')
    print(safe, flush=True)


def get_guilds_channels(page):
    """Navigate to Discord and discover servers + channels."""
    page.goto(f"{DISCORD_BASE}/channels/@me", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(5000)

    # Wait for Discord to fully load
    page.wait_for_selector('[class*=sidebar]', timeout=15000)

    # Get all guilds (servers) in the sidebar
    guilds = page.evaluate('''
    () => {
        let items = [];
        // Discord servers are usually in a list with aria-labels
        document.querySelectorAll('[class*=guild] a, [class*=guilds] a, [data-list-item-id*=guilds] a, nav a[href*="/channels/"]').forEach(el => {
            let href = el.getAttribute('href') || '';
            let parts = href.split('/').filter(Boolean);
            if (parts.length >= 2 && parts[0] === 'channels') {
                let name = el.getAttribute('aria-label') || el.getAttribute('data-list-item-id') || parts[1];
                items.push({name: name, id: parts[1], href: href});
            }
        });
        return items;
    }
    ''')

    log(f"Found {len(guilds)} guilds/servers")
    for g in guilds[:20]:
        log(f"  [{g['id']}] {g['name']}")

    return guilds


def get_channels(page, guild_id):
    """Get text channels for a specific server."""
    url = f"{DISCORD_BASE}/channels/{guild_id}"
    page.goto(url, wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(5000)

    channels = page.evaluate(f'''
    () => {{
        let items = [];
        document.querySelectorAll('[class*=channel] a, a[href*="/channels/{guild_id}/"]').forEach(el => {{
            let href = el.getAttribute('href') || '';
            let parts = href.split('/').filter(Boolean);
            let name = el.innerText?.trim() || el.getAttribute('aria-label') || parts[2];
            if (parts.length >= 3 && parts[1] === '{guild_id}') {{
                let isVoice = href.includes('/voice') || (el.querySelector('[class*=voice]'));
                if (!isVoice) items.push({{name: name, id: parts[2]}});
            }}
        }});
        return items;
    }}
    ''')

    log(f"  {len(channels)} text channels found")
    for c in channels[:10]:
        log(f"    [{c['id']}] #{c['name']}")
    return channels


def scrape_channel(page, guild_id, channel_id, channel_name, limit=100):
    """Scroll and scrape messages from a channel."""
    url = f"{DISCORD_BASE}/channels/{guild_id}/{channel_id}"
    page.goto(url, wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(5000)

    # Wait for messages to load
    try:
        page.wait_for_selector('[class*=message]', timeout=10000)
    except:
        log(f"    No messages loaded for #{channel_name}")
        return []

    # Scroll up to load older messages
    for i in range(10):
        page.evaluate("document.querySelector('[class*=scroller]')?.scrollTo(0, 0)")
        page.wait_for_timeout(1500)
        count = page.evaluate("document.querySelectorAll('[class*=message]').length")
        if count >= limit:
            break

    # Extract messages
    messages = page.evaluate('''
    () => {
        let items = [];
        document.querySelectorAll('[class*=message]').forEach(msg => {
            let author = msg.querySelector('[class*=author]')?.innerText?.trim() || '';
            let content = msg.querySelector('[class*=messageContent]')?.innerText?.trim() || '';
            let time = msg.querySelector('time')?.getAttribute('datetime') || '';
            let imgUrls = [];
            msg.querySelectorAll('img[src]').forEach(img => {
                let src = img.getAttribute('src') || '';
                if (src.startsWith('http') && !src.includes('emoji') && !src.includes('avatar')) {
                    imgUrls.push(src);
                }
            });
            if (author && content) {
                items.push({author, content, timestamp: time, images: imgUrls});
            }
        });
        return items;
    }
    ''')

    return messages


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.new_page()

        if "--discover" in sys.argv:
            get_guilds_channels(page)
            page.close()
            browser.close()
            return

        if not SERVER_ID or not CHANNEL_IDS:
            log("ERROR: Set SERVER_ID and CHANNEL_IDS first.")
            log("Run: python discord_scraper.py --discover")
            page.close()
            browser.close()
            return

        DATA_DIR.mkdir(exist_ok=True)

        for name, channel_id in CHANNEL_IDS.items():
            log(f"\nScraping #{name} ({channel_id})...")
            messages = scrape_channel(page, SERVER_ID, channel_id, name, MESSAGE_LIMIT)

            if messages:
                fpath = DATA_DIR / f"{name}.json"
                fpath.write_text(json.dumps(messages, indent=2, ensure_ascii=False), encoding="utf-8")
                log(f"  -> {len(messages)} messages to {fpath}")

                # Download attached images
                img_count = 0
                for msg in messages:
                    for img_url in msg.get('images', []):
                        try:
                            resp = requests.get(img_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                            if resp.status_code == 200 and len(resp.content) > 5000:
                                safe_name = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
                                fname = f"{safe_name}_img{img_count+1}.png"
                                (DATA_DIR / fname).write_bytes(resp.content)
                                img_count += 1
                        except:
                            pass
                if img_count:
                    log(f"  -> {img_count} images downloaded")

        page.close()
        browser.close()
        log(f"\nDone. Data in {DATA_DIR}/")


if __name__ == "__main__":
    main()
