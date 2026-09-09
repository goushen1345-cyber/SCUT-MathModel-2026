"""Generate only the U013-approved Q2 training/comparison/stress scenario drivers."""
from pathlib import Path
from datetime import datetime, timezone
import csv, hashlib, json, random

ROOT = Path(__file__).resolve().parents[2]
Q = Path(__file__).resolve().parent
OUT = Q / "runs/scenarios"
DATA = ROOT / "data/frozen/G1-v1-base"
YEARS = range(2024, 2031)

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def readcsv(path):
    with path.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def dump(path, obj): path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
def writecsv(path, rows):
    with path.open("x", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

state=json.loads((ROOT/'state/state.json').read_text(encoding='utf-8'))
assert state['stage']=='TRIAL' and state['active_question']=='Q2'
assert any(a['id']=='U013' and a['plan_version']=='Q2-TRIAL-v1' for a in state['authorizations'])
assert all(sha(ROOT/p)==h for p,h in state['data_snapshots']['G1-v1-base'].items())
q1snap=state['questions']['Q1']['snapshots']['Q1-D-v2-candidate']
assert all(sha(ROOT/p)==h for p,h in q1snap.items())
protocol=json.loads((Q/'protocols/uncertainty_v1.json').read_text(encoding='utf-8'))
assert protocol['status']=='PROPOSED_AT_A_NOT_APPROVED' and protocol['scenario_sets']['future_holdout']['count']==500

crops={int(r['crop_id']):r for r in readcsv(DATA/'crops.csv')}
levels=[0,1,2]; weights=[.25,.5,.25]
def pick(rng, vals): return rng.choices(vals, weights=weights, k=1)[0]

def random_set(label, count, seed):
    rng=random.Random(seed); rows=[]
    for number in range(count):
        sid=f'{label}-{number+1:03d}'; wheat_factor=1.0; fungi_factor={c:1.0 for c,r in crops.items() if '食用菌' in r['crop_type']}
        for year in YEARS:
            wheat_rate=pick(rng,[.05,.075,.10]); wheat_factor*=1+wheat_rate
            for crop,row in crops.items():
                ctype=row['crop_type']; other=pick(rng,[.95,1.0,1.05]); ym=pick(rng,[.9,1.0,1.1])
                if crop in (6,7): dm=wheat_factor
                else: dm=other
                step=year-2023; costm=1.05**step
                if '粮食' in ctype: pm=1.0
                elif '蔬菜' in ctype: pm=1.05**step
                elif row['crop_name']=='羊肚菌': pm=.95**step
                elif '食用菌' in ctype:
                    decline=pick(rng,[.01,.03,.05]); fungi_factor[crop]*=1-decline; pm=fungi_factor[crop]
                else: raise ValueError(ctype)
                rows.append({'scenario_set':label,'scenario_id':sid,'year':year,'crop_id':crop,'crop_name':row['crop_name'],
                             'demand_multiplier':f'{dm:.12g}','yield_multiplier':f'{ym:.12g}',
                             'cost_multiplier':f'{costm:.12g}','price_multiplier':f'{pm:.12g}',
                             'wheat_corn_growth_rate':f'{wheat_rate:.12g}' if crop in (6,7) else '',
                             'assumption_status':'model_scenario_not_forecast'})
    return rows

stress_specs=[
 ('worst_all',.05,.95,.90,.06,.04,.05), ('low_demand',.05,.95,1.0,.05,.05,.03),
 ('low_yield',.075,1.0,.90,.05,.05,.03), ('high_cost',.075,1.0,1.0,.06,.05,.03),
 ('weak_prices',.075,1.0,1.0,.05,.04,.05), ('demand_yield',.05,.95,.90,.05,.05,.03),
 ('demand_cost',.05,.95,1.0,.06,.05,.03), ('yield_cost',.075,1.0,.90,.06,.05,.03),
 ('price_cost',.075,1.0,1.0,.06,.04,.05), ('market_low',.05,.95,1.0,.05,.04,.05),
 ('production_market',.05,.95,.90,.05,.04,.03), ('midpoint',.075,1.0,1.0,.05,.05,.03)]
def stress_set():
    rows=[]
    for name,wg,other,ym,cr,vr,fd in stress_specs:
        wf=1.0
        for year in YEARS:
            wf*=1+wg; step=year-2023
            for crop,row in crops.items():
                ctype=row['crop_type']; dm=wf if crop in (6,7) else other; costm=(1+cr)**step
                if '粮食' in ctype:pm=1.0
                elif '蔬菜' in ctype:pm=(1+vr)**step
                elif row['crop_name']=='羊肚菌':pm=.95**step
                elif '食用菌' in ctype:pm=(1-fd)**step
                else:raise ValueError(ctype)
                rows.append({'scenario_set':'stress','scenario_id':f'stress-{name}','year':year,'crop_id':crop,'crop_name':row['crop_name'],
                             'demand_multiplier':f'{dm:.12g}','yield_multiplier':f'{ym:.12g}',
                             'cost_multiplier':f'{costm:.12g}','price_multiplier':f'{pm:.12g}',
                             'wheat_corn_growth_rate':f'{wg:.12g}' if crop in (6,7) else '',
                             'assumption_status':'named_stress_not_forecast'})
    return rows

if OUT.exists(): raise RuntimeError('scenario output exists; refusing overwrite')
OUT.mkdir(parents=True)
training=random_set('training',80,20240907); comparison=random_set('comparison',240,20241007); stress=stress_set()
writecsv(OUT/'training_drivers.csv',training); writecsv(OUT/'comparison_drivers.csv',comparison); writecsv(OUT/'stress_drivers.csv',stress)
checks={
 'training_scenarios':len({r['scenario_id'] for r in training}), 'comparison_scenarios':len({r['scenario_id'] for r in comparison}),
 'stress_scenarios':len({r['scenario_id'] for r in stress}), 'rows_per_scenario':len(crops)*len(list(YEARS)),
 'seeds_distinct':20240907!=20241007, 'future_holdout_generated':False,
 'all_multipliers_positive':all(float(r[k])>0 for r in training+comparison+stress for k in ('demand_multiplier','yield_multiplier','cost_multiplier','price_multiplier')),
 'random_yield_in_range':all(.9<=float(r['yield_multiplier'])<=1.1 for r in training+comparison),
 'other_random_demand_in_range':all(.95<=float(r['demand_multiplier'])<=1.05 for r in training+comparison if int(r['crop_id']) not in (6,7))
}
assert checks=={**checks,'training_scenarios':80,'comparison_scenarios':240,'stress_scenarios':12,'rows_per_scenario':287,'seeds_distinct':True,'future_holdout_generated':False,'all_multipliers_positive':True,'random_yield_in_range':True,'other_random_demand_in_range':True}
dump(OUT/'validation.json',{'protocol':'Q2-UNCERTAINTY-v1','authorization':'U013','created_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'passed':True,'source_hashes':state['data_snapshots']['G1-v1-base'],'human_verification':'pending'})
print(json.dumps({'training':80,'comparison':240,'stress':12,'rows':len(training)+len(comparison)+len(stress),'future_holdout_generated':False},ensure_ascii=False))
