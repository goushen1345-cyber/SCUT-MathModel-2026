"""Independent original-XLSX check via XML/Decimal; no EDA pipeline imports."""
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from collections import defaultdict,Counter
from decimal import Decimal as D
import json,hashlib
HERE=Path(__file__).resolve().parent;PROJECT=HERE.parents[2];ROOT=PROJECT.parents[1]
N={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def book(path):
    with ZipFile(path) as z:
        ss=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',N)]
        rel={e.attrib['Id']:e.attrib['Target'] for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        result={}
        for sh in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',N):
            t=rel[sh.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']];xml=ET.fromstring(z.read(t.lstrip('/') if t.startswith('/') else 'xl/'+t));c={}
            for e in xml.findall('.//s:sheetData/s:row/s:c',N):
                v=e.find('s:v',N)
                c[e.attrib['r']]=ss[int(v.text)] if e.attrib.get('t')=='s' and v is not None else ''.join(e.find('s:is',N).itertext()) if e.attrib.get('t')=='inlineStr' else v.text if v is not None else None
            for e in xml.findall('s:mergeCells/s:mergeCell',N):
                start,end=e.attrib['ref'].split(':')
                import re
                a,r=re.fullmatch(r'([A-Z]+)(\d+)',start).groups();b,q=re.fullmatch(r'([A-Z]+)(\d+)',end).groups()
                if a==b:
                    for row in range(int(r),int(q)+1):c[a+str(row)]=c.get(start)
            result[sh.attrib['name']]=c
        return result
def main():
    a=book(ROOT/'培训作业/第四次培训作业/附件1.xlsx');b=book(ROOT/'培训作业/第四次培训作业/附件2.xlsx')
    lc=a['乡村的现有耕地'];cc=a['乡村种植的农作物'];hc=b['2023年的农作物种植情况'];pc=b['2023年统计的相关数据']
    lands={lc[f'A{r}'].strip():(lc[f'B{r}'].strip(),D(lc[f'C{r}'])) for r in range(2,56)}
    cats={int(cc[f'A{r}']):cc[f'C{r}'].strip() for r in range(2,43)}
    h=[(hc[f'A{r}'].strip(),int(hc[f'B{r}']),hc[f'F{r}'].strip(),D(hc[f'E{r}'])) for r in range(2,89)]
    d=json.loads((HERE/'results/eda.json').read_text(encoding='utf-8'));fail=[]
    def eq(name,x,y):
        if isinstance(x,(int,float,D)) and isinstance(y,(int,float,D)):ok=abs(D(str(x))-D(str(y)))<D('0.00000001')
        else:ok=x==y
        if not ok:fail.append({'check':name,'source':str(x),'eda':str(y)})
    for row in d['land_stats']:
        ls=[v[1] for v in lands.values() if v[0]==row['type']];eq('land area '+row['type'],sum(ls),row['area']);eq('land count '+row['type'],len(ls),row['count'])
    for row in d['crop_history']:
        xs=[x for x in h if x[1]==row['crop']];eq('crop area '+row['name'],sum(x[3] for x in xs),row['area']);eq('crop plots '+row['name'],len({x[0] for x in xs}),row['plots'])
    for row in d['history_by_type']:
        for cat,val in row['areas'].items():eq('history '+row['type']+cat,sum(x[3] for x in h if lands[x[0]][0]==row['type'] and cats[x[1]]==cat),val)
    legal=set()
    for c in range(1,42):
        if c<=15:comb=[(t,'单季') for t in ['平旱地','梯田','山坡地']]
        elif c==16:comb=[('水浇地','单季')]
        elif c<=34:comb=[('水浇地','第一季'),('普通大棚','第一季'),('智慧大棚','第一季'),('智慧大棚','第二季')]
        elif c<=37:comb=[('水浇地','第二季')]
        else:comb=[('普通大棚','第二季')]
        legal.update((c,*x) for x in comb)
    obs={(c,lands[l][0],s) for l,c,s,v in h}
    expected=[[2 if (c,*x) in obs else 1 if (c,*x) in legal else 0 for x in d['coverage_columns']] for c in range(1,42)]
    eq('source-rule coverage matrix',expected,d['coverage_matrix'])
    for row in d['parameters']:
        r=row['source_row'];lo,hi=pc['H'+r].split('-')
        for field,val in [('yield',pc['F'+r]),('cost',pc['G'+r]),('price_low',lo),('price_high',hi)]:eq('parameter '+r+field,D(val),row[field])
    groups=Counter((l,s) for l,c,s,v in h)
    eq('mixed groups',sum(n>1 for n in groups.values()),d['summary']['mixed_groups'])
    eq('bean plots',len({l for l,c,s,v in h if '豆类' in cats[c]}),d['summary']['bean_plots'])
    eq('bean area',sum(v for l,c,s,v in h if '豆类' in cats[c]),d['summary']['bean_area_mu_times'])
    protected=json.loads((PROJECT/'audit/AUDIT-REVISIT-v1/protected_before.json').read_text(encoding='utf-8-sig'))
    mismatch=[k for k,v in protected.items() if hashlib.sha256((ROOT/k).read_bytes()).hexdigest()!=v]
    result={'method':'Original OOXML/Decimal; source rules explicitly encoded from attachment1 E2, not derived from EDA mapping','checked':'6 land groups,41 crop history groups,30 history category cells,410 coverage cells,107x4 parameter values,bean/mixed groups','failures':fail,'protected_files':len(protected),'protected_mismatches':mismatch,'independent_human_verification':False}
    (HERE/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False));assert not fail and not mismatch
if __name__=='__main__':main()
