"""Whisper-transcribe playlist videos that have no YouTube captions.

Source: circle_data/playlist_videos.json (from circle_playlist_extractor.py).
trade-reviews playlists first, then live-sessions. Resume-safe. Run AFTER
circle_transcribe.py finishes (both want the GPU).

    python yt_whisper.py                 # everything missing
    python yt_whisper.py trade-reviews   # one space only
"""

import json, re, subprocess, sys
from pathlib import Path

# ctranslate2 needs cublas/cudnn DLLs from the pip nvidia-* wheels; it resolves
# them via PATH (os.add_dll_directory is NOT enough — tested 2026-07-05)
import os, glob, site
_dirs = [d for p in site.getsitepackages()
         for d in glob.glob(os.path.join(p, "nvidia", "*", "bin"))]
os.environ["PATH"] = os.pathsep.join(_dirs) + os.pathsep + os.environ["PATH"]

YT_DIR = Path("youtube_data")
AUDIO_DIR = Path("circle_audio")
PLAYLISTS = Path("circle_data/playlist_videos.json")


def log(msg):
    print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)


def todo(only):
    items = []
    data = json.loads(PLAYLISTS.read_text(encoding="utf-8"))
    pls = sorted(data["playlists"], key=lambda p: p["space"] != "trade-reviews")
    for pl in pls:
        if only and pl["space"] not in only:
            continue
        for v in pl["videos"]:
            if not (YT_DIR / f"{v['id']}_transcript.txt").exists():
                items.append((pl["space"], v))
    return items


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    items = todo(only)
    log(f"{len(items)} playlist videos to whisper")
    if not items:
        return
    AUDIO_DIR.mkdir(exist_ok=True)

    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cuda", compute_type="int8_float16")
    log("whisper: small on CUDA")

    for i, (space, v) in enumerate(items, 1):
        vid, title = v["id"], v.get("title", "")
        log(f"[{i}/{len(items)}] {space}: {title[:60]} ({vid})")
        mp3 = AUDIO_DIR / f"yt_{vid}.mp3"
        if not mp3.exists():
            r = subprocess.run(
                ["yt-dlp", f"https://youtube.com/watch?v={vid}", "-x",
                 "--audio-format", "mp3", "--audio-quality", "9",
                 "-o", str(mp3.with_suffix(".%(ext)s")), "--no-part", "-q"],
                capture_output=True, text=True, timeout=3600)
            if not mp3.exists():
                log(f"    SKIP: audio fetch failed: {r.stderr.strip()[-120:]}")
                continue
        try:
            segments, _ = model.transcribe(str(mp3), language="en", vad_filter=True)
            text = "\n".join(f"[{s.start:.0f}s] {s.text.strip()}" for s in segments)
            (YT_DIR / f"{vid}_transcript.txt").write_text(
                f"# {title} ({space})\n\n{text}", encoding="utf-8")
            log(f"    -> {vid}_transcript.txt ({len(text)//1000}k chars)")
            mp3.unlink(missing_ok=True)
        except Exception as e:
            log(f"    transcribe FAILED: {e}")

    log("Done.")


if __name__ == "__main__":
    main()
