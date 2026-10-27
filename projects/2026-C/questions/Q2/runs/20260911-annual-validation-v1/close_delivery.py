"""Final manifest, source protection and record checks; Python standard library."""
from pathlib import Path
import json,hashlib,subprocess,sys
R=Path(__file__).resolve().parent;P=R.parents[3];OLD=R.parent/'20260911-four-candidates-v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=read(P/'data/prepared-v1/manifest.json')
for rel,h in manifest['raw_sha256'].items():assert sha(P/rel)==h,rel
for rel,h in read(OLD/'outputs/source_hashes.json').items():assert sha(P/rel)==h,rel
for rel,h in read(OLD/'outputs/output_hashes.json').items():assert sha(OLD/'outputs'/rel)==h,rel
for folder in ['annual','validation','refinement','supplement']:
 for rel,h in read(R/folder/'output_hashes.json').items():assert sha(R/folder/rel)==h,(folder,rel)
q2paper=P/'paper/q2_comparison_manuscript_v1';br=read(q2paper/'build_record.json');assert sha(q2paper/'论文草稿_含问题二候选比较.pdf')==br['pdf_sha256']
v1=read(R/'verification.json');v2=read(R/'delivery_verification.json');assert v1['status']==v2['status']=='passed';assert sha(R/'deliverables/result2.xlsx')==v2['saved_xlsx']['sha256']
s=read(P/'state/state.json');assert s['revision']==37 and s['stage']=='WAIT_D' and s['active_question']=='Q1';assert s['questions']['Q1']['frozen_version'] is None and s['questions']['Q2']['frozen_version'] is None;assert s['questions']['Q2']['depends_on']==[{'question':'Q1','version':None}]
summary=read(R/'delivery_data/summary.json');assert summary['actual_research_lp']==8156 and summary['official_days']==334;assert abs(summary['total_official_cost']-13583810.841364944)<1e-6
records=['questions/Q2/report.md','questions/Q2/experiments.md','paper_evidence/Q2.md','paper_evidence/问题二论文框架.md','paper_evidence/figure_registry.md','report.md','state/decisions.md','state/ai_usage_log.md','state/state.json','state/state.md']
for rel in records:assert (P/rel).is_file(),rel
assert 'Q2-annual-v4' in (P/records[0]).read_text(encoding='utf-8');assert 'Q2-ANNUAL-DELIVER-051' in (P/'state/decisions.md').read_text(encoding='utf-8')
rc=subprocess.run([sys.executable,str(P.parents[1]/'workflow/scripts/statectl.py'),'validate',str(P)],capture_output=True,text=True,encoding='utf-8');assert rc.returncode==0,rc.stdout+rc.stderr
files=[p for p in R.iterdir() if p.is_file() and p.name!='delivery_manifest.json']
for name in ['annual','validation','refinement','supplement','delivery_data','deliverables','previews']:files.extend(p for p in (R/name).rglob('*') if p.is_file())
out={'status':'completed','authorization':'Q2-ANNUAL-050','user_approval_of_outline':False,'model_frozen':False,'state_revision':37,'official_334day_cost':summary['total_official_cost'],'research_lp_calls':8156,'new_fits':104,'research_seconds':sum(read(R/f/'summary.json')['seconds'] for f in ['annual','validation','refinement','supplement']),'all10_original_files_unchanged':True,'old157_outputs_unchanged':True,'q1_and_old_q2_pdf_unchanged':True,'no_new_manuscript':True,'xlsx_visual_views':['result_purchase','result_midnight','result_last_dates','result_storage','result_emergency'],'xlsx_visual_findings':'Actual images inspected; same-civil-date midnight explicit; readable dates/values, no clipping. Extended emergency rows realigned before final export and independent saved-file verification.','ai_verification_not_human_review':True,'files':{str(p.relative_to(R)):sha(p) for p in sorted(set(files))},'project_record_hashes':{r:sha(P/r) for r in records}}
(R/'delivery_manifest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in out.items() if k not in ['files','project_record_hashes']},ensure_ascii=False))
