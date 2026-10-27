from pathlib import Path
import os,json,time,hashlib,csv,itertools
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import joblib
R=Path(__file__).resolve().parents[1]
P=R
O=R/'reproduced'
DATE=pd.Timestamp('2025-01-01')
N=365*144
N_DAYS=365
SLOTS=144
CAP=5000/6
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def daystr(d):return str((DATE+pd.Timedelta(days=int(d))).date())
class Budget:
 def __init__(self):self.calls=0;self.lp_calls=0;self.price_fits=0
 def check(self):pass
 def save(self):pass
class Logs:
 def event(self,*a,**kw):pass
budget=Budget();logs=Logs()
import q3_base as base
class Planner(base.Planner):
    def solve(self,L,V,initial,margin,slot,q0=None,fixed=None,terminal=True,floor_ratio=0.):
        n=len(L);f=0 if q0 is None else min(144-slot,n);eq,ub=self.matrices(n,f)
        p=self.price[(slot+np.arange(n))%144];net=np.maximum((L-V)/6+margin,0);sur=np.maximum(-((L-V)/6+margin),0)
        c=np.zeros(8*n);c[4*n:5*n]=5*p;c[6*n:7*n]=p;c[7*n:7*n+f]=.5*p[:f]
        if terminal:c[4*n-1]=-.9*self.price[0]
        lo=np.zeros(8*n);hi=np.full(8*n,np.inf)
        hi[:n]=CAP;hi[n:2*n]=np.minimum(sur,CAP);hi[2*n:3*n]=CAP;lo[3*n:4*n]=1200;hi[3*n:4*n]=10800
        hi[7*n+f:]=0
        if f and floor_ratio>0:lo[6*n:6*n+f]=floor_ratio*np.asarray(q0[:f])
        if fixed is not None:lo[6*n:7*n]=fixed;hi[6*n:7*n]=fixed
        beq=np.r_[np.zeros(n),net];beq[0]=initial
        bu=np.r_[np.full(n,CAP),net,([] if f==0 else q0[:f]),([] if f==0 else -q0[:f])]
        self.budget.calls+=1;self.budget.check();start=time.perf_counter()
        ans=linprog(c,A_ub=ub,A_eq=eq,b_ub=bu,b_eq=beq,bounds=np.c_[lo,hi],method='highs',
            options={'time_limit':10.,'primal_feasibility_tolerance':1e-8,'dual_feasibility_tolerance':1e-8})
        if not ans.success:raise RuntimeError(ans.message)
        err=max(float(np.max(abs(eq@ans.x-beq))),float(np.max(ub@ans.x-bu)),float(np.max(lo-ans.x)),float(np.max(ans.x-hi)))
        finite=np.isfinite(hi)
        dual=beq@ans.eqlin.marginals+bu@ans.ineqlin.marginals+lo@ans.lower.marginals+hi[finite]@ans.upper.marginals[finite]
        gap=abs(ans.fun-dual);z=ans.x.reshape(8,n)
        simultaneous=int(np.sum((z[0]+z[1]>1e-6)&(z[2]>1e-6)))
        assert err<1e-6 and gap<1e-4 and simultaneous==0
        return z,dict(n=n,f=f,initial=float(initial),objective=float(ans.fun),residual=err,dual_gap=float(gap),
            simultaneous=simultaneous,seconds=time.perf_counter()-start,status=int(ans.status),floor_ratio=float(floor_ratio))

def exact_quantile(values,ages,q,beta):
    from fractions import Fraction
    qf=Fraction(str(q));bf=Fraction(str(beta));age_max=int(np.max(ages))
    weights=[bf.numerator**int(a)*bf.denominator**(age_max-int(a)) for a in ages]
    total=sum(weights);acc=0
    for i,w in enumerate(weights):
        acc+=w
        if acc*qf.denominator>=qf.numerator*total:return max(0.,float(values[i]))
    return max(0.,float(values[-1]))
def make_load(kind,gain):
    residual=src['actual'][:365*144,0].reshape(365,144)-fc['L'][:,:144]
    load=np.full((1460,288),np.nan);theta=np.zeros((365,4,8));obs=np.zeros((365,4));count=np.zeros((365,4,8),int)
    for d in range(365):
        for a,slot in enumerate((0,36,72,108)):
            b=d*4+a;n=288-slot;load[b,:n]=fc['L'][d,slot:]
            if not slot:continue
            start=0 if 'PREFIX' in kind else slot-18
            current=residual[d,start:slot]
            observed=float(np.nanmean(current)) if np.isfinite(current).any() else 0.;obs[d,a]=observed
            past=np.arange(max(0,d-28),d)
            X=np.array([np.nanmean(residual[j,start:slot]) for j in past])
            for g in range(slot//18,8):
                Y=np.array([np.mean(residual[j,g*18:(g+1)*18]) for j in past])
                valid=np.isfinite(X)&np.isfinite(Y);x=X[valid];y=Y[valid];count[d,a,g]=len(x)
                if kind=='PERSIST_PREFIX':coef=1.
                else:coef=float(np.clip((x@y)/(x@x),0,1)) if len(x)>=7 and x@x>1e-12 else 0.
                theta[d,a,g]=coef
                left=g*18-slot;right=left+18
                load[b,left:right]=np.maximum(0,load[b,left:right]+gain*coef*observed)
    return load,theta,obs,count

def errors_for(load,pv):
    arrays={k:[] for k in ('release','target','error','kind')}
    for b,r in enumerate(src['release']):
        n=288-r%144;t=r+np.arange(n);ok=(t>0)&(t<365*144);truth=src['actual'][t[ok]]
        arrays['release'].append(np.full(ok.sum(),r));arrays['target'].append(t[ok]);arrays['kind'].append((np.arange(n)[ok]>=144).astype(int))
        arrays['error'].append(((truth[:,0]-truth[:,1])-(load[b,:n][ok]-pv[b,:n][ok]))/6)
    return {k:np.concatenate(v) for k,v in arrays.items()}
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
