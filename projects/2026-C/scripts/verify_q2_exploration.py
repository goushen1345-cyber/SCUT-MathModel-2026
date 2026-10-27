"""Independent raw-cell/accounting and historical-reference verification; no fit/solver."""
from pathlib import Path
from datetime import datetime,timedelta
from decimal import Decimal as D
import csv,json,hashlib,zipfile,xml.etree.ElementTree as ET,math,statistics
P=Path(__file__).resolve().parents[1];O=P/'audit/q2-exploration-v1/outputs'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
summary=json.loads((O/'summary.json').read_text(encoding='utf-8'))
assert all(sha(P/k)==v for k,v in summary['source_sha256'].items())
assert all(sha(O/k)==v for k,v in json.loads((O/'output_hashes.json').read_text(encoding='utf-8')).items())
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(P/'data/raw/C题/附件/附件2.xlsx') as z:
    cells=[]
    for i in [1,2]:
        t=ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml'))
        cells.append({c.get('r'):c.find('s:v',ns).text for c in t.findall('.//s:c',ns) if c.find('s:v',ns) is not None})
rawrows=list(csv.DictReader((P/'data/prepared-v1/actual_power.csv').open(encoding='utf-8-sig')))
derived=list(csv.DictReader((O/'intervals.csv').open(encoding='utf-8-sig')))
tot={k:D(0) for k in ['load_kwh','pv_kwh','direct_pv_kwh','positive_net_kwh','surplus_kwh','power_spill_lower_bound_kwh','grid_required_by_power_kwh']}
lookup={};cnt=0;pvpressure=0;netpressure=0
for r,s in zip(rawrows,derived):
    lv=cells[0][r['load_value_cell']];pv=cells[1][r['pv_value_cell']]
    assert float(lv)==float(r['load_kw'])==float(s['load_kw'])
    assert float(pv)==float(r['pv_actual_kw'])==float(s['pv_actual_kw'])
    dt=datetime.fromisoformat(r['source_date'])+timedelta(minutes=int(r['source_minute']))
    assert datetime.fromisoformat(s['interval_start'])==dt
    assert datetime.fromisoformat(s['interval_end'])==dt+timedelta(minutes=10)
    lookup[dt]=(float(lv),float(pv))
    if datetime(2025,2,1)<=dt<datetime(2026,1,1):
        l=D(lv);v=D(pv);cnt+=1
        values={'load_kwh':l/6,'pv_kwh':v/6,'direct_pv_kwh':min(l,v)/6,
          'positive_net_kwh':max(l-v,D(0))/6,'surplus_kwh':max(v-l,D(0))/6,
          'power_spill_lower_bound_kwh':max(v-l-5000,D(0))/6,'grid_required_by_power_kwh':max(l-v-5000,D(0))/6}
        for k,val in values.items():tot[k]+=val
        pvpressure+=v-l>5000;netpressure+=l-v>5000
assert cnt==48096 and pvpressure==241 and netpressure==3013
assert all(abs(v-D(str(summary['submission_period'][k])))<D('1e-6') for k,v in tot.items())
assert abs(tot['load_kwh']-tot['direct_pv_kwh']-tot['positive_net_kwh'])<D('1e-16')
assert abs(tot['pv_kwh']-tot['direct_pv_kwh']-tot['surplus_kwh'])<D('1e-16')
predrows=list(csv.DictReader((O/'fixed_history_references.csv').open(encoding='utf-8-sig')))
methods={'lag1':[1],'lag7':[7],'mean3':list(range(1,4)),'mean7':list(range(1,8)),
         'mean14':list(range(1,15)),'mean28':list(range(1,29)),'weekday4':[7,14,21,28]}
# Direct day/time lookup and math.fsum, independent of pandas shift/rolling implementation.
maxerr=0.;errors={}
for r in predrows:
    t=datetime.fromisoformat(r['interval_start']);zero=t.replace(hour=0,minute=0)
    for name,offsets in methods.items():
        hist=[t-timedelta(days=d) for d in offsets]
        assert all(h+timedelta(minutes=10)<=zero for h in hist)
        for variable,col in [('load',0),('pv',1)]:
            pr=math.fsum(lookup[h][col] for h in hist)/len(hist)
            err=abs(pr-float(r[f'{variable}_{name}']));maxerr=max(maxerr,err)
            assert err<1e-8
            errors.setdefault((variable,name),[]).append(lookup[t][col]-pr)
metrics=list(csv.DictReader((O/'history_reference_metrics.csv').open(encoding='utf-8-sig')))
for r in metrics:
    if r['span']=='Feb-Dec':
        es=errors[(r['variable'],r['method'])]
        assert abs(math.fsum(abs(x) for x in es)/len(es)-float(r['mae_kw']))<1e-8
erows=list(csv.DictReader((O/'net_reference_errors.csv').open(encoding='utf-8-sig')))
bydate={}
for r in erows:bydate.setdefault(r['date'],[]).append(r)
maxwindow=0.
windows=list(csv.DictReader((O/'six_hour_error_windows.csv').open(encoding='utf-8-sig')))
for r in windows:
    vals=bydate[r['date']];start=int(r['start_minute'])//10
    actual=math.fsum(float(x[r['pair']+'_error_kw'])/6 for x in vals[start:start+36])
    maxwindow=max(maxwindow,abs(actual-float(r['signed_error_kwh'])))
assert maxwindow<1e-8
result={'raw_numeric_values_checked':2*len(rawrows),'timestamp_mappings_checked':len(rawrows),
    'submission_intervals':cnt,'independent_decimal_totals':{k:str(v) for k,v in tot.items()},
    'all_fixed_reference_values_checked':len(predrows)*14,'max_reference_difference_kw':maxerr,
    'all_6h_windows_checked':len(windows),'max_window_difference_kwh':maxwindow,
    'past_only_information':True,'source_and_output_hashes_match':True,'ai_verification_only':True,
    'solver_calls':0,'fitted_models':0}
(O.parent/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
