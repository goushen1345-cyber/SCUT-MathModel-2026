"""Continue the original four candidates from saved June state, without retuning."""
import os
for x in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[x]='1'
from pathlib import Path
import sys,json,time,gzip,csv,platform
import numpy as np,pandas as pd,scipy,sklearn,joblib
from threadpoolctl import threadpool_limits
from core import R,P,sha,dump,Data,Forecasts,Planner,execute,metrics,daystr
OLD=R.parent/'20260911-four-candidates-v1';O=R/'annual';START=time.perf_counter()

class Logs:
    def __init__(self,out):self.out=out;self.files={};self.writers={};self.calls=0
    def event(self,name,row):
        if name=='solver_checks':self.calls+=1
        if name not in self.files:self.files[name]=(self.out/(name+'.jsonl')).open('w',encoding='utf-8')
        self.files[name].write(json.dumps(row,ensure_ascii=False)+'\n');self.files[name].flush()
    def csv(self,name,row):
        if name not in self.writers:
            h=gzip.open(self.out/(name+'.csv.gz'),'wt',encoding='utf-8-sig',newline='');w=csv.DictWriter(h,fieldnames=list(row));w.writeheader();self.writers[name]=(h,w)
        self.writers[name][1].writerow(row)
    def close(self):
        for h in self.files.values():h.close()
        for h,w in self.writers.values():h.close()

class Risk:
    def __init__(self,data,base=(4,7)):self.data=data;self.base=base;self.errors={}
    def error(self,d):
        if d not in self.errors:
            l,v,_=self.data.history(d,*self.base);a,b=self.data.truth(d);self.errors[d]=((a-b)-(l[:144]-v[:144]))/6
        return self.errors[d]
    def margin(self,d,q=.7,days=28,group_hours=4,decay=None):
        ix=list(range(max(1,d-days),d));pool=np.array([self.error(i) for i in ix]);m=np.zeros(144);records=[]
        width=group_hours*6
        for j in range(0,144,width):
            vals=(pool[:,j:j+width] if len(ix)>=14 else pool).ravel()
            if len(ix)<7:raw=0.
            elif decay is None:raw=float(np.quantile(vals,q))
            else:
                w=np.repeat(decay**np.arange(len(ix)-1,-1,-1),width if len(ix)>=14 else 144)
                order=np.argsort(vals,kind='stable');cdf=np.cumsum(w[order]);raw=float(vals[order][np.searchsorted(cdf,q*cdf[-1],side='left')])
            m[j:j+width]=max(0.,raw);records.append({'slot_start':j,'raw_quantile':raw,'value':max(0.,raw),'count':len(vals),'first':ix[0] if ix else None,'last':ix[-1] if ix else None})
        return np.tile(m,2),records

def period_summary(df):
    summ=[]
    for variant,g in df.groupby('variant'):
        x={'variant':variant,'days':len(g),'first':g.decision_date.min(),'last':g.decision_date.max()}
        for n in ['ordinary_cost','emergency_cost','total_cost','order_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh','grid_charge_kwh','pv_charge_kwh','discharge_kwh']:
            x[n]=float(g[n].sum())
        for pre,den in [('load',len(g)*144),('pv',len(g)*144),('net',len(g)*144),('pv_positive',g.pv_positive_slots.sum())]:x[pre+'_mae_kw']=float(g[pre+'_abs_error_sum'].sum()/den)
        x.update(start_kwh=float(g.storage_start_kwh.iloc[0]),end_kwh=float(g.storage_end_kwh.iloc[-1]),emergency_days=int((g.emergency_kwh>1e-6).sum()),max_daily_cost=float(g.total_cost.max()),max_contiguous_emergency_minutes=int(g.longest_emergency_minutes.max()))
        summ.append(x)
    return pd.DataFrame(summ).sort_values('total_cost')

def main():
    assert not O.exists();O.mkdir();logs=Logs(O)
    for rel,h in json.loads((OLD/'outputs/source_hashes.json').read_text()).items():assert sha(P/rel)==h
    for rel,h in json.loads((OLD/'outputs/output_hashes.json').read_text()).items():assert sha(OLD/'outputs'/rel)==h
    def guard():
        assert time.perf_counter()-START<1200
        assert logs.calls<8500
    data=Data(O);fc=Forecasts(data,O,logs.event,guard);planner=Planner(data.price,logs.event,guard);risk=Risk(data)
    olddaily=pd.read_csv(OLD/'outputs/daily_metrics.csv',float_precision='round_trip');prior=olddaily[olddaily.phase=='comparison'].copy();daily=[]
    selected=json.loads((OLD/'outputs/january_selection.json').read_text())['selected']
    fits=[json.loads(x) for x in (OLD/'outputs/fit_log.jsonl').read_text().splitlines()]
    for kind in ['T2','T3']:
        param=selected[kind];candidates=[x for x in fits if x['model']==kind and x['hyperparameter']==param and x['cutoff']<='2025-06-30']
        last=max(x['cutoff'] for x in candidates);pair={};fid=f'{kind}-{param}-{last}'
        for var in ['load','pv']:
            f=OLD/'outputs/models'/f'{fid}-{var}.joblib';z=joblib.load(f);pair[var]=(z['model'],z['scaler'])
            logs.event('restored_models',{'kind':kind,'param':param,'variable':var,'cutoff':last,'path':str(f.relative_to(P)),'sha256':sha(f)})
        fc.models[(kind,param)]=((pd.Timestamp(last)-pd.Timestamp('2025-01-01')).days,fid,pair)
    for kind in ['T1','T2','T3','T4']:
        state=float(prior[prior.variant==kind].iloc[-1].storage_end_kwh)
        for d in range(181,365):
            meta={'phase':'annual_extension','variant':kind,'decision_date':daystr(d),'day':d}
            l,v=fc.get('T1' if kind=='T4' else kind,tuple(selected['T1']) if kind in ['T1','T4'] else selected[kind],d,31)
            mar,records=risk.margin(d) if kind=='T4' else(np.zeros(288),[])
            if records:logs.event('risk_margins',dict(**meta,quantile=.7,history_days=28,group_hours=4,records=records))
            plan=planner.solve(l,v,state,mar,meta)
            for j in range(288):logs.csv('forecast_plans',dict(**meta,target_date=daystr(d+j//144),slot=j%144,horizon_slot=j,load_forecast_kw=float(l[j]),pv_forecast_kw=float(v[j]),risk_allowance_kwh=float(mar[j]),price=float(planner.p[j]),planned_order_kwh=float(plan[0][j]),planned_grid_charge_kwh=float(plan[1][j]),planned_pv_charge_kwh=float(plan[2][j]),planned_discharge_kwh=float(plan[3][j]),planned_storage_end_kwh=float(plan[4][j]),planned_initial_storage_kwh=state,committed=int(j<144)))
            a,b=data.truth(d);rows,state=execute(a,b,plan[0][:144],state,data.price)
            for row in rows:logs.csv('execution',dict(**meta,initialization_reference=0,**row))
            rec=dict(**meta,**metrics(rows,l,v));daily.append(rec);logs.event('daily_metrics',rec)
        print(json.dumps({'completed':kind,'through':'2025-12-31','end':state,'lp_calls':logs.calls},ensure_ascii=False),flush=True)
    logs.close();ext=pd.DataFrame(daily);ext.to_csv(O/'extension_daily.csv',index=False,encoding='utf-8-sig')
    full=pd.concat([prior,ext],ignore_index=True).sort_values(['variant','decision_date']);assert len(full)==4*334
    full.to_csv(O/'daily_metrics.csv',index=False,encoding='utf-8-sig');table=period_summary(full);table.to_csv(O/'comparison.csv',index=False,encoding='utf-8-sig')
    warm=olddaily[olddaily.phase=='initialization'];warm.to_csv(O/'common_january.csv',index=False,encoding='utf-8-sig')
    month=full.assign(month=pd.to_datetime(full.decision_date).dt.month).groupby(['variant','month'])[['ordinary_cost','emergency_cost','total_cost','unused_order_kwh','unused_pv_kwh','emergency_kwh']].sum();month.to_csv(O/'monthly.csv',encoding='utf-8-sig')
    dump(O/'summary.json',{'status':'completed','new_lp_calls':logs.calls,'new_fits':fc.fitcount,'seconds':time.perf_counter()-START,'official_days':334,'common_initialization_days':31,'comparison':table.to_dict('records'),'common_january_cost':float(warm.total_cost.sum()),'retuning':False,'source_and_previous_output_hashes_unchanged':True})
    dump(O/'environment.json',{'python':sys.version,'executable':sys.executable,'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__,'protocol':sha(R/'protocol.json'),'code':{n:sha(R/n) for n in ['core.py','annual.py']}})
    dump(O/'output_hashes.json',{str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file() and p.name!='output_hashes.json'})
    print(table[['variant','ordinary_cost','emergency_cost','total_cost']].to_json(orient='records',force_ascii=False),flush=True)
if __name__=='__main__':
    with threadpool_limits(limits=1):main()
