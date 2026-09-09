"""Independent OOXML verification for the Q1 S1 draft v2 workbook."""
from pathlib import Path
import csv, hashlib, json, re, zipfile
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]; Q=Path(__file__).resolve().parent
DATA=ROOT/'data/frozen/G1-v1-base'; OUT=Q/'outputs/Q1-DRAFT-v2'
SRC=ROOT.parents[1]/'培训作业/第四次培训作业/附件3'; SOURCE='result1_1.xlsx'; OUTPUT='result1_1_Q1-DRAFT-v2.xlsx'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
mapping=json.loads((DATA/'template_mapping.json').read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sheets(path):
    z=zipfile.ZipFile(path); wb=ET.fromstring(z.read('xl/workbook.xml')); rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    targets={x.attrib['Id']:x.attrib['Target'].lstrip('/') for x in rels}; shared=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        ss=ET.fromstring(z.read('xl/sharedStrings.xml')); shared=[''.join(t.text or '' for t in si.findall('.//m:t',NS)) for si in ss.findall('m:si',NS)]
    out={}
    for s in wb.find('m:sheets',NS):
        target=targets[s.attrib['{'+NS['r']+'}id']]; target=target if target.startswith('xl/') else 'xl/'+target
        out[s.attrib['name']]=ET.fromstring(z.read(target))
    return out,shared
def colnum(ref):
    n=0
    for c in re.match(r'[A-Z]+',ref).group():n=n*26+ord(c)-64
    return n
def display(xml,shared,allowed):
    out={}
    for c in xml.findall('.//m:c',NS):
        ref=c.attrib['r']; v=c.find('m:v',NS); inline=c.find('m:is',NS)
        if not allowed(ref):continue
        if c.attrib.get('t')=='s' and v is not None:out[ref]=shared[int(v.text)]
        elif inline is not None:out[ref]=''.join(t.text or '' for t in inline.findall('.//m:t',NS))
        elif v is not None:out[ref]=v.text
    return out
src,srcshared=sheets(SRC/SOURCE); got,gotshared=sheets(OUT/OUTPUT)
assert list(src)==list(got)==[str(y) for y in mapping['years']]
expected={str(y):{} for y in mapping['years']}; mp=mapping['templates'][SOURCE]
for row in rows(Q/'boost_runs/BOOST-D0-S1/solution.csv'):
    y=row['year']; season=mapping['source_season_to_template_season'][row['season']]
    excelrow=mp[y]['land_rows_by_template_season'][season][row['land_id']]; col=mp[y]['crop_columns'][row['crop_id']]
    expected[y][f'{col}{excelrow}']=float(row['area_mu'])
checked=0
for y in expected:
    assert display(src[y],srcshared,lambda ref:colnum(ref)<=2)==display(got[y],gotshared,lambda ref:colnum(ref)<=2)
    actual={k:float(v) for k,v in display(got[y],gotshared,lambda ref:3<=colnum(ref)<=43 and 2<=int(re.search(r'\d+',ref).group())<=83).items()}
    assert set(actual)==set(expected[y]),(y,set(actual)^set(expected[y]))
    for key,value in expected[y].items():assert abs(actual[key]-value)<=1e-7,(y,key,actual[key],value)
    checked+=len(actual)
audit=json.loads((OUT/'artifact_tool_audit.json').read_text(encoding='utf-8')); scans=[x for x in audit if x['phase']=='formula_error_scan']; assert len(scans)==1 and 'matched 0 entries' in scans[0]['ndjson']
s2=Q/'outputs/Q1-DRAFT-v1/result1_2_Q1-DRAFT-v1.xlsx'; assert sha(s2)=='92abe652f36ae4172de4ffc654d81d12e192d847f7bb029be9c6b6ef3613e8ff'
result={'protocol':'Q1-S1-BOOST-v1','method':'independent zipfile/XML; imports neither workbook builder nor solver','source_sha256':sha(SRC/SOURCE),'output_sha256':sha(OUT/OUTPUT),'sheets':7,'nonzero_cells_checked':checked,'labels_A_B_preserved':True,'csv_values_exact':True,'formula_error_scan_passed':True,'s2_workbook_unchanged':True,'passed':True,'human_verification':'pending'}
assert result['source_sha256']=='4f2484c0d70a5c4d047163f2ee6ef486949e813330466f46def4bd7d98af06af'
(OUT/'workbook_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2))
