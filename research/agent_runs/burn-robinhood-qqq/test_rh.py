import os, sys, subprocess
def test_selftest():
    here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([sys.executable, os.path.join(here, "rh.py"), "test"], capture_output=True, text=True)
    assert r.returncode == 0 and "TESTS OK" in r.stdout, r.stdout + r.stderr
