"""Descriptive EDA of supplied labels; no forecasting, dispatch or energy integration."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / 'data'
SIGNALS = ['load_kw', 'pv_actual_kw', 'net_load_kw', 'price_yuan_per_kwh']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values):
    a = np.asarray(values, dtype=float)
    return dict(n=len(a), mean=float(a.mean()), std=float(a.std(ddof=1)),
                min=float(a.min()), p10=float(np.quantile(a,.1)),
                median=float(np.median(a)), p90=float(np.quantile(a,.9)),
                max=float(a.max()), zero_count=int((a==0).sum()))


def lagcorr(a, lag):
    a = np.asarray(a, dtype=float)
    return float(np.corrcoef(a[:-lag], a[lag:])[0,1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default='reproduced/eda')
    args = ap.parse_args()
    out = (PROJECT / args.output).resolve()
    if not out.is_relative_to(PROJECT) or out.exists():
        raise ValueError('Use a new output directory inside the project.')
    raw_hashes = json.loads((SOURCE/'raw_hashes.json').read_text(encoding='utf-8'))
    input_hashes = {f.name: sha(f) for f in SOURCE.iterdir() if f.is_file()}
    ref = pd.read_csv(SOURCE/'day_reference.csv.gz')
    actual = pd.read_csv(SOURCE/'actual_power.csv.gz', parse_dates=['source_date'])
    price = pd.read_csv(SOURCE/'actual_price.csv.gz', parse_dates=['source_date'])
    forecast = pd.read_csv(SOURCE/'pv_forecasts.csv.gz', parse_dates=['release_datetime','target_datetime'])
    keys = ['source_date','source_minute']
    data = actual.merge(price[keys+['price_yuan_per_kwh']],on=keys,validate='one_to_one')
    data = data.sort_values(keys).reset_index(drop=True)
    assert len(data)==52560 and len(ref)==144 and len(forecast)==35040
    assert data.groupby('source_date').size().eq(144).all()
    data['timestamp'] = data.source_date + pd.to_timedelta(data.source_minute, unit='min')
    assert data.timestamp.diff().dropna().eq(pd.Timedelta(minutes=10)).all()
    data['month'] = data.source_date.dt.month
    data['weekday'] = data.source_date.dt.dayofweek
    data['net_load_kw'] = data.load_kw - data.pv_actual_kw
    data['pv_exceeds_load'] = data.net_load_kw < 0
    ref['net_load_kw'] = ref.load_kw-ref.pv_forecast_kw
    out.mkdir(parents=True)
    ref.to_csv(out/'reference_profile.csv',index=False)
    data[keys+['month','weekday']+SIGNALS].to_csv(out/'time_series.csv',index=False)
    daily = data.groupby('source_date')[SIGNALS].mean()
    daily['pv_exceeds_load_fraction'] = data.groupby('source_date').pv_exceeds_load.mean()
    daily['peak_net_load_kw'] = data.groupby('source_date').net_load_kw.max()
    daily['minimum_net_load_kw'] = data.groupby('source_date').net_load_kw.min()
    daily.to_csv(out/'daily_summary.csv')
    monthly = data.groupby('month')[SIGNALS].mean()
    monthly['days'] = data.groupby('month').source_date.nunique()
    monthly['pv_exceeds_load_fraction'] = data.groupby('month').pv_exceeds_load.mean()
    monthly.to_csv(out/'monthly_summary.csv')
    profile = data.groupby('source_minute')[SIGNALS].agg(['mean',lambda s:s.quantile(.1),lambda s:s.quantile(.9)])
    profile.columns = [f'{c}_{["mean","p10","p90"][i%3]}' for i,(c,_) in enumerate(profile.columns)]
    profile.to_csv(out/'intraday_summary.csv')
    mp = data.groupby(['month','source_minute'])[SIGNALS].mean()
    mp.to_csv(out/'month_intraday.csv')
    weekdays = data.groupby('weekday')[SIGNALS].mean()
    weekdays['days'] = data.groupby('weekday').source_date.nunique()
    weekdays.to_csv(out/'weekday_summary.csv')
    lag_rows = []
    summary_lags = {}
    for col in SIGNALS:
        # Subtract source-month x time-label mean only for retrospective diagnostics.
        residue = data[col]-data.groupby(['month','source_minute'])[col].transform('mean')
        summary_lags[col] = {str(h): {'raw':lagcorr(data[col],int(h*6)), 'month_time_residual':lagcorr(residue,int(h*6))} for h in [1,12,24,48,144,168,192,336]}
        for h in range(1,337):
            lag_rows.append(dict(signal=col,lag_hours=h,raw_correlation=lagcorr(data[col],h*6),residual_correlation=lagcorr(residue,h*6)))
    pd.DataFrame(lag_rows).to_csv(out/'lag_correlations.csv',index=False)
    matched = forecast.merge(data[['timestamp','pv_actual_kw']],left_on='target_datetime',right_on='timestamp',how='left',validate='many_to_one')
    assert matched.pv_actual_kw.isna().sum()==36
    matched['error_kw'] = matched.pv_forecast_kw-matched.pv_actual_kw
    matched['abs_error_kw'] = matched.error_kw.abs()
    matched['target_hour'] = matched.target_datetime.dt.hour
    matched['release_hour'] = matched.release_datetime.dt.hour
    valid = matched.dropna(subset=['pv_actual_kw']).copy()
    metrics=[]
    for name, frame in [('all',valid),('actual_positive',valid[valid.pv_actual_kw>0])]:
        for h,g in frame.groupby('lead_hours'):
            metrics.append(dict(scope=name,lead_hours=int(h),n=len(g),mae_kw=float(g.abs_error_kw.mean()),bias_kw=float(g.error_kw.mean()),rmse_kw=float(np.sqrt((g.error_kw**2).mean()))))
    pd.DataFrame(metrics).to_csv(out/'forecast_error_by_lead.csv',index=False)
    matched[['release_datetime','target_datetime','lead_hours','pv_forecast_kw','pv_actual_kw','error_kw','abs_error_kw','target_hour','release_hour']].to_csv(out/'forecast_matched.csv',index=False)
    # For each original midnight forecast targeting this day's h=7..24,
    # compare the original and the latest later published forecast strictly before target.
    initial = valid[(valid.release_hour==0)&(valid.lead_hours>=7)].copy()
    pairs=[]
    for r in initial.itertuples():
        pool=valid[(valid.target_datetime==r.target_datetime)&(valid.release_datetime>r.release_datetime)&(valid.release_datetime<r.target_datetime)]
        if pool.empty:
            continue
        new=pool.sort_values('release_datetime').iloc[-1]
        pairs.append(dict(target_datetime=r.target_datetime,actual_kw=r.pv_actual_kw,
                          initial_lead=r.lead_hours,latest_lead=int(new.lead_hours),
                          initial_forecast_kw=r.pv_forecast_kw,latest_forecast_kw=float(new.pv_forecast_kw),
                          initial_abs_error_kw=r.abs_error_kw,latest_abs_error_kw=float(new.abs_error_kw)))
    pairs=pd.DataFrame(pairs)
    pairs.to_csv(out/'forecast_same_target_pairs.csv',index=False)
    paired_stats={}
    for name,g in [('all',pairs),('actual_positive',pairs[pairs.actual_kw>0])]:
        diff=g.latest_abs_error_kw-g.initial_abs_error_kw
        paired_stats[name]=dict(n=len(g),initial_mae_kw=float(g.initial_abs_error_kw.mean()),latest_mae_kw=float(g.latest_abs_error_kw.mean()),improved_fraction=float((diff<0).mean()),worse_fraction=float((diff>0).mean()),tie_fraction=float((diff==0).mean()))
    def extreme_row(frame,col,which):
        r=frame.loc[getattr(frame[col],'idx'+which)()]
        return {'value':float(r[col]),'source_date':str(r.get('source_date','representative')),'source_minute':int(r.source_minute)}
    shapes={}
    for col in SIGNALS:
        matrix=data.pivot(index='source_date',columns='source_minute',values=col).to_numpy()
        corrs=np.array([np.corrcoef(matrix[i],matrix[i+1])[0,1] for i in range(364)])
        shapes[col]=stats(corrs)
    refstats={col:stats(ref[col]) for col in ['load_kw','pv_forecast_kw','net_load_kw','price_yuan_per_kwh']}
    refstats['positive_pv_labels'] = ref.loc[ref.pv_forecast_kw>0,'source_minute'].tolist()
    refstats['surplus_labels'] = ref.loc[ref.net_load_kw<0,'source_minute'].tolist()
    refstats['extrema']={col:{w:extreme_row(ref,col,w) for w in ['min','max']} for col in ['load_kw','pv_forecast_kw','net_load_kw','price_yuan_per_kwh']}
    price_spread=data.groupby('source_date').price_yuan_per_kwh.agg(['min','max'])
    price_spread['ratio']=price_spread['max']/price_spread['min']
    summary=dict(version='EDA-v1',scope='retrospective_descriptive_only',python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,script_sha256=sha(Path(__file__)),input_sha256=input_hashes,raw_sha256=raw_hashes,
                 reference=refstats,annual={c:stats(data[c]) for c in SIGNALS},
                 january_only={c:stats(data.loc[data.month==1,c]) for c in SIGNALS},
                 monthly=monthly.reset_index().to_dict('records'),lag_correlations=summary_lags,adjacent_day_shape_correlation=shapes,
                 annual_extrema={c:{w:extreme_row(data,c,w) for w in ['min','max']} for c in SIGNALS},
                 surplus=dict(sample_fraction=float(data.pv_exceeds_load.mean()),days_with_surplus=int((daily.pv_exceeds_load_fraction>0).sum()),max_surplus_kw=float(-data.net_load_kw.min())),
                 price_daily_max_min_ratio=stats(price_spread.ratio),forecast=dict(total=len(forecast),matched=len(valid),unmatched=36,actual_positive_count=int((valid.pv_actual_kw>0).sum()),mae_all_kw=float(valid.abs_error_kw.mean()),mae_actual_positive_kw=float(valid.loc[valid.pv_actual_kw>0,'abs_error_kw'].mean()),same_target=paired_stats),
                 caveats=['Source-label arithmetic means are not kWh or final interval semantics.','One year supports seasonal differences, not verified interannual periodicity.','Full-year diagnostics are hindsight; no future information is authorized for decisions.','Forecast metrics are at exact hourly target labels with no interpolation; economic value is not measured.','Month x time residuals are retrospective centering, not a trained forecasting model.'])
    assert input_hashes=={f.name:sha(f) for f in SOURCE.iterdir() if f.is_file()}
    # Raw file identifiers are retained; supplied CSV inputs are rechecked above.
    summary['source_unchanged']=True
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'monthly':summary['monthly'],'surplus':summary['surplus'],'forecast':summary['forecast'],'lags':summary_lags},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
