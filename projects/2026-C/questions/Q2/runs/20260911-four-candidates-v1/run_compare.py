"""Run only the user-approved four-candidate Q2 batch; retain all trial paths."""
import os
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[name]='1'
from pathlib import Path
import argparse,csv,gzip,json,time,sys,traceback,platform
import numpy as np
import pandas as pd
import scipy,sklearn
from threadpoolctl import threadpool_limits
from core import R,P,sha,dump,daystr,Data,Forecasts,Planner,execute,metrics

class Logs:
    def __init__(self,out):self.out=out;self.handles={};self.writers={}
    def event(self,name,row):
        if name not in self.handles:self.handles[name]=(self.out/(name+'.jsonl')).open('w',encoding='utf-8')
        self.handles[name].write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');self.handles[name].flush()
    def csv(self,name,row):
        if name not in self.writers:
            h=gzip.open(self.out/(name+'.csv.gz'),'wt',encoding='utf-8-sig',newline='')
            w=csv.DictWriter(h,fieldnames=list(row));w.writeheader();self.writers[name]=(h,w)
        self.writers[name][1].writerow(row)
    def close(self):
        for h in self.handles.values():h.close()
        for h,w in self.writers.values():h.close()

class Risk:
    def __init__(self,data,base,logs):self.data=data;self.base=base;self.logs=logs;self.cache={}
    def margin(self,d,q,phase,variant):
        days=list(range(max(1,d-28),d))
        for j in days:
            if j not in self.cache:
                l,v,_=self.data.history(j,*self.base);realL,realV=self.data.truth(j)
                self.cache[j]=((realL-realV)-(l[:144]-v[:144]))/6
                for k,e in enumerate(self.cache[j]):self.logs.csv('historical_risk_errors',dict(date=daystr(j),day=j,slot=k,error_kwh=float(e)))
        pool=np.array([self.cache[j] for j in days]);m=np.zeros(144)
        for group in range(6):
            if len(days)<7:raw=0.;count=0;mode='no allowance, fewer than7days'
            else:
                values=pool[:,group*24:(group+1)*24].ravel() if len(days)>=14 else pool.ravel()
                raw=float(np.quantile(values,q));count=len(values);mode='4hour group' if len(days)>=14 else 'allhours fallback'
            value=max(0.,raw);m[group*24:(group+1)*24]=value
            self.logs.event('risk_margins',dict(phase=phase,variant=variant,decision_date=daystr(d),group=group,
               quantile=q,raw_quantile_kwh=raw,allowance_kwh=value,historical_days=len(days),sample_count=count,
               first_history_date=daystr(days[0]) if days else None,last_history_date=daystr(days[-1]) if days else None,
               sample_weight='uniform1',mode=mode))
        return np.tile(m,2)

def summarize(daily):
    rows=[]
    for (phase,variant),g in daily.groupby(['phase','variant'],sort=False):
        r={'phase':phase,'variant':variant,'days':len(g),'first_date':g.decision_date.iloc[0],
           'last_date':g.decision_date.iloc[-1]}
        for name in ['total_cost','ordinary_cost','emergency_cost','order_kwh','emergency_kwh','unused_order_kwh',
                     'unused_pv_kwh','grid_charge_kwh','pv_charge_kwh','discharge_kwh','received_kwh']:
            r[name]=float(g[name].sum())
        r.update(storage_start_kwh=float(g.storage_start_kwh.iloc[0]),storage_end_kwh=float(g.storage_end_kwh.iloc[-1]),
            load_mae_kw=float(g.load_abs_error_sum.sum()/(144*len(g))),pv_mae_kw=float(g.pv_abs_error_sum.sum()/(144*len(g))),
            pv_positive_mae_kw=float(g.pv_positive_abs_error_sum.sum()/g.pv_positive_slots.sum()),
            net_mae_kw=float(g.net_abs_error_sum.sum()/(144*len(g))),
            emergency_days=int((g.emergency_kwh>1e-6).sum()),emergency_slots=int(g.emergency_slots.sum()),
            longest_within_day_emergency_minutes=int(g.longest_emergency_minutes.max()),
            daily_cost_max=float(g.total_cost.max()),daily_cost_p95=float(g.total_cost.quantile(.95)))
        rows.append(r)
    return pd.DataFrame(rows)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='outputs');a=parser.parse_args()
    out=(R/a.output).resolve();assert out.is_relative_to(P) and not out.exists();out.mkdir(parents=True)
    log=Logs(out);start=time.perf_counter();daily=[];planner=None;forecasts=None
    def guard():
        if time.perf_counter()-start>1800:raise RuntimeError('30minute batch budget reached')
    try:
        data=Data(out)
        def event(name,row):log.event(name,row)
        forecasts=Forecasts(data,out,event,guard);planner=Planner(data.price,event,guard)
        dump(out/'environment.json',dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,
                 sklearn=sklearn.__version__,platform=platform.platform(),threads=1,random_seed=2026,
                 protocol_sha256=sha(R/'protocol.json'),code_sha256={n:sha(R/n) for n in ['core.py','run_compare.py']}))

        def one_day(d,phase,variant,kind,param,state,phase_start,risk=None):
            guard();meta={'phase':phase,'variant':variant,'decision_date':daystr(d),'day':d}
            if d==0:
                l=np.tile(data.ref['load'],2);v=np.tile(data.ref['pv'],2);q=data.q1;planned=None;mar=np.zeros(288)
            else:
                l,v=forecasts.get('T1' if kind=='T4' else kind,risk.base if kind=='T4' else param,d,phase_start)
                mar=risk.margin(d,param,phase,variant) if kind=='T4' else np.zeros(288)
                planned=planner.solve(l,v,state,mar,meta);q=planned[0][:144]
                for j in range(288):
                    log.csv('forecast_plans',dict(**meta,target_date=daystr(d+j//144),slot=j%144,horizon_slot=j,
                        load_forecast_kw=float(l[j]),pv_forecast_kw=float(v[j]),risk_allowance_kwh=float(mar[j]),
                        price=float(planner.p[j]),planned_order_kwh=float(planned[0][j]),
                        planned_grid_charge_kwh=float(planned[1][j]),planned_pv_charge_kwh=float(planned[2][j]),
                        planned_discharge_kwh=float(planned[3][j]),planned_storage_end_kwh=float(planned[4][j]),
                        planned_initial_storage_kwh=float(state),committed=int(j<144)))
            trueL,trueV=data.truth(d,initialization=(d==0));rows,end=execute(trueL,trueV,q,state,data.price)
            for row in rows:log.csv('execution',dict(**meta,initialization_reference=int(d==0 and row['slot']==0),**row))
            rec=dict(**meta,**metrics(rows,l,v));daily.append(rec)
            log.event('daily_metrics',rec)
            return end

        state=6000.;warmstarts={}
        for d in range(31):
            warmstarts[d]=state;state=one_day(d,'initialization','common','T1',(1,3),state,1)
        feb_start=state;jan8_start=warmstarts[7]
        dump(out/'initialization.json',dict(jan1_initial=6000.,jan8_initial=jan8_start,feb1_initial=feb_start,
             first_interval_reference_flagged=True,jan1_order_source='retained Q1 C04',common_policy_after_day1='T1-w1-p3',
             no_daily_reset=True))
        print(json.dumps(dict(event='initialization_complete',feb1_storage=feb_start,lp_calls=planner.calls),ensure_ascii=False),flush=True)

        configs={'T1':[(1,3),(1,7),(4,3),(4,7)],'T2':[1,10,100],'T3':[3,5,7]};selected={};variant_to_param={}
        def label(kind,param):
            if kind=='T1':return f'T1-w{param[0]}-p{param[1]}'
            return f'{kind}-'+str(param)
        for kind in ['T1','T2','T3']:
            for param in configs[kind]:
                variant=label(kind,param);variant_to_param[variant]=param;state=jan8_start
                for d in range(7,31):state=one_day(d,'tuning',variant,kind,param,state,7)
                cost=sum(x['total_cost'] for x in daily if x['phase']=='tuning' and x['variant']==variant)
                print(json.dumps(dict(event='tuning_setting_complete',variant=variant,cost=cost,end_storage=state,
                       lp_calls=planner.calls,elapsed_seconds=time.perf_counter()-start),ensure_ascii=False),flush=True)
            table=summarize(pd.DataFrame(daily));g=table[(table.phase=='tuning')&table.variant.str.startswith(kind+'-')]
            winner=g.sort_values('total_cost',kind='stable').iloc[0].variant;selected[kind]=variant_to_param[winner]
        risk=Risk(data,selected['T1'],log)
        for param in [.7,.8,.9]:
            variant=f'T4-q{int(param*100)}';variant_to_param[variant]=param;state=jan8_start
            for d in range(7,31):state=one_day(d,'tuning',variant,'T4',param,state,7,risk)
            print(json.dumps(dict(event='tuning_setting_complete',variant=variant,
                 cost=sum(x['total_cost'] for x in daily if x['phase']=='tuning' and x['variant']==variant),
                 lp_calls=planner.calls),ensure_ascii=False),flush=True)
        table=summarize(pd.DataFrame(daily));g=table[(table.phase=='tuning')&table.variant.str.startswith('T4-')]
        winner=g.sort_values('total_cost',kind='stable').iloc[0].variant;selected['T4']=variant_to_param[winner]
        dump(out/'january_selection.json',dict(selected=selected,criterion='January actual ordinary+emergency bill',
             selected_after='2025-01-31 24:00',common_initial_storage=jan8_start,
             disclosure='January hyperparameter replays are hypothetical trajectories; annual EDA already observed'))
        print(json.dumps(dict(event='january_selection_complete',selected=selected,lp_calls=planner.calls),ensure_ascii=False),flush=True)
        for kind in ['T1','T2','T3','T4']:
            state=feb_start
            for d in range(31,181):
                state=one_day(d,'comparison',kind,kind,selected[kind],state,31,risk if kind=='T4' else None)
                if (d-30)%30==0:
                    print(json.dumps(dict(event='comparison_progress',strategy=kind,through=daystr(d),lp_calls=planner.calls,
                         elapsed_seconds=time.perf_counter()-start),ensure_ascii=False),flush=True)
        frame=pd.DataFrame(daily);frame.to_csv(out/'daily_metrics.csv',index=False,encoding='utf-8-sig')
        table=summarize(frame);table['inventory_adjusted_reference_cost']=table.total_cost-planner.value*(table.storage_end_kwh-table.storage_start_kwh)
        table.to_csv(out/'period_metrics.csv',index=False,encoding='utf-8-sig')
        comparison=table[table.phase=='comparison'].sort_values('total_cost').copy()
        comparison.to_csv(out/'comparison.csv',index=False,encoding='utf-8-sig')
        for rel,h in data.protected.items():assert sha(P/rel)==h
        summary=dict(status='completed',selected_parameters=selected,lp_calls=planner.calls,fits=forecasts.fitcount,
             elapsed_seconds=time.perf_counter()-start,comparison=comparison.to_dict('records'),
             source_hashes_unchanged=True,selection_period='Feb-Jun,150days',annual_validation=False,
             actual_bill_includes_no_inventory_income=True,entropy_weighting_used=False,
             source_time_mapping='retained start-labelled intervals',independent_verification='pending')
        dump(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
    except Exception as ex:
        dump(out/'failure.json',dict(error=repr(ex),traceback=traceback.format_exc(),
             elapsed_seconds=time.perf_counter()-start,lp_calls=planner.calls if planner else 0,
             fits=forecasts.fitcount if forecasts else 0))
        if daily:pd.DataFrame(daily).to_csv(out/'partial_daily_metrics.csv',index=False,encoding='utf-8-sig')
        raise
    finally:log.close()
    dump(out/'output_hashes.json',{str(f.relative_to(out)):sha(f) for f in out.rglob('*') if f.is_file() and f.name!='output_hashes.json'})

if __name__=='__main__':
    with threadpool_limits(limits=1):main()
