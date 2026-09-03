# G7.1 / drawdown — the true max drawdown of the 2-year book

**Austin:** *"you say max drawdown is not an issue but i still see it in the graph."*

**He is right on both halves, and they are not in conflict.** The drawdown in the
graph is real, it is drawn accurately, and it is **17.13R = $17,132 at 1R = $1,000**.
It "is not an issue" only because it is 1.3% of a +1,339R book — the equity chart
auto-scales its y-axis, so that dip renders **2.7 pixels deep on a 212-pixel plot**
in the default view and **114 pixels deep** the moment you filter to one slice.
The picture changes; the money does not.

And the honest answer to the prop question is the opposite of reassuring:
**at $1,000 per R this book blows every trailing floor from 4% to 6% of a $150k
account.** It only fits inside 4% at a risk unit of **$350–$408 per trade**.

Scripts (run 2026-08-29 on this machine, all read-only):

| script | what it produced |
|---|---|
| `research/g71_drawdown_audit.py` | depth, dates, duration, streaks, prop-floor table → `research/g71_drawdown.json` |
| `research/g71_drawdown_visual.py` | pixel geometry of the chart, per-filter drawdowns, months panel, time under water |
| `research/g71_drawdown_concurrency.py` | simultaneous open risk and worst intraday excursions |

Book: `research/bt2y_trades.json`, generated 2026-08-29T03:14:29 — 76,019 signals,
**2,437 traded**, 500 sessions 2024-08-21 → 2026-08-21, `LOSS_HALT` **on** (857 blocked),
total **+1,339.09R**, mean **+0.5495R**, win rate **49.5%** (1,198W / 1,222L / 17 scratch).

---

## 1. Where drawdown is computed and where it is charted

| file:line | what it does |
|---|---|
| `research/build_bt2y_report.py:378` | `var eq=0, peak=0, dd=0, …` — the only DD in the page |
| `research/build_bt2y_report.py:385` | `eq+=r; if(eq>peak) peak=eq; if(peak-eq>dd) dd=peak-eq;` |
| `research/build_bt2y_report.py:332-341` | `order` — sorted by `(day, et)`, so the curve **is** chronological. No bug. |
| `research/build_bt2y_report.py:479` | the KPI card: `["Max drawdown", "-"+fmt(s.dd,1)+"R", "worst peak-to-trough", "neg"]` |
| `research/build_bt2y_report.py:506 drawEquity` | the graph he is looking at — same series, 720×260, y auto-scaled |
| `research/build_bt2y_report.py:668,680` | the edge-scanner table's `MaxDD` column, per slice |
| `research/t0_rebaseline.py:43-48` | the same peak-to-trough, in Python, for the T0 before/after table |
| `research/t23_stack.py:261` | `max_dd_r` per arm |
| `research/x2_stop_floor_audit.py:405-412` | the standalone DD rig |

**`backtest_report.md`, `backtest_report_12mo.md`, `backtest_charts.json` and
`backtest_charts_12mo.json` contain no drawdown at all.** Those chart files are
905 per-trade candle records — they are not equity curves. If the graph Austin is
looking at is one of those, it is not showing drawdown of the book at all; the
only equity graph in the repo is `research/omen-2y-backtest.html`.

`research/omen-2y-backtest.html` (2026-08-29T03:27) embeds `"generated":"2026-08-29T03:14:29"`
and `"traded":2437` — it renders the current book. The graph is live and correct.

---

## 2. The true max drawdown

### Trade level — the intraday high-water an intraday-trailing account ratchets on

| | |
|---|---|
| **depth** | **−17.13R = −$17,132** |
| peak | 2025-08-22 10:04 TSLA, equity +588.60R |
| trough | 2025-09-12 10:05 META, equity +571.46R |
| duration | **73 trades / 15 trading sessions** (2025-08-22 → 2025-09-12) |
| recovery | 2025-09-22 — **21 sessions under water** from the peak |
| share of book | 1.3% of +1,339.1R |

Worst six episodes:

| depth | peak | trough | $ | trades | sessions |
|---:|---|---|---:|---:|---:|
| 17.13R | 2025-08-22 10:04 TSLA | 2025-09-12 10:05 META | $17,132 | 73 | 15 |
| 15.40R | 2025-10-13 10:06 COIN | 2025-10-31 10:05 META | $15,402 | 80 | 15 |
| 12.92R | 2024-11-27 09:44 AMZN | 2024-12-06 10:00 IWM | $12,924 | 19 | 7 |
| 11.60R | 2024-09-09 10:24 AVGO | 2024-09-24 10:09 NVDA | $11,605 | 32 | 12 |
| 11.41R | 2026-02-06 09:57 AAPL | 2026-02-12 09:46 MU | $11,410 | 19 | 5 |
| 11.00R | 2025-05-20 09:51 AVGO | 2025-05-28 10:00 QQQ | $11,000 | 11 | 6 |

### Day level — what an EOD-trailing account (Apex 4.0, Topstep MLL, MFF Pro) sees

| depth | peak day | trough day | $ | sessions |
|---:|---|---|---:|---:|
| **14.71R** | **2025-08-28** | **2025-09-11** | **$14,714** | **10** |
| 11.00R | 2025-05-20 | 2025-05-28 | $11,000 | 6 |
| 10.60R | 2024-09-09 | 2024-09-24 | $10,605 | 12 |
| 10.24R | 2025-10-20 | 2025-10-28 | $10,239 | 7 |
| 10.02R | 2024-11-26 | 2024-12-06 | $10,020 | 8 |
| 8.33R | 2026-06-23 | 2026-06-26 | $8,329 | 4 |

### Streaks

| | |
|---|---|
| max consecutive **losing trades** | **11** — 2025-05-21 10:02 AMZN → 2025-05-28 10:00 QQQ, −11.00R / −$11,000 |
| max consecutive **losing days** | **6** — 2025-10-21 → 2025-10-28, −10.24R / −$10,239 |
| worst single day | 2026-06-26, −5.78R / −$5,784 on 7 trades |
| most trades in one day | 22, on 2025-08-22 |
| trades/day | mean 4.91, median 4, p95 10 |

### Time under water

**55.2% of the 496 trading sessions closed below a prior equity peak.** Longest
under-water runs, in sessions: 15, 15, 12, 12, 10, 7, 7, 7. The *longest* stretch
(not the deepest) is 2025-10-13 → 2025-11-18, 132 trades and 27 sessions, 15.40R deep.

---

## 3. Why it looks big in the graph even though it is 1.3% of the book

`drawEquity` at `build_bt2y_report.py:507-512` fixes the plot at 212 px of height
and auto-scales y to `[min(0,min eq), max(0,max eq)]`. The pixel depth of the
identical drawdown therefore depends entirely on what is filtered:

| view on the page | n | total R | max DD | **px deep** | % of plot height |
|---|---:|---:|---:|---:|---:|
| **book = traded (the default)** | 2,437 | +1,339.1 | 17.13R | **2.7** | 1.3% |
| year = 2025 | 1,183 | +583.3 | 17.13R | 6.1 | 2.9% |
| year = 2024 | 328 | +157.2 | 12.92R | 16.7 | 7.9% |
| setup = one_candle_rule | 379 | +262.4 | 13.56R | 10.9 | 5.1% |
| Austin grade = S | 298 | +105.7 | 10.89R | 21.3 | 10.0% |
| symbol = TSLA | 170 | +91.6 | 10.06R | 22.4 | 10.6% |
| **symbol = IREN** | 90 | +21.7 | **24.11R** | **109.7** | **51.7%** |
| **engine grade = A** | 72 | +15.6 | **11.16R** | **114.4** | **54.0%** |

Two things fall out of that table and both are Austin's point, not a rebuttal of it:

1. **The visual size of the dip carries no information.** A 2.7 px dip and a 114 px
   dip are the same 11–17R. Anyone reading the chart for risk is reading a number
   the chart does not encode.
2. **Some slices really are worse than the whole book.** `symbol = IREN` draws down
   **24.11R** — deeper than the entire 2,437-trade book — on a slice that only ever
   made +21.7R total. `engine grade = A` (72 trades, +15.6R) draws down 11.16R and
   spends 35 sessions under water. The edge-scanner table at `:668/:680` prints
   exactly these per-slice MaxDDs, so they are already on his screen.

The months panel is unambiguous and green: **25 of 25 months positive**, worst
2025-09 at +3.92R, best 2026-07 at +114.20R. So the dip he sees is not a red month;
it is intra-month.

---

## 4. Would it bust a prop-firm trailing drawdown of 4–6%?

**At 1R = $1,000: yes, comfortably, on every floor in the range and on every real
firm's floor.**

| floor | $ | book EOD DD | book intraday DD | verdict at $1,000/R |
|---|---:|---:|---:|---|
| 4% of $150k | $6,000 | $14,714 | $17,132 | **BUST (2.9×)** |
| 5% of $150k | $7,500 | $14,714 | $17,132 | **BUST (2.3×)** |
| 6% of $150k | $9,000 | $14,714 | $17,132 | **BUST (1.9×)** |
| Apex $150K EOD 4.0 (`research/g4_prop_fit.md`) | $4,000 | $14,714 | $17,132 | **BUST (4.3×)** |
| Topstep $150K MLL / MFF Pro | $4,500 | $14,714 | $17,132 | **BUST (3.8×)** |
| Vanquish $150k (`risk_of_ruin.py`) | $7,500 | $14,714 | $17,132 | **BUST (2.3×)** |

The book's drawdown is scale-free in R, so the question is only what risk unit it
survives at:

| risk/trade | EOD DD $ | EOD DD % of $150k | intraday DD $ | intraday DD % |
|---:|---:|---:|---:|---:|
| $250 | $3,679 | 2.45% | $4,283 | 2.86% |
| **$350** | $5,150 | 3.43% | $5,996 | **4.00%** |
| $400 | $5,886 | 3.92% | $6,853 | 4.57% |
| $500 | $7,357 | 4.90% | $8,566 | 5.71% |
| $650 | $9,564 | 6.38% | $11,136 | 7.42% |
| $1,000 | $14,714 | 9.81% | $17,132 | 11.42% |

- **Largest risk unit that holds a 4% floor:** $408/trade EOD, **$350/trade intraday.**
- **Largest risk unit that holds a 6% floor:** $612/trade EOD, **$525/trade intraday.**
- **Apex's actual $4,000 EOD floor:** $272/trade EOD, $233/trade intraday.

This lands on top of `research/g4_prop_fit.md`, which sized the funded unit at
**$250–$525** purely from risk-of-ruin simulation without ever looking at this
curve. Two independent methods agree: **the risk unit is a few hundred dollars,
not $1,000.** Every R figure in `DIRECTION.md` is quoted at 1R = $1,000, so the
dollars a reader infers from the money gate are 2–4× what a prop account could
actually size.

Caveat that cuts against the account: these are **in-sample worst cases with zero
margin**. A live worst case is conventionally taken at 1.5–2× the backtested one,
which pushes the surviving unit for a 4% floor down to roughly **$175–$230**.

### Intraday exposure the R curve cannot show

The curve advances one trade at a time in exit order; the account does not.

- **Max simultaneously open positions: 18**, on 2025-08-22 around 10:03 ET.
  Worst case at that instant, every one at the −1.25R floor: **22.50R = $22,500.**
- 76.6% of open minutes hold one position, but 1.3% hold six or more.
- **9 of 496 sessions (1.8%) dipped to −4.00R or worse intraday** — the entire Apex
  $150K EOD floor consumed in one session at $1,000/R. 44 sessions (8.9%) dipped
  to −3.00R or worse. None reached −6.00R.
- Worst intraday realized excursions: 2026-06-26 −5.78R, 2025-02-28 −5.34R,
  2026-02-20 −5.00R, 2025-11-24 −4.97R, 2026-03-20 −4.66R.

An **intraday-trailing** plan ratchets on unrealized highs, so it is strictly worse
than any of these numbers. `research/g4_prop_fit.md` already excludes intraday-trail
plans for that reason; this book's 18-deep concurrency is the reason to keep
excluding them.

---

## 5. Two things that are stale, and one that is fine

**Fine:** the DD computation itself. `build_bt2y_report.py:385` and
`research/t0_rebaseline.py:43` both walk the curve chronologically off `(day, et)`
and both reproduce 17.13R independently of the script here. No fill is
re-implemented anywhere in this track.

**Stale 1 — `DIRECTION.md:20` and `:27` describe a book that no longer exists on disk.**
It says 2,595 traded / 43.1% win / +0.5481R / +1,422R. The book on disk is the
post-T23 one: **2,437 traded / 49.5% win / +0.5495R / +1,339R**, with the loss halt
on. `research/t23_stack.md:76-81` records the change; `DIRECTION.md` was not updated.
Anyone reading DIRECTION for the money gate is reading the pre-loss-halt engine.

**Stale 2 — the drawdown figure in circulation is 32.43R, not 17.13R.**
`research/t0_ratified_rebaseline.md:43` prints 14.94R → 32.43R for T0. T23 halved
it to 17.13R (`research/t23_stack.md:5,81`). Neither number appears in `DIRECTION.md`,
which is why "max drawdown" reads as settled: **nothing in the file an agent is
told to read first mentions drawdown at all.** That is the gap Austin is pointing at.

---

## 6. Proposed fix (NOT applied — diagnosis pass)

The KPI card gives a bare R number with no dollars, no dates and no duration, and
the chart next to it auto-scales so the dip's size is meaningless. Both are one edit.

```diff
--- a/research/build_bt2y_report.py
+++ b/research/build_bt2y_report.py
@@
 function stats(idxs){
   var n=idxs.length, w=0,l=0,sc=0, sumR=0, gp=0, gl=0, bars=0, dec=0;
-  var eq=0, peak=0, dd=0, streak=0, worstStreak=0;
+  var eq=0, peak=0, dd=0, streak=0, worstStreak=0;
+  var peakI=-1, ddPeakI=-1, ddTroughI=-1;   // so the KPI can date the drawdown
   var byMonth = {}, days = {};
   for(var k=0;k<n;k++){
     var i=idxs[k], r=cols.r[i], o=val("out",i);
     sumR+=r; bars+=cols.bars[i];
     if(o==="win"){w++;dec++;} else if(o==="loss"){l++;dec++;} else sc++;
     if(r>0) gp+=r; else gl+=-r;
-    eq+=r; if(eq>peak) peak=eq; if(peak-eq>dd) dd=peak-eq;
+    eq+=r;
+    if(eq>peak){ peak=eq; peakI=i; }
+    if(peak-eq>dd){ dd=peak-eq; ddPeakI=peakI; ddTroughI=i; }
     if(r<0){ streak++; if(streak>worstStreak) worstStreak=streak; } else streak=0;
     var m=val("ym",i); byMonth[m]=(byMonth[m]||0)+r;
     days[val("day",i)]=1;
   }
@@
-    dd: dd, worstStreak: worstStreak,
+    dd: dd, ddPeakI: ddPeakI, ddTroughI: ddTroughI,
+    worstStreak: worstStreak,
@@
-    ["Max drawdown", "-"+fmt(s.dd,1)+"R", "worst peak-to-trough", "neg"],
+    ["Max drawdown", "-"+fmt(s.dd,1)+"R",
+      money(-s.dd*RISK)+(s.ddPeakI>=0
+        ? " &middot; "+val("day",s.ddPeakI)+" \\u2192 "+val("day",s.ddTroughI)
+        : ""), "neg"],
```

Optional second half — shade the worst drawdown on the equity curve so the eye is
told what it is looking at, since the y-axis will not:

```diff
--- a/research/build_bt2y_report.py
+++ b/research/build_bt2y_report.py
@@ function drawEquity
   var d="M"+x(0)+","+y(eq[0]);
   for(var j=1;j<eq.length;j++) d+="L"+x(j)+","+y(eq[j]);
+  // mark the worst peak-to-trough so its depth is readable, not just visible
+  var sdd = stats(live);
+  if(sdd.ddPeakI>=0){
+    var a=live.indexOf(sdd.ddPeakI), b=live.indexOf(sdd.ddTroughI);
+    if(a>=0 && b>a){
+      svg.appendChild(svgEl("rect",{x:x(a), y:14, width:Math.max(1,x(b)-x(a)),
+        height:H-P-14, fill:"var(--loss)", "fill-opacity":".08"}));
+      svg.appendChild(svgEl("text",{x:(x(a)+x(b))/2, y:12, "class":"axlab",
+        "text-anchor":"middle"}, "-"+fmt(sdd.dd,1)+"R"));
+    }
+  }
   var area=d+"L"+x(eq.length-1)+","+y(Math.max(mn,0))+"L"+x(0)+","+y(Math.max(mn,0))+"Z";
```

Neither touches the engine, `stop_rule.py`, or any mark file.
`research/regression_gate.py` is unaffected — `build_bt2y_report.py` is a
presentation script with no detection code in it.

---

## 7. What to tell Austin

The dip is real and it is $17,132 at $1,000 a trade. It is small next to a
$1.3M book and it is enormous next to a prop account's floor — the same number,
two frames. At $1,000/R this book blows a 4%, 5% or 6% trailing drawdown; it fits
inside 4% only at about **$350 a trade**, which is the same risk unit
`research/g4_prop_fit.md` reached by a completely different route. Worst run:
11 losing trades in a row and 6 losing days in a row.
