"""Run only the U006-approved Q1-TRIAL-v1 batch."""
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timezone
from decimal import Decimal
import csv, hashlib, json, math, random, time
import highspy
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
QDIR=Path(__file__).resolve().parent
DATA=ROOT/'data/frozen/G1-v1-base'
RUNS=QDIR/'runs'
YEARS=list(range(2024,2031)); INF=highspy.kHighsInf; SEED=20240906

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load_csv(name):
    with (DATA/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def dump(path,obj):
    def native(x):
        if isinstance(x,np.integer):return int(x)
        if isinstance(x,np.floating):return float(x)
        raise TypeError(type(x).__name__)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=native),encoding='utf-8')
def write_csv(path,rows,fields=None):
    rows=list(rows); fields=fields or list(rows[0])
    with path.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def load_data():
    state=json.loads((ROOT/'state/state.json').read_text(encoding='utf-8'))
    assert state['stage'] in ('TRIAL','DEEPEN') and state['active_question']=='Q1'
    auth_id='U006' if state['stage']=='TRIAL' else 'U008'
    auth=next(a for a in state['authorizations'] if a['id']==auth_id)
    assert auth['plan_version'] in ('Q1-TRIAL-v1','Q1-DEEPEN-v1') and state['data_version']=='G1-v1-base'
    assert all(sha(ROOT/p)==h for p,h in state['data_snapshots']['G1-v1-base'].items())
    protocol=json.loads((QDIR/'protocols/demand_scenarios_v1.json').read_text(encoding='utf-8'))
    assert protocol['authorization_id']=='U005' and protocol['base_data_version']=='G1-v1-base'
    lands=load_csv('lands.csv'); crops=load_csv('crops.csv'); planting=load_csv('planting_2023.csv')
    params=load_csv('parameters_effective.csv'); prod=load_csv('production_2023.csv')
    ld={r['land_id']:{**r,'area':float(r['area_mu'])} for r in lands}
    cd={int(r['crop_id']):r for r in crops}
    pd={(int(r['crop_id']),r['land_type'],r['season']):{**r,'yield':float(r['yield_jin_per_mu']),'cost':float(r['cost_yuan_per_mu']),'price':float(r['price_midpoint_candidate_yuan_per_jin'])} for r in params}
    base={(int(r['crop_id']),r['season']):float(r['production_estimate_jin']) for r in prod}
    seasons=defaultdict(set)
    for c,t,s in pd: seasons[c].add(s)
    demands={}
    for sid,frac in [('D0',0),('D05',.05),('D10',.10)]:
        d={k:v for k,v in base.items()}
        for c,ss in seasons.items():
            obs=[s for s in ss if (c,s) in base]; miss=[s for s in ss if (c,s) not in base]
            if frac and len(obs)==1 and len(miss)==1:
                total=base[(c,obs[0])];d[(c,obs[0])]=total*(1-frac);d[(c,miss[0])]=total*frac
            else:
                for s in miss:d[(c,s)]=0.0
        demands[sid]=d
    price={}
    for (c,t,s),p in pd.items():price.setdefault((c,s),set()).add(p['price'])
    assert all(len(v)==1 for v in price.values());price={k:next(iter(v)) for k,v in price.items()}
    beans={c for c,r in cd.items() if r['is_legume']=='true'}
    hist_bean=defaultdict(float); last=defaultdict(set); byland=defaultdict(list)
    for r in planting:
        c=int(r['crop_id']);byland[r['land_id']].append(r)
        if c in beans:hist_bean[r['land_id']]+=float(r['area_mu'])
    rank={'单季':0,'第一季':1,'第二季':2}
    for l,rs in byland.items():
        mx=max(rank[r['season']] for r in rs)
        last[l]={int(r['crop_id']) for r in rs if rank[r['season']]==mx}
    return state,protocol,ld,cd,pd,demands,price,beans,hist_bean,last

STATE,PROTOCOL,LD,CD,PD,DEMANDS,PRICE,BEANS,HIST_BEAN,LAST=load_data()

def seasons_for_land(lt):
    if lt in ('平旱地','梯田','山坡地'):return ['单季']
    if lt=='水浇地':return ['单季','第一季','第二季']
    return ['第一季','第二季']

ELIG=defaultdict(list)
for (c,lt,s),p in PD.items():ELIG[(lt,s)].append(c)
for k in ELIG:ELIG[k].sort()

def scenario_rows(sid):
    return [{'scenario':sid,'crop_id':c,'crop_name':CD[c]['crop_name'],'season':s,'annual_normal_sales_limit_jin':f'{v:.10g}','status':'model_assumption_not_observed'} for (c,s),v in sorted(DEMANDS[sid].items())]

def incremental_value(c,lt,s,area,used,demand,sale):
    p=PD[(c,lt,s)]; q=area*p['yield']; full=max(0,min(q,demand-used)); excess=q-full
    revenue=PRICE[(c,s)]*(full+(0 if sale=='S1' else .5*excess))
    return revenue-area*p['cost'],q

def option_sets(lid):
    lt=LD[lid]['land_type']
    if lt in ('平旱地','梯田','山坡地'):
        return [[('单季',c)] for c in ELIG[(lt,'单季')]]
    if lt=='普通大棚':
        return [[('第一季',a),('第二季',b)] for a in ELIG[(lt,'第一季')] for b in ELIG[(lt,'第二季')]]
    if lt=='智慧大棚':
        return [[('第一季',a),('第二季',b)] for a in ELIG[(lt,'第一季')] for b in ELIG[(lt,'第二季')] if a!=b]
    if lt=='水浇地':
        out=[[('单季',c)] for c in ELIG[(lt,'单季')]]
        out += [[('第一季',a),('第二季',b)] for a in ELIG[(lt,'第一季')] for b in ELIG[(lt,'第二季')] if a!=b]
        return out
    raise ValueError(lt)

OPTIONS={l:option_sets(l) for l in LD}

def run_m0(sid,sale,outdir,cap=7):
    start=time.perf_counter(); demand=DEMANDS[sid]; used=defaultdict(float); plot_count=Counter(); bean_year=defaultdict(float)
    prev={l:set(LAST.get(l,set())) for l in LD}; rows=[]; infeasible=[]
    order=sorted(LD,key=lambda l:(-LD[l]['area'],l))
    for y in YEARS:
        for lid in order:
            area=LD[lid]['area']; lt=LD[lid]['land_type']; need=max(0,area-(HIST_BEAN[lid] if y==2025 else 0)-sum(bean_year[(lid,k)] for k in range(max(2024,y-2),y))) if y>=2025 else 0
            candidates=[]
            for opt in OPTIONS[lid]:
                if opt[0][1] in prev[lid] or any(opt[j][1]==opt[j-1][1] for j in range(1,len(opt))):continue
                if any(plot_count[(c,y,s)]>=cap for s,c in opt):continue
                barea=sum(area for s,c in opt if c in BEANS)
                if barea+1e-9<need:continue
                score=0; deltas=[]
                for s,c in opt:
                    val,q=incremental_value(c,lt,s,area,used[(c,y,s)],demand[(c,s)],sale);score+=val;deltas.append((s,c,q,val))
                candidates.append((score,tuple(-c for s,c in opt),opt,deltas,barea))
            if not candidates:
                infeasible.append({'land_id':lid,'year':y,'reason':'no_option_under_rotation_bean_and_cap'});continue
            score,_,opt,deltas,barea=max(candidates)
            for s,c,q,val in deltas:
                used[(c,y,s)]+=q;plot_count[(c,y,s)]+=1
                p=PD[(c,lt,s)]
                rows.append({'candidate':'M0','scenario':sid,'sale_case':sale,'year':y,'season':s,'land_id':lid,'land_type':lt,'crop_id':c,'crop_name':CD[c]['crop_name'],'area_mu':f'{area:.10g}','yield_jin_per_mu':f"{p['yield']:.10g}",'cost_yuan_per_mu':f"{p['cost']:.10g}",'price_yuan_per_jin':f"{PRICE[(c,s)]:.10g}"})
            bean_year[(lid,y)]=barea;prev[lid]={opt[-1][1]}
    write_csv(outdir/'solution.csv',rows)
    dump(outdir/'solver.json',{'candidate':'M0','method':'deterministic_profit_order_construct_and_repair','status':'FEASIBLE_CANDIDATE' if not infeasible else 'FAILED_CONSTRUCTION','infeasible':infeasible,'runtime_seconds':time.perf_counter()-start,'seed':SEED,'cap':cap,'area_fraction':1.0,'optimality_claim':'none'})
    return not infeasible

class ModelData:
    pass

def compile_model(sid,sale,alpha=.5,cap=7,stage='profit',profit_floor=None,relax=False,
                  bean_mode='aggregate',activation_cap=None):
    md=ModelData();md.meta=[];md.lb=[];md.ub=[];md.profit=[];md.obj=[];md.integer=[];md.rows=[]
    def var(meta,lb,ub,profit=0,integer=False,obj=None):
        j=len(md.meta);md.meta.append(meta);md.lb.append(lb);md.ub.append(ub);md.profit.append(profit);md.integer.append(integer and not relax);md.obj.append((-profit if stage=='profit' else (1.0 if meta[0]=='z' else 0.0)) if obj is None else obj);return j
    def row(coefs,lo=-INF,hi=INF,name=''):
        md.rows.append((dict(coefs),lo,hi,name))
    x={};z={};mode={}
    for lid,l in LD.items():
        area=l['area'];lt=l['land_type']
        for y in YEARS:
            if lt=='水浇地':mode[(lid,y)]=var(('mode_rice',lid,y),0,1,integer=True)
            for season in seasons_for_land(lt):
                for c in ELIG.get((lt,season),[]):
                    p=PD[(c,lt,season)]; baseprofit=-p['cost']
                    if sale=='S2':baseprofit+=.5*PRICE[(c,season)]*p['yield']
                    k=(lid,y,season,c);x[k]=var(('x',)+k,0,area,profit=baseprofit);z[k]=var(('z',)+k,0,1,integer=True)
                    row({x[k]:1,z[k]:-area},hi=0,name='link_upper')
                    row({x[k]:1,z[k]:-alpha*area},lo=0,name='link_lower')
    for lid,l in LD.items():
        area=l['area'];lt=l['land_type']
        for y in YEARS:
            if lt!='水浇地':
                for season in seasons_for_land(lt):row({x[(lid,y,season,c)]:1 for c in ELIG[(lt,season)]},lo=area,hi=area,name='capacity')
            else:
                r=mode[(lid,y)]
                row({**{x[(lid,y,'单季',c)]:1 for c in ELIG[(lt,'单季')]},r:-area},lo=0,hi=0,name='water_rice')
                row({**{x[(lid,y,'第一季',c)]:1 for c in ELIG[(lt,'第一季')]},r:area},lo=area,hi=area,name='water_first')
                row({**{x[(lid,y,'第二季',c)]:1 for c in ELIG[(lt,'第二季')]},r:area},lo=area,hi=area,name='water_second')
    groups=defaultdict(list)
    for k,j in z.items():groups[(k[3],k[1],k[2])].append(j)
    if cap is not None:
        for g,js in groups.items():row({j:1 for j in js},hi=cap,name='plot_cap')
    # Rotation, including the 2023 boundary.
    for lid,l in LD.items():
        lt=l['land_type']
        first='单季' if lt in ('平旱地','梯田','山坡地') else '第一季'
        if lt=='水浇地':
            for c in LAST.get(lid,set()):
                for s in ('单季','第一季'):
                    if (lid,2024,s,c) in z:row({z[(lid,2024,s,c)]:1},hi=0,name='history_rotation')
            for c in CD:
                for y in YEARS:
                    if (lid,y,'第一季',c) in z and (lid,y,'第二季',c) in z:row({z[(lid,y,'第一季',c)]:1,z[(lid,y,'第二季',c)]:1},hi=1,name='rotation')
                    if y>2024 and (lid,y-1,'第二季',c) in z and (lid,y,'第一季',c) in z:row({z[(lid,y-1,'第二季',c)]:1,z[(lid,y,'第一季',c)]:1},hi=1,name='rotation')
                    if y>2024 and (lid,y-1,'单季',c) in z and (lid,y,'单季',c) in z:row({z[(lid,y-1,'单季',c)]:1,z[(lid,y,'单季',c)]:1},hi=1,name='rotation')
        elif len(seasons_for_land(lt))==1:
            s=first
            for c in LAST.get(lid,set()):
                if (lid,2024,s,c) in z:row({z[(lid,2024,s,c)]:1},hi=0,name='history_rotation')
            for c in ELIG[(lt,s)]:
                for y in YEARS[1:]:row({z[(lid,y-1,s,c)]:1,z[(lid,y,s,c)]:1},hi=1,name='rotation')
        else:
            for c in LAST.get(lid,set()):
                if (lid,2024,'第一季',c) in z:row({z[(lid,2024,'第一季',c)]:1},hi=0,name='history_rotation')
            for c in CD:
                for y in YEARS:
                    if (lid,y,'第一季',c) in z and (lid,y,'第二季',c) in z:row({z[(lid,y,'第一季',c)]:1,z[(lid,y,'第二季',c)]:1},hi=1,name='rotation')
                    if y>2024 and (lid,y-1,'第二季',c) in z and (lid,y,'第一季',c) in z:row({z[(lid,y-1,'第二季',c)]:1,z[(lid,y,'第一季',c)]:1},hi=1,name='rotation')
    if bean_mode=='aggregate':
        # Rolling three-year bean-area proxy.
        for lid,l in LD.items():
            area=l['area']
            for end in range(2025,2031):
                co={j:1 for k,j in x.items() if k[0]==lid and k[1] in range(max(2024,end-2),end+1) and k[3] in BEANS}
                constant=HIST_BEAN[lid] if end==2025 else 0
                row(co,lo=area-constant,name='bean_window')
        full_bean={}
    elif bean_mode=='strict_full_plot':
        planting=load_csv('planting_2023.csv');hist_by_slot=defaultdict(float)
        for r in planting:
            if int(r['crop_id']) in BEANS:hist_by_slot[(r['land_id'],r['season'])]+=float(r['area_mu'])
        hist_full={lid:any(abs(a-LD[lid]['area'])<=1e-7 for (l,s),a in hist_by_slot.items() if l==lid) for lid in LD}
        full_bean={}
        for lid,l in LD.items():
            area=l['area'];lt=l['land_type']
            for y in YEARS:
                for s in seasons_for_land(lt):
                    bean_js=[x[(lid,y,s,c)] for c in ELIG.get((lt,s),[]) if c in BEANS]
                    if bean_js:
                        b=var(('full_bean',lid,y,s),0,1,integer=True);full_bean[(lid,y,s)]=b
                        row({**{j:1 for j in bean_js},b:-area},lo=0,name='full_bean_link')
            for end in range(2025,2031):
                co={j:1 for (l,y,s),j in full_bean.items() if l==lid and y in range(max(2024,end-2),end+1)}
                constant=1 if end==2025 and hist_full[lid] else 0
                row(co,lo=1-constant,name='strict_bean_window')
    else:
        raise ValueError(bean_mode)
    sold={}
    demand=DEMANDS[sid]
    prodgroups=defaultdict(dict)
    for (lid,y,s,c),j in x.items():prodgroups[(c,y,s)][j]=PD[(c,LD[lid]['land_type'],s)]['yield']
    for (c,y,s),co in prodgroups.items():
        soldprofit=PRICE[(c,s)] if sale=='S1' else .5*PRICE[(c,s)]
        q=var(('sold_full',c,y,s),0,demand[(c,s)],profit=soldprofit)
        sold[(c,y,s)]=q;row({q:1,**{j:-v for j,v in co.items()}},hi=0,name='sales_production')
    if profit_floor is not None:row({j:v for j,v in enumerate(md.profit) if abs(v)>0},lo=profit_floor,name='profit_floor')
    if activation_cap is not None:row({j:1 for j in z.values()},hi=activation_cap,name='activation_cap')
    md.x=x;md.z=z;md.mode=mode;md.sold=sold;md.full_bean=full_bean
    starts=[0];indices=[];values=[];rl=[];ru=[];names=[]
    for co,lo,hi,name in md.rows:
        for j,v in sorted(co.items()):
            if v:indices.append(j);values.append(v)
        starts.append(len(indices));rl.append(lo);ru.append(hi);names.append(name)
    lp=highspy.HighsLp();lp.num_col_=len(md.meta);lp.num_row_=len(md.rows)
    lp.col_cost_=np.asarray(md.obj,dtype=float);lp.col_lower_=np.asarray(md.lb,dtype=float);lp.col_upper_=np.asarray(md.ub,dtype=float)
    lp.row_lower_=np.asarray(rl,dtype=float);lp.row_upper_=np.asarray(ru,dtype=float)
    lp.a_matrix_.format_=highspy.MatrixFormat.kRowwise;lp.a_matrix_.start_=np.asarray(starts,dtype=np.int64);lp.a_matrix_.index_=np.asarray(indices,dtype=np.int32);lp.a_matrix_.value_=np.asarray(values,dtype=float)
    lp.integrality_=[highspy.HighsVarType.kInteger if v else highspy.HighsVarType.kContinuous for v in md.integer]
    md.lp=lp;md.row_names=names
    return md

def solve(md,time_limit,gap=.005,start_values=None):
    h=highspy.Highs();h.silent();h.setOptionValue('time_limit',float(time_limit));h.setOptionValue('random_seed',SEED);h.setOptionValue('mip_rel_gap',gap)
    assert h.passModel(md.lp)==highspy.HighsStatus.kOk
    if start_values is not None:
        warm=highspy.HighsSolution();warm.col_value=list(map(float,start_values));warm.value_valid=True
        assert h.setSolution(warm)==highspy.HighsStatus.kOk
    start=time.perf_counter();h.run();elapsed=time.perf_counter()-start;status=h.modelStatusToString(h.getModelStatus());sol=h.getSolution();info=h.getInfo()
    vals=np.asarray(sol.col_value,dtype=float) if sol.value_valid else np.zeros(len(md.meta))
    profit=float(np.dot(vals,np.asarray(md.profit))) if sol.value_valid else None
    return h,vals,{'status':status,'solution_valid':bool(sol.value_valid),'runtime_seconds':elapsed,'objective_value':float(h.getObjectiveValue()) if sol.value_valid else None,'recomputed_profit':profit,'mip_gap':float(getattr(info,'mip_gap',math.nan)),'mip_dual_bound':float(getattr(info,'mip_dual_bound',math.nan)),'mip_node_count':int(getattr(info,'mip_node_count',-1)),'simplex_iterations':int(getattr(info,'simplex_iteration_count',-1))}

def solution_rows(md,vals,candidate,sid,sale):
    rows=[]
    for k,j in md.x.items():
        if vals[j]>1e-7:
            lid,y,s,c=k;lt=LD[lid]['land_type'];p=PD[(c,lt,s)]
            rows.append({'candidate':candidate,'scenario':sid,'sale_case':sale,'year':y,'season':s,'land_id':lid,'land_type':lt,'crop_id':c,'crop_name':CD[c]['crop_name'],'area_mu':f'{vals[j]:.10g}','yield_jin_per_mu':f"{p['yield']:.10g}",'cost_yuan_per_mu':f"{p['cost']:.10g}",'price_yuan_per_jin':f"{PRICE[(c,s)]:.10g}"})
    return rows

def run_m1(sid,sale,outdir,alpha=.5,cap=7,time_limit=120,second=True,label='M1'):
    m1=compile_model(sid,sale,alpha,cap,'profit');h,v,a=solve(m1,time_limit)
    dump(outdir/'stage1_solver.json',a)
    if not a['solution_valid']:
        dump(outdir/'solver.json',{'candidate':label,'status':'NO_SOLUTION','stage1':a});return False
    chosen=v;stage2=None
    if second:
        floor=a['recomputed_profit']-max(abs(a['recomputed_profit'])*.001,1e-6)
        m2=compile_model(sid,sale,alpha,cap,'management',floor);h2,v2,stage2=solve(m2,time_limit)
        dump(outdir/'stage2_solver.json',stage2)
        if stage2['solution_valid']:chosen=v2;md=m2
        else:md=m1
    else:md=m1
    rows=solution_rows(md,chosen,label,sid,sale);write_csv(outdir/'solution.csv',rows)
    dump(outdir/'solver.json',{'candidate':label,'scenario':sid,'sale_case':sale,'alpha':alpha,'cap':cap,'stage1':a,'stage2':stage2,'selected_profit':float(np.dot(chosen,np.asarray(md.profit))),'selected_activations':int(sum(chosen[j]>.5 for j in md.z.values())),'model_size':{'columns':len(md.meta),'rows':len(md.rows)},'seed':SEED,'optimality_claim':'Only as supported by status, bound and gap.'})
    return True

def run_lp(sid,sale,outdir):
    md=compile_model(sid,sale,.5,7,'profit',relax=True);h,v,a=solve(md,30);dump(outdir/'lp_upper_bound.json',a);return a

def evaluate_csv(path,sid,sale):
    with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    prod=defaultdict(float);cost=0
    for r in rows:
        area=float(r['area_mu']);c=int(r['crop_id']);y=int(r['year']);season=r['season']
        prod[(c,y,season)]+=area*float(r['yield_jin_per_mu']);cost+=area*float(r['cost_yuan_per_mu'])
    revenue=0
    for (c,y,season),q in prod.items():
        full=min(q,DEMANDS[sid][(c,season)]);excess=q-full
        revenue+=PRICE[(c,season)]*(full+(0 if sale=='S1' else .5*excess))
    return {'profit':revenue-cost,'revenue':revenue,'cost':cost,'activations':len(rows)}

def repair_m1_summary(outdir,sid,sale,label='M1',alpha=.5,cap=7):
    a=json.loads((outdir/'stage1_solver.json').read_text(encoding='utf-8'))
    stage2=json.loads((outdir/'stage2_solver.json').read_text(encoding='utf-8')) if (outdir/'stage2_solver.json').exists() else None
    ev=evaluate_csv(outdir/'solution.csv',sid,sale)
    dump(outdir/'solver.json',{'candidate':label,'scenario':sid,'sale_case':sale,'alpha':alpha,'cap':cap,'stage1':a,'stage2':stage2,'selected_profit':ev['profit'],'selected_activations':ev['activations'],'model_size':{'columns':15337,'rows':'see rebuilt model; exact stage2 may include one extra row'},'seed':SEED,'recovered_after_json_serialization_error':True,'optimality_claim':'Only as supported by status, bound and gap.'})

def run_all():
    resumed=RUNS.exists();RUNS.mkdir(parents=True,exist_ok=True);start=time.perf_counter();summary=[]
    if not (RUNS/'batch.json').exists():dump(RUNS/'batch.json',{'protocol':'Q1-TRIAL-v1','authorization':'U006','started_utc':datetime.now(timezone.utc).isoformat(),'seed':SEED,'data_version':'G1-v1-base','source_hashes':STATE['data_snapshots']['G1-v1-base'],'code_sha256':sha(Path(__file__)),'highs_version':highspy.Highs().version()})
    for sid in ('D0','D05','D10'):
        sdir=RUNS/f'demand-{sid}';sdir.mkdir(exist_ok=True)
        if not (sdir/'demand.csv').exists():write_csv(sdir/'demand.csv',scenario_rows(sid))
        for sale in ('S1','S2'):
            for candidate in ('M0','M1'):
                d=RUNS/f'{candidate}-{sid}-{sale}';d.mkdir(exist_ok=True)
                if (d/'solution.csv').exists():
                    if candidate=='M1' and not (d/'solver.json').exists():repair_m1_summary(d,sid,sale)
                    ok=True
                else:ok=run_m0(sid,sale,d) if candidate=='M0' else run_m1(sid,sale,d)
                summary.append({'run_id':d.name,'type':'main','candidate':candidate,'scenario':sid,'sale_case':sale,'completed':ok})
            lpdir=RUNS/f'LP-{sid}-{sale}';lpdir.mkdir(exist_ok=True)
            a=json.loads((lpdir/'lp_upper_bound.json').read_text(encoding='utf-8')) if (lpdir/'lp_upper_bound.json').exists() else run_lp(sid,sale,lpdir)
            summary.append({'run_id':lpdir.name,'type':'lp','candidate':'LP','scenario':sid,'sale_case':sale,'completed':a['solution_valid']})
            if time.perf_counter()-start>40*60:break
    for sale in ('S1','S2'):
        for tag,alpha,cap in (('alpha25',.25,7),('cap10',.5,10)):
            d=RUNS/f'DIAG-{tag}-D0-{sale}';d.mkdir(exist_ok=True)
            if (d/'solution.csv').exists():
                if not (d/'solver.json').exists():repair_m1_summary(d,'D0',sale,f'M1-{tag}',alpha,cap)
                ok=True
            else:ok=run_m1('D0',sale,d,alpha,cap,90,False,label=f'M1-{tag}')
            summary.append({'run_id':d.name,'type':'management_diagnostic','candidate':f'M1-{tag}','scenario':'D0','sale_case':sale,'completed':ok})
    if (RUNS/'run_index.csv').exists():(RUNS/'run_index.csv').unlink()
    write_csv(RUNS/'run_index.csv',summary)
    dump(RUNS/'batch_complete.json',{'finished_utc':datetime.now(timezone.utc).isoformat(),'resume_wall_seconds':time.perf_counter()-start,'resumed_after_serialization_error':resumed,'runs':len(summary),'completed':sum(r['completed'] for r in summary)})
    print(json.dumps({'runs':len(summary),'completed':sum(r['completed'] for r in summary),'wall_seconds':time.perf_counter()-start},ensure_ascii=False))

if __name__=='__main__':run_all()
