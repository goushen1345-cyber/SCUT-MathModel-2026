"""Check manuscript values against saved evidence; no research execution."""
from pathlib import Path
import csv,hashlib,json,re,zipfile
import pdfplumber
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
B=PROJECT/'questions/Q2/runs/20260911-annual-validation-v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((HERE/'source_manifest.json').read_text('utf-8'))
assert all(sha(PROJECT/p)==v for p,v in manifest['source_sha256'].items())
fig=json.loads((HERE/'figures/manifest.json').read_text('utf-8'))
repro=json.loads((PROJECT/'tmp/q2-manuscript-fig-reproduction-v1/manifest.json').read_text('utf-8'))
assert fig['outputs']==repro['outputs']
assert all(sha(HERE/'figures'/p)==v for p,v in fig['outputs'].items())
pdf=HERE/'问题二的模型建立与求解.pdf'
pages=[];colors=set();out_of_page=[]
with pdfplumber.open(pdf) as doc:
    for i,p in enumerate(doc.pages,1):
        pages.append(p.extract_text() or '')
        for c in p.chars:
            color=c.get('non_stroking_color');colors.add(str(color))
            if c['x0']<0 or c['x1']>p.width+.5 or c['top']<0 or c['bottom']>p.height+.5:out_of_page.append((i,c.get('text')))
assert not out_of_page,out_of_page[:10]
assert colors.issubset({'0','0.0','(0.0,)','(0,)','(0, 0, 0)','(0.0, 0.0, 0.0)'}),colors
full='\n\n'.join(pages);clean=re.sub(r'\s+','',full)
assert len(pages)==8
assert all(s not in clean for s in ['G0','Skill','WAIT_D','审批','mathbf','??'])
values=[]
def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
for name in ('specified_table1','specified_table2','specified_table3'):
    rows=read(B/f'delivery_data/{name}.csv')
    for r in rows:
        if name=='specified_table1':keys=[k for k in r if k!='date']
        elif name=='specified_table2':keys=['charge_kwh','discharge_kwh','day_start_kwh','day_end_kwh']
        else:keys=['kwh','cost']
        values += [f'{float(r[k]):.2f}' for k in keys]
for p in [B/'annual/comparison.csv',B/'refinement/comparison.csv']:
    for r in read(p):
        if r['variant'] in ('T1','T2','T3','T4','error-decay70'):
            values += [f'{float(r[k])/1e4:.2f}' for k in ['ordinary_cost','emergency_cost','total_cost']]
summary=json.loads((B/'delivery_data/summary.json').read_text('utf-8'))
for k in ['total_official_cost','ordinary_cost','emergency_cost','continuous365day_cost_including_common_january']:
    values.append(f'{summary[k]:.2f}')
assert all(v in clean for v in values),[v for v in values if v not in clean]
log=(HERE/'build/pass2.txt').read_text('utf-8',errors='replace')
assert all(t not in log for t in ['Overfull','undefined','Missing character','! '])
report=PROJECT/'paper_evidence/问题一模型详细讲解报告.md'
text=report.read_text('utf-8')
links=re.findall(r'\]\((E:/[^)]+)\)',text)
missing=[]
for link in links:
    p=re.sub(r':\d+$','',link)
    if not Path(p).exists():missing.append(p)
assert not missing,missing
assert '35126.85' in text and '333.333' in text and '第17—18节' in text
inspection=HERE/'build/visual_inspection.json'
visual=json.loads(inspection.read_text('utf-8')) if inspection.exists() else {}
current={p.name:sha(p) for p in sorted((HERE/'preview').glob('page-*.png'))}
changes=[k for k,v in current.items() if visual.get('page_sha256',{}).get(k)!=v]
qa={'source_files_unchanged':len(manifest['source_sha256']),'pdf_pages':len(pages),'values_crosschecked':len(values),
 'figures_reproduced_identically':6,'black_text_colors':sorted(colors),'out_of_page_characters':out_of_page,
 'layout_reference_errors':False,'q1_report_links_checked':len(links),'pdf_sha256':sha(pdf),
 'rendered_pages':current,'pages_needing_visual_recheck':changes,'new_solves':0,'new_fits':0,
 'review_type':'AI source and visual checks, not human approval','warnings':'MiKTeX release/font redefinition warnings; no missing glyphs or overflow. pandas optional numexpr version warning during drawing.'}
(HERE/'qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),'utf-8')
(HERE/'build/extracted_text.txt').write_text(full,'utf-8')
print(json.dumps(qa,ensure_ascii=False,indent=2))
