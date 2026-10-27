"""Summarize saved trial evidence for explanation and paper, without new experiments."""
from pathlib import Path
import json,hashlib
import pandas as pd
R=Path(__file__).resolve().parent;O=R/'outputs';F=R/'interpretation';assert not F.exists();F.mkdir()
assert json.loads((R/'verification.json').read_text(encoding='utf-8'))['status']=='passed'
daily=pd.read_csv(O/'daily_metrics.csv');comp=pd.read_csv(O/'comparison.csv').set_index('variant')
d=daily[daily.phase=='comparison'].copy();d['month']=pd.to_datetime(d.decision_date).dt.month
d['weekday']=pd.to_datetime(d.decision_date).dt.weekday
for group in ['month','weekday']:
    out=d.groupby(['variant',group]).agg(total_cost=('total_cost','sum'),ordinary_cost=('ordinary_cost','sum'),
         emergency_cost=('emergency_cost','sum'),emergency_kwh=('emergency_kwh','sum'),unused_order_kwh=('unused_order_kwh','sum'),
         days=('day','size'),load_error_sum=('load_abs_error_sum','sum'),pv_error_sum=('pv_abs_error_sum','sum')).reset_index()
    out['load_mae_kw']=out.load_error_sum/(out.days*144);out['pv_mae_kw']=out.pv_error_sum/(out.days*144)
    out.to_csv(F/(group+'_metrics.csv'),index=False,encoding='utf-8-sig')
pairs=d.pivot(index='decision_date',columns='variant',values='total_cost')
pairs['saving_T1_minus_T4']=pairs.T1-pairs.T4;pairs.to_csv(F/'daily_paired_cost.csv',encoding='utf-8-sig')
best=pairs.saving_T1_minus_T4.idxmax();worst=pairs.saving_T1_minus_T4.idxmin()
events=pd.read_csv(O/'execution.csv.gz');events=events[events.phase=='comparison']
selected=events[(events.variant.isin(['T1','T4']))&events.decision_date.isin([best,worst])]
selected.to_csv(F/'paired_extreme_day_trajectories.csv',index=False,encoding='utf-8-sig')
v=.9*float(events.price.iloc[0]);gap=comp.loc['T1','total_cost']-comp.loc['T4','total_cost']
m=pd.read_csv(F/'month_metrics.csv').pivot(index='month',columns='variant',values='total_cost')
result=dict(selected_main='T4',selection_scope='four authorized candidates,Feb-Jun150days,same controller and48h planner',
 total_saving_vs_T1=float(gap),saving_pct_vs_T1=float(gap/comp.loc['T1','total_cost']*100),
 ordinary_cost_increase=float(comp.loc['T4','ordinary_cost']-comp.loc['T1','ordinary_cost']),
 emergency_cost_reduction=float(comp.loc['T1','emergency_cost']-comp.loc['T4','emergency_cost']),
 emergency_energy_reduction=float(comp.loc['T1','emergency_kwh']-comp.loc['T4','emergency_kwh']),
 emergency_energy_reduction_pct=float((1-comp.loc['T4','emergency_kwh']/comp.loc['T1','emergency_kwh'])*100),
 unused_order_increase=float(comp.loc['T4','unused_order_kwh']-comp.loc['T1','unused_order_kwh']),
 unused_pv_increase=float(comp.loc['T4','unused_pv_kwh']-comp.loc['T1','unused_pv_kwh']),
 final_storage_T4_minus_T1=float(comp.loc['T4','storage_end_kwh']-comp.loc['T1','storage_end_kwh']),
 inventory_reference_difference=float(v*(comp.loc['T4','storage_end_kwh']-comp.loc['T1','storage_end_kwh'])),
 improved_days=int((pairs.saving_T1_minus_T4>1e-6).sum()),worsened_days=int((pairs.saving_T1_minus_T4< -1e-6).sum()),
 tied_days=int((abs(pairs.saving_T1_minus_T4)<=1e-6).sum()),
 best_day=best,best_day_saving=float(pairs.loc[best,'saving_T1_minus_T4']),
 worst_day=worst,worst_day_saving=float(pairs.loc[worst,'saving_T1_minus_T4']),
 monthly_savings={str(k):float(v) for k,v in (m.T1-m.T4).items()},
 selected_history_load_weights=[.25]*4,selected_history_pv_weights=[1/7]*7,
 selected_risk_quantile=.7,risk_history_days=28,risk_group_hours=4,
 january_positive_margin_not_better_than_zero=True,
 caveats=['Jul-Dec not simulated','one controller,forecast features and48h horizon','no claims that all tree/ridge variants are inferior',
          'positive margin has lost days and higher unused ordinary/PV','not all candidate forecasts crossed with all margins','no entropy weighting'])
(F/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
