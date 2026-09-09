"""Independent Q1 trial verifier. Reads exported CSVs and frozen data only."""
from pathlib import Path
from collections import defaultdict, Counter
from decimal import Decimal
import csv, hashlib, itertools, json, math

ROOT=Path(__file__).resolve().parents[2];Q=Path(__file__).resolve().parent;D=ROOT/'data/frozen/G1-v1-base';RUNS=Q/'runs';Y=range(2024,2031)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def readcsv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def dec(x):return Decimal(str(x))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def writecsv(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

state=json.loads((ROOT/'state/state.json').read_text(encoding='utf-8'));assert state['stage']=='TRIAL'
assert all(sha(ROOT/p)==h for p,h in state['data_snapshots']['G1-v1-base'].items())
lands={r['land_id']:r for r in readcsv(D/'lands.csv')};crops={int(r['crop_id']):r for r in readcsv(D/'crops.csv')};params={(int(r['crop_id']),r['land_type'],r['season']):r for r in readcsv(D/'parameters_effective.csv')}
hist=readcsv(D/'planting_2023.csv');prod=readcsv(D/'production_2023.csv');beans={c for c,r in crops.items() if r['is_legume']=='true'}
base={(int(r['crop_id']),r['season']):dec(r['production_estimate_jin']) for r in prod};seasons=defaultdict(set);price=defaultdict(set)
for c,lt,s in params:seasons[c].add(s);price[(c,s)].add(dec(params[(c,lt,s)]['price_midpoint_candidate_yuan_per_jin']))
assert all(len(v)==1 for v in price.values());price={k:next(iter(v)) for k,v in price.items()}
demands={}
for sid,f in [('D0',Decimal(0)),('D05',Decimal('.05')),('D10',Decimal('.10'))]:
    dd=dict(base)
    for c,ss in seasons.items():
        obs=[s for s in ss if (c,s) in base];miss=[s for s in ss if (c,s) not in base]
        if f and len(obs)==len(miss)==1:
            total=base[(c,obs[0])];dd[(c,obs[0])]=total*(1-f);dd[(c,miss[0])]=total*f
        else:
            for s in miss:dd[(c,s)]=Decimal(0)
    demands[sid]=dd
histbean=defaultdict(Decimal);last=defaultdict(set);hr=defaultdict(list);rank={'单季':0,'第一季':1,'第二季':2}
for r in hist:
    c=int(r['crop_id']);hr[r['land_id']].append(r)
    if c in beans:histbean[r['land_id']]+=dec(r['area_mu'])
for l,rs in hr.items():
    m=max(rank[r['season']] for r in rs);last[l]={int(r['crop_id']) for r in rs if rank[r['season']]==m}

checks=[];metrics=[];violations=[]
def ck(run,name,ok,detail=''):
    checks.append({'run_id':run,'check':name,'passed':bool(ok),'detail':str(detail)[:1000]})

def verify_demand_files():
    for sid in demands:
        rows=readcsv(RUNS/f'demand-{sid}/demand.csv');got={(int(r['crop_id']),r['season']):dec(r['annual_normal_sales_limit_jin']) for r in rows}
        ck('batch','demand_'+sid,got==demands[sid] and all(r['status']=='model_assumption_not_observed' for r in rows),f'{len(got)} rows')

def verify_solution(run,path,sid,sale,alpha,cap,candidate):
    rows=readcsv(path);area=defaultdict(Decimal);z=set();production=defaultdict(Decimal);cost=Decimal(0);bean=defaultdict(Decimal);local=[]
    for r in rows:
        lid=r['land_id'];y=int(r['year']);s=r['season'];c=int(r['crop_id']);a=dec(r['area_mu']);lt=lands[lid]['land_type'];key=(lid,y,s,c)
        if lid not in lands or (c,lt,s) not in params or y not in Y:local.append(('bad_key',key));continue
        if key in z:local.append(('duplicate',key))
        z.add(key);area[(lid,y,s)]+=a
        p=params[(c,lt,s)];production[(c,y,s)]+=a*dec(p['yield_jin_per_mu']);cost+=a*dec(p['cost_yuan_per_mu'])
        if c in beans:bean[(lid,y)]+=a
        if a+Decimal('1e-7')<alpha*dec(lands[lid]['area_mu']) or a-decimal_eps()>dec(lands[lid]['area_mu']):local.append(('area_link',key,a))
        if dec(r['yield_jin_per_mu'])!=dec(p['yield_jin_per_mu']) or dec(r['cost_yuan_per_mu'])!=dec(p['cost_yuan_per_mu']) or dec(r['price_yuan_per_jin'])!=price[(c,s)]:local.append(('parameter_copy',key))
    # Land capacity and water mode.
    for lid,l in lands.items():
        A=dec(l['area_mu']);lt=l['land_type']
        for y in Y:
            if lt in ('平旱地','梯田','山坡地'):
                if abs(area[(lid,y,'单季')]-A)>decimal_eps():local.append(('capacity',lid,y))
            elif lt=='水浇地':
                q=(area[(lid,y,'单季')],area[(lid,y,'第一季')],area[(lid,y,'第二季')])
                if not ((abs(q[0]-A)<=decimal_eps() and q[1]==q[2]==0) or (q[0]==0 and abs(q[1]-A)<=decimal_eps() and abs(q[2]-A)<=decimal_eps())):local.append(('water_mode',lid,y,q))
            else:
                if abs(area[(lid,y,'第一季')]-A)>decimal_eps() or abs(area[(lid,y,'第二季')]-A)>decimal_eps():local.append(('capacity',lid,y))
    pc=Counter((c,y,s) for lid,y,s,c in z)
    if pc and max(pc.values())>cap:local.append(('plot_cap',max(pc.values())))
    # Consecutive actual crop sets.
    byslot=defaultdict(set)
    for lid,y,s,c in z:byslot[(lid,y,s)].add(c)
    for lid,l in lands.items():
        prev=set(last[lid]);lt=l['land_type']
        for y in Y:
            order=['单季'] if lt in ('平旱地','梯田','山坡地') else (['单季'] if area[(lid,y,'单季')]>0 else ['第一季','第二季']) if lt=='水浇地' else ['第一季','第二季']
            for s in order:
                now=byslot[(lid,y,s)]
                if prev & now:local.append(('rotation',lid,y,s,sorted(prev&now)))
                prev=now
    for lid,l in lands.items():
        A=dec(l['area_mu'])
        for end in range(2025,2031):
            total=(histbean[lid] if end==2025 else Decimal(0))+sum((bean[(lid,y)] for y in range(max(2024,end-2),end+1)),Decimal(0))
            if total+decimal_eps()<A:local.append(('bean_window',lid,end,total,A))
    revenue=Decimal(0);normal=Decimal(0);excess=Decimal(0)
    for (c,y,s),q in production.items():
        full=min(q,demands[sid][(c,s)]);extra=q-full;normal+=full;excess+=extra;revenue+=price[(c,s)]*(full+(Decimal(0) if sale=='S1' else Decimal('.5')*extra))
    profit=revenue-cost
    solver=json.loads((path.parent/'solver.json').read_text(encoding='utf-8'))
    reported=dec(solver['selected_profit']) if 'selected_profit' in solver else None
    # In stage 2, sold-full variables are accounting auxiliaries and need not be
    # maximal when the objective is only activation count. The exported planting
    # plan's attainable revenue is therefore recomputed as min(production,demand).
    # It must never be below the profit credited inside the model.
    if reported is not None and reported-profit>Decimal('.1'):local.append(('model_profit_above_export_recalculation',reported,profit))
    ck(run,'all_hard_constraints_and_recalculation',not local,local[:20]);violations.extend({'run_id':run,'detail':str(x)} for x in local)
    if reported is not None:
        ck(run,'model_accounting_profit_not_above_export_profit',reported<=profit+Decimal('.1'),{'model_profit':str(reported),'export_profit':str(profit),'unused_sales_auxiliary_slack':str(profit-reported)})
    dump(path.parent/'evaluation.json',{'independent_export_profit_yuan':str(profit),'revenue_yuan':str(revenue),'cost_yuan':str(cost),'model_accounting_profit_yuan':str(reported) if reported is not None else None,'unused_sales_auxiliary_slack_yuan':str(profit-reported) if reported is not None else None,'hard_constraint_violations':local})
    metrics.append({'run_id':run,'type':'main' if candidate in ('M0','M1','M1R') else 'diagnostic','candidate':candidate,'scenario':sid,'sale_case':sale,'profit_yuan':f'{profit:.6f}','revenue_yuan':f'{revenue:.6f}','cost_yuan':f'{cost:.6f}','production_jin':f'{sum(production.values()):.6f}','normal_sales_jin':f'{normal:.6f}','excess_jin':f'{excess:.6f}','activations':len(z),'min_area_fraction':f'{min(dec(r["area_mu"])/dec(lands[r["land_id"]]["area_mu"]) for r in rows):.6f}','max_plots_per_crop_year_season':max(pc.values()),'valid':not local})

def decimal_eps():return Decimal('0.00001')

def small_examples():
    # Example 1: exact two-part revenue.
    q=Decimal(120);d=Decimal(100);p=Decimal(2);s1=p*min(q,d);s2=p*min(q,d)+p*Decimal('.5')*(q-min(q,d))
    ck('small','sales_piecewise',s1==200 and s2==220,{'S1':str(s1),'S2':str(s2)})
    # Example 2: water mode enumeration allows rice-only or two vegetable seasons only.
    modes=[(r,v1,v2) for r,v1,v2 in itertools.product((0,1),repeat=3) if r+v1==1 and r+v2==1]
    ck('small','water_exclusive_mode',modes==[(0,1,1),(1,0,0)],modes)
    # Example 3: with 2023 non-bean, enumerate B/N in 2024-25; only sequences containing B satisfy first window, and repeats violate rotation.
    seq=[]
    for a,b in itertools.product('BN',repeat=2):
        rotation=(a!=b);bean_ok=('B' in (a,b));seq.append({'sequence':a+b,'feasible':rotation and bean_ok})
    ck('small','rotation_and_first_bean_window',[x['sequence'] for x in seq if x['feasible']]==['BN','NB'],seq)

verify_demand_files()
for sid in ('D0','D05','D10'):
    for sale in ('S1','S2'):
        verify_solution(f'M0-{sid}-{sale}',RUNS/f'M0-{sid}-{sale}/solution.csv',sid,sale,Decimal('.5'),7,'M0')
        verify_solution(f'M1-{sid}-{sale}',RUNS/f'M1-{sid}-{sale}/solution.csv',sid,sale,Decimal('.5'),7,'M1')
        verify_solution(f'M1R-{sid}-{sale}',RUNS/f'M1R-{sid}-{sale}/solution.csv',sid,sale,Decimal('.5'),7,'M1R')
        lp=json.loads((RUNS/f'LP-{sid}-{sale}/lp_upper_bound.json').read_text(encoding='utf-8'))
        related=[dec(m['profit_yuan']) for m in metrics if m['scenario']==sid and m['sale_case']==sale and m['candidate'] in ('M0','M1','M1R')]
        ck(f'LP-{sid}-{sale}','lp_is_upper_bound',lp['solution_valid'] and dec(lp['recomputed_profit'])+Decimal('.1')>=max(related),{'lp':lp['recomputed_profit'],'solutions':list(map(str,related))})
for sale in ('S1','S2'):
    verify_solution(f'DIAG-alpha25-D0-{sale}',RUNS/f'DIAG-alpha25-D0-{sale}/solution.csv','D0',sale,Decimal('.25'),7,'M1-alpha25')
    verify_solution(f'DIAG-cap10-D0-{sale}',RUNS/f'DIAG-cap10-D0-{sale}/solution.csv','D0',sale,Decimal('.5'),10,'M1-cap10')
small_examples()
main={(m['candidate'],m['scenario'],m['sale_case']):m for m in metrics if m['candidate'] in ('M0','M1','M1R')}
comparison=[]
for sid in ('D0','D05','D10'):
    for sale in ('S1','S2'):
        a=main[('M0',sid,sale)];legacy=main[('M1',sid,sale)];b=main[('M1R',sid,sale)];pa,pb=dec(a['profit_yuan']),dec(b['profit_yuan'])
        st=json.loads((RUNS/f'M1R-{sid}-{sale}/solver.json').read_text(encoding='utf-8'))
        lp=json.loads((RUNS/f'LP-{sid}-{sale}/lp_upper_bound.json').read_text(encoding='utf-8'))
        p1=dec(st['stage1']['recomputed_profit'])
        comparison.append({'scenario':sid,'sale_case':sale,'M0_profit_yuan':a['profit_yuan'],'legacy_M1_profit_yuan':legacy['profit_yuan'],'M1R_stage1_incumbent_yuan':f'{p1:.6f}','M1R_stage2_export_profit_yuan':b['profit_yuan'],'M1R_stage2_minus_M0_yuan':f'{pb-pa:.6f}','M1R_stage2_improvement_percent':f'{((pb/pa)-1)*100:.6f}','M0_activations':a['activations'],'M1R_activations':b['activations'],'LP_upper_profit_yuan':f"{dec(lp['recomputed_profit']):.6f}",'M1R_stage1_gap_to_LP_percent':f'{((dec(lp["recomputed_profit"])/p1)-1)*100:.6f}','stage1_status':st['stage1']['status'],'stage1_mip_gap':st['stage1']['mip_gap'],'stage2_status':st['stage2']['status'] if st.get('stage2') else ''})
writecsv(RUNS/'solution_metrics.csv',metrics);writecsv(RUNS/'comparison.csv',comparison)
validation={'protocol':'Q1-TRIAL-v1','verifier_sha256':sha(Path(__file__)),'checks':checks,'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),'violations':violations,'source_snapshot_valid':True,'human_verification':'pending','limitations':['Demand scenarios are assumptions','Bean requirement uses aggregate area proxy','No claim of global optimality unless a solver status and gap support it','CSV outputs only; result templates not yet authored']}
dump(RUNS/'validation.json',validation)
print(json.dumps({'checks':len(checks),'passed':validation['passed'],'failed':validation['failed'],'violations':len(violations),'main_comparison':comparison},ensure_ascii=False,indent=2))
assert validation['failed']==0
