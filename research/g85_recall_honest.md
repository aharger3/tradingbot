# Does the honest entry fill change accuracy?

Measured 2026-08-30 by `research/g85_recall_honest.py`. Grades from `research/marks_pool.py`. Router: the shipped one, asserted.

## The answer

> **The honest fill does nothing.** It changes 170 individual day verdicts, but discrimination -- how much more often the engine fires on a day he graded S than on a day he refused -- moves -1.8 points with a 95% range of [-7.5, +4.0], which straddles zero. Recall rises +15.2 points and false fires rise +16.9 points, and those two cancel.

**No dollar figure moves here.** This is the accuracy half of the fill change; the money half was settled overnight (control $683/day *unobtainable*, the obtainable block $33–$68/day, options $242–$346, against Austin's bar of **$397 a day**). Recall does not have a price attached — but if the honest fill had quietly bought or cost recall, every accuracy number published before today would have been measured on an engine the repo no longer ships.

Of 303 days he graded S, **54 changed verdict** when the price changed. Of 542 days he refused, **116 changed**. So this is not a quiet change — it is a loud change that lands on both sides in equal measure.

| | honest fill | old fill | change |
|---|---:|---:|---:|
| takes a trade on a day he graded **S** | 74.3% | 59.1% | **+15.2 pts** |
| takes a trade on a day he **refused** | 67.5% | 50.6% | **+16.9 pts** |
| **the gap between them** | **+6.7 pts** | **+8.5 pts** | **-1.8 pts, 95% [-7.5, +4.0]** |

**The honest fill buys recall and pays for every point of it in false fires.** Recall going up +15.2 points would be the headline of the night if the refusals had held still. They did not — they went up +16.9. The engine did not get better at telling his days apart; it just started trading more days.

## Side by side

Both columns were replayed **today, on today's code**, over the same 1145 bar-backed judged symbol-days, with the entry price as the only difference. The third column is last night's published figure, kept because five commits have landed since — three of them in the router — and it would have been dishonest to assume they changed nothing.

**They did change nothing.** The old-fill column reproduces last night's published numbers to the day, on every row, including the 100-card cross-check. So the middle column is a genuine control and the whole of the difference in the left column is the fill.

| | honest fill (the close) | old fill (published) | last night, as published |
|---|---|---|---|
| signal produced on his S days | 97.4% (295/303) | 97.4% (295/303) | 97.4% (295/303) |
| signal produced on his refusals | 97.6% (529/542) | 97.6% (529/542) | 97.6% (529/542) |
| trade taken on his S days (recall) | 74.3% (225/303) | 59.1% (179/303) | 59.1% (179/303) |
| trade taken on his refusals (false fire) | 67.5% (366/542) | 50.6% (274/542) | 50.6% (274/542) |
| trade taken on his A days | 64.5% (147/228) | 49.1% (112/228) | 49.1% (112/228) |
| trade taken on his C days | 81.0% (47/58) | 65.5% (38/58) | 65.5% (38/58) |
| precision | 38.1% | 39.5% | 39.5% |
| **separation (S minus refusals)** | **+6.7 pts** [0.3, 12.9] | **+8.5 pts** [1.5, 15.4] | **+8.5 pts** [1.5, 15.4] |

95% bands, honest fill: recall 69.1 – 78.9, false fire 63.5 – 71.3.

## What the fill actually touched

| | honest fill | old fill | change |
|---|---:|---:|---:|
| signals the engine produced | 7563 | 7563 | +0 |
| entries the engine took | 1903 | 1050 | +853 |
| days with the same signal count | 1145 of 1145 | | |
| days with the same entry count | 543 of 1145 | | |

Detection sits upstream of the price and filtering sits downstream, and this table says which one moved: **the engine sees exactly the same 7563 signals on exactly the same days, and lets 853 more of them become trades.** Nothing was detected that was not detected before.

### Which gate let go

Replayed again over just the **50 S days the honest fill newly trades**, counting why each signal was refused:

| what happened to the signal | old fill | honest fill |
|---|---:|---:|
| `fired` | 0 | 106 |
| `skipped_d` | 569 | 459 |
| `skipped_min_stop_pct` | 1 | 2 |
| `skipped_tight` | 9 | 12 |

**It is the minimum-risk floor, and only that.** `skipped_d` is `signal_runner.py:2866` — *"an intrabar fill sitting on the stop has no trade to size"* — and it falls 569 → 459 while 106 signals start firing. The minimum-stop-percent skip barely registers (1 → 2), so the report's first guess that both gates were involved was wrong and is corrected here. The reason is direct: the old fill back-dated the entry onto the level, and for a break-and-retest the level **is** the stop, so `entry - stop` collapsed toward zero and the trade could not be sized. Paying the minute's close puts real distance between entry and stop, and the floor stops binding.

That is worth saying plainly on its own: **for two years the unobtainable fill was silently vetoing the engine's own trades.** It priced the entry so close to the stop that the sizer refused them. Fixing the price did not make the engine smarter — it un-blocked a gate that the fake price was tripping.

Day-level verdict flips, by his grade:

| his grade | traded only on the honest fill | traded only on the old fill |
|---|---:|---:|
| S | 50 | 4 |
| A | 43 | 8 |
| C | 11 | 2 |
| B | 2 | 0 |
| none | 104 | 12 |

## The paired test

Same days, both arms, so this is a paired comparison and not two independent samples.

| | days | both fire | honest only | old only | neither | exact p |
|---|---:|---:|---:|---:|---:|---:|
| his S days | 303 | 175 | 50 | 4 | 74 | 0.000 |
| his refusals | 542 | 262 | 104 | 12 | 164 | 0.000 |

*("honest only" = the day is traded on the honest fill and silent on the old one.)*

## By setup — his label, honest fill vs old fill

| setup | recall, honest | recall, old | false fire, honest | false fire, old |
|---|---|---|---|---|
| break and retest | 77.5% (86/111) | 65.8% (73/111) | 84.2% (48/57) | 80.7% (46/57) |
| one candle rule | 54.1% (33/61) | 41.0% (25/61) | 65.6% (21/32) | 50.0% (16/32) |
| rule 84 | 100.0% (15/15) | 73.3% (11/15) | 100.0% (28/28) | 82.1% (23/28) |
| unlabelled | 75.5% (108/143) | 59.4% (85/143) | 63.4% (270/426) | 44.6% (190/426) |

Only 492 of the judged days carry a setup label he wrote, so these rows are thin. The unlabelled row is the rest.

## By entry minute — when the engine fired

| window | recall, honest | recall, old | false fire, honest | false fire, old |
|---|---|---|---|---|
| 09:30-09:45 | 25.7% (78/303) | 16.5% (50/303) | 10.1% (55/542) | 7.6% (41/542) |
| 09:45-10:15 | 52.8% (160/303) | 35.0% (106/303) | 39.9% (216/542) | 28.0% (152/542) |
| 10:15-11:00 | 30.0% (91/303) | 20.1% (61/303) | 39.9% (216/542) | 26.2% (142/542) |

Denominators are all S days and all refusal days, so the windows do not sum to the headline — a day can fire in more than one window.

### By the minute he stated

| window | recall, honest | recall, old |
|---|---|---|
| 09:30-09:45 | 66.7% (24/36) | 47.2% (17/36) |
| 09:45-10:15 | 68.2% (30/44) | 47.7% (21/44) |
| 10:15-11:00 | 20.0% (1/5) | 20.0% (1/5) |
| no_stated_minute | 78.0% (170/218) | 64.2% (140/218) |

## Honesty checks

- **honest fill, scored on the same 100 blind cards:** 27 of 34 S days, and 42 of 66 refusals fired.
- **published fill, scored on the same 100 blind cards:** 22 of 34 S days, and 35 of 66 refusals fired.
- **And there is the trap.** `DIRECTION.md` says to gate on held-out recall against that sample. On that sample alone the honest fill reads 27 of 34 against 22 of 34 and looks like a clear win. On the same sample its false fires go 35 of 66 to 42 of 66. **Held-out recall on its own cannot tell a better engine from a busier one** — it has no denominator for the days he refused. Score the refusals beside it, every time.
- Router delegation to `signal_runner.SignalRunner._route` asserted before either arm ran; the script exits rather than print a number off the old photocopy.
- Each arm asserts the fill mode it actually loaded with, so the two arms cannot silently be the same book.
- Legacy ladder, side by side and never mixed in: entries taken on his S days grade `{"A": 8, "B": 332, "C": 232}` (honest) and `{"A": 3, "B": 205, "C": 83}` (old). `A+` is retired; the live path now routes on his S grade.
- Replay errors: honest 0, published 0.

## Two things this changes in the files

1. **`DIRECTION.md`'s recall row is stale.** It reads 58.6%, and it says the recall and durability rows are unaffected by the fill. The recall row *is* affected: on the fill the repo now ships, recall is **74.3%** (225 of 303), and the distance to the 90% gate goes from 30.9 points to **15.7 points**. That is a real move in the gate row, and it was bought by loosening, not by discriminating.
2. **Precision is unchanged** — 38.1% against 39.5%. Of every 100 days it trades, about 38 are his and 62 are days he refused, same as before. Nothing about the sorting improved.

## What this does not say

It does not say the engine is accurate. Recall is 74.3% against a 90% gate, and it fires on 67.5% of the days he refused — the finding from last night stands unchanged: **the engine is not blind, it is undiscriminating.** All this measures is whether paying an honest price moved that.

