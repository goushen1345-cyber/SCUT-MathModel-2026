"""Independent standard-library checks; no dispatch imports or new solves."""
from pathlib import Path
from decimal import Decimal as D
import csv,json,hashlib,zipfile,xml.etree.ElementTree as ET

RUN=Path(__file__).resolve().parent; BASE=RUN.parent/'20260911-compare-v1'; PROJECT=RUN.parents[3]
OUT=RUN/'outputs'; NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def cells(p,index=1):
    with zipfile.ZipFile(p) as z:
        ss=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            ss=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS)]
        result={}
        for c in ET.fromstring(z.read(f'xl/worksheets/sheet{index}.xml')).findall('.//m:c',NS):
            v=c.find('m:v',NS)
            if c.get('t')=='inlineStr': value=''.join(c.find('m:is',NS).itertext())
            elif v is None: continue
            elif c.get('t')=='s': value=ss[int(v.text)]
            else: value=v.text
            result[c.get('r')]=value
        return result

def main():
    cfg=load(RUN/'protocol.json'); et=D(str(cfg['verification_energy_tolerance_kwh'])); ct=D(str(cfg['verification_cost_tolerance_yuan']))
    failures=[]; worst={}; count=0
    def ok(name,test):
        nonlocal count
        count+=1
        if not test: failures.append(name)
    def near(name,a,b=0,tol=et):
        d=abs(D(str(a))-D(str(b))); key=name.split(':')[0]
        worst[key]=max(worst.get(key,D(0)),d); ok(name,d<=tol)
    m=load(PROJECT/'data/prepared-v1/manifest.json')
    for p,h in m['raw_sha256'].items(): ok('raw hash:'+p,sha(PROJECT/p)==h)
    for p,v in m['outputs'].items(): ok('prepared hash:'+p,sha(PROJECT/'data/prepared-v1'/p)==v['sha256'])
    for p,h in load(OUT/'summary.json')['source_hashes'].items(): ok('source hash:'+p,sha(PROJECT/p)==h)
    ok('prior independent verification',load(BASE/'outputs/verification.json')['passed'])
    source=cells(PROJECT/'data/raw/C题/附件/附件1.xlsx'); dt=D(1)/6; eta=D('.9'); cc=D(5000)/6; n=144
    all_rows={}; summaries=[]
    for initial in [1200,6000,10800]:
        path=BASE/'outputs/schedules/C04.csv' if initial==6000 else OUT/f'schedules/initial_{initial}.csv'
        rs=rows(path); all_rows[initial]=rs; ok(f'length:{initial}',len(rs)==144); prev=D(initial)
        totals={k:D(0) for k in ['cost_yuan','purchase_kwh','charge_kwh','discharge','unused_pv_kwh','loss_kwh','grid_charge','pv_charge']}
        net=[]; surplus=[]; prices=[]
        for k,r in enumerate(rs,1):
            label=f'{initial}/{k}'; sr=145 if k==1 else k
            ok('time:'+label,int(D(r['k']))==k and int(D(r['start_minute']))==10*(k-1) and int(D(r['source_row']))==sr)
            for field,col in [('price','B'),('load_kw','C'),('pv_kw','D')]: near('raw:'+label+field,r[field],source[f'{col}{sr}'],D('1e-8'))
            l=D(source[f'C{sr}'])*dt; v=D(source[f'D{sr}'])*dt; p=D(source[f'B{sr}'])
            a=max(l-v,D(0)); b=max(v-l,D(0)); net.append(a); surplus.append(b); prices.append(p)
            x=D(r['grid_charge']); y=D(r['pv_charge']); z=D(r['discharge']); q=D(r['purchase_kwh']); c=x+y
            s=D(r['state_end']); start=D(r['state_start']); waste=D(r['unused_pv_kwh']); gl=D(r['grid_to_load_kwh'])
            ok('bounds:'+label,min(x,y,z,q,waste,gl)>=-et and y<=b+et and z<=a+et and D(1200)-et<=s<=D(10800)+et)
            ok('power:'+label,c<=cc+et and z<=cc+et); ok('mode:'+label,not(c>et and z>et))
            near('continuity:'+label,start,prev); near('storage:'+label,s,start+eta*c-z/eta)
            near('supply:'+label,min(l,v)+gl+z,l); near('pv:'+label,min(l,v)+y+waste,v)
            near('grid:'+label,q,gl+x); near('charge:'+label,r['charge_kwh'],c)
            near('cost:'+label,r['cost_yuan'],q*p,ct)
            near('loss:'+label,r['loss_kwh'],(1-eta)*c+(1/eta-1)*z)
            for key in totals: totals[key]+=D(r[key])
            prev=s
        near('terminal:'+str(initial),prev,initial)
        near('daily_energy:'+str(initial),totals['purchase_kwh']+sum(surplus)-sum(net),totals['unused_pv_kwh']+totals['loss_kwh'])
        cert=load(BASE/'outputs/lp_certificate.json' if initial==6000 else OUT/f'certificate_{initial}.json')
        y=list(map(lambda v:D(str(v)),cert['equality_marginals'])); z=list(map(lambda v:D(str(v)),cert['inequality_marginals']))
        lm=list(map(lambda v:D(str(v)),cert['lower_marginals'])); um=list(map(lambda v:D(str(v)),cert['upper_marginals']))
        lower=[D(0)]*(3*n)+[D(1200)]*n
        upper=[cc]*n+[min(e,cc) for e in surplus]+[min(e,cc) for e in net]+[D(10800)]*n
        lower[-1]=upper[-1]=D(initial)
        x=[D(r[f]) for f in ['grid_charge','pv_charge','discharge','state_end'] for r in rs]
        for j,val in enumerate(x): near('certificate_x:'+str(j),val,cert['x'][j])
        for t in range(n):
            deriv=[-eta*y[t]+z[t],-eta*y[t]+z[t],y[t]/eta,y[t]-(y[t+1] if t+1<n else 0)]
            for block,obj in enumerate([prices[t],D(0),-prices[t],D(0)]):
                j=block*n+t; near('stationarity:'+f'{initial}/{j}',obj,deriv[block]+lm[j]+um[j],D('1e-7'))
                ok('dual_sign:'+str(j),lm[j]>=D('-1e-7') and um[j]<=D('1e-7'))
            ok('inequality_sign:'+str(t),z[t]<=D('1e-7'))
        dual=D(initial)*y[0]+cc*sum(z)+sum(a*b for a,b in zip(lower,lm))+sum(a*b for a,b in zip(upper,um))+sum(p*a for p,a in zip(prices,net))
        near('primal_dual_gap:'+str(initial),totals['cost_yuan'],dual,ct)
        near('certificate_cost:'+str(initial),totals['cost_yuan'],cert['primal_cost'],ct)
        ok('optimal_status:'+str(initial),cert['status']==0)
        reported=next(r for r in rows(OUT/'sensitivity.csv') if int(r['initial_kwh'])==initial)
        for key in totals: near('reported:'+str(initial)+key,reported[key],totals[key],ct if key=='cost_yuan' else et)
        summaries.append(dict(initial_kwh=initial,**{k:float(v) for k,v in totals.items()},primal_dual_gap_yuan=float(totals['cost_yuan']-dual)))
    diffs=[]
    for initial in [1200,10800]:
        diff=[]
        for a,b in zip(all_rows[initial],all_rows[6000]):
            dq=D(a['purchase_kwh'])-D(b['purchase_kwh'])
            if abs(dq)>et: diff.append(dict(time=a['start_label'],purchase_difference_kwh=float(dq),price=float(a['price']),cost_difference_yuan=float(dq*D(a['price']))))
        diffs.append(dict(initial_kwh=initial,changed_slots=diff))
        row=next(r for r in rows(OUT/'sensitivity.csv') if int(r['initial_kwh'])==initial)
        near('difference_cost:'+str(initial),sum(D(str(r['cost_difference_yuan'])) for r in diff),row['cost_difference_yuan'],ct)
    base_rs=all_rows[6000]
    t1=rows(OUT/'table1_selected_purchase.csv'); t2=rows(OUT/'table2_four_hour.csv')
    for row,h in zip(t1,[10,12,14,16,18,20]): near('table1:'+str(h),row['purchase_kwh'],base_rs[h*6]['purchase_kwh'])
    for i,row in enumerate(t2):
        for field,outfield in [('charge_kwh','charge_kwh'),('discharge','discharge_kwh'),('purchase_kwh','purchase_kwh'),('cost_yuan','cost_yuan')]:
            near('table2:'+str(i)+field,row[outfield],sum(D(r[field]) for r in base_rs[24*i:24*(i+1)]),ct if field=='cost_yuan' else et)
    result=dict(passed=not failures,checks=count,failures=failures,largest_residuals={k:float(v) for k,v in worst.items()},
        results=summaries,changed_schedules=diffs,checker_sha256=sha(__file__),new_solves=0,
        method='Independent Decimal balance/source/LP certificate checks, no dispatch imports',limitation='AI verification; no human validation or annual robustness evidence')
    (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2)); assert not failures,failures[:10]

if __name__=='__main__': main()
