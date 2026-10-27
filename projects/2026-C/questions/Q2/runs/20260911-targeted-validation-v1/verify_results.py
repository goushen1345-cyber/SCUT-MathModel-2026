"""Independent source, scenario, physical, saved-output and risk checks. No LP."""
from pathlib import Path
from datetime import datetime,timedelta
from decimal import Decimal
import json,math,hashlib,csv
import numpy as np,pandas as pd
R=Path(__file__).resolve().parent;P=R.parents[3];B=R.parent/'20260911-annual-validation-v1';OLD=R.parent/'20260911-four-candidates-v1';O=R/'outputs';AN=R/'analysis'
read=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources=read(O/'source_hashes.json')
for rel,h in sources['previous_files'].items():assert sha(B/rel)==h,rel
for section in ['raw','oldprotected']:
 for rel,h in sources[section].items():assert sha(P/rel)==h,rel
assert sha(R/'protocol.json')==sources['protocol'] and sha(R/'run_validation.py')==sources['code'] and sha(B/'core.py')==sources['core']
for folder in [O,AN]:
 for rel,h in read(folder/'output_hashes.json').items():assert sha(folder/rel)==h,rel
base_date=datetime(2025,1,1);A={k:np.full((365,144),np.nan) for k in ['load','pv']}
raw=pd.read_csv(P/'data/prepared-v1/actual_power.csv',float_precision='round_trip')
for row in raw.itertuples():
 dt=datetime.fromisoformat(row.source_date)+timedelta(minutes=int(row.source_minute));d=(dt.date()-base_date.date()).days;k=dt.hour*6+dt.minute//10
 if 0<=d<365:A['load'][d,k]=row.load_kw;A['pv'][d,k]=row.pv_actual_kw
reference=pd.read_csv(P/'data/prepared-v1/day_reference.csv',float_precision='round_trip');reference['slot']=reference.source_minute.astype(int)%1440//10;reference=reference.sort_values('slot');fallback={'load':reference.load_kw.to_numpy(),'pv':reference.pv_forecast_kw.to_numpy()};price=reference.price_yuan_per_kwh.to_numpy()
maximum={};counts={'forecast_values':0,'actual_intervals':0,'plan_intervals':0,'episodes':0,'daily_rows':0,'group_rows':0,'tail_rows':0}
def close(name,a,b,tol=1e-6):
 x=np.asarray(a);y=np.asarray(b);assert x.shape==y.shape or x.ndim==0 or y.ndim==0,(name,x.shape,y.shape)
 assert np.array_equal(np.isnan(x),np.isnan(y)) if x.shape==y.shape else not np.isnan(x-y).any()
 diff=np.abs(x-y);err=float(np.nanmax(diff)) if np.isfinite(diff).any() else 0.;maximum[name]=max(maximum.get(name,0),err);assert err<tol,(name,err)
def predict(var,d,h):
 ix=[d+h-7*j for j in range(1,5) if 0<=d+h-7*j<d] if var=='load' else list(range(max(0,d-7),d))
 if not ix:ix=list(range(max(0,d-7),d))
 assert ix and max(ix)<d
 z=A[var][ix];n=np.isfinite(z).sum(axis=0);return np.divide(np.nansum(z,axis=0),n,out=fallback[var].copy(),where=n>0)
base=np.full((365,288,2),np.nan)
for d in range(1,365):
 for h in [0,1]:
  for v,var in enumerate(['load','pv']):base[d,h*144:(h+1)*144,v]=predict(var,d,h)
EL=A['load']-base[:,:144,0];EV=base[:,:144,1]-A['pv'];ref=np.load(O/'reference_inputs.npz');close('reference_forecasts',base,ref['forecasts'],1e-7);close('reference_load_errors',EL,ref['load_underestimate_errors_kw'],1e-7);close('reference_pv_errors',EV,ref['pv_overestimate_errors_kw'],1e-7)
episodes=read(O/'episodes.json');daily=pd.read_csv(O/'daily_metrics.csv',float_precision='round_trip');feb=read(OLD/'outputs/initialization.json')['feb1_initial'];totals=[]
solver=[json.loads(l) for l in (O/'solver_checks.jsonl').read_text(encoding='utf-8').splitlines()];assert len(solver)==2004;solvers={(r['scenario'],r['policy'],r['day']):r for r in solver}
assert len(solvers)==2004 and all(r['status']==0 and r['simultaneous_slots']==0 and r['primal_dual_gap']<1e-4 for r in solver)
for scenario in ['load_underestimate','pv_overestimate','joint_optimism']:
 expected=base.copy();donor=np.full(365,-1,dtype=int);event=np.zeros(365,dtype=bool)
 er=[r for r in episodes if r['scenario']==scenario];assert len(er)==24
 for start,rec in zip(range(31,365,14),er):
  assert rec['episode_start_day']==start;pool=[]
  for j in range(max(1,start-28),start-2):
   x=float(EL[j:j+3].sum()/6);y=float(EV[j:j+3].sum()/6)
   permitted=x>0 if scenario=='load_underestimate' else y>0 if scenario=='pv_overestimate' else x>0 and y>0
   if permitted:pool.append((x if scenario=='load_underestimate' else y if scenario=='pv_overestimate' else x+y,j))
  pool.sort();assert len(pool)==rec['eligible_blocks'];chosen=pool[math.ceil(.9*len(pool))-1][1] if pool else None;assert chosen==rec['source_start_day'];counts['episodes']+=1
  for j in range(min(3,365-start)):
   d=start+j;event[d]=True
   if chosen is None:continue
   source=chosen+j;assert source<start and chosen>=max(1,start-28);donor[d]=source
   el=EL[source] if scenario!='pv_overestimate' else np.zeros(144);ev=EV[source] if scenario!='load_underestimate' else np.zeros(144)
   rawl=base[d,:,0]-np.tile(el,2);rawv=base[d,:,1]+np.tile(ev,2);support=np.tile(np.any(A['pv'][max(0,d-28):d]>0,axis=0),2)
   expected[d,:,0]=np.maximum(0,rawl);expected[d,:,1]=np.maximum(0,rawv)*support
   mr=rec['records'][j];assert mr['day']==d and mr['source_day']==source;assert int((rawl<0).sum())==mr['load_clipped_slots'] and int((rawv<0).sum())==mr['pv_clipped_slots'];assert int(((rawv>0)&~support).sum())==mr['night_support_blocked_slots']
   close('realized_shift',mr['realized_load_underestimate_kwh'],float((base[d,:144,0]-expected[d,:144,0]).sum()/6));close('realized_shift',mr['realized_pv_overestimate_kwh'],float((expected[d,:144,1]-base[d,:144,1]).sum()/6))
 z=np.load(O/f'inputs-{scenario}.npz');close('stress_forecasts',z['forecasts'],expected,1e-7);assert np.array_equal(z['donor_days'],donor) and np.array_equal(z['event_days'],event)
 error=((A['load']-A['pv'])-(expected[:,:144,0]-expected[:,:144,1]))/6;close('reconstructed_scenario_errors',z['net_errors_kwh'],error,1e-7);counts['forecast_values']+=334*288*2
 for policy in ['equal','recent']:
  saved=np.load(O/'schedules'/f'{scenario}-{policy}.npz');assert np.array_equal(saved['days'],np.arange(31,365));a=saved['actual'];pl=saved['plan'];idx={x:i for i,x in enumerate(saved['actual_columns'])};flat=a.reshape(-1,a.shape[-1]);c=lambda key:flat[:,idx[key]]
  state=c('storage_start_kwh');end=c('storage_end_kwh');q=c('order_kwh');x=c('grid_charge_kwh');y=c('pv_charge_kwh');zdis=c('discharge_kwh');em=c('emergency_kwh');pr=np.tile(price,334);load=A['load'][31:].ravel()/6;pv=A['pv'][31:].ravel()/6
  close('actual_source',c('load_kw'),load*6);close('actual_source',c('pv_kw'),pv*6);close('actual_price',c('price'),pr);close('stock_initial',state[0],feb);close('cross_interval_stock',state[1:],end[:-1]);close('storage_equation',end,state+.9*(x+y)-zdis/.9)
  assert min(state.min(),end.min())>=1200-1e-6 and max(state.max(),end.max())<=10800+1e-6
  assert all(t.min()>-1e-6 for t in [q,x,y,zdis,em,c('unused_order_kwh'),c('unused_pv_kwh')]);assert (x+y).max()<=5000/6+1e-6 and zdis.max()<=5000/6+1e-6;assert not np.any(((x+y)>1e-6)&(zdis>1e-6))
  direct=np.minimum(load,pv);need=load-direct;surplus=pv-direct;short=np.maximum(need-q,0);zd=np.minimum.reduce([short,np.full(len(short),5000/6),np.maximum(.9*(state-1200),0)])
  charge=np.where(short>0,0,np.minimum.reduce([surplus+np.maximum(q-need,0),np.full(len(short),5000/6),np.maximum((10800-state)/.9,0)]))
  close('dispatch',zdis,zd);close('dispatch',em,short-zd);close('dispatch',x+y,charge);close('dispatch',y,np.minimum(surplus,charge));close('load_balance',direct+c('grid_to_load_kwh')+zdis+em,load);close('received',c('received_kwh'),c('grid_to_load_kwh')+x);close('ordinary_book',q,c('received_kwh')+c('unused_order_kwh'));close('pv_book',pv,direct+y+c('unused_pv_kwh'))
  close('ordinary_fee',c('ordinary_cost'),pr*q);close('emergency_fee',c('emergency_cost'),5*pr*em);counts['actual_intervals']+=len(flat)
  for i,d in enumerate(range(31,365)):
   matrix=pl[i];lf,vf,margin,order,gc,vc,dis,s=matrix.T;close('plan_inputs',matrix[:,:2],expected[d],1e-7);m=np.zeros(144)
   for slot in range(0,144,24):
    hist=error[d-28:d,slot:slot+24];vals=hist.ravel()
    if policy=='equal':qq=np.quantile(vals,.7)
    else:
     w=np.broadcast_to((.7**np.arange(27,-1,-1))[:,None],hist.shape).ravel();ind=np.argsort(vals,kind='stable');cw=np.cumsum(w[ind]);qq=vals[ind[np.searchsorted(cw,.7*cw[-1],side='left')]]
    m[slot:slot+24]=max(0,qq)
   close('margin_from_actual_past_issued_forecasts',margin,np.tile(m,2),1e-7);net=np.maximum((lf-vf)/6+margin,0);surplusplan=np.maximum((vf-lf)/6-margin,0);s0=a[i,0,idx['storage_start_kwh']]
   close('plan_order',order,net-dis+gc);close('plan_storage',s,np.r_[s0,s[:-1]]+.9*(gc+vc)-dis/.9);close('locked_actual_order',a[i,:,idx['order_kwh']],order[:144]);assert s.min()>=1200-1e-6 and s.max()<=10800+1e-6
   assert min(gc.min(),vc.min(),dis.min(),order.min())>-1e-6;assert (gc+vc).max()<=5000/6+1e-6 and dis.max()<=5000/6+1e-6;assert (vc-surplusplan).max()<1e-6 and (dis-net).max()<1e-6;assert not np.any(((gc+vc)>1e-6)&(dis>1e-6))
   close('objective',np.tile(price,2)@order-.9*price[0]*s[-1],solvers[(scenario,policy,d)]['objective'],1e-5)
   row=daily[(daily.scenario==scenario)&(daily.policy==policy)&(daily.day==d)].iloc[0];assert row.date==(base_date+timedelta(days=d)).strftime('%Y-%m-%d') and row.event_day==bool(event[d]);assert row.cycle_day==(d-31)%14
   for name in ['ordinary_cost','emergency_cost','order_kwh','received_kwh','grid_charge_kwh','pv_charge_kwh','discharge_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh']:close('daily_'+name,row[name],float(a[i,:,idx[name]].sum()),1e-5)
   close('daily_total',row.total_cost,float(np.sum(a[i,:,idx['ordinary_cost']]+a[i,:,idx['emergency_cost']])),1e-5);close('daily_initial',row.storage_start_kwh,s0);close('daily_final',row.storage_end_kwh,a[i,-1,idx['storage_end_kwh']]);flags=a[i,:,idx['emergency_kwh']]>1e-6;best=now=0
   for flag in flags:now=now+1 if flag else 0;best=max(best,now)
   assert row.emergency_slots==int(flags.sum()) and row.longest_emergency_minutes==best*10;counts['daily_rows']+=1;counts['plan_intervals']+=288
  dc=sum((Decimal(str(p))*Decimal(str(v)) for p,v in zip(pr,q)),Decimal(0));de=sum((Decimal(5)*Decimal(str(p))*Decimal(str(v)) for p,v in zip(pr,em)),Decimal(0));close('decimal_total',float(dc+de),daily[(daily.scenario==scenario)&(daily.policy==policy)].total_cost.sum(),1e-5);totals.append({'scenario':scenario,'policy':policy,'ordinary':str(dc),'emergency':str(de),'total':str(dc+de)})
 print('verified',scenario,flush=True)

# Validate grouped/risk CSV statistics independently using plain dictionaries.
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
allrows=rows(AN/'all_daily_metrics.csv');assert len(allrows)==334*2*4
source_rows=[]
for r in rows(B/'annual/daily_metrics.csv'):
 if r['variant']=='T4':source_rows.append(dict(r,scenario='original',policy='equal',date=r['decision_date']))
for r in rows(B/'delivery_data/selected_daily.csv'):source_rows.append(dict(r,scenario='original',policy='recent',date=r['decision_date']))
source_rows+=rows(O/'daily_metrics.csv');index={(r['scenario'],r['policy'],r['date']):r for r in source_rows};assert len(index)==len(allrows)
for r in allrows:
 src=index[(r['scenario'],r['policy'],r['date'])]
 for name in ['total_cost','ordinary_cost','emergency_cost','emergency_kwh','unused_order_kwh','unused_pv_kwh','storage_start_kwh','storage_end_kwh']:close('analysis_source',float(r[name]),float(src[name]))
 dt=datetime.fromisoformat(r['date']);assert int(r['month'])==dt.month;assert r['day_type']==('Mon-Fri' if dt.weekday()<5 else 'Sat-Sun');season={12:'winter',1:'winter',2:'winter',3:'spring',4:'spring',5:'spring',6:'summer',7:'summer',8:'summer',9:'autumn',10:'autumn',11:'autumn'}[dt.month];assert r['season']==season;assert r['exposure']==('episode' if (dt-datetime(2025,2,1)).days%14<3 else 'recovery')
for r in rows(AN/'group_metrics.csv'):
 subset=[v for v in allrows if v['scenario']==r['scenario'] and v['policy']==r['policy'] and str(v[r['dimension']])==r['group']];assert len(subset)==int(r['days'])
 for name in ['total_cost','ordinary_cost','emergency_cost','order_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh']:close('group_'+name,float(r[name]),sum(float(v[name]) for v in subset),1e-5)
 assert int(r['emergency_days'])==sum(float(v['emergency_kwh'])>1e-6 for v in subset);counts['group_rows']+=1
paired=rows(AN/'paired_daily.csv');assert len(paired)==334*4
for r in paired:close('paired_cost',float(r['extra_cost']),float(index[(r['scenario'],'recent',r['date'])]['total_cost'])-float(index[(r['scenario'],'equal',r['date'])]['total_cost']))
for r in read(AN/'tails.json'):
 if r['tail_kind']=='daily_emergency_cost':vals=[(float(v['emergency_cost']),v['date']) for v in allrows if v['scenario']==r['scenario'] and v['policy']==r['policy']]
 else:vals=[(float(v['extra_cost']),v['date']) for v in paired if v['scenario']==r['scenario']]
 vals.sort(key=lambda v:(-v[0],v[1]));top=vals[:math.ceil(.05*len(vals))];assert len(top)==r['count']==17;assert [x[1] for x in top]==r['dates'];close('tail_mean',r['mean'],sum(x[0] for x in top)/17);close('tail_maximum',r['maximum'],top[0][0]);counts['tail_rows']+=len(top)
result={'status':'passed','counts':counts,'max_absolute_error':maximum,'lp_calls_checked':2004,'new_lp_calls':0,'new_fits':0,'decimal_costs':totals,'all_prior_scientific_files_and_raw_unchanged':True,'causal_donor_selection_and_error_updates':True,'shared_stress_inputs_for_both_policies':True,'full_cross_day_inventory_and_locked_orders':True,'exported_daily_groups_and_tail_statistics_checked':True,'scope':'Only prespecified synthetic forecast-input scenarios and existing-year descriptive risk;not external generalization or universal robustness.','human_review':False}
(R/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)
