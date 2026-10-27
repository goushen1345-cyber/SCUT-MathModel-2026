"""Read saved, verified Q3 results. No optimization, fitting or source edits."""
from pathlib import Path
import os, json, hashlib, warnings
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
warnings.filterwarnings('ignore',message='Pandas requires version')
import numpy as np
import pandas as pd

R=Path(__file__).resolve().parent
O=R/'outputs'; A=R/'interpretation'; A.mkdir(exist_ok=True)
P=R.parents[3]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(name,x):(A/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def csv(name,x):pd.DataFrame(x).to_csv(A/name,index=False,encoding='utf-8-sig',float_format='%.17g')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

summary=read(O/'summary.json'); verification=read(O/'verification.json')
assert verification['status']=='checks_completed'
records={x['label']:x for x in summary['annual']}
daily={key:pd.read_csv(R/x['daily_csv'],float_precision='round_trip') for key,x in records.items()}
csv('annual_comparison.csv',summary['annual']);csv('january_comparison.csv',summary['calibration'])
paired=pd.DataFrame({'date':daily['S1_raw'].date})
for key,df in daily.items():
    assert df.date.equals(paired.date)
    for metric in ['total_cost','ordinary_cost','emergency_cost']:
        paired[key+'_'+metric]=df[metric]
paired['saving_fused_vs_raw']=paired.S1_raw_total_cost-paired.S2_fused_total_cost
paired['saving_tree_vs_raw']=paired.S1_raw_total_cost-paired.S3_tree_total_cost
paired['saving_total_intraday']=paired.I0_zero_only_total_cost-paired.S1_raw_total_cost
paired['saving_new_forecasts']=paired.I1_no_new_forecast_total_cost-paired.S1_raw_total_cost
paired['month']=pd.to_datetime(paired.date).dt.month
csv('paired_daily.csv',paired)
monthly=paired.drop(columns='date').groupby('month').sum().reset_index()
csv('monthly_comparison.csv',monthly)
saving=paired.saving_fused_vs_raw
extremes=paired.iloc[[saving.idxmax(),saving.idxmin()]]
csv('best_and_worst_days.csv',extremes)

s=dict(np.load(O/'sources.npz'));c=dict(np.load(O/'forecasts.npz'))
rr=s['release'];tt=s['targets'];N=365*144;first=31*144
hourmask=(rr[:,None]>=first)&(tt<N)
hourtruth=np.full_like(s['F'],np.nan);valid=tt<N;hourtruth[valid]=s['actual'][tt[valid],1]
errors=[]
def metrics(label,grid,pred,truth,release_hour,clock,mask):
    for domain,dmask in [('all_clock_hours',np.ones_like(mask,dtype=bool)),('clock_06_to_18',(clock>=6)&(clock<18))]:
        for release in [-1,0,6,12,18]:
            use=mask&dmask&(True if release==-1 else release_hour==release)
            e=pred[use]-truth[use]
            errors.append(dict(strategy=label,grid=grid,domain=domain,release_hour=release,n=len(e),
                mae_kw=float(np.mean(abs(e))) if len(e) else None,
                rmse_kw=float(np.sqrt(np.mean(e*e))) if len(e) else None,
                bias_pred_minus_actual_kw=float(np.mean(e)) if len(e) else None))
for label,key in [('S1_raw',None),('S2_fused','fused_hourly'),('S3_tree','tree7_hourly')]:
    pred=s['F'] if key is None else c[key]
    metrics(label,'as_issued_hourly_leads_1_to_24',pred,hourtruth,np.broadcast_to((rr%144/6)[:,None],tt.shape),tt%144/6,hourmask)
    for band in range(4):
        metrics(label,f'hourly_leads_{1+6*band}_to_{6+6*band}',pred,hourtruth,
                np.broadcast_to((rr%144/6)[:,None],tt.shape),tt%144/6,hourmask&(np.arange(24)//6==band)[None,:])
    # Each realized interval is evaluated exactly once using its newest release.
    ix=rr[:,None]+np.arange(36)
    truth=s['actual'][ix,1]
    pk={'S1_raw':'raw','S2_fused':'fused','S3_tree':'tree7'}[label]
    metrics(label,'next_six_hours_10min',c[pk][:,:36],truth,
            np.broadcast_to((rr%144/6)[:,None],ix.shape),ix%144/6,np.broadcast_to((rr>=first)[:,None],ix.shape))
csv('pv_error_metrics.csv',errors)

weight_rows=[]
for b in np.flatnonzero(rr>=first):
    for g in range(4):
        weight_rows.append(dict(release_index=b,release_day=int(rr[b]//144),release_hour=int(rr[b]%144//6),
            lead_group=g+1,official_weight=float(c['weights'][b,g]),n=int(c['counts'][b,g]),fallback=int(c['fallback'][b,g])))
csv('fusion_weights.csv',weight_rows)
w=pd.DataFrame(weight_rows);wg=w.groupby(['release_hour','lead_group']).official_weight.agg(['mean','median','min','max']).reset_index()
csv('fusion_weight_groups.csv',wg)
weights=c['weights'][rr>=first].ravel()
hourweights=np.repeat(c['weights'],6,axis=1)
dayw=hourweights[hourmask&(tt%144>=36)&(tt%144<108)]

physical=[]
for key in ['S1_raw','S2_fused','S3_tree','I0_zero_only','I1_no_new_forecast']:
    z=dict(np.load(R/records[key]['trace']));ex=z['execution'];plan=z['plans']
    emergency=ex[:,:,8]>1e-6
    invdiff=[];per_interval=[]
    for di in range(len(z['days'])):
        for a in range(4):
            if z['decision_mask'][di,a]:
                invdiff.append(ex[di,a*36+35,1]-plan[di,a,3,35])
                per_interval.extend(ex[di,a*36:(a+1)*36,1]-plan[di,a,3,:36])
    physical.append(dict(strategy=key,emergency_slots=int(emergency.sum()),
        emergency_at_storage_lower_bound=int((emergency&(ex[:,:,1]<=1200+1e-6)).sum()),
        emergency_at_discharge_limit=int((emergency&(ex[:,:,7]>=5000/6-1e-6)).sum()),
        actual_simultaneous_charge_discharge=int((((ex[:,:,5]+ex[:,:,6])>1e-6)&(ex[:,:,7]>1e-6)).sum()),
        min_storage=float(ex[:,:,:2].min()),max_storage=float(ex[:,:,:2].max()),
        six_hour_end_inventory_mae_from_plan_kwh=float(np.mean(abs(np.array(invdiff)))),
        next_six_hour_inventory_mae_from_plan_kwh=float(np.mean(abs(np.array(per_interval))))))
csv('execution_diagnostics.csv',physical)

q2path=P/'questions/Q2/runs/20260911-annual-validation-v1/delivery_data/summary.json';q2=read(q2path)
b=records['S1_raw'];f=records['S2_fused'];i0=records['I0_zero_only'];i1=records['I1_no_new_forecast']
numeric=[]
for x in summary['calibration']:
    if x['label'].endswith('_exact'):
        old=read(O/'calibration'/(x['label'][:-6]+'.summary.json'))
        numeric.append(dict(label=x['label'],old_cost=old['total_cost'],new_cost=x['total_cost'],difference=x['total_cost']-old['total_cost']))
save('numeric_correction_comparison.json',numeric)
out=dict(period='2025-02-01 to 2025-12-31',days=334,recommendation='S2_fused, initial main candidate only',
    fused_vs_raw=dict(saving=float(saving.sum()),saving_pct=float(saving.sum()/b['total_cost']*100),
        ordinary_saving=b['ordinary_cost']-f['ordinary_cost'],emergency_extra=f['emergency_cost']-b['emergency_cost'],
        cheaper_days=int((saving>1e-6).sum()),dearer_days=int((saving< -1e-6).sum()),equal_days=int((abs(saving)<=1e-6).sum()),
        cheaper_months=monthly.loc[monthly.saving_fused_vs_raw>0,'month'].tolist(),dearer_months=monthly.loc[monthly.saving_fused_vs_raw<0,'month'].tolist(),
        best_day=extremes.iloc[0].to_dict(),worst_day=extremes.iloc[1].to_dict()),
    fusion_weights=dict(mean=float(weights.mean()),median=float(np.median(weights)),min=float(weights.min()),max=float(weights.max()),
        mean_daytime_hourly_task_weight=float(dayw.mean()),median_daytime_hourly_task_weight=float(np.median(dayw)),
        fallback_counts={str(k):int(v) for k,v in w.fallback.value_counts().items()},
        raw_fallback_insufficient_records=int(((w.fallback==2)&(w.n<24)).sum()),
        raw_fallback_degenerate_denominator=int(((w.fallback==2)&(w.n>=24)).sum()),
        note='All 5344 group updates; daytime figures repeat each group over its actual 1-24h target tasks. Not one universal coefficient.'),
    information_value=dict(total_intraday=i0['total_cost']-b['total_cost'],
        feedback_and_adjustment=i0['total_cost']-i1['total_cost'],
        new_forecasts=i1['total_cost']-b['total_cost'],
        new_forecasts_pct=(i1['total_cost']-b['total_cost'])/i1['total_cost']*100,
        scope='raw-forecast strategy only; differences conditional on this ordered control design, not independent additive causal effects'),
    q2_context=dict(q2_total=q2['total_official_cost'],q3_total=f['total_cost'],
        extra=f['total_cost']-q2['total_official_cost'],extra_pct=(f['total_cost']/q2['total_official_cost']-1)*100,
        ordinary_saving=q2['ordinary_cost']-f['ordinary_cost'],emergency_extra=f['emergency_cost']-q2['emergency_cost'],
        q2_final=q2['end_kwh'],q3_final=f['final'],
        scope='Q2 family refined after annual diagnosis; Q3 initial January-selected batch. Not an isolated test of information value.'),
    numeric_correction=dict(max_calibration_cost_change=max(abs(x['difference']) for x in numeric),annual_traces_unchanged=True),
    new_fits=0,new_lp_calls=0,verification=verification['counts'])
save('findings.json',out)
save('manifest.json',dict(code_sha256=sha(__file__),sources={str(p.relative_to(P)):sha(p) for p in [O/'summary.json',O/'verification.json',O/'sources.npz',O/'forecasts.npz',q2path]},
    outputs={p.name:sha(p) for p in A.iterdir() if p.is_file() and p.name!='manifest.json'},
    error_definition='prediction minus actual power, kW; fixed daytime 06:00 inclusive to18:00 exclusive; hourly forecasts overlap, executed intervals counted once',
    no_training_or_solving=True))
print(json.dumps({k:out[k] for k in ['fused_vs_raw','fusion_weights','information_value','q2_context','numeric_correction']},ensure_ascii=False))
