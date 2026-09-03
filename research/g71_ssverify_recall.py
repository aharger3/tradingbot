"""G7.1 adversarial verify (track samplesize): re-run t0_heldout_recall.score_sweep
against the CURRENT working tree, in-process, WITHOUT writing t0_heldout_recall.json.
Answers: is recall on the 34-card blind sweep still 18/34 (52.9%), the constant the
power maths is keyed to, or has the shipped engine moved?"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import research.t0_heldout_recall as t0
s = t0.score_sweep()
print(json.dumps({k: v for k, v in s.items() if k != "missed_S"}, indent=2))
print("missed_S n=%d" % len(s["missed_S"]))
json.dump(s, open(os.path.join(HERE, "g71_ssverify_recall.json"), "w"), indent=2)
