"""G7.1 mediarepoint fix, item 4: INVENTORY ONLY. Counts what is on disk right now for the
1,077 recoverable YouTube videos and the 47,551 stored chart images. Makes no network call,
scrapes nothing, writes nothing.
"""
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent


def video_gap():
    ytd = ROOT / "youtube_data"
    have_transcript = {p.name.replace("_transcript.txt", "") for p in ytd.glob("*_transcript.txt")}
    have_thumb = {p.name.rsplit("_thumbnail", 1)[0] for p in ytd.glob("*_thumbnail.*")}
    no_transcript_has_thumb = have_thumb - have_transcript

    # dead/private/members-only: byte-identical placeholder thumbnails among the
    # no-transcript group (same heuristic as research/g71_media_yt_gap.py)
    md5_groups = Counter()
    import hashlib
    for vid in no_transcript_has_thumb:
        matches = list(ytd.glob(f"{vid}_thumbnail.*"))
        if not matches:
            continue
        h = hashlib.md5(matches[0].read_bytes()).hexdigest()
        md5_groups[h] += 1
    dead_count = sum(n for n in md5_groups.values() if n >= 50)  # large repeated placeholder groups

    print(f"youtube_data transcripts on disk        : {len(have_transcript)}")
    print(f"youtube_data thumbnails on disk          : {len(have_thumb)}")
    print(f"reached, transcript refused (has thumb)  : {len(no_transcript_has_thumb)}")
    print(f"  of those, in a >=50-file identical-md5 group (dead/private) : ~{dead_count}")
    print(f"recoverable ceiling (repo's own number)  : ~1077 (research/g71_media.md)")
    print(f"avg transcript size on disk               : "
          f"{sum(p.stat().st_size for p in ytd.glob('*_transcript.txt'))/max(1,len(have_transcript)):.0f} bytes")


def image_inventory():
    disc = list((ROOT / "discord_data" / "images").glob("*/*"))
    circ_img_dirs = list((ROOT / "circle_data").glob("*/images"))
    circ = [f for d in circ_img_dirs for f in d.glob("*")]
    print()
    print(f"discord_data/images files                : {len(disc)}")
    print(f"circle_data/*/images files                : {len(circ)}")
    print(f"total stored chart-ish images              : {len(disc)+len(circ)}")

    pilot = ROOT / "research" / "vision_pilot_manifest.jsonl"
    n_pilot = sum(1 for _ in open(pilot, encoding="utf-8")) if pilot.exists() else 0
    print(f"images ever shown to a model (vision pilot): {n_pilot}")

    # unit-cost benchmark: the only vision-model $/item numbers on disk are the video-ladder
    # runs (full video, not a single still image) -- report them as the nearest comparable,
    # not as a measured image cost.
    costs = []
    for fn in ("video_ladder_results_flash.jsonl", "video_ladder_results_qwen.jsonl", "video_ladder_results_batch.jsonl"):
        p = ROOT / "research" / fn
        if not p.exists():
            continue
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            c = d.get("cost_usd")
            if c is not None:
                costs.append(c)
    if costs:
        print(f"nearest cost benchmark on disk: {len(costs)} video-ladder rows, "
              f"avg ${sum(costs)/len(costs):.4f}/video (full video, not a single still image)")


if __name__ == "__main__":
    video_gap()
    image_inventory()
