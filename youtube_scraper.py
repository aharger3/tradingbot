"""YouTube scraper — transcripts + thumbnails for ALL known videos.

Usage: python youtube_scraper.py

Saves youtube_data/<video_id>_transcript.txt + _thumbnail.webp
"""
from pathlib import Path
import subprocess
from youtube_transcript_api import YouTubeTranscriptApi

DATA_DIR = Path("youtube_data")

# === JDUB TRADES (@jdubtrades) ===
JDUB = [
    "H8NxRPIx1V8", "qNEUuVG-T4Y", "b6HkDYfrnt4", "_McZebfqzds",
    "opHq3nz6Tdw", "PEaV7z8lc7k", "i72GVQXQwHo", "OByLdBe9qy4",
    "aOOUMis5SdU", "FIzcNCL7zfE", "SuLClS2FzAY", "2uOXP9oBIg8",
    "FAS9elq7ioE", "wwRJ-IPYVqk", "I9f1J6DYjdI",
]

# === SCARFACE TRADES (@ScarfaceTrades) ===
SCARFACE = [
    "ZaNh7OfkybY", "EIIiEtAEm3s", "Bl0CQnhSbgo", "dczXd1BFETs",
    "LErSLg9m0qs", "ICIYU_V0Zn0", "fxoO-3fNpq0", "bUt4lTdNSIU",
    "5KHVU0zOmks", "N2RnykeAvXc", "BXlvmQKIVvU", "ogy-Ep7s9zY",
    "dNXhFwy5tjY", "3PrTuaqRzng", "tstcEXqlsUM",
]

# === ORIGINAL 12 (from spec) ===
ORIGINAL = [
    "EIIiEtAEm3s", "8I6B2HSH-_0", "63p-lzRBTf0",
    "FEmD-hK1-yU", "JWRWP9ke2sY", "M-Pxkn5wjjA",
    "I9f1J6DYjdI", "6sxCfeoGn8g", "gM0dXZKM2X8",
    "IKv5ha6aA2k", "ZiU4HVCpo10", "leLDZzyTNPs",
]

# Combine, deduplicate
ALL_IDS = list(dict.fromkeys(JDUB + SCARFACE + ORIGINAL))


def get_transcripts():
    api = YouTubeTranscriptApi()
    print(f"\n=== Transcripts ({len(ALL_IDS)} videos) ===")
    for vid in ALL_IDS:
        fpath = DATA_DIR / f"{vid}_transcript.txt"
        if fpath.exists():
            continue
        try:
            tl = api.list(vid)
            t = None
            for x in tl:
                if x.language_code == "en":
                    t = x
                    break
            if not t:
                t = next(iter(tl))
            fetched = t.fetch()
            text = "\n".join(f"[{s.start:.0f}s] {s.text}" for s in fetched)
            DATA_DIR.mkdir(exist_ok=True)
            fpath.write_text(text)
        except Exception as e:
            print(f"  SKIP {vid}: {e}")


def get_thumbnails():
    print(f"\n=== Thumbnails ({len(ALL_IDS)} videos) ===")
    DATA_DIR.mkdir(exist_ok=True)
    for vid in ALL_IDS:
        existing = list(DATA_DIR.glob(f"{vid}_thumbnail.*"))
        if existing:
            continue
        try:
            subprocess.run(
                ["yt-dlp", f"https://youtube.com/watch?v={vid}",
                 "--write-thumbnail", "--skip-download",
                 "-o", f"{DATA_DIR}/{vid}_thumbnail.%(ext)s"],
                capture_output=True, text=True, timeout=30
            )
        except Exception as e:
            print(f"  SKIP {vid} thumb: {e}")


if __name__ == "__main__":
    get_transcripts()
    get_thumbnails()
    count = len(list(DATA_DIR.glob("*_transcript.txt")))
    print(f"\nDone. {count} transcripts in {DATA_DIR}/")
