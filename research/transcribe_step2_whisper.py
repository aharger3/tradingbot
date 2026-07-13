"""Step 2: Transcribe extracted WAV audio — one file at a time, checkpoint after each."""
import os, sys, time, json, traceback

# ctranslate2 needs cublas/cudnn DLLs from the pip nvidia-* wheels; it resolves
# them via PATH (same shim as circle_transcribe.py, tested 2026-07-05)
import glob, site
_dirs = [d for p in site.getsitepackages()
         for d in glob.glob(os.path.join(p, "nvidia", "*", "bin"))]
os.environ["PATH"] = os.pathsep.join(_dirs) + os.pathsep + os.environ["PATH"]

AUDIO_DIR = r"C:\Users\aharg\tradingbot\research\audio_extracted"
OUT_DIR = r"C:\Users\aharg\tradingbot\research\video_transcripts"
os.makedirs(OUT_DIR, exist_ok=True)
DONE_LOG = os.path.join(OUT_DIR, "_done.json")

done = {}
if os.path.exists(DONE_LOG):
    with open(DONE_LOG) as f:
        done = json.load(f)

files = sorted(os.listdir(AUDIO_DIR))
priority_names = [f for f in files if f.startswith("boot-camp-recordings")]
rest_names = [f for f in files if f not in priority_names and f.endswith('.wav')]
ordered = priority_names + rest_names
ordered = [f for f in ordered if f.endswith('.wav')]
ordered = [f for f in ordered if f not in done]

print(f"Remaining: {len(ordered)} files", flush=True)

for idx, filename in enumerate(ordered):
    inpath = os.path.join(AUDIO_DIR, filename)
    outname = filename.rsplit(".", 1)[0] + "_transcript.txt"
    outpath = os.path.join(OUT_DIR, outname)

    print(f"[{idx+1}/{len(ordered)}] {filename}", flush=True)
    try:
        from faster_whisper import WhisperModel
        # GPU first (2026-07-12: CPU medium ran ~1x realtime = 30h backlog);
        # RTX 2060 int8_float16 is 5-10x faster. CPU fallback keeps it running
        # if VRAM is tight or CUDA breaks.
        try:
            model = WhisperModel("medium", device="cuda", compute_type="int8_float16")
        except Exception as ge:
            print(f"  CUDA unavailable ({ge}); CPU int8 fallback", flush=True)
            model = WhisperModel("medium", device="cpu", compute_type="int8")

        t0 = time.time()
        segments, info = model.transcribe(inpath, beam_size=5, language="en")
        t1 = time.time()
        print(f"  Audio: {info.duration:.0f}s ({info.duration/(t1-t0):.1f}x)", flush=True)

        lines = []
        for seg in segments:
            lines.append(f"[{seg.start:.0f}s-{seg.end:.0f}s] {seg.text.strip()}")

        with open(outpath, "w", encoding="utf-8") as f:
            f.write(f"# Transcription: {filename}\n# Duration: {info.duration:.0f}s\n\n")
            f.write("\n".join(lines))

        done[filename] = {"status": "done", "segments": len(lines), "duration": info.duration}
        with open(DONE_LOG, "w") as f:
            json.dump(done, f)

        # Free model before next file
        del model
        print(f"  DONE ({len(lines)} segs)", flush=True)
    except Exception as e:
        print(f"  ERROR: {e}", flush=True)
        traceback.print_exc()
        done[filename] = {"status": "error", "error": str(e)}
        with open(DONE_LOG, "w") as f:
            json.dump(done, f)

print(f"DONE. {sum(1 for v in done.values() if v.get('status')=='done')}/{len(done)} ok", flush=True)
