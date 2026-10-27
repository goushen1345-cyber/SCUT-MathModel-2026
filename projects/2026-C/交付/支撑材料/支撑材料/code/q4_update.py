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
import q4
class Features(q4.PriceFeatures):
 def supply_forecast(self,day,slot):
  b=day*4+slot//36;n=288-slot
  return day*144+slot+np.arange(n),self.supply['load'][b,:n]-self.supply['pv'][b,:n]

class Prices(q4.PriceModels):
 def fit(self,candidate,cutoff_day):
  ans=super().fit(candidate,cutoff_day);self.datasets.clear();return ans
