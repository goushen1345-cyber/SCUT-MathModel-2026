"""Bounded follow-up to observed recency-weighted-error improvement."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import time,json
import numpy as np,pandas as pd
from threadpoolctl import threadpool_limits
from core import R,Planner,execute,metrics,dump,sha,daystr
from annual import Risk,Logs,period_summary
from validate_variants import getdata

def main():
    out=R/'refinement';assert not out.exists();out.mkdir();(out/'schedules').mkdir();data=getdata();logs=Logs(out);start=time.perf_counter();risk=Risk(data);daily=[]
    initial=json.loads((R.parent/'20260911-four-candidates-v1/outputs/initialization.json').read_text())
    planner=Planner(data.price,logs.event,lambda:None)
    def run(beta,begin,end,phase):
        state=initial['jan8_initial' if begin==7 else 'feb1_initial'];name=f'error-decay{int(beta*100)}';plans=[];acts=[]
        for d in range(begin,end):
            assert time.perf_counter()-start<900 and logs.calls<2000
            l,v,_=data.history(d,4,7);mar,rec=risk.margin(d,.7,28,4,beta)
            meta={'phase':phase,'variant':name,'decision_date':daystr(d),'day':d}
            logs.event('risk_margins',dict(**meta,decay=beta,records=rec))
            plan=planner.solve(l,v,state,mar,meta);a,b=data.truth(d);rows,state=execute(a,b,plan[0][:144],state,data.price)
            plans.append(np.column_stack([l,v,mar,*plan]));cols=list(rows[0]);acts.append([[r[c] for c in cols] for r in rows]);daily.append(dict(**meta,**metrics(rows,l,v)))
        np.savez_compressed(out/'schedules'/f'{phase}-{name}.npz',days=np.arange(begin,end),plan=np.array(plans),actual=np.array(acts),plan_columns=['load_forecast_kw','pv_forecast_kw','risk_allowance_kwh','order_kwh','grid_charge_kwh','pv_charge_kwh','discharge_kwh','storage_end_kwh'],actual_columns=cols)
        cost=sum(r['total_cost'] for r in daily if r['phase']==phase and r['variant']==name);print(json.dumps({'phase':phase,'variant':name,'cost':cost,'calls':logs.calls}),flush=True);return cost
    january={str(beta):run(beta,7,31,'january') for beta in [.7,.8,.9]};chosen=float(min(january,key=january.get))
    dump(out/'selection.json',{'january_cost':january,'chosen_decay':chosen,'chosen_after':'2025-01-31 24:00','criterion':'ordinary plus emergency cost Jan8-31','scope':'only three decay settings under q0.7 and same history; recency family motivated by later diagnostics, so no independent-final-test claim'})
    for beta in [.7,.9]:run(beta,31,365,'sensitivity')
    logs.close();df=pd.DataFrame(daily);df.to_csv(out/'daily_metrics.csv',index=False,encoding='utf-8-sig');period_summary(df[df.phase=='sensitivity']).to_csv(out/'comparison.csv',index=False,encoding='utf-8-sig')
    dump(out/'summary.json',{'status':'completed','lp_calls':logs.calls,'seconds':time.perf_counter()-start,'chosen_decay':chosen,'baseline_decay80_reused':'validation/schedules/weighted-error.npz','change':'exponential recent-day weights only, forecasts q and operating constraints unchanged','code_sha256':sha(R/'refine.py')})
    dump(out/'output_hashes.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='output_hashes.json'})
if __name__=='__main__':
    with threadpool_limits(limits=1):main()
