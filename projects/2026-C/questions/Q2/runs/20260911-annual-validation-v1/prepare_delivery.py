"""Explain saved results and prepare template payload; no solves or fitting."""
from pathlib import Path
import json,hashlib,math
import numpy as np,pandas as pd
R=Path(__file__).resolve().parent;P=R.parents[3];OLD=R.parent/'20260911-four-candidates-v1';D=R/'delivery_data';D.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,x):(D/name).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
sel=json.loads((R/'refinement/selection.json').read_text());assert sel['chosen_decay']==.7
z=np.load(R/'refinement/schedules/sensitivity-error-decay70.npz');columns=list(z['actual_columns']);main=pd.DataFrame(z['actual'].reshape(-1,len(columns)),columns=columns);main['day']=np.repeat(z['days'],144);main['date']=(pd.Timestamp('2025-01-01')+pd.to_timedelta(main.day,unit='d')).dt.strftime('%Y-%m-%d');main['slot']=main.slot.astype(int)
main.to_csv(D/'selected_execution.csv.gz',index=False,encoding='utf-8-sig')
df=pd.read_csv(R/'refinement/daily_metrics.csv');daily=df[(df.phase=='sensitivity')&(df.variant=='error-decay70')].copy();daily.to_csv(D/'selected_daily.csv',index=False,encoding='utf-8-sig')
annual=pd.read_csv(R/'annual/daily_metrics.csv');base=annual[annual.variant=='T4'];plain=annual[annual.variant=='T1'];comparison=pd.read_csv(R/'annual/comparison.csv');validation=pd.read_csv(R/'validation/comparison.csv');refine=pd.read_csv(R/'refinement/comparison.csv')
merged=daily[['decision_date','total_cost']].merge(base[['decision_date','total_cost']],on='decision_date',suffixes=('_main','_base'));merged['saving']=merged.total_cost_base-merged.total_cost_main;merged.to_csv(D/'paired_days.csv',index=False,encoding='utf-8-sig')
month=daily.assign(month=pd.to_datetime(daily.decision_date).dt.month).groupby('month')[['ordinary_cost','emergency_cost','total_cost','emergency_kwh','unused_order_kwh','unused_pv_kwh']].sum();month.to_csv(D/'selected_monthly.csv',encoding='utf-8-sig')
by_month=merged.assign(month=pd.to_datetime(merged.decision_date).dt.month).groupby('month').saving.sum()
def time(k):return '24:00' if k==144 else f'{k//6:02d}:{k%6*10:02d}'
events=[];purchase=[];storage=[];table1=[];table2=[];specified={'2025-03-20','2025-06-21','2025-09-23','2025-12-21'}
for date,g in main.groupby('date',sort=True):
 g=g.sort_values('slot');q=g.order_kwh.to_numpy();em=g.emergency_kwh.to_numpy();p=g.price.to_numpy();serial=int((pd.Timestamp(date)-pd.Timestamp('1899-12-30')).days)
 purchase.append([serial,*q[1:].tolist(),float(q[0]),float(q.sum()),float(p@q)])
 for i in range(6):
  gg=g.iloc[24*i:24*(i+1)];c=float((gg.grid_charge_kwh+gg.pv_charge_kwh).sum());dis=float(gg.discharge_kwh.sum());clock='0:00' if i==0 else '24:00' if i==1 else None;stock=float(g.storage_start_kwh.iloc[0]) if i==0 else float(g.storage_end_kwh.iloc[-1]) if i==1 else None
  storage.append([serial if i==0 else None,f'{time(i*24)}-{time((i+1)*24)}',c,dis,clock,stock])
  if date in specified:table2.append({'date':date,'interval':f'{time(i*24)}-{time((i+1)*24)}','charge_kwh':c,'discharge_kwh':dis,'day_start_kwh':float(g.storage_start_kwh.iloc[0]),'day_end_kwh':float(g.storage_end_kwh.iloc[-1])})
 k=0;found=False
 while k<144:
  if em[k]<=1e-6:k+=1;continue
  start=k
  while k<144 and em[k]>1e-6:k+=1
  events.append({'date':date,'serial':serial,'interval':f'{time(start)}-{time(k)}','start_slot':start,'end_slot':k,'kwh':float(em[start:k].sum()),'cost':float(5*p[start:k]@em[start:k])});found=True
 if not found:events.append({'date':date,'serial':serial,'interval':'无紧急购电','start_slot':None,'end_slot':None,'kwh':0.,'cost':0.})
 if date in specified:
  row={'date':date}
  for k in [60,72,84,96,108,120]:row[f'{time(k)}-{time(k+1)}_plan_kwh']=float(q[k])
  row.update(plan_daily_kwh=float(q.sum()),emergency_daily_kwh=float(em.sum()),all_purchased_daily_kwh=float(q.sum()+em.sum()),ordinary_fee=float(p@q),emergency_fee=float(5*p@em),total_fee=float(p@q+5*p@em));table1.append(row)
pd.DataFrame(events).to_csv(D/'emergency_events.csv',index=False,encoding='utf-8-sig');pd.DataFrame(table1).to_csv(D/'specified_table1.csv',index=False,encoding='utf-8-sig');pd.DataFrame(table2).to_csv(D/'specified_table2.csv',index=False,encoding='utf-8-sig');pd.DataFrame([x for x in events if x['date'] in specified]).to_csv(D/'specified_table3.csv',index=False,encoding='utf-8-sig')
energy_stats={n:float(main[n].sum()) for n in ['order_kwh','received_kwh','grid_charge_kwh','pv_charge_kwh','discharge_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh','ordinary_cost','emergency_cost']}
basecost=float(base.total_cost.sum());plaincost=float(plain.total_cost.sum());cost=float(daily.total_cost.sum());common=json.loads((R/'annual/summary.json').read_text())['common_january_cost']
betas=[.7,.8,.9];weights={str(b):{'half_life_days':math.log(.5)/math.log(b),'day_weights_newest_first':((b**np.arange(28))/np.sum(b**np.arange(28))).tolist(),'effective_days':float((np.sum(b**np.arange(28)))**2/np.sum(b**(2*np.arange(28))))} for b in betas}
summary={'selected_model':'separate4weekday_load+7recent_PV+recent-weighted-error_quantile+48hLP','forecast_weights':'equal4 and7; retained January-selected windows, not claimed universally best','risk_quantile':.7,'error_weight_decay':.7,'weight_selection_source':'Jan8-31 among0.7/0.8/0.9 under fixed q0.7; chosen family after full-period diagnostic, no independent-test claim','risk_history_days':28,'risk_group_hours':4,'official_days':334,'common_initialization_days':31,'total_official_cost':cost,'ordinary_cost':energy_stats['ordinary_cost'],'emergency_cost':energy_stats['emergency_cost'],'continuous365day_cost_including_common_january':common+cost,'common_january_cost':common,'saving_vs_plain_history':plaincost-cost,'saving_pct_vs_plain_history':100*(plaincost-cost)/plaincost,'saving_vs_uniform_error_margin':basecost-cost,'saving_pct_vs_uniform_error_margin':100*(basecost-cost)/basecost,'monthly_savings_vs_uniform':by_month.to_dict(),'improved_days_vs_uniform':int((merged.saving>1e-6).sum()),'worsened_days_vs_uniform':int((merged.saving<-1e-6).sum()),'same_days_vs_uniform':int((abs(merged.saving)<=1e-6).sum()),'start_kwh':float(main.storage_start_kwh.iloc[0]),'end_kwh':float(main.storage_end_kwh.iloc[-1]),'emergency_days':int((daily.emergency_kwh>1e-6).sum()),'max_contiguous_emergency_minutes':int(daily.longest_emergency_minutes.max()),'emergency_event_count':sum(x['kwh']>0 for x in events),'energy_totals':energy_stats,'decay_weight_details':weights,'specified_dates':table1,'actual_research_lp':6486,'new_fitted_models':104,'no_manuscript_created':True}
dump('summary.json',summary)
payload={'purchase':purchase,'storage':storage,'emergency':[[e['serial'],e['interval'],e['kwh']] for e in events],'source_selected_npz_sha256':sha(R/'refinement/schedules/sensitivity-error-decay70.npz'),'meaning':{'purchase_totals':'plan sheet daily quantity=sum locked normal orders, fee=sum tariff*normal orders; emergency separate. Specified tables also explicitly report all-purchase and all-fee totals.','midnight':'EO same civil-date00:00-00:10; B original00:10, EN23:50-24:00; no off-by-one-day relocation.','storage':'actual external-side charge/discharge and internal endpoint states','precision':'store full double precision; display2decimals, no resequencing by original source rows'}}
dump('workbook_payload.json',payload);dump('source_hashes.json',{str(f.relative_to(R)):sha(f) for f in [R/'refinement/schedules/sensitivity-error-decay70.npz',R/'refinement/selection.json',R/'annual/comparison.csv',R/'validation/comparison.csv',R/'refinement/comparison.csv']})
print(json.dumps({k:v for k,v in summary.items() if k not in ['decay_weight_details','specified_dates','energy_totals']},ensure_ascii=False))
