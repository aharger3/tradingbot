"""eye1: predict(candidate) -> p_S using the frozen logistic model in model.json.

Pure python (no sklearn at inference). The model is L2 logistic regression on
standardised features; coefficients are readable in model.json.
"""
import json
import math
from pathlib import Path

from eye1_features import FEATURES, featurize

MODEL_PATH = Path(__file__).with_name("model.json")
_MODEL = None


def load(path=MODEL_PATH):
    global _MODEL
    m = json.loads(Path(path).read_text())
    if m["features"] != FEATURES:
        raise ValueError("model.json feature list does not match eye1_features.FEATURES")
    _MODEL = m
    return m


def predict(candidate, model=None):
    """Probability Austin would grade this candidate S (vs one-off/two-off)."""
    m = model or _MODEL or load()
    x = featurize(candidate)
    z = m["intercept"]
    for v, med, mu, sd, w in zip(x, m["median"], m["mean"], m["std"], m["coef"]):
        v = med if v is None else v
        z += w * (v - mu) / sd
    return 1.0 / (1.0 + math.exp(-z))
