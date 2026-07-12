"""Transcribe circle_videos and circle_audio using faster-whisper medium model."""
import os, sys, time, glob, json
from faster_whisper import WhisperModel

PY313 = r"C:\Users\aharg\AppData\Local\Programs\Python\Python313\python.exe"
BASE = r"C:\Users\aharg\tradingbot"
VIDEO_DIR = os.path.join(BASE, "circle_videos")
AUDIO_DIR = os.path.join(BASE, "circle_audio")
OUT_DIR = os.path.join(BASE, "research", "video_transcripts")
os.makedirs(OUT_DIR, exist_ok=True)

# Priority order from spec: boot-camp-recordings, then rest
PRIORITY_PREFIXES = ["boot-camp-recordings"]
SKIP_EXISTING = True

def get_all_files():
    files = []
    for d in [VIDEO_DIR, AUDIO_DIR]:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(('.mp4', '.webm', '.m4a', '.mp3', '.wav')):
                # Skip .ytdl metadata files
                if f.endswith('.ytdl'):
                    continue
                files.append((d, f))
    return files

def sort_key(item):
    """Sort: priority prefixes first, then alphabetical."""
    name = item[1]
    for i, prefix in enumerate(PRIORITY_PREFIXES):
        if name.lower().startswith(prefix.lower()):
            return (0, i, name)
    return (1, 0, name)

def main():
    # Use GPU if available, else CPU
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute = "float16" if device == "cuda" else "int8"
    except:
        device = "cpu"
        compute = "int8"

    print(f"Device: {device}, Compute: {compute}", flush=True)
    model = WhisperModel("medium", device=device, compute_type=compute)

    files = get_all_files()
    files.sort(key=sort_key)
    print(f"Total files to transcribe: {len(files)}", flush=True)

    for dirpath, filename in files:
        out_name = filename.rsplit(".", 1)[0] + "_transcript.txt"
        out_path = os.path.join(OUT_DIR, out_name)
        if SKIP_EXISTING and os.path.exists(out_path):
            print(f"SKIP (exists): {filename}", flush=True)
            continue

        in_path = os.path.join(dirpath, filename)
        size_mb = os.path.getsize(in_path) / (1024 * 1024)
        print(f"TRANSCRIBE: {filename} ({size_mb:.1f}MB)", flush=True)

        try:
            start = time.time()
            segments, info = model.transcribe(in_path, beam_size=5, language="en")
            elapsed = time.time() - start
            print(f"  Duration: {info.duration:.0f}s, Audio @ {info.duration/elapsed:.1f}x", flush=True)

            lines = []
            for seg in segments:
                ts = f"[{seg.start:.0f}s-{seg.end:.0f}s]"
                lines.append(f"{ts} {seg.text.strip()}")

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"# Transcription: {filename}\n")
                f.write(f"# Duration: {info.duration:.0f}s, Audio speed: {info.duration/elapsed:.1f}x\n\n")
                f.write("\n".join(lines))
            print(f"  DONE -> {out_path} ({len(lines)} segments)", flush=True)
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)

    print("ALL DONE", flush=True)

if __name__ == "__main__":
    main()
