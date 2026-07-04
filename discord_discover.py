"""Discover Discord servers + channels by dumping DOM structure."""
import json, re, time
from playwright.sync_api import sync_playwright

CDP = "http://localhost:9222"
BASE = "https://discord.com"

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0]
    page = ctx.new_page()

    page.goto(f"{BASE}/channels/@me", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(8000)

    # Try multiple approaches to find servers

    # Method 1: Grab all <li> elements that might be server entries
    print("=== ALL <li> with aria-labels ===")
    items = page.evaluate("""
    () => {
        let results = [];
        document.querySelectorAll('li[aria-label]').forEach(el => {
            let label = el.getAttribute('aria-label') || '';
            let href = el.querySelector('a')?.getAttribute('href') || '';
            results.push({label: label, href: href, tag: el.tagName, class: (el.className || '').substring(0,60)});
        });
        return results;
    }
    """)
    for item in items[:30]:
        print(f'  aria-label="{item["label"]}" href={item["href"]} class={item["class"]}')

    # Method 2: Find anything that navigates to a server channel
    print("\n=== ALL <a> with channels/ in href ===")
    links = page.evaluate("""
    () => {
        let results = [];
        document.querySelectorAll('a[href*=\"/channels/\"]').forEach(el => {
            let href = el.getAttribute('href') || '';
            let text = el.innerText?.trim() || el.getAttribute('aria-label') || '';
            let parentRole = el.closest('[role]')?.getAttribute('role') || '';
            results.push({href: href.substring(0,80), text: text.substring(0,40), role: parentRole});
        });
        return results;
    }
    """)
    for link in links[:30]:
        print(f'  href={link["href"]} text="{link["text"]}" role={link["role"]}')

    # Method 3: Dump all roles and see what structure exists
    print("\n=== Elements with role='treeitem' or 'listitem' ===")
    roles = page.evaluate("""
    () => {
        let results = [];
        document.querySelectorAll('[role=\"treeitem\"], [role=\"listitem\"], [role=\"group\"]').forEach(el => {
            let role = el.getAttribute('role') || '';
            let label = el.getAttribute('aria-label') || '';
            let hrefs = [...el.querySelectorAll('a[href]')].map(a => a.getAttribute('href'));
            results.push({role: role, label: label, hrefs: hrefs.filter(Boolean)});
        });
        return results;
    }
    """)
    for r in roles[:20]:
        print(f'  role={r["role"]} label="{r["label"]}" hrefs={r["hrefs"][:3]}')

    # Method 4: Check nav elements
    print("\n=== Nav structure ===")
    navs = page.evaluate("""
    () => {
        let results = [];
        document.querySelectorAll('nav').forEach((el, i) => {
            let label = el.getAttribute('aria-label') || '';
            let links = [...el.querySelectorAll('a[href]')].length;
            results.push({index: i, label: label, linkCount: links});
        });
        return results;
    }
    """)
    for n in navs:
        print(f'  nav[{n["index"]}]: aria-label="{n["label"]}" links={n["linkCount"]}')

    page.close()
    b.close()
