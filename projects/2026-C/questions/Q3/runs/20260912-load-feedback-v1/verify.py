"""Read-only reconstruction of predictions, preparations, physical traces and bills."""
from pathlib import Path
from decimal import Decimal,localcontext
import json,hashlib
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parent;P=R.parents[3];O=R/'outputs'
B=P/'questions/Q3/runs/20260911-four-candidates-v1/outputs';I=P/'questions/Q3/runs/20260912-final-information-v1/outputs'
read=lambda p:json.loads(Path(p).read_text('utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
src=dict(np.load(B/'sources.npz'));fc=dict(np.load(B/'forecasts.npz'));pv=dict(np.load(I/'forecasts.npz'))
summary=read(O/'summary.json');maximum={};counts=dict(strategies=0,actual_intervals=0,regression_groups=0,margin_groups=0)
assert summary['code_sha256']==sha(R/'run.py') and summary['protocol_sha256']==sha(R/'protocol.json')
for path,value in read(O/'protected_sources.json').items():assert sha(P/path)==value,path
def check(name,x,y,tol=1e-7):
    x=np.asarray(x);y=np.asarray(y);assert x.shape==y.shape,(name,x.shape,y.shape)
    assert np.array_equal(np.isnan(x),np.isnan(y)),name
    finite=np.isfinite(x)&np.isfinite(y);v=float(np.max(abs(x[finite]-y[finite]))) if finite.any() else 0.
    maximum[name]=max(maximum.get(name,0),v);assert v<=tol,(name,v)
def D(x):return Decimal(str(float(x)))
def execute(l,v,q,s):
    l=float(l/6);v=float(v/6);m=min(l,v);need=l-m;extra=v-m;before=s
    if need>q:
        z=min(need-q,5000/6,max(0.,.9*(s-1200)));e=max(0.,need-q-z);x=y=0.;received=q
    else:
        charge=min(extra+q-need,5000/6,max(0.,(10800-s)/.9));y=min(extra,charge);x=charge-y;z=e=0.;received=need+x
    s+=.9*(x+y)-z/.9
    return np.array([before,s,received,received-x,m,x,y,z,e,max(0.,q-received),max(0.,extra-y),l]),s
records=summary['candidates']+([summary['no_new_control']] if summary['no_new_control'] else [])
baseline=summary['baseline'];baseline_daily=pd.read_csv(I/'strategies/F2_full.daily.csv',float_precision='round_trip')
analyses={};allframes={};coeff_summary={}
for record in records:
    label=record['label'];path=O/f'strategies/{label}';forecast=dict(np.load(str(path)+'.forecast.npz'));loads=forecast['load'];theta=forecast['theta']
    residual=src['actual'][:365*144,0].reshape(365,144)-fc['L'][:,:144]
    for d in range(365):
        for a,slot in enumerate((0,36,72,108)):
            n=288-slot;b=d*4+a;expected=fc['L'][d,slot:].copy()
            if slot:
                begin=0 if 'PREFIX' in record['kind'] else slot-18
                known=residual[d,begin:slot];xnow=np.nanmean(known) if np.isfinite(known).any() else 0.
                check('observed_prefix',np.asarray(xnow),forecast['observed'][d,a],1e-10)
                for g in range(slot//18,8):
                    pairs=[]
                    for past in range(max(0,d-28),d):
                        assert past*144+(g+1)*18<=d*144+slot
                        x=np.nanmean(residual[past,begin:slot]);y=np.mean(residual[past,g*18:(g+1)*18])
                        if np.isfinite(x) and np.isfinite(y):pairs.append((x,y))
                    if record['kind']=='PERSIST_PREFIX':coef=1.
                    elif len(pairs)<7:coef=0.
                    else:
                        arr=np.array(pairs);den=float(arr[:,0]@arr[:,0]);coef=float(np.clip((arr[:,0]@arr[:,1])/den,0,1)) if den>1e-12 else 0.
                    assert forecast['count'][d,a,g]==len(pairs)
                    check('regression_coefficient',np.asarray(coef),theta[d,a,g],1e-12)
                    left=g*18-slot;expected[left:left+18]=np.maximum(0,expected[left:left+18]+record['gain']*coef*xnow)
                    counts['regression_groups']+=1
            check('load_prediction',expected,loads[b,:n],1e-10)
            check('next_day_unchanged',loads[b,144-slot:n],fc['L'][d,144:],0)
    coef_rows=[]
    for a,slot in enumerate((36,72,108),1):
        vals=theta[31:,a,slot//18:8]
        coef_rows.append(dict(hour=slot/6,mean=float(vals.mean()),median=float(np.median(vals)),zero_fraction=float((vals==0).mean()),one_fraction=float((vals==1).mean())))
    coeff_summary[label]=coef_rows
    err=dict(np.load(str(path)+'.errors.npz'));rr,tt,ee,kind=(err[k] for k in ('release','target','error','kind'))
    expected=((src['actual'][tt,0]-src['actual'][tt,1])-(loads[rr//36,tt-rr]-pv[record['pvkey']][rr//36,tt-rr]))/6
    check('own_net_error',expected,ee,1e-10)
    margin=np.load(str(path)+'.margin.npz')['values']
    for b,r in enumerate(src['release']):
        n=288-r%144;targets=r+np.arange(n);pool=(rr>=r-4032)&(rr<r)&(tt+1<=r)&(rr%144==r%144)
        for typ in (0,1):
            same=pool&(kind==typ)
            for g in range(8):
                dest=(targets%144//18==g)&((np.arange(n)>=144)==bool(typ))
                if not dest.any():continue
                use=same&(tt%144//18==g)
                if use.sum()<24:use=same
                ids=np.flatnonzero(use);ids=ids[np.argsort(ee[ids],kind='stable')]
                if len(ids)<24:value=0.
                else:
                    ages=(r-1)//144-tt[ids]//144;ma=int(ages.max());weights=[7**int(age)*10**(ma-int(age)) for age in ages]
                    total=sum(weights);acc=0;value=None
                    for ix,w in enumerate(weights):
                        prev=acc;acc+=w
                        if 5*acc>=3*total:
                            assert 5*prev<3*total;value=max(0.,float(ee[ids[ix]]));break
                check('own_preparation',margin[b,:n][dest],np.full(dest.sum(),value),1e-10);counts['margin_groups']+=1
    tr=dict(np.load(str(path)+'.npz'));df=pd.read_csv(str(path)+'.daily.csv',float_precision='round_trip')
    assert np.array_equal(tr['days'],np.arange(31,365));check('zero_plan',tr['q0'],tr['versions'][:,0],0)
    for a,slot in enumerate((36,72,108),1):check('locked_prefix',tr['versions'][:,a,:slot],tr['versions'][:,a-1,:slot],0)
    state=record['initial'];total=Decimal(0)
    for i,d in enumerate(tr['days']):
        before=state;rows=[]
        for k in range(144):
            if k%36==0:check('decision_stock',np.asarray(state),tr['decision_storage'][i,k//36],1e-7)
            row,state=execute(*src['actual'][d*144+k],tr['versions'][i,k//36,k],state);rows.append(row)
        rows=np.asarray(rows);check('execution',rows,tr['execution'][i],1e-6)
        assert rows[:,1].min()>=1200-1e-7 and rows[:,1].max()<=10800+1e-7
        assert (rows[:,5]+rows[:,6]).max()<=5000/6+1e-7 and rows[:,7].max()<=5000/6+1e-7
        check('balance',rows[:,3]+rows[:,4]+rows[:,7]+rows[:,8],rows[:,11])
        q=tr['versions'][i,3];delta=q-tr['q0'][i]
        with localcontext() as c:
            c.prec=40
            normal=sum((D(p)*D(v) for p,v in zip(src['price'],q)),Decimal(0))
            adjust=sum((Decimal('.5')*D(p)*abs(D(v)) for p,v in zip(src['price'],delta)),Decimal(0))
            emergency=sum((Decimal(5)*D(p)*D(v) for p,v in zip(src['price'],rows[:,8])),Decimal(0))
        cost=normal+adjust+emergency;total+=cost
        check('daily_cost',np.array([float(normal),float(adjust),float(emergency),float(cost)]),df.loc[i,['normal_cost','adjustment_cost','emergency_cost','total_cost']].to_numpy(float),1e-6)
        check('cross_day',np.array([before,state]),df.loc[i,['initial','final']].to_numpy(float),1e-7);counts['actual_intervals']+=144
    check('total_bill',np.asarray(float(total)),np.asarray(record['total_cost']),1e-5)
    check('terminal_stock',np.asarray(state),np.asarray(record['final']),1e-7)
    solver=pd.read_csv(str(path)+'.solver.csv');assert len(solver)==1336 and solver.residual.max()<1e-6 and solver.dual_gap.max()<1e-4 and solver.simultaneous.sum()==0
    diff=baseline_daily.total_cost-df.total_cost;monthly=diff.groupby(pd.to_datetime(df.date).dt.month).sum()
    analyses[label]=dict(saving=baseline['total_cost']-record['total_cost'],percent=100*(baseline['total_cost']-record['total_cost'])/baseline['total_cost'],cheaper_days=int((diff>1e-6).sum()),costlier_days=int((diff< -1e-6).sum()),tied_days=int((abs(diff)<=1e-6).sum()),monthly_saving={str(k):float(v) for k,v in monthly.items()},max_saving=float(diff.max()),max_saving_date=str(df.loc[diff.idxmax(),'date']),max_increase=float(-diff.min()),max_increase_date=str(df.loc[diff.idxmin(),'date']),terminal_stock_difference=record['final']-baseline['final'],saving_with_terminal_reference=baseline['total_cost']-record['total_cost']+.9*src['price'][0]*(record['final']-baseline['final']))
    emergency_series=tr['execution'][:,:,8].ravel();flags=emergency_series>1e-6
    switches=np.flatnonzero(np.diff(np.r_[False,flags,False].astype(int)))
    longest=int(np.max(switches[1::2]-switches[::2]))*10 if len(switches) else 0
    analyses[label].update(max_emergency_interval_kwh=float(emergency_series.max()),max_emergency_day_kwh=float(df.emergency_kwh.max()),longest_emergency_minutes=longest,max_daily_cost=float(df.total_cost.max()))
    allframes[label]=df;counts['strategies']+=1
    print(json.dumps(dict(verified=label,**analyses[label]),ensure_ascii=False),flush=True)
information=None
if summary['no_new_control']:
    winner=summary['winner'];no=summary['no_new_control'];diff=allframes[no['label']].total_cost-allframes[winner['label']].total_cost
    information=dict(zero_only_cost=read(I/'strategies/F0_zero_only.summary.json')['total_cost'],no_new_cost=no['total_cost'],full_cost=winner['total_cost'],new_PV_saving=no['total_cost']-winner['total_cost'],new_PV_saving_percent=100*(no['total_cost']-winner['total_cost'])/no['total_cost'],cheaper_days=int((diff>1e-6).sum()),costlier_days=int((diff< -1e-6).sum()),terminal_stock_difference=winner['final']-no['final'])
result=dict(status='verified_by_AI_not_human_approval',counts=counts,max_errors=maximum,candidate_analysis=analyses,coefficient_summary=coeff_summary,updated_information_comparison=information,new_lp_calls=0,code_sha256=sha(__file__))
(O/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status=result['status'],counts=counts,max_errors=maximum,information=information),ensure_ascii=False))
