"""Recency-sensitive weekday loads, own residual preparation and a hindsight bound."""
from pathlib import Path
import os,json,time,hashlib,importlib.util
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix,diags,hstack,vstack,eye
R=Path(__file__).resolve().parent;P=R.parents[3];O=R/'outputs';O.mkdir(exist_ok=True)
PREV=P/'questions/Q3/runs/20260912-load-feedback-v1';BASE=P/'questions/Q3/runs/20260911-four-candidates-v1/outputs'
spec=importlib.util.spec_from_file_location('prev',PREV/'run.py');prev=importlib.util.module_from_spec(spec);spec.loader.exec_module(prev)
src=prev.src;orig=prev.fc;pv=prev.old_info;deep=prev.deep;base=prev.base
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def event(**v):print(json.dumps(v,ensure_ascii=False),flush=True)
class Budget:
 def __init__(self):self.calls=0;self.start=time.perf_counter()
 def check(self):assert self.calls<=15000 and time.perf_counter()-self.start<1800
budget=Budget();load_cache={};error_cache={};group_cache=None

def midnight(family):
 if family=='W4':return orig['L'].copy()
 weeks=1 if family=='W1' else 2 if family=='W2' else 4
 decay=.5 if family=='EW4' else 1.
 L=np.empty((365,288))
 for d in range(365):
  for h in (0,1):
   ds=[d+h-7*j for j in range(1,weeks+1) if 0<=d+h-7*j<d]
   if not ds:ds=list(range(max(0,d-7),d));weights=np.ones(len(ds))
   else:weights=decay**np.arange(len(ds))
   if not ds:L[d,h*144:(h+1)*144]=src['reference'][:,0];continue
   z=src['actual'][np.asarray(ds)[:,None]*144+np.arange(144),0];valid=np.isfinite(z)
   den=(weights[:,None]*valid).sum(0);num=(weights[:,None]*np.nan_to_num(z)).sum(0)
   L[d,h*144:(h+1)*144]=np.divide(num,den,out=src['reference'][:,0].copy(),where=den>0)
 return L

def prepare_load(family):
 if family not in load_cache:
  L=midnight(family);prev.fc=dict(orig,L=L)
  load,theta,obs,count=prev.make_load('LEARN_PREFIX',1.)
  load_cache[family]=load
  np.savez_compressed(O/f'load_{family}.npz',midnight=L,load=load,theta=theta,observed=obs,count=count)
 return load_cache[family]

def get_errors(family,pvkey):
 key=family+'_'+pvkey
 if key not in error_cache:
  err=prev.errors_for(prepare_load(family),pv[pvkey]);error_cache[key]=err
  np.savez_compressed(O/f'errors_{key}.npz',**err)
 return error_cache[key]

def group_index(err):
 global group_cache
 if group_cache is not None:return group_cache
 rr,tt,kind=(err[k] for k in ('release','target','kind'));bank=[]
 for b,r in enumerate(src['release']):
  n=288-r%144;t=r+np.arange(n);pool=np.flatnonzero((rr>=r-4032)&(rr<r)&(tt+1<=r)&(rr%144==r%144))
  for typ in (0,1):
   same=pool[kind[pool]==typ]
   for g in range(8):
    dest=np.flatnonzero((t%144//18==g)&((np.arange(n)>=144)==bool(typ)))
    if not len(dest):continue
    ids=same[tt[same]%144//18==g];fallback=0
    if len(ids)<24:ids=same;fallback=1
    bank.append((b,typ,g,dest,ids,(r-1)//144-tt[ids]//144,fallback))
 group_cache=bank;return bank

def quantile(values,ages,q):
 from fractions import Fraction
 order=np.argsort(values,kind='stable');values=values[order];ages=ages[order];m=int(ages.max())
 iw=[7**a*10**(m-a) for a in range(m+1)];hist=np.bincount(ages,minlength=m+1)
 total=sum(int(h)*w for h,w in zip(hist,iw));f=Fraction(str(q))
 cdf=np.cumsum(.7**ages);k=min(len(values)-1,int(np.searchsorted(cdf/cdf[-1],q)))
 histpre=np.bincount(ages[:k+1],minlength=m+1);acc=sum(int(h)*w for h,w in zip(histpre,iw))
 while k>0 and f.denominator*(acc-iw[int(ages[k])])>=f.numerator*total:acc-=iw[int(ages[k])];k-=1
 while f.denominator*acc<f.numerator*total:k+=1;acc+=iw[int(ages[k])]
 return max(0.,float(values[k]))

def margin_for(family,pvkey,q):
 err=get_errors(family,pvkey);bank=group_index(err);out=np.full((1460,288),np.nan);meta=[]
 for b,typ,g,dest,ids,ages,fallback in bank:
  value=quantile(err['error'][ids],ages,q) if len(ids)>=24 else 0.
  out[b,dest]=value;meta.append((b,typ,g,len(ids),fallback))
 return out,np.asarray(meta)

def run_case(family,q=.6,pvkey='full',zero=False):
 label=f'{family}_Q{int(round(q*100)):02d}_{pvkey}'+('_ZERO' if zero else '')
 folder=O/'strategies';folder.mkdir(exist_ok=True)
 if (folder/f'{label}.summary.json').exists():return json.loads((folder/f'{label}.summary.json').read_text('utf-8'))
 load=prepare_load(family);margin,meta=margin_for(family,pvkey,q);np.savez_compressed(folder/f'{label}.margin.npz',values=margin,meta=meta)
 planner=deep.Planner(src['price'],budget);state=8592.693560925925;days=np.arange(31,365)
 q0=np.empty((334,144));versions=np.empty((334,4,144));execution=np.empty((334,144,12));states=np.empty((334,4));checks=[];daily=[]
 for i,d in enumerate(days):
  initial=state;order=np.zeros(144)
  for a,slot in enumerate((0,36,72,108)):
   b=d*4+a;n=288-slot;states[i,a]=state
   if a==0 or not zero:
    plan,ck=planner.solve(load[b,:n],pv[pvkey][b,:n],state,margin[b,:n],slot,None if a==0 else q0[i,slot:])
    checks.append(dict(ck,day=int(d),release=a));order[slot:]=np.maximum(0,plan[6,:144-slot])
   if a==0:q0[i]=order.copy()
   versions[i,a]=order;truth=src['actual'][d*144+slot:d*144+slot+36]
   block,state=base.execute_block(truth[:,0],truth[:,1],order[slot:slot+36],state);execution[i,slot:slot+36]=block
  price=src['price'];delta=order-q0[i];normal=float(price@order);adjust=float(.5*price@abs(delta));emergency=float(5*price@execution[i,:,8])
  daily.append(dict(label=label,date=base.daystr(d),initial=initial,final=state,normal_cost=normal,adjustment_cost=adjust,ordinary_cost=normal+adjust,emergency_cost=emergency,total_cost=normal+adjust+emergency,
   emergency_kwh=float(execution[i,:,8].sum()),unused_order_kwh=float(execution[i,:,9].sum()),unused_pv_kwh=float(execution[i,:,10].sum())))
  if (i+1)%100==0:event(phase=label,days=i+1,lp_calls=budget.calls)
 df=pd.DataFrame(daily);df.to_csv(folder/f'{label}.daily.csv',index=False,float_format='%.17g',encoding='utf-8-sig')
 np.savez_compressed(folder/f'{label}.npz',days=days,q0=q0,versions=versions,execution=execution,decision_storage=states)
 pd.DataFrame(checks).to_csv(folder/f'{label}.solver.csv',index=False,float_format='%.17g')
 sums={k:float(df[k].sum()) for k in ('normal_cost','adjustment_cost','ordinary_cost','emergency_cost','total_cost','emergency_kwh','unused_order_kwh','unused_pv_kwh')}
 result=dict(sums,label=label,family=family,q=q,pvkey=pvkey,zero=zero,initial=8592.693560925925,final=state,emergency_days=int((df.emergency_kwh>1e-6).sum()),lp_calls=len(checks),max_residual=max(x['residual'] for x in checks),max_dual_gap=max(x['dual_gap'] for x in checks))
 dump(folder/f'{label}.summary.json',result);event(phase='complete',label=label,cost=result['total_cost'],emergency=result['emergency_cost']);return result

def hindsight_bound():
 truth=src['actual'][31*144:365*144];n=len(truth);price=np.tile(src['price'],334);net=np.maximum((truth[:,0]-truth[:,1])/6,0);sur=np.maximum((truth[:,1]-truth[:,0])/6,0)
 ident=eye(n,format='csr');storage=diags([np.ones(n),-np.ones(n-1)],[0,-1],shape=(n,n),format='csr')
 eq=hstack([-.9*ident,-.9*ident,ident/.9,storage],format='csr');ub=hstack([ident,ident,0*ident,0*ident],format='csr')
 rhs=np.zeros(n);rhs[0]=8592.693560925925;c=np.r_[price,np.zeros(n),-price,np.zeros(n)]
 lo=np.r_[np.zeros(3*n),np.full(n,1200.)];hi=np.r_[np.full(n,5000/6),np.minimum(sur,5000/6),np.minimum(net,5000/6),np.full(n,10800.)]
 start=time.perf_counter();ans=linprog(c,A_eq=eq,b_eq=rhs,A_ub=ub,b_ub=np.full(n,5000/6),bounds=np.c_[lo,hi],method='highs',options={'time_limit':180.})
 if not ans.success:
  out=dict(status='not_certified',message=ans.message,elapsed=time.perf_counter()-start);dump(O/'hindsight.json',out);return out
 dual=rhs@ans.eqlin.marginals+np.full(n,5000/6)@ans.ineqlin.marginals+lo@ans.lower.marginals+hi@ans.upper.marginals
 residual=max(float(abs(eq@ans.x-rhs).max()),float((ub@ans.x-5000/6).max()),float((lo-ans.x).max()),float((ans.x-hi).max()))
 assert residual<1e-6 and abs(ans.fun-dual)<.01
 np.savez_compressed(O/'hindsight.npz',variables=ans.x.reshape(4,n),dual_equal=ans.eqlin.marginals,dual_charge=ans.ineqlin.marginals,dual_lower=ans.lower.marginals,dual_upper=ans.upper.marginals)
 out=dict(status='solved_relaxation',cost=float(ans.fun+price@net),dual_lower_bound=float(dual+price@net),duality_gap=float(abs(ans.fun-dual)),residual=residual,final=float(ans.x[-1]),elapsed=time.perf_counter()-start,meaning='omniscient all-horizon ordinary-price physical relaxation; not executable and not future-leaking research candidate')
 dump(O/'hindsight.json',out);event(phase='hindsight_bound',**out);return out

def main():
 protected=[BASE/'sources.npz',BASE/'forecasts.npz',PREV/'run.py',PREV/'verify.py',PREV/'outputs/verification.json',PREV/'outputs/strategies/LEARN_PREFIX.summary.json',PREV/'outputs/strategies/LEARN_PREFIX.npz',P/'state/state.json',deep.R/'deepen.py',base.R/'core.py']
 dump(O/'protected_sources.json',{str(p.relative_to(P)):sha(p) for p in protected})
 baseline=json.loads((PREV/'outputs/strategies/LEARN_PREFIX.summary.json').read_text('utf-8'));baseline=dict(baseline,family='W4',q=.6,source='previous_verified')
 rows=[run_case(f) for f in ('W1','W2','EW4')];s1=min([baseline,*rows],key=lambda x:x['total_cost']);family=s1['family']
 risk=[run_case(family,q) for q in (.4,.5,.7,.8)];rows+=risk;best=min([s1,*risk],key=lambda x:x['total_cost'])
 if best['q']==.4:rows.append(run_case(family,.3))
 elif best['q']==.8:rows.append(run_case(family,.9))
 winner=min([baseline,*rows],key=lambda x:x['total_cost'])
 no=zero=None
 if winner['total_cost']<baseline['total_cost']:
  no=run_case(winner['family'],winner['q'],'no_new');zero=run_case(winner['family'],winner['q'],'full',True)
 bound=hindsight_bound()
 summary=dict(status='computed_pending_verification',baseline=baseline,candidates=rows,winner=winner,no_new_control=no,zero_control=zero,hindsight=bound,lp_calls=budget.calls,elapsed_seconds=time.perf_counter()-budget.start,code_sha256=sha(__file__),protocol_sha256=sha(R/'protocol.json'))
 dump(O/'summary.json',summary);pd.DataFrame(rows).to_csv(O/'comparison.csv',index=False,encoding='utf-8-sig',float_format='%.17g');event(phase='complete_all',winner=winner['label'],cost=winner['total_cost'])
if __name__=='__main__':main()
