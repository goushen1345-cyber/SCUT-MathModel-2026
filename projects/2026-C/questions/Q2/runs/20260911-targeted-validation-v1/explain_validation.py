"""Additional descriptive accounting of actual exposure; no optimization."""
from pathlib import Path
from datetime import datetime,timedelta
from collections import Counter
import json,csv,hashlib
R=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
summary=read(R/'analysis/summary.json');episodes=read(R/'outputs/episodes.json');paired=rows(R/'analysis/paired_daily.csv');base=datetime(2025,1,1);details=[]
for scenario in ['load_underestimate','pv_overestimate','joint_optimism']:
 active={}
 skipped=[]
 for ep in episodes:
  if ep['scenario']!=scenario:continue
  if ep['source_start_day'] is None:skipped.append(ep['episode_start'])
  for rec in ep['records']:active[rec['date']]=rec
 groups={True:[],False:[]}
 for r in paired:
  if r['scenario']==scenario:groups[r['date'] in active].append(r)
 detail={'scenario':scenario,'effective_event_days':len(active),'no_additional_perturbation_days':334-len(active),'skipped_episode_dates':skipped,'effective_days_per_month':dict(sorted(Counter(int(d[5:7]) for d in active).items())),'groups':[]}
 for on,group in groups.items():
  extra=[float(r['extra_cost']) for r in group];detail['groups'].append({'effective_input_perturbation':on,'days':len(group),'paired_saving':-sum(extra),'worse_days':sum(x>1e-6 for x in extra),'max_extra_cost':max(extra),'meaning':'Not a causal decomposition;different dates and inherited inventories,only identifies when additional input disturbance is active.'})
 details.append(detail)
tail=summary['original_tail_risk'];eq=next(r['mean'] for r in tail if r['policy']=='equal');re=next(r['mean'] for r in tail if r['policy']=='recent')
output={'effective_exposure':details,'original_tail_emergency_fee_reduction_pct':100*(eq-re)/eq,'notes':['outputs/summary.json event_days_per_scenario72 is the scheduled3day windows,not effective input perturbations;effective load/joint45,PV72.','Not all signed donor days individually unfavorable;72h selection retains alternating error signs andpairedhistory.','Comparisons across three scenarios have different realized error magnitudes and exposure,so they do not rank intrinsic load/PV difficulty.','Original per-policy worst17days may be different dates;paired regret tail separately compares matchingdates.']}
(R/'interpretation.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(output,ensure_ascii=False))
