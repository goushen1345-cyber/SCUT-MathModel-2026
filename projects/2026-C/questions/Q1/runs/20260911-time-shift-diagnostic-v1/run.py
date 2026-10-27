"""One authorized time-mapping diagnostic; never writes adopted artifacts."""
import sys
sys.dont_write_bytecode = True
import csv, json, hashlib, importlib.util, platform, zipfile
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

RUN = Path(__file__).resolve().parent
PROJECT = RUN.parents[3]
BASE = RUN.parent / '20260911-compare-v1'
OUT = RUN / 'outputs'
assert not OUT.exists(), 'Output already exists; inspect instead of overwriting'
spec = importlib.util.spec_from_file_location('q1_original', BASE/'compare.py')
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
protected = [PROJECT/'data/raw/C题/附件/附件1.xlsx',
             PROJECT/'data/prepared-v1/day_reference.csv', BASE/'compare.py',
             BASE/'protocol.json', BASE/'outputs/schedules/C04.csv',
             BASE/'outputs/lp_certificate.json',
             RUN.parent/'20260911-close-v1/deliverables/result1.xlsx',
             PROJECT/'paper/q1_manuscript_v1/问题一论文草稿.pdf']
hashes = {str(p.relative_to(PROJECT)):model.sha(p) for p in protected}
original_inputs = model.load_input()
cfg = json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
inputs = []
for i, old in enumerate(sorted(original_inputs,key=lambda r:r['source_row'])):
    row = dict(old)
    row.pop('template_result1_row')  # No implication of an official export mapping.
    row.update(k=i+1,start_minute=10*i,end_minute=10*(i+1),
               start_label=f'{i//6:02d}:{i%6*10:02d}')
    inputs.append(row)
assert [r['source_row'] for r in inputs] == list(range(2,146))
assert inputs[0]['start_minute']==0 and inputs[-1]['end_minute']==1440
OUT.mkdir()
model.write_csv(OUT/'input_mapping.csv', inputs)
actions, cert = model.solve_lp(inputs,cfg)  # The only new optimization solve.
rows = model.schedule(inputs,cfg,actions)
model.write_csv(OUT/'schedule.csv',rows)
model.dump(OUT/'lp_certificate.json',cert)

# Re-read the saved artifact and raw cell strings for independent checks.
with (OUT/'schedule.csv').open(encoding='utf-8-sig',newline='') as f:
    saved = list(csv.DictReader(f))
with (BASE/'outputs/schedules/C04.csv').open(encoding='utf-8-sig',newline='') as f:
    baseline = list(csv.DictReader(f))
ns = {'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(PROJECT/'data/raw/C题/附件/附件1.xlsx') as z:
    tree = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    raw = {c.attrib['r']:c.find('x:v',ns).text for c in tree.findall('.//x:c',ns)
           if c.find('x:v',ns) is not None}
eta=D('.9'); cap=D(5000)/6
res = {k:D(0) for k in ['source','storage','load','pv','grid','power','bounds','mode','nonnegative','chain']}
previous=D(6000); cost=D(0)
for i,row in enumerate(saved):
    r=i+2
    assert int(row['source_row'])==r and int(row['start_minute'])==10*i
    for col,key in [('B','price'),('C','load_kw'),('D','pv_kw')]:
        assert float(raw[f'{col}{r}'])==float(row[key])
    l=D(raw[f'C{r}'])/6; pv=D(raw[f'D{r}'])/6
    q=D(row['purchase_kwh']); c=D(row['charge_kwh']); z=D(row['discharge'])
    s=D(row['state_end']); direct=min(l,pv)
    x=D(row['grid_charge']); y=D(row['pv_charge'])
    gl=D(row['grid_to_load_kwh']); w=D(row['unused_pv_kwh'])
    tests = dict(storage=s-previous-eta*c+z/eta,
        load=direct+gl+z-l,pv=direct+y+w-pv,grid=q-gl-x,
        power=max(D(0),c-cap,z-cap),bounds=max(D(0),D(1200)-s,s-D(10800)),
        mode=min(c,z),nonnegative=max(D(0),-min(q,c,z,x,y,gl,w)),
        chain=D(row['state_start'])-previous,source=c-x-y)
    for k,v in tests.items():res[k]=max(res[k],abs(v))
    previous=s;cost+=D(raw[f'B{r}'])*q
assert previous==D(6000) and max(res.values())<D('1e-5'),res
base_cost=sum(D(raw[f"B{int(r['source_row'])}"])*D(r['purchase_kwh']) for r in baseline)

# Independently reconstruct stationarity and the dual lower bound.
y=[D(str(v)) for v in cert['equality_marginals']]
mu=[D(str(v)) for v in cert['inequality_marginals']]
lo=[D(str(v)) for v in cert['lower_marginals']]
hi=[D(str(v)) for v in cert['upper_marginals']]
p=[D(raw[f'B{r}']) for r in range(2,146)]
l=[D(raw[f'C{r}']) for r in range(2,146)]
v=[D(raw[f'D{r}']) for r in range(2,146)]
lower=[D(0)]*432+[D(1200)]*144
upper=[cap]*144+[min(cap,max(b-a,D(0))/6) for a,b in zip(l,v)]+[min(cap,max(a-b,D(0))/6) for a,b in zip(l,v)]+[D(10800)]*144
lower[-1]=upper[-1]=D(6000)
stationarity=[]
for k in range(144):
    grad=[-eta*y[k]+mu[k],-eta*y[k]+mu[k],y[k]/eta,y[k]-(y[k+1] if k<143 else 0)]
    obj=[p[k],D(0),-p[k],D(0)]
    stationarity.extend(abs(obj[b]-grad[b]-lo[b*144+k]-hi[b*144+k]) for b in range(4))
dual=D(6000)*y[0]+cap*sum(mu)+sum(a*b for a,b in zip(lower,lo))+sum(a*b for a,b in zip(upper,hi))+sum(pp*max(ll-vv,D(0))/6 for pp,ll,vv in zip(p,l,v))
assert abs(cost-dual)<D('1e-4') and max(stationarity)<D('1e-7')
assert all(x>=D('-1e-7') for x in lo) and all(x<=D('1e-7') for x in hi+mu)
assert all(model.sha(PROJECT/k)==h for k,h in hashes.items())
verification=dict(max_residual_kwh={k:str(v) for k,v in res.items()},
    decimal_fee=str(cost),baseline_decimal_fee=str(base_cost),
    decimal_dual_lower_bound=str(dual),primal_minus_dual=str(cost-dual),
    stationarity_residual=str(max(stationarity)),source_rows_complete=True,
    protected_files_unchanged=True,ai_check_only=True)
model.dump(OUT/'verification.json',verification)

by_source={int(r['source_row']):r for r in baseline}
comparison=[]
for r in saved:
    b=by_source[int(r['source_row'])]
    comparison.append(dict(source_row=r['source_row'],source_time_label=r['source_time_label'],
        original_start=b['start_label'],alternative_start=r['start_label'],
        original_purchase_kwh=float(b['purchase_kwh']),alternative_purchase_kwh=float(r['purchase_kwh']),
        purchase_delta_kwh=float(r['purchase_kwh'])-float(b['purchase_kwh']),
        original_state_start=float(b['state_start']),alternative_state_start=float(r['state_start']),
        original_state_end=float(b['state_end']),alternative_state_end=float(r['state_end']),
        cost_delta_yuan=float(r['cost_yuan'])-float(b['cost_yuan'])))
model.write_csv(OUT/'comparison_by_source_row.csv',comparison)
summary=dict(created_utc=datetime.now(timezone.utc).isoformat(),authorization='Q1-TIME-DIAG-040',
    protocol='Q1-time-shift-diagnostic-v1',lp_evaluations=1,
    original_fee=str(base_cost),alternative_fee=str(cost),difference_yuan=str(cost-base_cost),
    relative_difference_percent=str((cost-base_cost)/base_cost*100),
    alternative_metrics=model.metrics(rows),
    original_totals={k:sum(float(r[k]) for r in baseline) for k in ['purchase_kwh','charge_kwh','discharge','loss_kwh','unused_pv_kwh']},
    source_aligned_changed_purchase_rows=[r for r in comparison if abs(r['purchase_delta_kwh'])>1e-5],
    solver_status=cert['status'],solver_seconds=cert['time_seconds'],
    environment=dict(python=sys.version,executable=sys.executable,numpy=model.np.__version__,scipy=model.scipy.__version__,platform=platform.platform()),
    protected_sha256=hashes,script_sha256=model.sha(__file__),protocol_sha256=model.sha(RUN/'protocol.json'),
    adopted_mapping_changed=False,limitations='One alternative interpretation only; not proof of original or external interpretation; original artifacts unchanged')
model.dump(OUT/'summary.json',summary)
model.dump(OUT/'output_hashes.json',{p.name:model.sha(p) for p in sorted(OUT.iterdir()) if p.is_file()})
print(json.dumps({k:summary[k] for k in ['original_fee','alternative_fee','difference_yuan','alternative_metrics','original_totals','source_aligned_changed_purchase_rows','solver_seconds']},ensure_ascii=False,indent=2))
