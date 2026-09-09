"""Independent verifier for Q3-DEEPEN-v1; imports neither generator nor solver."""
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

state=json.loads((ROOT/'state/state.json').read_text(encoding='utf-8'));assert state['stage']=='DEEPEN' and state['active_question']=='Q3' and any(a['id']=='U020' for a in state['authorizations'])
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

DEEP=Q/'deep_runs'; names=('B0','N0','N10','N30')
paths={'B0':ROOT/'questions/Q2/runs/M0-R1/solution.csv',**{n:DEEP/n/'solution.csv' for n in names[1:]}}
plans={n:readcsv(paths[n]) for n in names};checks=[verify_plan(n,plans[n]) for n in names];assert all(c['valid'] for c in checks)

def world(sid):return sid.rsplit('-',1)[-1]
def summary(plan,ds):
    vals=[float(profit(plan,d,'D05','S2')) for d in ds.values()];mm=metrics(vals)
    return {**mm,**{w+'_mean':statistics.fmean(float(profit(plan,d,'D05','S2')) for sid,d in ds.items() if world(sid)==w) for w in ('R0','RS','RSC')}}

calc={n:summary(plans[n],comparison) for n in names}
reported={r['candidate']:r for r in readcsv(DEEP/'preholdout_summary.csv')};summary_checks=[]
for n in names:
    fields=('mean','worst10_mean','R0_mean','RS_mean','RSC_mean')
    ok=all(abs(calc[n][k]-float(reported[n][k]))<=.1 for k in fields)
    summary_checks.append({'candidate':n,'passed':ok,'max_error_yuan':max(abs(calc[n][k]-float(reported[n][k])) for k in fields)})
assert all(x['passed'] for x in summary_checks)

b0keys={(r['land_id'],r['year'],r['season'],r['crop_id']) for r in plans['B0']};accounting=[]
train_rsc={sid:d for sid,d in training.items() if world(sid)=='RSC'}
for n,k in (('N0',0),('N10',10),('N30',30)):
    solver=json.loads((DEEP/n/'solver.json').read_text(encoding='utf-8'));actual=statistics.fmean(float(profit(plans[n],d,'D05','S2')) for d in train_rsc.values());keys={(r['land_id'],r['year'],r['season'],r['crop_id']) for r in plans[n]};hamming=len(keys^b0keys)
    item={'candidate':n,'independent_training_mean':actual,'reported_training_mean':solver['training_mean_profit'],'difference_yuan':actual-solver['training_mean_profit'],'hamming_changes_from_B0':hamming,'limit':k,'passed':abs(actual-solver['training_mean_profit'])<=.1 and hamming<=k,'evidence_status':'EXCLUDED_WRONG_REFERENCE' if n=='N30' and hamming>k else 'VALID'}
    accounting.append(item)
assert all(x['passed'] for x in accounting if x['candidate'] in ('N0','N10'))
assert next(x for x in accounting if x['candidate']=='N30')['evidence_status']=='EXCLUDED_WRONG_REFERENCE'

base=calc['B0'];eligible=[]
for n in ('N0','N10'):
    r=calc[n];activations=next(c['activations'] for c in checks if c['candidate']==n)
    passed=(r['mean']>=base['mean']*1.001 and r['worst10_mean']>=base['worst10_mean']*.999 and r['RSC_mean']>base['RSC_mean'] and sum(r[w+'_mean']>=base[w+'_mean'] for w in ('R0','RS','RSC'))>=2 and activations<=next(c['activations'] for c in checks if c['candidate']=='B0')+10)
    if passed:eligible.append(n)
selection=json.loads((DEEP/'preholdout_selection.json').read_text(encoding='utf-8'));selection_check={'independent_eligible':eligible,'reported_challenger':selection['challenger'],'passed':not eligible and selection['challenger'] is None and selection['holdout_seen'] is False};assert selection_check['passed']

holdout=drivers(DEEP/'scenarios/holdout_drivers.csv');holdout_ids={sid.rsplit('-',1)[0] for sid in holdout};holdout_worlds=Counter(world(sid) for sid in holdout)
assert len(holdout)==1500 and len(holdout_ids)==500 and holdout_worlds==Counter({'R0':500,'RS':500,'RSC':500})
hcalc=summary(plans['B0'],holdout);hrow=readcsv(DEEP/'holdout_summary.csv')[0]
holdout_check={'scenario_count':len(holdout),'underlying_count':len(holdout_ids),'reported_mean_error_yuan':hcalc['mean']-float(hrow['mean']),'reported_worst10_error_yuan':hcalc['worst10_mean']-float(hrow['worst10_mean']),'passed':abs(hcalc['mean']-float(hrow['mean']))<=.1 and abs(hcalc['worst10_mean']-float(hrow['worst10_mean']))<=.1};assert holdout_check['passed']

mechanism=readcsv(DEEP/'mechanism_by_crop_year.csv');sum_rs=sum(float(r['mean_RS_minus_R0_yuan']) for r in mechanism);sum_rsc=sum(float(r['mean_RSC_minus_R0_yuan']) for r in mechanism)
mechanism_check={'rows':len(mechanism),'sum_RS_minus_R0':sum_rs,'direct_RS_minus_R0':base['RS_mean']-base['R0_mean'],'sum_RSC_minus_R0':sum_rsc,'direct_RSC_minus_R0':base['RSC_mean']-base['R0_mean'],'passed':abs(sum_rs-(base['RS_mean']-base['R0_mean']))<=.1 and abs(sum_rsc-(base['RSC_mean']-base['R0_mean']))<=.1};assert mechanism_check['passed']

sens=readcsv(DEEP/'sensitivity_summary.csv');sensitivity_check={'rows':len(sens),'expected_rows':3*3*2*4,'strengths':sorted({r['strength'] for r in sens}),'complete_cells':len({(r['strength'],r['demand_base'],r['sale_rule'],r['candidate']) for r in sens})==len(sens)};sensitivity_check['passed']=len(sens)==sensitivity_check['expected_rows'] and sensitivity_check['complete_cells'];assert sensitivity_check['passed']

final=json.loads((DEEP/'final_selection.json').read_text(encoding='utf-8'));no_m2=not any('M2' in p.name for p in DEEP.rglob('*'))
valid_accounting=all(x['passed'] for x in accounting if x['candidate'] in ('N0','N10'))
passed=all(c['valid'] for c in checks) and valid_accounting and all(x['passed'] for x in summary_checks) and selection_check['passed'] and mechanism_check['passed'] and sensitivity_check['passed'] and holdout_check['passed'] and no_m2 and final['selected']=='B0'
validation={'protocol':'Q3-DEEPEN-v1','authorization':'U020','method':'independent standard-library reconstruction; imports neither generator nor solver','source_snapshots_valid':True,'constraint_checks':checks,'accounting_checks':accounting,'preholdout_summary_checks':summary_checks,'selection_check':selection_check,'mechanism_check':mechanism_check,'sensitivity_check':sensitivity_check,'holdout_check':holdout_check,'final_selection':final,'m2_rerun_absent':no_m2,'passed':passed,'human_verification':'pending','limitations':['Relationship graph and coefficients are synthetic assumptions','D05 uses production proxy rather than observed sales','Aggregate bean-area rule does not prove strict whole-plot coverage','N30 used N10 as its Hamming reference, changed 40 B0 activations, and is excluded; it was not rerun after holdout access']}
dump(DEEP/'validation.json',validation);print(json.dumps({'passed':validation['passed'],'selection':selection_check,'holdout':holdout_check,'accounting':accounting},ensure_ascii=False,indent=2));assert validation['passed']

