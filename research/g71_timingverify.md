# G71/timingverify — adversarial re-check of the "T1 +0.0 splits in two" claim

Scripts: `research/g71_timingverify_recheck.py` (independent re-implementation),
`research/g71_timingverify_near.py` (near-signal dump). Read-only on every mark
file. No engine file edited.

## Verdict: the numbers reproduce exactly. One label is wrong.

Independent re-implementation of the statistic (own mark parse, own minute→bar,
own sign test) over `research/marks/probe_s_sweep_2026-08-28.jsonl` (34/34 S cards
carry a clean `notes.min`, all `H:MM`):

| measured | n | median | mean | late/exact/early | sign p |
|---|---:|---:|---:|---|---:|
| nearest SIGNAL, ±2 | 17 | +0.0 | −0.35 | 1 / 9 / 7 | 0.0703 |
| nearest FIRED, ±2 | 9 | **+1.0** | **+1.22** | **7 / 2 / 0** | **0.0156** |
| nearest FIRED, ±1 | 5 | +1.0 | +0.60 | 3 / 2 / 0 | 0.2500 |
| nearest FIRED, ±3 / ±4 | 11 | +1.0 | +1.00 | 8 / 2 / **1** | 0.0391 |
| nearest FIRED, ±6 | 12 | +1.5 | +1.42 | 9 / 2 / 1 | 0.0215 |
| RAW (undeduped) FIRED, ±2 | 9 | +1.0 | +1.22 | 7 / 2 / 0 | 0.0156 |

Bit-for-bit identical to `research/g71_timing_marks.txt`, and re-running
`python research/g71_timing.py --marks` on the current tree reproduces it too
(marks output mtime 2026-08-29T14:58 is newer than `signal_runner.py` 03:02,
`omen_bot.py`/`backtest_week.py` 02:5x — not stale).

**Paired, on the same 9 days** (the 9 FIRED±2 days are a strict subset of the 17
SIGNAL±2 days, so the split is a within-day comparison, not two populations):

```
dF (fired − his)   median +1.0  mean +1.22   7 late / 2 exact / 0 early   p=0.0156
dS (signal − his)  median -1.0  mean -0.56   0 late / 4 exact / 5 early   p=0.0625
dF − dS (paired)   median +2.0  mean +1.78   positive 9 of 9              p=0.0039
```

**Look-ahead: none.** `run_day` walks `candles[:i+1]`; an entry can only exist at
or after its own signal bar. **Reachability of "early": real, not structural.**
0 of 34 days has a fired bar before that day's first signal bar; but 4 of 34 days
have a fired entry strictly before his minute and 1 has one in `[his−6, his−1]`
(COIN 2026-04-07, dF −3). So the engine *can* fire before his minute; near his
minute it never does.

**The T0 re-baseline is not what created the split.** `t1_entry_minute_autopsy.md`'s
own table already splits the same way — its 15-row pooled statistic is 6 FIRED
(+1,0,+1,+2,+2,0 → median **+1.0**, 4 late / 2 exact / **0 early**) plus 9 DETECTED
(median **0.0**, 1 late / 4 exact / 4 early). T0 moved n from 6→9 and pushed the
sign test under 0.05; it did not reveal the split. The "T1 pooled FIRED and
DETECTED" diagnosis is therefore **confirmed straight off T1's own published table**.

## The defect: "the entries actually taken" is false for the shipped book

The FIRED population is `research.t4_engine_recall.run_day`'s `status=="fired"`
signals — a **detection-only recall harness**, not the book. Cross-checked against
`research/bt2y_trades.json` (76,019 signals, 500 sessions, 2,437 traded, meta
generated 2026-08-29T03:14 — the current post-T0/R31 book):

```
CRM  2025-09-19  his=10 harness fired 11 | book rows 6  traded 0
SMCI 2025-11-17  his=36 harness fired 38 | book rows 0  traded 0
TSM  2026-02-02  his= 6 harness fired  6 | book rows 4  traded 0
BABA 2025-02-05  his=11 harness fired 11 | book rows 10 traded 0
PLTR 2024-03-11  his=13 harness fired 15 | book rows 0  traded 0
HOOD 2024-11-06  his=49 harness fired 50 | book rows 1  traded 0
MSFT 2025-03-13  his=19 harness fired 21 | book rows 4  traded 0
AVGO 2025-10-10  his=17 harness fired 18 | book rows 18 traded 0
QQQ  2025-09-23  his= 9 harness fired 11 | book rows 6  traded 0
```

**Zero of the nine are trades in the book.** SMCI 2025-11-17 and PLTR 2024-03-11
are not in the book at all (SMCI is outside `meta.symbols`; 2024-03-11 predates
`meta.first` 2024-08-21). On the other seven the book records only `skipped_d`
rows near his minute, and its signal population differs in kind, not just in
grade — book `CRM 2025-09-19` bar 10 is a **put** on OR low while the harness's
near-window is a **call** break-and-retest run at 10/11/12. `research/t4_engine_recall.py:144-149`
warns about exactly this: `CaptureRunner._route` does not delegate to
`super()._route`, so any gate the base grows is inert in this rig.

So the correct scope is: **the entries the held-out recall harness takes**, not
the entries the book takes. The sentence "it … buys the one two candles later" is
not true of the shipped book on any of these nine days — the book buys nothing.

## Second defect, same section, not part of the claim

`research/g71_timing.md` §4 states *"Twelve near-signals over nine days. Eleven are
`X`."* The harness's own raw output over those nine days is **32 near-signals within
±2 bars, 19 graded X, and a `B:fired` on all nine days**
(`research/g71_timingverify_near.py`):

```
CRM  10:X:skipped_d · 11:B:fired · 12:C:fired
SMCI 35:X · 36:X · 37:X · 38:B:fired
TSM   5:X · 6:B:fired · 7:X · 8:C:skipped_tight
BABA 10:X · 11:B:fired · 12:C:skipped_tight · 13:X
PLTR 13:X · 15:B:fired
HOOD 48:X · 49:X · 50:B:fired
MSFT 17:X · 19:X · 20:X · 21:B:fired
AVGO 16:X · 17:X · 18:B:fired · 19:X · 19:B:fired
QQQ   9:X · 10:X · 11:B:fired
```

Seven of the nine rows in §4's table match `bt2y_trades.json`'s rows for that day
exactly (CRM 10:X, TSM 5:X, BABA 10:X, HOOD 48:X, MSFT 17:X·19:X, AVGO 16:X·19:X,
QQQ 9:X) while SMCI and PLTR — absent from the book — are harness rows. **The table
is built from a different population than the statistic above it**, and it omits
every fired signal on six of the nine days. "11 of 12 are X" should read
"19 of 32 are X, and the other 10 are fires the table dropped."

## What survives

- T1's `median +0.0` describes **detection**, not entry. Confirmed.
- On his own S days the engine's *entry* lands **+1 to +2 bars after** his minute,
  never before, paired 9/9 (p=0.0039). Confirmed on the recall harness.
- `DIRECTION.md:39`'s *"its timing is exact (median +0.0 bars)"* is a
  detection-only statement and should be qualified.
- The book cannot corroborate any of it: it takes **zero** trades on those days.
