"""Batch transcribe untranscribed audio from bottom up.
Skips boot-camp recordings (other session owns those).
Runs 2 parallel transcribe_one.py processes."""
import subprocess, os, sys, time, glob

AUDIO_DIR = r'C:\Users\aharg\tradingbot\research\audio_extracted'
TRANS_DIR = r'C:\Users\aharg\tradingbot\research\video_transcripts'
SCRIPT = r'C:\Users\aharg\tradingbot\research\transcribe_one.py'
PY = r'C:\Users\aharg\AppData\Local\Programs\Python\Python313\python.exe'

SKIP_PREFIXES = ['boot-camp-recordings']  # other session owns these
MAX_PARALLEL = 2

# Find untranscribed, sorted reverse alphabetical
wavs = sorted(glob.glob(os.path.join(AUDIO_DIR, '*.wav')), reverse=True)
queue = []
for w in wavs:
    base = os.path.basename(w).replace('.wav','')
    skip = any(base.lower().startswith(p.lower()) for p in SKIP_PREFIXES)
    if skip:
        continue
    out = os.path.join(TRANS_DIR, f'{base}_transcript.txt')
    if os.path.exists(out):
        continue
    queue.append((w, out, base))

total = len(queue)
print(f'Queue: {total} files (bottom-up, skipping boot-camp)', flush=True)

running = []
done = 0
idx = 0

while idx < len(queue) or running:
    # Launch new if room
    while len(running) < MAX_PARALLEL and idx < len(queue):
        w, out, base = queue[idx]
        idx += 1
        p = subprocess.Popen(
            [PY, '-u', SCRIPT, w, out, base + '.wav'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        running.append(p)
        print(f'LAUNCH [{idx}/{total}]: {base}', flush=True)

    # Check for done
    still_running = []
    for p in running:
        rc = p.poll()
        if rc is not None:
            done += 1
            out_line = p.stdout.read().decode(errors='replace').strip() if p.stdout else ''
            print(f'DONE [{done}/{total}]: rc={rc} {out_line[:100]}', flush=True)
        else:
            still_running.append(p)
    running = still_running

    if running:
        time.sleep(5)

print(f'All {total} done', flush=True)
