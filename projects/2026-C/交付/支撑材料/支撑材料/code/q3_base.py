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
def history_and_features(actual,reference,F,release,targets):
    # Profile j only uses observations of that clock slot whose intervals ended by r.
    hist=np.empty((1460,144));last=np.empty(1460)
    for b,r in enumerate(release):
        last[b]=actual[r-1,1] if r>1 else reference[0,1]
        for k in range(144):
            q=r-1-((r-1-k)%144);ii=q-144*np.arange(7);ii=ii[ii>=1]
            hist[b,k]=np.mean(actual[ii,1]) if len(ii) else reference[k,1]
    L=np.empty((365,288))
    for d in range(365):
        for h in [0,1]:
            ds=[d+h-7*j for j in range(1,5) if 0<=d+h-7*j<d]
            if not ds:ds=list(range(max(0,d-7),d))
            if not ds:L[d,h*144:(h+1)*144]=reference[:,0];continue
            z=actual[np.array(ds)[:,None]*144+np.arange(144)[None,:],0]
            cnt=np.isfinite(z).sum(axis=0)
            L[d,h*144:(h+1)*144]=np.divide(np.nansum(z,axis=0),cnt,out=reference[:,0].copy(),where=cnt>0)
    H=np.take_along_axis(hist,targets%144,axis=1)
    hr=targets%144/6;year=targets//144+1
    X=np.stack([F,H,np.repeat(last[:,None],24,axis=1),np.repeat((release%144/6)[:,None],24,axis=1),
                np.tile(np.arange(1,25),(1460,1)),np.sin(2*np.pi*hr/24),np.cos(2*np.pi*hr/24),
                np.sin(2*np.pi*year/365),np.cos(2*np.pi*year/365)],axis=-1).reshape(-1,9)
    return hist,last,L,H,X

def build_fusion(actual,F,H,release,targets):
    rr=np.repeat(release,24);tt=targets.ravel();ff=F.ravel();hh=H.ravel()
    truth=np.full(len(tt),np.nan);valid=tt<N;truth[valid]=actual[tt[valid],1]
    w=np.ones((1460,4));counts=np.zeros((1460,4),int);fallback=np.zeros((1460,4),int);cut=np.full((1460,4),-1,int)
    leadgroup=np.tile(np.arange(24)//6,1460)
    for b,r in enumerate(release):
        pool=(rr>=r-28*144)&(rr<r)&(tt+1<=r)&(rr%144==r%144)&np.isfinite(truth)
        for g in range(4):
            use=pool&(leadgroup==g)
            if use.sum()<24:use=pool;fallback[b,g]=1
            counts[b,g]=use.sum()
            if use.any():cut[b,g]=int(np.max(tt[use]+1))
            a=ff[use]-hh[use];den=a@a
            if use.sum()<24 or den<1e-12:fallback[b,g]=2;continue
            w[b,g]=np.clip(a@(truth[use]-hh[use])/den,0,1)
    fused=np.repeat(w,6,axis=1)*F+(1-np.repeat(w,6,axis=1))*H
    return fused,w,counts,fallback,cut

def to_intervals(hourly,hist,last,release,zero_version=False):
    out=np.full((1460,288),np.nan)
    for b,r in enumerate(release):
        n=288-r%144;targets=r+np.arange(n);v=hist[b,targets%144].copy()
        if zero_version:
            midnight=(r//144)*144;ix=np.flatnonzero(midnight+np.arange(1,25)*6>r)
            xp=np.r_[r,midnight+(ix+1)*6];fp=np.r_[last[b],hourly[(r//144)*4,ix]]
            inside=targets<midnight+144
            v[inside]=np.interp(targets[inside],xp,fp)
        else:v[:144]=np.interp(np.arange(144),np.arange(0,145,6),np.r_[last[b],hourly[b]])
        out[b,:n]=v
    return out

class Planner:
    """Variables x,y,z,S,e,r,q,w; r is paid but unreceived normal energy."""
    def __init__(self,price,budget):self.price=price;self.budget=budget;self.cache={}
    def matrices(self,n,f):
        key=(n,f)
        if key in self.cache:return self.cache[key]
        eq=lil_matrix((2*n,8*n));ub=lil_matrix((2*n+2*f,8*n))
        for i in range(n):
            eq[i,i]=-.9;eq[i,n+i]=-.9;eq[i,2*n+i]=1/.9;eq[i,3*n+i]=1
            if i:eq[i,3*n+i-1]=-1
            eq[n+i,6*n+i]=1;eq[n+i,i]=-1;eq[n+i,2*n+i]=1;eq[n+i,4*n+i]=1;eq[n+i,5*n+i]=-1
            ub[i,i]=ub[i,n+i]=1;ub[n+i,2*n+i]=ub[n+i,4*n+i]=1
        for i in range(f):
            ub[2*n+i,6*n+i]=1;ub[2*n+i,7*n+i]=-1
            ub[2*n+f+i,6*n+i]=-1;ub[2*n+f+i,7*n+i]=-1
        self.cache[key]=eq.tocsr(),ub.tocsr();return self.cache[key]
    def solve(self,L,V,initial,margin,slot,q0=None,fixed=None,terminal=True):
        n=len(L);f=0 if q0 is None else min(144-slot,n);eq,ub=self.matrices(n,f)
        p=self.price[(slot+np.arange(n))%144];net=np.maximum((L-V)/6+margin,0);ex=np.maximum((V-L)/6-margin,0)
        c=np.zeros(8*n);c[4*n:5*n]=5*p;c[6*n:7*n]=p;c[7*n:7*n+f]=.5*p[:f]
        if terminal:c[4*n-1]=-.9*self.price[0]
        lo=np.zeros(8*n);hi=np.full(8*n,np.inf)
        hi[:n]=CAP;hi[n:2*n]=np.minimum(ex,CAP);hi[2*n:3*n]=CAP;lo[3*n:4*n]=1200;hi[3*n:4*n]=10800
        hi[7*n+f:]=0
        if fixed is not None:lo[6*n:7*n]=fixed;hi[6*n:7*n]=fixed
        beq=np.r_[np.zeros(n),net];beq[0]=initial
        bu=np.r_[np.full(n,CAP),net,([] if f==0 else q0[:f]),([] if f==0 else -q0[:f])]
        self.budget.calls+=1;self.budget.check();start=time.perf_counter()
        ans=linprog(c,A_ub=ub,b_ub=bu,A_eq=eq,b_eq=beq,bounds=np.c_[lo,hi],method='highs',
              options={'time_limit':10.,'primal_feasibility_tolerance':1e-8,'dual_feasibility_tolerance':1e-8})
        if not ans.success:raise RuntimeError(ans.message)
        err=max(float(np.max(abs(eq@ans.x-beq))),float(np.max(ub@ans.x-bu)),float(np.max(lo-ans.x)),float(np.max(ans.x-hi)))
        finite=np.isfinite(hi)
        dual=beq@ans.eqlin.marginals+bu@ans.ineqlin.marginals+lo@ans.lower.marginals+hi[finite]@ans.upper.marginals[finite]
        gap=abs(ans.fun-dual);z=ans.x.reshape(8,n)
        simultaneous=int(np.sum((z[0]+z[1]>1e-6)&(z[2]>1e-6)))
        assert err<1e-6 and gap<1e-4,(err,gap)
        # Fixed-order feasibility diagnostics may be degenerate; actual execution is independently causal.
        if fixed is None:assert simultaneous==0, 'planned simultaneous charge/discharge'
        check=dict(n=n,f=f,initial=float(initial),objective=float(ans.fun),residual=err,dual_gap=float(gap),
                   simultaneous=simultaneous,seconds=time.perf_counter()-start,status=int(ans.status))
        return z,check

def execute_block(L,V,q,initial):
    # Columns retain physical flows separately from paid order and settlement.
    out=np.empty((len(q),12));s=float(initial)
    for k in range(len(q)):
        l=float(L[k]/6);v=float(V[k]/6);order=max(0.,float(q[k]));direct=min(l,v);need=l-direct;surplus=v-direct;s0=s
        if need>order:
            z=min(need-order,CAP,max(0.,.9*(s-1200)));e=max(0.,need-order-z);x=y=0.;received=order
        else:
            ch=min(surplus+order-need,CAP,max(0.,(10800-s)/.9));y=min(surplus,ch);x=ch-y;received=need+x;z=e=0.
        s+=.9*(x+y)-z/.9
        out[k]=[s0,s,received,received-x,direct,x,y,z,e,max(0.,order-received),max(0.,surplus-y),l]
        assert 1200-1e-6<=s<=10800+1e-6 and abs(received-x+direct+z+e-l)<1e-6
    return out,s
