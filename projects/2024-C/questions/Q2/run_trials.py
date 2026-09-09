"""Run only U013-approved Q2-TRIAL-v1 candidate solves."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import csv, hashlib, json, math, shutil, time
import highspy
import numpy as np

ROOT=Path(__file__).resolve().parents[2]; Q=Path(__file__).resolve().parent; DATA=ROOT/'data/frozen/G1-v1-base'; RUN=Q/'runs'
YEARS=list(range(2024,2031)); INF=highspy.kHighsInf; SEED=20240907
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def readcsv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def writecsv(p,rows):
    rows=list(rows)
    with p.open('x',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def dump(p,obj):
    def native(x):
        if isinstance(x,np.integer):return int(x)
        if isinstance(x,np.floating):return float(x)
        raise TypeError(type(x).__name__)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=native),encoding='utf-8')

state=json.loads((ROOT/'state/state.json').read_text(encoding='utf-8')); assert state['stage']=='TRIAL' and state['active_question']=='Q2'
assert any(a['id']=='U013' and a['plan_version']=='Q2-TRIAL-v1' for a in state['authorizations'])
assert all(sha(ROOT/p)==h for p,h in state['data_snapshots']['G1-v1-base'].items())
assert all(sha(ROOT/p)==h for p,h in state['questions']['Q1']['snapshots']['Q1-D-v2-candidate'].items())

lands={r['land_id']:{**r,'area':float(r['area_mu'])} for r in readcsv(DATA/'lands.csv')}
crops={int(r['crop_id']):r for r in readcsv(DATA/'crops.csv')}
params={(int(r['crop_id']),r['land_type'],r['season']):{**r,'yield':float(r['yield_jin_per_mu']),'cost':float(r['cost_yuan_per_mu']),'price':float(r['price_midpoint_candidate_yuan_per_jin'])} for r in readcsv(DATA/'parameters_effective.csv')}
planting=readcsv(DATA/'planting_2023.csv'); production=readcsv(DATA/'production_2023.csv')
base0={(int(r['crop_id']),r['season']):float(r['production_estimate_jin']) for r in production}; cropseasons=defaultdict(set)
for c,lt,s in params:cropseasons[c].add(s)
base_d05=dict(base0)
for c,seasons in cropseasons.items():
    obs=[s for s in seasons if (c,s) in base0]; missing=[s for s in seasons if (c,s) not in base0]
    if len(obs)==len(missing)==1:
        total=base0[(c,obs[0])];base_d05[(c,obs[0])]=.95*total;base_d05[(c,missing[0])]=.05*total
    else:
        for s in missing:base_d05[(c,s)]=0.0
price={}
for (c,lt,s),p in params.items():price.setdefault((c,s),set()).add(p['price'])
assert all(len(v)==1 for v in price.values());price={k:next(iter(v)) for k,v in price.items()}
beans={c for c,r in crops.items() if r['is_legume']=='true'};histbean=defaultdict(float);last=defaultdict(set);byland=defaultdict(list)
for row in planting:
    c=int(row['crop_id']);byland[row['land_id']].append(row)
    if c in beans:histbean[row['land_id']]+=float(row['area_mu'])
rank={'单季':0,'第一季':1,'第二季':2}
for lid,rows in byland.items():
    m=max(rank[r['season']] for r in rows);last[lid]={int(r['crop_id']) for r in rows if rank[r['season']]==m}
def seasons_for_land(lt):
    if lt in ('平旱地','梯田','山坡地'):return ['单季']
    if lt=='水浇地':return ['单季','第一季','第二季']
    return ['第一季','第二季']
elig=defaultdict(list)
for c,lt,s in params:elig[(lt,s)].append(c)
for k in elig:elig[k].sort()

def load_driver(path):
    rows=readcsv(path);by=defaultdict(dict)
    for x in rows:by[x['scenario_id']][(int(x['crop_id']),int(x['year']))]={k:float(x[k]) for k in ('demand_multiplier','yield_multiplier','cost_multiplier','price_multiplier')}
    return [{'id':sid,'drivers':values} for sid,values in sorted(by.items())]
training=load_driver(RUN/'scenarios/training_drivers.csv');stress=load_driver(RUN/'scenarios/stress_drivers.csv')
def midpoint():
    d={};wf=1.0
    for y in YEARS:
        wf*=1.075;step=y-2023
        for c,row in crops.items():
            if '粮食' in row['crop_type']:pm=1.0
            elif '蔬菜' in row['crop_type']:pm=1.05**step
            elif row['crop_name']=='羊肚菌':pm=.95**step
            else:pm=.97**step
            d[(c,y)]={'demand_multiplier':wf if c in (6,7) else 1.0,'yield_multiplier':1.0,'cost_multiplier':1.05**step,'price_multiplier':pm}
    return {'id':'midpoint','drivers':d}

class MD:pass
def compile_model(scenarios,kind,sale='S2'):
    md=MD();md.meta=[];md.lb=[];md.ub=[];md.obj=[];md.integer=[];rows=[]
    def var(meta,lb,ub,integer=False):
        j=len(md.meta);md.meta.append(meta);md.lb.append(lb);md.ub.append(ub);md.obj.append(0.0);md.integer.append(integer);return j
    def row(co,lo=-INF,hi=INF,name=''):rows.append((dict(co),lo,hi,name))
    x={};z={};mode={}
    for lid,l in lands.items():
        area=l['area'];lt=l['land_type']
        for y in YEARS:
            if lt=='水浇地':mode[(lid,y)]=var(('mode',lid,y),0,1,True)
            for s in seasons_for_land(lt):
                for c in elig.get((lt,s),[]):
                    k=(lid,y,s,c);x[k]=var(('x',)+k,0,area);z[k]=var(('z',)+k,0,1,True)
                    row({x[k]:1,z[k]:-area},hi=0,name='link_upper');row({x[k]:1,z[k]:-.5*area},lo=0,name='link_lower')
    for lid,l in lands.items():
        area=l['area'];lt=l['land_type']
        for y in YEARS:
            if lt!='水浇地':
                for s in seasons_for_land(lt):row({x[(lid,y,s,c)]:1 for c in elig[(lt,s)]},lo=area,hi=area,name='capacity')
            else:
                m=mode[(lid,y)];row({**{x[(lid,y,'单季',c)]:1 for c in elig[(lt,'单季')]},m:-area},lo=0,hi=0,name='water_rice')
                row({**{x[(lid,y,'第一季',c)]:1 for c in elig[(lt,'第一季')]},m:area},lo=area,hi=area,name='water_first')
                row({**{x[(lid,y,'第二季',c)]:1 for c in elig[(lt,'第二季')]},m:area},lo=area,hi=area,name='water_second')
    groups=defaultdict(list)
    for k,j in z.items():groups[(k[3],k[1],k[2])].append(j)
    for js in groups.values():row({j:1 for j in js},hi=7,name='plot_cap')
    for lid,l in lands.items():
        lt=l['land_type']
        if lt=='水浇地':
            for c in last.get(lid,set()):
                for s in ('单季','第一季'):
                    if (lid,2024,s,c) in z:row({z[(lid,2024,s,c)]:1},hi=0,name='history_rotation')
            for c in crops:
                for y in YEARS:
                    if (lid,y,'第一季',c) in z and (lid,y,'第二季',c) in z:row({z[(lid,y,'第一季',c)]:1,z[(lid,y,'第二季',c)]:1},hi=1,name='rotation')
                    if y>2024 and (lid,y-1,'第二季',c) in z and (lid,y,'第一季',c) in z:row({z[(lid,y-1,'第二季',c)]:1,z[(lid,y,'第一季',c)]:1},hi=1,name='rotation')
                    if y>2024 and (lid,y-1,'单季',c) in z and (lid,y,'单季',c) in z:row({z[(lid,y-1,'单季',c)]:1,z[(lid,y,'单季',c)]:1},hi=1,name='rotation')
        elif len(seasons_for_land(lt))==1:
            s='单季'
            for c in last.get(lid,set()):
                if (lid,2024,s,c) in z:row({z[(lid,2024,s,c)]:1},hi=0,name='history_rotation')
            for c in elig[(lt,s)]:
                for y in YEARS[1:]:row({z[(lid,y-1,s,c)]:1,z[(lid,y,s,c)]:1},hi=1,name='rotation')
        else:
            for c in last.get(lid,set()):
                if (lid,2024,'第一季',c) in z:row({z[(lid,2024,'第一季',c)]:1},hi=0,name='history_rotation')
            for c in crops:
                for y in YEARS:
                    if (lid,y,'第一季',c) in z and (lid,y,'第二季',c) in z:row({z[(lid,y,'第一季',c)]:1,z[(lid,y,'第二季',c)]:1},hi=1,name='rotation')
                    if y>2024 and (lid,y-1,'第二季',c) in z and (lid,y,'第一季',c) in z:row({z[(lid,y-1,'第二季',c)]:1,z[(lid,y,'第一季',c)]:1},hi=1,name='rotation')
    for lid,l in lands.items():
        area=l['area']
        for end in range(2025,2031):
            co={j:1 for (ll,y,s,c),j in x.items() if ll==lid and y in range(max(2024,end-2),end+1) and c in beans}
            row(co,lo=area-(histbean[lid] if end==2025 else 0),name='bean_window')
    prodgroups=defaultdict(dict)
    for (lid,y,s,c),j in x.items():prodgroups[(c,y,s)][j]=params[(c,lands[lid]['land_type'],s)]['yield']
    sold={};profit_coefs=[]
    for si,sc in enumerate(scenarios):
        co=defaultdict(float)
        for (lid,y,s,c),j in x.items():
            drv=sc['drivers'][(c,y)];p=params[(c,lands[lid]['land_type'],s)];cost=p['cost']*drv['cost_multiplier']
            co[j]-=cost
            if sale=='S2':co[j]+=.5*price[(c,s)]*drv['price_multiplier']*p['yield']*drv['yield_multiplier']
        for (c,y,s),baseprod in prodgroups.items():
            drv=sc['drivers'][(c,y)];q=var(('sold',si,c,y,s),0,base_d05[(c,s)]*drv['demand_multiplier']);sold[(si,c,y,s)]=q
            yco={j:v*drv['yield_multiplier'] for j,v in baseprod.items()};row({q:1,**{j:-v for j,v in yco.items()}},hi=0,name='sales_production')
            co[q]+=(1.0 if sale=='S1' else .5)*price[(c,s)]*drv['price_multiplier']
        profit_coefs.append(dict(co))
    n=len(scenarios)
    if kind in ('midpoint','mean'):
        for co in profit_coefs:
            for j,v in co.items():md.obj[j]-=v/n
    elif kind=='cvar':
        for co in profit_coefs:
            for j,v in co.items():md.obj[j]-=.5*v/n
        eta=var(('eta',),-INF,INF);md.obj[eta]=-.5;u=[];alpha=.10
        for si,co in enumerate(profit_coefs):
            uj=var(('shortfall',si),0,INF);u.append(uj);md.obj[uj]=.5/(alpha*n);row({**co,eta:-1,uj:1},lo=0,name='cvar_shortfall')
        md.eta=eta;md.u=u
    elif kind=='robust':
        theta=var(('theta',),-INF,INF);md.obj[theta]=-1
        for co in profit_coefs:row({**co,theta:-1},lo=0,name='robust_floor')
        md.theta=theta
    else:raise ValueError(kind)
    starts=[0];indices=[];values=[];lo=[];hi=[]
    for co,a,b,name in rows:
        for j,v in sorted(co.items()):
            if v:indices.append(j);values.append(v)
        starts.append(len(indices));lo.append(a);hi.append(b)
    lp=highspy.HighsLp();lp.num_col_=len(md.meta);lp.num_row_=len(rows);lp.col_cost_=np.asarray(md.obj);lp.col_lower_=np.asarray(md.lb);lp.col_upper_=np.asarray(md.ub)
    lp.row_lower_=np.asarray(lo);lp.row_upper_=np.asarray(hi);lp.a_matrix_.format_=highspy.MatrixFormat.kRowwise;lp.a_matrix_.start_=np.asarray(starts,dtype=np.int64);lp.a_matrix_.index_=np.asarray(indices,dtype=np.int32);lp.a_matrix_.value_=np.asarray(values)
    lp.integrality_=[highspy.HighsVarType.kInteger if v else highspy.HighsVarType.kContinuous for v in md.integer]
    md.lp=lp;md.x=x;md.z=z;md.mode=mode;md.sold=sold;md.scenarios=scenarios;md.profit_coefs=profit_coefs;return md

def start_from_csv(md,path):
    vals=np.zeros(len(md.meta));prod=defaultdict(float)
    for row in readcsv(path):
        key=(row['land_id'],int(row['year']),row['season'],int(row['crop_id']))
        if key not in md.x:continue
        area=float(row['area_mu']);vals[md.x[key]]=area;vals[md.z[key]]=1
        if lands[key[0]]['land_type']=='水浇地' and key[2]=='单季':vals[md.mode[(key[0],key[1])]]=1
    for si,sc in enumerate(md.scenarios):
        for (lid,y,s,c),j in md.x.items():prod[(si,c,y,s)]+=vals[j]*params[(c,lands[lid]['land_type'],s)]['yield']*sc['drivers'][(c,y)]['yield_multiplier']
        for (ssi,c,y,s),j in md.sold.items():
            if ssi==si:vals[j]=min(prod[(si,c,y,s)],base_d05[(c,s)]*sc['drivers'][(c,y)]['demand_multiplier'])
    profits=[sum(vals[j]*v for j,v in co.items()) for co in md.profit_coefs]
    if hasattr(md,'eta'):
        eta=float(np.quantile(profits,.10));vals[md.eta]=eta
        for si,j in enumerate(md.u):vals[j]=max(0,eta-profits[si])
    if hasattr(md,'theta'):vals[md.theta]=min(profits)
    return vals

def solve(md,seconds,start,gap=.01):
    h=highspy.Highs();h.silent();h.setOptionValue('time_limit',float(seconds));h.setOptionValue('random_seed',SEED);h.setOptionValue('mip_rel_gap',float(gap));assert h.passModel(md.lp)==highspy.HighsStatus.kOk
    warm=highspy.HighsSolution();warm.col_value=list(map(float,start));warm.value_valid=True;assert h.setSolution(warm)==highspy.HighsStatus.kOk
    t=time.perf_counter();h.run();elapsed=time.perf_counter()-t;sol=h.getSolution();info=h.getInfo();vals=np.asarray(sol.col_value) if sol.value_valid else np.zeros(len(md.meta))
    return vals,{'status':h.modelStatusToString(h.getModelStatus()),'solution_valid':bool(sol.value_valid),'runtime_seconds':elapsed,'objective_value':float(h.getObjectiveValue()) if sol.value_valid else None,'mip_gap':float(getattr(info,'mip_gap',math.nan)),'mip_dual_bound':float(getattr(info,'mip_dual_bound',math.nan)),'mip_node_count':int(getattr(info,'mip_node_count',-1)),'simplex_iterations':int(getattr(info,'simplex_iteration_count',-1)),'model_columns':len(md.meta),'model_rows':md.lp.num_row_}

def save_plan(md,vals,out,candidate,solver):
    rows=[]
    for (lid,y,s,c),j in md.x.items():
        if vals[j]>1e-7:rows.append({'candidate':candidate,'year':y,'season':s,'land_id':lid,'land_type':lands[lid]['land_type'],'crop_id':c,'crop_name':crops[c]['crop_name'],'area_mu':f'{vals[j]:.10g}'})
    writecsv(out/'solution.csv',rows);profits=[sum(vals[j]*v for j,v in co.items()) for co in md.profit_coefs]
    solver.update({'candidate':candidate,'protocol':'Q2-TRIAL-v1','authorization':'U013','training_scenario_count':len(profits),'training_mean_profit':float(np.mean(profits)),'training_p10_profit':float(np.quantile(profits,.10)),'training_worst10_mean':float(np.mean(sorted(profits)[:max(1,math.ceil(.1*len(profits)))])),'selected_activations':len(rows),'optimality_claim':'Only as supported by recorded status, bound and gap.'});dump(out/'solver.json',solver)

def run_candidate(name,kind,scenarios,seconds,warm_path,gap=.01):
    out=RUN/name;out.mkdir(exist_ok=False);md=compile_model(scenarios,kind);start=start_from_csv(md,warm_path);vals,record=solve(md,seconds,start,gap)
    if not record['solution_valid']:raise RuntimeError(f'{name} has no valid solution')
    save_plan(md,vals,out,name,record);return out/'solution.csv',record

def main():
    batch_start=time.perf_counter();source=ROOT/'questions/Q1/deep_runs/M1R3-D0-S2/solution.csv';b0=RUN/'B0';b0.mkdir(exist_ok=False);shutil.copyfile(source,b0/'solution.csv');dump(b0/'solver.json',{'candidate':'B0','method':'frozen Q1 S2 plan; evaluation only','source':str(source.relative_to(ROOT)),'source_sha256':sha(source),'runtime_seconds':0,'optimality_claim':'none'})
    index=[{'candidate':'B0','status':'EVALUATION_ONLY','runtime_seconds':0,'gap':''}]
    path,rec=run_candidate('M0','midpoint',[midpoint()],300,b0/'solution.csv');index.append({'candidate':'M0','status':rec['status'],'runtime_seconds':rec['runtime_seconds'],'gap':rec['mip_gap']})
    path1,rec=run_candidate('M1','mean',training,600,path);index.append({'candidate':'M1','status':rec['status'],'runtime_seconds':rec['runtime_seconds'],'gap':rec['mip_gap']})
    path2,rec=run_candidate('M2','cvar',training,900,path1);index.append({'candidate':'M2','status':rec['status'],'runtime_seconds':rec['runtime_seconds'],'gap':rec['mip_gap']})
    path3,rec=run_candidate('M3','robust',stress,600,path2);index.append({'candidate':'M3','status':rec['status'],'runtime_seconds':rec['runtime_seconds'],'gap':rec['mip_gap']})
    writecsv(RUN/'solver_index.csv',index);elapsed=time.perf_counter()-batch_start;dump(RUN/'solver_batch_complete.json',{'protocol':'Q2-TRIAL-v1','authorization':'U013','finished_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':elapsed,'wall_minutes':elapsed/60,'candidate_solves':4,'solve_budget_minutes':40})
    print(json.dumps({'wall_minutes':elapsed/60,'index':index},ensure_ascii=False))
if __name__=='__main__':main()
