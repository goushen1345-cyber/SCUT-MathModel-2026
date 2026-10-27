"""Independent read-back of saved Q3 deepening traces; no import from deepen.py."""
from pathlib import Path
from decimal import Decimal, localcontext
from fractions import Fraction
import json, hashlib
import numpy as np
import pandas as pd

R=Path(__file__).resolve().parent;P=R.parents[3];O=R/'outputs';BASE=P/'questions/Q3/runs/20260911-four-candidates-v1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def close(name,a,b,tol=1e-7):
    aa=np.asarray(a);bb=np.asarray(b)
    assert np.array_equal(np.isnan(aa),np.isnan(bb)),(name,'NaN positions differ')
    mask=np.isfinite(aa)&np.isfinite(bb)
    err=float(np.max(abs(aa[mask]-bb[mask]))) if np.any(mask) else 0.
    maxima[name]=max(maxima.get(name,0.),err)
    assert err<=tol,(name,err)
def D(x):return Decimal(str(float(x)))

summary=read(O/'summary.json');assert summary['protocol_sha256']==sha(R/'protocol.json') and summary['code_sha256']==sha(R/'deepen.py')
for name,fingerprint in read(O/'protected_sources.json').items():assert sha(P/name)==fingerprint
src=dict(np.load(BASE/'outputs/sources.npz'));actual=src['actual'];price=src['price'];maxima={};counts={'strategies':0,'actual_intervals':0,'margin_groups':0}

def execute_one(load_kw,pv_kw,order,state):
    load=float(load_kw/6);pv=float(pv_kw/6);order=max(0.,float(order));direct=min(load,pv);need=load-direct;surplus=pv-direct;old=state
    if need>order:
        discharge=min(need-order,5000/6,max(0.,.9*(state-1200)));emergency=max(0.,need-order-discharge);xc=yc=0.;received=order
    else:
        charge=min(surplus+order-need,5000/6,max(0.,(10800-state)/.9));yc=min(surplus,charge);xc=charge-yc;discharge=emergency=0.;received=need+xc
    state=old+.9*(xc+yc)-discharge/.9
    return np.array([old,state,received,received-xc,direct,xc,yc,discharge,emergency,max(0.,order-received),max(0.,surplus-yc),load]),state

for rec in summary['all']:
    if rec['family']=='baseline_reused':continue
    z=dict(np.load(R/rec['trace']));days=z['days'];q0=z['q0'];versions=z['versions'];saved=z['execution'];floor=float(z['floor'])
    assert np.array_equal(days,np.arange(31,365));close('q0',q0,versions[:,0],1e-12)
    for a,start in enumerate([0,36,72,108]):
        if a:
            close('locked_prefix',versions[:,a,:start],versions[:,a-1,:start],1e-12)
            assert np.min(versions[:,a,start:]-floor*q0[:,start:])>=-1e-7
    rows=[];state=float(rec['initial']);total=Decimal(0)
    for di,d in enumerate(days):
        before=state
        rebuilt=np.empty((144,12))
        for a,start in enumerate([0,36,72,108]):
            close('decision_state',z['decision_storage'][di,a],state,1e-7)
            for k in range(start,start+36):
                row,state=execute_one(*actual[d*144+k],versions[di,a,k],state);rebuilt[k]=row
        close('execution',rebuilt,saved[di],1e-6)
        delta=versions[di,3]-q0[di]
        with localcontext() as ctx:
            ctx.prec=40
            ordinary=sum((D(price[k])*D(versions[di,3,k])+Decimal('.5')*D(price[k])*abs(D(delta[k])) for k in range(144)),Decimal(0))
            emergency=sum((Decimal(5)*D(price[k])*D(rebuilt[k,8]) for k in range(144)),Decimal(0))
        rows.append([before,state,float(ordinary),float(emergency),float(ordinary+emergency),float(versions[di,3].sum()),float(rebuilt[:,8].sum()),float(rebuilt[:,9].sum()),float(rebuilt[:,10].sum()),float(np.maximum(-delta,0).sum()),float(np.maximum(delta,0).sum())])
        total+=ordinary+emergency;counts['actual_intervals']+=144
    frame=pd.read_csv(R/rec['daily_csv'],float_precision='round_trip')
    cols=['initial','final','ordinary_cost','emergency_cost','total_cost','order_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh','reduced_kwh','increased_kwh']
    close('daily',frame[cols].to_numpy(),np.array(rows),1e-6)
    close('period_cost',float(total),rec['total_cost'],1e-5);close('final_state',state,rec['final'],1e-7)
    solver=pd.read_csv(R/f'outputs/strategies/{rec["label"]}.solver.csv')
    assert len(solver)==1336 and solver.residual.max()<1e-6 and solver.dual_gap.max()<1e-4 and solver.simultaneous.sum()==0
    counts['strategies']+=1

# Recompute the selected q=.65, beta=.7 allowance with a separate exact rational CDF.
err=dict(np.load(BASE/'outputs/error_records.npz'));rr=err['release'];tt=err['target'];ee=err['error'];kind=err['kind'];group=tt%144//24
releases=src['release'];saved_margin=np.load(O/'margins/q65_b070.npz')['values'];rebuilt=np.full_like(saved_margin,np.nan)
q=Fraction(65,100);beta=Fraction(7,10)
for b,r in enumerate(releases):
    pool=(rr>=r-28*144)&(rr<r)&(tt+1<=r)&(rr%144==r%144);n=288-r%144;tgt=r+np.arange(n);future=(np.arange(n)>=144).astype(int)
    for typ in [0,1]:
        same=pool&(kind==typ)
        for g in range(6):
            dest=(tgt%144//24==g)&(future==typ)
            if not dest.any():continue
            use=same&(group==g)
            if use.sum()<24:use=same
            ids=np.flatnonzero(use);ids=ids[np.argsort(ee[ids],kind='stable')]
            if len(ids)<24:value=0.
            else:
                age=(r-1)//144-tt[ids]//144;amax=int(age.max())
                weights=[beta.numerator**int(a)*beta.denominator**(amax-int(a)) for a in age]
                total=sum(weights);acc=0;ix=len(ids)-1
                for j,w in enumerate(weights):
                    acc+=w
                    if acc*q.denominator>=q.numerator*total:ix=j;break
                value=max(0.,float(ee[ids[ix]]));assert int(np.max(tt[ids]+1))<=r
            rebuilt[b,:n][dest]=value;counts['margin_groups']+=1
close('selected_margin',rebuilt,saved_margin,1e-10)
assert summary['selected']['label']==min(summary['all'],key=lambda x:x['total_cost'])['label']
result=dict(status='checks_completed',counts=counts,max_errors=maxima,new_lp_calls=0,new_fits=0,
    selected=summary['selected']['label'],selected_cost=summary['selected']['total_cost'],
    reviewer='same AI, separate saved-result reconstruction; not human approval',code_sha256=sha(__file__))
(O/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
