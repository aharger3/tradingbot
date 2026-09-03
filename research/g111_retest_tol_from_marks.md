# g111 -- the retest tolerance, derived from his marks

465 marked (symbol, day, minute) triples across the full corpus, 426 resolved to a real bar with a causal level candidate.

| unit | median | IQR | mean | touched (dist=0) |
|---|---:|---:|---:|---:|
| cents | 0.00 | [0.00, 0.00] | 5.78 | 322/426 (75.6%) |
| % of stock price | 0.0000 | [0.0000, 0.0000] | 0.0240 | -- |
| % of bar's own range | 0.000 | [0.000, 0.000] | 10.114 | -- |

Near-miss subset (the 104/426 rows that did NOT literally touch -- this is what "a few cents give or take" is a claim about):

| unit | median | IQR | mean |
|---|---:|---:|---:|
| cents | 12.44 | [4.88, 27.00] | 23.69 |
| % of stock price | 0.0640 | [0.0253, 0.1179] | 0.0983 |
| % of bar's own range | 26.783 | [10.586, 55.392] | 41.427 |

Tightest distribution, all rows (lowest CV): **% of bar range**. Tightest on the near-miss subset: **% of bar range**.
