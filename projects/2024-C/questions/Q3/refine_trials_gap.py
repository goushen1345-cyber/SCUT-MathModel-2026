"""Fair-comparison repair: retain R0 and rerun the same approved candidates at 0.05% gap."""
from datetime import datetime, timezone
import json, time
import run_trials as r

def main():
    started=time.perf_counter();index=[]
    b0=r.RUN/'B0'/'solution.csv'
    p0,rec=r.run_candidate('M0-CORR-R1','mean',r.training_r0,480,b0,gap=.0005)
    index.append({'candidate':'M0-CORR','run_id':'M0-CORR-R1','status':rec['status'],'runtime_seconds':rec['runtime_seconds'],'gap':rec['mip_gap']})
    p1,rec=r.run_candidate('M1-NET-R1','mean',r.training_rsc,720,p0,gap=.0005)
    index.append({'candidate':'M1-NET','run_id':'M1-NET-R1','status':rec['status'],'runtime_seconds':rec['runtime_seconds'],'gap':rec['mip_gap']})
    p2,rec=r.run_candidate('M2-RELROB-R1','relationship_robust',r.training_all,900,p1,gap=.0005)
    index.append({'candidate':'M2-RELROB','run_id':'M2-RELROB-R1','status':rec['status'],'runtime_seconds':rec['runtime_seconds'],'gap':rec['mip_gap']})
    elapsed=time.perf_counter()-started
    r.writecsv(r.RUN/'solver_index_r1.csv',index)
    r.dump(r.RUN/'solver_batch_r1_complete.json',{
        'protocol':'Q3-TRIAL-v1','authorization':'U018','repair':'same models and scenarios; mip gap tightened from 0.5% to 0.05%',
        'finished_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':elapsed,'wall_minutes':elapsed/60,
        'candidate_solves':3,'solve_budget_minutes':35,'r0_preserved':True,
    })
    print(json.dumps({'wall_minutes':elapsed/60,'index':index},ensure_ascii=False))

if __name__=='__main__': main()
