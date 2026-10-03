# s-matcher

Does anything computable at decision time look like Austin's S label? Decision-time features (no future bars) joined
to his S / Not-S marks, walk-forward by date, interpretable models (tree depth 3, L1 logistic), forward R of the trades
the rule takes. Write-up: life-plan `07-money/omen/night-1003/s-matcher.md`.

    python sm_build.py OUTDIR            # feature table (stock.csv.gz, nq.csv.gz, labeled_nqctx.csv.gz), ~1 min
    python sm_fit.py   OUTDIR OUT.json   # walk-forward models + R tests, ~5 min
    python sm_posthoc.py OUTDIR OUT.json # hindsight check: re-enter his S at 11:00
    python -m pytest test_sm.py

`nq_candidates.py` is vendored from PR #40. NQZ4_2024.csv holds some reserved-window bars (2024-09-25 20:00-23:59 ET);
`sm_data._drop_reserved` filters every bar dated on or before 2024-09-25 right after each file is read, and
`build_nq_days` also skips the first session after the window: see `sm_data` and its tests. `final_model.json` is a descriptive fit on all
labels, not an out-of-sample result.
