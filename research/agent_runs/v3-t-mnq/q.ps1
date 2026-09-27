$r='C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs'
Get-ChildItem "$r\t02-break-retest" -File | select Name,Length | ft -AutoSize
(Get-ChildItem "$r\t01-orb5\fut" -File | select -First 20).Name -join ' '
Get-ChildItem -Path C:\Users\aharg\Desktop\Projects\tradingbot -Recurse -Filter propfirm_luck_check.py -ErrorAction SilentlyContinue | select -First 3 FullName
