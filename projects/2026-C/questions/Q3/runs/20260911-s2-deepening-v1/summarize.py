"""Summarize verified saved Q3 deepening results; no fits or optimization."""
from pathlib import Path
import json, hashlib
import pandas as pd
R=Path(__file__).resolve().parent;P=R.parents[3];O=R/'outputs';A=R/'analysis';A.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=read(O/'summary.json');v=read(O/'verification.json');assert v['status']=='checks_completed'
b=s['baseline'];w=s['selected'];q2=read(P/'questions/Q2/runs/20260911-annual-validation-v1/delivery_data/summary.json')
base=pd.read_csv(P/'questions/Q3/runs/20260911-four-candidates-v1/outputs/annual/S2_fused.daily.csv',float_precision='round_trip')
win=pd.read_csv(R/w['daily_csv'],float_precision='round_trip')
q2d=pd.read_csv(P/'questions/Q2/runs/20260911-annual-validation-v1/delivery_data/selected_daily.csv',float_precision='round_trip')
assert list(base.date)==list(win.date)==list(q2d.decision_date)
daily=pd.DataFrame({'date':win.date,'selected_total':win.total_cost,'baseline_total':base.total_cost,'q2_total':q2d.total_cost,
    'selected_emergency':win.emergency_cost,'baseline_emergency':base.emergency_cost,'q2_emergency':q2d.emergency_cost})
daily['saving_vs_baseline']=daily.baseline_total-daily.selected_total;daily['saving_vs_q2']=daily.q2_total-daily.selected_total
daily['month']=pd.to_datetime(daily.date).dt.month;daily.to_csv(A/'daily.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
monthly=daily.drop(columns='date').groupby('month').sum().reset_index();monthly.to_csv(A/'monthly.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
sens=[]
for q in [.6,.65,.7,.75,.8]:
    rec=next(x for x in s['all'] if x['label']==f'M_q{int(round(q*100)):02d}_b070')
    sens.append(dict(quantile=q,total_cost=rec['total_cost'],ordinary_cost=rec['ordinary_cost'],emergency_cost=rec['emergency_cost'],emergency_days=rec['emergency_days']))
pd.DataFrame(sens).to_csv(A/'quantile_sensitivity.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
out=dict(selected=w,comparison=dict(vs_initial_s2=dict(total_saving=b['total_cost']-w['total_cost'],saving_pct=(b['total_cost']-w['total_cost'])/b['total_cost']*100,
        ordinary_change=w['ordinary_cost']-b['ordinary_cost'],emergency_saving=b['emergency_cost']-w['emergency_cost'],
        emergency_kwh_reduction=b['emergency_kwh']-w['emergency_kwh'],emergency_kwh_reduction_pct=(b['emergency_kwh']-w['emergency_kwh'])/b['emergency_kwh']*100,
        emergency_days_change=w['emergency_days']-b['emergency_days'],unused_order_change=w['unused_order_kwh']-b['unused_order_kwh']),
    vs_refined_q2=dict(total_saving=q2['total_official_cost']-w['total_cost'],saving_pct=(q2['total_official_cost']-w['total_cost'])/q2['total_official_cost']*100,
        ordinary_change=w['ordinary_cost']-q2['ordinary_cost'],emergency_saving=q2['emergency_cost']-w['emergency_cost'])),
    monthly=dict(cheaper_than_initial_s2=int((monthly.saving_vs_baseline>0).sum()),dearer_than_initial_s2=int((monthly.saving_vs_baseline<0).sum()),
        cheaper_than_q2=int((monthly.saving_vs_q2>0).sum()),dearer_than_q2=int((monthly.saving_vs_q2<0).sum())),
    daily=dict(cheaper_than_initial_s2=int((daily.saving_vs_baseline>1e-6).sum()),dearer_than_initial_s2=int((daily.saving_vs_baseline<-1e-6).sum()),
        best_day=daily.loc[daily.saving_vs_baseline.idxmax()].to_dict(),worst_day=daily.loc[daily.saving_vs_baseline.idxmin()].to_dict()),
    search=dict(lp_calls=read(O/'budget.json')['lp_calls'],variants=len(s['all'])-1,parameter_selection='exploratory on the required year, not untouched external validation'),
    verification=v)
(A/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
sources=[O/'summary.json',O/'verification.json',P/'questions/Q2/runs/20260911-annual-validation-v1/delivery_data/summary.json']
(A/'manifest.json').write_text(json.dumps(dict(code_sha256=sha(__file__),sources={str(x.relative_to(P)):sha(x) for x in sources},
    outputs={x.name:sha(x) for x in A.iterdir() if x.is_file() and x.name!='manifest.json'},no_new_fit_or_optimization=True),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out['comparison'],ensure_ascii=False))
