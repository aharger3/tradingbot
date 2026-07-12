"""Batch transcribe all WAV files with checkpoint resume."""
import os, subprocess, json

AUDIO_DIR = r"C:\Users\aharg\tradingbot\research\audio_extracted"
OUT_DIR = r"C:\Users\aharg\tradingbot\research\video_transcripts"
SCRIPT = r"C:\Users\aharg\tradingbot\research\transcribe_one.py"
PYTHON = r"C:\Users\aharg\AppData\Local\Programs\Python\Python313\python.exe"
os.makedirs(OUT_DIR, exist_ok=True)

CHECKPOINT = os.path.join(OUT_DIR, "_checkpoint.json")

done = set()
if os.path.exists(CHECKPOINT):
    with open(CHECKPOINT) as f:
        done = set(json.load(f))

files = sorted(os.listdir(AUDIO_DIR))
files = [f for f in files if f.endswith('.wav')]
# Priority: boot-camp first
priority = [f for f in files if f.startswith("boot-camp-recordings")]
rest = [f for f in files if f not in priority]
ordered = priority + rest

todo = []
for f in ordered:
    outname = f.rsplit(".", 1)[0] + "_transcript.txt"
    outpath = os.path.join(OUT_DIR, outname)
    if os.path.exists(outpath) and os.path.getsize(outpath) > 100:
        continue
    todo.append(f)

print(f"Total: {len(files)}, Todo: {len(todo)}, Done: {len(done)}", flush=True)

for i, fname in enumerate(todo):
    inpath = os.path.join(AUDIO_DIR, fname)
    outname = fname.rsplit(".", 1)[0] + "_transcript.txt"
    outpath = os.path.join(OUT_DIR, outname)
    size_mb = os.path.getsize(inpath) / (1024*1024)

    print(f"[{i+1}/{len(todo)}] {fname} ({size_mb:.0f}MB)", flush=True)

    # Transcribe each file individually
    result = subprocess.run(
        [PYTHON, "-u", SCRIPT, inpath, outpath, fname],
        capture_output=True, text=True, timeout=600
    )

    if result.returncode == 0:
        ok_size = os.path.getsize(outpath)
        print(f"  OK: {ok_size:,} bytes", flush=True)
        done.add(fname)
        with open(CHECKPOINT, "w") as f:
            json.dump(list(done), f)
    else:
        err = result.stderr[:200] if result.stderr else result.stdout[:200]
        print(f"  FAIL: {err}", flush=True)

print(f"ALL DONE: {len(done)} complete", flush=True)
