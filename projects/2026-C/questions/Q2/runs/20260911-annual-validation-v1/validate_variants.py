"""Finite full-period sensitivity variants, preserving all outcomes."""
import os
for x in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[x]='1'
from pathlib import Path
import numpy as np,pandas as pd,json,time
from threadpoolctl import threadpool_limits
from core import R,P,Data,Planner,execute,metrics,dump,sha,daystr
from annual import Risk,Logs,period_summary

def getdata():
    z=np.load(R/'annual/source_arrays.npz');d=Data.__new__(Data);d.a={'load':z['load'],'pv':z['pv']};d.ref={'load':z['reference_load'],'pv':z['reference_pv']};d.price=z['price'];d.q1=z['q1_order'];return d

def history(data,d,w=4,p=7,decay=None):
    if decay is None:return data.history(d,w,p)[:2]
    out=[]
    for var,n,mode in [('load',w,'weekday'),('pv',p,'recent')]:
        z=[]
        for h in [0,1]:
            ix=([d+h-7*j for j in range(1,n+1) if 0<=d+h-7*j<d] if mode=='weekday' else list(range(d-1,max(-1,d-n-1),-1)))
            a=data.a[var][ix];weights=decay**np.arange(len(ix));weights/=weights.sum();z.append(np.nansum(a*weights[:,None],axis=0)/np.sum(np.isfinite(a)*weights[:,None],axis=0))
        out.append(np.concatenate(z))
    return out

def configs():
    a=[]
    for q in [.6,.8,.9]:a.append({'name':f'quantile{int(q*100)}','q':q})
    for q in [0.,.7]:
        a.extend([{'name':f'horizon24-q{int(q*100)}','q':q,'hours':24},{'name':f'no-terminal-q{int(q*100)}','q':q,'terminal':False}])
    for days in [14,56]:a.append({'name':f'error-window{days}','q':.7,'days':days})
    for group in [2,6]:a.append({'name':f'error-group{group}h','q':.7,'group':group})
    a.extend([{'name':'load1week-no-margin','q':0.,'w':1},{'name':'pv3days-no-margin','q':0.,'p':3},
              {'name':'weighted-history-no-margin','q':0.,'forecast_decay':.8},
              {'name':'weighted-error','q':.7,'risk_decay':.8}])
    return a

def main():
    out=R/'validation';assert not out.exists();out.mkdir();(out/'schedules').mkdir();log=Logs(out);data=getdata();risk=Risk(data);start=time.perf_counter()
    start_soc=json.loads((R.parent/'20260911-four-candidates-v1/outputs/initialization.json').read_text())['feb1_initial'];daily=[]
    def guard():
        assert time.perf_counter()-start<2400 and log.calls<7000
    actual_cols=None
    for cfg in configs():
        n=cfg.get('hours',48)*6;planner=Planner(data.price,log.event,guard,hours=cfg.get('hours',48),terminal=cfg.get('terminal',True));state=start_soc;save=[];actual=[];ds=[]
        for d in range(31,365):
            l,v=history(data,d,cfg.get('w',4),cfg.get('p',7),cfg.get('forecast_decay'));q=cfg['q']
            m,rec=risk.margin(d,q,cfg.get('days',28),cfg.get('group',4),cfg.get('risk_decay')) if q else(np.zeros(288),[])
            meta={'phase':'sensitivity','variant':cfg['name'],'decision_date':daystr(d),'day':d}
            if rec:log.event('risk_margins',dict(**meta,settings=cfg,records=rec))
            plan=planner.solve(l,v,state,m,meta);save.append(np.column_stack([l[:n],v[:n],m[:n],*plan]))
            a,b=data.truth(d);rows,state=execute(a,b,plan[0][:144],state,data.price)
            if actual_cols is None:actual_cols=list(rows[0])
            assert list(rows[0])==actual_cols
            actual.append([[row[c] for c in actual_cols] for row in rows]);ds.append(d)
            daily.append(dict(**meta,**metrics(rows,l,v)))
        np.savez_compressed(out/'schedules'/f'{cfg["name"]}.npz',days=ds,plan=np.array(save),actual=np.array(actual),plan_columns=['load_forecast_kw','pv_forecast_kw','risk_allowance_kwh','order_kwh','grid_charge_kwh','pv_charge_kwh','discharge_kwh','storage_end_kwh'],actual_columns=actual_cols)
        part=pd.DataFrame(daily);g=part[part.variant==cfg['name']];g.to_csv(out/'schedules'/f'{cfg["name"]}.csv',index=False,encoding='utf-8-sig')
        print(json.dumps({'variant':cfg['name'],'cost':float(g.total_cost.sum()),'lp_calls':log.calls},ensure_ascii=False),flush=True)
    log.close();df=pd.DataFrame(daily);df.to_csv(out/'daily_metrics.csv',index=False,encoding='utf-8-sig');table=period_summary(df);table.to_csv(out/'comparison.csv',index=False,encoding='utf-8-sig')
    dump(out/'summary.json',{'status':'completed','configurations':configs(),'lp_calls':log.calls,'seconds':time.perf_counter()-start,'initial_kwh':start_soc,'years':'Feb-Dec334days','sample_weighting':'forecast newest-to-oldest selected dates0.8^index normalized; residual0.8^calendar_day_age with weighted CDF quantile','no_hindsight_final_retuning':True,'code':{n:sha(R/n) for n in ['validate_variants.py','core.py','annual.py']}})
    dump(out/'output_hashes.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='output_hashes.json'})
if __name__=='__main__':
    with threadpool_limits(limits=1):main()
