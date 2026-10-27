"""Final-policy information controls; no new forecast fitting family or tuning."""
from pathlib import Path
import os, json, hashlib, importlib.util, time
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parent
P=R.parents[3]
O=R/'outputs'; O.mkdir(exist_ok=True)
BASE=P/'questions/Q3/runs/20260911-four-candidates-v1'
FINAL=P/'questions/Q3/runs/20260911-parameter-interpretability-v1'
spec=importlib.util.spec_from_file_location('deep',P/'questions/Q3/runs/20260911-s2-deepening-v1/deepen.py')
deep=importlib.util.module_from_spec(spec);spec.loader.exec_module(deep)
base=deep.base
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def event(**v):print(json.dumps(v,ensure_ascii=False),flush=True)
class Budget:
    def __init__(self):self.calls=0;self.start=time.perf_counter()
    def check(self):
        assert self.calls<=3200
        assert time.perf_counter()-self.start<1800
budget=Budget()

def errors_for(pred,src,fc):
    rr=[];tt=[];ee=[];kk=[]
    for b,r in enumerate(src['release']):
        n=288-r%144;t=r+np.arange(n);ok=(t>0)&(t<365*144)
        truth=src['actual'][t[ok]]
        error=((truth[:,0]-truth[:,1])-(fc['L'][r//144,r%144:][ok]-pred[b,:n][ok]))/6
        rr.append(np.full(ok.sum(),r));tt.append(t[ok]);ee.append(error);kk.append((np.arange(n)[ok]>=144).astype(int))
    return dict(release=np.concatenate(rr),target=np.concatenate(tt),error=np.concatenate(ee),kind=np.concatenate(kk))

def margin_for(err,releases):
    rr,tt,ee,kind=(err[k] for k in ('release','target','error','kind'))
    values=np.full((1460,288),np.nan);meta=[]
    for b,r in enumerate(releases):
        pool=(rr>=r-28*144)&(rr<r)&(tt+1<=r)&(rr%144==r%144)
        n=288-r%144;target=r+np.arange(n);ft=(np.arange(n)>=144).astype(int)
        for typ in (0,1):
            same=pool&(kind==typ)
            for g in range(8):
                dest=(target%144//18==g)&(ft==typ)
                if not dest.any():continue
                use=same&(tt%144//18==g);fallback=0
                if use.sum()<24:use=same;fallback=1
                ids=np.flatnonzero(use);ids=ids[np.argsort(ee[ids],kind='stable')]
                val=deep.exact_quantile(ee[ids],(r-1)//144-tt[ids]//144,.6,.7) if len(ids)>=24 else 0.
                values[b,:n][dest]=val
                meta.append([b,typ,g,len(ids),fallback,int(np.max(tt[ids]+1)) if len(ids) else -1])
        if b%365==0:event(phase='margin',release=b)
    return values,np.asarray(meta)

def run_arm(label,pred,margin,src,fc):
    planner=deep.Planner(src['price'],budget);state=8592.693560925925
    days=np.arange(31,365);q0=np.empty((334,144));versions=np.empty((334,4,144))
    execution=np.empty((334,144,12));states=np.empty((334,4));checks=[];daily=[]
    for di,d in enumerate(days):
        initial=state;order=np.zeros(144)
        for a,slot in enumerate((0,36,72,108)):
            b=d*4+a;n=288-slot;states[di,a]=state
            if a==0 or label!='F0_zero_only':
                plan,ck=planner.solve(fc['L'][d,slot:],pred[b,:n],state,margin[b,:n],slot,None if a==0 else q0[di,slot:])
                checks.append(dict(ck,day=int(d),release=a,label=label))
                order[slot:]=np.maximum(0,plan[6,:144-slot])
            if a==0:q0[di]=order.copy()
            versions[di,a]=order
            truth=src['actual'][d*144+slot:d*144+slot+36]
            block,state=base.execute_block(truth[:,0],truth[:,1],order[slot:slot+36],state)
            execution[di,slot:slot+36]=block
        p=src['price'];delta=order-q0[di];normal=float(p@order);adjust=float(.5*p@abs(delta));emergency=float(5*p@execution[di,:,8])
        daily.append(dict(label=label,date=base.daystr(d),day=int(d),initial=initial,final=state,
            normal_cost=normal,adjustment_cost=adjust,ordinary_cost=normal+adjust,emergency_cost=emergency,total_cost=normal+adjust+emergency,
            order_kwh=float(order.sum()),emergency_kwh=float(execution[di,:,8].sum()),unused_order_kwh=float(execution[di,:,9].sum()),unused_pv_kwh=float(execution[di,:,10].sum())))
        if (di+1)%100==0:event(phase=label,days=di+1,lp_calls=budget.calls)
    folder=O/'strategies';folder.mkdir(exist_ok=True)
    df=pd.DataFrame(daily);df.to_csv(folder/f'{label}.daily.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
    np.savez_compressed(folder/f'{label}.npz',days=days,q0=q0,versions=versions,execution=execution,decision_storage=states)
    pd.DataFrame(checks).to_csv(folder/f'{label}.solver.csv',index=False,float_format='%.17g')
    summary={k:float(df[k].sum()) for k in ('normal_cost','adjustment_cost','ordinary_cost','emergency_cost','total_cost','order_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh')}
    summary.update(label=label,days=334,initial=8592.693560925925,final=state,emergency_days=int((df.emergency_kwh>1e-6).sum()),lp_calls=len(checks),max_residual=max(c['residual'] for c in checks),max_dual_gap=max(c['dual_gap'] for c in checks))
    dump(folder/f'{label}.summary.json',summary);event(phase='complete',**summary)
    return summary

def main():
    protected=[BASE/'core.py',BASE/'outputs/sources.npz',BASE/'outputs/forecasts.npz',BASE/'outputs/error_records.npz',
        FINAL/'outputs/margins/q60_b070_w28_h03.npz',FINAL/'outputs/strategies/M_q60_b070_w28_h03.npz',
        FINAL/'outputs/strategies/M_q60_b070_w28_h03.summary.json',FINAL/'outputs/verification.json',
        P/'questions/Q3/runs/20260911-s2-deepening-v1/deepen.py',P/'state/state.json']
    manifest=json.loads((P/'data/prepared-v1/manifest.json').read_text('utf-8'))
    for name in ('day_reference.csv','actual_power.csv','pv_forecasts.csv'):
        p=P/'data/prepared-v1'/name;assert sha(p)==manifest['outputs'][name]['sha256'];protected.append(p)
    dump(O/'protected_sources.json',{str(p.relative_to(P)):sha(p) for p in protected})
    src=dict(np.load(BASE/'outputs/sources.npz'));fc=dict(np.load(BASE/'outputs/forecasts.npz'))
    # Reconstruct the full arm from raw hourly data before reproducing final trajectories.
    full_hour,w,counts,fb,cut=base.build_fusion(src['actual'],src['F'],fc['H'],src['release'],src['targets'])
    full=base.to_intervals(full_hour,fc['hist'],fc['last'],src['release'])
    assert np.allclose(full,fc['fused'],rtol=0,atol=1e-10,equal_nan=True)
    # No-new arm sees only this day's midnight official forecast. Beyond its coverage,
    # F=H makes fusion exactly historical; no post-midnight official labels/features enter.
    oldF=fc['H'].copy();available=np.zeros_like(oldF,dtype=bool);source_release=np.full_like(oldF,-1,dtype=int)
    for b,r in enumerate(src['release']):
        midnight=r//144*144;t=src['targets'][b];use=t<=midnight+144
        oldF[b,use]=src['F'][(r//144)*4,((t[use]-midnight)//6-1).astype(int)]
        available[b,use]=True;source_release[b,use]=midnight
    old_hour,ow,oc,of,ot=base.build_fusion(src['actual'],oldF,fc['H'],src['release'],src['targets'])
    old=base.to_intervals(old_hour,fc['hist'],fc['last'],src['release'])
    assert np.allclose(old[::4],full[::4],rtol=0,atol=1e-10,equal_nan=True)
    np.savez_compressed(O/'forecasts.npz',full=full,no_new=old,old_official=oldF,available=available,official_source_release=source_release,old_weights=ow,old_fit_cutoff=ot,old_hourly=old_hour)
    err=errors_for(old,src,fc);np.savez_compressed(O/'no_new_errors.npz',**err)
    margin,meta=margin_for(err,src['release']);np.savez_compressed(O/'no_new_margin.npz',values=margin,meta=meta)
    full_margin=np.load(FINAL/'outputs/margins/q60_b070_w28_h03.npz')['values']
    assert np.allclose(margin[::4],full_margin[::4],rtol=0,atol=1e-10,equal_nan=True)
    rows=[run_arm('F0_zero_only',full,full_margin,src,fc),run_arm('F1_no_new',old,margin,src,fc),run_arm('F2_full',full,full_margin,src,fc)]
    oldtrace=np.load(FINAL/'outputs/strategies/M_q60_b070_w28_h03.npz');newtrace=np.load(O/'strategies/F2_full.npz')
    reproduction={k:float(np.max(abs(oldtrace[k]-newtrace[k]))) for k in ('q0','versions','execution','decision_storage')}
    assert max(reproduction.values())<1e-7,reproduction
    pd.DataFrame(rows).to_csv(O/'comparison.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
    dump(O/'summary.json',dict(status='computed_pending_verification',arms=rows,reproduction=reproduction,lp_calls=budget.calls,elapsed_seconds=time.perf_counter()-budget.start,code_sha256=sha(__file__),protocol_sha256=sha(R/'protocol.json')))
if __name__=='__main__':main()
