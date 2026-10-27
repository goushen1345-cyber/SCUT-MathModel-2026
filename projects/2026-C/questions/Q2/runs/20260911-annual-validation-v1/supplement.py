"""Final-model controls within the authorized annual research hard budget."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
import json,time
import numpy as np,pandas as pd
from threadpoolctl import threadpool_limits
from core import R,Planner,execute,metrics,dump,sha,daystr
from annual import Risk,Logs,period_summary
from validate_variants import getdata

CONFIGS=[
 {'name':'equal-step-cdf','q':.7,'decay':1.},
 {'name':'selected-q60','q':.6,'decay':.7},
 {'name':'selected-q80','q':.8,'decay':.7},
 {'name':'selected-horizon24','q':.7,'decay':.7,'hours':24},
 {'name':'selected-no-terminal','q':.7,'decay':.7,'terminal':False},
]
def main():
 out=R/'supplement';assert not out.exists();out.mkdir();(out/'schedules').mkdir()
 dump(out/'protocol.json',{'authorization':'Q2-ANNUAL-050','purpose':'Separate quantile convention from weight contribution; directly check selected-model margin/horizon/terminal sensitivity. Numerical controls, not new candidate family or hindsight parameter selection.','configurations':CONFIGS,'lp_calls_planned':1670,'prior_new_lp_calls':6486,'new_total':8156,'hard_total_unchanged':8500,'no_retuning_of_selected_model':True})
 data=getdata();risk=Risk(data);log=Logs(out);start=time.perf_counter();daily=[]
 initial=json.loads((R.parent/'20260911-four-candidates-v1/outputs/initialization.json').read_text())['feb1_initial']
 def guard():assert log.calls<1670 and time.perf_counter()-start<600
 for cfg in CONFIGS:
  planner=Planner(data.price,log.event,guard,hours=cfg.get('hours',48),terminal=cfg.get('terminal',True));state=initial;plans=[];acts=[]
  for d in range(31,365):
   l,v,_=data.history(d,4,7);m,rec=risk.margin(d,cfg['q'],28,4,cfg['decay']);meta={'phase':'final_validation','variant':cfg['name'],'decision_date':daystr(d),'day':d}
   log.event('risk_margins',dict(**meta,records=rec));plan=planner.solve(l,v,state,m,meta);a,b=data.truth(d);rows,state=execute(a,b,plan[0][:144],state,data.price);n=len(plan[0])
   plans.append(np.column_stack([l[:n],v[:n],m[:n],*plan]));cols=list(rows[0]);acts.append([[r[c] for c in cols] for r in rows]);daily.append(dict(**meta,**metrics(rows,l,v)))
  np.savez_compressed(out/'schedules'/f'{cfg["name"]}.npz',days=np.arange(31,365),plan=np.array(plans),actual=np.array(acts),plan_columns=['load_forecast_kw','pv_forecast_kw','risk_allowance_kwh','order_kwh','grid_charge_kwh','pv_charge_kwh','discharge_kwh','storage_end_kwh'],actual_columns=cols)
  print(json.dumps({'variant':cfg['name'],'cost':sum(x['total_cost'] for x in daily if x['variant']==cfg['name']),'calls':log.calls}),flush=True)
 log.close();df=pd.DataFrame(daily);df.to_csv(out/'daily_metrics.csv',index=False,encoding='utf-8-sig');period_summary(df).to_csv(out/'comparison.csv',index=False,encoding='utf-8-sig')
 dump(out/'summary.json',{'status':'completed','lp_calls':log.calls,'seconds':time.perf_counter()-start,'code_sha256':sha(R/'supplement.py'),'selection_unchanged':True})
 dump(out/'output_hashes.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='output_hashes.json'})
if __name__=='__main__':
 with threadpool_limits(limits=1):main()
