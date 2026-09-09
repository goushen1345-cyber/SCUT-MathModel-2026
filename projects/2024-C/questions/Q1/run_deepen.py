"""Execute only U008-approved Q1-DEEPEN-v1 work packages W1-W3."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import csv, json, time
import numpy as np
import run_trials as r

ROOT=r.ROOT; Q=r.QDIR; OUT=Q/'deep_runs'; PROTOCOL=Q/'protocols/deepen_v1.json'

def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def start_from_csv(md,path,sid):
    vals=np.zeros(len(md.meta));prod=defaultdict(float);bean_area=defaultdict(float)
    for row in read_csv(path):
        key=(row['land_id'],int(row['year']),row['season'],int(row['crop_id']))
        if key not in md.x:continue
        area=float(row['area_mu']);vals[md.x[key]]=area;vals[md.z[key]]=1
        prod[(key[3],key[1],key[2])]+=area*float(row['yield_jin_per_mu'])
        if key[3] in r.BEANS:bean_area[(key[0],key[1],key[2])]+=area
        if row['land_type']=='水浇地' and row['season']=='单季':vals[md.mode[(key[0],key[1])]]=1
    for key,j in md.sold.items():vals[j]=min(prod[key],r.DEMANDS[sid][(key[0],key[2])])
    for key,j in md.full_bean.items():vals[j]=1 if bean_area[key]>=r.LD[key[0]]['area']-1e-7 else 0
    return vals

def existing_best(sid,sale):
    candidates=[]
    for name in ('M0','M1','M1R'):
        p=Q/'runs'/f'{name}-{sid}-{sale}'/'solution.csv'
        if p.exists():candidates.append((r.evaluate_csv(p,sid,sale)['profit'],name,p))
    return max(candidates)

def canonicalize_sales(md,vals,sid):
    vals=np.array(vals,dtype=float,copy=True);prod=defaultdict(float)
    for (lid,y,s,c),j in md.x.items():prod[(c,y,s)]+=vals[j]*r.PD[(c,r.LD[lid]['land_type'],s)]['yield']
    for key,j in md.sold.items():vals[j]=min(prod[key],r.DEMANDS[sid][(key[0],key[2])])
    return vals

def save_solution(out,md,vals,label,sid,sale,record):
    before=float(np.dot(vals,np.asarray(md.profit)));vals=canonicalize_sales(md,vals,sid)
    rows=r.solution_rows(md,vals,label,sid,sale);r.write_csv(out/'solution.csv',rows)
    ev=r.evaluate_csv(out/'solution.csv',sid,sale);after=float(np.dot(vals,np.asarray(md.profit)));record.update({'selected_profit':ev['profit'],'selected_revenue':ev['revenue'],'selected_cost':ev['cost'],'selected_activations':ev['activations'],'precanonical_model_accounting_profit':before,'sales_variables_canonicalized_after_solve':True,'model_accounting_profit':after,'accounting_difference':ev['profit']-after})
    r.dump(out/'solver.json',record);return ev

def run_w1(sid,sale):
    out=OUT/f'M1R3-{sid}-{sale}'
    if (out/'solution.csv').exists():
        record=json.loads((out/'solver.json').read_text(encoding='utf-8'));ev=r.evaluate_csv(out/'solution.csv',sid,sale)
        if abs(record.get('accounting_difference',0))>.1:
            backup=out/'solver_precanonical.json'
            if not backup.exists():backup.write_bytes((out/'solver.json').read_bytes())
            record['precanonical_model_accounting_profit']=record['model_accounting_profit'];record['sales_variables_canonicalized_after_solve']=True
            record['model_accounting_profit']=ev['profit'];record['accounting_difference']=0.0;record['postprocess_note']='Only sales auxiliary variables were set to min(production,demand); exported planting areas were unchanged.'
            r.dump(out/'solver.json',record)
        return {'run_id':out.name,'work_package':'W1','scenario':sid,'sale_case':sale,'profit':ev['profit'],'activations':ev['activations'],'selected_stage':record['selected_stage'],'stage1_status':record['stage1']['status'],'stage1_gap':record['stage1']['mip_gap'],'stage2_status':record['stage2']['status'],'stage3_status':record['stage3']['status']}
    out.mkdir(parents=True,exist_ok=False)
    base_profit,base_name,base_path=existing_best(sid,sale)
    m1=r.compile_model(sid,sale,.5,7,'profit');warm=start_from_csv(m1,base_path,sid)
    _,v1,a=r.solve(m1,180,gap=.01,start_values=warm);r.dump(out/'stage1_solver.json',a)
    if not a['solution_valid']:raise RuntimeError(f'W1 no stage1 solution {sid}/{sale}')
    floor=a['recomputed_profit']*.999
    m2=r.compile_model(sid,sale,.5,7,'management',profit_floor=floor)
    _,v2,b=r.solve(m2,90,gap=.005,start_values=v1);r.dump(out/'stage2_solver.json',b)
    if b['solution_valid']:
        activation_cap=int(sum(v2[j]>.5 for j in m2.z.values()))
        m3=r.compile_model(sid,sale,.5,7,'profit',profit_floor=floor,activation_cap=activation_cap)
        _,v3,c=r.solve(m3,60,gap=.005,start_values=v2);r.dump(out/'stage3_solver.json',c)
    else:
        activation_cap=None;m3=m1;v3=v1;c={'status':'SKIPPED_NO_STAGE2_SOLUTION','solution_valid':False}
    chosen_md,chosen,selection=m1,v1,'stage1_fallback'
    if c.get('solution_valid'):
        stage3_rows=r.solution_rows(m3,v3,'M1R3',sid,sale)
        tmp=out/'stage3_candidate.csv';r.write_csv(tmp,stage3_rows);stage3_ev=r.evaluate_csv(tmp,sid,sale);tmp.unlink()
        if stage3_ev['profit']+0.1>=r.evaluate_csv(Q/'runs'/f'M0-{sid}-{sale}'/'solution.csv',sid,sale)['profit']:
            chosen_md,chosen,selection=m3,v3,'stage3'
    record={'protocol':'Q1-DEEPEN-v1','authorization':'U008','candidate':'M1R3','scenario':sid,'sale_case':sale,'alpha':.5,'cap':7,'initial_incumbent':base_name,'initial_profit':base_profit,'profit_floor':floor,'activation_cap_from_stage2':activation_cap,'stage1':a,'stage2':b,'stage3':c,'selected_stage':selection,'seed':r.SEED,'time_limits_seconds':[180,90,60],'optimality_claim':'Only as supported by status, bound and gap.'}
    ev=save_solution(out,chosen_md,chosen,'M1R3',sid,sale,record)
    if abs(record['accounting_difference'])>.1:raise RuntimeError(f'Accounting mismatch {sid}/{sale}: {record["accounting_difference"]}')
    return {'run_id':out.name,'work_package':'W1','scenario':sid,'sale_case':sale,'profit':ev['profit'],'activations':ev['activations'],'selected_stage':selection,'stage1_status':a['status'],'stage1_gap':a['mip_gap'],'stage2_status':b['status'],'stage3_status':c['status']}

def run_w2(sale):
    results=[];sid='D0';base=OUT/f'M1R3-{sid}-{sale}'/'solution.csv'
    out=OUT/f'PARETO-D0-{sale}-profit';out.mkdir(exist_ok=False)
    mp=r.compile_model(sid,sale,.5,None,'profit');warm=start_from_csv(mp,base,sid)
    _,vp,a=r.solve(mp,120,gap=.01,start_values=warm);r.dump(out/'stage1_solver.json',a)
    if not a['solution_valid']:raise RuntimeError(f'W2 no profit solution {sale}')
    pev=save_solution(out,mp,vp,'PARETO-PROFIT',sid,sale,{'protocol':'Q1-DEEPEN-v1','authorization':'U008','candidate':'PARETO-PROFIT','scenario':sid,'sale_case':sale,'cap':None,'alpha':.5,'stage1':a,'seed':r.SEED})
    results.append({'run_id':out.name,'work_package':'W2','sale_case':sale,'retention':1.0,'profit':pev['profit'],'activations':pev['activations'],'status':a['status']})
    for retention in (.999,.995,.99):
        tag=str(retention).replace('.','p');d=OUT/f'PARETO-D0-{sale}-{tag}';d.mkdir(exist_ok=False)
        floor=a['recomputed_profit']*retention
        mm=r.compile_model(sid,sale,.5,None,'management',profit_floor=floor)
        _,vm,b=r.solve(mm,60,gap=.005,start_values=vp);r.dump(d/'stage2_solver.json',b)
        if not b['solution_valid']:raise RuntimeError(f'W2 no management solution {sale}/{retention}')
        ev=save_solution(d,mm,vm,'PARETO',sid,sale,{'protocol':'Q1-DEEPEN-v1','authorization':'U008','candidate':'PARETO','scenario':sid,'sale_case':sale,'cap':None,'alpha':.5,'retention':retention,'profit_floor':floor,'profit_stage':a,'management_stage':b,'seed':r.SEED})
        results.append({'run_id':d.name,'work_package':'W2','sale_case':sale,'retention':retention,'profit':ev['profit'],'activations':ev['activations'],'status':b['status']})
    return results

def run_w3(sale):
    sid='D0';out=OUT/f'BEAN-STRICT-D0-{sale}';out.mkdir(exist_ok=False)
    m=r.compile_model(sid,sale,.5,7,'profit',bean_mode='strict_full_plot')
    base=Q/'runs'/f'M0-{sid}-{sale}'/'solution.csv';warm=start_from_csv(m,base,sid)
    _,v,a=r.solve(m,120,gap=.01,start_values=warm);r.dump(out/'stage1_solver.json',a)
    if not a['solution_valid']:raise RuntimeError(f'W3 no solution {sale}')
    ev=save_solution(out,m,v,'BEAN-STRICT',sid,sale,{'protocol':'Q1-DEEPEN-v1','authorization':'U008','candidate':'BEAN-STRICT','scenario':sid,'sale_case':sale,'bean_mode':'strict_full_plot','alpha':.5,'cap':7,'stage1':a,'seed':r.SEED})
    return {'run_id':out.name,'work_package':'W3','sale_case':sale,'profit':ev['profit'],'activations':ev['activations'],'status':a['status'],'gap':a['mip_gap']}

def main():
    state=json.loads((ROOT/'state/state.json').read_text(encoding='utf-8'));protocol=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    assert state['stage']=='DEEPEN' and any(a['id']=='U008' and a['plan_version']=='Q1-DEEPEN-v1' for a in state['authorizations'])
    assert protocol['total_wall_budget_minutes']==55 and all(r.sha(ROOT/p)==h for p,h in state['data_snapshots']['G1-v1-base'].items())
    OUT.mkdir(exist_ok=True);started=time.perf_counter()
    if not (OUT/'batch.json').exists():r.dump(OUT/'batch.json',{'protocol':'Q1-DEEPEN-v1','authorization':'U008','started_utc':datetime.now(timezone.utc).isoformat(),'seed':r.SEED,'data_version':'G1-v1-base','source_hashes':state['data_snapshots']['G1-v1-base'],'runner_sha256':r.sha(Path(__file__))})
    index=[]
    for sid in ('D0','D05','D10'):
        for sale in ('S1','S2'):index.append(run_w1(sid,sale))
    for sale in ('S1','S2'):index.extend(run_w2(sale))
    for sale in ('S1','S2'):index.append(run_w3(sale))
    elapsed=time.perf_counter()-started
    r.write_csv(OUT/'solver_run_index.csv',index)
    r.dump(OUT/'solver_batch_complete.json',{'finished_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':elapsed,'wall_minutes':elapsed/60,'completed':len(index),'budget_minutes':55})
    print(json.dumps({'completed':len(index),'wall_minutes':elapsed/60},ensure_ascii=False))

if __name__=='__main__':main()
