"""Causal same-day load correction with arm-specific risk preparation."""
from pathlib import Path
import os, json, hashlib, importlib.util, time
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parent;P=R.parents[3];O=R/'outputs';O.mkdir(exist_ok=True)
B=P/'questions/Q3/runs/20260911-four-candidates-v1/outputs'
I=P/'questions/Q3/runs/20260912-final-information-v1'
spec=importlib.util.spec_from_file_location('info',I/'run.py');info=importlib.util.module_from_spec(spec);spec.loader.exec_module(info)
deep=info.deep;base=deep.base
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
    Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def event(**v):print(json.dumps(v,ensure_ascii=False),flush=True)
class Budget:
    def __init__(self):self.calls=0;self.start=time.perf_counter()
    def check(self):assert self.calls<=8500 and time.perf_counter()-self.start<1800
budget=Budget()
src=dict(np.load(B/'sources.npz'));fc=dict(np.load(B/'forecasts.npz'))
old_info=dict(np.load(I/'outputs/forecasts.npz'))

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

def run_case(label,kind,gain=1.,pvkey='full'):
    folder=O/'strategies';folder.mkdir(exist_ok=True)
    load,theta,obs,count=make_load(kind,gain);pv=old_info[pvkey]
    np.savez_compressed(folder/f'{label}.forecast.npz',load=load,theta=theta,observed=obs,count=count,gain=gain)
    err=errors_for(load,pv);np.savez_compressed(folder/f'{label}.errors.npz',**err)
    margin,meta=info.margin_for(err,src['release']);np.savez_compressed(folder/f'{label}.margin.npz',values=margin,meta=meta)
    oldmargin=np.load(P/'questions/Q3/runs/20260911-parameter-interpretability-v1/outputs/margins/q60_b070_w28_h03.npz')['values']
    assert np.allclose(margin[::4],oldmargin[::4],rtol=0,atol=1e-10,equal_nan=True)
    planner=deep.Planner(src['price'],budget);state=8592.693560925925;days=np.arange(31,365)
    q0=np.empty((334,144));versions=np.empty((334,4,144));execution=np.empty((334,144,12));states=np.empty((334,4));checks=[];daily=[]
    for di,d in enumerate(days):
        initial=state;order=np.zeros(144)
        for a,slot in enumerate((0,36,72,108)):
            b=d*4+a;n=288-slot;states[di,a]=state
            plan,ck=planner.solve(load[b,:n],pv[b,:n],state,margin[b,:n],slot,None if a==0 else q0[di,slot:])
            checks.append(dict(ck,day=int(d),release=a,label=label));order[slot:]=np.maximum(0,plan[6,:144-slot])
            if a==0:q0[di]=order.copy()
            versions[di,a]=order;truth=src['actual'][d*144+slot:d*144+slot+36]
            block,state=base.execute_block(truth[:,0],truth[:,1],order[slot:slot+36],state);execution[di,slot:slot+36]=block
        p=src['price'];delta=order-q0[di];normal=float(p@order);adjust=float(.5*p@abs(delta));emergency=float(5*p@execution[di,:,8])
        daily.append(dict(label=label,date=base.daystr(d),day=int(d),initial=initial,final=state,normal_cost=normal,adjustment_cost=adjust,ordinary_cost=normal+adjust,emergency_cost=emergency,total_cost=normal+adjust+emergency,
            order_kwh=float(order.sum()),emergency_kwh=float(execution[di,:,8].sum()),unused_order_kwh=float(execution[di,:,9].sum()),unused_pv_kwh=float(execution[di,:,10].sum())))
        if (di+1)%100==0:event(phase=label,days=di+1,lp_calls=budget.calls)
    df=pd.DataFrame(daily);df.to_csv(folder/f'{label}.daily.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
    np.savez_compressed(folder/f'{label}.npz',days=days,q0=q0,versions=versions,execution=execution,decision_storage=states)
    pd.DataFrame(checks).to_csv(folder/f'{label}.solver.csv',index=False,float_format='%.17g')
    sums={k:float(df[k].sum()) for k in ('normal_cost','adjustment_cost','ordinary_cost','emergency_cost','total_cost','order_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh')}
    mae=[]
    for a,slot in enumerate((36,72,108),1):
        truth=np.stack([src['actual'][d*144+slot:d*144+slot+36,0] for d in days]);prediction=load[days*4+a,:36];old=fc['L'][days,slot:slot+36]
        mae.append(dict(hour=slot/6,old_mae=float(abs(truth-old).mean()),new_mae=float(abs(truth-prediction).mean())))
    result=dict(sums,label=label,kind=kind,gain=gain,pvkey=pvkey,days=334,initial=8592.693560925925,final=state,emergency_days=int((df.emergency_kwh>1e-6).sum()),lp_calls=len(checks),max_residual=max(c['residual'] for c in checks),max_dual_gap=max(c['dual_gap'] for c in checks),load_prediction_mae=mae)
    dump(folder/f'{label}.summary.json',result);event(phase='complete',label=label,cost=result['total_cost'],emergency_kwh=result['emergency_kwh'])
    dump(O/'progress.json',dict(lp_calls=budget.calls,elapsed=time.perf_counter()-budget.start,last=result));return result

def main():
    protected=[B/'sources.npz',B/'forecasts.npz',I/'run.py',I/'outputs/forecasts.npz',I/'outputs/verification.json',I/'outputs/strategies/F2_full.npz',I/'outputs/strategies/F2_full.summary.json',deep.R/'deepen.py',base.R/'core.py',P/'state/state.json']
    for name,meta in json.loads((P/'data/prepared-v1/manifest.json').read_text('utf-8'))['outputs'].items():
        p=P/'data/prepared-v1'/name
        if p.is_file():assert sha(p)==meta['sha256'];protected.append(p)
    dump(O/'protected_sources.json',{str(p.relative_to(P)):sha(p) for p in protected})
    baseline=json.loads((I/'outputs/strategies/F2_full.summary.json').read_text('utf-8'))
    rows=[run_case(kind,kind) for kind in ('PERSIST_PREFIX','LEARN_PREFIX','LEARN_RECENT')]
    first=min(rows,key=lambda r:r['total_cost'])
    half=[first['kind']] if first['total_cost']<baseline['total_cost'] else ['LEARN_PREFIX','LEARN_RECENT']
    rows.extend(run_case(kind+'_HALF',kind,.5) for kind in half)
    winner=min(rows,key=lambda r:r['total_cost']);saving=baseline['total_cost']-winner['total_cost']
    reference_saving=saving+.9*src['price'][0]*(winner['final']-baseline['final'])
    control=None
    if saving>0 and reference_saving>0:control=run_case(winner['label']+'_NO_NEW',winner['kind'],winner['gain'],'no_new')
    summary=dict(status='computed_pending_verification',baseline=baseline,candidates=rows,winner=winner if saving>0 and reference_saving>0 else baseline,no_new_control=control,
        saving=saving,reference_adjusted_saving=reference_saving,lp_calls=budget.calls,elapsed_seconds=time.perf_counter()-budget.start,protocol_sha256=sha(R/'protocol.json'),code_sha256=sha(__file__))
    dump(O/'summary.json',summary);pd.DataFrame(rows).to_csv(O/'comparison.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
    event(phase='finished',winner=summary['winner']['label'],saving=saving,lp_calls=budget.calls)
if __name__=='__main__':main()
