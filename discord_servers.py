"""Dump ALL Accelerator Discord channels with full names."""
from playwright.sync_api import sync_playwright

CDP = "http://localhost:9222"
SERVER_ID = "1218766394997346395"

def log(msg):
    safe = msg.encode('ascii', errors='replace').decode('ascii')
    print(safe, flush=True)

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0]
    page = ctx.new_page()

    page.goto(f"https://discord.com/channels/{SERVER_ID}", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(8000)

    # Get all channel names + IDs with category context
    channels = page.evaluate(f"""
    () => {{
        let results = [];
        let currentCategory = '';

        document.querySelectorAll('[class*=sidebar] *').forEach(el => {{
            let tag = el.tagName.toLowerCase();

            // Detect category headers
            if (el.getAttribute('role') === 'button' && el.querySelector('[class*=name]')) {{
                let catName = el.querySelector('[class*=name]')?.innerText?.trim() || '';
                if (catName) currentCategory = catName;
            }}

            // Channel links
            if (tag === 'a' && el.getAttribute('href')) {{
                let href = el.getAttribute('href') || '';
                let parts = href.split('/').filter(Boolean);
                if (parts.length >= 3) {{
                    let nameEl = el.querySelector('[class*=name]');
                    let name = '';
                    if (nameEl) {{
                        name = nameEl.innerText?.trim() || '';
                    }}
                    if (!name) name = el.innerText?.trim()?.split('\\n')[0] || '';
                    if (name && parts[0] === 'channels' && parts[1] === '{SERVER_ID}') {{
                        results.push({{
                            category: currentCategory,
                            name: name,
                            id: parts[2],
                            full_text: el.innerText?.trim()?.substring(0, 80) || ''
                        }});
                    }}
                }}
            }}
        }});

        return results;
    }}
    """)

    log(f"\n=== Accelerator Discord Channels ===")
    seen = set()
    for c in channels:
        key = c['id']
        if key not in seen:
            seen.add(key)
            log(f"  [{c['id']}] ({c['category']}) #{c['name']}")

    page.close()
    b.close()
