"""Fair-comparison repair: warm-start M1 from the feasible M0 solution."""
from pathlib import Path
from collections import defaultdict
import csv,json,numpy as np
import run_trials as r

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def start_from_csv(md,path,sid):
    v=np.zeros(len(md.meta));prod=defaultdict(float)
    rows=read(path)
    for row in rows:
        key=(row['land_id'],int(row['year']),row['season'],int(row['crop_id']));a=float(row['area_mu'])
        v[md.x[key]]=a;v[md.z[key]]=1;prod[(key[3],key[1],key[2])]+=a*float(row['yield_jin_per_mu'])
        if row['land_type']=='水浇地' and row['season']=='单季':v[md.mode[(key[0],key[1])]]=1
    for k,j in md.sold.items():v[j]=min(prod[k],r.DEMANDS[sid][(k[0],k[2])])
    return v

def main():
    index=[]
    for sid in ('D0','D05','D10'):
        for sale in ('S1','S2'):
            out=r.RUNS/f'M1R-{sid}-{sale}';assert not out.exists();out.mkdir()
            m0=r.RUNS/f'M0-{sid}-{sale}/solution.csv'
            m1=r.compile_model(sid,sale,.5,7,'profit');warm=start_from_csv(m1,m0,sid)
            h,v,a=r.solve(m1,45,start_values=warm);r.dump(out/'stage1_solver.json',a)
            assert a['solution_valid'];floor=a['recomputed_profit']-max(abs(a['recomputed_profit'])*.001,1e-6)
            m2=r.compile_model(sid,sale,.5,7,'management',floor);warm2=np.zeros(len(m2.meta));warm2[:len(v)]=v
            h2,v2,b=r.solve(m2,45,start_values=warm2);r.dump(out/'stage2_solver.json',b)
            chosen=v2 if b['solution_valid'] else v;md=m2 if b['solution_valid'] else m1
            rows=r.solution_rows(md,chosen,'M1R',sid,sale);r.write_csv(out/'solution.csv',rows)
            ev=r.evaluate_csv(out/'solution.csv',sid,sale)
            r.dump(out/'solver.json',{'candidate':'M1R','repair_of':f'M1-{sid}-{sale}','reason':'M1 feasible region contains M0; inject M0 as incumbent for fair comparison','scenario':sid,'sale_case':sale,'alpha':.5,'cap':7,'stage1':a,'stage2':b,'selected_model_profit':float(np.dot(chosen,np.asarray(md.profit))),'selected_profit':ev['profit'],'selected_activations':ev['activations'],'model_size':{'columns':len(md.meta),'rows':len(md.rows)},'seed':r.SEED,'time_limit_each_stage_seconds':45,'optimality_claim':'Only as supported by status, bound and gap.'})
            index.append({'run_id':out.name,'scenario':sid,'sale_case':sale,'stage1_status':a['status'],'stage1_gap':a['mip_gap'],'stage2_status':b['status'],'export_profit':ev['profit'],'activations':ev['activations']})
    r.write_csv(r.RUNS/'warmstart_repair_index.csv',index)
    print(json.dumps(index,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
