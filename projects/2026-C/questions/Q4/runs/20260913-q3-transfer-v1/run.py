"""Transfer verified Q3 load feedback to original full-Ridge Q4-3, no future prices."""
from pathlib import Path
import os,json,time,hashlib,importlib.util
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parent;P=R.parents[3];O=R/'outputs'
OLD=P/'questions/Q4/runs/20260912-three-candidates-v1'
DEP=P/'questions/Q4/runs/20260912-selected-deepening-v1'
UP=P/'questions/Q3/runs/20260912-forecast-risk-v1'
read=lambda p:json.loads(Path(p).read_text('utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('q4',OLD/'run_compare.py');q4=importlib.util.module_from_spec(spec);spec.loader.exec_module(q4)
q4.R=R;q4.O=O
dump=q4.dump
class Budget:
 def __init__(self):self.start=time.perf_counter();self.lp_calls=0;self.price_fits=0
 def check(self):assert self.lp_calls<=9000 and self.price_fits<=60 and time.perf_counter()-self.start<=1800
 def save(self):dump(O/'budget.json',dict(lp_calls=self.lp_calls,price_fits=self.price_fits,seconds=time.perf_counter()-self.start))
budget=Budget();q4.budget=budget
class Features(q4.PriceFeatures):
 def supply_forecast(self,day,slot):
  b=day*4+slot//36;n=288-slot
  return day*144+slot+np.arange(n),self.supply['load'][b,:n]-self.supply['pv'][b,:n]
class Prices(q4.PriceModels):
 def fit(self,candidate,cutoff_day):
  ans=super().fit(candidate,cutoff_day);self.datasets.clear();return ans

def simulate(label,load,pv,margin,forecast,prices,base,actual,legacy=False):
 path=O/'strategies';planner=q4.Q43Planner(.9*base[0]);state=8592.693560925925
 q0=np.empty((334,144));versions=np.empty((334,4,144));execution=np.empty((334,144,12));stocks=np.empty((334,4));daily=[]
 for i,d in enumerate(range(31,365)):
  initial=state;order=np.zeros(144)
  for a,r in enumerate((0,36,72,108)):
   b=d*4+a;n=288-r;stocks[i,a]=state
   lh=load[d,r:] if legacy else load[b,:n]
   order[r:]=planner.solve(lh,pv[b,:n],state,margin[b,:n],r,None if a==0 else q0[i,r:],forecast[b,:n],dict(strategy=label,day=d,release_slot=r))[:144-r]
   if a==0:q0[i]=order
   versions[i,a]=order
   block,state=q4.execute_block(actual[d*144+r:d*144+r+36,0],actual[d*144+r:d*144+r+36,1],order[r:r+36],state)
   execution[i,r:r+36]=block
  energy=float(prices[d]@order);adjust=float(.5*prices[d]@abs(order-q0[i]));em=float(5*prices[d]@execution[i,:,8])
  daily.append(dict(date=q4.daystr(d),day=d,initial=initial,final=state,ordinary_cost=energy,adjustment_cost=adjust,ordinary_settlement_cost=energy+adjust,emergency_cost=em,total_cost=energy+adjust+em,order_kwh=float(order.sum()),emergency_kwh=float(execution[i,:,8].sum()),unused_order_kwh=float(execution[i,:,9].sum()),unused_pv_kwh=float(execution[i,:,10].sum())))
 df=pd.DataFrame(daily);df.to_csv(path/f'{label}.daily.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
 np.savez_compressed(path/f'{label}.npz',days=np.arange(31,365),q0=q0,versions=versions,execution=execution,decision_storage=stocks)
 out={k:float(df[k].sum()) for k in ['ordinary_cost','adjustment_cost','ordinary_settlement_cost','emergency_cost','total_cost','order_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh']}
 out.update(label=label,initial=8592.693560925925,final=state,days=334,emergency_days=int((df.emergency_kwh>1e-6).sum()),**q4.evaluate_prices(prices,forecast,'Q4-3'))
 dump(path/f'{label}.summary.json',out);budget.save();print(json.dumps(dict(completed=label,cost=out['total_cost'],emergency_cost=em if False else out['emergency_cost']),ensure_ascii=False),flush=True)
 return out

def main():
 if O.exists():raise FileExistsError('Isolated output already exists; inspect rather than overwrite')
 O.mkdir();(O/'strategies').mkdir();(O/'price_models').mkdir()
 protocol=read(R/'protocol.json')
 for rel,h in protocol['source_sha256'].items():assert sha(P/rel)==h,rel
 for mp in [UP/'outputs/protected_sources.json',P/'questions/Q3/runs/20260912-load-feedback-v1/outputs/protected_sources.json']:
  for rel,h in read(mp).items():assert sha(P/rel)==h,rel
 assert read(UP/'outputs/verification.json')['status']=='verified_by_AI_not_human_approval'
 prices,base,_=q4.load_prices_and_base();source=dict(np.load(OLD/'outputs/supply_inputs.npz'))
 oldfc=dict(np.load(OLD/'outputs/price_forecasts.npz'));forecast_old=oldfc['q43'][list(oldfc['candidates']).index('P2')]
 load=np.load(UP/'outputs/load_EW4.npz')['load'];pv=np.load(P/'questions/Q3/runs/20260912-final-information-v1/outputs/forecasts.npz')['full']
 np.testing.assert_allclose(pv,source['q3_pv'],atol=1e-12,rtol=0)
 np.savez_compressed(O/'supply.npz',load=load,pv=pv,actual=source['q3_actual'],price=prices,reference_price=base)
 baseline=simulate('OLD_P2_REPLAY',source['q3_load'],source['q3_pv'],source['q3_margin'],forecast_old,prices,base,source['q3_actual'],True)
 tr=np.load(O/'strategies/OLD_P2_REPLAY.npz');oldtr=np.load(DEP/'outputs/strategies/Q4-3-P2-full.npz')
 for k in ('q0','versions','execution'):np.testing.assert_allclose(tr[k],oldtr[k],atol=1e-7,rtol=0)
 oldsum=next(x for x in read(DEP/'outputs/summary.json')['results'] if x['branch']=='Q4-3' and x['strategy']=='P2-full')
 assert abs(baseline['total_cost']-oldsum['total_cost'])<1e-6
 print(json.dumps(dict(baseline_reproduced=True,cost=baseline['total_cost'])),flush=True)
 f=Features(prices,base,dict(load=load,pv=pv),'Q4-3');engine=Prices(f,'Q4-3');forecast=np.full((1460,288),np.nan)
 for d in range(31,365):
  for a,r in enumerate((0,36,72,108)):forecast[d*4+a,:288-r]=engine.predict('P2',d,r)
  if d%100==0:print(json.dumps(dict(price_forecast_day=d,fits=budget.price_fits)),flush=True)
 np.savez_compressed(O/'prices.npz',values=forecast)
 rows=[]
 for q in (60,40,50,70,80):
  margin=np.load(UP/f'outputs/strategies/EW4_Q{q}_full.margin.npz')['values']
  row=simulate(f'EW4_P2_Q{q}',load,pv,margin,forecast,prices,base,source['q3_actual']);row['quantile']=q/100;rows.append(row)
 winner=min(rows,key=lambda r:r['total_cost'])
 for rel,h in protocol['source_sha256'].items():assert sha(P/rel)==h,rel
 out=dict(status='computed_pending_independent_verification',baseline=baseline,candidates=rows,winner=winner,lp_calls=budget.lp_calls,price_fits=budget.price_fits,elapsed_seconds=time.perf_counter()-budget.start,code_sha256=sha(__file__),protocol_sha256=sha(R/'protocol.json'))
 dump(O/'summary.json',out);pd.DataFrame([baseline,*rows]).to_csv(O/'comparison.csv',index=False,encoding='utf-8-sig',float_format='%.17g');q4.logs.close()
 print(json.dumps(dict(all_completed=True,winner=winner['label'],cost=winner['total_cost'],saving=baseline['total_cost']-winner['total_cost'])),flush=True)
if __name__=='__main__':main()
