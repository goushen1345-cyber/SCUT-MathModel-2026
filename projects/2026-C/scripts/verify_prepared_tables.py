"""Verify saved CSVs against source XLSX XML independently of the builder.

No imports from prepare_source_tables, no workbook editing or computation model.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[1]
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def check(condition,message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xml_cells(path,sheet):
    with zipfile.ZipFile(path) as archive:
        book=ET.fromstring(archive.read('xl/workbook.xml'))
        props=book.find('s:workbookPr',NS)
        check(props is None or props.attrib.get('date1904','0') in ('0','false'),'Unsupported date epoch')
        sheet_rid=next(s for s in book.find('s:sheets',NS) if s.attrib['name']==sheet).attrib[RID]
        targets={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        target=targets[sheet_rid]
        target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
        shared=[]
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared=[''.join(s.itertext()) for s in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        result={}
        for cell in ET.fromstring(archive.read(target)).findall('.//s:sheetData/s:row/s:c',NS):
            address=cell.attrib['r']
            kind=cell.attrib.get('t','n')
            check(cell.find('s:f',NS) is None,f'Unexpected input formula {sheet}:{address}')
            v=cell.find('s:v',NS)
            if kind=='s':
                value=shared[int(v.text)]
            elif kind=='inlineStr':
                value=''.join(n.text or '' for n in cell.findall('.//s:t',NS))
            else:
                value=v.text if v is not None else ''
            result[address]=(kind,value)
        return result


def coordinates(address):
    letters,row=re.fullmatch(r'([A-Z]+)(\d+)',address).groups()
    col=0
    for c in letters:
        col=col*26+ord(c)-64
    return int(row),col


def colname(c):
    letters=''
    while c:
        c,r=divmod(c-1,26)
        letters=chr(65+r)+letters
    return letters


def original_day(cell):
    kind,value=cell
    if kind=='n':
        serial=Decimal(value)
        check(serial==int(serial),'Unexpected intraday date value')
        return (datetime(1899,12,30)+timedelta(days=int(serial))).date()
    parts=list(map(int,re.findall(r'\d+',value)))
    check(len(parts)==3,f'Unexpected source date {value}')
    return datetime(*parts).date()


def original_minute(cell):
    kind,value=cell
    if kind=='n':
        minutes=Decimal(value)*1440
        result=int(minutes.to_integral_value())
        check(abs(minutes-result)<Decimal('0.000001'),'Source time not an exact minute')
        return result
    parts=re.fullmatch(r'(\d+):(\d+)(\+1)?',value)
    check(parts is not None,f'Bad time text {value}')
    return int(parts[1])*60+int(parts[2])+(1440 if parts[3] else 0)


def expected_time_label(cell):
    if cell[0]=='n':
        m=original_minute(cell)
        return f'{m//60:02d}:{m%60:02d}:00','time'
    return cell[1],'str'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',default='data/prepared-v1')
    parser.add_argument('--output',default='audit/prepared_v1_verification.json')
    args=parser.parse_args()
    folder=(ROOT/args.input).resolve()
    output=(ROOT/args.output).resolve()
    check(ROOT in folder.parents and ROOT in output.parents,'Paths must remain within project')
    check(not output.exists(),'Refusing to overwrite prior verification')
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    audit=json.loads((ROOT/'audit/data_audit_v1.json').read_text(encoding='utf-8'))
    check(manifest['raw_sha256']==audit['source_sha256'],'Source manifest differs from approved input')
    for p,h in manifest['raw_sha256'].items():
        check(sha(ROOT/p)==h,f'Original changed: {p}')
    check(sha(ROOT/manifest['script'])==manifest['script_sha256'],'Builder script changed')
    check(sha(folder/'README.md')==manifest['readme_sha256'],'Readme changed')
    raw={sid:xml_cells(ROOT/item['path'],item['sheet']) for sid,item in manifest['sources'].items()}
    expected={
        'annex1':{f'{colname(c)}{r}' for r in range(2,146) for c in range(2,5)},
        'annex2_load':{f'{colname(c)}{r}' for r in range(2,367) for c in range(2,146)},
        'annex2_pv':{f'{colname(c)}{r}' for r in range(2,367) for c in range(2,146)},
        'annex3':{f'{colname(c)}{r}' for r in range(2,1462) for c in range(3,27)},
        'annex4':{f'{colname(c)}{r}' for r in range(2,367) for c in range(2,146)},
    }
    seen={sid:set() for sid in expected}
    zero_source=Counter()
    zero_output=Counter()
    keys={}
    source_values_checked=0
    def number(sid,address,value):
        nonlocal source_values_checked
        check(address in expected[sid],f'Unexpected numeric source {sid}:{address}')
        check(address not in seen[sid],f'Duplicated numeric source {sid}:{address}')
        kind,original=raw[sid][address]
        check(kind=='n' and value==original,f'Numeric text altered {sid}:{address}')
        check(Decimal(value).is_finite(),f'Nonfinite value {sid}:{address}')
        zero_source[sid]+=Decimal(original)==0
        zero_output[sid]+=Decimal(value)==0
        seen[sid].add(address)
        source_values_checked+=1
    def matrix_label(record,sid,prefix,value_field):
        cell=record[prefix+'value_cell']
        row,col=coordinates(cell)
        check(record[prefix+'source_id']==sid,'Wrong source identity')
        check(record[prefix+'date_cell']==f'A{row}' and record[prefix+'time_cell']==f'{colname(col)}1','Source row/column mismatch')
        d=original_day(raw[sid][f'A{row}'])
        m=original_minute(raw[sid][f'{colname(col)}1'])
        t,kind=expected_time_label(raw[sid][f'{colname(col)}1'])
        check(record['source_date']==d.isoformat() and int(record['source_minute'])==m,'Date/time shifted')
        check(record['source_time_label']==t and record['source_time_type']==kind,'Original time label/type not retained')
        check(record['source_date_label']==d.isoformat()+'T00:00:00' and record['source_date_type']=='datetime','Original date label/type not retained')
        number(sid,cell,record[value_field])
        return d.isoformat(),m
    expected_rows={'day_reference.csv':144,'actual_power.csv':52560,'actual_price.csv':52560,'pv_forecasts.csv':35040}
    counts={}
    midnight_count=Counter()
    release_counts=Counter()
    inherited_source_rows=set()
    no_actual_labels=0
    target_2026=0
    actual_labels=set()
    for name in expected_rows:
        path=folder/name
        check(sha(path)==manifest['outputs'][name]['sha256'],f'Output hash mismatch: {name}')
        filekeys=set()
        n=0
        with path.open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream)
            check(reader.fieldnames==manifest['outputs'][name]['columns'],'Header mismatch')
            for rec in reader:
                n+=1
                if name=='day_reference.csv':
                    r=int(rec['slot_index'])+1
                    check(rec['source_id']=='annex1' and rec['time_cell']==f'A{r}','Reference source mismatch')
                    t,kind=expected_time_label(raw['annex1'][f'A{r}'])
                    m=original_minute(raw['annex1'][f'A{r}'])
                    check(rec['source_time_label']==t and rec['source_time_type']==kind and int(rec['source_minute'])==m,'Reference time mismatch')
                    for field,col in [('price','B'),('load','C'),('pv_forecast','D')]:
                        check(rec[field+'_cell']==f'{col}{r}','Reference numeric shift')
                        valuefield='price_yuan_per_kwh' if field=='price' else field+'_kw'
                        number('annex1',rec[field+'_cell'],rec[valuefield])
                    key=m
                    midnight_count[name]+=m==1440
                elif name=='actual_power.csv':
                    key=matrix_label(rec,'annex2_load','load_','load_kw')
                    other=matrix_label(rec,'annex2_pv','pv_','pv_actual_kw')
                    check(key==other,'Wrong actual-power join')
                    actual_labels.add(datetime.fromisoformat(key[0])+timedelta(minutes=key[1]))
                    midnight_count[name]+=key[1]==1440
                elif name=='actual_price.csv':
                    key=matrix_label(rec,'annex4','','price_yuan_per_kwh')
                    midnight_count[name]+=key[1]==1440
                else:
                    check(rec['source_id']=='annex3','Wrong forecast identity')
                    row,col=coordinates(rec['value_cell'])
                    group_row=2+((row-2)//4)*4
                    check(rec['group_date_cell']==f'A{group_row}' and rec['row_date_cell']==f'A{row}' and rec['release_cell']==f'B{row}','Forecast provenance mismatch')
                    d=original_day(raw['annex3'][f'A{group_row}'])
                    m=original_minute(raw['annex3'][f'B{row}'])
                    release=datetime.combine(d,datetime.min.time())+timedelta(minutes=m)
                    lead=col-2
                    target=release+timedelta(hours=lead)
                    check(rec['release_datetime']==release.isoformat() and int(rec['lead_hours'])==lead and rec['target_datetime']==target.isoformat(),'Forecast release/target shifted')
                    check(rec['source_date_label']==raw['annex3'][f'A{group_row}'][1] and rec['source_date_type']=='str','Group date original not preserved')
                    row_label=raw['annex3'].get(f'A{row}',('inlineStr',''))[1]
                    check(rec['source_row_date_label']==row_label,'Blank original date not preserved')
                    inherited=int(row_label=='')
                    check(int(rec['date_inherited'])==inherited,'Wrong inherited-date flag')
                    if inherited:
                        inherited_source_rows.add(row)
                    t,kind=expected_time_label(raw['annex3'][f'B{row}'])
                    check(rec['source_release_label']==t and rec['source_release_type']==kind,'Release label not preserved')
                    available=int(target in actual_labels)
                    check(int(rec['has_actual_target_label'])==available,'Incorrect target coverage flag')
                    no_actual_labels+=not available
                    target_2026+=target.year==2026
                    release_counts[release.isoformat()]+=1
                    number('annex3',rec['value_cell'],rec['pv_forecast_kw'])
                    key=release.isoformat(),lead
                check(key not in filekeys,f'Duplicate output key: {name}:{key}')
                filekeys.add(key)
        check(n==expected_rows[name] and n==manifest['outputs'][name]['rows'],f'Wrong count: {name}')
        counts[name]=n
        keys[name]=filekeys
    check(keys['day_reference.csv']==set(range(10,1441,10)),'Incomplete reference day')
    dates=[(datetime(2025,1,1)+timedelta(days=d)).date().isoformat() for d in range(365)]
    expected_actual={(d,m) for d in dates for m in range(10,1441,10)}
    check(keys['actual_power.csv']==expected_actual==keys['actual_price.csv'],'Incomplete actual date/time grid')
    expected_releases={(datetime.fromisoformat(d)+timedelta(hours=h)).isoformat() for d in dates for h in [0,6,12,18]}
    check(set(release_counts)==expected_releases and set(release_counts.values())=={24},'Forecast batch coverage wrong')
    check(len(inherited_source_rows)==1095 and no_actual_labels==36 and target_2026==40,'Forecast boundary/grouping mismatch')
    for sid in expected:
        check(seen[sid]==expected[sid],f'Omitted numeric source cells: {sid}')
    check(source_values_checked==193152 and zero_source==zero_output,'Numeric count/zero preservation mismatch')
    for p,h in manifest['raw_sha256'].items():
        check(sha(ROOT/p)==h,f'Original changed during verification: {p}')
    check(set(p.name for p in folder.iterdir())==set(expected_rows)|{'README.md','manifest.json'},'Unexpected candidate artifacts')
    result={'verified_at':datetime.now().astimezone().isoformat(),'method':'Independent XLSX XML reader; all saved CSV numeric strings and source keys checked, no builder imports','candidate':folder.relative_to(ROOT).as_posix(),'manifest_sha256':sha(folder/'manifest.json'),'verifier_script_sha256':sha(Path(__file__)),'row_counts':counts,'source_numeric_cells_checked':source_values_checked,'numeric_changes':0,'duplicate_or_missing_source_numeric_cells':0,'original_files_unchanged':len(manifest['raw_sha256']),'all_source_numeric_texts_exact':True,'all_date_time_labels_and_joins_checked':True,'midnight_labels_retained':dict(midnight_count),'inherited_date_source_rows':len(inherited_source_rows),'forecast_batches':len(release_counts),'forecast_target_labels_in_2026':target_2026,'forecast_records_without_actual_target_label':no_actual_labels,'zero_counts_preserved_by_source':dict(zero_source),'passed':True,'human_verification':'not performed','data_frozen':False,'limitations':['source labels only; physical interval meaning not selected','hourly interpolation and energy conversion not performed','CSV information-role labels do not enforce causal model access','no validation of physical measurement truth or forecast skill']}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
