"""Independent read-back checks. Does not import the planner/forecast code or solve/train."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import json,hashlib,warnings
warnings.filterwarnings('ignore',message='Pandas requires version')
from pathlib import Path
from decimal import Decimal,localcontext
import numpy as np
import pandas as pd
import joblib
from threadpoolctl import threadpool_limits

R=Path(__file__).resolve().parent;P=R.parents[3];O=R/'outputs';N=52560
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
maxima={};counts={}
def close(name,a,b,tol=1e-6):
    err=float(np.max(np.abs(np.asarray(a)-np.asarray(b)))) if np.size(a) else 0.
    maxima[name]=max(maxima.get(name,0),err);assert np.isfinite(err) and err<tol,(name,err)
def save(name,obj): (O/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def forecasts():
    s=dict(np.load(O/'sources.npz'));c=dict(np.load(O/'forecasts.npz'));m=dict(np.load(O/'margins.npz'))
    for path,digest in read(O/'protected_sources.json').items():assert sha(P/path)==digest,path
    f=pd.read_csv(P/'data/prepared-v1/pv_forecasts.csv',float_precision='round_trip')
    aa=pd.read_csv(P/'data/prepared-v1/actual_power.csv',float_precision='round_trip')
    dates=pd.to_datetime(aa.source_date)+pd.to_timedelta(aa.source_minute,unit='m')
    index=((dates-pd.Timestamp('2025-01-01')).dt.total_seconds()/600).to_numpy().astype(int)
    close('actual_source',s['actual'][index],aa[['load_kw','pv_actual_kw']].to_numpy(),1e-10)
    close('forecast_source',s['F'].ravel(),f.pv_forecast_kw.to_numpy(),1e-10)
    release=s['release'];T=s['targets'];actual=s['actual'];F=s['F'];ref=s['reference']
    hist=np.empty((1460,144))
    for b,r in enumerate(release):
        for k in range(144):
            ix=np.arange(k,r,144);ix=ix[ix>0][-7:]
            hist[b,k]=actual[ix,1].mean() if len(ix) else ref[k,1]
    close('historical_PV',hist,c['hist'],1e-9)
    H=hist[np.arange(1460)[:,None],T%144];close('historical_hourly_PV',H,c['H'],1e-9)
    last=np.array([actual[r-1,1] if r else ref[0,1] for r in release]);close('anchor',last,c['last'],1e-10)
    for d in range(365):
        for h in [0,1]:
            ix=[j for j in range(d) if (j-(d+h))%7==0][-4:]
            if not ix:ix=list(range(max(0,d-7),d))
            if not ix:lp=ref[:,0]
            else:
                dat=actual[np.array(ix)[:,None]*144+np.arange(144),0];nn=np.isfinite(dat).sum(axis=0)
                lp=np.divide(np.nansum(dat,axis=0),nn,out=ref[:,0].copy(),where=nn>0)
            close('load_reference',lp,c['L'][d,h*144:(h+1)*144],1e-9)
    rr=np.repeat(release,24);tt=T.ravel();Ff=F.ravel();Hf=H.ravel();truth=np.full(len(tt),np.nan)
    use=tt<N;truth[use]=actual[tt[use],1];bands=np.tile(np.arange(24)//6,1460)
    for b,r in enumerate(release):
        pool=(rr>=r-4032)&(rr<r)&(tt<r)&(rr%144==r%144)&np.isfinite(truth)
        for g in range(4):
            ids=np.flatnonzero(pool&(bands==g))
            if len(ids)<24:ids=np.flatnonzero(pool)
            assert len(ids)==c['counts'][b,g]
            u=Ff[ids]-Hf[ids];den=np.sum(u*u)
            w=float(np.clip(np.sum(u*(truth[ids]-Hf[ids]))/den,0,1)) if len(ids)>=24 and den>=1e-12 else 1.
            close('fusion_weight',w,c['weights'][b,g],1e-9)
            assert c['latest_fit_end'][b,g]<=r
    fused=np.repeat(c['weights'],6,axis=1)*F+(1-np.repeat(c['weights'],6,axis=1))*H
    close('fusion_hourly',fused,c['fused_hourly'],1e-9)
    hr=T%144/6;yr=T//144+1
    X=np.column_stack([Ff,Hf,np.repeat(last,24),np.repeat(release%144/6,24),np.tile(np.arange(1,25),1460),
        np.sin(2*np.pi*hr.ravel()/24),np.cos(2*np.pi*hr.ravel()/24),np.sin(2*np.pi*yr.ravel()/365),np.cos(2*np.pi*yr.ravel()/365)])
    close('tree_features',X,c['X'],1e-9)
    fitlog=read(O/'tree_fits.json')
    for rec in fitlog:
        r=rec['release'];path=R/rec['model'];assert sha(path)==rec['sha256']
        expected=np.flatnonzero((rr>=r-90*144)&(rr<r)&(tt<r)&np.isfinite(truth))
        assert np.array_equal(np.load(path.with_suffix('.indices.npy')),expected)
        assert rec['latest_end']==int(np.max(tt[expected]+1))<=r
        mod=joblib.load(path);params=mod.get_params()
        assert params['early_stopping']==False and params['random_state']==2026 and params['max_leaf_nodes']==rec['leaf']
        b0=r//36;b1=min(b0+28,1460)
        with threadpool_limits(limits=1):pv=np.maximum(0,Ff[b0*24:b1*24]+mod.predict(X[b0*24:b1*24]))
        close('saved_tree_prediction',pv,c['tree'+str(rec['leaf'])+'_hourly'][b0:b1].ravel(),1e-8)
    for key,hh in [('raw',F),('fused',fused),('tree7',c['tree7_hourly']),('tree15',c['tree15_hourly'])]:
        for b,r in enumerate(release):
            n=288-r%144;j=np.arange(144);h=j//6;fraction=(j%6)/6
            anchors=np.r_[last[b],hh[b]];expected=(1-fraction)*anchors[h]+fraction*anchors[h+1]
            tail=hist[b,(r+np.arange(144,n))%144]
            close('interval_'+key,np.r_[expected,tail],c[key][b,:n],1e-8)
    for b,r in enumerate(release):
        n=288-r%144;mid=r-r%144;end=144-r%144;j=np.arange(end)
        clock=r%144+j;left=clock//6;right=left+1;frac=j%6/6
        anchors=np.r_[0,F[mid//144*4]];anchors[r%144//6]=last[b]
        expect=(1-frac)*anchors[left]+frac*anchors[right]
        close('old_version_only',np.r_[expect,hist[b,(r+np.arange(end,n))%144]],c['old'][b,:n],1e-8)
    err=dict(np.load(O/'error_records.npz'));br=err['release']//36;offset=err['target']-err['release']
    ee=((actual[err['target'],0]-actual[err['target'],1])-(
         c['L'][err['release']//144,err['release']%144+offset]-c['fused'][br,offset]))/6
    close('own_as_issued_errors',ee,err['error'],1e-9)
    assert np.array_equal(err['kind'],(offset>=144).astype(int))
    for b,typ,g,num,fb,latest in m['sample_meta']:
        r=release[b];use=(err['release']>=r-28*144)&(err['release']<r)&(err['release']%144==r%144)&(err['target']<r)&(err['kind']==typ)
        same=use&(err['target']%144//24==g)
        ids=np.flatnonzero(same if same.sum()>=24 else use);assert len(ids)==num
        assert latest<=r and latest==(int(np.max(err['target'][ids]+1)) if len(ids) else -1)
        order=np.argsort(err['error'][ids],kind='stable');ids=ids[order]
        n=288-r%144;ttt=r+np.arange(n);dest=(ttt%144//24==g)&((np.arange(n)>=144)==bool(typ))
        for j,(alpha,beta) in enumerate(m['pairs']):
            if len(ids)<24:q=0.
            else:
                age=(r-1)//144-err['target'][ids]//144
                with localcontext() as context:
                    context.prec=80
                    powers=[Decimal(str(float(beta)))**a for a in range(int(age.max())+1)]
                    weights=[powers[int(a)] for a in age];threshold=Decimal(str(float(alpha)))*sum(weights,Decimal(0))
                    acc=Decimal(0)
                    for ix,weight in enumerate(weights):
                        acc+=weight
                        if acc>=threshold:break
                q=max(0.,float(err['error'][ids[ix]]))
            close('margin_quantile',m['values'][j,b,:n][dest],q,1e-7)
    counts.update(hourly_forecasts=len(tt),tree_fits=len(fitlog),prepared_error_records=len(ee),margin_groups=len(m['sample_meta']))
    return s,c,m

def strategies(s,c,m):
    summary=read(O/'summary.json');price=s['price'];actual=s['actual'];seen=set();plans_checked=slots=0
    D=lambda x:Decimal(str(float(x)))
    for rec in summary['calibration']+summary['annual']:
        if rec['trace'] in seen:continue
        seen.add(rec['trace']);z=dict(np.load(R/rec['trace']));days=z['days'];q0=z['q0'];v=z['versions'];ex=z['execution'];state=rec['initial']
        daily=pd.read_csv(R/rec['daily_csv'],float_precision='round_trip');total=Decimal(0)
        logs=read((R/rec['trace']).with_suffix('.solver.json'));log_index=0
        for di,d in enumerate(days):
            close('q0_immutable',v[di,0],q0[di],1e-12)
            for a,start in enumerate([0,36,72,108]):
                if a:close('executed_prefix_locked',v[di,a,:start],v[di,a-1,:start],1e-12)
                close('decision_inventory',z['decision_storage'][di,a],state,1e-7)
                n=288-start;b=d*4+a
                expected_pv=c['raw'][d*4,start:] if rec['mode']=='I0' else c[rec['prediction_key']][b,:n]
                close('used_prediction',expected_pv,z['predictions'][di,a,:n],1e-9)
                margin=np.zeros(n) if rec['margin_index'] is None else m['values'][rec['margin_index'],b,:n]
                close('used_margin',margin,z['margins'][di,a,:n],1e-9)
                if z['decision_mask'][di,a]:
                    plan=z['plans'][di,a,:,:n];x,y,dis,S,e,r,q,w=plan
                    net=np.maximum((c['L'][d,start:]-expected_pv)/6+margin,0);sur=np.maximum(-((c['L'][d,start:]-expected_pv)/6+margin),0)
                    close('plan_storage',S,np.r_[state,S[:-1]]+.9*(x+y)-dis/.9)
                    close('plan_supply',q-x+dis+e-r,net)
                    assert np.min(plan)>-1e-6 and np.min(S)>=1200-1e-6 and np.max(S)<=10800+1e-6
                    assert np.max(x+y)<=5000/6+1e-6 and np.max(dis)<=5000/6+1e-6 and np.max(dis+e-net)<1e-6 and np.max(y-sur)<1e-6
                    p=price[(start+np.arange(n))%144];obj=p@q+5*p@e-.9*price[0]*S[-1]
                    if a:
                        f=144-start;assert np.min(w[:f]-abs(q[:f]-q0[di,start:]))>-1e-6
                        obj+=.5*p[:f]@abs(q[:f]-q0[di,start:])
                    close('plan_objective_readback',obj,logs[log_index]['objective'],1e-5);log_index+=1;plans_checked+=1
                    close('planned_order_committed',np.maximum(q[:144-start],0),v[di,a,start:],1e-9)
                for k in range(start,start+36):
                    load,pv=actual[d*144+k]/6;order=v[di,a,k];direct=min(load,pv);balance=order+direct-load;old=state
                    if balance<0:
                        discharge=min(-balance,5000/6,.9*(state-1200));emergency=-balance-discharge;xc=yc=0.;received=order
                    else:
                        charge=min(balance+pv-direct,5000/6,(10800-state)/.9)
                        yc=min(charge,pv-direct);xc=charge-yc;discharge=emergency=0.;received=load-direct+xc
                    state=old+.9*(xc+yc)-discharge/.9
                    row=[old,state,received,received-xc,direct,xc,yc,discharge,emergency,max(0,order-received),max(0,pv-direct-yc),load]
                    close('actual_execution',row,ex[di,k],1e-6);slots+=1
            close('day_end_inventory',state,daily.final.iloc[di],1e-6)
            with localcontext() as ctx:
                ctx.prec=35
                normal=sum((D(price[k])*D(v[di,3,k])+Decimal('.5')*D(price[k])*abs(D(v[di,3,k])-D(q0[di,k])) for k in range(144)),Decimal(0))
                emerg=sum((Decimal(5)*D(price[k])*D(ex[di,k,8]) for k in range(144)),Decimal(0))
            close('decimal_daily_ordinary',float(normal),daily.ordinary_cost.iloc[di],1e-6)
            close('decimal_daily_emergency',float(emerg),daily.emergency_cost.iloc[di],1e-6)
            total+=normal+emerg
        close('decimal_period_bill',float(total),rec['total_cost'],1e-5)
        assert log_index==len(logs)==rec['lp_calls']
    selection=summary['selection'];cal=summary['calibration']
    tree=min([x for x in cal if x['label'].startswith('S3')],key=lambda x:x['total_cost'])
    risk=min([x for x in cal if x['label']=='S2_fused' or x['label'].startswith('S4')],key=lambda x:x['total_cost'])
    assert selection['tree']==tree['prediction_key'] and selection['margin_index']==risk['margin_index']
    assert all(x['end']=='2025-01-31' for x in cal)
    assert all(x['days']==334 and x['initial']==8592.693560925925 for x in summary['annual'])
    counts.update(actual_intervals=slots,plans_readback=plans_checked,unique_strategies=len(seen))

if __name__=='__main__':
    try:
        s,c,m=forecasts();print('forecast, training and margin checks complete',flush=True)
        strategies(s,c,m)
        save('verification.json',dict(status='checks_completed',counts=counts,max_errors=maxima,new_fits=0,new_lp_calls=0,
             reviewer='same AI, independent read-back computation; not human approval',code_sha256=sha(Path(__file__))))
        print(json.dumps(dict(status='checks_completed',counts=counts,max_errors=maxima),ensure_ascii=False),flush=True)
    except Exception as e:
        save('verification_failure.json',dict(error=type(e).__name__,message=str(e),counts=counts,max_errors=maxima));raise
