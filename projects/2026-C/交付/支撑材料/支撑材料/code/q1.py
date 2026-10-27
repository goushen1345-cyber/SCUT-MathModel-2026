from pathlib import Path
import os,json,time,hashlib,csv,itertools
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import joblib
R=Path(__file__).resolve().parents[1]
P=R
O=R/'reproduced'
DATE=pd.Timestamp('2025-01-01')
N=365*144
N_DAYS=365
SLOTS=144
CAP=5000/6
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def daystr(d):return str((DATE+pd.Timedelta(days=int(d))).date())
class Budget:
 def __init__(self):self.calls=0;self.lp_calls=0;self.price_fits=0
 def check(self):pass
 def save(self):pass
class Logs:
 def event(self,*a,**kw):pass
budget=Budget();logs=Logs()
def arrays(inputs, config):
    dt=config['dt_hours']
    l=np.array([r['load_kw']*dt for r in inputs]); v=np.array([r['pv_kw']*dt for r in inputs])
    p=np.array([r['price'] for r in inputs])
    return l, v, p, np.maximum(l-v,0), np.maximum(v-l,0)

def terminal_bands(net, cfg):
    n=len(net); low=np.empty(n+1); high=np.empty(n+1)
    low[n]=high[n]=cfg['terminal_kwh']
    up=cfg['eta_charge']*cfg['external_charge_kw']*cfg['dt_hours']
    down=np.minimum(net,cfg['external_discharge_kw']*cfg['dt_hours'])/cfg['eta_discharge']
    for t in range(n-1,-1,-1):
        low[t]=max(cfg['min_kwh'],low[t+1]-up)
        high[t]=min(cfg['max_kwh'],high[t+1]+down[t])
    return low,high,up,down

def rule(inputs, cfg, low_q, high_q, target_fraction, reserve):
    l,v,p,net,excess=arrays(inputs,cfg); n=len(p)
    low_price=float(np.quantile(p,low_q)); high_price=float(np.quantile(p,high_q))
    cap_c=cfg['external_charge_kw']*cfg['dt_hours']; cap_d=cfg['external_discharge_kw']*cfg['dt_hours']
    eta_c=cfg['eta_charge']; eta_d=cfg['eta_discharge']; smin=cfg['min_kwh']; smax=cfg['max_kwh']
    target=smin+target_fraction*(smax-smin)
    lo,hi,up,down=terminal_bands(net,cfg)
    state=cfg['initial_kwh']; rows=[]
    for t in range(n):
        desired=0.; cap=target; reserve_amount=0.
        reason='idle'
        if excess[t]>1e-10:
            desired=min(eta_c*min(excess[t],cap_c),smax-state)
            reason='pv_charge'
        elif p[t]>=high_price:
            desired=-min(down[t],state-smin)
            reason='peak_discharge'
        elif p[t]<=low_price:
            future_prices=p[t+1:][net[t+1:]>1e-10]
            economical=len(future_prices)>0 and p[t]<eta_c*eta_d*float(future_prices.max())
            if reserve:
                future=np.flatnonzero(excess[t+1:]>1e-10)
                if len(future):
                    a=t+1+int(future[0]); b=a
                    while b<n and excess[b]>1e-10: b+=1
                    incoming=eta_c*float(np.minimum(excess[a:b],cap_c).sum())
                    release=float(down[t+1:a][p[t+1:a]>=high_price].sum())
                    reserve_amount=min(smax-smin,max(0.,incoming-release))
                    cap=min(target,max(smin,smax-reserve_amount))
            if economical:
                desired=min(up,max(0.,cap-state)); reason='low_price_charge'
        allowed_low=max(-down[t],lo[t+1]-state,smin-state)
        allowed_high=min(up,hi[t+1]-state,smax-state)
        assert allowed_low<=allowed_high+1e-7, (t,state,allowed_low,allowed_high)
        actual=float(np.clip(desired,allowed_low,allowed_high))
        c=max(actual,0.)/eta_c; discharge=max(-actual,0.)*eta_d
        cpv=min(c,excess[t]); cg=c-cpv
        before=state; state+=actual
        rows.append(dict(grid_charge=cg,pv_charge=cpv,discharge=discharge,state_start=before,state_end=state,
            action_reason=reason,desired_delta=desired,actual_delta=actual,
            terminal_projection=int(abs(actual-desired)>1e-7), reserve_kwh=reserve_amount,grid_charge_target=cap))
    return rows,dict(low_quantile=low_q,high_quantile=high_q,target_fraction=target_fraction,
        low_price=low_price,high_price=high_price,target_kwh=target)

def solve_lp(inputs,cfg):
    l,v,p,net,excess=arrays(inputs,cfg); n=len(p)
    # x = [grid_charge, pv_charge, load-side discharge, end storage]
    objective=np.r_[p,np.zeros(n),-p,np.zeros(n)]
    aeq=np.zeros((n,4*n)); beq=np.zeros(n)
    for t in range(n):
        aeq[t,t]=-cfg['eta_charge']; aeq[t,n+t]=-cfg['eta_charge']
        aeq[t,2*n+t]=1/cfg['eta_discharge']; aeq[t,3*n+t]=1
        if t: aeq[t,3*n+t-1]=-1
        else: beq[t]=cfg['initial_kwh']
    aub=np.zeros((n,4*n))
    for t in range(n): aub[t,t]=aub[t,n+t]=1
    cc=cfg['external_charge_kw']*cfg['dt_hours']; dc=cfg['external_discharge_kw']*cfg['dt_hours']
    lower=np.r_[np.zeros(3*n),np.full(n,cfg['min_kwh'])]
    upper=np.r_[np.full(n,cc),np.minimum(excess,cc),np.minimum(net,dc),np.full(n,cfg['max_kwh'])]
    lower[-1]=upper[-1]=cfg['terminal_kwh']
    before=time.perf_counter()
    result=linprog(objective,A_ub=aub,b_ub=np.full(n,cc),A_eq=aeq,b_eq=beq,
        bounds=list(zip(lower,upper)),method='highs',options=dict(time_limit=cfg['lp_time_limit_seconds'],
            primal_feasibility_tolerance=cfg['lp_feasibility_tolerance'],
            dual_feasibility_tolerance=cfg['lp_feasibility_tolerance']))
    elapsed=time.perf_counter()-before
    assert result.success, result.message
    x=result.x; base=float(p@net)
    dual=float(beq@result.eqlin.marginals+np.full(n,cc)@result.ineqlin.marginals+
        lower@result.lower.marginals+upper@result.upper.marginals+base)
    cert=dict(status=int(result.status),message=result.message,method='HiGHS LP',iterations=int(result.nit),
        time_seconds=elapsed,primal_cost=float(result.fun+base),dual_cost=dual,
        primal_dual_gap=float(result.fun+base-dual),objective=objective.tolist(),x=x.tolist(),
        equality_marginals=result.eqlin.marginals.tolist(),inequality_marginals=result.ineqlin.marginals.tolist(),
        lower_marginals=result.lower.marginals.tolist(),upper_marginals=result.upper.marginals.tolist())
    rows=[]
    for t in range(n):
        s0=cfg['initial_kwh'] if t==0 else x[3*n+t-1]
        rows.append(dict(grid_charge=float(x[t]),pv_charge=float(x[n+t]),discharge=float(x[2*n+t]),
            state_start=float(s0),state_end=float(x[3*n+t]),action_reason='whole_day_optimization',
            desired_delta=float(x[3*n+t]-s0),actual_delta=float(x[3*n+t]-s0),
            terminal_projection=0,reserve_kwh=0.,grid_charge_target=0.))
    return rows,cert

def schedule(inputs, cfg, actions):
    l,v,p,net,excess=arrays(inputs,cfg); records=[]
    for t,(r,a) in enumerate(zip(inputs,actions)):
        charge=a['grid_charge']+a['pv_charge']; q=net[t]-a['discharge']+a['grid_charge']
        rec=dict(r); rec.update(a)
        rec.update(load_kwh=float(l[t]),pv_kwh=float(v[t]),direct_pv_kwh=float(min(l[t],v[t])),
            grid_to_load_kwh=float(net[t]-a['discharge']),purchase_kwh=float(q),charge_kwh=float(charge),
            unused_pv_kwh=float(excess[t]-a['pv_charge']),
            loss_kwh=float((1-cfg['eta_charge'])*charge+(1/cfg['eta_discharge']-1)*a['discharge']),
            cost_yuan=float(p[t]*q))
        records.append(rec)
    return records

def metrics(rows):
    totals={key:float(sum(r[key] for r in rows)) for key in
        ['cost_yuan','purchase_kwh','charge_kwh','discharge','pv_charge','grid_charge','unused_pv_kwh','loss_kwh']}
    states=[rows[0]['state_start']]+[r['state_end'] for r in rows]
    totals.update(start_kwh=states[0],end_kwh=states[-1],min_kwh=min(states),max_kwh=max(states),
        max_charge_kw=max(r['charge_kwh']*6 for r in rows),max_discharge_kw=max(r['discharge']*6 for r in rows),
        simultaneous_slots=sum(r['charge_kwh']>1e-5 and r['discharge']>1e-5 for r in rows),
        terminal_projection_slots=sum(r['terminal_projection'] for r in rows))
    return totals
