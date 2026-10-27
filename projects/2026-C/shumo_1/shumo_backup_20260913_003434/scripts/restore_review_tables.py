"""Reproduce the two review tables using saved trajectories; no model is run."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--output-root', type=Path, default=HERE.parent)
OUT = parser.parse_args().output_root.resolve()
(OUT/'tables').mkdir(parents=True, exist_ok=True)
(OUT/'scripts').mkdir(parents=True, exist_ok=True)
inputs=[]
def readcsv(p):
    inputs.append(p)
    return pd.read_csv(p, float_precision='round_trip')
def readnpz(p):
    inputs.append(p)
    return dict(np.load(p))
def num(x):
    return f'{0 if abs(x)<0.0005 else x:.2f}'
def clock(k):
    return f'{k//6:02d}:{k%6*10:02d}'
def table(filename, caption, label, cols, rows, spec, note=''):
    parts=[r'% Generated from saved trajectories by scripts/restore_review_tables.py.',
           r'\begin{table}[H]',r'\centering',r'\caption{'+caption+'}',r'\label{'+label+'}',
           r'\small',r'\setlength{\tabcolsep}{5pt}',r'\begin{tabular}{'+spec+'}',
           r'\toprule',' & '.join(cols)+r' \\',r'\midrule']
    parts += [row if isinstance(row,str) else ' & '.join(row)+r' \\' for row in rows]
    parts += [r'\bottomrule',r'\end{tabular}']
    if note: parts += [r'\par\smallskip',r'\begin{minipage}{0.96\textwidth}',r'\small '+note,r'\end{minipage}']
    parts += [r'\end{table}','']
    p=OUT/'tables'/filename
    p.write_text('\n'.join(parts),encoding='utf-8')
    return p

dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
names=['3月20日','6月21日','9月23日','12月21日']
q3=PROJECT/'questions/Q3/runs/20260912-forecast-risk-v1/outputs/strategies'
d3=readcsv(q3/'EW4_Q60_full.daily.csv')
z3=readnpz(q3/'EW4_Q60_full.npz')
price=readnpz(PROJECT/'questions/Q3/runs/20260911-four-candidates-v1/outputs/sources.npz')['price']
rows=[]
checks=[]
for date,name in zip(dates,names):
    i=int(d3.index[d3.date==date][0])
    e=z3['execution'][i,:,8]
    costs=5*price*e
    assert abs(e.sum()-d3.loc[i,'emergency_kwh'])<1e-6
    assert abs(costs.sum()-d3.loc[i,'emergency_cost'])<1e-6
    ks=np.flatnonzero(e>1e-6)
    for j,k in enumerate(ks):
        rows.append([name if j==0 else '',clock(k)+'--'+clock(k+1),num(e[k]),num(costs[k])])
    if not len(ks): rows.append([name,'无','0.00','0.00'])
    checks.append({'branch':'Q3','date':date,'emergency_kwh':float(e.sum()),'emergency_cost':float(costs.sum())})
outputs=[table('q3_emergency.tex','指定日期紧急购电的时段、电量及费用','tab:q3_emergency',
               ['日期','时间段','紧急购电量/kWh','费用/元'],rows,'llrr')]

q42=PROJECT/'questions/Q4/runs/20260912-selected-deepening-v1/outputs/strategies/Q4-2-P3-leaves31'
q43=PROJECT/'questions/Q4/runs/20260913-q3-transfer-v1/outputs/strategies/EW4_P2_Q60'
q4price=readnpz(PROJECT/'questions/Q4/runs/20260913-q3-transfer-v1/outputs/supply.npz')['price']
rows=[]
for branch,path,expected in [('四-2',q42,14248570.87),('四-3',q43,13695929.70)]:
    df=readcsv(path.with_suffix('.daily.csv'))
    z=readnpz(path.with_suffix('.npz'))
    assert len(df)==334 and abs(df.total_cost.sum()-expected)<0.01
    assert abs(df.iloc[0]['initial']-8592.693560925925)<1e-6
    for date,name in zip(dates,names):
        i=int(df.index[df.date==date][0]); day=int(df.loc[i,'day']); ex=z['execution'][i]
        order=z['order'][i] if 'order' in z else z['versions'][i,-1]
        ordinary=float(q4price[day]@order)
        emergency=float(5*q4price[day]@ex[:,8])
        adjustment=0. if 'order' in z else float(.5*q4price[day]@abs(order-z['q0'][i]))
        assert abs(ordinary-df.loc[i,'ordinary_cost'])<1e-6
        assert abs(adjustment-df.loc[i,'adjustment_cost'])<1e-6
        assert abs(emergency-df.loc[i,'emergency_cost'])<1e-6
        assert abs(ordinary+adjustment+emergency-df.loc[i,'total_cost'])<1e-6
        assert abs(order.sum()-df.loc[i,'order_kwh'])<1e-6
        assert abs(ex[:,8].sum()-df.loc[i,'emergency_kwh'])<1e-6
        assert abs(ex[-1,1]-df.loc[i,'final'])<1e-6
        rows.append([branch,name,num(order.sum()),num(ex[:,8].sum()),num(ex[-1,1]),num(df.loc[i,'total_cost'])])
        checks.append({'branch':branch,'date':date,'total_cost':float(df.loc[i,'total_cost']),
                       'ordinary_cost':ordinary,'adjustment_cost':adjustment,'emergency_cost':emergency})
    if branch=='四-2':rows.append(r'\midrule')
outputs.append(table('q4_specified_dates.tex','问题四两条分支的指定日期结果','tab:q4_specified_dates',
                    ['分支','日期','普通订单/kWh','紧急购电/kWh','日末储电/kWh','总费用/元'],rows,'llrrrr',
                    '注：普通订单为全天最终订单之和；总费用按实际电价计算，包含普通购电、调整与紧急购电。'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'sources':[{'path':str(p),'sha256':sha(p)} for p in inputs],
          'outputs':[{'path':str(p),'sha256':sha(p)} for p in outputs],
          'checks':checks,'scope':'saved result aggregation and independent bill checks; no model run'}
(OUT/'scripts/review_tables_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps({'tables':[str(p) for p in outputs],'checked_dates':len(checks)},ensure_ascii=False))
