"""Rebuild numerical inputs from the included, value-preserving CSV exports."""
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def main():
 date=pd.Timestamp('2025-01-01');read=lambda n:pd.read_csv(ROOT/'data'/f'{n}.csv.gz',float_precision='round_trip')
 ref=read('day_reference');ref=ref.assign(t=ref.source_minute%1440).sort_values('t')
 a=read('actual_power');t=pd.to_datetime(a.source_date)+pd.to_timedelta(a.source_minute,unit='m')
 ix=((t-date).dt.total_seconds()/600).astype(int).to_numpy();assert np.array_equal(ix,np.arange(1,52561))
 actual=np.full((52561,2),np.nan);actual[ix]=a[['load_kw','pv_actual_kw']].to_numpy()
 f=read('pv_forecasts');release=np.arange(1460)*36;targets=release[:,None]+np.arange(1,25)[None,:]*6
 rr=((pd.to_datetime(f.release_datetime)-date).dt.total_seconds()/600).astype(int).to_numpy()
 tt=((pd.to_datetime(f.target_datetime)-date).dt.total_seconds()/600).astype(int).to_numpy()
 assert np.array_equal(rr,np.repeat(release,24)) and np.array_equal(tt,targets.ravel())
 p=read('actual_price');p['day']=(pd.to_datetime(p.source_date)-date).dt.days;p['slot']=p.source_minute.astype(int)%1440//10
 prices=p.pivot(index='day',columns='slot',values='price_yuan_per_kwh').reindex(index=range(365),columns=range(144)).to_numpy()
 data=dict(actual=actual,reference=ref[['load_kw','pv_forecast_kw']].to_numpy(),price=ref.price_yuan_per_kwh.to_numpy(),F=f.pv_forecast_kw.to_numpy().reshape(1460,24),release=release,targets=targets,actual_prices=prices)
 saved=np.load(ROOT/'data/inputs.npz')
 for k,v in data.items():np.testing.assert_array_equal(v,saved[k],err_msg=k)
 out=ROOT/'reproduced';out.mkdir(exist_ok=True);np.savez_compressed(out/'inputs.npz',**data)
 print('Prepared arrays match all saved inputs exactly.')
if __name__=='__main__':main()
