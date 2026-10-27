"""Focused Q3 deepening around S2: causal allowances and reduction floors."""
from pathlib import Path
import os, sys, json, time, hashlib, importlib.util
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
os.environ['NUMEXPR_MAX_THREADS']='1'
import numpy as np
import pandas as pd
from scipy.optimize import linprog

R=Path(__file__).resolve().parent
P=R.parents[3]
BASE=P/'questions/Q3/runs/20260911-four-candidates-v1'
O=R/'outputs'; O.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('q3base',BASE/'core.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
CAP=5000/6
DATE=pd.Timestamp('2025-01-01')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def daystr(d):return str((DATE+pd.Timedelta(days=int(d))).date())
def event(name,**kw):print(json.dumps(dict(event=name,**kw),ensure_ascii=False),flush=True)

class Budget:
    def __init__(self):
        self.path=O/'budget.json';old=json.loads(self.path.read_text()) if self.path.exists() else {}
        self.calls=int(old.get('lp_calls',0));self.elapsed=float(old.get('elapsed_seconds',0));self.start=time.perf_counter()
    def check(self):
        assert self.calls<=35000,'LP budget exhausted'
        assert self.elapsed+time.perf_counter()-self.start<=1800,'research time budget exhausted'
    def save(self):
        dump(self.path,dict(lp_calls=self.calls,tree_fits=0,elapsed_seconds=self.elapsed+time.perf_counter()-self.start))

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

def build_margin(q,beta):
    folder=O/'margins';folder.mkdir(exist_ok=True)
    name=f'q{int(round(q*100)):02d}_b{int(round(beta*100)):03d}.npz';path=folder/name
    if path.exists():return np.load(path)['values']
    old=dict(np.load(BASE/'outputs/error_records.npz'));rr=old['release'];tt=old['target'];ee=old['error'];tag=old['kind']
    releases=np.load(BASE/'outputs/sources.npz')['release'];group=tt%144//24
    values=np.full((1460,288),np.nan);counts=[]
    for b,r in enumerate(releases):
        pool=(rr>=r-28*144)&(rr<r)&(tt+1<=r)&(rr%144==r%144);n=288-r%144;tgt=r+np.arange(n);futurekind=(np.arange(n)>=144).astype(int)
        for typ in [0,1]:
            samekind=pool&(tag==typ)
            for g in range(6):
                dest=(tgt%144//24==g)&(futurekind==typ)
                if not dest.any():continue
                use=samekind&(group==g);fallback=0
                if use.sum()<24:use=samekind;fallback=1
                ids=np.flatnonzero(use);order=np.argsort(ee[ids],kind='stable');ids=ids[order]
                val=exact_quantile(ee[ids],(r-1)//144-tt[ids]//144,q,beta) if len(ids)>=24 else 0.
                values[b,:n][dest]=val;counts.append([b,typ,g,len(ids),fallback,int(np.max(tt[ids]+1)) if len(ids) else -1])
        if b%365==0:event('margin_progress',q=q,beta=beta,release=b)
    np.savez_compressed(path,values=values,meta=np.array(counts,float),q=q,beta=beta)
    return values

def run(label,margin=None,scale=(1,1,1,1),floor=0.,family='allowance'):
    folder=O/'strategies';folder.mkdir(exist_ok=True)
    summary_path=folder/(label+'.summary.json')
    if summary_path.exists():return json.loads(summary_path.read_text())
    src=dict(np.load(BASE/'outputs/sources.npz'));fc=dict(np.load(BASE/'outputs/forecasts.npz'))
    planner=Planner(src['price'],budget);days=list(range(31,365));state=8592.693560925925
    qzero=np.empty((334,144));versions=np.empty((334,4,144));execution=np.empty((334,144,12));states=np.empty((334,4));checks=[];daily=[]
    for di,d in enumerate(days):
        qorder=np.zeros(144);day_initial=state
        for a,slot in enumerate([0,36,72,108]):
            b=d*4+a;n=288-slot;states[di,a]=state
            marr=np.zeros(n) if margin is None else margin[b,:n]*scale[a]
            plan,check=planner.solve(fc['L'][d,slot:],fc['fused'][b,:n],state,marr,slot,None if a==0 else qzero[di,slot:],floor_ratio=floor)
            checks.append(dict(check,day=d,release=a,label=label))
            qorder[slot:]=np.maximum(0,plan[6,:144-slot])
            if a==0:qzero[di]=qorder.copy()
            versions[di,a]=qorder
            truth=src['actual'][d*144+slot:d*144+slot+36]
            block,state=base.execute_block(truth[:,0],truth[:,1],qorder[slot:slot+36],state);execution[di,slot:slot+36]=block
        qf=qorder;delta=qf-qzero[di];price=src['price']
        ordinary=float(price@qf+.5*price@abs(delta));emergency=float(5*price@execution[di,:,8])
        daily.append(dict(label=label,date=daystr(d),day=d,initial=day_initial,final=state,ordinary_cost=ordinary,
            emergency_cost=emergency,total_cost=ordinary+emergency,original_plan_cost=float(price@qzero[di]),
            order_kwh=float(qf.sum()),emergency_kwh=float(execution[di,:,8].sum()),
            unused_order_kwh=float(execution[di,:,9].sum()),unused_pv_kwh=float(execution[di,:,10].sum()),
            reduced_kwh=float(np.maximum(-delta,0).sum()),increased_kwh=float(np.maximum(delta,0).sum())))
        if (di+1)%50==0:event('strategy_progress',label=label,days=di+1,lp_calls=budget.calls)
    df=pd.DataFrame(daily);df.to_csv(folder/(label+'.daily.csv'),index=False,encoding='utf-8-sig',float_format='%.17g')
    np.savez_compressed(folder/(label+'.npz'),days=np.array(days),q0=qzero,versions=versions,execution=execution,decision_storage=states,
        scale=np.array(scale),floor=floor)
    pd.DataFrame(checks).to_csv(folder/(label+'.solver.csv'),index=False,encoding='utf-8-sig',float_format='%.17g')
    result=dict(label=label,family=family,total_cost=float(df.total_cost.sum()),ordinary_cost=float(df.ordinary_cost.sum()),
        emergency_cost=float(df.emergency_cost.sum()),emergency_kwh=float(df.emergency_kwh.sum()),
        unused_order_kwh=float(df.unused_order_kwh.sum()),unused_pv_kwh=float(df.unused_pv_kwh.sum()),
        reduced_kwh=float(df.reduced_kwh.sum()),increased_kwh=float(df.increased_kwh.sum()),days=334,
        initial=8592.693560925925,final=float(state),emergency_days=int((df.emergency_kwh>1e-6).sum()),
        lp_calls=len(checks),floor_ratio=float(floor),release_scale=list(scale),
        max_residual=max(x['residual'] for x in checks),max_dual_gap=max(x['dual_gap'] for x in checks),
        trace=str((folder/(label+'.npz')).relative_to(R)),daily_csv=str((folder/(label+'.daily.csv')).relative_to(R)))
    dump(summary_path,result);budget.save();event('strategy_complete',label=label,total=result['total_cost'],emergency=result['emergency_cost'])
    return result

def best(rows):return min(rows,key=lambda x:x['total_cost'])
def main():
    protected=[BASE/'outputs/summary.json',BASE/'outputs/verification.json',BASE/'outputs/sources.npz',BASE/'outputs/forecasts.npz',BASE/'outputs/error_records.npz',BASE/'core.py']
    dump(O/'protected_sources.json',{str(p.relative_to(P)):sha(p) for p in protected})
    base_summary=next(x for x in json.loads((BASE/'outputs/summary.json').read_text())['annual'] if x['label']=='S2_fused')
    rows=[dict(base_summary,label='S2_baseline',family='baseline_reused',release_scale=[0,0,0,0],floor_ratio=0.)]
    stage1=[]
    for q in [.6,.7,.8]:
        for beta in [.7,.8,1.]:
            m=build_margin(q,beta);r=run(f'M_q{int(q*100):02d}_b{int(beta*100):03d}',m,family='allowance_stage1')
            r.update(q=q,beta=beta);stage1.append(r);rows.append(r)
    winner=best([rows[0],*stage1]);fine=[]
    if winner['family']!='baseline_reused':
        q=winner['q'];beta=winner['beta'];around={.6:[.5,.55,.65],.7:[.65,.75],.8:[.75,.85,.9]}[q]
        for q2 in around:
            r=run(f'M_q{int(round(q2*100)):02d}_b{int(beta*100):03d}',build_margin(q2,beta),family='allowance_fine')
            r.update(q=q2,beta=beta);fine.append(r);rows.append(r)
    allowance=best([rows[0],*stage1,*fine]);margin=None if allowance['family']=='baseline_reused' else build_margin(allowance['q'],allowance['beta'])
    floors=[]
    for rho in [.25,.5,.75,1.]:
        r=run(f'R_floor{int(rho*100):03d}',None,floor=rho,family='reduction_floor');floors.append(r);rows.append(r)
    combos=[];scales=[]
    if margin is not None:
        for rho in [.25,.5,.75,1.]:
            r=run(f'C_{allowance["label"]}_floor{int(rho*100):03d}',margin,floor=rho,family='allowance_plus_floor')
            r.update(q=allowance['q'],beta=allowance['beta']);combos.append(r);rows.append(r)
        schedules=[(1,.75,.5,.25),(1,1,.75,.5),(1,.5,0,0),(1,0,0,0)]
        for j,scale in enumerate(schedules,1):
            r=run(f'S{j}_{allowance["label"]}',margin,scale=scale,family='release_scaled_allowance')
            r.update(q=allowance['q'],beta=allowance['beta']);scales.append(r);rows.append(r)
        bf=best([allowance,*combos]);bs=best([allowance,*scales])
        if bf.get('floor_ratio',0)>0 and bs.get('release_scale',[1,1,1,1])!=[1,1,1,1]:
            r=run(f'X_{allowance["label"]}_floor{int(bf["floor_ratio"]*100):03d}',margin,scale=tuple(bs['release_scale']),floor=bf['floor_ratio'],family='best_combination')
            r.update(q=allowance['q'],beta=allowance['beta']);rows.append(r)
    result=best(rows);comparison=pd.DataFrame(rows).sort_values('total_cost')
    comparison.to_csv(O/'comparison.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
    dump(O/'summary.json',dict(status='completed_pending_independent_verification',baseline=rows[0],selected=result,
        all=rows,budget=json.loads((O/'budget.json').read_text()),selection_note='exploratory selection on the required334days; not untouched external test',
        code_sha256=sha(__file__),protocol_sha256=sha(R/'protocol.json')))
    event('deepening_complete',winner=result['label'],cost=result['total_cost'],saving=rows[0]['total_cost']-result['total_cost'],lp_calls=budget.calls)

budget=Budget()
if __name__=='__main__':
    try:main()
    finally:budget.save()
