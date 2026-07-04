"""Extract YouTube playlist video IDs from Circle live sessions + trade reviews.
Gets ALL video IDs from each playlist, then downloads transcripts.

Usage:
  1. Chrome debug window open, logged into Circle.
  2. python circle_playlist_extractor.py

Saves youtube_data/playlist_videos.json + transcripts for all embedded videos.
"""
import json, re, subprocess, sys
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

CDP = "http://localhost:9222"
BASE = "https://traders-lab.circle.so"
API = f"{BASE}/internal_api"
DATA_DIR = Path("circle_data")
YT_DIR = Path("youtube_data")
YT_DIR.mkdir(exist_ok=True)

# Only these spaces have YouTube playlist embeds
SPACES = ["live-sessions", "trade-reviews"]


def log(msg):
    safe = msg.encode('ascii', errors='replace').decode('ascii')
    print(safe, flush=True)


def get_playlist_videos(playlist_id):
    """Get all video IDs from a YouTube playlist via yt-dlp."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--dump-json",
             f"https://www.youtube.com/playlist?list={playlist_id}"],
            capture_output=True, text=True, timeout=60
        )
        videos = []
        for line in result.stdout.strip().split("\n"):
            if line:
                try:
                    v = json.loads(line)
                    if v.get("id"):
                        videos.append({"id": v["id"], "title": v.get("title", "")})
                except:
                    pass
        return videos
    except Exception as e:
        log(f"    yt-dlp error: {e}")
        return []


def get_transcript(video_id):
    """Get YouTube transcript for a video."""
    from youtube_transcript_api import YouTubeTranscriptApi
    try:
        api = YouTubeTranscriptApi()
        tl = api.list(video_id)
        t = next((x for x in tl if x.language_code == "en"), next(iter(tl)))
        fetched = t.fetch()
        text = "\n".join(f"[{s.start:.0f}s] {s.text}" for s in fetched)
        return text
    except Exception as e:
        return None


def main():
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = ctx.new_page()

        all_playlists = {}
        total_videos = 0

        for slug in SPACES:
            log(f"\n== {slug} ==")
            page.goto(f"{BASE}/c/{slug}", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(4000)

            html = page.content()
            m = re.search(r'view-space--(\d+)', html)
            if not m:
                log(f"  SKIP: no space_id")
                continue
            space_id = m.group(1)

            cookies = {c['name']: c['value'] for c in page.context.cookies()}
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
                'X-CSRF-Token': cookies.get('CSRF-Token', ''),
                'Referer': f'{BASE}/',
            }

            r = requests.get(f"{API}/courses/{space_id}/sections", headers=headers, cookies=cookies, timeout=15)
            if r.status_code != 200:
                log(f"  SKIP: API error {r.status_code}")
                continue

            sections = r.json().get('records', [])

            for sec in sections:
                sid = sec['id']
                r2 = requests.get(f"{API}/courses/{space_id}/sections/{sid}/lessons?per_page=100",
                                  headers=headers, cookies=cookies, timeout=15)
                if r2.status_code != 200:
                    continue

                for lesson in r2.json().get('records', []):
                    lid = lesson['id']
                    r3 = requests.get(f"{API}/courses/{space_id}/sections/{sid}/lessons/{lid}",
                                      headers=headers, cookies=cookies, timeout=15)
                    if r3.status_code != 200:
                        continue
                    detail = r3.json()
                    embed = detail.get('featured_media_embed', {}) or {}
                    content = embed.get('content', '') or ''

                    pl_match = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', content)
                    if not pl_match:
                        continue
                    pl_id = pl_match.group(1)
                    lesson_name = detail.get('name', '')

                    if pl_id in all_playlists:
                        continue

                    log(f"  Playlist: {lesson_name} ({pl_id})")
                    videos = get_playlist_videos(pl_id)
                    all_playlists[pl_id] = {
                        "lesson_name": lesson_name,
                        "space": slug,
                        "playlist_id": pl_id,
                        "videos": videos,
                    }
                    total_videos += len(videos)
                    log(f"    -> {len(videos)} videos")

        page.close()
        b.close()

        # Save playlist data
        output = {
            "playlists": list(all_playlists.values()),
            "total_videos": total_videos,
            "unique_video_ids": list(dict.fromkeys(
                v["id"] for pl in all_playlists.values() for v in pl["videos"]
            )),
        }

        playlist_file = DATA_DIR / "playlist_videos.json"
        playlist_file.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"\nSaved {total_videos} videos across {len(all_playlists)} playlists")
        log(f"Unique video IDs: {len(output['unique_video_ids'])}")

        # Download transcripts
        log(f"\n=== Downloading transcripts ===")
        success = 0
        for pl in all_playlists.values():
            for v in pl["videos"]:
                vid = v["id"]
                fpath = YT_DIR / f"{vid}_transcript.txt"
                if fpath.exists():
                    success += 1
                    continue
                text = get_transcript(vid)
                if text:
                    fpath.write_text(text)
                    success += 1
                    log(f"  {vid} - {v['title'][:50]}")
                else:
                    log(f"  SKIP {vid} - no transcript")

        log(f"\nDone. {success}/{total_videos} transcripts in {YT_DIR}/")
        log(f"Playlist data: {playlist_file}")


if __name__ == "__main__":
    main()
