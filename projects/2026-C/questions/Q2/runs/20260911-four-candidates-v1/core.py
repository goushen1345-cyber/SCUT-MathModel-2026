"""Causal forecasts, common continuous LP and interval-feedback execution for Q2."""
from pathlib import Path
import hashlib,json,time
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor
import joblib

R=Path(__file__).resolve().parent
P=R.parents[3]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def daystr(d):return str((pd.Timestamp('2025-01-01')+pd.Timedelta(days=int(d))).date())

class Data:
    def __init__(self,out):
        self.out=out
        manifest=json.loads((P/'data/prepared-v1/manifest.json').read_text(encoding='utf-8'))
        self.protected={}
        for n in ['actual_power.csv','day_reference.csv']:
            p=P/'data/prepared-v1'/n
            assert sha(p)==manifest['outputs'][n]['sha256']
            self.protected[str(p.relative_to(P))]=sha(p)
        for n in ['data/raw/C题/附件/附件1.xlsx','data/raw/C题/附件/附件2.xlsx',
                  'questions/Q1/runs/20260911-compare-v1/outputs/schedules/C04.csv',
                  'questions/Q1/runs/20260911-close-v1/deliverables/result1.xlsx',
                  'paper/q1_manuscript_v1/问题一论文草稿.pdf']:
            self.protected[n]=sha(P/n)
        df=pd.read_csv(P/'data/prepared-v1/actual_power.csv',float_precision='round_trip')
        df['start']=pd.to_datetime(df.source_date)+pd.to_timedelta(df.source_minute,unit='m')
        assert df.start.is_unique and (df.start.diff().dropna()==pd.Timedelta(minutes=10)).all()
        df['day']=(df.start.dt.normalize()-pd.Timestamp('2025-01-01')).dt.days
        df['slot']=df.start.dt.hour*6+df.start.dt.minute//10
        self.a={}
        for var,col in [('load','load_kw'),('pv','pv_actual_kw')]:
            self.a[var]=df.pivot(index='day',columns='slot',values=col).reindex(index=range(181),columns=range(144)).to_numpy()
            assert np.isnan(self.a[var]).sum()==1 and np.isnan(self.a[var][0,0])
        ref=pd.read_csv(P/'data/prepared-v1/day_reference.csv',float_precision='round_trip')
        ref['minute']=ref.source_minute%1440;ref=ref.sort_values('minute')
        assert list(ref.minute)==list(range(0,1440,10))
        self.ref={'load':ref.load_kw.to_numpy(),'pv':ref.pv_forecast_kw.to_numpy()}
        self.price=ref.price_yuan_per_kwh.to_numpy()
        q1=pd.read_csv(P/'questions/Q1/runs/20260911-compare-v1/outputs/schedules/C04.csv',float_precision='round_trip')
        assert list(q1.start_minute)==list(range(0,1440,10))
        self.q1=q1.purchase_kwh.to_numpy()
        np.savez_compressed(out/'source_arrays.npz',load=self.a['load'],pv=self.a['pv'],price=self.price,
                            reference_load=self.ref['load'],reference_pv=self.ref['pv'],q1_order=self.q1)
        dump(out/'source_hashes.json',self.protected)
        df[df.day.between(0,180)].to_csv(out/'actual_source_mapping.csv.gz',index=False,compression='gzip',encoding='utf-8-sig')

    def refmean(self,var,d,h,mode,n):
        # Only target-day calendar is future-known; all observed values have dates < d.
        if mode=='weekday':idx=[d+h-7*j for j in range(1,n+1) if 0<=d+h-7*j<d]
        else:idx=list(range(max(0,d-n),d))
        fallback=False
        if not idx:idx=list(range(max(0,d-7),d));fallback=True
        assert idx and max(idx)<d
        z=self.a[var][idx];count=np.isfinite(z).sum(axis=0)
        ans=np.divide(np.nansum(z,axis=0),count,out=self.ref[var].copy(),where=count>0)
        meta={'variable':var,'decision_date':daystr(d),'horizon_day':h+1,'mode':mode,'requested_n':n,
              'history_dates':[daystr(i) for i in idx],'weight_per_available_value':'1/count_at_slot',
              'count_min':int(count.min()),'count_max':int(count.max()),
              'calendar_fallback':fallback,'reference_only_slots':np.flatnonzero(count==0).tolist(),
              'latest_history_interval_end':daystr(max(idx)+1)+' 00:00'}
        return ans,meta

    def history(self,d,w,pv_days):
        L=[];V=[];weights=[]
        for h in [0,1]:
            l,lm=self.refmean('load',d,h,'weekday',w)
            v,vm=self.refmean('pv',d,h,'recent',pv_days)
            L.append(l);V.append(v);weights.extend([lm,vm])
        return np.concatenate(L),np.concatenate(V),weights

    def truth(self,d,initialization=False):
        l=self.a['load'][d].copy();v=self.a['pv'][d].copy()
        if d==0 and initialization:l[0]=self.ref['load'][0];v[0]=self.ref['pv'][0]
        assert np.isfinite(l).all() and np.isfinite(v).all()
        return l,v

    def features(self,d,h,var):
        k=np.arange(144);t=2*np.pi*k/144;target=pd.Timestamp(daystr(d+h));dow=target.dayofweek
        cols=[np.sin(t),np.cos(t),np.sin(2*t),np.cos(2*t)]
        names=['time_sin1','time_cos1','time_sin2','time_cos2']
        for i in range(7):cols.append(np.full(144,int(dow==i)));names.append('weekday_'+str(i))
        cols.extend([np.full(144,h+1),np.full(144,np.sin(2*np.pi*target.dayofyear/365)),
                     np.full(144,np.cos(2*np.pi*target.dayofyear/365))])
        names.extend(['horizon_day','year_sin','year_cos'])
        for mode,n,name in [('recent',1,'recent_slot_last'),('recent',3,'recent_slot_mean3'),
                            ('recent',7,'recent_slot_mean7'),('weekday',1,'matching_week1'),('weekday',4,'matching_week4')]:
            value,_=self.refmean(var,d,h,mode,n);cols.append(value);names.append(name)
        cols.extend([np.full(144,np.nanmean(self.a[var][d-1])),
                     np.full(144,np.nanmean(self.a[var][max(0,d-7):d]))])
        names.extend(['last_daily_level','recent7_daily_level'])
        x=np.column_stack(cols);assert np.isfinite(x).all()
        return x,names

class Forecasts:
    def __init__(self,data,out,event,guard):
        self.data=data;self.out=out;self.event=event;self.guard=guard;self.models={};self.cache={};self.fitcount=0
        self.X={};self.y={};self.origins=[];self.targets=[]
        for var in ['load','pv']:
            xs=[];ys=[];orig=[];target=[]
            for d in range(2,181):
                for h in [0,1]:
                    if d+h>=181:continue
                    x,self.names=data.features(d,h,var);xs.append(x);ys.append(data.a[var][d+h])
                    orig.extend([d]*144);target.extend([d+h]*144)
            self.X[var]=np.vstack(xs);self.y[var]=np.concatenate(ys)
            self.origins=np.array(orig);self.targets=np.array(target)
        np.savez_compressed(out/'feature_bank.npz',load_X=self.X['load'],pv_X=self.X['pv'],
                            load_y=self.y['load'],pv_y=self.y['pv'],origins=self.origins,targets=self.targets)
        dump(out/'feature_names.json',self.names)
        (out/'models').mkdir()

    def fit(self,kind,param,d):
        fitid=f'{kind}-{param}-{daystr(d)}';modelpair={}
        eligible=(self.origins>=max(2,d-56))&(self.targets<d)
        assert eligible.any() and int(self.targets[eligible].max())<d
        for var in ['load','pv']:
            self.guard();x=self.X[var][eligible];y=self.y[var][eligible];start=time.perf_counter()
            scaler=None
            if kind=='T2':
                scaler=StandardScaler();xt=scaler.fit_transform(x);model=Ridge(alpha=float(param));model.fit(xt,y)
            else:
                model=HistGradientBoostingRegressor(max_depth=int(param),max_iter=200,learning_rate=.05,
                       min_samples_leaf=48,l2_regularization=1.,max_bins=63,early_stopping=False,random_state=2026)
                model.fit(x,y)
            elapsed=time.perf_counter()-start
            if elapsed>60:raise RuntimeError('Single fit budget exceeded')
            self.fitcount+=1
            joblib.dump({'model':model,'scaler':scaler,'feature_names':self.names,'cutoff':daystr(d)},
                        self.out/'models'/f'{fitid}-{var}.joblib',compress=3)
            record={'fit_id':fitid,'variable':var,'cutoff':daystr(d),'n_rows':int(eligible.sum()),
                    'history_origin_min':daystr(self.origins[eligible].min()),
                    'latest_target_end':daystr(self.targets[eligible].max()+1)+' 00:00','seconds':elapsed,
                    'sample_weight':'uniform1','hyperparameter':param,'model':kind}
            if kind=='T2':
                unscaled=model.coef_/scaler.scale_
                record.update(coefficients_standardized=model.coef_.tolist(),coefficients_original=unscaled.tolist(),
                    feature_means=scaler.mean_.tolist(),feature_scales=scaler.scale_.tolist(),
                    intercept_original=float(model.intercept_-np.dot(unscaled,scaler.mean_)),
                    intercept_standardized=float(model.intercept_))
            else:
                counts=np.zeros(len(self.names),dtype=int)
                for group in model._predictors:
                    for tree in group:
                        nodes=tree.nodes
                        for z in nodes[nodes['is_leaf']==0]:counts[int(z['feature_idx'])]+=1
                record.update(learning_rate=.05,iterations=int(model.n_iter_),split_feature_counts=counts.tolist(),
                              split_counts_are_not_weights_or_causal_importance=True)
            self.event('fit_log',record);modelpair[var]=(model,scaler)
        self.models[(kind,param)]=(d,fitid,modelpair)
        return self.models[(kind,param)]

    def get(self,kind,param,d,phase_start):
        key=(kind,str(param),d,phase_start)
        if key in self.cache:return self.cache[key]
        if kind=='T1':
            w,p=param;l,v,weights=self.data.history(d,w,p);fitid='equal-history'
            for row in weights:self.event('history_weights',dict(setting=f'w{w}-p{p}',**row))
        else:
            previous=self.models.get((kind,param))
            if previous is None or d==phase_start or d-previous[0]>=7:previous=self.fit(kind,param,d)
            fitday,fitid,models=previous
            assert fitday<=d
            forecasts=[]
            for var in ['load','pv']:
                x=np.vstack([self.data.features(d,h,var)[0] for h in [0,1]])
                model,scaler=models[var];pred=model.predict(scaler.transform(x) if scaler is not None else x)
                pred=np.maximum(pred,0.)
                if var=='pv':
                    support=np.any(self.data.a['pv'][max(0,d-28):d]>0,axis=0)
                    pred*=np.tile(support,2)
                forecasts.append(pred)
            l,v=forecasts
        assert np.isfinite(l).all() and np.isfinite(v).all() and min(l.min(),v.min())>=0
        self.event('forecast_registry',{'kind':kind,'parameter':str(param),'decision_date':daystr(d),
             'fit_id':fitid,'forecast_horizon_days':2,'latest_allowed_observation_end':daystr(d)+' 00:00',
             'prediction_sha256':hashlib.sha256(np.r_[l,v].tobytes()).hexdigest()})
        self.cache[key]=(l,v);return l,v

class Planner:
    def __init__(self,price,event,guard):
        self.p=np.tile(price,2);self.value=.9*price[0];self.calls=0;self.event=event;self.guard=guard
        n=288;self.n=n;eq=lil_matrix((n,4*n));ub=lil_matrix((n,4*n))
        for k in range(n):
            eq[k,k]=-.9;eq[k,n+k]=-.9;eq[k,2*n+k]=1/.9;eq[k,3*n+k]=1
            if k:eq[k,3*n+k-1]=-1
            ub[k,k]=ub[k,n+k]=1
        self.eq=eq.tocsr();self.ub=ub.tocsr();self.bub=np.full(n,5000/6)
        self.c=np.r_[self.p,np.zeros(n),-self.p,np.zeros(n)];self.c[-1]=-self.value

    def solve(self,L,V,state,margin,meta):
        self.guard();self.calls+=1
        if self.calls>1200:raise RuntimeError('LP hard budget exceeded')
        n=self.n;net=np.maximum((L-V)/6+margin,0);excess=np.maximum((V-L)/6-margin,0)
        lo=np.r_[np.zeros(3*n),np.full(n,1200.)]
        hi=np.r_[np.full(n,5000/6),np.minimum(excess,5000/6),np.minimum(net,5000/6),np.full(n,10800.)]
        beq=np.zeros(n);beq[0]=state;start=time.perf_counter()
        r=linprog(self.c,A_ub=self.ub,b_ub=self.bub,A_eq=self.eq,b_eq=beq,bounds=np.column_stack((lo,hi)),
                  method='highs',options={'time_limit':10.,'primal_feasibility_tolerance':1e-8,'dual_feasibility_tolerance':1e-8})
        elapsed=time.perf_counter()-start
        if not r.success:raise RuntimeError(r.message)
        x,y,z,s=np.split(r.x,4);q=net-z+x
        eqerr=np.max(np.abs(self.eq@r.x-beq));uberr=max(0.,np.max(self.ub@r.x-self.bub))
        berr=max(0.,np.max(lo-r.x),np.max(r.x-hi))
        dual=beq@r.eqlin.marginals+self.bub@r.ineqlin.marginals+lo@r.lower.marginals+hi@r.upper.marginals
        gap=abs(r.fun-dual);sim=int(np.sum((x+y>1e-6)&(z>1e-6)))
        assert max(eqerr,uberr,berr)<1e-6 and gap<1e-4 and sim==0 and q.min()>-1e-6
        q=np.maximum(q,0)
        self.event('solver_checks',dict(**meta,status=int(r.status),seconds=elapsed,eq_residual=float(eqerr),
               inequality_residual=float(uberr),bound_residual=float(berr),primal_dual_gap=float(gap),
               simultaneous_slots=sim,objective=float(r.fun+self.p@net),initial_storage=float(state),
               terminal_storage=float(s[-1]),terminal_value=float(self.value)))
        return q,x,y,z,s

def execute(L,V,q,initial,price):
    rows=[];state=float(initial)
    for k in range(144):
        load=float(L[k]/6);pv=float(V[k]/6);order=float(q[k]);m=min(load,pv);need=load-m;surplus=pv-m
        s0=state
        if need>order:
            z=min(need-order,5000/6,max(0.,.9*(state-1200)))
            e=max(0.,need-order-z);y=x=0.;received=order
        else:
            c=min(surplus+order-need,5000/6,max(0.,(10800-state)/.9))
            y=min(surplus,c);x=c-y;received=need+x;z=e=0.
        state+=.9*(x+y)-z/.9
        unused_order=max(0.,order-received);unused_pv=max(0.,surplus-y)
        bal=m+(received-x)+z+e-load
        assert abs(bal)<1e-6 and 1200-1e-6<=state<=10800+1e-6
        rows.append({'slot':k,'load_kw':float(L[k]),'pv_kw':float(V[k]),'price':float(price[k]),
                     'order_kwh':order,'received_kwh':received,'grid_to_load_kwh':received-x,
                     'direct_pv_kwh':m,'grid_charge_kwh':x,'pv_charge_kwh':y,'discharge_kwh':z,
                     'emergency_kwh':e,'unused_order_kwh':unused_order,'unused_pv_kwh':unused_pv,
                     'storage_start_kwh':s0,'storage_end_kwh':state,
                     'ordinary_cost':float(price[k]*order),'emergency_cost':float(5*price[k]*e),
                     'balance_residual':bal})
    return rows,state

def metrics(rows,Lhat,Vhat):
    df=pd.DataFrame(rows);r={n:float(df[n].sum()) for n in ['order_kwh','received_kwh','grid_charge_kwh',
             'pv_charge_kwh','discharge_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh','ordinary_cost','emergency_cost']}
    errorL=df.load_kw.to_numpy()-Lhat[:144];errorV=df.pv_kw.to_numpy()-Vhat[:144];pos=df.pv_kw.to_numpy()>0
    event=df.emergency_kwh.to_numpy()>1e-6
    longest=cur=0
    for yes in event:cur=cur+1 if yes else 0;longest=max(longest,cur)
    r.update(total_cost=r['ordinary_cost']+r['emergency_cost'],storage_start_kwh=rows[0]['storage_start_kwh'],
             storage_end_kwh=rows[-1]['storage_end_kwh'],emergency_slots=int(event.sum()),
             longest_emergency_minutes=int(longest*10),load_abs_error_sum=float(abs(errorL).sum()),
             pv_abs_error_sum=float(abs(errorV).sum()),pv_positive_abs_error_sum=float(abs(errorV[pos]).sum()),
             pv_positive_slots=int(pos.sum()),net_abs_error_sum=float(abs(errorL-errorV).sum()),
             load_squared_error_sum=float((errorL**2).sum()),pv_squared_error_sum=float((errorV**2).sum()))
    return r
