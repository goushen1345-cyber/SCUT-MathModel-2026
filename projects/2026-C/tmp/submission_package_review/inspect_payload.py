from pathlib import Path
import numpy as np,json,openpyxl
P=Path(__file__).resolve().parents[2]
for label,rel in [('Q2','Q2/runs/20260911-annual-validation-v1/refinement/schedules/sensitivity-error-decay70.npz'),('Q3','Q3/runs/20260912-forecast-risk-v1/outputs/strategies/EW4_Q60_full.npz'),('Q42','Q4/runs/20260912-selected-deepening-v1/outputs/strategies/Q4-2-P3-leaves31.npz'),('Q43','Q4/runs/20260913-q3-transfer-v1/outputs/strategies/EW4_P2_Q60.npz')]:
 z=np.load(P/'questions'/rel);print(label,{k:(v.shape,v.dtype.name) for k,v in z.items()});
 if label=='Q2':print(z['actual_columns'])
for p in (P/'data/raw/C题/附件/附件5').glob('*.xlsx'):
 w=openpyxl.load_workbook(p);print('\n',p.name)
 for s in w:
  print(s.title,s.max_row,s.max_column,'merges',str(s.merged_cells)[:800])
  for r in [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,145,146,147,148,149,150,151,152,153]:
   if r>s.max_row:continue
   cells=[(c.coordinate,str(c.value)) for c in s[r] if c.value is not None]
   print(cells[:7],cells[-3:] if len(cells)>7 else '')
