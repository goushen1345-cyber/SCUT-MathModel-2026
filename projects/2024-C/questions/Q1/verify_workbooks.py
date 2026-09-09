"""Independent OOXML verification of the two Q1 draft workbooks."""
from pathlib import Path
import csv, hashlib, json, re, zipfile
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[2];Q=Path(__file__).resolve().parent;DATA=ROOT/'data/frozen/G1-v1-base';OUT=Q/'outputs/Q1-DRAFT-v1';SRC=ROOT.parents[1]/'培训作业/第四次培训作业/附件3'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','p':'http://schemas.openxmlformats.org/package/2006/relationships'}
mapping=json.loads((DATA/'template_mapping.json').read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sheets(path):
    z=zipfile.ZipFile(path);wb=ET.fromstring(z.read('xl/workbook.xml'));rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'));targets={x.attrib['Id']:x.attrib['Target'].lstrip('/') for x in rels}
    shared=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        ss=ET.fromstring(z.read('xl/sharedStrings.xml'));shared=[''.join(t.text or '' for t in si.findall('.//m:t',NS)) for si in ss.findall('m:si',NS)]
    out={}
    for s in wb.find('m:sheets',NS):
        target=targets[s.attrib['{'+NS['r']+'}id']];target=target if target.startswith('xl/') else 'xl/'+target
        out[s.attrib['name']]=ET.fromstring(z.read(target))
    return out,shared
def cellmap(xml,allowed=None):
    out={}
    for c in xml.findall('.//m:c',NS):
        ref=c.attrib['r'];v=c.find('m:v',NS)
        if v is not None and (allowed is None or allowed(ref)):out[ref]=v.text
    return out
def displaymap(xml,shared,allowed):
    out={}
    for c in xml.findall('.//m:c',NS):
        ref=c.attrib['r']
        if not allowed(ref):continue
        v=c.find('m:v',NS);inline=c.find('m:is',NS)
        if c.attrib.get('t')=='s' and v is not None:out[ref]=shared[int(v.text)]
        elif inline is not None:out[ref]=''.join(t.text or '' for t in inline.findall('.//m:t',NS))
        elif v is not None:out[ref]=v.text
    return out
def colnum(ref):
    letters=re.match(r'[A-Z]+',ref).group();n=0
    for c in letters:n=n*26+ord(c)-64
    return n
def verify(source,output,solution):
    (src,srcshared)=sheets(SRC/source);(got,gotshared)=sheets(OUT/output);assert list(src)==list(got)==[str(y) for y in mapping['years']]
    expected={str(y):{} for y in mapping['years']};mp=mapping['templates'][source]
    for r in rows(Q/'deep_runs'/solution):
        y=r['year'];season=mapping['source_season_to_template_season'][r['season']];row=mp[y]['land_rows_by_template_season'][season][r['land_id']];col=mp[y]['crop_columns'][r['crop_id']];expected[y][f'{col}{row}']=float(r['area_mu'])
    checked=0
    for y in expected:
        outside=lambda ref: colnum(ref)<=2
        assert displaymap(src[y],srcshared,outside)==displaymap(got[y],gotshared,outside)
        actual={k:float(v) for k,v in cellmap(got[y],lambda ref:3<=colnum(ref)<=43 and 2<=int(re.search(r'\d+',ref).group())<=83).items()}
        assert set(actual)==set(expected[y]),(output,y,set(actual)^set(expected[y]))
        for k,v in expected[y].items():assert abs(actual[k]-v)<=1e-7,(output,y,k,actual[k],v)
        checked+=len(actual)
    return {'source':source,'source_sha256':sha(SRC/source),'output':output,'output_sha256':sha(OUT/output),'sheets':7,'nonzero_cells_checked':checked,'labels_A_B_preserved':True,'csv_values_exact':True}
checks=[verify('result1_1.xlsx','result1_1_Q1-DRAFT-v1.xlsx','M1R3-D0-S1/solution.csv'),verify('result1_2.xlsx','result1_2_Q1-DRAFT-v1.xlsx','M1R3-D0-S2/solution.csv')]
assert checks[0]['source_sha256']=='4f2484c0d70a5c4d047163f2ee6ef486949e813330466f46def4bd7d98af06af'
assert checks[1]['source_sha256']=='6166d43f5a64bf9d1657e80d4aee7f10f54bb1a5695b81a28a0ac5e657297649'
audit=json.loads((OUT/'artifact_tool_audit.json').read_text(encoding='utf-8'));error_scans=[x for x in audit if x['phase']=='formula_error_scan'];assert len(error_scans)==2
result={'protocol':'Q1-DEEPEN-v1','method':'independent zipfile/XML; does not import workbook builder or solver','checks':checks,'artifact_formula_error_scans':len(error_scans),'visual_renders_reviewed':['result1_1 2024','result1_2 2024'],'passed':True,'human_verification':'pending'}
(OUT/'workbook_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
