# g71 / track `advrouter` — adversarial verify of the "router is not the separator" claim

Scripts (written this pass, nothing shared edited):
`research/g71_advrouter_cardsplit.py`, `research/g71_advrouter_16cards.py`.
Data: `research/g71_advrouter_16cards.json`, `research/g71_advrouter_cardsplit.json`.

Method: run the BOOK's own path (`backtest_week.simulate_day` with `backtest_2y.py`'s
level inputs, `BacktestRunner` instrumented in-process to keep every captured signal and
its bar index) beside the recall harness (`t4_engine_recall.run_day` with the delegating
router from `g71_router_recall.py`) on the same symbol-days, then join on bar index.
Fidelity check: my reproduction of the book reproduces `research/bt2y_trades.json`'s row
count exactly on **16 of 16** cards.

## Reproduces

| assertion | verdict |
|---|---|
| `bt2y_trades.json` runs the correct router (`BacktestRunner._route` delegates) | TRUE — `backtest_week.py:619-644`, `super()._route` at :631 |
| PLTR 2025-07-01: harness 11 raw / 5 fired; book holds 4 rows, all X; none of the 5 fires present | TRUE, exactly |
| CRM 2025-09-19: harness 12 raw / 3 fired; book 6 rows all X/skipped_d | TRUE, exactly |
| the book's own runner detects the SAME signals and fires the SAME count on these two cards (11/5 and 12/3) | TRUE — so the router is not the discriminator here |
| the mechanism: an X row arms the 2-bar `seen[key]` window and hides the fire on the next bar | TRUE — PLTR book rows are bars 48/56/62/65, the first of each contiguous run; fires at 49,50 and 57,58,59 are eaten |
| "book fires on 2 and trades 1" | TRUE on the current book AND on the 2,595-trade post-T0 book (`git show 9edd2ba7`), so the book-identity worry is immaterial |

## Does not reproduce / overstated

1. **The cited evidence is not producible by the cited script.** `research/g71_router_diag.py:26`
   is `def part_a(symbol="QQQ", day="2025-09-23")` and `__main__` calls `part_a()` with no
   arguments — it dumps QQQ 2025-09-23 only, never PLTR or CRM, and it never opens
   `bt2y_trades.json` (no read of the book anywhere in the file). Its artifact
   `research/g71_router_diag.json` holds only `cells` and `hits`. The harness-vs-book
   comparison had to be written from scratch (`g71_advrouter_cardsplit.py`).
2. **17 → 16.** 17 of the 22 hits are in the book's 28-symbol list, but `PLTR_2024-03-11`
   predates the book's `first: 2024-08-21`; the book has **0 rows** on it. Only 16 are
   reachable. "the harness fires 17 and the book fires on 2" compares 17 against a
   16-card denominator.
3. **"Same router, same archive, same window" is false.** The two rigs compute HTF bias
   from different series — `t4_engine_recall.py:109 htf_bias` uses **daily RTH closes**,
   `backtest_week.py:713 htf_bias_for` uses **hourly closes**. They disagree on **9 of 16**
   cards (PLTR 2025-07-01 bullish/bearish, CRM 2025-09-19 bearish/bullish — inverted on both
   of the claim's own exhibits). Consequence: the fired count differs between rigs on **5 of
   16** cards and the detected count on **2 of 16**.
4. **"Card by card the book is simply MISSING rows" holds on 13 of 16, not all 16.** On
   `BABA_2025-08-28`, `SPCX_2026-06-25` and `TSM_2026-02-02` the book's own runner fires
   **zero** signals — there is nothing for dedupe to remove. Those three are lost to the
   bias/level-input difference, not to the dedupe.
5. Minor: PLTR's 5 fires are B-grade in the harness but **B,B,C,C,C** in the book's runner.

## Standing numbers, my rig, 16 in-book in-window cards

harness fired-raw 32 / deduped entries 24 · book fires 27 · fires that reach the book **5**
(2 cards) · traded **1** card · fires lost to the book dedupe **22**.

## Conflict to adjudicate

`research/g71_router.md` was rewritten in parallel and now reports held-out recall
**23/34 under BOTH routers** (no move), against the 22/34 in `g71_router_diag.json` that the
claim's "22 corrected-harness S hits" rests on. If 23 is right the hit list gains
`QQQ_2025-09-23` — which is in the book with **6 rows, all X, 0 fired** — so the counts become
18 in-symbol / 17 in-window and the book still fires 2 / trades 1. The headline is unchanged
either way; the denominator is not settled.
