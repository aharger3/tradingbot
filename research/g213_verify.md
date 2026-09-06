# g213_verify -- 20 hand-checked option rows

19 pass, 0 fail, 1 fetch error, of 20 sampled

Referee pass 1 note: at 20 real-priced rows in the whole book, this IS the entire real-row population, not a sample of it -- it verifies that the 20 cached prices match Polygon (cache integrity) and nothing about the other 749 model rows, the option/exit-clock choice, or the futures column.

- MSFT 2025-05-12 09:46 O:MSFT250516P00440000: stored entry=3.93 exit=3.70 -- fresh entry=3.93 exit=3.70 -- PASS
- AMD 2026-04-23 09:44 O:AMD260424C00305000: stored entry=5.50 exit=5.10 -- fresh entry=5.50 exit=5.10 -- PASS
- META 2025-11-21 09:40 O:META251121C00592500: stored entry=5.00 exit=3.96 -- fresh entry=5.00 exit=3.96 -- PASS
- SPY 2025-01-30 09:46 O:SPY250130C00605000: stored entry=1.40 exit=1.67 -- fresh entry=1.40 exit=1.67 -- PASS
- PLTR 2026-08-05 09:37 O:PLTR260807C00165000: stored entry=4.01 exit=4.90 -- fresh entry=4.01 exit=4.90 -- PASS
- QQQ 2025-02-25 09:47 O:QQQ250225P00517000: stored entry=2.38 exit=2.38 -- fresh entry=2.38 exit=2.38 -- PASS
- QQQ 2025-10-06 10:45 O:QQQ251006P00606000: stored entry=0.83 exit=0.56 -- fresh entry=0.83 exit=0.56 -- PASS
- META 2024-12-31 10:11 O:META250103P00590000: stored entry=6.35 exit=5.90 -- fresh entry=6.35 exit=5.90 -- PASS
- TSLA 2024-09-05 09:53 O:TSLA240906C00230000: FETCH ERROR (HTTP 403 / HTTP 403)
- PLTR 2024-09-23 09:43 O:PLTR240927C00037500: stored entry=0.75 exit=0.71 -- fresh entry=0.75 exit=0.71 -- PASS
- AMZN 2026-01-16 09:45 O:AMZN260116P00237500: stored entry=1.10 exit=1.02 -- fresh entry=1.10 exit=1.02 -- PASS
- GOOGL 2025-08-28 10:05 O:GOOGL250829C00210000: stored entry=2.80 exit=3.05 -- fresh entry=2.80 exit=3.05 -- PASS
- MSFT 2024-09-06 09:46 O:MSFT240906C00410000: stored entry=1.90 exit=1.40 -- fresh entry=1.90 exit=1.40 -- PASS
- PLTR 2025-03-07 09:45 O:PLTR250307C00082000: stored entry=1.79 exit=2.38 -- fresh entry=1.79 exit=2.38 -- PASS
- MSFT 2025-12-15 09:45 O:MSFT251219P00477500: stored entry=4.84 exit=5.00 -- fresh entry=4.84 exit=5.00 -- PASS
- AMD 2025-06-24 09:41 O:AMD250627C00134000: stored entry=2.55 exit=3.72 -- fresh entry=2.55 exit=3.72 -- PASS
- PLTR 2026-03-12 09:52 O:PLTR260313P00152500: stored entry=2.45 exit=2.28 -- fresh entry=2.45 exit=2.28 -- PASS
- MSFT 2024-09-13 09:47 O:MSFT240913C00427500: stored entry=1.95 exit=1.51 -- fresh entry=1.95 exit=1.51 -- PASS
- PLTR 2025-05-02 09:40 O:PLTR250502C00121000: stored entry=1.43 exit=2.04 -- fresh entry=1.43 exit=2.04 -- PASS
- TSLA 2026-07-20 09:52 O:TSLA260720P00380000: stored entry=2.85 exit=3.15 -- fresh entry=2.85 exit=3.15 -- PASS