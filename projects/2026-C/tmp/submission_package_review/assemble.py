from pathlib import Path
import ast,json,shutil,hashlib,gzip
import numpy as np
P=Path(__file__).resolve().parents[2];D=P/'支撑材料';D.mkdir(exist_ok=True)
for f in ['code','data','results','evidence','templates']:(D/f).mkdir(exist_ok=True)
mapping=[]
def write(name,s):(D/name).write_text(s,encoding='utf-8')
def extract(rel,names):
 s=(P/rel).read_text('utf-8-sig');tree=ast.parse(s);out=[]
 for node in tree.body:
  if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:
   text=ast.get_source_segment(s,node);out.append(text)
   mapping.append(dict(file=rel,symbol=node.name,sha256=hashlib.sha256(text.encode()).hexdigest()))
 missing=set(names)-{n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
 assert not missing,missing
 return '\n\n'.join(out)+'\n'
imports='''from pathlib import Path
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
'''
q1='questions/Q1/runs/20260911-compare-v1/compare.py'
write('code/q1.py',imports+extract(q1,['arrays','terminal_bands','rule','solve_lp','schedule','metrics']))
q2='questions/Q2/runs/20260911-annual-validation-v1/core.py'
text=extract(q2,['Data','Forecasts','Planner','execute','metrics'])
tree=ast.parse(text);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Data');init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
lines=text.splitlines();lines[init.lineno-1:init.end_lineno]=['    def __init__(self,source):','        self.a={"load":source["actual"][:N,0].reshape(365,144),"pv":source["actual"][:N,1].reshape(365,144)}','        self.ref={"load":source["reference"][:,0],"pv":source["reference"][:,1]}','        self.price=source["price"]']
write('code/q2.py',imports+'\n'.join(lines)+'\n\n'+extract('questions/Q2/runs/20260911-annual-validation-v1/annual.py',['Risk']))
q3='questions/Q3/runs/20260911-four-candidates-v1/core.py'
write('code/q3_base.py',imports+extract(q3,['history_and_features','build_fusion','to_intervals','Planner','execute_block']))
text=extract('questions/Q3/runs/20260911-s2-deepening-v1/deepen.py',['Planner','exact_quantile'])
write('code/q3.py',imports+'import q3_base as base\n'+text+extract('questions/Q3/runs/20260912-load-feedback-v1/run.py',['make_load','errors_for'])+extract('questions/Q3/runs/20260912-forecast-risk-v1/run.py',['midnight','group_index','quantile']))
q4='questions/Q4/runs/20260912-three-candidates-v1/run_compare.py'
write('code/q4.py',imports+extract(q4,['Q2Risk','PriceFeatures','PriceModels','Q42Planner','Q43Planner','execute_block']))
write('code/q4_tree.py',imports+'import q4\n'+extract('questions/Q4/runs/20260912-selected-deepening-v1/run_deepening.py',['ForecastEngine']))
write('code/q4_update.py',imports+'import q4\n'+extract('questions/Q4/runs/20260913-q3-transfer-v1/run.py',['Features','Prices']))
src=np.load(P/'questions/Q3/runs/20260911-four-candidates-v1/outputs/sources.npz')
z=dict(src);z['actual_prices']=np.load(P/'questions/Q4/runs/20260913-q3-transfer-v1/outputs/supply.npz')['price']
np.savez_compressed(D/'data/inputs.npz',**z)
cfg=json.loads((P/'questions/Q1/runs/20260911-compare-v1/protocol.json').read_text('utf-8'))
cfg={k:v for k,v in cfg.items() if k in ['dt_hours','initial_kwh','terminal_kwh','min_kwh','max_kwh','external_charge_kw','external_discharge_kw','eta_charge','eta_discharge','lp_time_limit_seconds','lp_feasibility_tolerance','low_quantiles','high_quantiles','target_fractions_of_usable_capacity']}
write('data/q1_config.json',json.dumps(cfg,indent=2))
shutil.copy2(P/'questions/Q1/runs/20260911-compare-v1/outputs/schedules/C04.csv',D/'results/Q1.csv')
z=np.load(P/'questions/Q2/runs/20260911-annual-validation-v1/refinement/schedules/sensitivity-error-decay70.npz');a=z['actual'];c=list(z['actual_columns'])
cols=['storage_start_kwh','storage_end_kwh','received_kwh','grid_to_load_kwh','direct_pv_kwh','grid_charge_kwh','pv_charge_kwh','discharge_kwh','emergency_kwh','unused_order_kwh','unused_pv_kwh']
execution=np.stack([*[a[:,:,c.index(k)] for k in cols],a[:,:,c.index('load_kw')]/6],axis=-1)
np.savez_compressed(D/'results/Q2.npz',days=z['days'],order=a[:,:,c.index('order_kwh')],execution=execution)
for name,rel in [('Q3','Q3/runs/20260912-forecast-risk-v1/outputs/strategies/EW4_Q60_full.npz'),('Q4-2','Q4/runs/20260912-selected-deepening-v1/outputs/strategies/Q4-2-P3-leaves31.npz'),('Q4-3','Q4/runs/20260913-q3-transfer-v1/outputs/strategies/EW4_P2_Q60.npz')]:shutil.copy2(P/'questions'/rel,D/'results'/f'{name}.npz')
for path in (P/'data/raw/C题/附件/附件5').glob('*.xlsx'):shutil.copy2(path,D/'templates'/path.name)
for n in ['actual_power.csv','actual_price.csv','pv_forecasts.csv','day_reference.csv']:
 with gzip.open(D/'data'/f'{n}.gz','wb') as f:f.write((P/'data/prepared-v1'/n).read_bytes())
# Original numerical preparation logic retained, with a portable root.
text=(P/'scripts/prepare_source_tables.py').read_text('utf-8-sig')
print('preprocessing header',text[:420])
write('code/source_map.json',json.dumps(mapping,ensure_ascii=False,indent=2))
print('created',D,'bytes',sum(p.stat().st_size for p in D.rglob('*') if p.is_file()))
