cd /d C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t01-orb5
python -u orb5.py proxy > run_proxy.log 2>&1
python -u orb5.py fut > run_fut.log 2>&1
python -u gate_top3.py > run_gate.log 2>&1
echo ALLDONE > alldone.txt
