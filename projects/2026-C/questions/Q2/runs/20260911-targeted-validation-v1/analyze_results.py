"""Existing-year downside and seasonal analysis plus saved stress summaries."""
from pathlib import Path
import json,math,hashlib
import numpy as np,pandas as pd
R=Path(__file__).resolve().parent;B=R.parent/'20260911-annual-validation-v1';O=R/'analysis';O.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda y:y.item()),encoding='utf-8')
old=pd.read_csv(B/'annual/daily_metrics.csv',float_precision='round_trip');equal=old[old.variant=='T4'].copy();equal['policy']='equal';equal['date']=equal.decision_date
recent=pd.read_csv(B/'delivery_data/selected_daily.csv',float_precision='round_trip');recent['policy']='recent';recent['date']=recent.decision_date
fields=['date','policy','total_cost','ordinary_cost','emergency_cost','order_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh','storage_start_kwh','storage_end_kwh','longest_emergency_minutes','emergency_slots']
original=pd.concat([equal[fields],recent[fields]],ignore_index=True);original['scenario']='original';new=pd.read_csv(R/'outputs/daily_metrics.csv',float_precision='round_trip')
allrows=pd.concat([original,new],ignore_index=True);dt=pd.to_datetime(allrows.date);allrows['month']=dt.dt.month;allrows['season']=allrows.month.map({12:'winter',1:'winter',2:'winter',3:'spring',4:'spring',5:'spring',6:'summer',7:'summer',8:'summer',9:'autumn',10:'autumn',11:'autumn'});allrows['day_type']=np.where(dt.dt.weekday<5,'Mon-Fri','Sat-Sun');allrows['exposure']=np.where((dt-pd.Timestamp('2025-02-01')).dt.days%14<3,'episode','recovery')
allrows.to_csv(O/'all_daily_metrics.csv',index=False,encoding='utf-8-sig')
groups=[]
for dimension in ['month','season','day_type','exposure']:
 for (scenario,policy,group),g in allrows.groupby(['scenario','policy',dimension],sort=True):
  r={'scenario':scenario,'policy':policy,'dimension':dimension,'group':group,'days':len(g),'emergency_days':int((g.emergency_kwh>1e-6).sum()),'longest_within_day_emergency_minutes':float(g.longest_emergency_minutes.max()),'max_daily_emergency_fee':float(g.emergency_cost.max())}
  for col in ['total_cost','ordinary_cost','emergency_cost','order_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh']:r[col]=float(g[col].sum())
  groups.append(r)
gdf=pd.DataFrame(groups);gdf.to_csv(O/'group_metrics.csv',index=False,encoding='utf-8-sig')
group_pairs=gdf[gdf.policy=='equal'].merge(gdf[gdf.policy=='recent'],on=['scenario','dimension','group'],suffixes=('_equal','_recent'));group_pairs['saving']=group_pairs.total_cost_equal-group_pairs.total_cost_recent;group_pairs['saving_pct']=100*group_pairs.saving/group_pairs.total_cost_equal;group_pairs.to_csv(O/'group_paired.csv',index=False,encoding='utf-8-sig')
paired=allrows[allrows.policy=='equal'].merge(allrows[allrows.policy=='recent'],on=['scenario','date'],suffixes=('_equal','_recent'));paired['extra_cost']=paired.total_cost_recent-paired.total_cost_equal;paired.to_csv(O/'paired_daily.csv',index=False,encoding='utf-8-sig')
tails=[];tail_rows=[]
for (scenario,policy),g in allrows.groupby(['scenario','policy']):
 n=math.ceil(.05*len(g));h=g.sort_values(['emergency_cost','date'],ascending=[False,True]).head(n)
 for r in h.itertuples():tail_rows.append({'scenario':scenario,'policy':policy,'tail_kind':'daily_emergency_cost','date':r.date,'value':r.emergency_cost})
 tails.append({'scenario':scenario,'policy':policy,'tail_kind':'daily_emergency_cost','count':n,'mean':float(h.emergency_cost.mean()),'maximum':float(h.emergency_cost.max()),'dates':h.date.tolist()})
for scenario,g in paired.groupby('scenario'):
 n=math.ceil(.05*len(g));h=g.sort_values(['extra_cost','date'],ascending=[False,True]).head(n)
 for r in h.itertuples():tail_rows.append({'scenario':scenario,'policy':'recent-minus-equal','tail_kind':'paired_extra_cost','date':r.date,'value':r.extra_cost})
 tails.append({'scenario':scenario,'policy':'recent-minus-equal','tail_kind':'paired_extra_cost','count':n,'mean':float(h.extra_cost.mean()),'maximum':float(h.extra_cost.max()),'dates':h.date.tolist()})
pd.DataFrame(tail_rows).to_csv(O/'tail_dates.csv',index=False,encoding='utf-8-sig');dump('tails.json',tails)
summary=[]
for scenario,g in paired.groupby('scenario'):
 e=float(g.total_cost_equal.sum());r=float(g.total_cost_recent.sum());summary.append({'scenario':scenario,'equal_cost':e,'recent_cost':r,'saving':e-r,'saving_pct':100*(e-r)/e,'better_days':int((g.extra_cost<-1e-6).sum()),'worse_days':int((g.extra_cost>1e-6).sum()),'same_days':int((abs(g.extra_cost)<=1e-6).sum()),'worst_extra_cost':float(g.extra_cost.max()),'worst_date':g.loc[g.extra_cost.idxmax(),'date']})
baseline=next(r for r in summary if r['scenario']=='original')
for r in summary:r['equal_cost_change_vs_original']=r['equal_cost']-baseline['equal_cost'];r['recent_cost_change_vs_original']=r['recent_cost']-baseline['recent_cost']
pd.DataFrame(summary).to_csv(O/'scenario_comparison.csv',index=False,encoding='utf-8-sig')
episode=json.loads((R/'outputs/episodes.json').read_text(encoding='utf-8'));exposure=[]
for scen in ['load_underestimate','pv_overestimate','joint_optimism']:
 es=[x for x in episode if x['scenario']==scen];days=[y for x in es for y in x['records']]
 exposure.append({'scenario':scen,'episodes':len(es),'zero_donor_episodes':sum(x['source_start_day'] is None for x in es),'perturbed_days':len(days),'load_clipped_48h_slots':sum(x['load_clipped_slots'] for x in days),'pv_clipped_48h_slots':sum(x['pv_clipped_slots'] for x in days),'night_mask_48h_slots':sum(x['night_support_blocked_slots'] for x in days),'realized_load_underestimate_kwh':sum(x['realized_load_underestimate_kwh'] for x in days),'realized_pv_overestimate_kwh':sum(x['realized_pv_overestimate_kwh'] for x in days),'positive_net_shift_days':sum(x['realized_load_underestimate_kwh']+x['realized_pv_overestimate_kwh']>0 for x in days)})
z=np.load(B/'refinement/schedules/sensitivity-error-decay70.npz');a=z['actual'];idx={k:i for i,k in enumerate(z['actual_columns'])};causes=[]
for month in range(2,13):
 days=pd.to_datetime('2025-01-01')+pd.to_timedelta(z['days'],unit='D');v=a[days.month==month];em=v[:,:,idx['emergency_kwh']]>1e-6;low=v[:,:,idx['storage_end_kwh']]<1200+1e-6;lim=v[:,:,idx['discharge_kwh']]>5000/6-1e-6
 causes.append({'month':month,'emergency_slots':int(em.sum()),'inventory_limited_slots':int((em&low).sum()),'power_limited_slots':int((em&lim).sum()),'both_limited_slots':int((em&low&lim).sum())})
pd.DataFrame(causes).to_csv(O/'original_emergency_causes.csv',index=False,encoding='utf-8-sig')
result={'scenario_comparisons':summary,'original_tail_risk':[r for r in tails if r['scenario']=='original'],'original_groups':group_pairs[(group_pairs.scenario=='original')&(group_pairs.dimension.isin(['season','day_type']))][['dimension','group','days_equal','total_cost_equal','total_cost_recent','saving','saving_pct']].to_dict('records'),'stress_exposure':exposure,'definition':'Fixed365-day inherited trajectory;official334day statistics. Winter isFeb+Dec,Mon-Fri not legalholidaycalendar;tail mean empirical17days,not probability guarantee.','generalization':'Daily forecasts are past-only as previously independently verified. Year participated in exploration and strategy-family selection;season groups and synthetic stress are not independent-year/site tests.','new_lp_calls':0,'new_fits':0}
dump('summary.json',result);dump('source_hashes.json',{str(p.relative_to(R.parent)):sha(p) for p in [B/'annual/daily_metrics.csv',B/'delivery_data/selected_daily.csv',B/'refinement/schedules/sensitivity-error-decay70.npz',R/'outputs/daily_metrics.csv',R/'outputs/episodes.json']});dump('output_hashes.json',{str(p.relative_to(O)):sha(p) for p in O.iterdir() if p.is_file() and p.name!='output_hashes.json'})
print(json.dumps(result,ensure_ascii=False,default=lambda x:x.item()),flush=True)
