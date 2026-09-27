"""eye1 tests: feature mapping + predict() agrees with the trained sklearn model."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from eye1_features import FEATURES, featurize  # noqa: E402
import eye1_model  # noqa: E402


def test_feature_count_and_spy_with():
    assert len(FEATURES) <= 10
    x = featurize({"side": "L", "spy_trend": "bull", "bars_break_to_sig": 3})
    assert x[FEATURES.index("spy_trend_with")] == 1.0
    assert abs(x[FEATURES.index("log_bars_break_to_sig")] - math.log1p(3)) < 1e-12
    x = featurize({"side": "S", "spy_trend": "bull"})
    assert x[FEATURES.index("spy_trend_with")] == 0.0


def test_missing_values_are_none_and_predict_imputes():
    x = featurize({})
    assert all(v is None for v in x)
    p = eye1_model.predict({})
    assert 0.0 < p < 1.0


def test_predict_matches_saved_test_predictions():
    preds = pd.read_csv(HERE / "test_predictions.csv")
    df = pd.read_csv(HERE / "s_trades.csv").set_index("sig_id")
    for _, r in preds.head(40).iterrows():
        cand = df.loc[r.sig_id].to_dict()
        cand["sig_id"] = r.sig_id
        assert abs(eye1_model.predict(cand) - r.p_logit) < 1e-9


def test_model_json_is_readable():
    m = json.loads((HERE / "model.json").read_text())
    assert m["features"] == FEATURES and len(m["coef"]) == len(FEATURES)
    assert np.all(np.array(m["std"]) > 0)
