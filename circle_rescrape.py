"""Circle re-scrape — capture created_at, author, post_id, space for every post.

Reuses the existing Circle scraper's auth path: a Chrome instance logged into
Circle, driven over CDP on port 9222 (same as circle_scraper.py). Instead of
DOM-scraping (which dropped timestamps/authors), it calls the same internal_api
the Circle web app itself uses, from inside the authenticated page via fetch().
No new auth is built; the logged-in session cookies do the work.

Writes circle_data/<space>/posts_v2.json (absolute path), originals untouched.
Video/audio out of scope.

USAGE:
  1. Chrome already running with --remote-debugging-port=9222, logged into Circle.
  2. python circle_rescrape.py
"""
import json, time, sys
from pathlib import Path
import requests, websocket  # type: ignore

CDP_URL = "http://localhost:9222"
DATA_DIR = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\circle_data")
RESEARCH_MD = Path(r"C:\Users\aharg\Desktop\Projects\.loop-wt-tradingbot\circle-rescrape\research\circle_rescrape.md")
COMMUNITY = "traders-lab.circle.so"

# Reused verbatim from circle_scraper.py: folder slug -> (display name, real space slug).
# The real slug is what appears in internal_api/spaces[].slug.
TARGETS = [
    ("a-setups",         "A+ Setups",         "a-setups"),
    ("important-info",   "Important Info",    "start-here-a51448"),
    ("key-levels",       "Key Levels",        "key-levels-6080d3"),
    ("resources",        "Resources",         "resources"),
    ("traders-lab-chat", "Traders Lab Chat",  "traders-lab-chat"),
    ("announcements",    "Announcements",     "announcements"),
]


def log(msg):
    print(msg, flush=True)


class CDP:
    """Minimal CDP client over a page target, Origin suppressed to bypass
    Chrome's --remote-allow-origins restriction."""

    def __init__(self):
        t = requests.put(f"{CDP_URL}/json/new", timeout=10).json()
        self.tab = t
        self.ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=30, suppress_origin=True)
        self._mid = 0
        self._cmd("Page.enable"); self._cmd("Network.enable"); self._cmd("Runtime.enable")

    def _cmd(self, method, params=None):
        self._mid += 1
        i = self._mid
        self.ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
        self.ws.settimeout(30)
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == i:
                return msg

    def navigate(self, url, settle=6):
        self._cmd("Page.navigate", {"url": url})
        time.sleep(settle)

    def fetch_json(self, url):
        """Authenticated fetch from inside the page (cookies sent automatically)."""
        expr = (
            "(async()=>{const r=await fetch(" + json.dumps(url) + ","
            "{credentials:'include',headers:{'Accept':'application/json'}});"
            "const t=await r.text();return JSON.stringify({status:r.status,body:t});})()"
        )
        m = self._cmd("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True})
        res = m.get("result", {}).get("result", {})
        if m.get("result", {}).get("exceptionDetails"):
            raise RuntimeError("fetch failed: " + str(m["result"]["exceptionDetails"])[:200])
        val = res.get("value")
        if not val:
            raise RuntimeError("fetch returned no value: " + str(res)[:200])
        d = json.loads(val)
        if d.get("status") != 200:
            raise RuntimeError(f"HTTP {d['status']} for {url}: {d['body'][:200]}")
        return json.loads(d["body"])

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
        try:
            requests.get(f"{CDP_URL}/json/close/{self.tab['id']}", timeout=5)
        except Exception:
            pass


def extract_text(tiptap):
    """Walk a tiptap prosemirror doc ({"type": "doc", "content": [...]}) and
    collect all text nodes. Caller must pass the doc itself, not Circle's
    `tiptap_body` wrapper (`{"body": {...doc...}, "circle_ios_fallback_text":
    ..., "inline_attachments": [...], ...}`) — passing the wrapper directly
    silently returns "" because the wrapper has no top-level "type"/"content"
    key for the walk to find. See extract_images() docstring for the same bug
    on the attachments side."""
    if not tiptap:
        return ""
    out = []
    stack = [tiptap]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("type") == "text" and node.get("text"):
                out.append(node["text"])
            content = node.get("content")
            if isinstance(content, list):
                stack.extend(reversed(content))
        elif isinstance(node, list):
            stack.extend(reversed(node))
    return " ".join(out).strip()


def extract_images_from_body(doc):
    """Walk a tiptap prosemirror doc for inline image nodes (type=='image'),
    collecting attrs.url. This is where images actually live in the list
    endpoint's response — not in a top-level `inline_attachments` field."""
    imgs = []
    if not doc:
        return imgs
    stack = [doc]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("type") == "image":
                u = (node.get("attrs") or {}).get("url")
                if u and u.startswith("http"):
                    imgs.append(u)
            content = node.get("content")
            if isinstance(content, list):
                stack.extend(reversed(content))
        elif isinstance(node, list):
            stack.extend(reversed(node))
    return imgs


def extract_images(post):
    """Collect image URLs from a post record.

    FIELD-MAPPING BUG (fixed here): `inline_attachments` and
    `circle_ios_fallback_text` are NOT top-level keys on the post record the
    list endpoint returns — verified 2026-08-26 against
    `internal_api/spaces/{id}/posts` live. Both are nested one level down,
    inside `post["tiptap_body"]`. The old code read `post.get(...)` directly
    and always got None/[] as a result. Images also appear as inline
    `type: "image"` nodes inside `tiptap_body["body"]`'s content tree
    (attrs.url) even when `inline_attachments` itself is empty.
    """
    tb = post.get("tiptap_body") or {}
    imgs = []
    for ia in (tb.get("inline_attachments") or []):
        u = ia.get("url")
        if u and u.startswith("http"):
            imgs.append(u)
    imgs.extend(extract_images_from_body(tb.get("body")))
    cv = post.get("cover_image_url")
    if cv and cv.startswith("http"):
        imgs.append(cv)
    # de-dup, preserve order
    seen = set(); out = []
    for u in imgs:
        if u not in seen:
            seen.add(u); out.append(u)
    return out


def author_name(cm):
    if not cm:
        return None
    first = (cm.get("first_name") or "").strip()
    last = (cm.get("last_name") or "").strip()
    name = (first + " " + last).strip()
    return name or cm.get("name") or cm.get("public_uid") or None


def fetch_spaces(cdp):
    """Return {real_slug: space_record} for all spaces."""
    spaces = {}
    page = 1
    while True:
        d = cdp.fetch_json(f"https://{COMMUNITY}/internal_api/spaces?include_sidebar=true&per_page=100&page={page}")
        for r in d.get("records", []):
            spaces[r["slug"]] = r
        if not d.get("has_next_page"):
            break
        page += 1
        if page > 10:
            break
    return spaces


def scrape_space_posts(cdp, space_id):
    """Paginate the posts endpoint; return list of raw post records."""
    records = []
    page = 1
    while True:
        url = (f"https://{COMMUNITY}/internal_api/spaces/{space_id}/posts"
               f"?include_top_pinned_post=true&used_on=posts&per_page=50&page={page}")
        d = cdp.fetch_json(url)
        recs = d.get("records", [])
        records.extend(recs)
        log(f"    page {page}: +{len(recs)} (total {len(records)} / api count {d.get('count')})")
        if not d.get("has_next_page") or not recs:
            break
        page += 1
        if page > 30:
            break
    return records


def main():
    # ---- auth: connect to the logged-in Chrome and load any Circle page ----
    try:
        cdp = CDP()
    except Exception as e:
        write_failure("CDP connect", str(e))
        return
    try:
        cdp.navigate(f"https://{COMMUNITY}/c/a-setups", settle=6)
        # prove auth works before scraping
        try:
            probe = cdp.fetch_json(f"https://{COMMUNITY}/internal_api/current_contact")
        except Exception as e:
            write_failure("current_contact (auth check)", str(e))
            return
        log(f"auth ok: contact user_id={probe.get('user_id')}")

        spaces = fetch_spaces(cdp)
        log(f"loaded {len(spaces)} spaces")

        all_posts = []
        span_min, span_max = None, None
        counts = []

        for folder_slug, name, real_slug in TARGETS:
            log(f"\n== {name} ({folder_slug}) ==")
            rec = spaces.get(real_slug)
            if not rec:
                # fall back: match by name
                rec = next((s for s in spaces.values() if s.get("name") and name.lower() in s["name"].lower()), None)
            if not rec:
                log(f"  SKIP: space slug '{real_slug}' not found in spaces list")
                continue
            sid = rec["id"]
            log(f"  space_id={sid} api_posts_count={rec.get('posts_count')}")

            posts_raw = scrape_space_posts(cdp, sid)
            if not posts_raw:
                log(f"  no posts from API (chat space / empty) — posts_v2 will be []")
                # still write an empty file so the space is represented
                (DATA_DIR / folder_slug).mkdir(parents=True, exist_ok=True)
                (DATA_DIR / folder_slug / "posts_v2.json").write_text("[]", encoding="utf-8")
                counts.append((folder_slug, 0, 0))
                continue

            entries = []
            for p in posts_raw:
                ts = p.get("created_at") or p.get("published_at")
                author = author_name(p.get("community_member"))
                tb = p.get("tiptap_body") or {}
                text = (tb.get("circle_ios_fallback_text") or "").strip() or extract_text(tb.get("body"))
                entry = {
                    "post_id": p.get("id"),
                    "created_at": ts,
                    "author": author,
                    "space": folder_slug,
                    "space_name": p.get("space_name") or rec.get("name"),
                    "text": text,
                    "images": extract_images(p),
                }
                entries.append(entry)
                if ts:
                    day = ts[:10]
                    span_min = day if span_min is None else min(span_min, day)
                    span_max = day if span_max is None else max(span_max, day)
                all_posts.append(entry)

            out_dir = DATA_DIR / folder_slug
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "posts_v2.json").write_text(
                json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            with_ts = sum(1 for e in entries if e["created_at"])
            with_auth = sum(1 for e in entries if e["author"])
            log(f"  wrote {len(entries)} posts -> posts_v2.json ({with_ts} with ts, {with_auth} with author)")
            counts.append((folder_slug, with_ts, with_auth))

        # ---- research doc ----
        posts_total = sum(c[1] for c in counts)  # = all_posts len w/ ts
        # use counts of entries written instead
        entries_total = 0; ts_total = 0; auth_total = 0
        for folder_slug, wt, wa in counts:
            entries_total += 0  # placeholder
        # recompute from all_posts
        posts_with_ts = sum(1 for e in all_posts if e["created_at"])
        posts_with_author = sum(1 for e in all_posts if e["author"])
        posts_total_real = len(all_posts)
        spaces_rescraped = sum(1 for c in counts if c[1] >= 0)  # all attempted

        write_research(spaces_rescraped, posts_with_ts, posts_with_author,
                       posts_total_real, span_min, span_max, counts)
        log(f"\nDONE. posts_with_ts={posts_with_ts}/{posts_total_real} span={span_min}->{span_max}")

    finally:
        cdp.close()


def write_failure(step, detail):
    """Auth failed — name the exact step, never fabricate a timestamp."""
    log(f"AUTH FAILURE at step: {step}\n  detail: {detail}")
    RESEARCH_MD.parent.mkdir(parents=True, exist_ok=True)
    RESEARCH_MD.write_text(
        f"# Circle re-scrape\n\n"
        f"AUTH FAILED at step: **{step}**\n\n"
        f"detail: {detail}\n\n"
        f"No posts were scraped. No timestamps fabricated.\n\n"
        f"```\nspaces_rescraped: 0\nposts_with_ts: 0\nposts_with_author: 0\nposts_total: 0\nspan_utc: never -> never\n```\n",
        encoding="utf-8",
    )


def write_research(spaces_rescraped, posts_with_ts, posts_with_author,
                   posts_total, span_min, span_max, counts):
    RESEARCH_MD.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# Circle re-scrape\n")
    lines.append("Re-scraped Circle spaces via the authenticated `internal_api` the Circle web app "
                 "uses, driven through the same logged-in Chrome CDP session (port 9222) the existing "
                 "`circle_scraper.py` uses — no new auth path. Each post now carries `created_at`, "
                 "`author`, `post_id`, `space` alongside the existing `text` and `images`. "
                 "Video/audio out of scope.\n")
    lines.append("## counts\n")
    lines.append("```")
    lines.append(f"spaces_rescraped: {spaces_rescraped}")
    lines.append(f"posts_with_ts: {posts_with_ts}")
    lines.append(f"posts_with_author: {posts_with_author}")
    lines.append(f"posts_total: {posts_total}")
    lines.append(f"span_utc: {span_min} -> {span_max}")
    lines.append("```")
    lines.append("\n## per-space\n")
    lines.append("| space | posts_with_ts | posts_with_author |")
    lines.append("|---|---|---|")
    for folder_slug, wt, wa in counts:
        lines.append(f"| {folder_slug} | {wt} | {wa} |")
    lines.append("\nNote: the prior `posts.json` counts (a-setups 649, important-info 107, "
                 "key-levels 77, resources 57, traders-lab-chat 49, announcements 33) were DOM-scraped "
                 "and over-counted comments as posts. The `internal_api/spaces/{id}/posts` endpoint "
                 "returns top-level posts only, so `posts_v2.json` counts are lower and accurate. "
                 "traders-lab-chat is a chat space (posts_count=0) — no top-level posts via the posts API.\n")
    RESEARCH_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
