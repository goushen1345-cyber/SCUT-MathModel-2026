"""Independent export/source and LP certificate checks; no import of dispatch code."""
from pathlib import Path
from decimal import Decimal as D
import argparse, csv, hashlib, itertools, json, zipfile, xml.etree.ElementTree as ET

RUN=Path(__file__).resolve().parent; PROJECT=RUN.parents[3]
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def readcsv(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def cells(path):
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS)]
        result={}
        for c in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//m:c',NS):
            v=c.find('m:v',NS)
            if c.get('t')=='inlineStr': value=''.join(c.find('m:is',NS).itertext())
            elif v is None: continue
            elif c.get('t')=='s': value=strings[int(v.text)]
            else: value=v.text
            result[c.attrib['r']]=value
        return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',default='outputs'); a=ap.parse_args()
    out=RUN/a.output; cfg=load(RUN/'protocol.json'); m=load(PROJECT/'data/prepared-v1/manifest.json')
    et=D(str(cfg['verification_energy_tolerance_kwh'])); ct=D(str(cfg['verification_cost_tolerance_yuan']))
    failures=[]; checks=0; worst={}; results={}
    def ok(name, cond):
        nonlocal checks
        checks+=1
        if not cond: failures.append(name)
    def near(name,value,tolerance=et):
        value=abs(D(value)); worst[name.split(':')[0]]=max(worst.get(name.split(':')[0],D(0)),value)
        ok(name,value<=tolerance)
    for rel,h in m['raw_sha256'].items(): ok('raw:'+rel,sha(PROJECT/rel)==h)
    for rel,info in m['outputs'].items(): ok('prepared:'+rel,sha(PROJECT/'data/prepared-v1'/rel)==info['sha256'])
    raw=cells(PROJECT/'data/raw/C题/附件/附件1.xlsx')
    template=cells(PROJECT/'data/raw/C题/附件/附件5/result1.xlsx')
    mapping=readcsv(out/'input_mapping.csv')
    ok('144 inputs',len(mapping)==144)
    ok('source/template bijection',sorted(int(r['source_row']) for r in mapping)==list(range(2,146)))
    for k,r in enumerate(mapping,1):
        minute=(k-1)*10; source_row=145 if k==1 else k
        ok(f'map:{k}',int(r['start_minute'])==minute and int(r['source_row'])==source_row and int(r['template_result1_row'])==source_row)
        for col,field in [('B','price'),('C','load_kw'),('D','pv_kw')]: near(f'source_values:{k}{col}',D(r[field])-D(raw[f'{col}{source_row}']),D('1e-8'))
        label=raw[f'A{source_row}']
        if source_row==145: ok('midnight source',label=='0:00+1')
        elif ':' in label: ok(f'time_label:{k}',int(label.split(':')[0])*60+int(label.split(':')[1])==minute)
        else: near(f'excel_time:{k}',D(label)*D(1440)-D(minute),D('1e-6'))
    ok('template first position',template['A2']=='0:10-0:20')
    ok('template last position',template['A145']=='0:00+1-0:10+1')
    dt=D(1)/D(6); eta=D('0.9'); cc=D(5000)/6; smin=D(1200); smax=D(10800)
    files=sorted((out/'schedules').glob('*.csv')); ok('55 schedules',len(files)==55)
    for path in files:
        rows=readcsv(path); ok(path.stem+' length',len(rows)==144)
        totals={key:D(0) for key in ['cost_yuan','purchase_kwh','charge_kwh','discharge','pv_charge','grid_charge','unused_pv_kwh','loss_kwh']}
        prev=D(6000)
        for k,(r,src) in enumerate(zip(rows,mapping),1):
            name=f'{path.stem}/{k}'
            for f in ['k','start_minute','source_row','price','load_kw','pv_kw']: ok('input_match:'+name+f,r[f]==src[f])
            l=D(src['load_kw'])*dt; v=D(src['pv_kw'])*dt; p=D(src['price']); direct=min(l,v)
            cg=D(r['grid_charge']); cp=D(r['pv_charge']); d=D(r['discharge']); c=cg+cp
            begin=D(r['state_start']); end=D(r['state_end']); q=D(r['purchase_kwh']); gl=D(r['grid_to_load_kwh']); w=D(r['unused_pv_kwh'])
            ok('nonnegative:'+name,min(cg,cp,d,q,gl,w)>=-et)
            ok('power:'+name,c<=cc+et and d<=cc+et)
            ok('capacity:'+name,smin-et<=end<=smax+et)
            ok('mode:'+name,not(c>et and d>et))
            near('continuity:'+name,begin-prev); near('storage:'+name,end-begin-eta*c+d/eta)
            near('load_balance:'+name,direct+gl+d-l); near('pv_balance:'+name,direct+cp+w-v)
            near('grid_balance:'+name,q-gl-cg); near('charge_total:'+name,D(r['charge_kwh'])-c)
            near('unit_load:'+name,D(r['load_kwh'])-l); near('unit_pv:'+name,D(r['pv_kwh'])-v)
            near('direct_pv:'+name,D(r['direct_pv_kwh'])-direct)
            loss=(1-eta)*c+(1/eta-1)*d
            near('loss:'+name,D(r['loss_kwh'])-loss)
            near('slot_cost:'+name,D(r['cost_yuan'])-q*p,ct)
            for key in totals: totals[key]+=D(r[key])
            prev=end
        near('terminal:'+path.stem,prev-D(6000))
        near('daily_energy:'+path.stem,totals['purchase_kwh']+sum(D(r['pv_kwh']) for r in rows)-sum(D(r['load_kwh']) for r in rows)-totals['unused_pv_kwh']-totals['loss_kwh'])
        results[path.stem]=totals
    scores=readcsv(out/'parameter_scores.csv'); summary=load(out/'summary.json')
    expected=list(itertools.product(cfg['low_quantiles'],cfg['high_quantiles'],cfg['target_fractions_of_usable_capacity']))
    for candidate in ['03','10']:
        group=[r for r in scores if r['candidate']==candidate]
        ok('27 settings:'+candidate,len(group)==27)
        ok('full grid:'+candidate,[(float(r['low_quantile']),float(r['high_quantile']),float(r['target_fraction'])) for r in group]==expected)
        best=min(group,key=lambda r:(D(r['cost_yuan']),int(r['param_index'])))
        ok('selection:'+candidate,best['key']==summary['selected_parameters'][candidate]['key'])
    for r in scores:
        for field,total in results[r['key']].items(): near('score:'+r['key']+field,D(r[field])-total,ct if field=='cost_yuan' else et)
    for r in readcsv(out/'comparison.csv'):
        for field,total in results[r['key']].items(): near('comparison:'+r['key']+field,D(r[field])-total,ct if field=='cost_yuan' else et)
    paired=readcsv(out/'paired_comparison.csv')
    for r in paired:
        i=int(r['param_index']); diff=results[f'C03-p{i:02d}']['cost_yuan']-results[f'C10-p{i:02d}']['cost_yuan']
        near('paired:'+str(i),D(r['saving_yuan'])-diff,ct)
    # Certificate algebra independently reconstructed from the declared variables and source data.
    cert=load(out/'lp_certificate.json'); lp=readcsv(out/'schedules/C04.csv'); n=144
    y=list(map(lambda x:D(str(x)),cert['equality_marginals'])); z=list(map(lambda x:D(str(x)),cert['inequality_marginals']))
    lm=list(map(lambda x:D(str(x)),cert['lower_marginals'])); um=list(map(lambda x:D(str(x)),cert['upper_marginals']))
    lower=[D(0)]*(3*n)+[smin]*n; upper=[cc]*n
    net=[max(D(r['load_kw'])-D(r['pv_kw']),D(0))*dt for r in mapping]
    excess=[max(D(r['pv_kw'])-D(r['load_kw']),D(0))*dt for r in mapping]
    price=[D(r['price']) for r in mapping]
    upper += [min(e,cc) for e in excess]+[min(e,cc) for e in net]+[smax]*n
    lower[-1]=upper[-1]=D(6000)
    x=[D(r[f]) for f in ['grid_charge','pv_charge','discharge','state_end'] for r in lp]
    for j,val in enumerate(x): near('certificate_x:'+str(j),val-D(str(cert['x'][j])))
    for t in range(n):
        deriv=[-eta*y[t]+z[t],-eta*y[t]+z[t],y[t]/eta,y[t]-(y[t+1] if t+1<n else 0)]
        obj=[price[t],D(0),-price[t],D(0)]
        for block in range(4):
            j=block*n+t
            near('stationarity:'+str(j),obj[block]-deriv[block]-lm[j]-um[j],D('1e-7'))
            ok('dual_bounds_sign:'+str(j),lm[j]>=D('-1e-7') and um[j]<=D('1e-7'))
        ok('dual_inequality_sign:'+str(t),z[t]<=D('1e-7'))
    base=sum(p*q for p,q in zip(price,net))
    dual=D(6000)*y[0]+cc*sum(z)+sum(a*b for a,b in zip(lower,lm))+sum(a*b for a,b in zip(upper,um))+base
    primal=results['C04']['cost_yuan']; near('primal_dual_gap',primal-dual,ct)
    near('certificate_primal',primal-D(str(cert['primal_cost'])),ct)
    near('certificate_dual',dual-D(str(cert['dual_cost'])),ct)
    ok('solver_status',cert['status']==0)
    result=dict(passed=not failures,check_count=checks,failures=failures,schedules_checked=len(files),
        checker_sha256=sha(__file__),method='Standard-library Decimal, original XLSX XML, independent LP certificate algebra; no dispatch imports',
        largest_residuals={k:float(v) for k,v in worst.items()},lp_primal_yuan=float(primal),lp_dual_yuan=float(dual),
        raw_files_unchanged=True,prepared_files_unchanged=True,
        limitations='Independent AI numerical check, not human review; does not prove annual robustness or physical sampling assumption')
    (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2)); assert not failures, failures[:10]

if __name__=='__main__': main()
