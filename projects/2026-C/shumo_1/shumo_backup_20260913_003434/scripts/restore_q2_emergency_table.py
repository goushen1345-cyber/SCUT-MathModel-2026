"""Restore the Q2 paper's accidentally duplicated order table from saved execution."""
from pathlib import Path
import csv, gzip, hashlib, json

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[2]
RUN=PROJECT/'questions/Q2/runs/20260911-annual-validation-v1'
DATA=RUN/'delivery_data'
OUT=HERE.parent/'tables/q2_emergency.tex'
dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
labels=dict(zip(dates,['3月20日','6月21日','9月23日','12月21日']))
tracefile=DATA/'selected_execution.csv.gz'
with gzip.open(tracefile,'rt',encoding='utf-8-sig',newline='') as f:
    trace=list(csv.DictReader(f))
assert len(trace)==334*144
with (DATA/'specified_table3.csv').open(encoding='utf-8-sig',newline='') as f:
    old=list(csv.DictReader(f))
with (DATA/'selected_daily.csv').open(encoding='utf-8-sig',newline='') as f:
    daily={r['decision_date']:r for r in csv.DictReader(f)}
events=[];totals={}
for d in dates:
    rows=[r for r in trace if r['date']==d]
    assert len(rows)==144 and [int(r['slot']) for r in rows]==list(range(144))
    positive=[r for r in rows if float(r['emergency_kwh'])>1e-6]
    total=sum(float(r['emergency_kwh']) for r in rows)
    ref=[r for r in old if r['date']==d]
    assert abs(total-sum(float(r['kwh']) for r in ref))<1e-8
    assert abs(total-float(daily[d]['emergency_kwh']))<1e-8
    totals[d]=total
    for row in positive:
        k=int(row['slot']);start=f'{k//6:02d}:{k%6*10:02d}';end=f'{(k+1)//6:02d}:{(k+1)%6*10:02d}'
        assert any(int(float(r['start_slot']))==k and abs(float(r['kwh'])-float(row['emergency_kwh']))<1e-8 for r in ref if r['start_slot'])
        events.append({'date':d,'interval':start+'--'+end,'emergency_kwh':float(row['emergency_kwh']),'emergency_cost':float(row['emergency_cost'])})
text=[r'% Restored from verified Q2 selected_execution.csv.gz; no model rerun.',r'\begin{table}[H]',r'\centering',r'\caption{问题二指定日期发生紧急购电的时段及电量}',r'\label{tab:q2_emergency_purchase}',r'\begin{tabular}{llr}',r'\toprule',r'日期 & 时间段 & 紧急购电量/kWh \\',r'\midrule']
for r in events:
    text.append(f"{labels[r['date']]} & {r['interval']} & {r['emergency_kwh']:.2f}"+r' \\')
text += [r'\bottomrule',r'\end{tabular}',r'\end{table}','']
OUT.write_text('\n'.join(text),encoding='utf-8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result={'events':events,'daily_emergency_kwh':totals,'checks':{'complete_334_days':True,'each_selected_day_144_sorted_slots':True,'matches_saved_specified_table':True,'matches_selected_daily':True,'new_fits':0,'new_solves':0},
 'sources':[{'path':str(p),'sha256':sha(p)} for p in [tracefile,DATA/'specified_table3.csv',DATA/'selected_daily.csv',RUN/'delivery_verification.json']],
 'output':{'path':str(OUT),'sha256':sha(OUT)},'code':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))}}
(HERE/'q2_emergency_table_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'events':events,'daily_totals':totals,'all_checks':True},ensure_ascii=False))
