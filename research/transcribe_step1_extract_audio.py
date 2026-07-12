"""Step 1: Extract audio from all circle_videos and circle_audio using ffmpeg.
Outputs smaller audio files for faster transcription."""
import os, subprocess, sys

BASE = r"C:\Users\aharg\tradingbot"
VIDEO_DIR = os.path.join(BASE, "circle_videos")
AUDIO_DIR = os.path.join(BASE, "circle_audio")
AUDIO_EXTRACT_DIR = os.path.join(BASE, "research", "audio_extracted")
os.makedirs(AUDIO_EXTRACT_DIR, exist_ok=True)

FFMPEG = r"C:\Users\aharg\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"

def extract_audio(inpath, outpath):
    if os.path.exists(outpath):
        print(f"  SKIP (exists): {outpath}")
        return True
    cmd = [FFMPEG, "-y", "-i", inpath, "-vn", "-acodec", "pcm_s16le",
           "-ar", "16000", "-ac", "1", outpath]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[:200]}")
        return False
    return True

def main():
    files = []
    for d in [VIDEO_DIR, AUDIO_DIR]:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(('.mp4', '.webm', '.m4a', '.mp3', '.wav')) and not f.endswith('.ytdl'):
                files.append((d, f))

    print(f"Extracting audio from {len(files)} files...", flush=True)
    for dirpath, filename in files:
        inpath = os.path.join(dirpath, filename)
        outname = filename.rsplit(".", 1)[0] + ".wav"
        outpath = os.path.join(AUDIO_EXTRACT_DIR, outname)
        in_mb = os.path.getsize(inpath) / (1024*1024)
        print(f"[{filename}] ({in_mb:.0f}MB) -> {outname}", flush=True)
        if extract_audio(inpath, outpath):
            out_mb = os.path.getsize(outpath) / (1024*1024)
            print(f"  DONE ({out_mb:.0f}MB)", flush=True)

    print("ALL DONE - audio extraction complete", flush=True)

if __name__ == "__main__":
    main()
