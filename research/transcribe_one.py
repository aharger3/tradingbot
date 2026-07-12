"""Transcribe a single WAV file - tiny model for speed."""
import sys, time
from faster_whisper import WhisperModel

inpath = sys.argv[1]
outpath = sys.argv[2]
filename = sys.argv[3]

model = WhisperModel("tiny", device="cpu", compute_type="int8")
t0 = time.time()
segments, info = model.transcribe(inpath, beam_size=1, language="en", vad_filter=True)
t1 = time.time()
lines = []
for seg in segments:
    lines.append(f"[{seg.start:.0f}s-{seg.end:.0f}s] {seg.text.strip()}")
with open(outpath, "w", encoding="utf-8") as f:
    f.write(f"# Transcription: {filename}\n# Duration: {info.duration:.0f}s\n# Model: tiny\n\n")
    f.write("\n".join(lines))
speed = info.duration / (t1 - t0) if (t1 - t0) > 0 else 0
print(f"OK:{len(lines)}segs,{speed:.1f}x,{info.duration:.0f}s")
