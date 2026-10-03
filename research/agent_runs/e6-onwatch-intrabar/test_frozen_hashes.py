"""Freeze check: the frozen baseline modules E6 imports from the main checkout (untracked there) must match the sha256
values locked in prereg-E6.md. Kept separate from test_e6.py (which imports them) so a missing file fails HERE with a clear
message instead of an import error."""
import hashlib, os
import pytest

AR = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs"
FROZEN = {
    AR + r"\v3-t-mnq\mnq.py": "b9068778d3ec871b7763905840853113e00cd7b5eee7719fea2b22e6608ca1ec",
    AR + r"\v2-t01-orb-1m\orb1m.py": "af5b8abbd4eb93733485af2ede9d17d7d2f19ab0be89b019dba843d74c78f4a3",
}


@pytest.mark.parametrize("path", sorted(FROZEN))
def test_frozen_module_present_and_hash_matches(path):
    assert os.path.isfile(path), (
        f"FROZEN MODULE MISSING: {path}. E6 imports it by absolute path from the main tradingbot checkout (it is untracked "
        f"in git). Restore the file (sha256 must be {FROZEN[path]}) or the tests in test_e6.py cannot run.")
    got = hashlib.sha256(open(path, "rb").read()).hexdigest()
    assert got == FROZEN[path], (
        f"FROZEN MODULE CHANGED: {path} sha256 {got} != locked {FROZEN[path]} (prereg-E6.md section 5). "
        f"The baseline is no longer the frozen one; do not trust or compare results until restored.")
