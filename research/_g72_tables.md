
### (a) every losing trade, resting order deleted, no clamp -- arm `none`

| trades | losing trades | mean loss | median | 90th | 95th | 99th | worst |
|--:|--:|--:|--:|--:|--:|--:|--:|
| 4822 | 1776 | $1,401 | $1,291 | $2,007 | $2,385 | $3,330 | **$6,062** |

losses past $1,250: 970 | past $1,500: 525 | past $2,000: 178 | past $3,000: 32 | past $5,000: 1 | past $10,000: 0
total lost on losing trades $2,488,196, of which $447,507 sits beyond $1,250

### (b) the sweep

| catastrophic level | binds on | of which real | of which wicked out | mean loss | $/trade | win% | months | weeks | worst trade | worst drawdown |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| $1,250 | 1411 (30.9%) | 952 | 459 | $1,184 | $588 | 61.3% | 25/25 | 98/105 | $1,250 | $15,200 |
| $1,500 | 937 (20.2%) | 532 | 405 | $1,302 | $576 | 62.2% | 25/25 | 97/105 | $1,500 | $15,934 |
| $2,000 | 374 (7.9%) | 182 | 192 | $1,387 | $567 | 62.8% | 25/25 | 97/105 | $2,000 | $19,216 |
| $2,500 | 145 (3.1%) | 79 | 66 | $1,398 | $570 | 62.8% | 25/25 | 96/105 | $2,500 | $21,402 |
| $3,000 | 72 (1.5%) | 33 | 39 | $1,407 | $567 | 62.8% | 25/25 | 96/105 | $3,000 | $21,435 |
| $4,000 | 20 (0.4%) | 4 | 16 | $1,408 | $569 | 62.9% | 25/25 | 96/105 | $4,000 | $22,549 |
| $5,000 | 6 (0.1%) | 1 | 5 | $1,408 | $569 | 62.9% | 25/25 | 96/105 | $5,000 | $22,395 |
| none (uncapped) | - | - | - | $1,401 | $572 | 62.9% | 25/25 | 96/105 | $6,062 | $22,395 |
| _today's engine (order rests at the level stop)_ | - | - | - | $975 | $584 | 59.2% | 25/25 | 100/105 | $1,000 | $11,105 |
| _option 1 as the board measured it (clamp $1,250)_ | - | - | - | $1,151 | $669 | 63.0% | 25/25 | 102/105 | $1,250 | $14,299 |

### (b2) what each level buys and what it costs

| level | trades it touches | dollars of disaster it cuts | dollars it gives back on trades that would have survived | winners it turns into losses | net |
|---|--:|--:|--:|--:|--:|
| $1,250 | 1411 of 4559 (30.9%) | +$431,151 | -$342,624 | 72 | +$88,527 |
| $1,500 | 937 of 4640 (20.2%) | +$264,016 | -$242,754 | 34 | +$21,262 |
| $2,000 | 374 of 4712 (7.9%) | +$104,336 | -$114,822 | 7 | -$10,486 |
| $2,500 | 145 of 4726 (3.1%) | +$45,739 | -$45,885 | 2 | -$146 |
| $3,000 | 72 of 4726 (1.5%) | +$20,156 | -$32,240 | 1 | -$12,084 |
| $4,000 | 20 of 4727 (0.4%) | +$3,177 | -$15,186 | 0 | -$12,009 |
| $5,000 | 6 of 4727 (0.1%) | +$1,062 | -$13,625 | 0 | -$12,563 |

### (c) the tail, on the uncapped book

| a cap here | trades that lost more | share of the book | dollars of loss beyond it | share of all loss |
|---|--:|--:|--:|--:|
| $1,000 | 1649 | 34.20% | $767,961 | 30.86% |
| $1,250 | 970 | 20.12% | $447,507 | 17.99% |
| $1,500 | 525 | 10.89% | $264,346 | 10.62% |
| $1,750 | 299 | 6.20% | $163,548 | 6.57% |
| $2,000 | 178 | 3.69% | $104,021 | 4.18% |
| $2,250 | 105 | 2.18% | $68,594 | 2.76% |
| $2,500 | 77 | 1.60% | $45,775 | 1.84% |
| $3,000 | 32 | 0.66% | $20,356 | 0.82% |
| $3,500 | 17 | 0.35% | $8,973 | 0.36% |
| $4,000 | 4 | 0.08% | $3,177 | 0.13% |
| $5,000 | 1 | 0.02% | $1,062 | 0.04% |

### (c) how often a RESTING order at each level is reached at all (sample of 1200 trades, 760 of them winners)

| order here | trades whose worst moment reached it | share | WINNERS whose worst moment reached it | share of winners |
|---|--:|--:|--:|--:|
| $1,250 | 363 | 30.25% | 28 | 3.68% |
| $1,500 | 225 | 18.75% | 10 | 1.32% |
| $2,000 | 85 | 7.08% | 2 | 0.26% |
| $2,500 | 34 | 2.83% | 1 | 0.13% |
| $3,000 | 20 | 1.67% | 1 | 0.13% |
| $4,000 | 6 | 0.50% | 0 | 0.00% |
| $5,000 | 1 | 0.08% | 0 | 0.00% |

### does the cap cost edge? paired against the uncapped book

| level | shared rows | change in mean R | SE | t |
|---|--:|--:|--:|--:|
| $1,250 | 4559 | +0.0194 | 0.0096 | +2.01 |
| $1,500 | 4640 | +0.0046 | 0.0077 | +0.59 |
| $2,000 | 4712 | -0.0022 | 0.0045 | -0.49 |
| $2,500 | 4726 | -0.0000 | 0.0024 | -0.01 |
| $3,000 | 4726 | -0.0026 | 0.0020 | -1.26 |
| $4,000 | 4727 | -0.0025 | 0.0013 | -2.03 |
| $5,000 | 4727 | -0.0027 | 0.0014 | -1.91 |
| clamp1250 | 4728 | +0.0956 | 0.0044 | +21.94 |
| shipped | 4276 | +0.0169 | 0.0143 | +1.19 |

### (e) touch or close

| level | trades that lost more than it | reached it intrabar first | only its close got there | the bar BEFORE still closed inside $1,000 | where the trade stood at that prior close |
|---|--:|--:|--:|--:|--:|
| $2,000 | 178 | 178 | 0 | 155 of 157 | -$494 |
| $2,500 | 77 | 77 | 0 | 67 of 67 | -$439 |
| $3,000 | 32 | 32 | 0 | 28 of 28 | -$136 |

### (f) the sequencing governor on the uncapped book

3-loss cap + a -$2,000 floor on the day, no per-trade cap: 4891 trades over 499 days, worst single trade **$6,062**, worst day $8,976, worst drawdown $19,679. Days that still finished worse than -$2,000: 137. Single trades that alone lost more than $2,000: 169 (more than $5,000: 1).

Same governor WITH a $2,000 per-trade cap: 4773 trades, worst single trade $2,000, worst day $7,465, worst drawdown $19,540, days past -$2,000: 120.
