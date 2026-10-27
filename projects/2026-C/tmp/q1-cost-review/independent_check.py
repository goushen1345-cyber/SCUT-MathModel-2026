"""Read-only Q1 numerical audit; isolated outputs, no Worker imports."""
import csv, json, sys, hashlib, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
from decimal import Decimal as D, ROUND_HALF_UP
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'questions/Q1/runs/20260911-compare-v1'
FINAL=ROOT/'questions/Q1/runs/20260911-close-v1/deliverables/result1.xlsx'
NS={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def read_cells(path, sheet=1):
    with zipfile.ZipFile(path) as z:
        ss=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            ss=[''.join(t.itertext()) for t in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('x:si',NS)]
        cells={}
        for c in ET.fromstring(z.read(f'xl/worksheets/sheet{sheet}.xml')).findall('.//x:c',NS):
            v=c.find('x:v',NS)
            if c.get('t')=='inlineStr': val=''.join(c.find('x:is',NS).itertext())
            elif v is None: continue
            elif c.get('t')=='s': val=ss[int(v.text)]
            else: val=v.text
            cells[c.get('r')]=val
        return cells

raw=read_cells(ROOT/'data/raw/C题/附件/附件1.xlsx')
final=read_cells(FINAL)
final2=read_cells(FINAL,2)
order=[145]+list(range(2,145))
rows=list(csv.DictReader((RUN/'outputs/schedules/C04.csv').open(encoding='utf-8-sig')))
price=[D(raw[f'B{r}']) for r in order]
load=[D(raw[f'C{r}']) for r in order]
pv=[D(raw[f'D{r}']) for r in order]
assert len(rows)==len(set(order))==144
errors=[]
max_xml_binary_serialization_delta=D(0)
for i,(r,row) in enumerate(zip(order,rows)):
    label=raw[f'A{r}']
    if label=='0:00+1': minute=0
    elif ':' in label: minute=int(label.split(':')[0])*60+int(label.split(':')[1])
    else: minute=int((D(label)*1440).to_integral_value())
    if minute!=i*10: errors.append(['time',r,minute,i*10])
    for col,key in [('B','price'),('C','load_kw'),('D','pv_kw')]:
        max_xml_binary_serialization_delta=max(max_xml_binary_serialization_delta,abs(D(raw[f'{col}{r}'])-D(row[key])))
        if float(raw[f'{col}{r}'])!=float(row[key]): errors.append(['source',r,col])
    if abs(D(final[f'B{r}'])-D(row['purchase_kwh']))>D('1e-10'): errors.append(['export',r])
eta=D('.9'); cap=D(5000)/6
res={k:D(0) for k in ['storage','load','pv','grid','chain','power','bounds','mode']}
prev=D(6000)
for i,row in enumerate(rows):
    q=D(row['purchase_kwh']); c=D(row['charge_kwh']); d=D(row['discharge']); s=D(row['state_end'])
    w=D(row['unused_pv_kwh']); gl=D(row['grid_to_load_kwh']); gc=D(row['grid_charge']); pc=D(row['pv_charge'])
    direct=min(load[i],pv[i])/6
    tests={'storage':s-prev-eta*c+d/eta,'load':direct+gl+d-load[i]/6,
           'pv':direct+pc+w-pv[i]/6,'grid':q-gc-gl,'chain':D(row['state_start'])-prev,
           'power':max(D(0),c-cap,d-cap),'bounds':max(D(0),1200-s,s-10800),
           'mode':min(c,d)}
    for k,v in tests.items():res[k]=max(res[k],abs(v))
    prev=s
assert prev==D(6000)
for block in range(6):
    rr=block+2
    for col,key in [('B','charge_kwh'),('C','discharge')]:
        if abs(D(final2[f'{col}{rr}'])-sum(D(r[key]) for r in rows[block*24:(block+1)*24]))>D('1e-9'):
            errors.append(['4hour',rr,col])
assert D(final2['E2'])==D(final2['E3'])==6000

q=[D(r['purchase_kwh']) for r in rows]
raw_cost=sum(a*b for a,b in zip(price,q))
export_cost=sum(D(raw[f'B{r}'])*D(final[f'B{r}']) for r in order)
def rnd(v,places=2):return v.quantize(D(10)**(-places),rounding=ROUND_HALF_UP)
rounding={
    'exact_schedule':str(raw_cost),'actual_xlsx':str(export_cost),
    'round_each_cost_to_cents':str(sum(rnd(a*b) for a,b in zip(price,q))),
    'round_each_purchase_to_2_places':str(sum(a*rnd(b) for a,b in zip(price,q))),
    'round_each_purchase_and_cost':str(sum(rnd(a*rnd(b)) for a,b in zip(price,q))),
    'round_4h_cost_to_cents':str(sum(rnd(sum(price[i]*q[i] for i in range(b*24,(b+1)*24))) for b in range(6))),
    'round_hourly_cost_to_cents':str(sum(rnd(sum(price[i]*q[i] for i in range(b*6,(b+1)*6))) for b in range(24)))
}

# Validate the stored certificate using Decimal arithmetic and raw workbook values.
cert=json.loads((RUN/'outputs/lp_certificate.json').read_text(encoding='utf-8'))
y=[D(str(x)) for x in cert['equality_marginals']]
mu=[D(str(x)) for x in cert['inequality_marginals']]
lo=[D(str(x)) for x in cert['lower_marginals']]
hi=[D(str(x)) for x in cert['upper_marginals']]
lower=[D(0)]*432+[D(1200)]*144
upper=[cap]*144+[min(cap,max(p-l,D(0))/6) for l,p in zip(load,pv)]+[min(cap,max(l-p,D(0))/6) for l,p in zip(load,pv)]+[D(10800)]*144
lower[-1]=upper[-1]=D(6000)
stn=[]
for k in range(144):
    grad=[-eta*y[k]+mu[k],-eta*y[k]+mu[k],y[k]/eta,y[k]-(y[k+1] if k<143 else 0)]
    obj=[price[k],D(0),-price[k],D(0)]
    stn.extend(abs(obj[b]-grad[b]-lo[b*144+k]-hi[b*144+k]) for b in range(4))
dual=D(6000)*y[0]+cap*sum(mu)+sum(a*b for a,b in zip(lower,lo))+sum(a*b for a,b in zip(upper,hi))+sum(p*max(l-v,D(0))/6 for l,v,p in zip(load,pv,price))
certificate_check={'dual_lower_bound':str(dual),'primal_minus_dual_yuan':str(raw_cost-dual),
    'max_stationarity_residual':str(max(stn)),
    'dual_sign_violations':sum(x<D('-1e-10') for x in lo)+sum(x>D('1e-10') for x in hi+mu),
    'solver_status':cert['status']}

# Independent LP: q (purchase), c (total external charge), u (load-side discharge),
# S (internal state), w (unused PV). Costs directly on q, with full bus balance.
# This differs from Worker's separated grid/PV charge variables and net-cost offset.
def solve(dt=1/6,cap_value=None,kw_decimals=None,price_decimals=None,method='highs-ds'):
    from scipy.optimize import linprog
    n=144
    l=np.array([float(x if kw_decimals is None else rnd(x,kw_decimals))*dt for x in load])
    v=np.array([float(x if kw_decimals is None else rnd(x,kw_decimals))*dt for x in pv])
    p=np.array([float(x if price_decimals is None else rnd(x,price_decimals)) for x in price])
    limit=5000*dt if cap_value is None else cap_value
    eq=np.zeros((2*n,5*n)); rhs=np.zeros(2*n)
    # q - c + u - w = L - PV
    # S_k - S_(k-1) - .9 c + u/.9 = 0
    for k in range(n):
        eq[k,k]=1;eq[k,n+k]=-1;eq[k,2*n+k]=1;eq[k,4*n+k]=-1;rhs[k]=l[k]-v[k]
        eq[n+k,n+k]=-.9;eq[n+k,2*n+k]=1/.9;eq[n+k,3*n+k]=1
        if k:eq[n+k,3*n+k-1]=-1
        else:rhs[n+k]=6000
    bounds=[(0,None)]*n+[(0,limit)]*n+[(0,min(limit,max(ll-vv,0))) for ll,vv in zip(l,v)]+[(1200,10800)]*n+[(0,max(vv-ll,0)) for ll,vv in zip(l,v)]
    bounds[4*n-1]=(6000,6000)
    ans=linprog(np.r_[p,np.zeros(4*n)],A_eq=eq,b_eq=rhs,bounds=bounds,method=method,
                options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9,'time_limit':30})
    assert ans.success,ans.message
    return {'cost':float(ans.fun),'status':int(ans.status),'max_eq_residual':float(np.abs(eq@ans.x-rhs).max()),
            'total_purchase':float(ans.x[:n].sum()),'max_simultaneous_kwh':float(np.minimum(ans.x[n:2*n],ans.x[2*n:3*n]).max()),
            'soc_first_end':[6000,float(ans.x[4*n-1])],'grid_difference_l1_to_original':float(np.abs(ans.x[:n]-np.array(q,dtype=float)).sum())}

diagnostics=json.loads((Path(__file__).parent/'check_result.json').read_text(encoding='utf-8'))['independent_lp'] if '--reuse-solves' in sys.argv else {
    'exact_independent_simplex':solve(),
    'exact_independent_interior_point':solve(method='highs-ipm'),
    'diagnostic_charge_discharge_cap_833_33':solve(cap_value=833.33),
    'diagnostic_dt_0_166667':solve(dt=.166667),
    'diagnostic_power_inputs_2decimals':solve(kw_decimals=2),
    'diagnostic_power_inputs_3decimals':solve(kw_decimals=3)
}
result={'source_mapping_and_export_errors':errors,'max_original_residuals':{k:str(v) for k,v in res.items()},
        'max_xml_binary_serialization_delta':str(max_xml_binary_serialization_delta),
        'source_values_match_as_binary64':not any(e[0]=='source' for e in errors),
        'rounding':rounding,'independent_lp':diagnostics,
        'independent_certificate_check':certificate_check,
        'input_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'data/raw/C题/附件/附件1.xlsx',RUN/'outputs/schedules/C04.csv',FINAL,RUN/'outputs/lp_certificate.json']},
        'external_reported_amount':'35126.95 only; no external schedule or accounting supplied',
        'note':'Diagnostic input changes are not proposed replacements and not actual external provenance.'}
(Path(__file__).parent/'check_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
