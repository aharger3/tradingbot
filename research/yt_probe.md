| probe | worked | exit_code | error |
|---|---|---|---|
| video_stream (`-f "bv*[height<=720]/b[height<=720]" --no-playlist`) | no | 1 | ERROR: [youtube] 64iZlhhObY0: Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies for the authentication. See https://github.com/yt-dlp/yt-dlp/wiki/FAQ for how to pass cookies. (SABR wall: player response blocked, no format URLs returned.) |
| auto_captions (`--write-auto-subs --sub-langs en --skip-download`) | no | 1 | ERROR: [youtube] 64iZlhhObY0: Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies for the authentication. See https://github.com/yt-dlp/yt-dlp/wiki/FAQ for how to pass cookies. (SABR wall: caption tracks ride the player response, none reachable.) |
| thumbnail (`GET https://i.ytimg.com/vi/<id>/maxresdefault.jpg`, hqdefault fallback) | yes | 0 | maxresdefault.jpg HTTP 200, 1280x720 baseline JPEG, 205244 bytes. hqdefault.jpg also HTTP 200, 480x360, 18851 bytes. Image CDN unaffected by the SABR wall. |

## Channel enumeration (worked)

`yt-dlp --flat-playlist --skip-download -J <channel>/videos` — a plain web request to the channel videos tab — succeeded for both channels from this GitHub Actions IP:

- `@ScarfaceTrades` → 98 videos (channel `scarface`)
- `@jdubtrades` → 119 videos (channel `jdub`)
- Total 217 unique video IDs, sorted by `video_id` in `research/yt_worklist.jsonl` (≥200, each line carries `video_id` and `channel`).

## Probe method

All three probes ran against one video of at least 5 minutes: scarface `64iZlhhObY0` ("How To Start Day Trading As A Beginner in 2025 (Full Course)"), `duration_s = 6015`. yt-dlp was given the `node` JS runtime (`--js-runtimes node`) and current `--no-playlist`, so the only remaining variable for the stream/caption probes was the datacenter-IP wall — not a missing dependency. The flat-playlist enumeration needed no JS runtime.

## What the wall is

The watch page HTML loads (HTTP 200 via curl), but the embedded player response comes back as the SABR bot interstitial (`playabilityStatus` LOGIN_REQUIRED, surfaced by yt-dlp as "Sign in to confirm you're not a bot"). This blocks anything that needs format URLs or caption tracks: the video stream and the automatic captions both fail with exit code 1 on the same error line. Per the task's honesty rule, this block was not worked around — no cookies, no credentials, no retry with auth. **A probe that fails is a successful probe.** The wall is reported, not circumvented.

## upload_date caveat

`research/yt_worklist.jsonl` carries `video_id`, `channel`, `title`, `duration_s`, and `upload_date`. The flat videos tab exposes `duration` but not `upload_date`; the only endpoint that carries `upload_date` is the per-video watch page, which is blocked by the SABR wall above. Since that wall is not to be circumvented, `upload_date` is emitted as `null` for every row. `duration_s` is populated for all 217 rows. The done-when (≥200 lines each carrying `video_id` and `channel`) is met.

## Download cleanup

No video or caption bytes were downloaded (both probes failed at the wall before any media). The two thumbnail JPEGs fetched for the probe were deleted after recording their status; no YouTube media artifacts remain on disk.

FRAME SOURCE: thumbnail
