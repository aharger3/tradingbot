#!/bin/bash
# Transcribe all WAV files with checkpoint, one at a time
AUDIO_DIR="/c/Users/aharg/tradingbot/research/audio_extracted"
OUT_DIR="/c/Users/aharg/tradingbot/research/video_transcripts"
PYTHON="/c/Users/aharg/AppData/Local/Programs/Python/Python313/python.exe"
SCRIPT="/c/Users/aharg/tradingbot/research/transcribe_one.py"

mkdir -p "$OUT_DIR"

# Checkpoint file
CHECKPOINT="$OUT_DIR/_done_files.txt"

# Get all WAV files, boot-camp first
FILES=$(ls "$AUDIO_DIR"/*.wav | sort)
# Reorder: boot-camp first
BOOT_FILES=$(echo "$FILES" | grep "boot-camp-recordings")
REST_FILES=$(echo "$FILES" | grep -v "boot-camp-recordings")
ALL_FILES="$BOOT_FILES $REST_FILES"

TOTAL=$(echo "$ALL_FILES" | wc -w)
echo "Total files: $TOTAL"

COUNT=0
for INPATH in $ALL_FILES; do
    BASENAME=$(basename "$INPATH" .wav)
    OUTNAME="${BASENAME}_transcript.txt"
    OUTPATH="$OUT_DIR/$OUTNAME"

    # Skip if already done
    if [ -f "$OUTPATH" ] && [ $(stat -c%s "$OUTPATH") -gt 100 ]; then
        COUNT=$((COUNT + 1))
        echo "[$COUNT/$TOTAL] SKIP $BASENAME"
        continue
    fi

    SIZE_MB=$(du -m "$INPATH" | cut -f1)
    echo "[$((COUNT+1))/$TOTAL] $BASENAME.wav (${SIZE_MB}MB)"

    if "$PYTHON" -u "$SCRIPT" "$INPATH" "$OUTPATH" "$BASENAME.wav" 2>&1; then
        F_SIZE=$(stat -c%s "$OUTPATH" 2>/dev/null || echo 0)
        echo "  OK: ${F_SIZE} bytes"
        echo "$BASENAME" >> "$CHECKPOINT"
    else
        echo "  FAIL"
    fi

    COUNT=$((COUNT + 1))
done

echo "ALL DONE - $COUNT files processed"
