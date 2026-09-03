# G7.1 / media — media pipeline inventory (diagnosis only, nothing scraped)

Run 2026-08-29. Every count below comes from files on disk, produced by
`research/g71_media_inventory.py`, `research/g71_media_yt_gap.py`,
`research/g71_media_image_gap.py`, `research/g71_media_mining_gap.py`.
No network call was made.

Austin's question: *"if videos and images are still stale and not all there, we need a
langraph team of agents."*

**Short answer: images are 99.2% complete and course videos are 100% transcribed. One
hole is real — 1,670 of 2,475 known YouTube videos have no transcript — and it is not a
fan-out problem. Four scrapers cannot start because `playwright` is not importable, and
the YouTube transcript API refused ~1,463 videos with no log kept of why.**

---

## 1. Video inventory: upstream → downloaded → transcribed → mined

| corpus | upstream | downloaded | transcribed | mined for rules |
|---|---:|---:|---:|---:|
| Circle course lessons (HLS) | 234 lesson rows in 16 `circle_data/*/videos.json`; **195** carry a playable URL | 80 `.mp4` (+1 `.part`, +1 `.ytdl` stub) | **195 / 195** (100%) | 88 of 193 slug transcripts |
| Circle YouTube playlists | 29 playlists, 555 rows, **547** unique ids | n/a (transcript-only path) | **546 / 547** (99.8%) | 20 of 220 (T6 video ladder) |
| Discord-posted YouTube | **2,357** unique ids (2,227 from coach channels) | 2,161 thumbnails | **687 / 2,357** (29%) | 67 ids cited in `scarface-rules-*.md` |
| **union of all YouTube ids** | **2,475** | — | **805 (32.5%)** | — |

Per-space lesson detail (`research/g71_media_inventory.py`):

```
space                              lessons has_url   txt   mp4
bonus                                    6       3     3     3
boot-camp-recordings                    20      15    15    15
building-your-profitable-system         12      12    12    12
hayden-s-coaching                        7       7     7     7
live-sessions                           17       0     0     0   <- playlist wrappers
mastermind-1-0..5-0                     31      30    30    30
performance-coaching                    61      61    61    13
psychology-coaching                      9       9     9     0
technical-analysis                       6       6     6     0
the-accelerator-course                  32      32    32     0
tony-s-q-a                              20      20    20     0
trade-reviews                           13       0     0     0   <- playlist wrappers
TOTAL                                  234     195   195    80
```

`live-sessions` (17) and `trade-reviews` (13) hold no `video_url` by design — they are
YouTube playlist wrappers; their content is the 547 ids above. The 115 lessons with a
transcript but no `.mp4` were transcribed audio-only and the audio deleted, as intended.

### The 1,670 untranscribed videos, split by what actually happened

| bucket | count | evidence |
|---|---:|---|
| thumbnail on disk, no transcript → **reached, transcript refused** | **1,463** | `youtube_data/<id>_thumbnail.*` exists, `<id>_transcript.txt` does not |
| of those, byte-identical placeholder thumbnails (3 md5 groups: 372 / 115 / 106) → dead, private, or members-only | **593** | 0 of the 372-file group has a transcript |
| no thumbnail and no transcript → **never attempted** | **207** | neither file exists |

Recoverable ceiling on a re-run is therefore roughly **1,077**, not 1,670.

By channel, untranscribed coach-posted ids: jdub-alerts 381, live-sessions 277,
options-trade-reviews 242, pre-market-live 188, scarface-trade-reviews 139,
weekly-outlook 97, scarface-alerts 73, jdub-trade-reviews 70, youtube 49,
futures-trade-reviews 33, weekly-live-education 7.

2026 alone: 596 coach-posted ids, **526 untranscribed**. Since 2026-08-01: 44 ids,
**44 untranscribed** (0%).

### Playlists never captured

`circle_data/playlist_videos.json` (written 2026-07-05 21:41) holds 29 playlists. Four
playlists linked in Discord are absent from it entirely:

```
2024-03-31 jdub-trade-reviews   PLwhGkGhTV3K1EpKg6EAkuQwXt7Hqx6f80
2024-03-31 weekly-outlook       PLwhGkGhTV3K3tXq4p34aA1oNyQTk0bvgW
2024-04-05 questions            PL8CPJw0RJBkdLbAQ4OZ9Q5NJAt1bo4MK4
2024-06-05 member-tips-tricks   PLdCDl3t21xnyiXQbeE6DL04N2SkrKf6OT
```

Its month labels run Jan–Dec for one completed year plus Jan–Jul for another, so the
whole run is a snapshot taken before 2026-08. It has not been refreshed since Jul 5.

### Rule mining

- `research/video_transcripts/` = 89 whisper transcripts, batched into 36 groups
  (`_extract_groups.json`), extracted via DeepSeek on **2026-07-13** into
  `research/scarface-rules-videos.md` (1.57 MB). 124 checkpoint files present for 36
  groups (re-runs), `_done_files.txt` lists 151 lines.
- **105 course transcripts have never been through that pass**: performance-coaching 45,
  the-accelerator-course 27, tony-s-q-a 18, psychology-coaching 9, technical-analysis 6.
- **753 of 820 YouTube transcripts are cited nowhere** in any `scarface-rules-*.md`.
- Both extraction scripts are **dead as written**: `_extract_video_rules.py:17-22` and
  `_compile_video_extraction.py:6-9` hardcode `C:\Users\aharg\tradingbot\research\...`,
  a path that does not exist (repo lives at `Desktop\Projects\tradingbot`). Their
  2026-07-13 output cannot be regenerated without editing those constants.

---

## 2. Image inventory

| store | files |
|---|---:|
| `discord_data/images/` (38 channel dirs) | **30,053** |
| `circle_data/*/images/` | **17,498** |
| `youtube_data/*_thumbnail.*` | 2,161 (2,320 file count incl. dupes by ext) |

### Discord coverage vs messages that carry an image URL

27,205 messages carry an image URL; **7,943 have no local file**. But:

```
channel                    msgs_w_img  missing   last_missing
post-your-gains                 10890     7809   2026-07-07
futures-alerts                   1711       43   2026-08-17
trading-floor                    3175       36   2026-02-27
options-trade-reviews              46       30   2026-02-03
questions                        1183       13   2026-02-10
trade-feedback                    944        4   2026-07-16
...all other channels            <=2 each
jdub-alerts                      2380        0   —
premarket-charts                  591        0   —
scarface-alerts                  5066        1   2026-03-24
```

**7,809 of the 7,943 are `post-your-gains`** — member P&L screenshots, not charts, and
that channel is not in `discord_scraper.py::CHANNEL_IDS` any more. Excluding it, the
chart channels are **134 missing out of 16,315 = 99.2% complete** through 2026-08-21.

**100.0% of stored attachment URLs carry a Discord `ex=` expiry token.** Any image not
downloaded at scrape time is unrecoverable from the stored JSON; only a fresh API fetch
of the message yields a live URL. Backfilling old images therefore means re-running the
scraper against Discord, not re-reading local files.

Circle image stores: a-setups 5,113 · student-wins 5,385 · key-levels 4,566 ·
resources 1,211 · traders-lab-chat 668 · important-info 227 · announcements 133 ·
course thumbnails ~195.

### Images mined

**200.** That is the entire history of a model looking at a chart image in this repo:
`research/vision_pilot_manifest.jsonl` (100 jdub-alerts / 60 scarface-alerts /
40 premarket-charts), run through 5 tiers on 2026-08-20/21 → `research/vision_ladder.md`.
0.7% of the discord image store; 0 of the 17,498 circle images.

`scarface_image_annotator.py` — the script `research/vision_ladder.md:30` and
`_vision_ladder_runner.py:16` both name as the production annotator — **does not exist**
anywhere in the repo or in the four `.loop-wt-tradingbot` worktrees.

---

## 3. Staleness: last successful run per stage

| stage | last success | how known |
|---|---|---|
| Discord messages | content through **2026-08-21**; files rewritten 2026-08-28 09:25 with **zero messages newer than Aug 21** | `_state.json` newest snowflakes all decode to ≤2026-08-21; `save()` runs unconditionally so the mtime does not prove a fetch |
| Discord images | **2026-08-21 13:40** | newest file in `discord_data/images/**` |
| Circle post re-scrape (`circle_rescrape.py`) | **2026-08-26 16:22–16:34** | `posts_v2.json` mtimes |
| Circle course `videos.json` | **2026-08-01 20:11–20:14** | mtimes |
| Circle HLS downloads | **2026-07-04 18:10** | newest `circle_videos/*.mp4` |
| Circle transcription | **2026-07-06 16:43** | newest `transcripts_text/*.txt` |
| Playlist extraction | **2026-07-05 21:41** | `playlist_videos.json` |
| YouTube transcripts / thumbnails | **2026-08-01 16:43 / 10:27** | mtime histogram: 176 transcripts + 178 thumbs written that day |
| Video rule extraction (DeepSeek) | **2026-07-13 03:47** | `scarface-rules-videos.md` |
| Vision ladder (T3) | **2026-08-21 14:46** | `vision_ladder.md` |
| Video ladder (T6) | **2026-08-24 09:25** | `video_ladder.md` |

`journal/scanner_status.json` is the live signal scanner, not media:
`timestamp 2026-08-28T10:59:11-04:00`, `signals_fired_today: 0`,
`last_error: "MARA: Too Many Requests. Rate limited."` — a Polygon rate limit, unrelated
to this track.

**Partial failure in the newest run**: `circle_rescrape.py` (2026-08-26) under-captured 3
of its 6 target spaces — `traders-lab-chat/posts_v2.json` is empty (0 posts vs 64 in the
v1 file), `announcements` 4 vs 33, `important-info` 26 vs 107. `a-setups` (215) and
`key-levels` (78) and `resources` (57) came back correct.

---

## 4. Root causes

### R1 — `playwright` is not importable; four scrapers cannot start (blocker)

```
$ python -c "import playwright"
ModuleNotFoundError: No module named 'playwright'
   (interpreter: C:\Users\aharg\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe)
```

Module-level imports that hard-fail: `discord_scraper.py:25`,
`circle_video_scraper.py:14`, `circle_playlist_extractor.py:13`, `circle_scraper.py:17`.

`_run_delta.py:3` records the second half of it: *"playwright CDP connect is broken on
Chrome 151, so sniff_token cannot run"*. The workarounds in the tree
(`_run_delta.py`, `_run_delta_noplaywright.py`, `_sniff_cdp.py`, `.disc_token_tmp` from
2026-08-21) are all hand-operated patches around this one import.

**The fix already exists in the repo**: `circle_rescrape.py:44-90` implements `class CDP`,
a raw CDP client over websocket with `suppress_origin=True`, which is exactly what
playwright's `connect_over_cdp` was doing and does not need playwright at all. It is
proven — it produced the 2026-08-26 Circle scrape.

### R2 — `circle_transcribe.py` reports "no audio" whenever yt-dlp does not emit mp3

`circle_transcribe.py:58-68` writes yt-dlp output to `dest.with_suffix(".%(ext)s")` and
then tests `dest.exists()` where `dest` is the `.mp3` path. When ffmpeg post-processing
does not produce mp3, yt-dlp leaves `.mp4` and the function returns False forever.
`circle_audio/` holds exactly **9 `.mp4` leftovers, 2.6 GB**, each one a lesson that logs
`SKIP: no audio` on every run. Moot right now (195/195 are transcribed) but it will bite
the next batch.

### R3 — `youtube_scraper.py` keeps no failure log

`youtube_scraper.py:77-78` — `except Exception as e: print(f"  SKIP {vid}: {e}")`. Nothing
is persisted, so there is no way to tell "transcripts disabled on this video" from
"IP rate-limited, retry later" for the 1,463 videos in that bucket. Every re-run repeats
the same work and discards the same answer.

### R4 — extraction scripts point at a repo path that no longer exists

`_extract_video_rules.py:17-22`, `_compile_video_extraction.py:6-9` →
`C:\Users\aharg\tradingbot\research\...`. Dead as written.

---

## 5. Proposed diffs (NOT applied — diagnosis pass)

### R2

```diff
--- a/circle_transcribe.py
+++ b/circle_transcribe.py
@@ -58,11 +58,16 @@ def fetch_audio(v, dest):
 def fetch_audio(v, dest):
     """Try direct mp4 first, fall back to HLS. Audio-only keeps it small."""
     for url in filter(None, [v.get("download_url"), v.get("video_url")]):
         r = subprocess.run(
             ["yt-dlp", url, "-x", "--audio-format", "mp3", "--audio-quality", "9",
              "-o", str(dest.with_suffix(".%(ext)s")), "--no-part", "-q"],
             capture_output=True, text=True, timeout=1800)
-        if dest.exists():
-            return True
+        if dest.exists():
+            return True
+        # yt-dlp fell back to the container's own audio (no ffmpeg mp3 step).
+        # Whisper reads m4a/mp4/webm fine; take whatever landed.
+        for alt in sorted(dest.parent.glob(dest.stem + ".*")):
+            if alt != dest:
+                alt.rename(dest.with_suffix(alt.suffix))
+                return True
         log(f"    fetch failed ({url[:60]}...): {r.stderr.strip()[-120:]}")
     return False
```

(and `model.transcribe(str(mp3))` at line ~104 becomes a glob of the same stem; the
9 orphans in `circle_audio/` are then consumed instead of re-downloaded.)

### R3

```diff
--- a/youtube_scraper.py
+++ b/youtube_scraper.py
@@ -55,6 +55,7 @@ def get_transcripts():
 def get_transcripts():
     api = YouTubeTranscriptApi()
+    faillog = DATA_DIR / "_transcript_failures.jsonl"
     print(f"\n=== Transcripts ({len(ALL_IDS)} videos) ===")
     for vid in ALL_IDS:
         fpath = DATA_DIR / f"{vid}_transcript.txt"
@@ -75,7 +76,11 @@ def get_transcripts():
             DATA_DIR.mkdir(exist_ok=True)
             fpath.write_text(text)
         except Exception as e:
-            print(f"  SKIP {vid}: {e}")
+            import json as _j, time as _t
+            DATA_DIR.mkdir(exist_ok=True)
+            with faillog.open("a", encoding="utf-8") as fh:
+                fh.write(_j.dumps({"id": vid, "err": type(e).__name__,
+                                   "msg": str(e)[:300], "at": _t.strftime("%Y-%m-%d")}) + "\n")
+            print(f"  SKIP {vid}: {e}")
```

### R1

No diff proposed — this is a lift-and-share of `circle_rescrape.py::CDP` into a new
`cdp_client.py`, then four call-site swaps. Structural enough that it should be its own
ticket with its own review, not a patch pasted into a diagnosis report.

---

## 6. Answer: agent team, or one-script backfill?

**One-script backfill, plus one auth fix. A LangGraph team would not touch any of the
three root causes.**

An agent team is the right shape when the work is many independent judgement calls that
need coordinating. Nothing here is a judgement call. The pipeline is stalled on a missing
Python package, a filename-suffix test, and an unlogged exception. Adding agents on top
of four scrapers that cannot import their dependency produces four agents that cannot
import their dependency.

Also, the premise is only a third true. Images are **99.2% complete** on the chart
channels through 2026-08-21, and both course-lesson corpora are **~100% transcribed**.
The only genuinely thin corpus is Discord-posted YouTube (32.5%), and about a third of
that hole is dead videos that no amount of retrying will recover.

### Cheapest path

| # | step | hands-on | unattended |
|---|---|---:|---:|
| 1 | Lift `class CDP` (`circle_rescrape.py:44`) into `cdp_client.py`; swap `discord_scraper.py:84`, `circle_video_scraper.py:171`, `circle_playlist_extractor.py:69`, `circle_scraper.py:217`; delete the playwright imports | 45 min | — |
| 2 | Re-run `discord_scraper.py` — pulls Aug 22→today messages **and their images while the `ex=` tokens are still live** | 20 min | 40 min |
| 3 | Apply the R3 diff, re-run `youtube_scraper.py` over all 2,475 union ids | 15 min | 3–4 h |
| 4 | Re-run `circle_playlist_extractor.py` — 2026 playlists were never captured, plus the 4 missing playlist ids above | 30 min | 1 h |
| 5 | Fix the two hardcoded `C:\Users\aharg\tradingbot` paths, re-run the 36-group extraction over the 105 unmined course transcripts | 20 min | 2 h |
| 6 | Apply the R2 diff so the next transcription batch does not silently skip | 15 min | — |

**Total: ~2.5 h hands-on, ~8 h unattended, single-threaded, one script at a time.**
Steps 1–3 are the whole answer to Austin's question; 4–6 are cleanup.

Step 3 is also the only measurement that matters here: its failure log is the first hard
number on how many of the 1,463 are permanently unavailable versus recoverable. Do not
build anything larger before reading it.

### Where fan-out would actually earn its keep — and it is still not a graph of agents

Annotating the **30,053** Discord chart images is the one stage with real fan-out; the T3
pilot covered 200 of them (0.7%). But the ladder already picked the winner —
`google/gemma-4-31b-it`, 80.0% price-in-range, **$0.0128 per 200 images ≈ $1.92 for all
30k**. That is a batch job with a concurrency pool, not a multi-agent system. And the
script the ladder says would run it, `scarface_image_annotator.py`, does not exist and
has to be written first. Ticket it separately, after Step 3 reports.
