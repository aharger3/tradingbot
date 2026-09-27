# B1 real-NQ OOS, one shot, once DATABENTO_API_KEY is in the PC User env. Paper research only.
$ErrorActionPreference = "Stop"
$env:DATABENTO_API_KEY = [Environment]::GetEnvironmentVariable("DATABENTO_API_KEY", "User")
if (-not $env:DATABENTO_API_KEY) { throw "set DATABENTO_API_KEY in User env first" }
python -m pip install -q databento
Set-Location $PSScriptRoot
python pull.py estimate --budget 120   # free; writes omen-data\databento\estimate.json
python pull.py pull --budget 120       # priority order, stops before exceeding $120
python pull.py convert                 # -> t01 CSVs + t02 json.gz bars
python oos_db.py --window A            # THE gate: 2019-09-26..2024-09-25 -> oos_A.json
python oos_db.py --window B            # report-only: 2010-06-07..2019-09-25 -> oos_B.json
