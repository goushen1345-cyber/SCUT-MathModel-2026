"""Run the authorized Q3 batch; restart resumes completed strategies/caches."""
from core import *

def preflight(planner):
    if (O/'preflight.json').exists():return
    original_price=planner.price.copy();planner.price=np.ones(144)
    tests=[]
    for demand,expected in [(80,90),(90,95),(120,130),(0,50)]:
        z,c=planner.solve(np.array([demand*6.]),np.array([0.]),1200.,np.zeros(1),0,np.array([100.]),terminal=False)
        q=z[6,0];bill=q+.5*abs(q-100)
        assert abs(q-demand)<1e-7 and abs(bill-expected)<1e-7
        tests.append(dict(demand=demand,original=100.,final=float(q),bill=float(bill),expected=expected,check=c))
    # Keeping an insufficient/excessive order remains feasible using emergency/unreceived terms.
    for fixed in [0.,200.]:
        z,c=planner.solve(np.array([600.]),np.array([0.]),1200.,np.zeros(1),0,np.array([100.]),fixed=np.array([fixed]),terminal=False)
        assert abs(z[6,0]-fixed)<1e-7
        tests.append(dict(fixed=fixed,emergency=float(z[4,0]),unreceived=float(z[5,0]),check=c))
    planner.price=original_price;dump(O/'preflight.json',tests);planner.budget.save()

def run_strategy(label,key,margin_idx,days,initial,mode,data,fc,mg,planner):
    folder=O/('calibration' if days[0]==7 else 'annual');folder.mkdir(exist_ok=True)
    path=folder/(label+'.npz');sp=folder/(label+'.summary.json')
    if path.exists() and sp.exists():return json.loads(sp.read_text())
    D=len(days);qzero=np.empty((D,144));versions=np.empty((D,4,144));exe=np.empty((D,144,12))
    plans=np.full((D,4,8,288),np.nan);pred=np.full((D,4,288),np.nan);marg=np.full((D,4,288),np.nan)
    startS=np.empty((D,4));decision=np.zeros((D,4),int);daily=[];checks=[];s=float(initial)
    actual=data['actual'];price=data['price'];state_start=s;L=fc['L'];pred_base=fc[key]
    for di,d in enumerate(days):
        q=np.zeros(144);before=s
        for a,slot in enumerate([0,36,72,108]):
            b=d*4+a;n=288-slot;startS[di,a]=s
            if mode=='I0':pv=fc['raw'][d*4,slot:288]
            else:pv=pred_base[b,:n]
            margin=np.zeros(n) if margin_idx is None else mg['values'][margin_idx,b,:n]
            pred[di,a,:n]=pv;marg[di,a,:n]=margin
            if a==0 or mode!='I0':
                z,c=planner.solve(L[d,slot:],pv,s,margin,slot,None if a==0 else qzero[di,slot:])
                decision[di,a]=1;plans[di,a,:,:n]=z
                q[slot:]=np.maximum(0,z[6,:144-slot])
                c.update(day=int(d),release_hour=slot/6,label=label);checks.append(c)
                if a==0:qzero[di]=q.copy()
            versions[di,a]=q
            tr=actual[d*144+slot:d*144+slot+36]
            block,s=execute_block(tr[:,0],tr[:,1],q[slot:slot+36],s);exe[di,slot:slot+36]=block
        qf=q;delta=qf-qzero[di]
        retained=float(price@np.minimum(qf,qzero[di]));inc=float(1.5*price@np.maximum(delta,0));pen=float(.5*price@np.maximum(-delta,0))
        ordinary=retained+inc+pen;emergency=float(5*price@exe[di,:,8]);orig=float(price@qzero[di])
        mask=exe[di,:,8]>1e-6;longest=cur=0
        for x in mask:cur=cur+1 if x else 0;longest=max(longest,cur)
        row=dict(label=label,date=daystr(d),day=int(d),initial=before,final=s,original_plan_cost=orig,
                 ordinary_cost=ordinary,emergency_cost=emergency,total_cost=ordinary+emergency,net_adjustment=ordinary-orig,
                 retained_base_cost=retained,increased_order_cost=inc,reduction_penalty=pen,
                 original_order_kwh=float(qzero[di].sum()),final_order_kwh=float(qf.sum()),
                 increased_final_kwh=float(np.maximum(delta,0).sum()),reduced_final_kwh=float(np.maximum(-delta,0).sum()),
                 emergency_kwh=float(exe[di,:,8].sum()),emergency_slots=int(mask.sum()),longest_emergency_minutes=longest*10,
                 unused_order_kwh=float(exe[di,:,9].sum()),unused_pv_kwh=float(exe[di,:,10].sum()),
                 grid_charge_kwh=float(exe[di,:,5].sum()),pv_charge_kwh=float(exe[di,:,6].sum()),discharge_kwh=float(exe[di,:,7].sum()))
        daily.append(row)
        if di%31==0:event('strategy_progress',label=label,through=daystr(d),days_done=di+1,lp_calls=planner.budget.calls);planner.budget.save()
    np.savez_compressed(path,days=np.array(days),q0=qzero,versions=versions,execution=exe,plans=plans,
                       predictions=pred,margins=marg,decision_storage=startS,decision_mask=decision)
    df=pd.DataFrame(daily);df.to_csv(folder/(label+'.daily.csv'),index=False,encoding='utf-8-sig',float_format='%.17g')
    sums=['original_plan_cost','ordinary_cost','emergency_cost','total_cost','net_adjustment','increased_order_cost','reduction_penalty',
          'original_order_kwh','final_order_kwh','increased_final_kwh','reduced_final_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh',
          'grid_charge_kwh','pv_charge_kwh','discharge_kwh']
    result={k:float(df[k].sum()) for k in sums}
    result.update(label=label,prediction_key=key,margin_index=margin_idx,mode=mode,days=D,start=daystr(days[0]),end=daystr(days[-1]),
                  initial=state_start,final=s,emergency_days=int((df.emergency_kwh>1e-6).sum()),
                  max_daily_cost=float(df.total_cost.max()),max_emergency_run=int(df.longest_emergency_minutes.max()),
                  trace=str(path.relative_to(R)),daily_csv=str((folder/(label+'.daily.csv')).relative_to(R)),
                  lp_calls=len(checks),max_primal_residual=max(c['residual'] for c in checks),
                  max_dual_gap=max(c['dual_gap'] for c in checks),planned_simultaneous=sum(c['simultaneous'] for c in checks))
    dump(folder/(label+'.solver.json'),checks);dump(sp,result);planner.budget.save()
    event('strategy_complete',label=label,total=result['total_cost'],emergency=result['emergency_cost'],final=s)
    return result

def main():
    O.mkdir(exist_ok=True);budget=Budget()
    try:
        prepare(budget)
        data=np.load(O/'sources.npz');fc=np.load(O/'forecasts.npz');mg=np.load(O/'margins.npz')
        init=json.loads((O/'initialization.json').read_text());planner=Planner(data['price'],budget);preflight(planner)
        cal=[]
        base=[('S1_raw','raw',None),('S2_fused','fused',None),('S3_leaf7','tree7',None),('S3_leaf15','tree15',None)]
        for j,(alpha,beta) in enumerate(mg['pairs']):base.append((f'S4_a{alpha:g}_b{beta:g}','fused',j))
        for label,key,idx in base:cal.append(run_strategy(label,key,idx,list(range(7,31)),init['jan8'],'full',data,fc,mg,planner))
        tree=min([x for x in cal if x['label'].startswith('S3')],key=lambda x:x['total_cost'])
        risk=min([x for x in cal if x['label']=='S2_fused' or x['label'].startswith('S4')],key=lambda x:x['total_cost'])
        selection=dict(selected_after='2025-01-31 24:00',tree=tree['prediction_key'],margin_index=risk['margin_index'],
                       margin_parameters=None if risk['margin_index'] is None else mg['pairs'][risk['margin_index']].tolist(),
                       calibration_winner_tree=tree,calibration_winner_margin=risk,selection_uses='January actual total settlement plus emergency only')
        dump(O/'selection.json',selection);event('january_selection',tree=selection['tree'],margin=selection['margin_parameters'])
        annual=[];specs=[('S1_raw','raw',None,'full'),('S2_fused','fused',None,'full'),
                        ('S3_tree',tree['prediction_key'],None,'full'),('S4_margin','fused',risk['margin_index'],'full'),
                        ('I0_zero_only','raw',None,'I0'),('I1_no_new_forecast','old',None,'full')]
        for label,key,idx,mode in specs:
            if label=='S4_margin' and idx is None:
                z=dict(next(x for x in annual if x['label']=='S2_fused'));z.update(label=label,alias_of='S2_fused',lp_calls=0)
                dump(O/'annual/S4_margin.summary.json',z);annual.append(z);continue
            annual.append(run_strategy(label,key,idx,list(range(31,365)),init['feb1'],mode,data,fc,mg,planner))
        budget.save();dump(O/'summary.json',dict(status='completed_pending_independent_verification',calibration=cal,selection=selection,annual=annual,
              budget=json.loads((O/'budget.json').read_text()),execution_columns=EXEC_COLUMNS,protocol_sha256=sha(R/'protocol.json'),
              code={p.name:sha(p) for p in [R/'core.py',R/'run_compare.py']}))
        event('batch_complete',lp_calls=budget.calls,tree_fits=budget.fits)
    except Exception as exc:
        budget.save();dump(O/'failure.json',dict(type=type(exc).__name__,message=str(exc)));raise

if __name__=='__main__':main()
