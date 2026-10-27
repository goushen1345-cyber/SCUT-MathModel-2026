"""Independent readback: no imports from core/run_compare and no model fitting/solve."""
import os
for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[n]='1'
from pathlib import Path
from datetime import datetime,timedelta
from decimal import Decimal,getcontext
from functools import lru_cache
import hashlib,json,math,re
import numpy as np
import pandas as pd
import joblib
from threadpoolctl import threadpool_limits
R=Path(__file__).resolve().parent;P=R.parents[3];O=R/'outputs';getcontext().prec=40
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
lines=lambda n:[json.loads(z) for z in (O/(n+'.jsonl')).read_text(encoding='utf-8').splitlines()]
for rel,h in read(O/'source_hashes.json').items():assert sha(P/rel)==h,rel
for rel,h in read(O/'output_hashes.json').items():assert sha(O/rel)==h,rel
summary=read(O/'summary.json');env=read(O/'environment.json')
assert env['protocol_sha256']==sha(R/'protocol.json')
for n,h in env['code_sha256'].items():assert sha(R/n)==h,n
raw=pd.read_csv(P/'data/prepared-v1/actual_power.csv',float_precision='round_trip')
base=datetime(2025,1,1);A={v:np.full((181,144),np.nan) for v in ['load','pv']}
for r in raw.itertuples(index=False):
    t=datetime.fromisoformat(r.source_date)+timedelta(minutes=int(r.source_minute));d=(t.date()-base.date()).days
    if d<181:
        k=t.hour*6+t.minute//10;A['load'][d,k]=r.load_kw;A['pv'][d,k]=r.pv_actual_kw
ref=pd.read_csv(P/'data/prepared-v1/day_reference.csv',float_precision='round_trip')
ref.index=(ref.source_minute%1440//10).astype(int);ref=ref.sort_index()
fallback={'load':ref.load_kw.to_numpy(),'pv':ref.pv_forecast_kw.to_numpy()};prices=ref.price_yuan_per_kwh.to_numpy()
date=lambda d:str((base+timedelta(days=int(d))).date())
day=lambda s:(datetime.fromisoformat(s).date()-base.date()).days
@lru_cache(None)
def mean(var,d,h,mode,n):
    dates=[d+h-7*j for j in range(1,n+1) if 0<=d+h-7*j<d] if mode=='week' else list(range(max(0,d-n),d))
    if not dates:dates=list(range(max(0,d-7),d))
    ans=[]
    for k in range(144):
        values=[float(A[var][i,k]) for i in dates if math.isfinite(A[var][i,k])]
        ans.append(math.fsum(values)/len(values) if values else fallback[var][k])
    return np.array(ans)
@lru_cache(None)
def features(var,d,h):
    k=np.arange(144);t=2*np.pi*k/144;target=base+timedelta(days=d+h);doy=target.timetuple().tm_yday
    cols=[np.sin(t),np.cos(t),np.sin(2*t),np.cos(2*t)]
    cols.extend([np.full(144,int(target.weekday()==i)) for i in range(7)])
    cols.extend([np.full(144,h+1),np.full(144,np.sin(2*np.pi*doy/365)),np.full(144,np.cos(2*np.pi*doy/365))])
    cols.extend([mean(var,d,h,'recent',1),mean(var,d,h,'recent',3),mean(var,d,h,'recent',7),
                 mean(var,d,h,'week',1),mean(var,d,h,'week',4)])
    cols.extend([np.full(144,np.nanmean(A[var][d-1])),np.full(144,np.nanmean(A[var][max(0,d-7):d]))])
    return np.column_stack(cols)

bank=np.load(O/'feature_bank.npz');feature_error=0.
for var in ['load','pv']:
    X=bank[var+'_X'];Y=bank[var+'_y']
    for origin in np.unique(bank['origins']):
        for target in [origin,origin+1]:
            mask=(bank['origins']==origin)&(bank['targets']==target)
            if not mask.any():continue
            feature_error=max(feature_error,float(np.max(abs(X[mask]-features(var,int(origin),int(target-origin))))))
            assert np.max(abs(Y[mask]-A[var][target]))<1e-9
assert feature_error<1e-8
fitlog=lines('fit_log');normal_errors=[]
for fit in fitlog:
    d=day(fit['cutoff']);mask=(bank['origins']>=max(2,d-56))&(bank['targets']<d)
    assert int(mask.sum())==fit['n_rows'] and day(fit['latest_target_end'][:10])<=d
    assert np.max(bank['targets'][mask])<d
    if fit['model']=='T2':
        X=bank[fit['variable']+'_X'][mask];y=bank[fit['variable']+'_y'][mask]
        assert np.max(abs(X.mean(axis=0)-np.array(fit['feature_means'])))<1e-8
        Z=(X-fit['feature_means'])/fit['feature_scales'];b=np.array(fit['coefficients_standardized']);yc=y-y.mean()
        rhs=Z.T@yc;err=np.linalg.norm((Z.T@Z+fit['hyperparameter']*np.eye(Z.shape[1]))@b-rhs)/max(1.,np.linalg.norm(rhs))
        normal_errors.append(float(err));assert err<1e-7 and abs(fit['intercept_standardized']-y.mean())<1e-7

exe=pd.read_csv(O/'execution.csv.gz',float_precision='round_trip')
plan=pd.read_csv(O/'forecast_plans.csv.gz',float_precision='round_trip')
daily=pd.read_csv(O/'daily_metrics.csv',float_precision='round_trip')
assert len(exe)==943*144 and len(plan)==942*288
keys=['phase','variant','decision_date'];assert not exe.duplicated(keys+['slot']).any()
assert (exe.groupby(keys).size()==144).all() and (plan.groupby(keys).size()==288).all()
assert set(exe[exe.phase=='comparison'].variant)=={'T1','T2','T3','T4'}
assert (exe[exe.phase=='comparison'].groupby('variant').decision_date.nunique()==150).all()
assert exe.initialization_reference.sum()==1
L=A['load'][exe.day.to_numpy(),exe.slot.to_numpy()].copy();V=A['pv'][exe.day.to_numpy(),exe.slot.to_numpy()].copy()
L[np.isnan(L)]=fallback['load'][0];V[np.isnan(V)]=fallback['pv'][0]
assert np.max(abs(exe.load_kw-L))<1e-8 and np.max(abs(exe.pv_kw-V))<1e-8
assert np.max(abs(exe.price-prices[exe.slot.to_numpy()]))<1e-12
c=exe.grid_charge_kwh+exe.pv_charge_kwh;z=exe.discharge_kwh;s0=exe.storage_start_kwh;s1=exe.storage_end_kwh
res={
 'actual_load_balance':float(abs(exe.direct_pv_kwh+exe.grid_to_load_kwh+z+exe.emergency_kwh-exe.load_kw/6).max()),
 'actual_storage_update':float(abs(s1-s0-.9*c+z/.9).max()),
 'grid_split':float(abs(exe.received_kwh-exe.grid_to_load_kwh-exe.grid_charge_kwh).max()),
 'contract_split':float(abs(exe.order_kwh-exe.received_kwh-exe.unused_order_kwh).max()),
 'pv_split':float(abs(exe.pv_kw/6-exe.direct_pv_kwh-exe.pv_charge_kwh-exe.unused_pv_kwh).max())}
assert max(res.values())<1e-6
assert min(s0.min(),s1.min())>=1200-1e-6 and max(s0.max(),s1.max())<=10800+1e-6
assert c.max()<=5000/6+1e-6 and z.max()<=5000/6+1e-6 and not ((c>1e-6)&(z>1e-6)).any()
for n in ['order_kwh','received_kwh','grid_to_load_kwh','grid_charge_kwh','pv_charge_kwh','discharge_kwh',
           'emergency_kwh','unused_order_kwh','unused_pv_kwh']:assert exe[n].min()>-1e-6,n
need=np.maximum((L-V)/6,0);surplus=np.maximum((V-L)/6,0);deficit=np.maximum(need-exe.order_kwh,0)
expected_discharge=np.minimum.reduce([deficit,np.full(len(exe),5000/6),np.maximum(.9*(s0-1200),0)])
expected_charge=np.where(deficit>0,0,np.minimum.reduce([surplus+np.maximum(exe.order_kwh-need,0),np.full(len(exe),5000/6),np.maximum((10800-s0)/.9,0)]))
assert np.max(abs(z-expected_discharge))<1e-6 and np.max(abs(c-expected_charge))<1e-6
assert np.max(abs(exe.pv_charge_kwh-np.minimum(surplus,expected_charge)))<1e-6
assert np.max(abs(exe.emergency_kwh-(deficit-expected_discharge)))<1e-6
for key,g in exe.groupby(['phase','variant'],sort=False):
    assert np.max(abs(g.storage_start_kwh.to_numpy()[1:]-g.storage_end_kwh.to_numpy()[:-1]))<1e-6,key
init=read(O/'initialization.json')
for key,g in exe.groupby(['phase','variant'],sort=False):
    start={'initialization':6000.,'tuning':init['jan8_initial'],'comparison':init['feb1_initial']}[key[0]]
    assert abs(g.storage_start_kwh.iloc[0]-start)<1e-6
assert abs(init['feb1_initial']-exe[(exe.phase=='initialization')&(exe.day==30)].storage_end_kwh.iloc[-1])<1e-6
q1=pd.read_csv(P/'questions/Q1/runs/20260911-compare-v1/outputs/schedules/C04.csv',float_precision='round_trip')
assert np.max(abs(exe[(exe.phase=='initialization')&(exe.day==0)].order_kwh.to_numpy()-q1.purchase_kwh.to_numpy()))<1e-8
joined=exe[exe.day>0].merge(plan[plan.committed==1][keys+['slot','planned_order_kwh']],on=keys+['slot'],validate='one_to_one')
assert len(joined)==942*144 and np.max(abs(joined.order_kwh-joined.planned_order_kwh))<1e-8

sel=read(O/'january_selection.json')['selected'];registry={(r['kind'],r['parameter'],r['decision_date']):r for r in lines('forecast_registry')}
model_cache={};pred_error=0.;planner_error=0.;prediction_slots=0
for (phase,variant,date0),g in plan.groupby(keys,sort=False):
    d=day(date0);g=g.sort_values('horizon_slot');kind='T1' if variant=='common' else variant.split('-')[0]
    if kind in ['T1','T4']:
        if variant=='common':w,p=1,3
        elif kind=='T4' or phase=='comparison':w,p=sel['T1']
        else:w,p=map(int,re.findall(r'\d+',variant)[1:])
        predL=np.concatenate([mean('load',d,h,'week',w) for h in [0,1]])
        predV=np.concatenate([mean('pv',d,h,'recent',p) for h in [0,1]])
    else:
        param=int(variant.split('-')[1]) if phase=='tuning' else sel[kind]
        fitid=registry[(kind,str(param),date0)]['fit_id'];preds=[]
        for var in ['load','pv']:
            file=f'{fitid}-{var}.joblib'
            if file not in model_cache:model_cache[file]=joblib.load(O/'models'/file)
            fitted=model_cache[file];X=np.vstack([features(var,d,h) for h in [0,1]])
            scaled=fitted['scaler'].transform(X) if fitted['scaler'] is not None else X
            with threadpool_limits(limits=1):pred=np.maximum(fitted['model'].predict(scaled),0)
            if var=='pv':pred*=np.tile(np.any(A['pv'][max(0,d-28):d]>0,axis=0),2)
            preds.append(pred)
        predL,predV=preds
    pred_error=max(pred_error,float(np.max(abs(predL-g.load_forecast_kw))),float(np.max(abs(predV-g.pv_forecast_kw))))
    prediction_slots+=576
    net=np.maximum((g.load_forecast_kw-g.pv_forecast_kw)/6+g.risk_allowance_kwh,0)
    excess=np.maximum((g.pv_forecast_kw-g.load_forecast_kw)/6-g.risk_allowance_kwh,0)
    pc=g.planned_grid_charge_kwh+g.planned_pv_charge_kwh;pz=g.planned_discharge_kwh;ps=g.planned_storage_end_kwh.to_numpy()
    pstart=np.r_[g.planned_initial_storage_kwh.iloc[0],ps[:-1]]
    planner_error=max(planner_error,float(np.max(abs(g.planned_order_kwh-net+pz-g.planned_grid_charge_kwh))),
                      float(np.max(abs(ps-pstart-.9*pc+pz/.9))))
    assert np.min(g.planned_pv_charge_kwh)>=-1e-6 and np.max(g.planned_pv_charge_kwh-excess)<1e-6
    assert np.max(pz-net)<1e-6 and pc.max()<=5000/6+1e-6 and pz.max()<=5000/6+1e-6
    assert ps.min()>=1200-1e-6 and ps.max()<=10800+1e-6 and not ((pc>1e-6)&(pz>1e-6)).any()
assert pred_error<1e-7 and planner_error<1e-6

archive=pd.read_csv(O/'historical_risk_errors.csv.gz',float_precision='round_trip').pivot(index='day',columns='slot',values='error_kwh')
for d,row in archive.iterrows():
    expected=(A['load'][d]-A['pv'][d]-mean('load',int(d),0,'week',sel['T1'][0])+mean('pv',int(d),0,'recent',sel['T1'][1]))/6
    assert np.max(abs(row.to_numpy()-expected))<1e-8
margin_error=0.
for m in lines('risk_margins'):
    d=day(m['decision_date']);days=list(range(max(1,d-28),d));group=m['group']
    if len(days)<7:value=0.
    else:
        pool=archive.loc[days].to_numpy();values=pool[:,group*24:(group+1)*24].ravel() if len(days)>=14 else pool.ravel()
        value=max(0.,float(np.quantile(values,m['quantile'])))
    margin_error=max(margin_error,abs(value-m['allowance_kwh']))
    applied=plan[(plan.phase==m['phase'])&(plan.variant==m['variant'])&(plan.decision_date==m['decision_date'])]
    applied=applied[applied.slot.between(group*24,(group+1)*24-1)]
    assert len(applied)==48 and np.max(abs(applied.risk_allowance_kwh-value))<1e-7
assert margin_error<1e-7

decimal_totals={};cost_difference=0.
for (phase,variant),g in exe.groupby(['phase','variant'],sort=False):
    ordinary=sum((Decimal(str(r.price))*Decimal(str(r.order_kwh)) for r in g.itertuples()),Decimal(0))
    emergency=sum((Decimal(5)*Decimal(str(r.price))*Decimal(str(r.emergency_kwh)) for r in g.itertuples()),Decimal(0))
    expected=daily[(daily.phase==phase)&(daily.variant==variant)].total_cost.sum()
    cost_difference=max(cost_difference,abs(float(ordinary+emergency)-expected))
    decimal_totals[phase+'/'+variant]={'ordinary':str(ordinary),'emergency':str(emergency),'total':str(ordinary+emergency)}
assert cost_difference<1e-5
for kind in ['T1','T2','T3','T4']:
    candidates={k:float(v['total']) for k,v in decimal_totals.items() if k.startswith('tuning/'+kind+'-')}
    winner=min(candidates,key=candidates.get).split('/')[1]
    selected=sel[kind]
    expected=f'T1-w{selected[0]}-p{selected[1]}' if kind=='T1' else f'T4-q{int(selected*100)}' if kind=='T4' else f'{kind}-{selected}'
    assert winner==expected
checks=lines('solver_checks');assert len(checks)==942 and all(c['status']==0 for c in checks)
result={'status':'passed','actual_intervals_checked':len(exe),'planned_intervals_checked':len(plan),
        'forecast_values_recomputed':prediction_slots,'fitted_models_information_checked':len(fitlog),
        'max_feature_difference':feature_error,'max_prediction_difference_kw':pred_error,
        'max_ridge_normal_equation_relative_residual':max(normal_errors),'actual_constraint_residuals':res,
        'max_plan_equation_residual':planner_error,'max_risk_margin_difference_kwh':margin_error,
        'max_decimal_total_difference_yuan':cost_difference,'decimal_costs':decimal_totals,
        'past_only_features_training_and_risk':True,'all_orders_match_committed_plans':True,
        'same_comparison_start_continuous_storage':True,'separate_load_pv_models':True,
        'source_and_output_hashes_match':True,'new_fits':0,'new_solver_calls':0,
        'ai_verification_only':True,'q2_annual_robustness_not_claimed':True}
(R/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='decimal_costs'},ensure_ascii=False,indent=2))
