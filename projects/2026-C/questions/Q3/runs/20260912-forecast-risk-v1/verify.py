"""Independent checks of source-time forecasts, exact quantiles, physical flows and bills."""
from pathlib import Path
from fractions import Fraction
from decimal import Decimal,localcontext
import json,hashlib
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parent;P=R.parents[3];O=R/'outputs'
PREV=P/'questions/Q3/runs/20260912-load-feedback-v1';B=P/'questions/Q3/runs/20260911-four-candidates-v1/outputs'
I=P/'questions/Q3/runs/20260912-final-information-v1/outputs'
read=lambda p:json.loads(Path(p).read_text('utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=read(O/'summary.json');src=dict(np.load(B/'sources.npz'));pv=dict(np.load(I/'forecasts.npz'))
assert s['code_sha256']==sha(R/'run.py') and s['protocol_sha256']==sha(R/'protocol.json')
for manifest in (O/'protected_sources.json',PREV/'outputs/protected_sources.json'):
 for p,h in read(manifest).items():assert sha(P/p)==h,p
maximum={};counts=dict(load_families=0,preparation_groups=0,actual_intervals=0)
def ck(name,a,b,tol=1e-7):
 a=np.asarray(a);b=np.asarray(b);assert a.shape==b.shape,(name,a.shape,b.shape)
 assert np.array_equal(np.isnan(a),np.isnan(b)),name
 mask=np.isfinite(a)&np.isfinite(b);err=float(abs(a[mask]-b[mask]).max()) if mask.any() else 0.
 maximum[name]=max(maximum.get(name,0),err);assert err<=tol,(name,err)
def D(x):return Decimal(str(float(x)))
families={x['family'] for x in s['candidates']};loads={}
for family in families:
 cache=dict(np.load(O/f'load_{family}.npz'));mid=np.empty((365,288));weeks={'W1':1,'W2':2,'W4':4,'EW4':4}[family]
 for d in range(365):
  for h in (0,1):
   indices=[d+h-7*j for j in range(1,weeks+1) if 0<=d+h-7*j<d]
   weights=np.array([(.5 if family=='EW4' else 1.)**j for j in range(len(indices))])
   if not indices:indices=list(range(max(0,d-7),d));weights=np.ones(len(indices))
   for k in range(144):
    pairs=[(src['actual'][day*144+k,0],w) for day,w in zip(indices,weights) if np.isfinite(src['actual'][day*144+k,0])]
    assert all(day*144+143<d*144 for day in indices)
    mid[d,h*144+k]=sum(x*w for x,w in pairs)/sum(w for x,w in pairs) if pairs else src['reference'][k,0]
 ck('midnight_forecast',mid,cache['midnight'],1e-9)
 res=src['actual'][:365*144,0].reshape(365,144)-mid[:,:144];load=np.full((1460,288),np.nan)
 for d in range(365):
  for a,slot in enumerate((0,36,72,108)):
   b=d*4+a;n=288-slot;load[b,:n]=mid[d,slot:]
   if not slot:continue
   observed=np.nanmean(res[d,:slot]);ck('observed_bias',np.asarray(observed),cache['observed'][d,a],1e-9)
   for g in range(slot//18,8):
    pairs=[]
    for j in range(max(0,d-28),d):
     x=np.nanmean(res[j,:slot]);y=np.mean(res[j,g*18:(g+1)*18])
     if np.isfinite(x) and np.isfinite(y):pairs.append((x,y))
    den=sum(x*x for x,y in pairs);coef=max(0.,min(1.,sum(x*y for x,y in pairs)/den)) if len(pairs)>=7 and den>1e-12 else 0.
    ck('learned_coefficient',np.asarray(coef),cache['theta'][d,a,g],1e-10)
    assert len(pairs)==cache['count'][d,a,g]
    ix=g*18-slot;load[b,ix:ix+18]=np.maximum(0,load[b,ix:ix+18]+coef*observed)
 ck('updated_load',load,cache['load'],1e-8);loads[family]=cache['load'];counts['load_families']+=1

records=s['candidates']+([s['no_new_control'],s['zero_control']] if s['no_new_control'] else [])
baseline_df=pd.read_csv(PREV/'outputs/strategies/LEARN_PREFIX.daily.csv',float_precision='round_trip');analyses={};frames={};groups=None;checked_errors=set()
for rec in records:
 label=rec['label'];family=rec['family'];key=family+'_'+rec['pvkey'];errors=dict(np.load(O/f'errors_{key}.npz'));rr,tt,ee,kind=(errors[k] for k in ('release','target','error','kind'))
 if key not in checked_errors:
  expected=((src['actual'][tt,0]-src['actual'][tt,1])-(loads[family][rr//36,tt-rr]-pv[rec['pvkey']][rr//36,tt-rr]))/6
  ck('own_errors',expected,ee,1e-10);checked_errors.add(key)
 if groups is None:
  groups=[]
  for b,r in enumerate(src['release']):
   n=288-r%144;t=r+np.arange(n);past=np.flatnonzero((rr>=r-4032)&(rr<r)&(tt<r)&(rr%144==r%144))
   for typ in (0,1):
    candidates=past[kind[past]==typ]
    for g in range(8):
     dest=np.flatnonzero((t%144//18==g)&((np.arange(n)>=144)==bool(typ)))
     if not len(dest):continue
     ids=candidates[tt[candidates]%144//18==g]
     if len(ids)<24:ids=candidates
     groups.append((b,r,dest,ids))
 saved_margin=np.load(O/f'strategies/{label}.margin.npz')['values'];q=Fraction(str(rec['q']))
 for b,r,dest,ids in groups:
  if len(ids)<24:value=0.
  else:
   ids=ids[np.argsort(ee[ids],kind='stable')];ages=(r-1)//144-tt[ids]//144;ma=int(ages.max());weights=[7**int(a)*10**(ma-int(a)) for a in ages]
   total=sum(weights);acc=0;value=None
   for i,w in enumerate(weights):
    old=acc;acc+=w
    if acc*q.denominator>=total*q.numerator:
     assert old*q.denominator<total*q.numerator;value=max(0.,float(ee[ids[i]]));break
  ck('exact_quantile',saved_margin[b,dest],np.full(len(dest),value),1e-10);counts['preparation_groups']+=1
 tr=dict(np.load(O/f'strategies/{label}.npz'));df=pd.read_csv(O/f'strategies/{label}.daily.csv',float_precision='round_trip')
 assert np.array_equal(tr['days'],np.arange(31,365));ck('zero_order',tr['q0'],tr['versions'][:,0],0)
 for a,slot in enumerate((0,36,72,108)):
  if a:ck('prefix_locked',tr['versions'][:,a,:slot],tr['versions'][:,a-1,:slot],0)
  if rec['zero']:ck('all_day_locked',tr['versions'][:,a],tr['q0'],0)
 x=tr['execution'].reshape(-1,12);qfinal=tr['versions'][:,3].ravel();truth=src['actual'][31*144:365*144]/6
 start=x[:,0];end=x[:,1];ck('initial',start[:1],np.array([8592.693560925925]),0);ck('stock_link',start[1:],end[:-1],0)
 direct=np.minimum(truth[:,0],truth[:,1]);need=truth[:,0]-direct;sur=truth[:,1]-direct;deficit=need>qfinal
 z=np.where(deficit,np.minimum.reduce([need-qfinal,np.full(len(x),5000/6),np.maximum(0,.9*(start-1200))]),0)
 e=np.where(deficit,np.maximum(0,need-qfinal-z),0)
 charge=np.where(deficit,0,np.minimum.reduce([sur+qfinal-need,np.full(len(x),5000/6),np.maximum(0,(10800-start)/.9)]))
 y=np.minimum(sur,charge);grid=charge-y;received=np.where(deficit,qfinal,need+grid)
 rebuilt=np.column_stack([start,start+.9*charge-z/.9,received,received-grid,direct,grid,y,z,e,np.maximum(0,qfinal-received),np.maximum(0,sur-y),truth[:,0]])
 ck('physical_execution',x,rebuilt,1e-6);assert end.min()>=1200-1e-7 and end.max()<=10800+1e-7
 ck('load_balance',received-grid+direct+z+e,truth[:,0]);ck('decision_stock',tr['decision_storage'],x[:,0].reshape(334,144)[:,[0,36,72,108]],0)
 total=Decimal(0)
 for i in range(334):
  qday=qfinal.reshape(334,144)[i];delta=qday-tr['q0'][i];eday=e.reshape(334,144)[i]
  with localcontext() as c:
   c.prec=40
   normal=sum((D(p)*D(v) for p,v in zip(src['price'],qday)),Decimal(0));adj=sum((Decimal('.5')*D(p)*abs(D(v)) for p,v in zip(src['price'],delta)),Decimal(0));em=sum((Decimal(5)*D(p)*D(v) for p,v in zip(src['price'],eday)),Decimal(0))
  cost=normal+adj+em;total+=cost;ck('daily_bill',np.array([float(normal),float(adj),float(em),float(cost)]),df.loc[i,['normal_cost','adjustment_cost','emergency_cost','total_cost']].to_numpy(float),1e-6)
 ck('total_bill',np.asarray(float(total)),np.asarray(rec['total_cost']),1e-5);ck('final_stock',end[-1:],np.array([rec['final']]),0)
 solver=pd.read_csv(O/f'strategies/{label}.solver.csv');assert len(solver)==(334 if rec['zero'] else 1336) and solver.residual.max()<1e-6 and solver.dual_gap.max()<1e-4 and solver.simultaneous.sum()==0
 diff=baseline_df.total_cost-df.total_cost;monthly=diff.groupby(pd.to_datetime(df.date).dt.month).sum();flags=e>1e-6;switch=np.flatnonzero(np.diff(np.r_[False,flags,False].astype(int)))
 analyses[label]=dict(saving=s['baseline']['total_cost']-rec['total_cost'],saving_percent=100*(s['baseline']['total_cost']-rec['total_cost'])/s['baseline']['total_cost'],cheaper_days=int((diff>1e-6).sum()),costlier_days=int((diff< -1e-6).sum()),monthly_saving={str(k):float(v) for k,v in monthly.items()},max_increase=float(-diff.min()),max_increase_date=str(df.loc[diff.idxmin(),'date']),max_saving=float(diff.max()),max_saving_date=str(df.loc[diff.idxmax(),'date']),max_emergency_interval=float(e.max()),max_emergency_day=float(e.reshape(334,144).sum(1).max()),longest_emergency_minutes=int((switch[1::2]-switch[::2]).max())*10 if len(switch) else 0,terminal_reference_saving=s['baseline']['total_cost']-rec['total_cost']+.9*src['price'][0]*(rec['final']-s['baseline']['final']))
 counts['actual_intervals']+=len(x);frames[label]=df;print(json.dumps(dict(verified=label,cost=rec['total_cost']),ensure_ascii=False),flush=True)

bound_result=None
if s['hindsight']['status']=='solved_relaxation':
 h=dict(np.load(O/'hindsight.npz'));x,y,z,stock=h['variables'];truth=src['actual'][31*144:365*144]/6;net=np.maximum(truth[:,0]-truth[:,1],0);sur=np.maximum(truth[:,1]-truth[:,0],0);p=np.tile(src['price'],334)
 before=np.r_[8592.693560925925,stock[:-1]];ck('bound_stock',stock,before+.9*(x+y)-z/.9,1e-6)
 assert min(x.min(),y.min(),z.min())>=-1e-7 and (x+y).max()<=5000/6+1e-7 and z.max()<=5000/6+1e-7
 assert (y-sur).max()<=1e-7 and (z-net).max()<=1e-7 and stock.min()>=1200-1e-7 and stock.max()<=10800+1e-7
 cost=float(p@(net-z+x));ck('bound_bill',np.asarray(cost),np.asarray(s['hindsight']['cost']),1e-5)
 # Validate dual feasibility directly for the four variable blocks (x,y,z,S).
 n=len(x);eq=h['dual_equal'];ub=h['dual_charge'];dl=h['dual_lower'];du=h['dual_upper']
 c=np.r_[p,np.zeros(n),-p,np.zeros(n)]
 station=np.r_[-.9*eq+ub,-.9*eq+ub,eq/.9,eq-np.r_[eq[1:],0]]+dl+du
 ck('bound_dual_stationarity',station,c,1e-7)
 assert ub.max()<1e-7 and du.max()<1e-7 and dl.min()>-1e-7
 hi=np.r_[np.full(n,5000/6),np.minimum(sur,5000/6),np.minimum(net,5000/6),np.full(n,10800.)];lo=np.r_[np.zeros(3*n),np.full(n,1200.)]
 dual=float(8592.693560925925*eq[0]+5000/6*ub.sum()+lo@dl+hi@du+p@net)
 ck('bound_dual_value',np.asarray(dual),np.asarray(s['hindsight']['dual_lower_bound']),1e-5)
 bound_result=dict(cost=cost,dual_lower_bound=dual,room_from_baseline=s['baseline']['total_cost']-dual,room_from_winner=s['winner']['total_cost']-dual,not_implementable=True)
info=None
if s['no_new_control']:
 no=s['no_new_control'];full=s['winner'];zero=s['zero_control'];difference=frames[no['label']].total_cost-frames[full['label']].total_cost
 info=dict(zero_cost=zero['total_cost'],no_new_cost=no['total_cost'],full_cost=full['total_cost'],new_PV_saving=no['total_cost']-full['total_cost'],new_PV_saving_percent=100*(no['total_cost']-full['total_cost'])/no['total_cost'],cheaper_days=int((difference>1e-6).sum()),costlier_days=int((difference< -1e-6).sum()),final_inventory_difference=full['final']-no['final'])
out=dict(status='verified_by_AI_not_human_approval',counts=counts,max_errors=maximum,analyses=analyses,hindsight=bound_result,information=info,new_solver_calls=0,code_sha256=sha(__file__))
(O/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False))
