"""Circle scraper — full depth, all spaces. Text + screenshots.

USAGE:
  1. Start Chrome with remote debugging:
     Start-Process chrome "https://circle.so --remote-debugging-port=9222 --user-data-dir=C:/Users/aharg/circle-profile"
     Log into Circle.

  2. Run:
     cd C:/Users/aharg/tradingbot && python circle_scraper.py

Saves circle_data/<slug>/posts.json + images/
"""

import json, time
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

DATA_DIR = Path("circle_data")
BASE = "https://traders-lab.circle.so/c"

# All known spaces. Commented = video/group pages (different layout, handle later)
SPACES = [
    ("start-here",         "Start Here",          f"{BASE}/start-here-e13c08"),
    ("announcements",      "Announcements",       f"{BASE}/announcements"),
    ("key-levels",         "Key Levels",          f"{BASE}/key-levels-6080d3"),
    ("resources",          "Resources",           f"{BASE}/resources"),
    ("important-info",     "Important Info",      f"{BASE}/start-here-a51448"),
    ("traders-lab-chat",   "Traders Lab Chat",    f"{BASE}/traders-lab-chat"),
    ("a-setups",           "A+ Setups",           f"{BASE}/a-setups"),
    ("student-wins",       "Student Wins",        f"{BASE}/student-wins"),
]


def log(msg):
    safe = msg.encode('ascii', errors='replace').decode('ascii')
    print(safe, flush=True)


def find_scroll_container(page):
    """Find the div that actually scrolls (not <body>)."""
    return page.evaluate("""
    () => {
        let best = null;
        document.querySelectorAll('*').forEach(el => {
            let s = window.getComputedStyle(el);
            if ((s.overflowY === 'scroll' || s.overflowY === 'auto') &&
                el.scrollHeight > el.clientHeight + 100 &&
                el.querySelector('.post')) {
                if (!best || el.scrollHeight > best.scrollHeight) best = el;
            }
        });
        if (!best) return null;
        return {scrollH: best.scrollHeight, clientH: best.clientHeight};
    }
    """)


def scroll_to_load_all(page, container_sel):
    """Scroll container and click 'More' until no new content loads."""
    last_count = 0
    stagnant = 0
    max_iter = 100  # safety cap

    for i in range(max_iter):
        # 1. Scroll container to bottom
        page.evaluate(f"""
        () => {{
            let el = document.querySelector('{container_sel}');
            if (!el) {{ window.scrollTo(0, document.body.scrollHeight); return; }}
            el.scrollTop = el.scrollHeight;
        }}
        """)
        page.wait_for_timeout(2000)

        # 2. Click "More" if present
        more_btn = page.query_selector("button:has-text('More'), button:has-text('Load more')")
        if more_btn:
            more_btn.scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            more_btn.click(force=True, timeout=5000)
            page.wait_for_timeout(2000)

        # 3. Count current posts
        post_count = page.evaluate("document.querySelectorAll('.post').length")

        if post_count > last_count:
            last_count = post_count
            stagnant = 0
            log(f"    ... {post_count} posts loaded")
        else:
            stagnant += 1
            if stagnant >= 3:
                log(f"    -> stopped at {post_count} posts (no new content after 3 checks)")
                break

    return last_count


def detect_layout(page):
    # Check chat FIRST — some chat spaces have no .post elements
    body_p = page.query_selector_all("p")
    real_ps = [p for p in body_p if len(p.inner_text().strip()) > 20]
    if len(real_ps) > 10:
        return "chat"
    has_post = len(page.query_selector_all(".post")) > 0
    if has_post:
        return "posts"
    return "empty"


def scrape_posts(page, layout, space_dir, img_dir):
    """Extract all post text + images from whatever's loaded in DOM. Returns (count, img_count)."""
    posts_data = []
    seen = set()

    if layout == "posts":
        cards = page.query_selector_all(".post")
    else:
        cards = page.query_selector_all("p")

    for card in cards:
        text = card.inner_text().strip()
        if not text or text in seen:
            continue
        seen.add(text)

        entry = {"text": text, "images": []}
        for img in card.query_selector_all("img[src]"):
            src = img.get_attribute("src")
            if not src or not src.startswith("http"):
                continue
            cls = (img.get_attribute("class") or "").lower()
            if any(x in cls for x in ["emoji", "icon"]):
                continue
            try:
                resp = requests.get(src, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200 and len(resp.content) > 8000:
                    ext = src.rstrip("/").rsplit(".", 1)[-1].split("?")[0]
                    ext = ext if ext in ("webp","png","jpg","jpeg","gif") else "jpg"
                    fname = f"img_{len(entry['images'])+1}.{ext}"
                    (img_dir / fname).write_bytes(resp.content)
                    entry["images"].append(fname)
            except Exception:
                pass
        posts_data.append(entry)

    (space_dir / "posts.json").write_text(
        json.dumps(posts_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    return len(posts_data), sum(len(p["images"]) for p in posts_data)


def scrape_space(page, slug, name, url):
    log(f"\n== {name} ==")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(4000)
    except Exception as e:
        log(f"  NAV FAIL: {e}")
        return

    layout = detect_layout(page)
    if layout == "empty":
        log(f"  SKIP: no content (group/video page)")
        return

    space_dir = DATA_DIR / slug
    space_dir.mkdir(parents=True, exist_ok=True)
    img_dir = space_dir / "images"
    img_dir.mkdir(exist_ok=True)

    # Scroll to get ALL posts — save partial data even if scroll crashes
    try:
        container_info = find_scroll_container(page)
        if container_info:
            log(f"  scrollable container: {container_info['scrollH']}px loaded, {container_info['clientH']}px viewport")
            scroll_to_load_all(page, ".community__content")
        else:
            log(f"  no scroll container found, using window scroll")
            scroll_to_load_all(page, "body")
    except Exception as e:
        log(f"  SCROLL STOPPED: {e}")

    # Scrape whatever's in the DOM (even partial)
    total, imgs = scrape_posts(page, layout, space_dir, img_dir)
    log(f"  SCRAPED: {total} items, {imgs} images")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp("http://localhost:9222")
        ctx = browser.contexts[0]
        page = ctx.new_page()

        for slug, name, url in SPACES:
            try:
                scrape_space(page, slug, name, url)
            except Exception as e:
                log(f"  CRASHED: {e}")
                # Don't kill entire run — try next space
                page = ctx.new_page()
                continue

        page.close()
        browser.close()
        log(f"\nDone. Data in {DATA_DIR}/")


if __name__ == "__main__":
    main()
