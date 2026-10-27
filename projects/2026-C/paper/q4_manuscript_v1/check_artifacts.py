"""Read-only evidence and rendered-PDF consistency checks; no model computation."""
from pathlib import Path
import hashlib,json,re
import pdfplumber
HERE=Path(__file__).resolve().parent
P=HERE.parents[1]
manifest=json.loads((HERE/'source_manifest.json').read_text(encoding='utf-8'))
for name,expected in manifest['inputs'].items():
    assert hashlib.sha256((P/name).read_bytes()).hexdigest()==expected,name
for name,expected in manifest['outputs'].items():
    assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==expected,name
assert hashlib.sha256((HERE/'prepare.py').read_bytes()).hexdigest()==manifest['code_sha256']
f=json.loads((HERE/'paper_findings.json').read_text(encoding='utf-8'))
for key in ['q42_selected','q43_selected']:
    row=f[key]
    assert abs(row['ordinary_cost']+row['adjustment_cost']+row['emergency_cost']-row['total_cost'])<1e-6
assert abs(f['q42_selected']['total_cost']-14248570.873613387)<1e-6
assert abs(f['q43_selected']['total_cost']-13822901.349092131)<1e-6
state_hash=hashlib.sha256((P/'state/state.json').read_bytes()).hexdigest()
assert state_hash==f['state_sha256']
pdf=HERE/'问题四的模型建立与求解.pdf'
with pdfplumber.open(pdf) as doc:
    pages=[page.extract_text() or '' for page in doc.pages]
text='\n'.join(pages)
assert len(pages)==8,len(pages)
for key in ['14248570.87','13822901.35','0.60','0.70','268515.82','635048.55','模型求解','参考文献']:
    assert key in text,key
for key in ['G0','Skill','审批','P2-full','run_compare','WAIT_D','候选待填','\ufffd']:
    assert key not in text,key
tex=(HERE/'问题四的模型建立与求解.tex').read_text(encoding='utf-8')
assert '\\begin{document}' in tex and len(tex)>10000
log=(HERE/'build/pass2.txt').read_text(encoding='utf-8',errors='replace')
assert 'Overfull' not in log
assert 'There were undefined references' not in log
assert 'undefined on input line' not in log
assert 'Missing character' not in log
report=P/'paper_evidence/问题四模型与论文详细讲解报告.md'
assert report.is_file()
result={'scope':'writing QA only','pdf_pages':len(pages),'page_text_lengths':[len(x) for x in pages],
 'inputs_checked':len(manifest['inputs']),'figures_checked':len(manifest['outputs']),
 'state_unchanged':True,'state_sha256':state_hash,'primary_totals_match_saved_evidence':True,
 'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),
 'no_overfull_or_missing_glyph_or_undefined_reference':True,
 'visual_review':'See visual_qa.md for actual assistant page inspection; no human approval implied',
 'new_model_fits':0,'new_optimization_solves':0}
(HERE/'qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
