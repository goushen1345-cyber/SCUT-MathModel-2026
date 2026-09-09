"""Fair rerun of the same U013 candidates after the 1% tolerance made all plans identical."""
from datetime import datetime, timezone
import json, time
import run_trials as r

def main():
    if any((r.RUN/f'{name}-R1').exists() for name in ('M0','M1','M2','M3')):
        raise RuntimeError('R1 output already exists; refusing overwrite')
    started=time.perf_counter();index=[]
    p0,a=r.run_candidate('M0-R1','midpoint',[r.midpoint()],270,r.RUN/'M0/solution.csv',.001);index.append({'candidate':'M0','run_id':'M0-R1','status':a['status'],'runtime_seconds':a['runtime_seconds'],'gap':a['mip_gap']})
    p1,a=r.run_candidate('M1-R1','mean',r.training,540,p0,.001);index.append({'candidate':'M1','run_id':'M1-R1','status':a['status'],'runtime_seconds':a['runtime_seconds'],'gap':a['mip_gap']})
    p2,a=r.run_candidate('M2-R1','cvar',r.training,810,p1,.001);index.append({'candidate':'M2','run_id':'M2-R1','status':a['status'],'runtime_seconds':a['runtime_seconds'],'gap':a['mip_gap']})
    p3,a=r.run_candidate('M3-R1','robust',r.stress,540,p2,.001);index.append({'candidate':'M3','run_id':'M3-R1','status':a['status'],'runtime_seconds':a['runtime_seconds'],'gap':a['mip_gap']})
    r.writecsv(r.RUN/'solver_index_r1.csv',index);elapsed=time.perf_counter()-started
    r.dump(r.RUN/'solver_batch_r1_complete.json',{'protocol':'Q2-TRIAL-v1','authorization':'U013','reason':'R0 all identical because 1% tolerance accepted the common warm start','mip_relative_gap_target':.001,'finished_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':elapsed,'wall_minutes':elapsed/60,'runs':index,'original_runs_preserved':True})
    print(json.dumps({'wall_minutes':elapsed/60,'runs':index},ensure_ascii=False))
if __name__=='__main__':main()
