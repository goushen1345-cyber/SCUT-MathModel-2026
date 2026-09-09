"""U008 limited repair: make the S2 99.0% Pareto point inherit the 99.5% incumbent."""
from pathlib import Path
import json, sys
import run_trials as r
import run_deepen as d

out=d.OUT/'PARETO-D0-S2-0p99-R1';out.mkdir(exist_ok=False)
profit_record=json.loads((d.OUT/'PARETO-D0-S2-profit'/'solver.json').read_text(encoding='utf-8'))
floor=float(profit_record['stage1']['recomputed_profit'])*.99
md=r.compile_model('D0','S2',.5,None,'management',profit_floor=floor)
warm=d.start_from_csv(md,d.OUT/'PARETO-D0-S2-0p995'/'solution.csv','D0')
_,vals,solve=r.solve(md,60,gap=.005,start_values=warm);r.dump(out/'stage2_solver.json',solve)
if not solve['solution_valid']:raise RuntimeError('No repaired Pareto solution')
ev=d.save_solution(out,md,vals,'PARETO-R1','D0','S2',{'protocol':'Q1-DEEPEN-v1','authorization':'U008','candidate':'PARETO-R1','scenario':'D0','sale_case':'S2','cap':None,'alpha':.5,'retention':.99,'profit_floor':floor,'management_stage':solve,'repair_of':'PARETO-D0-S2-0p99','repair_reason':'inherit the known 99.5% incumbent so the relaxed frontier is monotone','seed':r.SEED})
print(json.dumps({'profit':ev['profit'],'activations':ev['activations'],'status':solve['status']},ensure_ascii=False))
