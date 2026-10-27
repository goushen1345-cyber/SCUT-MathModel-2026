"""Independent readback: causal price features, ridge equations, dispatch and bills."""
from pathlib import Path
from decimal import Decimal,localcontext
import os,json,hashlib
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import numpy as np
import pandas as pd
import joblib
R=Path(__file__).resolve().parent;P=R.parents[3];O=R/'outputs'
OLD=P/'questions/Q4/runs/20260912-three-candidates-v1'
DEP=P/'questions/Q4/runs/20260912-selected-deepening-v1'
UP=P/'questions/Q3/runs/20260912-forecast-risk-v1'
read=lambda p:json.loads(Path(p).read_text('utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
maxima={};counts=dict(strategies=0,intervals=0,price_models=0,price_forecasts=0)
def ck(name,a,b,tol=1e-7):
 a=np.asarray(a);b=np.asarray(b);assert a.shape==b.shape,(name,a.shape,b.shape)
 assert np.array_equal(np.isnan(a),np.isnan(b)),name
 mask=np.isfinite(a)&np.isfinite(b);err=float(abs(a[mask]-b[mask]).max()) if mask.any() else 0.
 maxima[name]=max(maxima.get(name,0),err);assert err<=tol,(name,err,tol)
protocol=read(R/'protocol.json');s=read(O/'summary.json')
assert sha(R/'run.py')==s['code_sha256'] and sha(R/'protocol.json')==s['protocol_sha256']
for rel,h in protocol['source_sha256'].items():assert sha(P/rel)==h,rel
assert read(UP/'outputs/verification.json')['status']=='verified_by_AI_not_human_approval'
for mp in [UP/'outputs/protected_sources.json',P/'questions/Q3/runs/20260912-load-feedback-v1/outputs/protected_sources.json']:
 for rel,h in read(mp).items():assert sha(P/rel)==h,rel
src=dict(np.load(O/'supply.npz'));oldsrc=dict(np.load(OLD/'outputs/supply_inputs.npz'))
ck('transfer_load',src['load'],np.load(UP/'outputs/load_EW4.npz')['load'],0)
ck('transfer_pv',src['pv'],oldsrc['q3_pv'],0);ck('actual_same',src['actual'],oldsrc['q3_actual'],0)
pf=pd.read_csv(P/'data/prepared-v1/actual_price.csv',float_precision='round_trip')
pf['day']=(pd.to_datetime(pf.source_date)-pd.Timestamp('2025-01-01')).dt.days;pf['slot']=pf.source_minute.astype(int)%1440//10
assert len(pf)==365*144 and not pf.duplicated(['day','slot']).any()
price=pf.pivot(index='day',columns='slot',values='price_yuan_per_kwh').reindex(index=range(365),columns=range(144)).to_numpy()
ck('mapped_actual_price',src['price'],price,0)
rf=pd.read_csv(P/'data/prepared-v1/day_reference.csv',float_precision='round_trip');rf['slot']=rf.source_minute.astype(int)%1440//10
base=rf.sort_values('slot').price_yuan_per_kwh.to_numpy();ck('reference_price',src['reference_price'],base,0)

# Reconstruct all features without importing the research implementation.
feature_names=['attachment1_base','matching_weekday_median4','recent7_median','lag7_price','predicted_net_load_1000kw','current_day_level','current_level_decay6h','last_residual_decay1h','lead_hours','season_sin','season_cos',*[f'weekday_{j}' for j in range(7)],'release_fraction']
curve_cache={};matrix_cache={}
def curve(d,t):
 key=(d,t)
 if key not in curve_cache:
  ds=[t-7*j for j in range(1,5) if 0<=t-7*j<d]
  if not ds:ds=list(range(max(0,d-7),d))
  assert all(j<d for j in ds)
  curve_cache[key]=np.median(price[ds],axis=0) if ds else base.copy()
 return curve_cache[key]
def features(d,r):
 key=(d,r)
 if key in matrix_cache:return matrix_cache[key]
 n=288-r;b=d*4+r//36;target=d*144+r+np.arange(n);td=target//144;ts=target%144
 match=np.empty(n);recent=np.empty(n);lag=np.empty(n)
 for t in np.unique(td):
  ix=td==t;match[ix]=curve(d,int(t))[ts[ix]]
  ds=list(range(max(0,d-7),d));recent[ix]=np.median(price[ds][:,ts[ix]],axis=0) if ds else base[ts[ix]]
  lag[ix]=price[t-7,ts[ix]] if 0<=t-7<d else match[ix]
 if r:
  past=price[d,:r]-curve(d,d)[:r];level=float(np.median(past));last=float(past[-1])
 else:level=last=0.
 lead=np.arange(n)/6;sameday=td==d;date=pd.Timestamp('2025-01-01')+pd.to_timedelta(td,unit='D');year_day=np.asarray(date.dayofyear);weekday=np.asarray(date.dayofweek)
 x=np.column_stack([base[ts],match,recent,lag,(src['load'][b,:n]-src['pv'][b,:n])/1000,level*sameday,level*np.exp(-lead/6)*sameday,last*np.exp(-lead)*sameday,lead,np.sin(2*np.pi*year_day/365),np.cos(2*np.pi*year_day/365),*[(weekday==j).astype(float) for j in range(7)],np.full(n,r/108)])
 assert x.shape==(n,19) and np.isfinite(x).all()
 matrix_cache[key]=(target,x);return target,x
fitlog=[json.loads(x) for x in (O/'price_fit_log.jsonl').read_text('utf-8').splitlines()]
assert len(fitlog)==49==s['price_fits'];models={}
for rec in fitlog:
 cutoff=rec['cutoff_day'];path=R/rec['model_path'];assert sha(path)==rec['model_sha256']
 payload=joblib.load(path);model,scaler=payload['model'],payload['scaler'];assert payload['features']==feature_names and model.alpha==10
 xs=[];ys=[]
 for d in range(max(1,cutoff-56),cutoff):
  for r in (0,36,72,108):
   tt,x=features(d,r);valid=(tt<cutoff*144)&(tt<365*144)
   if valid.any():xs.append(x[valid]);ys.append(price.ravel()[tt[valid]])
 x=np.vstack(xs);y=np.concatenate(ys);assert len(y)==rec['training_rows']
 mu=x.mean(0);std=x.std(0);std[std<1e-12]=1
 ck('ridge_training_mean',mu,scaler.mean_,1e-8);ck('ridge_training_scale',std,scaler.scale_,1e-8)
 z=(x-scaler.mean_)/scaler.scale_;res=z@model.coef_+model.intercept_-y
 gradient=z.T@res+10*model.coef_;ck('ridge_normal_equations',gradient,np.zeros(19),1e-5);ck('ridge_intercept_equation',np.asarray(res.sum()),np.asarray(0.),1e-5)
 models[cutoff]=(model.coef_.copy(),float(model.intercept_),scaler.mean_.copy(),scaler.scale_.copy());counts['price_models']+=1
pred=np.load(O/'prices.npz')['values'];rebuild=np.full_like(pred,np.nan)
for d in range(31,365):
 cutoff=d//7*7;co,inter,mu,std=models[cutoff]
 for a,r in enumerate((0,36,72,108)):
  tt,x=features(d,r);assert cutoff<=d
  rebuild[d*4+a,:len(tt)]=np.maximum((x-mu)/std@co+inter,.001);counts['price_forecasts']+=1
ck('price_predictions',pred,rebuild,1e-10)
forecastlog=[json.loads(x) for x in (O/'price_forecast_log.jsonl').read_text('utf-8').splitlines()]
assert len(forecastlog)==1336
for rec in forecastlog:
 d=rec['decision_day'];r=rec['release_slot'];v=pred[d*4+r//36,:288-r]
 assert rec['known_price_intervals_today']==r and rec['fit_cutoff_day']==d//7*7<=d
 assert hashlib.sha256(v.astype(np.float64).tobytes()).hexdigest()==rec['sha256']
print(json.dumps(dict(price_models_verified=49,price_predictions_verified=1336)),flush=True)

oldfc=dict(np.load(OLD/'outputs/price_forecasts.npz'));oldpred=oldfc['q43'][list(oldfc['candidates']).index('P2')]
baseline_df=pd.read_csv(DEP/'outputs/strategies/Q4-3-P2-full.daily.csv',float_precision='round_trip')
analyses={};truth=src['actual'][31*144:365*144]/6;high=price[31:]>=np.quantile(price[31:],.95)
for rec in [s['baseline'],*s['candidates']]:
 label=rec['label'];tr=dict(np.load(O/f'strategies/{label}.npz'));df=pd.read_csv(O/f'strategies/{label}.daily.csv',float_precision='round_trip')
 assert len(df)==334 and list(df.day)==list(range(31,365)) and np.array_equal(tr['days'],np.arange(31,365))
 ck('zero_order',tr['q0'],tr['versions'][:,0],0)
 for a in (1,2,3):ck('locked_prefix',tr['versions'][:,a,:a*36],tr['versions'][:,a-1,:a*36],0)
 if label=='OLD_P2_REPLAY':
  oldtr=dict(np.load(DEP/'outputs/strategies/Q4-3-P2-full.npz'))
  for k in ('q0','versions','execution'):ck('baseline_'+k,tr[k],oldtr[k],1e-7)
 x=tr['execution'].reshape(-1,12);q=tr['versions'][:,-1].ravel();assert q.min()>=0 and np.isfinite(x).all()
 start=x[:,0];end=x[:,1];ck('initial',start[:1],np.array([protocol['initial']]),0);ck('cross_interval_inventory',start[1:],end[:-1],0)
 direct=np.minimum(truth[:,0],truth[:,1]);need=truth[:,0]-direct;sur=truth[:,1]-direct;deficit=need>q
 discharge=np.where(deficit,np.minimum.reduce([need-q,np.full(len(q),5000/6),np.maximum(.9*(start-1200),0)]),0)
 emergency=np.where(deficit,np.maximum(need-q-discharge,0),0)
 charge=np.where(deficit,0,np.minimum.reduce([sur+q-need,np.full(len(q),5000/6),np.maximum((10800-start)/.9,0)]))
 pc=np.minimum(sur,charge);gc=charge-pc;received=np.where(deficit,q,need+gc)
 expected=np.column_stack([start,start+.9*charge-discharge/.9,received,received-gc,direct,gc,pc,discharge,emergency,np.maximum(q-received,0),np.maximum(sur-pc,0),truth[:,0]])
 ck('physical_execution',x,expected,1e-6);ck('load_balance',received-gc+direct+discharge+emergency,truth[:,0],1e-7)
 assert end.min()>=1200-1e-7 and end.max()<=10800+1e-7
 ck('decision_inventory',tr['decision_storage'],tr['execution'][:,[0,36,72,108],0],0)
 price2=price[31:];orders=q.reshape(334,144);em=emergency.reshape(334,144);delta=orders-tr['q0'];energy=(price2*orders).sum(1);adjust=.5*(price2*abs(delta)).sum(1);ec=5*(price2*em).sum(1)
 for key,val in [('ordinary_cost',energy),('adjustment_cost',adjust),('emergency_cost',ec),('total_cost',energy+adjust+ec)]:ck('daily_'+key,df[key].to_numpy(),val,1e-6)
 with localcontext() as ctx:
  ctx.prec=45;total=Decimal(0)
  for p,qo,dq,e in zip(price2.ravel(),q,delta.ravel(),emergency):total+=Decimal(str(float(p)))*(Decimal(str(float(qo)))+Decimal('.5')*abs(Decimal(str(float(dq))))+5*Decimal(str(float(e))))
 ck('total_bill',np.asarray(float(total)),np.asarray(rec['total_cost']),1e-5);ck('final_inventory',end[-1:],np.array([rec['final']]),0)
 fc=oldpred if label=='OLD_P2_REPLAY' else pred;pr=np.concatenate([fc[d*4+a,:36] for d in range(31,365) for a in range(4)]).reshape(334,144);err=pr-price2
 ck('price_mae',np.asarray(abs(err).mean()),np.asarray(rec['price_mae']),1e-10);ck('high_price_mae',np.asarray(abs(err)[high].mean()),np.asarray(rec['top5_price_mae']),1e-10)
 diff=baseline_df.total_cost-df.total_cost;monthly=diff.groupby(pd.to_datetime(df.date).dt.month).sum();flags=emergency>1e-6;switch=np.flatnonzero(np.diff(np.r_[False,flags,False].astype(int)))
 saving=s['baseline']['total_cost']-rec['total_cost'];stockdiff=rec['final']-s['baseline']['final']
 analyses[label]=dict(saving=saving,saving_percent=100*saving/s['baseline']['total_cost'],cheaper_days=int((diff>1e-6).sum()),costlier_days=int((diff< -1e-6).sum()),monthly_saving={str(k):float(v) for k,v in monthly.items()},max_cost_increase=float(-diff.min()),max_cost_increase_date=str(df.loc[diff.idxmin(),'date']),max_saving=float(diff.max()),max_saving_date=str(df.loc[diff.idxmax(),'date']),final_inventory_difference=stockdiff,terminal_reference_saving=saving+.9*base[0]*stockdiff,terminal_savings_range=[saving+.9*float(v)*stockdiff for v in [np.quantile(price2,.05),np.median(price2),np.quantile(price2,.95)]],high_price_emergency_kwh=float(em[high].sum()),max_interval_emergency_kwh=float(emergency.max()),longest_emergency_minutes=int((switch[1::2]-switch[::2]).max())*10 if len(switch) else 0)
 counts['strategies']+=1;counts['intervals']+=len(x);print(json.dumps(dict(verified=label,cost=rec['total_cost'])),flush=True)
solver=[json.loads(x) for x in (O/'solver_checks.jsonl').read_text('utf-8').splitlines()]
assert len(solver)==8016==s['lp_calls'] and all(x['status']==0 and x['simultaneous']==0 for x in solver)
assert max(x['residual'] for x in solver)<1e-6 and max(x['dual_gap'] for x in solver)<1e-4
counts['solver_records']=len(solver)
for rel,h in protocol['source_sha256'].items():assert sha(P/rel)==h,rel
out=dict(status='verified_by_independent_AI_program_not_human_approval',counts=counts,max_errors=maxima,analyses=analyses,source_and_Q3_verified_cache_hashes_unchanged=True,scope='No new fit or solver calls; independently reconstruct features and check Ridge normal equations and final trajectories. Reused Q3 predictions/quantiles retain prior independent verification.',code_sha256=sha(__file__))
(O/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
print(json.dumps(dict(verification_complete=True,counts=counts,max_errors=maxima),ensure_ascii=False),flush=True)
