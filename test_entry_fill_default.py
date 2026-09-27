"""Self-check for entry_fill's default ENTRY_FILL. Run: python test_entry_fill_default.py"""
import importlib
import os

import entry_fill

_prior = os.environ.get("ENTRY_FILL")
os.environ.pop("ENTRY_FILL", None)
try:
    reloaded = importlib.reload(entry_fill)
    assert reloaded.ENTRY_FILL == "next_open", (
        "an unset ENTRY_FILL must default to next_open (the honest fill), got %r"
        % reloaded.ENTRY_FILL)
    print("unset ENTRY_FILL defaults to next_open: OK")
finally:
    # Leave the module exactly as this process found it -- other tests in the
    # same run may import `entry_fill` and read its module-level ENTRY_FILL.
    if _prior is None:
        os.environ.pop("ENTRY_FILL", None)
    else:
        os.environ["ENTRY_FILL"] = _prior
    importlib.reload(entry_fill)

print("all entry_fill default checks passed")
