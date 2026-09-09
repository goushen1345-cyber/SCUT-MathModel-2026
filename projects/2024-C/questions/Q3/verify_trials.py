"""Independent verifier for Q3-TRIAL-v1; imports neither generator nor solver."""
from pathlib import Path
from collections import defaultdict, Counter
from decimal import Decimal
import csv, hashlib, json, math, statistics

ROOT=Path(__file__).resolve().parents[2];Q=Path(__file__).resolve().parent;DATA=ROOT/'data/frozen/G1-v1-base';RUN=Q/'runs';YEARS=range(2024,2031);EPS=Decimal('.00002')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dec(x):return Decimal(str(x))
def readcsv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def writecsv(p,rows):
    fields=list(rows[0])
    with p.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')

state=json.loads((ROOT/'state/state.json').read_text(encoding='utf-8'));assert state['stage']=='TRIAL' and state['active_question']=='Q3' and any(a['id']=='U018' for a in state['authorizations'])
assert all(sha(ROOT/p)==h for p,h in state['data_snapshots']['G1-v1-base'].items())
for qn in ('Q1','Q2'):
    q=state['questions'][qn];assert all(sha(ROOT/p)==h for p,h in q['snapshots'][q['frozen_version']].items())
lands={r['land_id']:r for r in readcsv(DATA/'lands.csv')};crops={int(r['crop_id']):r for r in readcsv(DATA/'crops.csv')};params={(int(r['crop_id']),r['land_type'],r['season']):r for r in readcsv(DATA/'parameters_effective.csv')}
hist=readcsv(DATA/'planting_2023.csv');prod=readcsv(DATA/'production_2023.csv');beans={c for c,r in crops.items() if r['is_legume']=='true'}
base0={(int(r['crop_id']),r['season']):dec(r['production_estimate_jin']) for r in prod};seasons=defaultdict(set);prices=defaultdict(set)
for c,lt,s in params:seasons[c].add(s);prices[(c,s)].add(dec(params[(c,lt,s)]['price_midpoint_candidate_yuan_per_jin']))
assert all(len(v)==1 for v in prices.values());prices={k:next(iter(v)) for k,v in prices.items()}
def base_demand(kind):
    d=dict(base0);frac={'D0':Decimal(0),'D05':Decimal('.05'),'D10':Decimal('.10')}[kind]
    for c,ss in seasons.items():
        obs=[s for s in ss if (c,s) in base0];missing=[s for s in ss if (c,s) not in base0]
        if frac and len(obs)==len(missing)==1:
            total=base0[(c,obs[0])];d[(c,obs[0])]=total*(1-frac);d[(c,missing[0])]=total*frac
        else:
            for s in missing:d[(c,s)]=Decimal(0)
    return d
bases={k:base_demand(k) for k in ('D0','D05','D10')}
rank={'单季':0,'第一季':1,'第二季':2};histrows=defaultdict(list);histbean=defaultdict(Decimal);last=defaultdict(set)
for row in hist:
    lid=row['land_id'];c=int(row['crop_id']);histrows[lid].append(row)
    if c in beans:histbean[lid]+=dec(row['area_mu'])
for lid,rows in histrows.items():
    m=max(rank[r['season']] for r in rows);last[lid]={int(r['crop_id']) for r in rows if rank[r['season']]==m}

def drivers(path):
    out=defaultdict(dict)
    for row in readcsv(path):out[row['scenario_id']][(int(row['crop_id']),int(row['year']))]={k:dec(row[k]) for k in ('demand_multiplier','yield_multiplier','cost_multiplier','price_multiplier')}
    return dict(sorted(out.items()))
training=drivers(RUN/'scenarios/training_drivers.csv');comparison=drivers(RUN/'scenarios/comparison_drivers.csv');stress=drivers(RUN/'scenarios/stress_drivers.csv')
assert len(training)==360 and len(comparison)==900 and len(stress)==18 and not(set(training)&set(comparison))
def midpoint():
    d={};wf=Decimal(1)
    for y in YEARS:
        wf*=Decimal('1.075');step=y-2023
        for c,row in crops.items():
            if '粮食' in row['crop_type']:pm=Decimal(1)
            elif '蔬菜' in row['crop_type']:pm=Decimal('1.05')**step
            elif row['crop_name']=='羊肚菌':pm=Decimal('.95')**step
            else:pm=Decimal('.97')**step
            d[(c,y)]={'demand_multiplier':wf if c in (6,7) else Decimal(1),'yield_multiplier':Decimal(1),'cost_multiplier':Decimal('1.05')**step,'price_multiplier':pm}
    return d

def verify_plan(name,rows):
    area=defaultdict(Decimal);beanarea=defaultdict(Decimal);keys=set();issues=[]
    for row in rows:
        lid=row['land_id'];y=int(row['year']);s=row['season'];c=int(row['crop_id']);a=dec(row['area_mu']);lt=lands[lid]['land_type'];k=(lid,y,s,c)
        if k in keys:issues.append(('duplicate',k))
        keys.add(k)
        if (c,lt,s) not in params or y not in YEARS:issues.append(('bad_key',k));continue
        A=dec(lands[lid]['area_mu'])
        if a+EPS<Decimal('.5')*A or a-A>EPS:issues.append(('area_link',k,a))
        area[(lid,y,s)]+=a
        if c in beans:beanarea[(lid,y,s)]+=a
    for lid,l in lands.items():
        A=dec(l['area_mu']);lt=l['land_type']
        for y in YEARS:
            if lt in ('平旱地','梯田','山坡地'):
                if abs(area[(lid,y,'单季')]-A)>EPS:issues.append(('capacity',lid,y))
            elif lt=='水浇地':
                v=(area[(lid,y,'单季')],area[(lid,y,'第一季')],area[(lid,y,'第二季')])
                if not ((abs(v[0]-A)<=EPS and v[1]==v[2]==0) or (v[0]==0 and abs(v[1]-A)<=EPS and abs(v[2]-A)<=EPS)):issues.append(('water_mode',lid,y,v))
            elif abs(area[(lid,y,'第一季')]-A)>EPS or abs(area[(lid,y,'第二季')]-A)>EPS:issues.append(('capacity',lid,y))
    pc=Counter((c,y,s) for lid,y,s,c in keys)
    if max(pc.values())>7:issues.append(('plot_cap',max(pc.values())))
    byslot=defaultdict(set)
    for lid,y,s,c in keys:byslot[(lid,y,s)].add(c)
    for lid,l in lands.items():
        previous=set(last[lid]);lt=l['land_type']
        for y in YEARS:
            order=['单季'] if lt in ('平旱地','梯田','山坡地') else (['单季'] if lt=='水浇地' and area[(lid,y,'单季')]>0 else ['第一季','第二季'])
            for s in order:
                current=byslot[(lid,y,s)]
                if previous&current:issues.append(('rotation',lid,y,s,sorted(previous&current)))
                previous=current
    for lid,l in lands.items():
        A=dec(l['area_mu'])
        for end in range(2025,2031):
            total=(histbean[lid] if end==2025 else Decimal(0))+sum((beanarea[(lid,y,s)] for y in range(max(2024,end-2),end+1) for s in ('单季','第一季','第二季')),Decimal(0))
            if total+EPS<A:issues.append(('bean_window',lid,end,total,A))
    return {'candidate':name,'activations':len(keys),'max_plots':max(pc.values()),'violations':len(issues),'valid':not issues,'examples':list(map(str,issues[:20]))}

def profit(rows,drv,basekind,sale):
    production=defaultdict(Decimal);cost=Decimal(0)
    for row in rows:
        lid=row['land_id'];y=int(row['year']);s=row['season'];c=int(row['crop_id']);a=dec(row['area_mu']);p=params[(c,lands[lid]['land_type'],s)];d=drv[(c,y)]
        production[(c,y,s)]+=a*dec(p['yield_jin_per_mu'])*d['yield_multiplier'];cost+=a*dec(p['cost_yuan_per_mu'])*d['cost_multiplier']
    revenue=Decimal(0);base=bases[basekind]
    for (c,y,s),qty in production.items():
        cap=base[(c,s)]*drv[(c,y)]['demand_multiplier'];full=min(qty,cap);extra=qty-full;pr=prices[(c,s)]*drv[(c,y)]['price_multiplier']
        revenue+=pr*(full+(Decimal(0) if sale=='S1' else Decimal('.5')*extra))
    return revenue-cost
def metrics(values):
    xs=sorted(values);n=len(xs);tail=xs[:math.ceil(.1*n)]
    return {'mean':statistics.fmean(values),'median':statistics.median(values),'p10':xs[max(0,math.ceil(.1*n)-1)],'worst10_mean':statistics.fmean(tail),'std':statistics.pstdev(values),'min':xs[0],'max':xs[-1]}

names=('B0','M0-CORR','M1-NET','M2-RELROB');run_paths={'B0':'B0','M0-CORR':'M0-CORR-R1','M1-NET':'M1-NET-R1','M2-RELROB':'M2-RELROB'}
plans={name:readcsv(RUN/run_paths[name]/'solution.csv') for name in names};checks=[verify_plan(n,plans[n]) for n in names];assert all(c['valid'] for c in checks)

world_of=lambda sid:sid.rsplit('-',1)[-1]
allrows=[];primary={};paired={};world_metrics={}
for basekind in ('D05','D0','D10'):
    for sale in ('S2','S1'):
        for name in names:
            vals=[float(profit(plans[name],drv,basekind,sale)) for drv in comparison.values()];m=metrics(vals)
            allrows.append({'candidate':name,'demand_base':basekind,'sale_case':sale,'relationship_world':'ALL',**{k:f'{v:.6f}' for k,v in m.items()}})
            for world in ('R0','RS','RSC'):
                wvals=[float(profit(plans[name],drv,basekind,sale)) for sid,drv in comparison.items() if world_of(sid)==world];wm=metrics(wvals)
                allrows.append({'candidate':name,'demand_base':basekind,'sale_case':sale,'relationship_world':world,**{k:f'{v:.6f}' for k,v in wm.items()}})
                if basekind=='D05' and sale=='S2':world_metrics[(name,world)]=wm
            if basekind=='D05' and sale=='S2':primary[name]=m;paired[name]=vals

stressrows=[]
for name in names:
    vals=[float(profit(plans[name],drv,'D05','S2')) for drv in stress.values()];m=metrics(vals)
    stressrows.append({'candidate':name,**{k:f'{v:.6f}' for k,v in m.items()}})
    primary[name]['named_stress_min']=m['min'];primary[name]['underperform_B0_probability']=sum(v<b for v,b in zip(paired[name],paired['B0']))/len(paired[name])

pairwise=[]
for a,b in (('M0-CORR','B0'),('M1-NET','M0-CORR'),('M2-RELROB','M0-CORR'),('M2-RELROB','M1-NET')):
    diffs=[x-y for x,y in zip(paired[a],paired[b])]
    pairwise.append({'candidate':a,'reference':b,'mean_difference_yuan':f'{statistics.fmean(diffs):.6f}','min_difference_yuan':f'{min(diffs):.6f}','max_difference_yuan':f'{max(diffs):.6f}','positive_scenarios':sum(d>0 for d in diffs),'equal_scenarios':sum(d==0 for d in diffs),'negative_scenarios':sum(d<0 for d in diffs)})

similarity=[]
for a,b in (('M0-CORR','B0'),('M1-NET','M0-CORR'),('M2-RELROB','M0-CORR'),('M2-RELROB','M1-NET')):
    aa={(r['land_id'],r['year'],r['season'],r['crop_id']):dec(r['area_mu']) for r in plans[a]};bb={(r['land_id'],r['year'],r['season'],r['crop_id']):dec(r['area_mu']) for r in plans[b]};keys=set(aa)|set(bb)
    similarity.append({'candidate':a,'reference':b,'area_l1_mu':str(sum((abs(aa.get(k,0)-bb.get(k,0)) for k in keys),Decimal(0))),'activation_keys_different':len(set(aa)^set(bb))})

accounting=[];trainsets={
    'M0-CORR':{sid:d for sid,d in training.items() if world_of(sid)=='R0'},
    'M1-NET':{sid:d for sid,d in training.items() if world_of(sid)=='RSC'},
    'M2-RELROB':training,
}
for name in ('M0-CORR','M1-NET','M2-RELROB'):
    vals=[profit(plans[name],drv,'D05','S2') for drv in trainsets[name].values()];actual=sum(vals,Decimal(0))/Decimal(len(vals));solver=json.loads((RUN/run_paths[name]/'solver.json').read_text(encoding='utf-8'));diff=actual-dec(solver['training_mean_profit']);accounting.append({'candidate':name,'run_id':run_paths[name],'independent_training_mean':str(actual),'solver_training_mean':solver['training_mean_profit'],'difference_yuan':str(diff),'passed':abs(diff)<=Decimal('.1')})
assert all(x['passed'] for x in accounting)

scenario_rows=readcsv(RUN/'scenarios/training_drivers.csv')+readcsv(RUN/'scenarios/comparison_drivers.csv')+readcsv(RUN/'scenarios/stress_drivers.csv')
relationship_checks={
    'r0_multiplier_exactly_one':all(dec(r['relationship_multiplier'])==1 for r in scenario_rows if r['relationship_world']=='R0'),
    'multiplier_within_clip':all(Decimal('.9')<=dec(r['relationship_multiplier'])<=Decimal('1.1') for r in scenario_rows),
    'demand_factorizes':all(abs(dec(r['demand_multiplier'])-dec(r['demand_multiplier_base'])*dec(r['relationship_multiplier']))<=Decimal('0.0000001') for r in scenario_rows),
    'future_holdout_absent':not any('holdout' in p.name.lower() for p in (RUN/'scenarios').iterdir()),
}
assert all(relationship_checks.values())

summary=[]
for n in names:
    m=primary[n];summary.append({'candidate':n,'mean_profit_yuan':f"{m['mean']:.6f}",'p10_profit_yuan':f"{m['p10']:.6f}",'worst10_mean_yuan':f"{m['worst10_mean']:.6f}",'std_yuan':f"{m['std']:.6f}",'named_stress_min_yuan':f"{m['named_stress_min']:.6f}",'underperform_B0_probability':f"{m['underperform_B0_probability']:.6f}",'worst_world_mean_yuan':f"{min(world_metrics[(n,w)]['mean'] for w in ('R0','RS','RSC')):.6f}",'activations':next(c['activations'] for c in checks if c['candidate']==n)})

m0=primary['M0-CORR'];m1=primary['M1-NET'];m2=primary['M2-RELROB'];b0=primary['B0']
m1_pass=(m1['mean']>=m0['mean']*1.001 and m1['worst10_mean']>=m0['worst10_mean']*.999 and world_metrics[('M1-NET','RSC')]['mean']>world_metrics[('M0-CORR','RSC')]['mean'])
best_nonrobust='M1-NET' if m1['mean']>m0['mean'] else 'M0-CORR';best=primary[best_nonrobust]
best_worst=min(world_metrics[(best_nonrobust,w)]['mean'] for w in ('R0','RS','RSC'));m2_worst=min(world_metrics[('M2-RELROB',w)]['mean'] for w in ('R0','RS','RSC'))
m2_pass=False
m0_pass=m0['mean']>=b0['mean']*1.001 and m0['worst10_mean']>=b0['worst10_mean']*.999
recommended='M2-RELROB' if m2_pass else 'M1-NET' if m1_pass else 'M0-CORR' if m0_pass else 'B0'
selection={'M1_over_M0_pass':m1_pass,'M2_over_best_nonrobust_pass':m2_pass,'M2_evidence_status':'INCONCLUSIVE_R1_BUDGET_STOP; R0 independently checked but gap exceeds 0.1% decision threshold','M0_over_B0_pass':m0_pass,'best_nonrobust':best_nonrobust,'recommended_initial_model':recommended}

writecsv(RUN/'comparison.csv',allrows);writecsv(RUN/'stress_comparison.csv',stressrows);writecsv(RUN/'pairwise_comparison.csv',pairwise);writecsv(RUN/'plan_similarity.csv',similarity);writecsv(RUN/'primary_summary.csv',summary)
validation={'protocol':'Q3-TRIAL-v1','authorization':'U018','selected_run_ids':run_paths,'method':'independent standard-library reconstruction; imports neither generator nor solver','source_snapshots_valid':True,'scenario_sets':{'training_world_scenarios':360,'comparison_world_scenarios':900,'stress':18,'future_holdout_opened':False},'constraint_checks':checks,'accounting_checks':accounting,'relationship_checks':relationship_checks,'primary_summary':summary,'pairwise_comparison':pairwise,'plan_similarity':similarity,'selection':selection,'passed':all(c['valid'] for c in checks) and all(x['passed'] for x in accounting) and all(relationship_checks.values()),'human_verification':'pending','limitations':['All correlations and relationship edges are synthetic assumptions, not estimates','D05 demand base uses production proxy, not observed sales','Aggregate bean-area rule has a spatial-coverage limitation','All MIP claims are limited by recorded solver gaps']}
dump(RUN/'validation.json',validation);print(json.dumps({'passed':validation['passed'],'summary':summary,'selection':selection,'accounting':accounting},ensure_ascii=False,indent=2));assert validation['passed']
