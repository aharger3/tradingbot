import subprocess
out=subprocess.run(['powershell','-NoProfile','-Command',"Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Select-Object ProcessId,CommandLine | ConvertTo-Json"],capture_output=True,text=True).stdout
import json
for p in json.loads(out) if out.strip() else []:
    cl=p.get('CommandLine') or ''
    if 'fetch' in cl: print(p['ProcessId'], cl[:150])
    if 'fetch_fut.py ES NQ' in cl and 'agent_runs' not in cl.split('fetch_fut.py')[0][-40:] :
        pass
