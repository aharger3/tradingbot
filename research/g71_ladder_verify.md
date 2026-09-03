# G7.1 adversarial verify — track `ladder`

Scripts: `research/g71_ladderv_audit.py` (book-only), `research/g71_ladderv_instr.py`
(instrumented 2y re-run), `research/g71_ladderv_attrib.py` (attribution).
Instrumented book: `research/g71_ladderv_instr_book.json` (76,035 sig / 2,436 traded;
+16 sig / −1 trade drift vs HEAD from the reason-tag patch — noted, not material).

## Reproduced
On the committed `research/bt2y_trades.json` (HEAD, 76,019 sig / 2,437 traded):
traded 2,361 B / 72 A / 4 A+; `[floor B…]` = 1,370 (56.2%); `[x-lift:clean]` = 582
(23.9%); neither = 485 (19.9%). Buckets are disjoint (0 overlap) — the floor writes
`B`, and `_apply_x_lift` only fires on `_SKIP_GRADES = ("X","D")` (signal_runner.py:190,
:2481), so a floored row can never be lifted. DIRECTION.md's "968 of 1,016" traces to
`research/a2_bt2y_rerun.json` (1,017 traded, 969 floored) — stale, as claimed.

## Refuted: the 485 bucket is not `_grade_pa`
The script infers "`_grade_pa` picked it" from the *absence* of two tags. At least three
grade-writing paths leave no tag:
- A+ stack floor, `signal_runner.py:2768` / `:3052` — `if stack and grade.value in ("C",)+_SKIP_GRADES … grade = TradeGrade.B`, explicitly overriding the candle grader.
- D→C alert bump, `:2770` / `:3054`.
- the `reentry_84_rule` grade path, which ships tradeable letters over a raw `C`.

Stamping the raw `_grade_trade` return onto every emission (`g71_ladderv_instr.py`) and
re-cutting the same buckets:

| bucket | n | raw `_grade_pa` verdict |
|---|---:|---|
| floor | 1,369 | C 991 · **X 283** · B 63 · n/a 32 |
| x-lift | 583 | **X 528** · C 47 · B 2 · n/a 6 |
| neither | 484 | B 277 · **C 109** · **X 4** · n/a 94 |

113 of the 484 "neither" rows had a raw `_grade_pa` verdict of C or X — the ladder said
*do not trade* and an untagged path made them tradeable (101 `reentry_84_rule` raw-C,
8 B&R with `aplus_stack=True`, 4 raw X). A further 94 rows never reached `_grade_trade`
at all.

**True `_grade_pa`-selected traded rows ≤ 371 / 2,436 = 15.2%**, not 485 / 19.9%.
Claim over-attributes to the legacy ladder by 114 rows (+4.7pp, 23% relative).

Second attribution error: "582 … un-vetoing a `_grade_pa` X" is **528**; 47 were raw C
and 2 raw B, D-benched by the min-risk floor and then lifted.

Third: the book is mislabelled. `research/bt2y_trades.json` at HEAD is the **T23** book
(`145d564e`, 2026-08-29 03:14, `loss_halt` on, 857 blocked). The **T0** book (`9edd2ba7`)
was 75,953 sig / **2,595** traded. Right file, wrong name.

## What survives, and is stronger
No traded row in the two-year book carries a raw `_grade_pa` verdict of `A` or `A+`.
The top two rungs of the legacy ladder select nothing at all; ≥84.8% of the traded book
gets its tradeable letter from arrival order, the X-lift, the A+ stack floor or the
reentry path. The removal being "mostly a rename" holds — the claim's own numbers just
understate it.
