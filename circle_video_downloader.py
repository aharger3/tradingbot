"""Batch download Circle HLS videos + extract YouTube embeds.

1. Re-scrapes all spaces (catches YouTube embeds from lesson body)
2. Downloads all 195+ HLS videos via yt-dlp
3. Downloads YouTube transcripts for embedded videos

Steps:
  python circle_video_downloader.py --rescan    # re-scrape + find YouTube embeds
  python circle_video_downloader.py --videos    # download all HLS videos
  python circle_video_downloader.py --yt-transcripts  # get YouTube transcripts

Or just:
  python circle_video_downloader.py --all
"""
import json, subprocess, sys, re
from pathlib import Path

DATA_DIR = Path("circle_data")
VIDEO_DIR = Path("circle_videos")


def log(msg):
    safe = msg.encode('ascii', errors='replace').decode('ascii')
    print(safe, flush=True)


def collect_videos():
    """Collect all lessons with video_url from all spaces."""
    items = []
    for f in sorted(DATA_DIR.glob("*/videos.json")):
        slug = f.parent.name
        data = json.loads(f.read_text())
        for v in data:
            if v.get("video_url"):
                items.append((slug, v))
    return items


def collect_yt_ids():
    """Collect all YouTube IDs from all spaces."""
    ids = []
    for f in sorted(DATA_DIR.glob("*/videos.json")):
        data = json.loads(f.read_text())
        for v in data:
            for yid in v.get("youtube_ids", []):
                ids.append(yid)
    return list(dict.fromkeys(ids))


def download_videos():
    VIDEO_DIR.mkdir(exist_ok=True)
    items = collect_videos()
    log(f"\n=== Downloading {len(items)} HLS videos ===")

    for slug, v in items:
        url = v["video_url"]
        name = re.sub(r'[^a-zA-Z0-9]+', '_', v["name"]).strip("_")[:60]
        safe = f"{slug}_{name}"
        out_path = VIDEO_DIR / f"{safe}.mp4"

        if out_path.exists():
            continue

        dur = v.get('duration', '?')
        log(f"  [{v['name']} ({dur})]")
        try:
            subprocess.run([
                "yt-dlp", url,
                "-o", str(out_path),
                "--downloader", "ffmpeg",
                "--hls-use-mpegts",
                "--continue",
                "--progress",
                "--newline",
            ], check=True, timeout=7200)
        except subprocess.CalledProcessError as e:
            log(f"    FAIL: {e}")
        except Exception as e:
            log(f"    ERROR: {e}")


def download_yt_transcripts():
    from youtube_transcript_api import YouTubeTranscriptApi

    yt_ids = collect_yt_ids()
    log(f"\n=== YouTube transcripts for {len(yt_ids)} embedded videos ===")

    api = YouTubeTranscriptApi()
    yt_dir = DATA_DIR / "youtube_transcripts"
    yt_dir.mkdir(exist_ok=True)

    for vid in yt_ids:
        fpath = yt_dir / f"{vid}.txt"
        if fpath.exists():
            continue
        try:
            tl = api.list(vid)
            t = next((x for x in tl if x.language_code == "en"), next(iter(tl)))
            fetched = t.fetch()
            text = "\n".join(f"[{s.start:.0f}s] {s.text}" for s in fetched)
            fpath.write_text(text)
            log(f"  {vid} -> {len(fetched)} lines")
        except Exception as e:
            log(f"  SKIP {vid}: {e}")


if __name__ == "__main__":
    if "--all" in sys.argv:
        download_videos()
        download_yt_transcripts()
    elif "--videos" in sys.argv:
        download_videos()
    elif "--yt-transcripts" in sys.argv:
        download_yt_transcripts()
    else:
        log("Usage:")
        log("  python circle_video_downloader.py --videos            # download HLS videos")
        log("  python circle_video_downloader.py --yt-transcripts    # get YouTube transcripts")
        log("  python circle_video_downloader.py --all               # both")
