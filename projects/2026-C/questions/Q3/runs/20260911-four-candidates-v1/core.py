"""Q3 causal forecast preparation, continuous dispatch and actual feedback.
All source materials remain read-only. See protocol.json for authorization.
"""
import os
for _k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_k]='1'
os.environ['NUMEXPR_MAX_THREADS']='1'
from pathlib import Path
import json, hashlib, time, warnings
warnings.filterwarnings('ignore',message='Pandas requires version')
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits
import joblib

R=Path(__file__).resolve().parent
P=R.parents[3]
O=R/'outputs'
N=365*144
CAP=5000/6
DATE=pd.Timestamp('2025-01-01')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def daystr(d):return str((DATE+pd.Timedelta(days=int(d))).date())
def event(msg,**kw):print(json.dumps(dict(event=msg,**kw),ensure_ascii=False),flush=True)

class Budget:
    def __init__(self):
        self.path=O/'budget.json'; self.start=time.perf_counter()
        self.old=json.loads(self.path.read_text()) if self.path.exists() else dict(lp_calls=0,tree_fits=0,elapsed_seconds=0.)
        self.calls=self.old['lp_calls'];self.fits=self.old['tree_fits']
    def check(self):
        assert self.calls<=12000 and self.fits<=200, 'research count budget exhausted'
        assert self.old['elapsed_seconds']+time.perf_counter()-self.start<3600,'research time budget exhausted'
    def save(self):
        dump(self.path,dict(lp_calls=self.calls,tree_fits=self.fits,elapsed_seconds=self.old['elapsed_seconds']+time.perf_counter()-self.start))

def load_inputs():
    O.mkdir(exist_ok=True)
    m=json.loads((P/'data/prepared-v1/manifest.json').read_text(encoding='utf-8'))
    protect={}
    for n in ['day_reference.csv','actual_power.csv','pv_forecasts.csv']:
        path=P/'data/prepared-v1'/n;assert sha(path)==m['outputs'][n]['sha256'];protect[str(path.relative_to(P))]=sha(path)
    paths=[P/'data/raw/C题/C题.pdf',*list((P/'data/raw/C题/附件').rglob('*.xlsx')),
           P/'questions/Q1/runs/20260911-compare-v1/outputs/schedules/C04.csv',
           P/'questions/Q2/runs/20260911-four-candidates-v1/core.py',
           P/'questions/Q2/runs/20260911-four-candidates-v1/outputs/initialization.json',
           P/'questions/Q2/runs/20260911-annual-validation-v1/delivery_data/summary.json',
           P/'questions/Q2/runs/20260911-annual-validation-v1/delivery_data/selected_daily.csv',
           P/'paper/q2_manuscript_v2/chapter.tex',P/'paper/q2_manuscript_v2/问题二的模型建立与求解.pdf']
    for p in paths:
        if p.name.startswith('~$'):continue
        assert p.is_file(),p;protect[str(p.relative_to(P))]=sha(p)
    dump(O/'protected_sources.json',protect)
    ref=pd.read_csv(P/'data/prepared-v1/day_reference.csv',float_precision='round_trip')
    ref=ref.assign(t=ref.source_minute%1440).sort_values('t')
    assert list(ref.t)==list(range(0,1440,10))
    price=ref.price_yuan_per_kwh.to_numpy();reference=ref[['load_kw','pv_forecast_kw']].to_numpy()
    a=pd.read_csv(P/'data/prepared-v1/actual_power.csv',float_precision='round_trip')
    t=pd.to_datetime(a.source_date)+pd.to_timedelta(a.source_minute,unit='m')
    idx=((t-DATE).dt.total_seconds()/600).astype(int).to_numpy()
    assert np.array_equal(idx,np.arange(1,N+1))
    actual=np.full((N+1,2),np.nan);actual[idx]=a[['load_kw','pv_actual_kw']].to_numpy()
    f=pd.read_csv(P/'data/prepared-v1/pv_forecasts.csv',float_precision='round_trip')
    rr=((pd.to_datetime(f.release_datetime)-DATE).dt.total_seconds()/600).astype(int).to_numpy()
    tt=((pd.to_datetime(f.target_datetime)-DATE).dt.total_seconds()/600).astype(int).to_numpy()
    release=np.arange(1460)*36;targets=release[:,None]+np.arange(1,25)[None,:]*6
    assert np.array_equal(rr,np.repeat(release,24)) and np.array_equal(tt,targets.ravel())
    F=f.pv_forecast_kw.to_numpy().reshape(1460,24)
    init=json.loads((P/'questions/Q2/runs/20260911-four-candidates-v1/outputs/initialization.json').read_text())
    annual=json.loads((P/'questions/Q2/runs/20260911-annual-validation-v1/delivery_data/summary.json').read_text())
    assert abs(init['feb1_initial']-annual['start_kwh'])<1e-9
    np.savez_compressed(O/'sources.npz',actual=actual,reference=reference,price=price,F=F,release=release,targets=targets)
    dump(O/'initialization.json',dict(jan8=init['jan8_initial'],feb1=init['feb1_initial'],source='existing common Q2 January path, unchanged'))
    return actual,reference,price,F,release,targets

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

def tree_predictions(actual,F,release,targets,X,budget):
    rr=np.repeat(release,24);tt=targets.ravel();Y=np.full(len(tt),np.nan)
    m=tt<N;Y[m]=actual[tt[m],1]-F.ravel()[m]
    outs={};records=[]
    for leaf in [7,15]:
        model=None;pred=F.copy()
        for b,r in enumerate(release):
            d=r//144
            if r%144==0 and d>=7 and (d-7)%7==0:
                ix=np.flatnonzero((rr>=r-90*144)&(rr<r)&(tt+1<=r)&np.isfinite(Y))
                if len(ix)>=60:
                    budget.fits+=1;budget.check()
                    model=HistGradientBoostingRegressor(max_leaf_nodes=leaf,max_iter=100,learning_rate=.05,
                        l2_regularization=1,min_samples_leaf=30,early_stopping=False,random_state=2026)
                    with threadpool_limits(limits=1):model.fit(X[ix],Y[ix])
                    path=O/'models'/f'leaf{leaf}-day{d:03d}.joblib';path.parent.mkdir(exist_ok=True)
                    joblib.dump(model,path);np.save(path.with_suffix('.indices.npy'),ix)
                    records.append(dict(leaf=leaf,day=int(d),release=int(r),n=len(ix),latest_end=int(np.max(tt[ix]+1)),model=str(path.relative_to(R)),sha256=sha(path)))
            if model is not None:
                with threadpool_limits(limits=1):pred[b]=np.maximum(0,F[b]+model.predict(X[b*24:(b+1)*24]))
            if b%240==0:event('tree_cache',leaf=leaf,through_day=int(d),fits=budget.fits);budget.save()
        outs[f'tree{leaf}']=pred
    dump(O/'tree_fits.json',records)
    return outs

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

def exact_quantile(values,ages,alpha,beta):
    """First weighted CDF crossing, including exact equality at decimal risk levels."""
    age_max=int(np.max(ages));digits=int(round(beta*10));an=int(round(alpha*10))
    iw=[digits**age * 10**(age_max-age) for age in range(age_max+1)]
    hist=np.bincount(ages,minlength=age_max+1)
    total=sum(int(count)*weight for count,weight in zip(hist,iw))
    floats=beta**ages;cdf=np.cumsum(floats)
    k=min(len(values)-1,int(np.searchsorted(cdf/cdf[-1],alpha)))
    head=np.bincount(ages[:k+1],minlength=age_max+1)
    prefix=sum(int(count)*weight for count,weight in zip(head,iw))
    while k>0 and 10*(prefix-iw[int(ages[k])])>=an*total:
        prefix-=iw[int(ages[k])];k-=1
    while 10*prefix<an*total:
        k+=1;prefix+=iw[int(ages[k])]
    return max(0.,float(values[k]))

def build_margins(actual,pred,L,release,budget):
    all_r=[];all_t=[];all_e=[];all_tag=[]
    for b,r in enumerate(release):
        n=288-r%144;tt=r+np.arange(n);ok=(tt<N)&(tt>0)
        tr=actual[tt[ok]];lp=L[r//144,r%144:r%144+n][ok]
        all_r.extend(np.full(ok.sum(),r));all_t.extend(tt[ok]);all_tag.extend((np.arange(n)[ok]>=144).astype(int))
        all_e.extend(((tr[:,0]-tr[:,1])-(lp-pred[b,:n][ok]))/6)
    rr=np.asarray(all_r);tt=np.asarray(all_t);ee=np.asarray(all_e);tag=np.asarray(all_tag)
    pairs=[(a,b) for a in [.5,.7,.9] for b in [1.,.9,.7]]
    margins=np.full((9,1460,288),np.nan);sample_meta=[]
    group=tt%144//24
    for b,r in enumerate(release):
        budget.check();pool=(rr>=r-28*144)&(rr<r)&(tt+1<=r)&(rr%144==r%144)
        n=288-r%144;tgt=r+np.arange(n);pred_tag=(np.arange(n)>=144).astype(int)
        for typ in [0,1]:
            tp=pool&(tag==typ)
            for g in range(6):
                dest=(tgt%144//24==g)&(pred_tag==typ)
                if not dest.any():continue
                use=tp&(group==g);fb=0
                if use.sum()<24:use=tp;fb=1
                ids=np.flatnonzero(use);values=ee[ids];o=np.argsort(values,kind='stable');ids=ids[o];values=values[o]
                sample_meta.append((b,typ,g,len(ids),fb,int(np.max(tt[ids]+1)) if len(ids) else -1))
                for beta in [1.,.9,.7]:
                    for alpha in [.5,.7,.9]:
                        j=pairs.index((alpha,beta))
                        q=exact_quantile(values,(r-1)//144-tt[ids]//144,alpha,beta) if len(ids)>=24 else 0.
                        margins[j,b,:n][dest]=q
        if b%360==0:event('margin_cache',through_day=int(r//144));budget.save()
    np.savez_compressed(O/'error_records.npz',release=rr,target=tt,error=ee,kind=tag)
    return margins,np.array(pairs),np.asarray(sample_meta)

def prepare(budget):
    if (O/'forecasts.npz').exists():return
    actual,reference,price,F,release,targets=load_inputs()
    hist,last,L,H,X=history_and_features(actual,reference,F,release,targets)
    fused,w,counts,fallback,cut=build_fusion(actual,F,H,release,targets)
    tree=tree_predictions(actual,F,release,targets,X,budget)
    preds={key:to_intervals(val,hist,last,release) for key,val in dict(raw=F,fused=fused,**tree).items()}
    preds['old']=to_intervals(F,hist,last,release,True)
    margins,pairs,smeta=build_margins(actual,preds['fused'],L,release,budget)
    np.savez_compressed(O/'forecasts.npz',**preds,L=L,hist=hist,H=H,last=last,X=X,fused_hourly=fused,
                        tree7_hourly=tree['tree7'],tree15_hourly=tree['tree15'],weights=w,counts=counts,fallback=fallback,latest_fit_end=cut)
    np.savez_compressed(O/'margins.npz',values=margins,pairs=pairs,sample_meta=smeta)
    import scipy,sklearn
    dump(O/'environment.json',dict(python=os.sys.version,numpy=np.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__,threads=1))
    budget.save();event('preparation_complete',tree_fits=budget.fits)

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

EXEC_COLUMNS=['storage_start','storage_end','received','grid_load','pv_load','grid_charge','pv_charge','discharge','emergency','unused_order','unused_pv','load_energy']
