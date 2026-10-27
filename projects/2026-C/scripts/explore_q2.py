"""Q2 exploration from local sources only; fixed history diagnostics, no fitting/dispatch."""
from pathlib import Path
import argparse, hashlib, json, platform, sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd

P=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def csv(p,x):x.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.17g')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='audit/q2-exploration-v1/outputs');a=parser.parse_args()
    out=(P/a.output).resolve();assert out.is_relative_to(P) and not out.exists()
    manifest=json.loads((P/'data/prepared-v1/manifest.json').read_text(encoding='utf-8'))
    sources=[P/'data/prepared-v1/actual_power.csv',P/'data/prepared-v1/day_reference.csv']
    for f in sources:assert sha(f)==manifest['outputs'][f.name]['sha256']
    for rel in ['data/raw/C题/附件/附件1.xlsx','data/raw/C题/附件/附件2.xlsx']:
        assert sha(P/rel)==manifest['raw_sha256'][rel]
    protected=sources+[P/'data/raw/C题/附件/附件1.xlsx',P/'data/raw/C题/附件/附件2.xlsx',
        P/'questions/Q1/runs/20260911-compare-v1/outputs/schedules/C04.csv',
        P/'questions/Q1/runs/20260911-close-v1/deliverables/result1.xlsx',
        P/'paper/q1_manuscript_v1/问题一论文草稿.pdf']
    before={str(f.relative_to(P)):sha(f) for f in protected}
    df=pd.read_csv(sources[0],float_precision='round_trip')
    ref=pd.read_csv(sources[1],float_precision='round_trip')
    df['interval_start']=pd.to_datetime(df.source_date)+pd.to_timedelta(df.source_minute,unit='m')
    df['interval_end']=df.interval_start+pd.Timedelta(minutes=10)
    assert len(df)==52560 and df.interval_start.is_unique
    assert (df.interval_start.diff().dropna()==pd.Timedelta(minutes=10)).all()
    assert np.isfinite(df[['load_kw','pv_actual_kw']]).all().all()
    assert (df[['load_kw','pv_actual_kw']]>=0).all().all()
    df['date']=df.interval_start.dt.normalize();df['minute']=df.interval_start.dt.hour*60+df.interval_start.dt.minute
    df['weekday']=df.interval_start.dt.dayofweek;df['month']=df.interval_start.dt.month
    prices=dict(zip(ref.source_minute%1440,ref.price_yuan_per_kwh))
    assert len(prices)==144
    df['fixed_price']=df.minute.map(prices)
    df['load_kwh']=df.load_kw/6;df['pv_kwh']=df.pv_actual_kw/6
    df['direct_pv_kwh']=np.minimum(df.load_kw,df.pv_actual_kw)/6
    df['net_kw']=df.load_kw-df.pv_actual_kw
    df['positive_net_kwh']=df.net_kw.clip(lower=0)/6
    df['surplus_kwh']=(-df.net_kw).clip(lower=0)/6
    df['power_spill_lower_bound_kwh']=(-df.net_kw-5000).clip(lower=0)/6
    df['grid_required_by_power_kwh']=(df.net_kw-5000).clip(lower=0)/6
    counts=df.groupby('date').size()
    complete_dates=counts[counts==144].index
    all_complete=df[df.date.isin(complete_dates)].copy()
    assert len(complete_dates)==364 and complete_dates[0]==pd.Timestamp('2025-01-02')
    target=all_complete[all_complete.date>=pd.Timestamp('2025-02-01')].copy()
    assert len(target)==334*144
    out.mkdir(parents=True)
    csv(out/'intervals.csv',df)
    cols=['load_kwh','pv_kwh','direct_pv_kwh','positive_net_kwh','surplus_kwh','power_spill_lower_bound_kwh','grid_required_by_power_kwh']
    daily=all_complete.groupby('date')[cols].sum().reset_index()
    daily['month']=daily.date.dt.month;daily['weekday']=daily.date.dt.dayofweek
    daily['has_pv_surplus']=daily.surplus_kwh>1e-10
    daily['surplus_exceeds_one_fill']=daily.surplus_kwh>9600/.9
    monthly=daily.groupby('month')[cols].mean().add_prefix('daily_mean_').reset_index()
    monthly['days']=daily.groupby('month').size().values
    monthly['pv_to_load_ratio']=monthly.daily_mean_pv_kwh/monthly.daily_mean_load_kwh
    weekday=daily.groupby('weekday')[cols].mean().add_prefix('daily_mean_').reset_index()
    weekday['days']=daily.groupby('weekday').size().values
    daily['load_minus_month_mean']=daily.load_kwh-daily.groupby('month').load_kwh.transform('mean')
    weekday['load_minus_month_mean_kwh']=daily.groupby('weekday').load_minus_month_mean.mean().values
    weekday['surplus_day_fraction']=daily.groupby('weekday').has_pv_surplus.mean().values
    csv(out/'daily.csv',daily);csv(out/'monthly.csv',monthly);csv(out/'weekday.csv',weekday)
    curves=all_complete.groupby(['weekday','minute'])[['load_kw','pv_actual_kw','net_kw']].mean().reset_index()
    csv(out/'weekday_curves.csv',curves)
    monthcurves=all_complete.groupby(['month','minute'])[['load_kw','pv_actual_kw','net_kw']].mean().reset_index()
    csv(out/'month_curves.csv',monthcurves)
    lags=[]
    for variable in ['load_kw','pv_actual_kw']:
        detrended=all_complete[variable]-all_complete.groupby(['month','minute'])[variable].transform('mean')
        for lag in [1,7,14,28]:
            step=lag*144
            lags.append(dict(variable=variable,lag_days=lag,
                raw_corr=float(all_complete[variable].iloc[step:].corr(all_complete[variable].shift(step).iloc[step:])),
                month_slot_demeaned_corr=float(detrended.iloc[step:].corr(detrended.shift(step).iloc[step:]))))
    csv(out/'lag_correlations.csv',pd.DataFrame(lags))
    daily_lags={c:{str(lag):float(daily[c].corr(daily[c].shift(lag))) for lag in [1,7]} for c in ['load_kwh','pv_kwh']}

    # Seven predeclared references, no parameter estimation or selection.
    L=all_complete.pivot(index='date',columns='minute',values='load_kw')
    V=all_complete.pivot(index='date',columns='minute',values='pv_actual_kw')
    dates=L.index[L.index>=pd.Timestamp('2025-02-01')]
    assert L.shape==(364,144) and V.shape==L.shape
    names=['lag1','lag7','mean3','mean7','mean14','mean28','weekday4']
    def forecasts(x):
        f={'lag1':x.shift(1),'lag7':x.shift(7)}
        for n in [3,7,14,28]:f['mean'+str(n)]=x.shift(1).rolling(n,min_periods=n).mean()
        f['weekday4']=sum(x.shift(n) for n in [7,14,21,28])/4
        return {k:y.loc[dates].to_numpy() for k,y in f.items()}
    forecasts_by_var={'load':forecasts(L),'pv':forecasts(V)}
    truths={'load':L.loc[dates].to_numpy(),'pv':V.loc[dates].to_numpy()}
    metricrows=[];byday=[]
    ranges={'Feb-Dec':np.ones(len(dates),dtype=bool),'Feb-Jun':dates.month<=6,'Jul-Dec':dates.month>=7}
    ranges.update({f'month-{m:02d}':dates.month==m for m in range(2,13)})
    for variable,methods in forecasts_by_var.items():
        actual=truths[variable]
        for method,pred in methods.items():
            assert np.isfinite(pred).all()
            error=actual-pred
            for span,mask in ranges.items():
                obs=actual[mask];er=error[mask];active=obs>0
                metricrows.append(dict(variable=variable,method=method,span=span,days=int(mask.sum()),samples=int(obs.size),
                    mae_kw=float(np.abs(er).mean()),rmse_kw=float(np.sqrt(np.square(er).mean())),bias_kw=float(er.mean()),
                    wape=float(np.abs(er).sum()/np.abs(obs).sum()),
                    positive_actual_mae_kw=float(np.abs(er[active]).mean()),positive_actual_samples=int(active.sum())))
            for i,day in enumerate(dates):
                byday.append(dict(date=day,variable=variable,method=method,mae_kw=float(np.abs(error[i]).mean()),bias_kw=float(error[i].mean())))
    csv(out/'history_reference_metrics.csv',pd.DataFrame(metricrows));csv(out/'history_reference_daily.csv',pd.DataFrame(byday))
    # Save all reference predictions, so the diagnostic itself is auditable.
    actual_eval=target[['interval_start','interval_end','date','minute','load_kw','pv_actual_kw','net_kw']].copy()
    assert actual_eval.date.to_numpy()[::144].tolist()==dates.to_numpy().tolist()
    for variable,methods in forecasts_by_var.items():
        for method,arr in methods.items():actual_eval[variable+'_'+method]=arr.ravel()
    csv(out/'fixed_history_references.csv',actual_eval)
    available=[]
    for day in dates:
        for method in names:
            offsets={'lag1':[1],'lag7':[7],'weekday4':[7,14,21,28]}.get(method)
            if offsets is None:offsets=list(range(1,int(method[4:])+1))
            earliest=day-pd.Timedelta(days=max(offsets))
            latest_start=day-pd.Timedelta(days=min(offsets))+pd.Timedelta(hours=23,minutes=50)
            latest_end=latest_start+pd.Timedelta(minutes=10)
            assert latest_end<=day and earliest>=pd.Timestamp('2025-01-02')
            available.append(dict(decision_time=day,method=method,history_first_interval=earliest,history_last_interval=latest_start,history_available_by=latest_end))
    csv(out/'reference_information_audit.csv',pd.DataFrame(available))
    net=truths['load']-truths['pv'];errsummary={};autocorr=[];cumulative=[];errframe=actual_eval.iloc[:,:7].copy()
    for label,lmethod in [('week1_pv7','lag7'),('week4_pv7','weekday4')]:
        le=truths['load']-forecasts_by_var['load'][lmethod]
        ve=truths['pv']-forecasts_by_var['pv']['mean7']
        er=le-ve;errframe[label+'_error_kw']=er.ravel()
        errframe[label+'_reference_net_kw']=(net-er).ravel()
        erstats=dict(mae_kw=float(np.abs(er).mean()),bias_kw=float(er.mean()),
            load_pv_error_corr=float(np.corrcoef(le.ravel(),ve.ravel())[0,1]),cumulative={})
        for lag in [1,3,6,12,18,36]:
            correlation=float(np.corrcoef(er[:,lag:].ravel(),er[:,:-lag].ravel())[0,1])
            autocorr.append(dict(pair=label,lag_minutes=10*lag,correlation=correlation))
        cs=np.c_[np.zeros(len(dates)),np.cumsum(er/6,axis=1)]
        for length in [6,18,36]:
            windows=cs[:,length:]-cs[:,:-length]
            erstats['cumulative'][str(length//6)+'h']=dict(count=int(windows.size),
                q50_kwh=float(np.quantile(windows,.5)),q90_kwh=float(np.quantile(windows,.9)),q95_kwh=float(np.quantile(windows,.95)),
                q99_kwh=float(np.quantile(windows,.99)),max_kwh=float(windows.max()),min_kwh=float(windows.min()))
            if length==36:
                for i,day in enumerate(dates):
                    for start,value in enumerate(windows[i]):
                        cumulative.append(dict(pair=label,date=day,start_minute=start*10,hours=6,signed_error_kwh=float(value)))
        errsummary[label]=erstats
    csv(out/'net_reference_errors.csv',errframe)
    csv(out/'error_autocorrelation.csv',pd.DataFrame(autocorr))
    csv(out/'six_hour_error_windows.csv',pd.DataFrame(cumulative))
    requested=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
    csv(out/'specified_days.csv',errframe[errframe.date.isin(pd.to_datetime(requested))])
    def totals(x):
        d=x.groupby('date')[cols].sum()
        return dict(days=int(len(d)),intervals=int(len(x)),**{c:float(x[c].sum()) for c in cols},
            pv_to_load_ratio=float(x.pv_kwh.sum()/x.load_kwh.sum()),direct_load_fraction=float(x.direct_pv_kwh.sum()/x.load_kwh.sum()),
            surplus_intervals=int((x.surplus_kwh>0).sum()),surplus_days=int((d.surplus_kwh>0).sum()),
            days_surplus_above_one_fill=int((d.surplus_kwh>9600/.9).sum()),
            surplus_above_charge_limit_intervals=int((x.net_kw< -5000).sum()),
            net_above_discharge_limit_intervals=int((x.net_kw>5000).sum()),
            max_surplus_kw=float(-x.net_kw.min()),max_net_kw=float(x.net_kw.max()),
            min_load_kw=float(x.load_kw.min()),max_load_kw=float(x.load_kw.max()),max_pv_kw=float(x.pv_actual_kw.max()))
    summary=dict(version='Q2-exploration-v1',created_utc=datetime.now(timezone.utc).isoformat(),
        scope='Independently computed local Q2 EDA and fixed-history diagnostic; no optimization, fitted model, or selection',
        time=dict(first_start=str(df.interval_start.min()),last_start=str(df.interval_start.max()),
            raw_records=len(df),missing_start='2025-01-01 00:00',first_partial_day_intervals=int(counts.iloc[0]),
            excluded_nextyear_intervals=int((df.date.dt.year>2025).sum()),complete_days=len(complete_dates)),
        submission_period=totals(target),complete_day_description=totals(all_complete),daily_lags=daily_lags,
        reference_errors=errsummary,
        storage=dict(min_kwh=1200,max_kwh=10800,usable_internal_kwh=9600,one_fill_external_kwh=9600/.9,
            usable_load_side_full_kwh=9600*.9,usable_load_side_initial6000_kwh=(6000-1200)*.9,
            full_discharge_at5000_hours=9600*.9/5000,eta_charge=.9,eta_discharge=.9),
        information_audit=dict(reference_records=len(available),max_history_available_after_decision=False,
            annex3_used=False,annex4_used=False,teammate_computed_data_or_figures_used=False),
        limitations=['Whole-year exploratory diagnostics; no untouched holdout claim',
            'No real controller/orders/SOC path: surplus is not spill and reference error is not emergency power',
            'Overlapping error windows not independent; full-year quantiles cannot be used at past decisions',
            'Jan1 first slot remains missing; no simulation initialization choice made'],
        environment=dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__,platform=platform.platform()),
        source_sha256=before,script_sha256=sha(__file__),protocol_sha256=sha(P/'audit/q2-exploration-v1/protocol.json'))
    assert all(sha(P/k)==v for k,v in before.items())
    dump(out/'summary.json',summary)
    dump(out/'output_hashes.json',{f.name:sha(f) for f in sorted(out.iterdir()) if f.is_file()})
    print(json.dumps({k:summary[k] for k in ['time','submission_period','daily_lags','reference_errors']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
