"""Three prespecified causal forecast-input stress paths; no model retuning."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
import sys,json,time,hashlib,math
from pathlib import Path
import numpy as np,pandas as pd,scipy
from threadpoolctl import threadpool_limits
R=Path(__file__).resolve().parent;P=R.parents[3];B=R.parent/'20260911-annual-validation-v1';OLD=R.parent/'20260911-four-candidates-v1'
sys.dont_write_bytecode=True;sys.path.insert(0,str(B))
from core import Data,Planner,execute,metrics,daystr
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
SCENARIOS=['load_underestimate','pv_overestimate','joint_optimism']
class Log:
 def __init__(self,out):self.out=out;self.handles={};self.calls=0
 def event(self,name,row):
  if name=='solver_checks':self.calls+=1
  if name not in self.handles:self.handles[name]=(self.out/f'{name}.jsonl').open('w',encoding='utf-8')
  self.handles[name].write(json.dumps(row,ensure_ascii=False)+'\n')
 def close(self):
  for h in self.handles.values():h.close()

def build_inputs(data,out):
 base=np.full((365,288,2),np.nan);EL=np.full((365,144),np.nan);EV=EL.copy()
 for d in range(1,365):
  l,v,_=data.history(d,4,7);base[d,:,0]=l;base[d,:,1]=v;EL[d]=data.a['load'][d]-l[:144];EV[d]=v[:144]-data.a['pv'][d]
 np.savez_compressed(out/'reference_inputs.npz',forecasts=base,load_underestimate_errors_kw=EL,pv_overestimate_errors_kw=EV)
 paths={};allmeta=[]
 for scenario in SCENARIOS:
  f=base.copy();donors=np.full(365,-1,dtype=int);is_event=np.zeros(365,dtype=bool)
  for d in range(31,365,14):
   eligible=[]
   for i in range(max(1,d-28),d-2):
    el=float(EL[i:i+3].sum()/6);ev=float(EV[i:i+3].sum()/6)
    if scenario=='load_underestimate' and el>0:eligible.append((el,i,el,ev))
    elif scenario=='pv_overestimate' and ev>0:eligible.append((ev,i,el,ev))
    elif scenario=='joint_optimism' and el>0 and ev>0:eligible.append((el+ev,i,el,ev))
   eligible.sort(key=lambda t:(t[0],t[1]));rank=math.ceil(.9*len(eligible))-1 if eligible else None;choice=eligible[rank] if eligible else None
   rec={'scenario':scenario,'episode_start_day':d,'episode_start':daystr(d),'eligible_blocks':len(eligible),'nearest_rank_1based':rank+1 if rank is not None else None,'source_start_day':choice[1] if choice else None,'source_start':daystr(choice[1]) if choice else None,'source_end':daystr(choice[1]+2) if choice else None,'source_score_kwh':choice[0] if choice else 0.,'donor_load_error_kwh':choice[2] if choice else 0.,'donor_pv_error_kwh':choice[3] if choice else 0.,'records':[]}
   for j in range(min(3,365-d)):
    day=d+j;is_event[day]=True
    if choice is None:continue
    src=choice[1]+j;donors[day]=src;assert src<d<=day
    el=EL[src] if scenario!='pv_overestimate' else np.zeros(144);ev=EV[src] if scenario!='load_underestimate' else np.zeros(144)
    rawl=base[day,:,0]-np.tile(el,2);rawv=base[day,:,1]+np.tile(ev,2)
    l=np.maximum(rawl,0);v=np.maximum(rawv,0);support=np.any(data.a['pv'][max(0,day-28):day]>0,axis=0);v*=np.tile(support,2)
    f[day,:,0]=l;f[day,:,1]=v
    rec['records'].append({'day':day,'date':daystr(day),'source_day':src,'load_clipped_slots':int((rawl<0).sum()),'pv_clipped_slots':int((rawv<0).sum()),'night_support_blocked_slots':int(((rawv>0)&(~np.tile(support,2))).sum()),'realized_load_underestimate_kwh':float((base[day,:144,0]-l[:144]).sum()/6),'realized_pv_overestimate_kwh':float((v[:144]-base[day,:144,1]).sum()/6)})
   allmeta.append(rec)
  err=((data.a['load']-data.a['pv'])-(f[:,:144,0]-f[:,:144,1]))/6
  np.savez_compressed(out/f'inputs-{scenario}.npz',forecasts=f,net_errors_kwh=err,donor_days=donors,event_days=is_event)
  paths[scenario]=(f,err,is_event)
 dump(out/'episodes.json',allmeta);return paths

def main():
 start=time.perf_counter();out=R/'outputs';assert not out.exists();out.mkdir();(out/'schedules').mkdir()
 saved=json.loads((B/'delivery_manifest.json').read_text(encoding='utf-8'))
 for rel,h in saved['files'].items():assert sha(B/rel)==h,rel
 raw=json.loads((P/'data/prepared-v1/manifest.json').read_text(encoding='utf-8'))['raw_sha256']
 for rel,h in raw.items():assert sha(P/rel)==h,rel
 oldprotected=json.loads((OLD/'outputs/source_hashes.json').read_text(encoding='utf-8'))
 for rel,h in oldprotected.items():assert sha(P/rel)==h,rel
 dump(out/'source_hashes.json',{'previous_files':saved['files'],'raw':raw,'oldprotected':oldprotected,'protocol':sha(R/'protocol.json'),'code':sha(R/'run_validation.py'),'core':sha(B/'core.py')})
 z=np.load(B/'annual/source_arrays.npz');data=Data.__new__(Data);data.a={'load':z['load'],'pv':z['pv']};data.ref={'load':z['reference_load'],'pv':z['reference_pv']};data.price=z['price'];data.q1=z['q1_order']
 paths=build_inputs(data,out);log=Log(out);daily=[];initial=json.loads((OLD/'outputs/initialization.json').read_text(encoding='utf-8'))['feb1_initial']
 def guard():assert log.calls<2200 and time.perf_counter()-start<1800
 for scenario in SCENARIOS:
  f,err,events=paths[scenario]
  for policy in ['equal','recent']:
   planner=Planner(data.price,log.event,guard);stock=initial;planlist=[];actual=[]
   for d in range(31,365):
    l,v=f[d,:,0],f[d,:,1];ix=np.arange(d-28,d);assert ix.max()<d;m=np.zeros(144);records=[]
    for k in range(0,144,24):
     values=err[ix,k:k+24].ravel();assert np.isfinite(values).all()
     if policy=='equal':rawq=float(np.quantile(values,.7))
     else:
      weights=np.repeat(.7**(d-1-ix),24);order=np.argsort(values,kind='stable');cdf=np.cumsum(weights[order]);rawq=float(values[order][np.searchsorted(cdf,.7*cdf[-1],side='left')])
     m[k:k+24]=max(0.,rawq);records.append({'slot_start':k,'raw_quantile':rawq,'margin':max(0.,rawq),'first_day':int(ix.min()),'last_day':int(ix.max())})
    m=np.tile(m,2);meta={'scenario':scenario,'policy':policy,'day':d,'date':daystr(d),'event_day':bool(events[d]),'cycle_day':(d-31)%14}
    log.event('risk_margins',dict(**meta,records=records));plan=planner.solve(l,v,stock,m,meta);a,b=data.truth(d);rows,stock=execute(a,b,plan[0][:144],stock,data.price)
    planlist.append(np.column_stack([l,v,m,*plan]));cols=list(rows[0]);actual.append([[r[c] for c in cols] for r in rows]);daily.append(dict(**meta,**metrics(rows,l,v)))
   np.savez_compressed(out/'schedules'/f'{scenario}-{policy}.npz',days=np.arange(31,365),plan=np.array(planlist),actual=np.array(actual),actual_columns=cols,plan_columns=['load_forecast_kw','pv_forecast_kw','margin_kwh','order_kwh','grid_charge_kwh','pv_charge_kwh','discharge_kwh','storage_end_kwh'])
   cost=sum(x['total_cost'] for x in daily if x['scenario']==scenario and x['policy']==policy);print(json.dumps({'scenario':scenario,'policy':policy,'cost':cost,'lp_calls':log.calls}),flush=True)
 log.close();df=pd.DataFrame(daily);df.to_csv(out/'daily_metrics.csv',index=False,encoding='utf-8-sig')
 summary=[]
 for (scenario,policy),g in df.groupby(['scenario','policy'],sort=True):
  row={'scenario':scenario,'policy':policy,'days':len(g)}
  for n in ['total_cost','ordinary_cost','emergency_cost','order_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh','emergency_slots']:row[n]=float(g[n].sum())
  row.update(emergency_days=int((g.emergency_kwh>1e-6).sum()),longest_within_day_emergency_minutes=int(g.longest_emergency_minutes.max()),start_kwh=float(g.storage_start_kwh.iloc[0]),end_kwh=float(g.storage_end_kwh.iloc[-1]));summary.append(row)
 pd.DataFrame(summary).to_csv(out/'comparison.csv',index=False,encoding='utf-8-sig')
 dump(out/'summary.json',{'status':'completed','lp_calls':log.calls,'new_fits':0,'seconds':time.perf_counter()-start,'initial_kwh':initial,'scenarios':SCENARIOS,'comparison':summary,'episodes_per_scenario':24,'event_days_per_scenario':72})
 dump(out/'environment.json',{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'executable':sys.executable,'code_sha256':sha(R/'run_validation.py'),'protocol_sha256':sha(R/'protocol.json'),'inherited_core_sha256':sha(B/'core.py')})
 dump(out/'output_hashes.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='output_hashes.json'})
if __name__=='__main__':
 with threadpool_limits(limits=1):main()
