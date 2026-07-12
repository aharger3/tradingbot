"""Transcribe all WAV files using subprocess per file (clean memory)."""
import os, subprocess

AUDIO_DIR = r"C:\Users\aharg\tradingbot\research\audio_extracted"
OUT_DIR = r"C:\Users\aharg\tradingbot\research\video_transcripts"
SCRIPT = r"C:\Users\aharg\tradingbot\research\transcribe_one.py"
PYTHON = r"C:\Users\aharg\AppData\Local\Programs\Python\Python313\python.exe"
os.makedirs(OUT_DIR, exist_ok=True)

files = sorted(os.listdir(AUDIO_DIR))
files = [f for f in files if f.endswith('.wav')]

# Priority: boot-camp-recordings first
priority = [f for f in files if f.startswith("boot-camp-recordings")]
rest = [f for f in files if f not in priority]
ordered = priority + rest

todo = []
for f in ordered:
    outname = f.rsplit(".", 1)[0] + "_transcript.txt"
    outpath = os.path.join(OUT_DIR, outname)
    if not (os.path.exists(outpath) and os.path.getsize(outpath) > 100):
        todo.append(f)

print(f"Total: {len(files)}, Need: {len(todo)}", flush=True)

for i, fname in enumerate(todo):
    inpath = os.path.join(AUDIO_DIR, fname)
    outname = fname.rsplit(".", 1)[0] + "_transcript.txt"
    outpath = os.path.join(OUT_DIR, outname)

    size_mb = os.path.getsize(inpath) / (1024*1024)
    print(f"[{i+1}/{len(todo)}] {fname} ({size_mb:.0f}MB)", flush=True)

    result = subprocess.run(
        [PYTHON, "-u", SCRIPT, inpath, outpath, fname],
        capture_output=True, text=True, timeout=3600
    )

    output = (result.stdout or "") + (" " + result.stderr[:200] if result.stderr else "")
    status = "OK" if result.returncode == 0 else "FAIL"
    print(f"  {status}: {output.strip()[:150]}", flush=True)

print("ALL DONE", flush=True)
