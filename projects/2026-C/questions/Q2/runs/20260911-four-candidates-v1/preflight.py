import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import numpy as np
from core import R,dump,execute,Planner
out=R/'preflight';assert not out.exists();out.mkdir()
price=np.ones(144);zero=np.zeros(144);checks={};cert=[]
def first(x):a=zero.copy();a[0]=x;return a
r,s=execute(zero,zero,first(100),10800,price)
assert r[0]['ordinary_cost']==100 and r[0]['unused_order_kwh']==100 and s==10800
checks['full_battery_unused_order_still_paid']=True
r,s=execute(first(600),zero,zero,1200,price)
assert r[0]['emergency_kwh']==100 and r[0]['emergency_cost']==500 and s==1200
checks['minimum_storage_emergency_at5p']=True
r,s=execute(zero,first(9000),first(300),10710,price)
assert abs(r[0]['pv_charge_kwh']-100)<1e-8 and r[0]['unused_order_kwh']==300 and s==10800
checks['capacity_limit_and_pv_priority']=True
r,s=execute(zero,first(9000),first(300),1200,price)
assert abs(r[0]['pv_charge_kwh']-5000/6)<1e-8 and r[0]['unused_order_kwh']==300
checks['charging_power_limit']=True
planner=Planner(price,lambda name,row:cert.append(row),lambda:None)
for name,L,V,S in [('no_energy',0,0,6000),('surplus_only',0,1000,6000),('constant_load_empty',2000,0,1200)]:
    q,x,y,z,s=planner.solve(np.full(288,L),np.full(288,V),S,np.zeros(288),{'case':name})
    if name=='no_energy':assert np.max(abs(q))<1e-6 and np.max(abs(s-6000))<1e-6
    elif name=='surplus_only':assert q.sum()<1e-6 and abs(s[-1]-10800)<1e-6 and abs(y.sum()-4800/.9)<1e-6
    else:assert np.max(abs(q-2000/6))<1e-6 and np.max(abs(s-1200))<1e-6
    checks[name]=True
dump(out/'checks.json',{'hand_cases':checks,'solver_checks':cert,'lp_calls':planner.calls,'new_training':0})
print(checks)
