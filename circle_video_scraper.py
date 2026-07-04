"""Circle video scraper — extracts lesson metadata + video URLs from all courses.

USAGE:
  1. Chrome debug window open, logged into Circle.
  2. python circle_video_scraper.py

Saves circle_data/<slug>/videos.json with lesson metadata + video URLs.
Also downloads thumbnails to images/.
"""

import json, re, time, html
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

DATA_DIR = Path("circle_data")
CDP = "http://localhost:9222"
BASE = "https://traders-lab.circle.so"
API = f"{BASE}/internal_api"

SPACES = [
    "psychology-coaching", "boot-camp-recordings", "the-accelerator-course",
    "trade-reviews", "live-sessions", "mastermind-1-0", "mastermind-2-0",
    "mastermind-3-0", "mastermind-4-0", "mastermind-5-0",
    "tony-s-q-a", "performance-coaching", "hayden-s-coaching",
    "technical-analysis", "building-your-profitable-system", "bonus",
]


def log(msg):
    safe = msg.encode('ascii', errors='replace').decode('ascii')
    print(safe, flush=True)


def extract_space_id(page, slug):
    """Get space/course ID from the page's CSS class."""
    page.goto(f"{BASE}/c/{slug}", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(4000)
    html = page.content()
    m = re.search(r'view-space--(\d+)', html)
    return m.group(1) if m else None


def api_get(path, headers, cookies):
    r = requests.get(f"{API}{path}", headers=headers, cookies=cookies, timeout=15)
    if r.status_code != 200:
        return None
    return r.json()


def scrape_space(page, slug):
    log(f"\n== {slug} ==")

    space_id = extract_space_id(page, slug)
    if not space_id:
        log(f"  SKIP: no space_id found")
        return

    log(f"  space_id={space_id}")

    cookies = {c['name']: c['value'] for c in page.context.cookies()}
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json',
        'X-CSRF-Token': cookies.get('CSRF-Token', ''),
        'Referer': f'{BASE}/',
    }

    space_dir = DATA_DIR / slug
    space_dir.mkdir(parents=True, exist_ok=True)
    img_dir = space_dir / "images"
    img_dir.mkdir(exist_ok=True)

    # Fetch sections
    sections = api_get(f"/courses/{space_id}/sections", headers, cookies)
    if not sections:
        log(f"  SKIP: no sections API response")
        return

    records = sections.get('records', [])
    log(f"  sections={len(records)}")

    lessons_data = []

    for section in records:
        sid = section['id']
        section_name = section.get('name', '')

        # Fetch lessons in section
        lesson_list = api_get(f"/courses/{space_id}/sections/{sid}/lessons?per_page=100", headers, cookies)
        if not lesson_list:
            continue

        for lesson in lesson_list.get('records', []):
            lid = lesson['id']

            # Fetch lesson detail
            detail = api_get(f"/courses/{space_id}/sections/{sid}/lessons/{lid}", headers, cookies)
            if not detail:
                continue

            media = detail.get('featured_media', {}) or {}
            body_raw = detail.get('body', '') or ''

            # Extract YouTube IDs from embedded iframes/links in lesson body
            body_youtube_ids = list(dict.fromkeys(
                re.findall(r'(?:youtube\.com/embed/|youtu\.be/|youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})', body_raw)
            ))

            # YouTube playlist embed (live sessions, trade reviews use this)
            embed = detail.get('featured_media_embed', {}) or {}
            embed_content = embed.get('content', '') or ''
            playlist_id = ''
            pl_match = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', embed_content)
            if pl_match:
                playlist_id = pl_match.group(1)
            elif 'youtube.com/playlist' in embed_content:
                pl_match2 = re.search(r'/([a-zA-Z0-9_-]+)(?:\?|$)', embed_content.split('?')[0])
                if pl_match2:
                    playlist_id = pl_match2.group(1)

            entry = {
                'name': detail.get('name', ''),
                'section': section_name,
                'duration': media.get('duration', ''),
                'video_url': media.get('playback_url', ''),
                'download_url': media.get('url', ''),
                'filename': media.get('filename', ''),
                'thumbnail': media.get('thumbnail_image_url', ''),
                'completed': detail.get('completed', False),
                'transcript_id': media.get('media_transcript_id'),
                'transcript_ready': False,
                'youtube_ids': body_youtube_ids,
                'has_embed': len(body_youtube_ids) > 0,
                'playlist_id': playlist_id,
                'has_playlist': bool(playlist_id),
                'playlist_title': embed.get('title', ''),
            }

            # Check transcript
            if entry['transcript_id']:
                try:
                    tr = api_get(f"/media_transcripts/{entry['transcript_id']}", headers, cookies)
                    if tr:
                        entry['transcript_ready'] = tr.get('is_ai_ready', False) or tr.get('is_user_ready', False)
                except:
                    pass

            # Download thumbnail
            if entry['thumbnail']:
                try:
                    resp = requests.get(entry['thumbnail'], timeout=10,
                                        headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200 and len(resp.content) > 2000:
                        (img_dir / f"thumb_{lid}.jpg").write_bytes(resp.content)
                except:
                    pass

            lessons_data.append(entry)
            ready = " [T]" if entry.get('transcript_ready') else ""
            log(f"    {entry['name']} ({entry['duration']}){ready}")

    (space_dir / "videos.json").write_text(
        json.dumps(lessons_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    log(f"  -> {len(lessons_data)} lessons saved")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.new_page()

        for slug in SPACES:
            try:
                scrape_space(page, slug)
            except Exception as e:
                log(f"  CRASHED: {e}")
                page.close()
                page = ctx.new_page()

        page.close()
        browser.close()
        log(f"\nDone. Data in {DATA_DIR}/<slug>/videos.json")


if __name__ == "__main__":
    main()
