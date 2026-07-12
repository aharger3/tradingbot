"""Transcribe Circle course videos with faster_whisper (RTX 2060, CUDA).

Prereq: fresh videos.json URLs (Circle HLS tokens expire ~daily):
    python circle_video_scraper.py     # with debug Chrome logged in
Then (no browser needed):
    python circle_transcribe.py        # priority order, resume-safe
    python circle_transcribe.py trade-reviews boot-camp-recordings   # only these

Writes circle_data/transcripts_text/<space>_<slug>_transcript.txt
Audio temp files go to circle_audio/ and are deleted after transcription.
"""

import json, re, subprocess, sys
from pathlib import Path

# ctranslate2 needs cublas/cudnn DLLs from the pip nvidia-* wheels; it resolves
# them via PATH (os.add_dll_directory is NOT enough — tested 2026-07-05)
import os, glob, site
_dirs = [d for p in site.getsitepackages()
         for d in glob.glob(os.path.join(p, "nvidia", "*", "bin"))]
os.environ["PATH"] = os.pathsep.join(_dirs) + os.pathsep + os.environ["PATH"]

DATA_DIR = Path("circle_data")
OUT_DIR = DATA_DIR / "transcripts_text"
AUDIO_DIR = Path("circle_audio")

# Austin's priority (2026-07-05): reviews + bootcamp + TA first, chatter last
PRIORITY = [
    "trade-reviews", "boot-camp-recordings", "technical-analysis",
    "building-your-profitable-system", "hayden-s-coaching", "psychology-coaching",
    "performance-coaching", "mastermind-1-0", "mastermind-2-0", "mastermind-3-0",
    "mastermind-4-0", "mastermind-5-0", "tony-s-q-a", "live-sessions",
    "the-accelerator-course", "bonus",
]


def log(msg):
    print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def lessons_todo(only):
    todo = []
    for space in (only or PRIORITY):
        f = DATA_DIR / space / "videos.json"
        if not f.exists():
            continue
        for v in json.loads(f.read_text(encoding="utf-8")):
            out = OUT_DIR / f"{space}_{slug(v['name'])}_transcript.txt"
            if not out.exists() and (v.get("download_url") or v.get("video_url")):
                todo.append((space, v, out))
    return todo


def fetch_audio(v, dest):
    """Try direct mp4 first, fall back to HLS. Audio-only keeps it small."""
    for url in filter(None, [v.get("download_url"), v.get("video_url")]):
        r = subprocess.run(
            ["yt-dlp", url, "-x", "--audio-format", "mp3", "--audio-quality", "9",
             "-o", str(dest.with_suffix(".%(ext)s")), "--no-part", "-q"],
            capture_output=True, text=True, timeout=1800)
        if dest.exists():
            return True
        log(f"    fetch failed ({url[:60]}...): {r.stderr.strip()[-120:]}")
    return False


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    todo = lessons_todo(only)
    log(f"{len(todo)} lessons to transcribe")
    if not todo:
        return
    OUT_DIR.mkdir(exist_ok=True)
    AUDIO_DIR.mkdir(exist_ok=True)

    from faster_whisper import WhisperModel
    try:
        model = WhisperModel("small", device="cuda", compute_type="int8_float16")
        log("whisper: small on CUDA")
    except Exception as e:
        log(f"CUDA unavailable ({e}); CPU int8 fallback (slower)")
        model = WhisperModel("small", device="cpu", compute_type="int8")

    for i, (space, v, out) in enumerate(todo, 1):
        log(f"[{i}/{len(todo)}] {space}: {v['name'][:60]} ({v.get('duration', '?')})")
        mp3 = AUDIO_DIR / f"{space}_{slug(v['name'])}.mp3"
        if not mp3.exists() and not fetch_audio(v, mp3):
            log("    SKIP: no audio (rerun circle_video_scraper.py for fresh URLs)")
            continue
        try:
            segments, _ = model.transcribe(str(mp3), language="en", vad_filter=True)
            text = "\n".join(f"[{s.start:.0f}s] {s.text.strip()}" for s in segments)
            out.write_text(f"# {v['name']} ({space})\n\n{text}", encoding="utf-8")
            log(f"    -> {out.name} ({len(text)//1000}k chars)")
            mp3.unlink(missing_ok=True)
        except Exception as e:
            log(f"    transcribe FAILED: {e}")

    log("Done.")


if __name__ == "__main__":
    main()
