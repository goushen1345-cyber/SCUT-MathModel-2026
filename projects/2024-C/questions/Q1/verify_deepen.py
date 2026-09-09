"""Independent verifier for U008 Q1-DEEPEN-v1; never imports solver code."""
from pathlib import Path
from collections import defaultdict, Counter
from decimal import Decimal
from datetime import datetime, timezone
import csv, hashlib, itertools, json

ROOT=Path(__file__).resolve().parents[2];Q=Path(__file__).resolve().parent;D=ROOT/'data/frozen/G1-v1-base';RUN=Q/'runs';DEEP=Q/'deep_runs';Y=range(2024,2031);EPS=Decimal('.00002')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def readcsv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def dec(x):return Decimal(str(x))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def writecsv(p,rows,fields=None):
    fields=fields or sorted({k for r in rows for k in r})
    with p.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

state=json.loads((ROOT/'state/state.json').read_text(encoding='utf-8'));assert state['stage']=='DEEPEN'
assert any(a['id']=='U008' and a['plan_version']=='Q1-DEEPEN-v1' for a in state['authorizations'])
assert all(sha(ROOT/p)==h for p,h in state['data_snapshots']['G1-v1-base'].items())
lands={r['land_id']:r for r in readcsv(D/'lands.csv')};crops={int(r['crop_id']):r for r in readcsv(D/'crops.csv')};params={(int(r['crop_id']),r['land_type'],r['season']):r for r in readcsv(D/'parameters_effective.csv')}
hist=readcsv(D/'planting_2023.csv');prod=readcsv(D/'production_2023.csv');beans={c for c,r in crops.items() if r['is_legume']=='true'}
base={(int(r['crop_id']),r['season']):dec(r['production_estimate_jin']) for r in prod};seasons=defaultdict(set);prices=defaultdict(set)
for c,lt,s in params:seasons[c].add(s);prices[(c,s)].add(dec(params[(c,lt,s)]['price_midpoint_candidate_yuan_per_jin']))
assert all(len(v)==1 for v in prices.values());prices={k:next(iter(v)) for k,v in prices.items()}
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
rank={'单季':0,'第一季':1,'第二季':2};hr=defaultdict(list);histbean=defaultdict(Decimal);histbean_slot=defaultdict(Decimal);last=defaultdict(set)
for row in hist:
    lid=row['land_id'];c=int(row['crop_id']);hr[lid].append(row)
    if c in beans:histbean[lid]+=dec(row['area_mu']);histbean_slot[(lid,row['season'])]+=dec(row['area_mu'])
for lid,rows in hr.items():
    m=max(rank[r['season']] for r in rows);last[lid]={int(r['crop_id']) for r in rows if rank[r['season']]==m}

checks=[];violations=[];metrics=[]
def ck(run,name,ok,detail=''):checks.append({'run_id':run,'check':name,'passed':bool(ok),'detail':str(detail)[:1000]})
def calculate(rows,sid,sale):
    production=defaultdict(Decimal);cost=Decimal(0)
    for row in rows:
        c=int(row['crop_id']);y=int(row['year']);s=row['season'];a=dec(row['area_mu']);p=params[(c,lands[row['land_id']]['land_type'],s)]
        production[(c,y,s)]+=a*dec(p['yield_jin_per_mu']);cost+=a*dec(p['cost_yuan_per_mu'])
    revenue=Decimal(0)
    for (c,y,s),q in production.items():
        full=min(q,demands[sid][(c,s)]);extra=q-full;revenue+=prices[(c,s)]*(full+(Decimal(0) if sale=='S1' else Decimal('.5')*extra))
    return revenue-cost,revenue,cost,production

def verify(run,path,sid,sale,cap=7,strict=False,kind='main'):
    rows=readcsv(path);area=defaultdict(Decimal);z=set();beanarea=defaultdict(Decimal);local=[]
    for row in rows:
        lid=row['land_id'];y=int(row['year']);s=row['season'];c=int(row['crop_id']);a=dec(row['area_mu']);lt=lands[lid]['land_type'];k=(lid,y,s,c)
        if (c,lt,s) not in params or y not in Y:local.append(('bad_key',k));continue
        if k in z:local.append(('duplicate',k))
        z.add(k);area[(lid,y,s)]+=a
        if c in beans:beanarea[(lid,y,s)]+=a
        if a+EPS<Decimal('.5')*dec(lands[lid]['area_mu']) or a-dec(lands[lid]['area_mu'])>EPS:local.append(('area_link',k,a))
        p=params[(c,lt,s)]
        if dec(row['yield_jin_per_mu'])!=dec(p['yield_jin_per_mu']) or dec(row['cost_yuan_per_mu'])!=dec(p['cost_yuan_per_mu']) or dec(row['price_yuan_per_jin'])!=prices[(c,s)]:local.append(('parameter_copy',k))
    for lid,l in lands.items():
        A=dec(l['area_mu']);lt=l['land_type']
        for y in Y:
            if lt in ('平旱地','梯田','山坡地'):
                if abs(area[(lid,y,'单季')]-A)>EPS:local.append(('capacity',lid,y))
            elif lt=='水浇地':
                q=(area[(lid,y,'单季')],area[(lid,y,'第一季')],area[(lid,y,'第二季')])
                if not ((abs(q[0]-A)<=EPS and q[1]==q[2]==0) or (q[0]==0 and abs(q[1]-A)<=EPS and abs(q[2]-A)<=EPS)):local.append(('water_mode',lid,y,q))
            elif abs(area[(lid,y,'第一季')]-A)>EPS or abs(area[(lid,y,'第二季')]-A)>EPS:local.append(('capacity',lid,y))
    pc=Counter((c,y,s) for lid,y,s,c in z)
    if cap is not None and pc and max(pc.values())>cap:local.append(('plot_cap',max(pc.values()),cap))
    byslot=defaultdict(set)
    for lid,y,s,c in z:byslot[(lid,y,s)].add(c)
    for lid,l in lands.items():
        prev=set(last[lid]);lt=l['land_type']
        for y in Y:
            order=['单季'] if lt in ('平旱地','梯田','山坡地') else (['单季'] if area[(lid,y,'单季')]>0 else ['第一季','第二季']) if lt=='水浇地' else ['第一季','第二季']
            for s in order:
                now=byslot[(lid,y,s)]
                if prev&now:local.append(('rotation',lid,y,s,sorted(prev&now)))
                prev=now
    for lid,l in lands.items():
        A=dec(l['area_mu'])
        for end in range(2025,2031):
            if strict:
                hist_full=end==2025 and any(abs(a-A)<=EPS for (ll,s),a in histbean_slot.items() if ll==lid)
                full=hist_full or any(abs(beanarea[(lid,y,s)]-A)<=EPS for y in range(max(2024,end-2),end+1) for s in ('单季','第一季','第二季'))
                if not full:local.append(('strict_bean_window',lid,end))
            else:
                total=(histbean[lid] if end==2025 else Decimal(0))+sum((beanarea[(lid,y,s)] for y in range(max(2024,end-2),end+1) for s in ('单季','第一季','第二季')),Decimal(0))
                if total+EPS<A:local.append(('bean_window',lid,end,total,A))
    profit,revenue,cost,production=calculate(rows,sid,sale);solver=json.loads((path.parent/'solver.json').read_text(encoding='utf-8'))
    if kind=='main' and abs(dec(solver['model_accounting_profit'])-profit)>Decimal('.1'):local.append(('accounting',solver['model_accounting_profit'],profit))
    ck(run,'independent_constraints_and_profit',not local,local[:20]);violations.extend({'run_id':run,'detail':str(x)} for x in local)
    m={'run_id':run,'kind':kind,'scenario':sid,'sale_case':sale,'profit_yuan':f'{profit:.6f}','revenue_yuan':f'{revenue:.6f}','cost_yuan':f'{cost:.6f}','activations':len(z),'max_plots':max(pc.values()),'valid':not local};metrics.append(m);return m,rows

main={};solutions={}
for sid in ('D0','D05','D10'):
    for sale in ('S1','S2'):
        m,rows=verify(f'M1R3-{sid}-{sale}',DEEP/f'M1R3-{sid}-{sale}'/'solution.csv',sid,sale);main[(sid,sale)]=m;solutions[(sid,sale)]=rows
pareto=[]
for sale in ('S1','S2'):
    for tag,ret in [('profit','1.0'),('0p999','.999'),('0p995','.995'),('0p99','.99')]:
        run=f'PARETO-D0-{sale}-{tag}'
        if sale=='S2' and tag=='0p99':
            verify(run,DEEP/run/'solution.csv','D0',sale,cap=None,kind='pareto_superseded_attempt')
            run+='-R1'
        m,_=verify(run,DEEP/run/'solution.csv','D0',sale,cap=None,kind='pareto');pareto.append({**m,'retention':ret})
bean=[]
for sale in ('S1','S2'):
    run=f'BEAN-STRICT-D0-{sale}';m,_=verify(run,DEEP/run/'solution.csv','D0',sale,cap=7,strict=True,kind='strict_bean');basep=dec(main[('D0',sale)]['profit_yuan']);p=dec(m['profit_yuan']);bean.append({**m,'main_profit_yuan':f'{basep:.6f}','strict_minus_main_yuan':f'{p-basep:.6f}','strict_change_percent':f'{(p/basep-1)*100:.6f}'})

comparison=[]
for sid in ('D0','D05','D10'):
    for sale in ('S1','S2'):
        m=main[(sid,sale)];p=dec(m['profit_yuan']);m0=calculate(readcsv(RUN/f'M0-{sid}-{sale}'/'solution.csv'),sid,sale)[0];old=calculate(readcsv(RUN/f'M1R-{sid}-{sale}'/'solution.csv'),sid,sale)[0];solver=json.loads((DEEP/f'M1R3-{sid}-{sale}'/'solver.json').read_text(encoding='utf-8'))
        comparison.append({'scenario':sid,'sale_case':sale,'M0_profit_yuan':f'{m0:.6f}','M1R_profit_yuan':f'{old:.6f}','M1R3_profit_yuan':f'{p:.6f}','M1R3_minus_M0_yuan':f'{p-m0:.6f}','M1R3_minus_M1R_yuan':f'{p-old:.6f}','improvement_over_M0_percent':f'{(p/m0-1)*100:.6f}','activations':m['activations'],'stage1_status':solver['stage1']['status'],'stage1_mip_gap':solver['stage1']['mip_gap'],'selected_stage':solver['selected_stage']})

cross=[]
for sale in ('S1','S2'):
    for source in ('D0','D05','D10'):
        vals={target:calculate(solutions[(source,sale)],target,sale)[0] for target in ('D0','D05','D10')}
        for target,p in vals.items():cross.append({'sale_case':sale,'plan_source_scenario':source,'evaluation_scenario':target,'profit_yuan':f'{p:.6f}'})
for row in cross:
    same=[dec(x['profit_yuan']) for x in cross if x['sale_case']==row['sale_case'] and x['evaluation_scenario']==row['evaluation_scenario']]
    row['regret_vs_best_of_three_plans_yuan']=f'{max(same)-dec(row["profit_yuan"]):.6f}'

similar=[]
for sale in ('S1','S2'):
    for a,b in itertools.combinations(('D0','D05','D10'),2):
        aa={(r['land_id'],int(r['year']),r['season'],int(r['crop_id'])):dec(r['area_mu']) for r in solutions[(a,sale)]};bb={(r['land_id'],int(r['year']),r['season'],int(r['crop_id'])):dec(r['area_mu']) for r in solutions[(b,sale)]};keys=set(aa)|set(bb);inter=set(aa)&set(bb);union=set(aa)|set(bb);l1=sum((abs(aa.get(k,0)-bb.get(k,0)) for k in keys),Decimal(0));den=sum(aa.values(),Decimal(0))
        similar.append({'sale_case':sale,'scenario_a':a,'scenario_b':b,'area_l1_mu':f'{l1:.6f}','area_l1_share_of_plan_a_percent':f'{l1/den*100:.6f}','activation_jaccard':f'{Decimal(len(inter))/Decimal(len(union)):.6f}'})

# Rebuild a heterogeneous run index after the original DictWriter field mismatch.
index=[]
for d in sorted(p for p in DEEP.iterdir() if p.is_dir() and (p/'solver.json').exists()):
    s=json.loads((d/'solver.json').read_text(encoding='utf-8'));index.append({'run_id':d.name,'candidate':s.get('candidate'),'scenario':s.get('scenario'),'sale_case':s.get('sale_case'),'profit_yuan':s.get('selected_profit'),'activations':s.get('selected_activations'),'retention':s.get('retention'),'valid_solution_csv':(d/'solution.csv').exists()})
writecsv(DEEP/'solver_run_index.csv',index);writecsv(DEEP/'solution_metrics.csv',metrics);writecsv(DEEP/'main_comparison.csv',comparison);writecsv(DEEP/'pareto.csv',pareto);writecsv(DEEP/'bean_diagnostic.csv',bean);writecsv(DEEP/'cross_evaluation.csv',cross);writecsv(DEEP/'scenario_similarity.csv',similar)
validation={'protocol':'Q1-DEEPEN-v1','authorization':'U008','verifier_sha256':sha(Path(__file__)),'source_snapshot_valid':True,'checks':checks,'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),'violations':violations,'main_comparison':comparison,'human_verification':'pending','limitations':['D0/D05/D10 demand values are assumptions, not observations','Midpoint prices are candidate values','Aggregate bean rule does not prove within-plot spatial coverage','Time-limited MIP solutions are not globally optimal unless their recorded gap supports it']}
dump(DEEP/'validation.json',validation);dump(DEEP/'solver_batch_complete.json',{'finished_utc':datetime.now(timezone.utc).isoformat(),'solver_outputs':len(index),'main_runs':6,'pareto_runs':8,'strict_bean_runs':2,'index_write_error_recovered':True})
print(json.dumps({'checks':len(checks),'passed':validation['passed'],'failed':validation['failed'],'violations':len(violations),'main':comparison,'bean':bean},ensure_ascii=False,indent=2));assert validation['failed']==0
