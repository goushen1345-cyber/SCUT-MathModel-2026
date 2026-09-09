"""Independent source-XML verification; does not import builder or openpyxl."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal
import csv,hashlib,json,re,zipfile,posixpath
import xml.etree.ElementTree as ET

P=Path(__file__).resolve().parents[1];D=P/'data/candidates/G1-v1'
N={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
CHECKS=[]
def check(name,ok,detail=None):
    CHECKS.append({'check':name,'passed':bool(ok),'detail':detail})
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dec(v):return Decimal(str(v))
def table(fn):
    with (D/fn).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def coord(c):
    m=re.fullmatch('([A-Z]+)([0-9]+)',c);n=0
    for a in m[1]:n=n*26+ord(a)-64
    return n,int(m[2])
def col(n):
    s=''
    while n:n,k=divmod(n-1,26);s=chr(65+k)+s
    return s
def same(a,b):
    if isinstance(a,(Decimal,int,float)) and isinstance(b,(Decimal,int,float)):return dec(a)==dec(b)
    return a==b
def workbook(p):
    with zipfile.ZipFile(p) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(e.itertext()) if False else ''.join(t.text or '' for t in e.findall('.//s:t',N)) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',N)]
        relations={x.attrib['Id']:x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        out={}
        for s in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',N):
            target=relations[s.attrib['{'+R+'}id']];path=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            root=ET.fromstring(z.read(path));cells={}
            for c in root.findall('s:sheetData/s:row/s:c',N):
                v=c.find('s:v',N);t=c.attrib.get('t','n')
                if t=='inlineStr':value=''.join(x.text or '' for x in c.findall('.//s:t',N))
                elif v is None or v.text is None:value=None
                elif t=='s':value=shared[int(v.text)]
                elif t=='n':value=Decimal(v.text)
                else:value=v.text
                cells[c.attrib['r']]=value
            merges={}
            for m in root.findall('s:mergeCells/s:mergeCell',N):
                a,b=m.attrib['ref'].split(':');x0,y0=coord(a);x1,y1=coord(b)
                for y in range(y0,y1+1):
                    for x in range(x0,x1+1):merges[f'{col(x)}{y}']=(a,m.attrib['ref'])
            out[s.attrib['name']]={'cells':cells,'merges':merges}
        return out
def raw(ws,c):return ws['cells'].get(c)
def resolved(ws,c):return raw(ws,ws['merges'].get(c,(c,None))[0])

def main():
    manifest=json.loads((D/'manifest.json').read_text(encoding='utf-8'));src=Path(manifest['source_directory'])
    books={f:workbook(src/f) for f in ('附件1.xlsx','附件2.xlsx')}
    landws=books['附件1.xlsx']['乡村的现有耕地'];cropws=books['附件1.xlsx']['乡村种植的农作物']
    histws=books['附件2.xlsx']['2023年的农作物种植情况'];parws=books['附件2.xlsx']['2023年统计的相关数据']
    check('all_six_source_hashes',all(sha(src/f)==h for f,h in manifest['source_hashes'].items()))
    check('all_candidate_manifest_hashes',all(sha(D/f)==h for f,h in manifest['files'].items()))
    check('builder_hash',sha(P/manifest['builder']['path'])==manifest['builder']['sha256'])
    ts={fn:table(fn) for fn in manifest['row_counts']}
    check('expected_row_counts',{k:len(v) for k,v in ts.items()}=={'lands.csv':54,'crops.csv':41,'planting_2023.csv':87,'parameters_original.csv':107,'parameters_effective.csv':125,'production_2023.csv':47,'coverage.csv':59})
    faults=[]
    fieldsets={'lands.csv':['land_id','land_type','area_mu'],'crops.csv':['crop_id','crop_name','crop_type','suitable_land_text','notes'],
        'planting_2023.csv':['land_id','crop_id','crop_name','crop_type','area_mu','season'],
        'parameters_original.csv':['source_sequence','crop_id','crop_name','land_type','season','yield_jin_per_mu','cost_yuan_per_mu','price_interval_raw']}
    trimmed={'land_id','land_type','crop_name','crop_type','season'}
    for fn,fields in fieldsets.items():
        seen=[]
        for row in ts[fn]:
            ws=books[row['source_file']][row['source_sheet']];r=int(row['source_row']);seen.append(r)
            refs=json.loads(row['source_cells_json'])
            for i,f in enumerate(fields,1):
                c=f'{col(i)}{r}';anchor,merge=ws['merges'].get(c,(c,None));actual=raw(ws,c);val=raw(ws,anchor);ref=refs[f]
                if not (ref['cell']==c and ref['anchor']==anchor and ref['merged_range']==merge and same(ref['raw_value'],actual) and same(ref['anchor_value'],val)):faults.append([fn,r,f,'provenance'])
                expected=val.strip() if f in trimmed and isinstance(val,str) else val
                if isinstance(expected,Decimal):ok=dec(row[f])==expected
                else:ok=row[f]==('' if expected is None else expected)
                if not ok:faults.append([fn,r,f,'value'])
        check(fn+'_no_source_row_loss_or_duplication',len(seen)==len(set(seen)) and sorted(seen)==list(range(2,len(seen)+2)))
    check('all_raw_values_anchors_and_clean_fields_match_XML',not faults,faults[:20])
    lands={r['land_id']:r for r in ts['lands.csv']};crops={r['crop_id']:r for r in ts['crops.csv']}
    check('unique_land_crop_ids',len(lands)==54 and len(crops)==41)
    check('bean_flags_match_source_types',all((r['is_legume']=='true')==('豆类' in r['crop_type']) for r in crops.values()))
    orig={r['record_id']:r for r in ts['parameters_original.csv']};eff={r['record_id']:r for r in ts['parameters_effective.csv']}
    pkeys={(r['crop_id'],r['land_type'],r['season']) for r in eff.values()}
    # Explicit ID ranges cross-checked against source crop labels and Attachment 1 notes.
    expected={(str(i),lt,'单季') for i in range(1,16) for lt in ('平旱地','梯田','山坡地')}
    expected.add(('16','水浇地','单季'))
    expected|={(str(i),lt,'第一季') for i in range(17,35) for lt in ('水浇地','普通大棚','智慧大棚')}
    expected|={(str(i),'智慧大棚','第二季') for i in range(17,35)}
    expected|={(str(i),'水浇地','第二季') for i in range(35,38)}
    expected|={(str(i),'普通大棚','第二季') for i in range(38,42)}
    check('125_unique_keys_match_explicit_eligibility',len(eff)==125 and len(pkeys)==125 and pkeys==expected)
    check('all_107_original_parameters_retained',all(all(eff[k][f]==v for f,v in r.items()) for k,r in orig.items()))
    inherited=[r for r in eff.values() if r['origin']=='derived_from_note'];errors=[]
    note=raw(parws,'B111')
    for r in inherited:
        parent=orig.get(r['derived_from_record_id']);ok=bool(parent)
        if ok:
            ok=(parent['land_type']=='普通大棚' and r['land_type']=='智慧大棚' and parent['season']==r['season']=='第一季'
                and all(r[f]==parent[f] for f in parent if f not in ('record_id','land_type'))
                and r['rule_source']=='附件2.xlsx/2023年统计的相关数据!B111')
        if not ok:errors.append(r['record_id'])
    check('18_inherited_parameters_have_correct_source_and_note',len(inherited)==18 and not errors and '均与普通大棚相同' in note,errors)
    price_errors=[]
    for r in eff.values():
        lo,hi=map(Decimal,r['price_interval_raw'].split('-'))
        if not (dec(r['price_lower_yuan_per_jin'])==lo and dec(r['price_upper_yuan_per_jin'])==hi and dec(r['price_midpoint_candidate_yuan_per_jin'])*2==lo+hi and lo>0 and hi>=lo):price_errors.append(r['record_id'])
    check('all_price_endpoints_and_midpoints_exact',not price_errors,price_errors)
    # Compute historical outputs from source XML, looking up ORIGINAL parameter rows.
    rawlands={str(raw(landws,f'A{r}')):str(raw(landws,f'B{r}')).strip() for r in range(2,56)}
    rawparams={(str(raw(parws,f'B{r}')),str(raw(parws,f'D{r}')).strip(),str(raw(parws,f'E{r}'))):(r,raw(parws,f'F{r}')) for r in range(2,109)}
    expected_aggregate=defaultdict(Decimal);expected_areas=defaultdict(Decimal);expected_ids=defaultdict(list);row_results={};areas=defaultdict(Decimal)
    for r in range(2,89):
        lid=resolved(histws,f'A{r}');cid=str(raw(histws,f'B{r}'));season=raw(histws,f'F{r}');area=raw(histws,f'E{r}');lt=rawlands[lid]
        lookup=(cid,'普通大棚' if lt=='智慧大棚' and season=='第一季' else lt,season)
        pr,y=rawparams[lookup];v=area*y;hid=f'H{r:03}';ref=f'I{int(cid):02}' if lt=='智慧大棚' and season=='第一季' else f'P{pr:03}'
        row_results[hid]={'source_history_row':r,'source_parameter_row':pr,'area_mu':str(area),'yield_jin_per_mu':str(y),'production_estimate_jin':str(v),'parameter_record_id':ref}
        expected_aggregate[(cid,season)]+=v;expected_areas[(cid,season)]+=area;expected_ids[(cid,season)].append(hid);areas[(lid,season)]+=area
    htable={h['record_id']:h for h in ts['planting_2023.csv']}
    check('all_87_production_estimates_recomputed_from_XML',all(dec(htable[k]['production_estimate_jin'])==dec(v['production_estimate_jin']) and htable[k]['parameter_record_id']==v['parameter_record_id'] for k,v in row_results.items()))
    check('2023_year_and_single_season_preserved',all(h['planting_year']=='2023' and h['template_season']==('第一季' if h['season']=='单季' else h['season']) for h in htable.values()))
    check('all_land_season_areas_equal_land_area',all(a==dec(lands[l]['area_mu']) for (l,s),a in areas.items()))
    check('physical_area_and_sown_area',sum(dec(l['area_mu']) for l in lands.values())==1213 and sum(areas.values())==1292)
    production={(r['crop_id'],r['season']):r for r in ts['production_2023.csv']};aggregate_errors=[]
    for k,r in production.items():
        cs=json.loads(r['contributions_json']);ids=[c['history_record_id'] for c in cs]
        ok=(dec(r['production_estimate_jin'])==expected_aggregate[k] and dec(r['planted_area_mu'])==expected_areas[k] and sorted(ids)==sorted(expected_ids[k]))
        ok=ok and all(c['parameter_record_id']==row_results[c['history_record_id']]['parameter_record_id'] and dec(c['production_estimate_jin'])==dec(row_results[c['history_record_id']]['production_estimate_jin']) and dec(c['area_mu'])==dec(row_results[c['history_record_id']]['area_mu']) for c in cs)
        if not ok:aggregate_errors.append(k)
    check('47_aggregates_and_all_contribution_lineage',set(production)==set(expected_aggregate) and not aggregate_errors,aggregate_errors)
    coverage={(r['crop_id'],r['season']):r for r in ts['coverage.csv']};unseen={k for k in coverage if k not in expected_aggregate}
    covok=set(coverage)=={(i,s) for i,l,s in expected}
    for k,r in coverage.items():
        covok=covok and r['normal_sales_limit_jin']=='' and r['demand_status']=='unknown_not_imputed'
        covok=covok and sorted(json.loads(r['source_history_ids_json']))==sorted(expected_ids.get(k,[]))
        covok=covok and set(json.loads(r['eligible_parameter_ids_json']))=={v['record_id'] for v in eff.values() if (v['crop_id'],v['season'])==k}
        covok=covok and ((r['historical_planting_status']=='unobserved' and r['production_estimate_jin']=='') if k in unseen else (r['historical_planting_status']=='observed' and dec(r['production_estimate_jin'])==expected_aggregate[k]))
    check('59_demands_unknown_12_unobserved_not_zero',covok and len(unseen)==12)
    m=json.loads((D/'template_mapping.json').read_text(encoding='utf-8'));maperrors=[]
    for fn,years in m['templates'].items():
        book=workbook(src/'附件3'/fn)
        if set(years)!=set(str(y) for y in range(2024,2031)):maperrors.append([fn,'years'])
        for y,spec in years.items():
            ws=book[y]
            for cid,c in spec['crop_columns'].items():
                if str(raw(ws,c+'1')).strip()!=crops[cid]['crop_name']:maperrors.append([fn,y,cid])
            for season,lrs in spec['land_rows_by_template_season'].items():
                for lid,r in lrs.items():
                    if raw(ws,f'B{r}')!=lid or ('第一季' if r<56 else '第二季')!=season:maperrors.append([fn,y,lid])
            if len(spec['crop_columns'])!=41 or sum(len(v) for v in spec['land_rows_by_template_season'].values())!=82:maperrors.append([fn,y,'coverage'])
    check('Q1_template_mapping_all_14_sheets',set(m['templates'])=={'result1_1.xlsx','result1_2.xlsx'} and not maperrors,maperrors[:10])
    logs=[json.loads(x) for x in (D/'transform_log.jsonl').read_text(encoding='utf-8').splitlines()];lc=Counter(x['operation'] for x in logs)
    merged_h=[x for x in logs if x['operation']=='P02_merged_anchor' and x['record_id'].startswith('H') and x['field']=='land_id']
    check('transform_log_counts',len(logs)==manifest['transform_event_count'] and len(merged_h)==33 and lc['P03_explicit_note_reference']==18 and lc['P04_interval_and_midpoint']==107 and lc['P05_production_estimate']==87,dict(lc))
    check('source_hashes_after_verification',all(sha(src/f)==h for f,h in manifest['source_hashes'].items()))
    examples={k:row_results[k] for k in ('H028','H070','H075')}
    validation={'candidate_id':'G1-v1','status':'PASS' if all(c['passed'] for c in CHECKS) else 'FAIL',
        'method':'Independent OOXML XML parsing and Decimal arithmetic; no builder import or openpyxl.',
        'verifier_sha256':sha(Path(__file__)),'source_hashes':manifest['source_hashes'],'manifest_sha256':sha(D/'manifest.json'),
        'checks':CHECKS,'manual_arithmetic_examples_for_human_review':examples,
        'production_total_estimate_jin':str(sum(expected_aggregate.values())),
        'human_verification':'pending; all checks above executed by AI/tools',
        'limitations':['No market-demand inference','No full rotation/spatial feasibility certification','No optimization','No data freeze']}
    with (D/'validation.json').open('x',encoding='utf-8') as f:json.dump(validation,f,ensure_ascii=False,indent=2)
    print(json.dumps({'status':validation['status'],'checks':len(CHECKS),'failed':[c for c in CHECKS if not c['passed']],
        'examples':examples,'production_total_estimate_jin':validation['production_total_estimate_jin']},ensure_ascii=False,indent=2))
    assert validation['status']=='PASS','Independent verification failed; inspect before use'

if __name__=='__main__':main()
