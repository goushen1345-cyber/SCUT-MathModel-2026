"""Independent saved-array information, physical and settlement checks; no solver."""
from pathlib import Path
from decimal import Decimal, localcontext
import json, hashlib
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parent;P=R.parents[3];O=R/'outputs'
B=P/'questions/Q3/runs/20260911-four-candidates-v1/outputs'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text('utf-8'))
maxima={};counts=dict(actual_intervals=0,fusion_groups=0,margin_groups=0)
def check(name,x,y,tol=1e-7):
    x=np.asarray(x);y=np.asarray(y);assert x.shape==y.shape,(name,x.shape,y.shape)
    assert np.array_equal(np.isnan(x),np.isnan(y)),name
    mask=np.isfinite(x)&np.isfinite(y);e=float(np.max(abs(x[mask]-y[mask]))) if mask.any() else 0.
    maxima[name]=max(maxima.get(name,0),e);assert e<=tol,(name,e)
def D(x):return Decimal(str(float(x)))
src=dict(np.load(B/'sources.npz'));orig=dict(np.load(B/'forecasts.npz'));fc=dict(np.load(O/'forecasts.npz'))
summary=read(O/'summary.json')
assert summary['protocol_sha256']==sha(R/'protocol.json') and summary['code_sha256']==sha(R/'run.py')
for p,h in read(O/'protected_sources.json').items():assert sha(P/p)==h,p

# All no-new official values come from that calendar day's midnight release.
for b,r in enumerate(src['release']):
    targets=src['targets'][b];midnight=r//144*144;avail=targets<=midnight+144
    assert np.array_equal(fc['available'][b],avail)
    assert np.all(fc['official_source_release'][b,avail]==midnight)
    assert np.all(fc['official_source_release'][b,~avail]==-1)
    official=orig['H'][b].copy()
    for j,t in enumerate(targets):
        if avail[j]:official[j]=src['F'][(r//144)*4,int((t-midnight)//6-1)]
    check('official_provenance',fc['old_official'][b],official,0)
    hist=np.empty(144)
    for k in range(144):
        indices=np.arange(k if k else 144,r,144,dtype=int)[-7:]
        hist[k]=src['actual'][indices,1].mean() if len(indices) else src['reference'][k,1]
    check('causal_history',orig['hist'][b],hist,1e-10)

rr=np.repeat(src['release'],24);tt=src['targets'].ravel();ff=fc['old_official'].ravel();hh=orig['H'].ravel()
truth=np.full(len(tt),np.nan);valid=tt<365*144;truth[valid]=src['actual'][tt[valid],1]
lead=np.tile(np.arange(24)//6,1460)
for b,r in enumerate(src['release']):
    pool=(rr>=r-4032)&(rr<r)&(tt<r)&(rr%144==r%144)&np.isfinite(truth)
    weights=[]
    for g in range(4):
        use=pool&(lead==g)
        if use.sum()<24:use=pool
        x=ff[use]-hh[use];y=truth[use]-hh[use]
        w=1. if use.sum()<24 or x@x<1e-12 else float(np.clip((x@y)/(x@x),0,1))
        weights.append(w);counts['fusion_groups']+=1
        assert fc['old_fit_cutoff'][b,g]<=r
    check('fusion_weights',fc['old_weights'][b],np.asarray(weights),1e-12)
    hourly=np.repeat(weights,6)*fc['old_official'][b]+(1-np.repeat(weights,6))*orig['H'][b]
    check('fused_hourly',fc['old_hourly'][b],hourly,1e-10)
    n=288-r%144;targets=r+np.arange(n);rebuilt=orig['hist'][b,targets%144].copy()
    rebuilt[:144]=np.interp(np.arange(144),np.arange(25)*6,np.r_[orig['last'][b],hourly])
    check('interpolation',fc['no_new'][b,:n],rebuilt,1e-10)

errors=dict(np.load(O/'no_new_errors.npz'));er,et,ev,kind=(errors[k] for k in ('release','target','error','kind'))
expected=((src['actual'][et,0]-src['actual'][et,1])-(orig['L'][er//144,et-er//144*144]-fc['no_new'][er//36,et-er]))/6
check('own_forecast_errors',ev,expected,1e-10)
assert np.all(et>0) and np.all(et<365*144)
margin=np.load(O/'no_new_margin.npz')['values']
for b,r in enumerate(src['release']):
    n=288-r%144;target=r+np.arange(n)
    pool=(er>=r-4032)&(er<r)&(et+1<=r)&(er%144==r%144)
    for typ in (0,1):
        same=pool&(kind==typ)
        for g in range(8):
            dest=(target%144//18==g)&((np.arange(n)>=144)==bool(typ))
            if not dest.any():continue
            use=same&(et%144//18==g)
            if use.sum()<24:use=same
            ids=np.flatnonzero(use);ids=ids[np.argsort(ev[ids],kind='stable')]
            if len(ids)<24:q=0.
            else:
                ages=(r-1)//144-et[ids]//144;ma=int(ages.max())
                weights=[7**int(a)*10**(ma-int(a)) for a in ages]
                total=sum(weights);cumulative=0;q=None
                for index,w in enumerate(weights):
                    prior=cumulative;cumulative+=w
                    if 5*cumulative>=3*total:
                        assert 5*prior<3*total;q=max(0.,float(ev[ids[index]]));break
            check('own_margin',margin[b,:n][dest],np.full(dest.sum(),q),1e-10);counts['margin_groups']+=1

def execute(load,pv,order,state):
    l=load/6;v=pv/6;direct=min(l,v);need=l-direct;surplus=v-direct;before=state
    if need>order:
        z=min(need-order,5000/6,.9*(state-1200));e=max(0.,need-order-z);x=y=0.;received=order
    else:
        charge=min(surplus+order-need,5000/6,(10800-state)/.9)
        y=min(surplus,charge);x=charge-y;z=e=0.;received=need+x
    state+=.9*(x+y)-z/.9
    return np.array([before,state,received,received-x,direct,x,y,z,e,max(0.,order-received),max(0.,surplus-y),l]),state

daily_frames={}
for record in summary['arms']:
    name=record['label'];tr=dict(np.load(O/f'strategies/{name}.npz'));df=pd.read_csv(O/f'strategies/{name}.daily.csv',float_precision='round_trip')
    assert np.array_equal(tr['days'],np.arange(31,365));check('midnight_order',tr['q0'],tr['versions'][:,0],0)
    for a,slot in enumerate((0,36,72,108)):
        if a:check('locked_prefix',tr['versions'][:,a,:slot],tr['versions'][:,a-1,:slot],0)
        if name=='F0_zero_only':check('all_day_lock',tr['versions'][:,a],tr['q0'],0)
    state=record['initial'];total=Decimal(0)
    for i,d in enumerate(tr['days']):
        before=state;rebuild=[]
        for k in range(144):
            if k%36==0:check('decision_storage',np.asarray(state),tr['decision_storage'][i,k//36])
            row,state=execute(*src['actual'][d*144+k],tr['versions'][i,k//36,k],state);rebuild.append(row)
        rebuild=np.asarray(rebuild);check('execution',rebuild,tr['execution'][i],1e-6)
        assert rebuild[:,1].min()>=1200-1e-7 and rebuild[:,1].max()<=10800+1e-7
        assert np.max(rebuild[:,5]+rebuild[:,6])<=5000/6+1e-7 and np.max(rebuild[:,7])<=5000/6+1e-7
        check('energy_balance',rebuild[:,3]+rebuild[:,4]+rebuild[:,7]+rebuild[:,8],rebuild[:,11])
        q=tr['versions'][i,3];delta=q-tr['q0'][i]
        with localcontext() as context:
            context.prec=40
            normal=sum((D(p)*D(v) for p,v in zip(src['price'],q)),Decimal(0))
            adjust=sum((Decimal('.5')*D(p)*abs(D(v)) for p,v in zip(src['price'],delta)),Decimal(0))
            emergency=sum((Decimal(5)*D(p)*D(v) for p,v in zip(src['price'],rebuild[:,8])),Decimal(0))
        cost=normal+adjust+emergency;total+=cost
        check('daily_cost',np.array([float(normal),float(adjust),float(emergency),float(cost)]),df.loc[i,['normal_cost','adjustment_cost','emergency_cost','total_cost']].to_numpy(float),1e-6)
        check('cross_day',np.array([before,state]),df.loc[i,['initial','final']].to_numpy(float),1e-7)
        counts['actual_intervals']+=144
    check('total_bill',np.asarray(float(total)),np.asarray(record['total_cost']),1e-5)
    check('terminal_inventory',np.asarray(state),np.asarray(record['final']),1e-7)
    solver=pd.read_csv(O/f'strategies/{name}.solver.csv');assert len(solver)==(334 if name=='F0_zero_only' else 1336)
    assert solver.residual.max()<1e-6 and solver.dual_gap.max()<1e-4 and solver.simultaneous.sum()==0
    daily_frames[name]=df

contrasts={}
for before,after in [('F0_zero_only','F1_no_new'),('F1_no_new','F2_full'),('F0_zero_only','F2_full')]:
    a=next(x for x in summary['arms'] if x['label']==before);b=next(x for x in summary['arms'] if x['label']==after)
    diff=daily_frames[before].total_cost-daily_frames[after].total_cost
    monthly=diff.groupby(pd.to_datetime(daily_frames[before].date).dt.month).sum()
    terminal_credit=.9*src['price'][0]*(b['final']-a['final'])
    contrasts[before+'__'+after]=dict(saving=a['total_cost']-b['total_cost'],saving_percent=100*(a['total_cost']-b['total_cost'])/a['total_cost'],
        emergency_kwh_reduction=a['emergency_kwh']-b['emergency_kwh'],unused_order_reduction=a['unused_order_kwh']-b['unused_order_kwh'],
        cheaper_days=int((diff>1e-6).sum()),costlier_days=int((diff< -1e-6).sum()),tied_days=int((abs(diff)<=1e-6).sum()),
        monthly_saving={str(k):float(v) for k,v in monthly.items()},max_saving=float(diff.max()),max_saving_date=str(daily_frames[before].loc[diff.idxmax(),'date']),
        max_increase=float(-diff.min()),max_increase_date=str(daily_frames[before].loc[diff.idxmin(),'date']),
        terminal_stock_credit=terminal_credit,saving_with_terminal_reference=a['total_cost']-b['total_cost']+terminal_credit)
out=dict(status='saved_outputs_verified_by_AI_not_human_approval',counts=counts,max_errors=maxima,contrasts=contrasts,code_sha256=sha(__file__),new_lp_calls=0)
(O/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
