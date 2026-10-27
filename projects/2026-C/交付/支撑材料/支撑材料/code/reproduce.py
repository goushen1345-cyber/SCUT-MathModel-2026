"""Reproduce the paper's final schedules from prepared inputs; no parameter search."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import q1,q2,q3_base,q3,q4,q4_tree,q4_update
ROOT=Path(__file__).resolve().parents[1]
SRC=dict(np.load(ROOT/'data/inputs.npz'))
OUT=Path(os.environ.get('SUPPORT_REPRO_OUTPUT',str(ROOT/'reproduced'))).resolve();OUT.mkdir(parents=True,exist_ok=True)

def save(label,order,execution,versions=None,qzero=None):
 arrays=dict(days=np.arange(31,31+len(order)),execution=execution)
 if versions is None:arrays['order']=order
 else:arrays.update(q0=qzero,versions=versions)
 np.savez_compressed(OUT/f'{label}.npz',**arrays)
 return arrays

def question1():
 cfg=json.loads((ROOT/'data/q1_config.json').read_text())
 ref=pd.read_csv(ROOT/'results/Q1.csv',float_precision='round_trip')
 # Only source inputs are reused; orders, states and costs are solved anew.
 inputs=ref[['k','start_minute','end_minute','load_kw','pv_kw','price']].to_dict('records')
 actions,certificate=q1.solve_lp(inputs,cfg);rows=q1.schedule(inputs,cfg,actions)
 pd.DataFrame(rows).to_csv(OUT/'Q1.csv',index=False,float_format='%.17g')
 assert abs(sum(r['cost_yuan'] for r in rows)-35126.85)<.005
 return np.array([r['purchase_kwh'] for r in rows])

def january(data,q1order):
 planner=q2.Planner(data.price,lambda *a:None,lambda:None);state=6000.;orders=[];ex=[]
 for d in range(31):
  order=q1order if d==0 else planner.solve(*data.history(d,1,3)[:2],state,np.zeros(288),{})[0][:144]
  l,v=data.truth(d,initialization=d==0);block,state=q3_base.execute_block(l,v,order,state)
  orders.append(order);ex.append(block)
 np.savez_compressed(OUT/'January.npz',days=np.arange(31),order=orders,execution=ex)
 assert abs(state-8592.693560925925)<1e-6,state
 return state

def question2(data,initial,end,quantile=.7,decay=.7):
 planner=q2.Planner(data.price,lambda *a:None,lambda:None);risk=q2.Risk(data);state=initial;orders=[];ex=[]
 for d in range(31,end):
  l,v,_=data.history(d,4,7);m,_=risk.margin(d,quantile,28,4,decay)
  order=planner.solve(l,v,state,m,{})[0][:144]
  a,b=data.truth(d);block,state=q3_base.execute_block(a,b,order,state);orders.append(order);ex.append(block)
 return save('Q2',np.array(orders),np.array(ex))

def supply3(family='EW4',quantile=.6,information='full'):
 actual,reference,F,release,targets=(SRC[k] for k in ['actual','reference','F','release','targets'])
 hist,last,L,H,X=q3_base.history_and_features(actual,reference,F,release,targets)
 hourly,w,count,fb,cut=q3_base.build_fusion(actual,F,H,release,targets)
 if information=='no_new':
  oldF=H.copy()
  for b,r in enumerate(release):
   midnight=r//144*144;t=targets[b];use=t<=midnight+144
   oldF[b,use]=F[(r//144)*4,((t[use]-midnight)//6-1).astype(int)]
  hourly,w,count,fb,cut=q3_base.build_fusion(actual,oldF,H,release,targets)
 full=q3_base.to_intervals(hourly,hist,last,release)
 q3.src=SRC;q3.orig={'L':L};q3.fc={'L':q3.midnight(family)}
 load,theta,obs,count=q3.make_load('LEARN_PREFIX',1.)
 err=q3.errors_for(load,full);q3.group_cache=None;margin=np.full((1460,288),np.nan)
 for b,typ,g,dest,ids,ages,fallback in q3.group_index(err):
  margin[b,dest]=q3.quantile(err['error'][ids],ages,quantile) if len(ids)>=24 else 0.
 np.savez_compressed(OUT/'supply3.npz',load=load,pv=full,margin=margin,weights=w,theta=theta)
 return load,full,margin

def question3(initial,end,supply,locked=False):
 load,pv,margin=supply;planner=q3.Planner(SRC['price'],q3.Budget());state=initial
 orders=[];zeros=[];versions=[];ex=[]
 for d in range(31,end):
  order=np.zeros(144);dayversions=[];blocks=[]
  for a,r in enumerate((0,36,72,108)):
   b=d*4+a;n=288-r
   if a==0 or not locked:
    plan,_=planner.solve(load[b,:n],pv[b,:n],state,margin[b,:n],r,None if a==0 else qzero[r:])
    order[r:]=np.maximum(0,plan[6,:144-r])
   if a==0:qzero=order.copy()
   dayversions.append(order.copy());truth=SRC['actual'][d*144+r:d*144+r+36]
   block,state=q3_base.execute_block(truth[:,0],truth[:,1],order[r:r+36],state);blocks.append(block)
  orders.append(order.copy());zeros.append(qzero);versions.append(dayversions);ex.append(np.concatenate(blocks))
  if (d-30)%100==0:print('Q3 completed days',d-30,flush=True)
 return save('Q3',np.array(orders),np.array(ex),np.array(versions),np.array(zeros))

def question4(data,initial,end,supply,branch):
 for m in (q4,q4_tree,q4_update):m.R=OUT;m.O=OUT
 prices=SRC['actual_prices'];reference=SRC['price'];state=initial
 if branch=='Q4-2':
  load=np.empty((365,288));pv=load.copy();margin=load.copy();risk=q4.Q2Risk(data)
  load[0]=np.tile(SRC['reference'][:,0],2);pv[0]=np.tile(SRC['reference'][:,1],2);margin[0]=0
  for d in range(1,365):load[d],pv[d],_=data.history(d,4,7);margin[d]=risk.margin(d)[0]
  features=q4.PriceFeatures(prices,reference,dict(load=load,pv=pv),branch)
  engine=q4_tree.ForecastEngine('Q4-2-leaves31',features,'p3',max_leaf_nodes=31)
  planner=q4.Q42Planner(.9*reference[0]);orders=[];ex=[]
  for d in range(31,end):
   forecast=engine.predict(d,0);order=planner.solve(load[d],pv[d],state,margin[d],forecast,dict(day=d))[:144]
   a,b=data.truth(d);block,state=q4.execute_block(a,b,order,state);orders.append(order);ex.append(block)
   if (d-30)%50==0:print(branch,'completed days',d-30,flush=True)
  return save(branch,np.array(orders),np.array(ex))
 load,pv,margin=supply
 features=q4_update.Features(prices,reference,dict(load=load,pv=pv),branch)
 engine=q4_update.Prices(features,branch);planner=q4.Q43Planner(.9*reference[0])
 orders=[];zeros=[];versions=[];ex=[]
 for d in range(31,end):
  order=np.zeros(144);dayversions=[];blocks=[]
  for a,r in enumerate((0,36,72,108)):
   b=d*4+a;n=288-r;forecast=engine.predict('P2',d,r)
   order[r:]=planner.solve(load[b,:n],pv[b,:n],state,margin[b,:n],r,None if a==0 else qzero[r:],forecast,dict(day=d,release_slot=r))[:144-r]
   if a==0:qzero=order.copy()
   dayversions.append(order.copy());truth=SRC['actual'][d*144+r:d*144+r+36]
   block,state=q4.execute_block(truth[:,0],truth[:,1],order[r:r+36],state);blocks.append(block)
  orders.append(order.copy());zeros.append(qzero);versions.append(dayversions);ex.append(np.concatenate(blocks))
  if (d-30)%100==0:print(branch,'completed days',d-30,flush=True)
 return save(branch,np.array(orders),np.array(ex),np.array(versions),np.array(zeros))

def compare(label,z):
 old=np.load(ROOT/'results'/f'{label}.npz');n=len(z['days']);errors={}
 for k in ('order','q0','versions','execution'):
  if k in z:
   errors[k]=float(np.max(abs(z[k]-old[k][:n])))
   np.testing.assert_allclose(z[k],old[k][:n],rtol=0,atol=1e-5,err_msg=label+' '+k)
 print(label,'reproduced',n,'days; max differences',errors,flush=True)
 return errors

def main():
 p=argparse.ArgumentParser();p.add_argument('--question',choices=['all','Q1','Q2','Q3','Q4-2','Q4-3'],default='all');p.add_argument('--days',type=int,default=334);a=p.parse_args()
 assert 1<=a.days<=334;end=31+a.days
 data=q2.Data(SRC);order=question1();initial=january(data,order);report={}
 if a.question in ('all','Q2'):report['Q2']=compare('Q2',question2(data,initial,end))
 supply=supply3() if a.question in ('all','Q3','Q4-3') else None
 if a.question in ('all','Q3'):report['Q3']=compare('Q3',question3(initial,end,supply))
 for branch in ('Q4-2','Q4-3'):
  if a.question in ('all',branch):report[branch]=compare(branch,question4(data,initial,end,supply,branch))
 (OUT/'reproduction_check.json').write_text(json.dumps(dict(days=a.days,errors=report),indent=2),encoding='utf-8')
if __name__=='__main__':
 with threadpool_limits(limits=1):main()
