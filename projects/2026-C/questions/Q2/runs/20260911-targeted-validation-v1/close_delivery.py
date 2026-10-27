"""Final scientific-file and delivery-record checks; no experiment execution."""
from pathlib import Path
import json,hashlib,csv,subprocess,sys
R=Path(__file__).resolve().parent;P=R.parents[3];B=R.parent/'20260911-annual-validation-v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
src=read(R/'outputs/source_hashes.json')
for rel,h in src['previous_files'].items():assert sha(B/rel)==h,rel
for section in ['raw','oldprotected']:
 for rel,h in src[section].items():assert sha(P/rel)==h,rel
for folder in ['outputs','analysis']:
 for rel,h in read(R/folder/'output_hashes.json').items():assert sha(R/folder/rel)==h,rel
v=read(R/'verification.json');summary=read(R/'outputs/summary.json');assert v['status']=='passed' and v['lp_calls_checked']==summary['lp_calls']==2004 and summary['new_fits']==0
interpret=read(R/'interpretation.json');episodes=read(R/'outputs/episodes.json')
for r in interpret['effective_exposure']:
 es=[x for x in episodes if x['scenario']==r['scenario']];days=[y['date'] for x in es for y in x['records']];assert len(days)==r['effective_event_days'];assert [x['episode_start'] for x in es if x['source_start_day'] is None]==r['skipped_episode_dates'];assert r['no_additional_perturbation_days']==334-len(days)
 assert sum(r['effective_days_per_month'].values())==len(days);assert sum(g['days'] for g in r['groups'])==334
 for group in r['groups']:
  with (R/'analysis/paired_daily.csv').open(encoding='utf-8-sig',newline='') as h:part=[x for x in csv.DictReader(h) if x['scenario']==r['scenario'] and ((x['date'] in set(days))==group['effective_input_perturbation'])]
  assert len(part)==group['days'];assert abs(-sum(float(x['extra_cost']) for x in part)-group['paired_saving'])<1e-6
s=read(P/'state/state.json');assert s['revision']==40 and s['stage']=='WAIT_D' and s['active_question']=='Q1';assert s['questions']['Q1']['frozen_version'] is None and s['questions']['Q2']['frozen_version'] is None;assert s['questions']['Q2']['depends_on']==[{'question':'Q1','version':None}]
rc=subprocess.run([sys.executable,str(P.parents[1]/'workflow/scripts/statectl.py'),'validate',str(P)],capture_output=True,text=True,encoding='utf-8');assert rc.returncode==0,rc.stdout+rc.stderr
records=['questions/Q2/report.md','questions/Q2/experiments.md','paper_evidence/Q2.md','paper_evidence/问题二论文框架.md','report.md','state/decisions.md','state/ai_usage_log.md','state/state.json','state/state.md']
assert 'Q2-validation-v5' in (P/records[0]).read_text(encoding='utf-8');assert 'Q2-ROBUST-DELIVER-054' in (P/'state/decisions.md').read_text(encoding='utf-8')
files=[p for p in R.rglob('*') if p.is_file() and p.name!='delivery_manifest.json' and '__pycache__' not in p.parts]
result={'status':'completed','authorization':'Q2-ROBUST-053','state_revision':40,'research_lp_calls':2004,'new_fits':0,'research_seconds':summary['seconds'],'validation':'Independently verified numeric/information paths and saved statistics;AI not human review','actual_perturbed_days':[r['effective_event_days'] for r in interpret['effective_exposure']],'prior_scientific_files_and_all_raw_unchanged':True,'original_result2_unchanged':True,'original_334day_cost_unchanged':13583810.841364942,'no_manuscript_or_figures_created':True,'model_not_changed_or_frozen':True,'no_external_generalization_claim':True,'files':{str(p.relative_to(R)):sha(p) for p in sorted(files)},'project_record_hashes':{r:sha(P/r) for r in records}}
(R/'delivery_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k not in ['files','project_record_hashes']},ensure_ascii=False))
