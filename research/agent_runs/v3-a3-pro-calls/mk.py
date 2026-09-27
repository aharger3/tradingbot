import pandas as p
D=r'C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v3-a3-pro-calls\\'
r=p.read_csv(D+'pro_calls_raw.csv');b=p.read_csv(D+'pro_calls_bt.csv')
print(len(r),r.swing.sum(),len(b))
b['stop']=b['stop'].fillna(b.stop_used)
b[['source','time','instrument','direction','entry','stop','target','strike','R','orb_retest','S_match','text']].to_csv(D+'pro_calls.csv',index=False)
print(b.instrument.value_counts().head(6).to_dict())
