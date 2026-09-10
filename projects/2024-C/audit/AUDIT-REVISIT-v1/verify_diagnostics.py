"""Independent ZIP/XML checks of selected key, area, price and template claims."""
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from collections import defaultdict, Counter
from decimal import Decimal
import hashlib,json,csv

HERE=Path(__file__).resolve().parent;PROJECT=HERE.parents[1];ROOT=PROJECT.parents[1]
RAW=ROOT/'培训作业/第四次培训作业';NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def read_xml_book(path):
    with ZipFile(path) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        rels={x.attrib['Id']:x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        result={}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS):
            target=rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            path=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            root=ET.fromstring(z.read(path));cells={}
            for c in root.findall('.//s:sheetData/s:row/s:c',NS):
                v=c.find('s:v',NS)
                if c.attrib.get('t')=='s' and v is not None:val=shared[int(v.text)]
                elif c.attrib.get('t')=='inlineStr':val=''.join(c.find('s:is',NS).itertext())
                else:val=v.text if v is not None else None
                cells[c.attrib['r']]=val
            result[sheet.attrib['name']]={'cells':cells,'merges':[x.attrib['ref'] for x in root.findall('s:mergeCells/s:mergeCell',NS)],'state':sheet.attrib.get('state','visible')}
        return result

def main():
    a=read_xml_book(RAW/'附件1.xlsx');b=read_xml_book(RAW/'附件2.xlsx')
    lc=a['乡村的现有耕地']['cells'];cc=a['乡村种植的农作物']['cells'];hs=b['2023年的农作物种植情况'];pc=b['2023年统计的相关数据']['cells']
    lands={lc[f'A{r}'].strip():(lc[f'B{r}'].strip(),Decimal(lc[f'C{r}'])) for r in range(2,56)}
    crops=[cc[f'B{r}'].strip() for r in range(2,43)]
    merged={}
    for m in hs['merges']:
        start,end=m.split(':');lo=int(start[1:]);hi=int(end[1:])
        for r in range(lo,hi+1):merged[f'A{r}']=start
    sums=defaultdict(Decimal)
    for r in range(2,89):
        pos=f'A{r}';land=hs['cells'][merged.get(pos,pos)].strip();season=hs['cells'][f'F{r}'].strip()
        sums[(land,season)]+=Decimal(hs['cells'][f'E{r}'])
    direct=json.loads((HERE/'diagnostic_details.json').read_text(encoding='utf-8'))
    recorded={(x['land'],x['season']):Decimal(x['sum_original_area_mu']) for x in direct['area_capacity_checks']}
    price_bad=[]
    for r in range(2,109):
        values=pc[f'H{r}'].strip().split('-')
        if len(values)!=2 or not Decimal(values[1])>=Decimal(values[0])>0:price_bad.append(f'H{r}')
    templates=[]
    for p in (RAW/'附件3').glob('*.xlsx'):
        for year,s in read_xml_book(p).items():
            cells=s['cells'];first=[cells[f'B{r}'].strip() for r in range(2,56)];second=[cells[f'B{r}'].strip() for r in range(56,84)]
            expected_second={k for k,(typ,area) in lands.items() if typ in ['水浇地','普通大棚','智慧大棚']}
            def col(i):
                out=''
                while i:i,j=divmod(i-1,26);out=chr(65+j)+out
                return out
            names=[cells[f'{col(i)}1'].strip() for i in range(3,44)]
            templates.append({'file':p.name,'year':year,'first_season_exact_land_set':set(first)==set(lands) and len(first)==54,
              'second_season_exact_land_set':set(second)==expected_second and len(second)==28,'all_crop_columns_order_match':names==crops,
              'notes_present':all(cells.get(f'B{i}') for i in [85,86,87]),'sheet_state':s['state']})
    with (PROJECT/'data/frozen/G1-v1-base/coverage.csv').open(encoding='utf-8-sig',newline='') as f:old=list(csv.DictReader(f))
    source_manifest=json.loads((PROJECT/'paper/understanding_v2/source_manifest.json').read_text(encoding='utf-8'))['sha256']
    originals=[]
    for p in [RAW/'C题.pdf',*RAW.rglob('*.xlsx')]:
        key=str(p.relative_to(ROOT)).replace('\\','/');originals.append({'path':key,'matches_v2_reading_source':hashlib.sha256(p.read_bytes()).hexdigest()==source_manifest.get(key)})
    sales_mentions=[{'sheet':sheet,'cell':k,'text':v} for book in [a,b] for sheet,s in book.items() for k,v in s['cells'].items() if isinstance(v,str) and any(x in v for x in ['销量','销售','需求'])]
    checks={'xml_land_count':len(lands),'xml_crop_count':len(crops),'xml_history_rows':87,'xml_area_groups':len(sums),
      'xml_matches_openpyxl_area_groups':sums==recorded,'xml_area_groups_over_capacity':[str(k) for k,v in sums.items() if v>lands[k[0]][1]],
      'xml_price_interval_failures':price_bad,'xml_template_checks':templates,'raw_sources_match_first_stage_v2':originals,
      'old_coverage_rows':len(old),'old_sales_upper_limits_blank':sum(x['normal_sales_limit_jin']=='' for x in old),
      'sales_related_source_cells':sales_mentions,'method':'Independent XML of source workbooks; old coverage fields read, no production/midpoint recomputation.'}
    (HERE/'independent_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in checks.items() if k not in ['xml_template_checks','sales_related_source_cells']},ensure_ascii=False))

if __name__=='__main__':main()
