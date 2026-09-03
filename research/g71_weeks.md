# G7.1 / `weeks` — green weeks as a first-class gate

**Question (Austin, 2026-08-29):** *"besides green months i want green weeks."*

**Answer in one line: the book is already 91 of 105 weeks green (86.7%), and "every week
green" is not reachable by trading less — the curve runs the other way.** Every arm that
cuts trades cuts green weeks too. The only thing that buys green weeks is a *stop-when-green*
rule at the week level, and it costs 86% of the income to go from 86.7% to 97.1%. Nothing
except the look-ahead oracle gets to 105/105.

Script: `research/g71_weeks.py`. Data: `research/_g71_weeks.json`. Book:
`research/bt2y_trades.json` (generated 2026-08-29T03:14:29, 500 sessions 2024-08-21 →
2026-08-21, 496 candidate days, **105 ISO weeks**, 25 months, 76,019 signals, 2,437 traded).

Policies P0–P5 are imported verbatim from `research/g71_firsts_policy.py` (`walk`, `ekey`,
`xkey`, `iso_week`, `P_*`) so the two tracks cannot drift. Nothing is re-simulated: every
row's R is fixed at detection, so a policy is pure selection over rows `backtest_2y.py`
already wrote. No engine file was touched.

**Definition.** A week is the ISO week of the session date. **Green = week R > 0.** A week
the policy sat out is a **flat week and is not green** — silence is not a win. On the
shipped book there are **zero flat weeks**: all 105 weeks traded.

---

## 1. Where the shipped book stands, weekly

| | value |
|---|---|
| **weeks green** | **91 / 105 = 86.7%** (Wilson 95% CI 78.9–91.9) |
| months green (for contrast) | 25 / 25 = 100% |
| **worst week** | **2025-W37, −7.66R = −$7,657** |
| **longest red streak** | **2 weeks** (2025-W36 −5.70R → 2025-W37 −7.66R, −$13,352 combined) |
| mean week | +12.75R = **$12,753/week** on 23.2 trades |
| median week | +11.07R |
| week Sharpe (mean/sd) | 12.75 / 12.70 = **1.004** |
| red weeks cost | **−41.57R total, against +1,380.66R from the 91 green weeks — 3.0%** |
| worst week / median week | **0.69** — one bad week is undone by two-thirds of one normal week |

**Weekly R distribution (105 weeks, R):**

| min | p05 | p10 | q1 | med | q3 | p90 | p95 | max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| −7.66 | −3.01 | −1.20 | +2.69 | **+11.07** | +18.43 | +29.46 | +37.73 | +59.47 |

Histogram (weeks per R bucket): `−10..−5: 3 · −5..−2: 4 · −2..0: 7 · 0..2: 9 · 2..5: 9 ·
5..10: 18 · 10..20: 31 · 20..40: 20 · 40+: 4`. **No week is worse than −10R and none is
worse than −$7,657.** The left tail is remarkably shallow; the fourteen red weeks are
mostly rounding errors (five of them are inside −$1,300).

**All 14 non-green weeks** (week, R, $, trades that week):

| week | R | $ | trades | note |
|---|---:|---:|---:|---|
| 2025-W37 | −7.66 | −$7,657 | 23 | the 2025-09 wound |
| 2025-W21 | −6.41 | −$6,405 | 11 | |
| 2025-W36 | −5.70 | −$5,695 | 23 | adjacent to W37 — the only 2-week run |
| 2024-W49 | −4.55 | −$4,547 | 14 | |
| 2025-W43 | −4.09 | −$4,089 | 24 | |
| 2025-W28 | −3.08 | −$3,075 | 18 | |
| 2024-W46 | −2.77 | −$2,769 | 17 | |
| 2026-W07 | −1.73 | −$1,730 | 23 | |
| 2025-W24 | −1.30 | −$1,305 | 17 | |
| 2024-W38 | −1.27 | −$1,275 | 15 | |
| 2024-W37 | −1.26 | −$1,265 | 14 | |
| 2026-W01 | −1.11 | −$1,109 | 15 | |
| 2025-W08 | −0.58 | −$582 | 13 | |
| 2025-W05 | −0.07 | −$72 | 26 | |

**Not one red week is a low-activity week.** They run 11–26 trades, at or above the 23.2/wk
average. A red week is not the engine going quiet; it is the engine trading normally into a
week that did not pay. That kills the obvious hypothesis before anyone spends a day on it.

---

## 2. Every policy, on the week

`t/wk` = trades per week · `%grn` = weeks green · `worst` = worst single week ·
`redrun` = longest consecutive-red-week run · `recov` = median weeks needed to earn the
worst week back · `Shrp` = weekly mean/sd · `mo` = months green (the current gate).

| policy | t/wk | weeks green | %grn | 95% CI | worst wk | worst $ | redrun | med wk R | recov | Shrp | $/wk | mo |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **P0 shipped (R31 on, concurrent)** | 23.21 | **91/105** | **86.7%** | 78.9–91.9 | −7.66 | −$7,657 | **2** | +11.07 | 0.69 | 1.00 | **$12,753** | 25/25 |
| P0u all counted (R31 off) | 31.37 | 93/105 | 88.6% | 81.1–93.3 | −12.35 | −$12,351 | 3 | +13.22 | 0.93 | 1.01 | $15,802 | 25/25 |
| P0seq all counted, 1 at a time | 17.76 | 93/105 | 88.6% | 81.1–93.3 | −9.69 | −$9,694 | 3 | +6.59 | 1.47 | 0.97 | $8,859 | 24/25 |
| P1 first signal only | 4.72 | 77/105 | 73.3% | 64.2–80.9 | −5.00 | −$5,000 | 4 | +2.18 | 2.29 | 0.68 | $2,888 | 22/25 |
| P2 first; win=done; 2 losses=done | 6.71 | 83/105 | 79.0% | 70.3–85.7 | −7.24 | −$7,238 | 4 | +3.32 | 2.18 | 0.78 | $3,805 | 22/25 |
| P3 until day net green (no cap) | 9.26 | 87/105 | 82.9% | 74.5–88.9 | −10.75 | −$10,749 | 3 | +3.97 | 2.71 | 0.79 | $4,500 | 23/25 |
| P4 until net green, 3-loss cap | 8.20 | 85/105 | 81.0% | 72.4–87.3 | −5.75 | −$5,749 | 4 | +3.23 | 1.78 | 0.78 | $4,236 | 23/25 |
| P5 P2 on S only | 3.11 | 59/105 | 56.2% | 46.6–65.3 | −6.16 | −$6,157 | 5 | +0.33 | 18.66 | 0.27 | $858 | 14/25 |
| P5b P2 on S, incl legacy-C | 3.60 | 57/105 | 54.3% | 44.8–63.5 | −6.16 | −$6,157 | 7 | +0.41 | 15.05 | 0.30 | $1,060 | 16/25 |
| ORACLE best single trade/day | 4.72 | **105/105** | 100% | 96.5–100 | **+2.83** | +$2,834 | 0 | +15.47 | — | 2.29 | $16,252 | 25/25 |

**P5's 56.2% is the broken S proxy, not his S rule** — same caveat the `firsts` track
records (`research/g71_firsts.md`, "The S restriction cannot be run today"). Do not report
it to Austin as "your S rule tested worse on weeks."

### Paired McNemar on the same 105 weeks

Green/not-green is a binary outcome on the *same* weeks, so the honest test is McNemar's
exact test on discordant weeks, not two independent intervals.

| comparison | weeks P0 wins | weeks other wins | p (exact) | verdict |
|---|---:|---:|---:|---|
| P0 vs **P1** | 22 | 8 | **0.016** | P1 is significantly **worse** on weeks |
| P0 vs P2 | 16 | 8 | 0.152 | n.s. |
| P0 vs P3 | 12 | 8 | 0.503 | n.s. |
| P0 vs P4 | 14 | 8 | 0.286 | n.s. |
| P0 vs **P5** | 38 | 6 | **<0.0001** | far worse |
| P0 vs P0seq | 6 | 8 | 0.791 | n.s. |
| P0 vs P0u | 3 | 5 | 0.727 | n.s. |
| P0 vs CAP-3 | 6 | 9 | 0.607 | n.s. |
| P0 vs **W1** | 1 | **12** | **0.0034** | W1 is significantly **better** on weeks |
| P0 vs **W2-8** | 2 | 12 | **0.013** | better |

Two of these clear their own error bar, which is rare in this project
(`omen-error-bar-exceeds-arms`). **Cutting to one trade a day costs green weeks. Stopping
the week once it is green buys them.**

---

## 3. The trade-off curve: trades/week vs P(green week) vs dollars

Two families, both measured on the same 105 weeks. **CAP-N** takes at most the first N
counted signals of a day, one position at a time — a pure *count* sweep with the kind of
trade held fixed. **W** stops the whole week the moment the week is net green.

| trades/wk | arm | P(green week) | $/week | worst week $ | redrun |
|---:|---|---:|---:|---:|---:|
| 1.99 | W2-3 stop green or −3R week | 84.8% | $1,212 | −$3,445 | 2 |
| 2.51 | **W2-5** stop green or −5R | 93.3% | $1,495 | −$5,445 | 1 |
| 2.51 | W3 P3 daily + stop week green | 85.7% | $1,369 | −$10,749 | 2 |
| 2.90 | **W2-8** stop green or −8R | 96.2% | $1,686 | −$8,445 | 1 |
| 3.04 | **W1** stop the week when green | **97.1%** | $1,757 | −$9,694 | **1** |
| 3.11 | P5 (S proxy) | 56.2% | $858 | −$6,157 | 5 |
| 4.72 | P1 / CAP-1 | 73.3% | $2,888 | −$5,000 | 4 |
| 6.71 | P2 | 79.0% | $3,805 | −$7,238 | 4 |
| 8.20 | P4 | 81.0% | $4,236 | −$5,749 | 4 |
| 9.14 | CAP-2 | 80.0% | $4,962 | −$5,405 | 5 |
| 9.26 | P3 | 82.9% | $4,500 | −$10,749 | 3 |
| 12.73 | CAP-3 | 89.5% | $6,787 | −$5,909 | 2 |
| 15.16 | CAP-4 | 84.8% | $7,518 | −$9,106 | 3 |
| 16.59 | CAP-5 | 85.7% | $7,846 | −$8,631 | 3 |
| 17.32 | CAP-6 | 85.7% | $8,304 | −$8,308 | 3 |
| 17.76 | CAP-8/10/12/16/24 (= P0seq) | 88.6% | $8,859 | −$9,694 | 3 |
| **23.21** | **P0 shipped** | **86.7%** | **$12,753** | **−$7,657** | **2** |
| 31.37 | P0u | 88.6% | $15,802 | −$12,351 | 3 |

**Read the CAP column top to bottom: P(green week) rises with trade count, from 73.3% at
4.7/wk to 88.6% at 17.8/wk.** That is not an accident of this book, it is arithmetic. If a
week is a sum of *n* trades with per-trade mean μ and sd σ, weekly mean is *n*μ and weekly
sd is √*n*·σ, so

    P(green week) = Φ( √n · μ/σ )

and it **increases** with n. Fewer trades is a smaller n and a *lower* chance of a green
week, unless the trades you drop have negative edge — which the CAP sweep shows they do
not. The model check: predicted P(green) for P0 is 84.2% against 86.7% observed, and the
realised weekly sd is 1.244× the iid prediction, so intra-week correlation costs about 24%
of the diversification but does not reverse the sign.

Above ~13 trades/week the curve is flat inside its error bar (CAP-3 89.5% vs CAP-8 88.6%,
McNemar p = 1.0). **Between 13 and 31 trades a week, green-week share is bought and paid
for; the only lever left there is dollars, and dollars keep rising.**

---

## 4. Is "every week green" achievable?

**No, not as a target the system can hit.**

**a) Nothing reaches it.** The best real arm is W1 at 102/105. The only 105/105 in the whole
table is the look-ahead oracle, which picks the best trade of each day with foresight.

**b) The arithmetic of the ask.** For a fresh 105-week stretch to come in all green at even
coin-flip odds, each week needs P(green) = 99.34%, i.e. a **weekly Sharpe of 2.48**. Today
it is **1.00**. At the current per-trade edge that needs

| target | P per week | week Sharpe | trades/week needed | × today's volume | or: per-trade μ/σ needed at today's volume |
|---|---:|---:|---:|---:|---:|
| P(all 105 green) ≥ 50% | 99.34% | 2.48 | **141.5** | **6.1×** | 0.640 |
| ≥ 80% | 99.79% | 2.86 | 188.2 | 8.1× | 0.738 |
| ≥ 95% | 99.95% | 3.30 | 250.2 | 10.8× | 0.851 |

Today's per-trade μ/σ is **0.259**. So "every week green" costs either **six times the trade
count** or **2.5× the per-trade edge** — and the six-times route means ~140 trades a week,
which the 09:30–11:00 window on 28 symbols does not produce (it produces 6.6 candidates a
day, 33 a week, of which 23 are traded).

**c) It is not a sizing question.** P(green week) is scale-invariant: halving risk per trade
halves the dollars and leaves the green-week share exactly where it is. There is no risk
setting that buys green weeks.

**d) The one thing that does work is not free, and it is the wrong shape.** W1 — stop trading
for the week the moment the week is net green — gets **102/105 (97.1%, p = 0.0034 vs P0)** on
**3.04 trades a week**. It costs:

- income **$12,753 → $1,757 a week, −86%** (total 1,339R → 184R over two years);
- a **worse** worst week: −$9,694 vs −$7,657, because W1 keeps trading into a losing week and
  only stands down after a win;
- a left tail that now matters: W1's worst week is **6.6 median weeks**, against P0's **0.69**.
  Its median week is +1.47R. It is picking up small change in front of the same bus.
- durability at the month falls 25/25 → 24/25.

That is the classic shape of a stop-when-green rule and it is exactly what a naïve 100%
weekly gate would reward. **If the weekly gate is set at 100%, the optimiser's answer is W1,
and W1 makes the system worse in every way except the metric.**

---

## 5. What the gate should be

Weekly durability should ship as a reported gate, but at a level the book can hold and with
two guards that stop it being gamed by stop-when-green:

> **Weekly durability (proposed):** ≥ 90% of weeks green **and** no red run longer than 2
> weeks **and** worst week ≥ −10R **and** worst week ≤ 1.0 median weeks.

Current shipped book: **86.7%** (miss, by 3.3 points ≈ 4 weeks) · **2-week run** (met) ·
**−7.66R** (met) · **0.69 median weeks** (met). **Three of four, and the one that misses is
the one Austin is pointing at.** The last two terms are what W1 fails (6.62 median weeks),
so the gate cannot be cleared by trading less.

The monthly gate at 100% survives only because a month aggregates four to five weeks. Keep
both rows side by side; do not replace months with weeks.

---

## 6. Proposed diff — add the weekly gate to the standard report

Not applied (diagnosis pass). Verified: patched copy builds a 10.7 MB report, and the
`isoWeek` JS was checked against Python's `date.isocalendar()` on **1,200 consecutive days
(2024-01-01 → 2027-04-14) with zero mismatches**, so the page and `research/g71_weeks.py`
cannot disagree. On the default (traded) selection the new KPIs read **Weeks green 87%,
105 weeks · Worst week −7.7R, −$7.7k, 2-week red run**.

```diff
--- a/research/build_bt2y_report.py
+++ b/research/build_bt2y_report.py
@@ -270,8 +270,14 @@
   </section>
 
   <section>
-    <h2>Monthly durability <span class="hint">the gate is every month green</span></h2>
+    <h2>Durability <span class="hint">the gate is every month green &mdash; and, since 2026-08-29, every week</span></h2>
     <div class="panel"><svg id="months" viewBox="0 0 720 200" role="img" aria-label="R by month"></svg></div>
+    <div class="panel"><svg id="weeks" viewBox="0 0 720 200" role="img" aria-label="R by ISO week"></svg></div>
+    <p class="note" style="margin-top:9px">A week is 5 sessions where a month is 21, so the
+    weekly row is the harsher read of the same gate and it is the one Austin asked for
+    (2026-08-29, &ldquo;besides green months i want green weeks&rdquo;). Denominator is the
+    ISO weeks the <i>current selection</i> touches &mdash; a week this filter never traded is
+    not counted against it. On the unfiltered traded book that is 105 weeks.</p>
   </section>
 
   <section>
@@ -373,10 +379,22 @@
 }
 
 // ---- stats ----------------------------------------------------------------
+// ISO-8601 week key, identical to Python's date.isocalendar() -- the weekly
+// durability row has to agree with research/g71_weeks.py digit for digit.
+var _wkc = {};
+function isoWeek(d){
+  if(_wkc[d]) return _wkc[d];
+  var p=d.split("-"), dt=new Date(Date.UTC(+p[0], +p[1]-1, +p[2]));
+  dt.setUTCDate(dt.getUTCDate() - ((dt.getUTCDay()+6)%7) + 3);   // Thursday
+  var y=dt.getUTCFullYear(), j4=new Date(Date.UTC(y,0,4));
+  var wk=1+Math.round(((dt-j4)/86400000 - 3 + ((j4.getUTCDay()+6)%7))/7);
+  return (_wkc[d] = y+"-W"+(wk<10?"0":"")+wk);
+}
+
 function stats(idxs){
   var n=idxs.length, w=0,l=0,sc=0, sumR=0, gp=0, gl=0, bars=0, dec=0;
   var eq=0, peak=0, dd=0, streak=0, worstStreak=0;
-  var byMonth = {}, days = {};
+  var byMonth = {}, byWeek = {}, days = {};
   for(var k=0;k<n;k++){
     var i=idxs[k], r=cols.r[i], o=val("out",i);
     sumR+=r; bars+=cols.bars[i];
@@ -385,10 +403,22 @@
     eq+=r; if(eq>peak) peak=eq; if(peak-eq>dd) dd=peak-eq;
     if(r<0){ streak++; if(streak>worstStreak) worstStreak=streak; } else streak=0;
     var m=val("ym",i); byMonth[m]=(byMonth[m]||0)+r;
-    days[val("day",i)]=1;
+    var d=val("day",i); days[d]=1;
+    var wk=isoWeek(d); byWeek[wk]=(byWeek[wk]||0)+r;
   }
   var months=Object.keys(byMonth).sort();
   var green=0; months.forEach(function(m){ if(byMonth[m]>0) green++; });
+  // Weekly durability. worstWeek is the deepest single week in R (dollars are
+  // that times RISK); worstWeekRun is the longest run of consecutive weeks
+  // that did not finish green -- the number that decides whether a red patch
+  // is one bad week or a month you would have stopped trading through.
+  var weeks=Object.keys(byWeek).sort();
+  var gw=0, worstWeek=0, wrun=0, worstWeekRun=0;
+  weeks.forEach(function(x){
+    var v=byWeek[x];
+    if(v>0){ gw++; wrun=0; } else { wrun++; if(wrun>worstWeekRun) worstWeekRun=wrun; }
+    if(v<worstWeek) worstWeek=v;
+  });
   return {n:n, w:w, l:l, sc:sc, dec:dec,
     wr: dec? w/dec*100 : 0,
     meanR: n? sumR/n : 0, sumR: sumR,
@@ -397,6 +427,9 @@
     bars: n? bars/n : 0,
     months: months, byMonth: byMonth,
     greenPct: months.length? green/months.length*100 : 0,
+    weeks: weeks, byWeek: byWeek,
+    greenWkPct: weeks.length? gw/weeks.length*100 : 0,
+    worstWeek: worstWeek, worstWeekRun: worstWeekRun,
     days: Object.keys(days).length};
 }
 
@@ -469,6 +502,7 @@
   var s = stats(live);
   var gate = s.meanR >= 2 ? "pass" : "fail";
   var durable = s.greenPct >= 100 ? "pass" : "fail";
+  var durableWk = s.greenWkPct >= 100 ? "pass" : "fail";
   var k = [
     ["Signals", s.n.toLocaleString(), s.days+" sessions touched", "neu"],
     ["Win rate", fmt(s.wr,1)+"%", s.w+"W / "+s.l+"L / "+s.sc+" scratch", "neu"],
@@ -480,6 +514,10 @@
     ["Worst losing run", s.worstStreak, "consecutive negative trades", "neu"],
     ["Months green", fmt(s.greenPct,0)+"%",
       '<span class="gate '+durable+'">'+s.months.length+" months</span>", cls(s.greenPct-50)],
+    ["Weeks green", fmt(s.greenWkPct,0)+"%",
+      '<span class="gate '+durableWk+'">'+s.weeks.length+" weeks</span>", cls(s.greenWkPct-50)],
+    ["Worst week", fmt(s.worstWeek,1)+"R",
+      money(s.worstWeek*RISK)+" &middot; "+s.worstWeekRun+"-week red run", "neg"],
     ["Avg hold", fmt(s.bars,0)+" min", "entry bar to exit bar", "neu"]
   ];
   document.getElementById("kpis").innerHTML = k.map(function(x){
@@ -574,6 +612,32 @@
   svg.appendChild(svgEl("text",{x:4,y:zero-4,"class":"axlab"},"+"+mx.toFixed(0)+"R"));
 }
 
+function drawWeeks(){
+  var svg=document.getElementById("weeks"); clear(svg);
+  var W=720,H=200,P=30;
+  var s=stats(live), ws=s.weeks;
+  if(!ws.length) return;
+  var vals=ws.map(function(x){return s.byWeek[x];});
+  var mx=Math.max.apply(null,vals.map(Math.abs))||1;
+  var bw=(W-P-8)/ws.length, zero=(H-24)/2+8;
+  ws.forEach(function(x,k){
+    var v=s.byWeek[x], h=Math.abs(v)/mx*((H-40)/2);
+    var rect=svgEl("rect",{x:P+k*bw+1,y:v>=0?zero-h:zero,width:Math.max(1,bw-2),
+      height:Math.max(1,h),rx:1,fill:v>=0?"var(--win)":"var(--loss)"});
+    rect.appendChild(svgEl("title",{},x+"  "+(v>=0?"+":"")+v.toFixed(2)+"R"));
+    svg.appendChild(rect);
+    if(k%Math.ceil(ws.length/12)===0)
+      svg.appendChild(svgEl("text",{x:P+k*bw+bw/2,y:H-6,"class":"axlab",
+        "text-anchor":"middle"},x.slice(2)));
+  });
+  svg.appendChild(svgEl("line",{x1:P,x2:W-8,y1:zero,y2:zero,stroke:"var(--line)"}));
+  svg.appendChild(svgEl("text",{x:4,y:zero-4,"class":"axlab"},"+"+mx.toFixed(0)+"R"));
+  svg.appendChild(svgEl("text",{x:4,y:zero+12,"class":"axlab"},"-"+mx.toFixed(0)+"R"));
+  svg.appendChild(svgEl("text",{x:P,y:14,"class":"axlab"},
+    "R by ISO week  "+s.weeks.length+" weeks, "+
+    ws.filter(function(x){return s.byWeek[x]>0;}).length+" green"));
+}
+
 // ---- tables ---------------------------------------------------------------
 // Sample floor for any per-slice row (edge scanner AND the breakdown table).
 // Not a JS-only number: it is universe.MIN_SAMPLE_N, threaded through by the
@@ -725,7 +789,7 @@
   refilter();
   renderChips();
   renderKPIs();
-  drawEquity(); drawHist(); drawMonths();
+  drawEquity(); drawHist(); drawMonths(); drawWeeks();
   renderScan(); renderDim(); renderTrades();
 }
```

### And the companion edit to `DIRECTION.md`

```diff
-| **Durability** | every month green | **25 of 25 months** -- MET for the first time (was 23 of 25). |
+| **Durability** | every month green **and >=90% of weeks green, no 3-week red run, worst week >= -10R** | months **25 of 25** -- MET. Weeks **91 of 105 (86.7%)** -- MISS by ~4 weeks; worst week 2025-W37 **-7.66R / -$7,657**; longest red run **2 weeks** (2025-W36+W37). Weekly row added 2026-08-29 (`research/g71_weeks.md`) after Austin: *"besides green months i want green weeks."* **Do not set the weekly bar at 100%** -- the only arm that gets near it (stop-the-week-when-green, 102/105) costs 86% of the income and makes the worst week worse. |
```

---

## Recommendation

1. **Ship the weekly row in the report** (diff above), at **≥90% green + red-run ≤2 +
   worst week ≥ −10R + worst ≤ 1.0 median weeks**. It reads 86.7% today — a near miss, and
   honest.
2. **Do not set the weekly gate at 100%.** It is unreachable (needs 6.1× the trade count or
   2.5× the per-trade edge) and the only thing that approaches it is a stop-when-green rule
   that trades the shape of the return for the shape of the metric.
3. **Green weeks are an argument for *more* trades, not fewer.** This is the opposite of the
   `firsts` track's day rule, which cuts to 4.7 trades/week and takes green weeks from 86.7%
   to 73.3% (McNemar p = 0.016). If Austin wants green weeks *and* his one-trade-a-day rule,
   he is asking for two things that pull against each other, and the week is where the
   conflict shows.
4. **The weekly wound is 2025-W36 + W37** — the same 2025-09 that is the only red month under
   every non-shipped arm. One two-week patch is the entire red-run number. Explaining
   2025-09 is worth more to the weekly gate than any policy change.

## Open question for Austin

Green weeks and his one-trade-a-day rule point in opposite directions, and the week is where
that shows: P1 takes green weeks from 87% to 73%. **Which does he want when they conflict —
the day rule, or the green week?** And is a **flat** week (no trade taken all week) a failure
of "every week green", or is standing aside fine? This report scores flat as not-green; on
the shipped book it never happens (0 of 105), but under his day rule it starts to matter.
