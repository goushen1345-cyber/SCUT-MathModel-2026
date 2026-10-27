"""Reproduce the existing paper comparisons; choose one setting per invocation."""
import argparse,itertools,json
import numpy as np
import pandas as pd
import reproduce as r
from threadpoolctl import threadpool_limits
def main():
 p=argparse.ArgumentParser();p.add_argument('question',choices=['Q1','Q2','Q3']);p.add_argument('--quantile',type=float);p.add_argument('--decay',type=float,default=.7);p.add_argument('--family',choices=['W1','W2','W4','EW4'],default='EW4');p.add_argument('--information',choices=['full','no_new','zero_only'],default='full');p.add_argument('--days',type=int,default=334);a=p.parse_args()
 assert 1<=a.days<=334
 if a.question=='Q1':
  cfg=json.loads((r.ROOT/'data/q1_config.json').read_text());inputs=pd.read_csv(r.ROOT/'results/Q1.csv',float_precision='round_trip')[['k','start_minute','end_minute','load_kw','pv_kw','price']].to_dict('records');rows=[]
  for reserve in [False,True]:
   for low,high,target in itertools.product(cfg['low_quantiles'],cfg['high_quantiles'],cfg['target_fractions_of_usable_capacity']):
    actions,_=r.q1.rule(inputs,cfg,low,high,target,reserve)
    rows.append(dict(reserve=reserve,low=low,high=high,target=target,**r.q1.metrics(r.q1.schedule(inputs,cfg,actions))))
  for initial in [1200,6000,10800]:
   cfg.update(initial_kwh=initial,terminal_kwh=initial);actions,_=r.q1.solve_lp(inputs,cfg);rows.append(dict(initial=initial,**r.q1.metrics(r.q1.schedule(inputs,cfg,actions))))
  pd.DataFrame(rows).to_csv(r.OUT/'Q1_comparisons.csv',index=False);print('Q1: 54 rule settings and three initial-storage settings reproduced.');return
 initial=r.january(r.q2.Data(r.SRC),r.question1())
 if a.question=='Q2':z=r.question2(r.q2.Data(r.SRC),initial,31+a.days,a.quantile if a.quantile is not None else .7,a.decay)
 else:
  supply=r.supply3(a.family,a.quantile if a.quantile is not None else .6,'no_new' if a.information=='no_new' else 'full')
  z=r.question3(initial,31+a.days,supply,a.information=='zero_only')
 ex=z['execution'];order=z['order'] if 'order' in z else z['versions'][:,-1];zero=z.get('q0',order);price=r.SRC['price']
 normal=float((order*price).sum());adjust=float((.5*price*abs(order-zero)).sum());emergency=float((5*price*ex[:,:,8]).sum())
 print(json.dumps(dict(settings=vars(a),normal_cost=normal,adjustment_cost=adjust,emergency_cost=emergency,total_cost=normal+adjust+emergency,emergency_kwh=float(ex[:,:,8].sum())),ensure_ascii=False,indent=2))
if __name__=='__main__':
 with threadpool_limits(limits=1):main()
