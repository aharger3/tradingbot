# Video ladder (T6) — read the chart instead of the caption

Stage J's ceiling was *"triggers survive the caption; stops do not."* This row tests
whether feeding Gemini the **video itself** (bare YouTube URL as `fileData.fileUri`,
no download, no `yt-dlp`) recovers the stop that the caption throws away.

20 videos drawn from `research/yt_worklist.jsonl`, every one of which already yielded
caption setups in `corpus_entries.jsonl`, so each has a caption row to compare against.
Same strict-JSON schema as T3 plus a `timestamp` per setup, `null` for anything not
actually visible on screen. Done-guard held: **zero error rows written** across all
three result files.

## Coverage gap, stated

58 of 60 planned calls completed. `qwen` is missing `xZiwFNrIJRQ` and `flash` is
missing `gOIAHpy-Ays` — both were still in flight when the row hit its 3600s
timeout, and neither could be retried afterwards (the OpenRouter balance is
exhausted and the `GOOGLE_AI_STUDIO_API_KEY` quota is spent). `batch` ran all 20.
Rates below are over each rung's own completed videos; one missing video cannot
move any conclusion here.

## The measurement that decides it

`stop_rate` is the share of extracted setups that come back with a **numeric**
stop — an actual price the engine could place an order against.

This is stricter than "non-null", and deliberately so. The caption corpus stores
strings like `low of day`, `break above`, `break of 5min low` in its `stop` field:
those are 96.3% non-null but only 31.5% are a price. A rule for finding a stop is
not a stop. Both sides below are scored on the same numeric test.

```
| rung | model | videos | setups | stop_rate | level_agree_with_caption | cost_usd |
|---|---|---:|---:|---:|---:|---:|
| qwen | qwen/qwen3.7-flash | 19 | 34 | 5.9% | 1/19 (5%) | 0.0193 |
| batch | google/gemini-3.5-flash-lite | 20 | 446 | 1.3% | 6/20 (30%) | 0.5856 |
| flash | gemini-3.6-flash | 19 | 53 | 96.2% | 6/19 (32%) | 0.1900 |
```

CAPTION_BASELINE_STOP_RATE: 31.5

VERDICT: video beats captions

## What the three rungs actually did

**`flash` is the only rung that works.** 51 of 53 setups carry a real price stop —
3× the caption baseline and 16× the next-best rung. It also stays disciplined about
how much it extracts: 2.8 setups per video, close to how many setups a trader
actually calls in one video.

**`batch` over-extracts and reads nothing.** 446 setups from 20 videos — 22 per
video — with 6 stops between them. It is generating plausible-looking setup objects
rather than reading the chart, at 3× flash's cost. Its 30% level agreement comes
from having so many guesses that some land.

**`qwen` under-extracts.** 34 setups over 19 videos and 2 numeric stops. It is cheap
($0.019 for the rung) and it is not doing the job.

## The caveat this row cannot close

flash's 96.2% is a **yield** number, not an accuracy number. Its levels agree with
the caption-derived levels on only 6 of 19 videos (32%), which leaves two readings
open: either flash is reading the chart correctly and the captions were the wrong
reference all along, or flash is producing confident numbers that are not on the
screen. Nothing in this row separates those.

T3's vision ladder already built the instrument that would settle it —
`price_in_range_pct`, checking every extracted price against the day's actual bar
range. Running that grader over `video_ladder_results_flash.jsonl` is the obvious
next step and it needs no new model calls.

## Consequence

The video thread stays open, on `gemini-3.6-flash` only. Discord charts are no
longer the only possible stop source. Do not promote flash's stops into the corpus
until the in-range grading pass has run.
