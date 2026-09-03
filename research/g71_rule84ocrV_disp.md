# G71 / rule84ocrV — adversarial verify of the rule84ocr displacement claim

**Claim under test.** `_has_displacement` is a HARD veto inside
`detect_order_block_setup`, killing 39.5% of isolation survivors — but ballot q18
makes missing displacement a DOWNGRADE with BR+OCR confluence as an explicit
exemption. *"The ratified exemption is inverted, and it removes exactly the
confluence setup Austin calls his best."*

**Verdict: REFUTED on the conclusion, upheld on the arithmetic.** The 39.5% is
exactly reproducible. The reasoning attached to it is not: q18 is a rule about the
**B&R** path on **Austin's S/A/C downgrade ladder**, the veto sits on the **OCR**
path in the **legacy A+/A/B/C/X detection** chain, the ratified exemption **is
already implemented** in the layer q18 belongs to, and the veto measurably removes
**zero** BR+OCR-confluence B&R signals.

Scripts (read-only, none touches an engine file):

| script | what it does |
|---|---|
| `research/g71_rule84ocrV_disp.py` | re-runs the funnel; adds a distinct-setup denominator |
| `research/g71_rule84ocrV_brocr_ab.py` | A/Bs `DISPLACEMENT_MULT` 1.5 vs 0.0 over real signals, counting `br_ocr` |

---

## 1. What reproduces

`python research/g71_rule84ocrV_disp.py 25 6`, AAPL/AMD/AMZN/AVGO/BABA/COIN,
2026-06-25 → 2026-07-30, 09:30–11:00:

```
3 passed isolation                1902    9.11%
4 KILLED by _has_displacement      751    3.60%
4 passed displacement             1151    5.51%
BAR-EVAL   751/1902 = 39.48%
DISTINCT   (sym,day,dir,block_idx,break_idx): 177/371 = 47.71%
```

Byte-identical to `research/g71_rule84ocr.md`. `omen_bot.py:427` is a hard
`return None, None, "No displacement - slow/hesitant break, skipped"`. No
look-ahead: the funnel evaluates `bars[:i+1]` only, and `break_idx` comes from
`MarketStructure.last_hh/last_ll` inside that window.

Two caveats the original report did not state:

- The 20,880 denominator is **bar × direction evaluations**, not setups. There are
  only **371 distinct (symbol, day, direction, block_idx, break_idx) setups** in
  that population — 56× re-counting. The ratio survives (47.7% on distinct setups),
  so this does not rescue the claim, but no percentage in that funnel is a
  per-setup rate.
- Book currency is a non-issue here: the funnel is bar-derived, not book-derived.
  For the record, `research/bt2y_trades.json` meta = 500 sessions / 76,019 signals
  / **2,437 traded**, generated 2026-08-29 03:14, and 2,437 is the current post-T23
  book that **supersedes** the 2,595-trade post-T0 one
  (`research/g71_sigfireverify.md:19`, `research/g71_ddverify.md:33`).

## 2. Refutation A — q18 is a **B&R** rule, and the B&R path has no displacement gate

`research/rule_ballot_batch01.jsonl`:

```json
{"q": 18, "rule": "br-needs-displacement", "answer": "tweak",
 "note": "This is true for 90 percent of S trades. for the other 10 percent, no
 displacement is forgiven if: BR OCR confluence, bull/bear flag to start the day,
 longer timeframe thesis"}
```

The rule id is `br-needs-displacement`. `signal_runner.py:153-155`, unchanged:

```
# omen_bot._has_displacement gates the OCR path only
# (detect_order_block_setup); the B&R entry path never checked displacement.
```

Verified empirically in §4: disabling the veto moves the B&R signal count by 0.
A gate that does not exist on the path the ballot addresses cannot be that
ballot's exemption "inverted".

Note also that q18's answer **ratifies** the displacement requirement for 90% of S
trades. It is not a gate with no source; it is a gate whose source says "true,
with three carve-outs".

## 3. Refutation B — the exemption is implemented, in the layer q18 lives in

q18 is item **#1 of the eight downgrade variables** on Austin's S/A/C ladder
(`omen-rulebook.md:272`), and CLAUDE.md is explicit that this ladder is
*"measured only, **not wired into detection**"*. `_has_displacement` is a
detection gate feeding the legacy `A+/A/B/C/X` chain. Treating a downgrade-list
exemption as a detection-gate exemption is the ladder mix the repo forbids.

In the ladder it does belong to, the exemption is live and reachable —
`research/downgrade.py:516-528`:

```python
tripped = [name for name, fn in CHECKS.items() if fn(bars, i, level, is_long)]
...
confl_br_ocr = has_confluence(bars, i, level, is_long)
confl = confl_br_ocr or confl_ml
net = len(tripped) - (1 if confl else 0)
grade = "S" if net <= 0 else ("A" if net == 1 else "C")
```

`no_displacement` is `VARIABLES[0]` (`downgrade.py:65`); BR+OCR confluence is the
`−1`. One downgrade plus confluence ⇒ `net = 0` ⇒ **S**. That is q18's exemption,
verbatim, already shipped.

`omen-rulebook.md:294-298` settled this in writing on 2026-08-23:

> This also settles the ambiguity in ballot q18 … Confluence present is a bonus;
> confluence absent costs nothing.

So the exemption is neither absent nor inverted.

## 4. Refutation C — the veto removes **zero** BR+OCR confluence B&R signals

`research/g71_rule84ocrV_brocr_ab.py`, 6 symbols × 25 sessions, real
`SignalRunner` replay, `omen_bot.DISPLACEMENT_MULT` 1.5 (shipped) vs 0.0 (veto
inert):

| setup | br_ocr | shipped | disp OFF | delta |
|---|---|---:|---:|---:|
| `break_and_retest` | False | 55 | 55 | **+0** |
| `break_and_retest` | **True** | 154 | 153 | **−1** |
| `one_candle_rule` | False | 9 | 16 | +7 |
| `one_candle_rule` | **True** | 13 | 28 | **+15** |

- **154 of the 167 shipped `br_ocr=True` signals (92.2%) are on the B&R path, and
  the veto touches none of them.** The mechanism is structural, not incidental:
  `_label_confluence` (`signal_runner.py:2394-2426`) computes the label with
  `downgrade.has_confluence` → `_break_bar` + `find_ocr` + `ocr_not_respected`
  (`downgrade.py:450-468`, `:280-314`). Nothing on that path calls
  `detect_order_block_setup` or `_has_displacement`.
- Confluence is **not** preferentially killed. Among the OCR signals the veto
  releases, `br_ocr` = 15/22 = 68%; among the OCR signals it lets through today,
  13/22 = 59%. A 9-point difference on n=44 is not "removes exactly the confluence
  setup".

## 5. What survives, and should be carried forward

The veto is real and it is expensive **on the OCR path only**: OCR signals
22 → 44 when it is made inert, a 2× recall change on 7.1% of the book's
detections. That is a legitimate A/B candidate on its own merits. What it is not
is a ratified exemption inverted, and the recommended action #3 in
`research/g71_rule84ocr.md` ("exempt BR+OCR confluence from `_has_displacement`,
per ballot q18") should not be shipped on q18's authority — q18 does not reach
this gate, and its exemption is already honoured in `downgrade.py`.

**Corrected claim.** `_has_displacement` (`omen_bot.py:427`) is a hard veto on the
OCR detection path that removes 39.5% of isolation survivors (47.7% of distinct
setups) and halves shipped OCR signals — a real, unmeasured recall lever. It is
**not** ballot q18 inverted: q18 is a B&R downgrade-ladder rule whose confluence
exemption is already implemented at `research/downgrade.py:524-528`, the B&R path
has never had a displacement gate (`signal_runner.py:153-155`), and disabling the
veto changes the BR+OCR confluence signal count by −1 of 154.
