"""Execute only the U020-approved Q3-DEEPEN-v1 work packages."""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import csv, json, math, statistics, time

import highspy
import numpy as np
import model_core_deepen as m
import scenario_core_deepen as sg

ROOT=m.ROOT; Q=m.Q; OUT=Q/'deep_runs'; SCEN=OUT/'scenarios'; START=time.perf_counter()

def dump(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def writecsv(path,rows):
    rows=list(rows)
    with path.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def readcsv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def elapsed():return time.perf_counter()-START
def budget_guard(limit=1500):
    if elapsed()>=limit:raise TimeoutError('Q3-DEEPEN-v1 total 25-minute boundary reached')

def plan_rows(path):return readcsv(path)
def plan_dict(rows):return {(r['land_id'],int(r['year']),r['season'],int(r['crop_id'])):float(r['area_mu']) for r in rows}

def profit_components(rows,drv,base='D05',sale='S2'):
    bases={'D05':m.base_d05,'D0':m.base0}
    if base=='D10':
        d=dict(m.base0)
        for c,seasons in m.cropseasons.items():
            obs=[s for s in seasons if (c,s) in m.base0];missing=[s for s in seasons if (c,s) not in m.base0]
            if len(obs)==len(missing)==1:
                total=m.base0[(c,obs[0])];d[(c,obs[0])]=.9*total;d[(c,missing[0])]=.1*total
            else:
                for s in missing:d[(c,s)]=0.0
        bases['D10']=d
    production=defaultdict(float);costs=defaultdict(float)
    for r in rows:
        lid=r['land_id'];y=int(r['year']);s=r['season'];c=int(r['crop_id']);a=float(r['area_mu']);p=m.params[(c,m.lands[lid]['land_type'],s)];d=drv[(c,y)]
        production[(c,y,s)]+=a*p['yield']*d['yield_multiplier'];costs[(c,y,s)]+=a*p['cost']*d['cost_multiplier']
    out={}
    for key,qty in production.items():
        c,y,s=key;d=drv[(c,y)];cap=bases[base][(c,s)]*d['demand_multiplier'];full=min(qty,cap);extra=qty-full;price=m.price[(c,s)]*d['price_multiplier']
        revenue=price*(full+(0 if sale=='S1' else .5*extra));out[key]={'profit':revenue-costs[key],'production':qty,'cap':cap,'full':full,'extra':extra}
    return out
def profit(rows,drv,base='D05',sale='S2'):return sum(v['profit'] for v in profit_components(rows,drv,base,sale).values())
def metrics(vals):
    xs=sorted(vals);tail=xs[:math.ceil(.1*len(xs))]
    return {'mean':statistics.fmean(vals),'worst10_mean':statistics.fmean(tail),'p10':xs[math.ceil(.1*len(xs))-1],'min':xs[0],'max':xs[-1]}

def W1(b0):
    comparison=m.load_driver(m.RUN/'scenarios/comparison_drivers.csv');by=defaultdict(dict)
    for sc in comparison:by[sc['id'].rsplit('-',1)[0]][sc['id'].rsplit('-',1)[1]]=sc['drivers']
    agg=defaultdict(lambda:defaultdict(list));binding=defaultdict(list)
    for worlds in by.values():
        comps={w:profit_components(b0,d) for w,d in worlds.items()}
        for key,v in comps['R0'].items():
            c,y,s=key;binding[(c,y,s)].append(v['production']>=v['cap']-1e-7)
            for world in ('RS','RSC'):agg[(c,y,s)][world].append(comps[world][key]['profit']-v['profit'])
    rows=[]
    for c,y,s in sorted(agg):
        rows.append({'crop_id':c,'crop_name':m.crops[c]['crop_name'],'year':y,'season':s,
                     'mean_RS_minus_R0_yuan':f"{statistics.fmean(agg[(c,y,s)]['RS']):.6f}",
                     'mean_RSC_minus_R0_yuan':f"{statistics.fmean(agg[(c,y,s)]['RSC']):.6f}",
                     'r0_sales_cap_binding_rate':f"{statistics.fmean(binding[(c,y,s)]):.6f}"})
    writecsv(OUT/'mechanism_by_crop_year.csv',rows)
    dump(OUT/'W1.json',{'status':'complete','existing_comparison_only':True,'rows':len(rows),'runtime_seconds':elapsed()})

def solve_neighbour(name,k,seconds,warm_path):
    budget_guard();md=m.compile_model(m.training_rsc,'mean');start=m.start_from_csv(md,warm_path);ones={j for j in md.z.values() if start[j]>.5}
    h=highspy.Highs();h.silent();h.setOptionValue('time_limit',float(seconds));h.setOptionValue('random_seed',20250908);h.setOptionValue('mip_rel_gap',.0005)
    assert h.passModel(md.lp)==highspy.HighsStatus.kOk
    indices=np.asarray(sorted(md.z.values()),dtype=np.int32);values=np.asarray([-1.0 if j in ones else 1.0 for j in indices])
    assert h.addRow(-highspy.kHighsInf,float(k-len(ones)),len(indices),indices,values)==highspy.HighsStatus.kOk
    warm=highspy.HighsSolution();warm.col_value=list(map(float,start));warm.value_valid=True;assert h.setSolution(warm)==highspy.HighsStatus.kOk
    t=time.perf_counter();h.run();runtime=time.perf_counter()-t;sol=h.getSolution();info=h.getInfo()
    if not sol.value_valid:raise RuntimeError(name+' has no feasible solution')
    vals=np.asarray(sol.col_value);out=OUT/name;out.mkdir()
    rows=[]
    for (lid,y,s,c),j in md.x.items():
        if vals[j]>1e-7:rows.append({'candidate':name,'year':y,'season':s,'land_id':lid,'land_type':m.lands[lid]['land_type'],'crop_id':c,'crop_name':m.crops[c]['crop_name'],'area_mu':f'{vals[j]:.10g}'})
    writecsv(out/'solution.csv',rows)
    rec={'candidate':name,'protocol':'Q3-DEEPEN-v1','authorization':'U020','neighbourhood_k':k,'time_limit_seconds':seconds,'runtime_seconds':runtime,
         'status':h.modelStatusToString(h.getModelStatus()),'mip_gap':float(getattr(info,'mip_gap',math.nan)),'mip_dual_bound':float(getattr(info,'mip_dual_bound',math.nan)),
         'objective_value':float(h.getObjectiveValue()),'solution_valid':True,'selected_activations':len(rows),'training_mean_profit':float(np.mean([sum(vals[j]*v for j,v in co.items()) for co in md.profit_coefs]))}
    dump(out/'solver.json',rec);return out/'solution.csv',rec

def scaled(path,strength):
    raw=readcsv(path);by=defaultdict(dict)
    for r in raw:
        rel=min(1.10,max(.90,1+strength*(float(r['relationship_multiplier'])-1)))
        by[r['scenario_id']][(int(r['crop_id']),int(r['year']))]={'demand_multiplier':float(r['demand_multiplier_base'])*rel,'yield_multiplier':float(r['yield_multiplier']),'cost_multiplier':float(r['cost_multiplier']),'price_multiplier':float(r['price_multiplier'])}
    return dict(sorted(by.items()))

def compare(plans,drivers):
    rows=[];detail={}
    for name,plan in plans.items():
        vals=[profit(plan,d) for d in drivers.values()];detail[name]=vals;mm=metrics(vals)
        worlds={w:metrics([profit(plan,d) for sid,d in drivers.items() if sid.endswith('-'+w)]) for w in ('R0','RS','RSC')}
        rows.append({'candidate':name,**{k:f'{v:.6f}' for k,v in mm.items()},**{f'{w}_mean':f"{worlds[w]['mean']:.6f}" for w in worlds},'activations':len(plan)})
    return rows,detail

def main():
    if OUT.exists():raise RuntimeError('deep_runs exists; refusing overwrite')
    OUT.mkdir();SCEN.mkdir();b0_path=m.ROOT/'questions/Q2/runs/M0-R1/solution.csv';b0=plan_rows(b0_path)
    W1(b0);budget_guard()
    runs=[];warm=b0_path
    for name,k,seconds in [('N0',0,120),('N10',10,240),('N30',30,360)]:
        path,rec=solve_neighbour(name,k,seconds,warm);runs.append(rec);warm=path
    budget_guard()
    plans={'B0':b0,**{x['candidate']:plan_rows(OUT/x['candidate']/'solution.csv') for x in runs}}
    comparison=scaled(m.RUN/'scenarios/comparison_drivers.csv',1.0);summary,detail=compare(plans,comparison);writecsv(OUT/'preholdout_summary.csv',summary)
    base=next(r for r in summary if r['candidate']=='B0');eligible=[]
    for r in summary:
        if r['candidate']=='B0':continue
        d=[x-y for x,y in zip(detail[r['candidate']],detail['B0'])]
        passes=(float(r['mean'])>=float(base['mean'])*1.001 and float(r['worst10_mean'])>=float(base['worst10_mean'])*.999 and
                float(r['RSC_mean'])>float(base['RSC_mean']) and sum(float(r[w+'_mean'])>=float(base[w+'_mean']) for w in ('R0','RS','RSC'))>=2 and int(r['activations'])<=int(base['activations'])+10)
        if passes:eligible.append((int(r['candidate'][1:]),r['candidate']))
    challenger=min(eligible)[1] if eligible else None
    dump(OUT/'preholdout_selection.json',{'challenger':challenger,'eligible':eligible,'rule':'Q3-DEEPEN-v1 preregistered rule','holdout_seen':False})
    sens=[]
    for strength in (.5,1.0,2.0):
        drivers=scaled(m.RUN/'scenarios/comparison_drivers.csv',strength)
        for basekind in ('D0','D05','D10'):
            for sale in ('S1','S2'):
                for name,plan in plans.items():
                    mm=metrics([profit(plan,d,basekind,sale) for d in drivers.values()]);sens.append({'strength':strength,'demand_base':basekind,'sale_rule':sale,'candidate':name,'mean':f"{mm['mean']:.6f}",'worst10_mean':f"{mm['worst10_mean']:.6f}"})
    writecsv(OUT/'sensitivity_summary.csv',sens);budget_guard()
    holdout_base=sg.base_rows('holdout',500,20250308);holdout_rows=sg.expand_worlds(holdout_base);writecsv(SCEN/'holdout_drivers.csv',holdout_rows)
    dump(SCEN/'validation.json',{'seed':20250308,'underlying':500,'world_scenarios':1500,'rows':len(holdout_rows),'generated_after_challenger_fixed':True,'challenger':challenger,'passed':len(holdout_rows)==500*3*41*7})
    holdout=scaled(SCEN/'holdout_drivers.csv',1.0);fixed={'B0':b0};
    if challenger:fixed[challenger]=plans[challenger]
    hsummary,hdetail=compare(fixed,holdout);writecsv(OUT/'holdout_summary.csv',hsummary)
    final={'challenger':challenger,'selected':'B0','replace_pass':False,'reason':'no pre-holdout challenger met the gate'}
    if challenger:
        diffs=[]
        by=defaultdict(list)
        for sid,(a,b) in zip(holdout.keys(),zip(hdetail[challenger],hdetail['B0'])):by[sid.rsplit('-',1)[0]].append(a-b)
        diffs=[statistics.fmean(v) for v in by.values()];mean=statistics.fmean(diffs);lo=mean-1.96*statistics.stdev(diffs)/math.sqrt(len(diffs));hr={r['candidate']:r for r in hsummary}
        passed=(float(hr[challenger]['mean'])>=float(hr['B0']['mean'])*1.001 and lo>0 and float(hr[challenger]['worst10_mean'])>=float(hr['B0']['worst10_mean'])*.999)
        final={'challenger':challenger,'selected':challenger if passed else 'B0','replace_pass':passed,'paired_mean_difference':mean,'paired_95_lower':lo}
    dump(OUT/'final_selection.json',final);budget_guard()
    dump(OUT/'completion.json',{'protocol':'Q3-DEEPEN-v1','authorization':'U020','finished_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds_before_independent_verification':elapsed(),'runs':runs,'challenger':challenger,'final_selection':final,'m2_rerun':False,'holdout_opened_once':True})
    print(json.dumps({'wall_minutes':elapsed()/60,'challenger':challenger,'final':final},ensure_ascii=False))

if __name__=='__main__':main()
