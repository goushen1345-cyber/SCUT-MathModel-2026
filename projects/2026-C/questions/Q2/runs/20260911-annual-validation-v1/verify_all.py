"""Independent recomputation from immutable sources; no training/optimization."""
import os
for v in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[v]='1'
from pathlib import Path
from datetime import datetime,timedelta
from decimal import Decimal
from functools import lru_cache
import json,hashlib,math
import numpy as np,pandas as pd,joblib
from threadpoolctl import threadpool_limits
R=Path(__file__).resolve().parent;P=R.parents[3];OLD=R.parent/'20260911-four-candidates-v1';O=R/'annual'
read=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for rel,h in read(OLD/'outputs/source_hashes.json').items():assert sha(P/rel)==h,rel
for rel,h in read(OLD/'outputs/output_hashes.json').items():assert sha(OLD/'outputs'/rel)==h,rel
for folder in ['annual','validation','refinement']:
 for rel,h in read(R/folder/'output_hashes.json').items():assert sha(R/folder/rel)==h,rel
raw=pd.read_csv(P/'data/prepared-v1/actual_power.csv',float_precision='round_trip');base=datetime(2025,1,1)
A={x:np.full((365,144),np.nan) for x in ['load','pv']}
for r in raw.itertuples():
 t=datetime.fromisoformat(r.source_date)+timedelta(minutes=int(r.source_minute));d=(t.date()-base.date()).days
 if 0<=d<365:k=t.hour*6+t.minute//10;A['load'][d,k]=r.load_kw;A['pv'][d,k]=r.pv_actual_kw
ref=pd.read_csv(P/'data/prepared-v1/day_reference.csv',float_precision='round_trip');ref.index=(ref.source_minute%1440//10).astype(int);ref=ref.sort_index();price=ref.price_yuan_per_kwh.to_numpy()
fallback={'load':ref.load_kw.to_numpy(),'pv':ref.pv_forecast_kw.to_numpy()}
day=lambda t:(datetime.fromisoformat(t[:10])-base).days

@lru_cache(None)
def mean(var,d,h,mode,n,decay=None):
 dates=[d+h-7*j for j in range(1,n+1) if 0<=d+h-7*j<d] if mode=='week' else list(range(d-1,max(-1,d-n-1),-1))
 if not dates:dates=list(range(d-1,max(-1,d-8),-1))
 assert max(dates)<d
 w=np.ones(len(dates)) if decay is None else decay**np.arange(len(dates));z=A[var][dates];count=np.sum(np.isfinite(z)*w[:,None],axis=0)
 return np.divide(np.nansum(z*w[:,None],axis=0),count,out=fallback[var].copy(),where=count>0)
@lru_cache(None)
def features(var,d,h):
 t=2*np.pi*np.arange(144)/144;target=base+timedelta(days=int(d+h));doy=target.timetuple().tm_yday
 x=[np.sin(t),np.cos(t),np.sin(2*t),np.cos(2*t)]+[np.full(144,int(target.weekday()==i)) for i in range(7)]
 x += [np.full(144,h+1),np.full(144,np.sin(2*np.pi*doy/365)),np.full(144,np.cos(2*np.pi*doy/365))]
 x += [mean(var,d,h,'recent',1),mean(var,d,h,'recent',3),mean(var,d,h,'recent',7),mean(var,d,h,'week',1),mean(var,d,h,'week',4),np.full(144,np.nanmean(A[var][d-1])),np.full(144,np.nanmean(A[var][max(0,d-7):d]))]
 return np.column_stack(x)
@lru_cache(None)
def margin(d,q=.7,days=28,group=4,decay=None):
 ix=list(range(max(1,d-days),d));pool=np.array([(A['load'][i]-A['pv'][i]-mean('load',i,0,'week',4)+mean('pv',i,0,'recent',7))/6 for i in ix]);m=np.zeros(144)
 if len(ix)<7:return np.tile(m,2)
 width=group*6
 for k in range(0,144,width):
  z=pool[:,k:k+width] if len(ix)>=14 else pool;x=z.ravel()
  if decay is None:value=np.quantile(x,q)
  else:
   weights=np.broadcast_to((decay**(d-1-np.array(ix)))[:,None],z.shape).ravel();ind=np.argsort(x,kind='stable');cum=np.cumsum(weights[ind]);value=x[ind[np.searchsorted(cum,q*cum[-1])]]
  m[k:k+width]=max(0.,value)
 return np.tile(m,2)

counts={'actual':0,'planned':0,'forecast_values':0,'fits':0};maximum={'source':0.,'forecast':0.,'margin':0.,'balance':0.,'storage':0.,'plan':0.,'fees':0.,'features':0.}
def close(name,a,b,tol=1e-6):
 err=float(np.max(np.abs(np.asarray(a)-np.asarray(b))));maximum[name]=max(maximum[name],err);assert err<tol,(name,err)
def check_actual(df,initial):
 k=df.slot.astype(int).to_numpy();d=df.day.astype(int).to_numpy();L=A['load'][d,k].copy();V=A['pv'][d,k].copy();L[np.isnan(L)]=fallback['load'][0];V[np.isnan(V)]=fallback['pv'][0]
 close('source',df.load_kw,L);close('source',df.pv_kw,V);close('source',df.price,price[k]);close('storage',df.storage_start_kwh.iloc[0],initial)
 s=df.storage_start_kwh.to_numpy();end=df.storage_end_kwh.to_numpy();x=df.grid_charge_kwh.to_numpy();y=df.pv_charge_kwh.to_numpy();z=df.discharge_kwh.to_numpy();q=df.order_kwh.to_numpy();e=df.emergency_kwh.to_numpy()
 close('storage',s[1:],end[:-1]);close('storage',end,s+.9*(x+y)-z/.9)
 for arr in [x,y,z,q,e,df.received_kwh,df.unused_order_kwh,df.unused_pv_kwh]:assert np.min(arr)>-1e-6
 assert min(s.min(),end.min())>=1200-1e-6 and max(s.max(),end.max())<=10800+1e-6
 assert (x+y).max()<=5000/6+1e-6 and z.max()<=5000/6+1e-6 and not np.any(((x+y)>1e-6)&(z>1e-6))
 close('balance',df.direct_pv_kwh+df.grid_to_load_kwh+z+e,L/6)
 close('balance',df.received_kwh,df.grid_to_load_kwh+x);close('balance',q,df.received_kwh+df.unused_order_kwh)
 close('balance',V/6,df.direct_pv_kwh+y+df.unused_pv_kwh)
 need=np.maximum((L-V)/6,0);surplus=np.maximum((V-L)/6,0);deficit=np.maximum(need-q,0)
 zd=np.minimum.reduce([deficit,np.full(len(s),5000/6),np.maximum(.9*(s-1200),0)])
 ch=np.where(deficit>0,0,np.minimum.reduce([surplus+np.maximum(q-need,0),np.full(len(s),5000/6),np.maximum((10800-s)/.9,0)]))
 close('balance',z,zd);close('balance',e,deficit-zd);close('balance',x+y,ch);close('balance',y,np.minimum(surplus,ch))
 close('fees',df.ordinary_cost,df.price*q);close('fees',df.emergency_cost,5*df.price*e)
 counts['actual']+=len(df)
 return float(np.sum(price[k]*q+5*price[k]*e))
def check_plan(plan,initial,actual_orders):
 l,v,m,q,x,y,z,s=plan.T;net=np.maximum((l-v)/6+m,0);surplus=np.maximum((v-l)/6-m,0)
 close('plan',q,net-z+x);close('plan',s,np.r_[initial,s[:-1]]+.9*(x+y)-z/.9);close('plan',q[:144],actual_orders)
 assert x.min()>-1e-6 and y.min()>-1e-6 and z.min()>-1e-6 and q.min()>-1e-6
 assert max((y-surplus).max(),(z-net).max())<1e-6
 assert (x+y).max()<=5000/6+1e-6 and z.max()<=5000/6+1e-6 and s.min()>=1200-1e-6 and s.max()<=10800+1e-6
 assert not np.any(((x+y)>1e-6)&(z>1e-6));counts['planned']+=len(plan)

bank=np.load(O/'feature_bank.npz')
for var in ['load','pv']:
 for d in range(2,365):
  for h in [0,1]:
   mask=(bank['origins']==d)&(bank['targets']==d+h)
   if mask.any():close('features',bank[var+'_X'][mask],features(var,d,h),1e-7);close('source',bank[var+'_y'][mask],A[var][d+h])
fitlog=[json.loads(t) for t in (O/'fit_log.jsonl').read_text().splitlines()];ridge_res=[]
for f in fitlog:
 d=day(f['cutoff']);mask=(bank['origins']>=max(2,d-56))&(bank['targets']<d);assert mask.sum()==f['n_rows'] and day(f['latest_target_end'])<=d
 if f['model']=='T2':
  X=bank[f['variable']+'_X'][mask];Y=bank[f['variable']+'_y'][mask];close('features',X.mean(0),f['feature_means'],1e-7);Z=(X-f['feature_means'])/f['feature_scales'];b=np.array(f['coefficients_standardized']);rhs=Z.T@(Y-Y.mean());res=np.linalg.norm((Z.T@Z+f['hyperparameter']*np.eye(len(b)))@b-rhs)/max(1,np.linalg.norm(rhs));assert res<1e-7;ridge_res.append(float(res))
 counts['fits']+=1

oldex=pd.read_csv(OLD/'outputs/execution.csv.gz',float_precision='round_trip');oldex=oldex[oldex.phase.isin(['comparison','initialization'])]
newex=pd.read_csv(O/'execution.csv.gz',float_precision='round_trip');pl=pd.read_csv(O/'forecast_plans.csv.gz',float_precision='round_trip')
assert len(newex)==736*144 and len(pl)==736*288
comp=pd.read_csv(O/'comparison.csv').set_index('variant');feb=read(OLD/'outputs/initialization.json')['feb1_initial'];totals={}
warm=oldex[oldex.phase=='initialization'].sort_values(['day','slot']);check_actual(warm,6000);close('storage',warm.storage_end_kwh.iloc[-1],feb)
registry={(x['kind'],x['decision_date']):x for x in map(json.loads,(O/'forecast_registry.jsonl').read_text().splitlines())};model_cache={}
for kind in ['T1','T2','T3','T4']:
 ex=pd.concat([oldex[(oldex.phase=='comparison')&(oldex.variant==kind)],newex[newex.variant==kind]]).sort_values(['day','slot'])
 assert len(ex)==334*144 and not ex.duplicated(['day','slot']).any();close('fees',check_actual(ex,feb),comp.loc[kind,'total_cost'],1e-5)
 ordinary=sum((Decimal(str(r.price))*Decimal(str(r.order_kwh)) for r in ex.itertuples()),Decimal(0));emerg=sum((Decimal(5)*Decimal(str(r.price))*Decimal(str(r.emergency_kwh)) for r in ex.itertuples()),Decimal(0));close('fees',float(ordinary+emerg),comp.loc[kind,'total_cost'],1e-5);totals[kind]={'ordinary':str(ordinary),'emergency':str(emerg),'total':str(ordinary+emerg)}
 for d,g in pl[pl.variant==kind].groupby('day',sort=True):
  g=g.sort_values('horizon_slot');date=g.decision_date.iloc[0]
  if kind in ['T1','T4']:
   L=np.r_[mean('load',d,0,'week',4),mean('load',d,1,'week',4)];V=np.r_[mean('pv',d,0,'recent',7),mean('pv',d,1,'recent',7)]
  else:
   fid=registry[(kind,date)]['fit_id'];forecast=[];fitday=day(fid.split('-',2)[2]);assert fitday<=d and d-fitday<7
   assert (fitday-31)%7==0
   for var in ['load','pv']:
    name=fid+'-'+var+'.joblib';file=O/'models'/name
    if not file.exists():file=OLD/'outputs/models'/name
    if name not in model_cache:model_cache[name]=joblib.load(file)
    obj=model_cache[name];X=np.vstack([features(var,d,0),features(var,d,1)]);sc=obj['scaler'];z=np.maximum(obj['model'].predict(sc.transform(X) if sc else X),0)
    if var=='pv':z*=np.tile(np.any(A['pv'][max(0,d-28):d]>0,axis=0),2)
    forecast.append(z)
   L,V=forecast
  close('forecast',g.load_forecast_kw,L,1e-7);close('forecast',g.pv_forecast_kw,V,1e-7);close('margin',g.risk_allowance_kwh,margin(d) if kind=='T4' else np.zeros(288),1e-7)
  actual=ex[ex.day==d];arr=g[['load_forecast_kw','pv_forecast_kw','risk_allowance_kwh','planned_order_kwh','planned_grid_charge_kwh','planned_pv_charge_kwh','planned_discharge_kwh','planned_storage_end_kwh']].to_numpy();check_plan(arr,actual.storage_start_kwh.iloc[0],actual.order_kwh.to_numpy());counts['forecast_values']+=576
print('annual prediction/physical/accounting check passed',flush=True)

configs=read(R/'validation/summary.json')['configurations'];checks=[]
for cfg in configs:checks.append((R/'validation/schedules'/f'{cfg["name"]}.npz',cfg,31,pd.read_csv(R/'validation/daily_metrics.csv',float_precision='round_trip')))
for phase in ['january','sensitivity']:
 for beta in ([.7,.8,.9] if phase=='january' else [.7,.9]):
  cfg={'name':f'error-decay{int(beta*100)}','q':.7,'risk_decay':beta};checks.append((R/'refinement/schedules'/f'{phase}-{cfg["name"]}.npz',cfg,7 if phase=='january' else 31,pd.read_csv(R/'refinement/daily_metrics.csv',float_precision='round_trip').query('phase==@phase')))
for file,cfg,begin,daily in checks:
 z=np.load(file);days=z['days'];assert np.array_equal(days,np.arange(begin,31 if begin==7 else 365));vals=z['actual'];df=pd.DataFrame(vals.reshape(-1,vals.shape[-1]),columns=z['actual_columns']);df['day']=np.repeat(days,144)
 initial=read(OLD/'outputs/initialization.json')['jan8_initial'] if begin==7 else feb;total=check_actual(df,initial);close('fees',total,daily[daily.variant==cfg['name']].total_cost.sum(),1e-5)
 for i,d in enumerate(days):
  plan=z['plan'][i];n=len(plan);L=np.r_[mean('load',d,0,'week',cfg.get('w',4),cfg.get('forecast_decay')),mean('load',d,1,'week',cfg.get('w',4),cfg.get('forecast_decay'))];V=np.r_[mean('pv',d,0,'recent',cfg.get('p',7),cfg.get('forecast_decay')),mean('pv',d,1,'recent',cfg.get('p',7),cfg.get('forecast_decay'))]
  close('forecast',plan[:,0],L[:n],1e-7);close('forecast',plan[:,1],V[:n],1e-7);M=margin(d,cfg['q'],cfg.get('days',28),cfg.get('group',4),cfg.get('risk_decay')) if cfg['q'] else np.zeros(288);close('margin',plan[:,2],M[:n],1e-7)
  aa=df[df.day==d];check_plan(plan,aa.storage_start_kwh.iloc[0],aa.order_kwh.to_numpy());counts['forecast_values']+=n*2
 print('verified',file.name,flush=True)
solver_calls=0
for folder in ['annual','validation','refinement']:
 rows=[json.loads(x) for x in (R/folder/'solver_checks.jsonl').read_text().splitlines()];solver_calls+=len(rows)
 assert all(x['status']==0 and x['simultaneous_slots']==0 and x['primal_dual_gap']<1e-4 for x in rows)
assert solver_calls==6486
sel=read(R/'refinement/selection.json');assert min(sel['january_cost'],key=sel['january_cost'].get)=='0.7' and sel['chosen_decay']==.7
result={'status':'passed','counts':counts,'maximum_absolute_errors':maximum,'max_ridge_relative_equation_residual':max(ridge_res),'solver_calls_checked':solver_calls,'decimal_annual_totals':totals,'source_previous_output_new_output_hashes':True,'causal_information_and_refit_cadence':True,'separate_load_pv_models':True,'all_daily_orders_locked_and_civil_dates_continuous':True,'new_solves':0,'new_fits':0,'human_review':False,'proves':'Numerical/information and accounting consistency under stated model; not unseen-year generalization.'}
(R/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)
