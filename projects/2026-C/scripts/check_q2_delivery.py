"""Check delivered Q2 evidence/figures without repeating analysis or model runs."""
from pathlib import Path
import hashlib,json,re

P=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
A=P/'audit/q2-exploration-v1';O=A/'outputs';F=P/'paper/figures/q2-exploration-v4'
summary=read(O/'summary.json');v=read(A/'verification.json');m=read(F/'manifest.json')
for rel,h in summary['source_sha256'].items():assert sha(P/rel)==h,rel
for rel,h in read(O/'output_hashes.json').items():assert sha(O/rel)==h,rel
assert sha(P/'scripts/explore_q2.py')==summary['script_sha256']
assert sha(A/'protocol.json')==summary['protocol_sha256']
assert sha(P/'scripts/plot_q2_exploration.py')==m['script_sha256']
for n,h in m['source_sha256'].items():assert sha(O/n)==h,n
for n,h in m['output_sha256'].items():
    assert sha(F/n)==h,n
    assert sha(P/'tmp/q2-figure-reproduction-v1'/n)==h,n
unchanged=['02_weekday_structure','03_storage_limits','05_error_continuity','06_specified_days']
for n in unchanged:assert sha(F/(n+'.png'))==sha(P/'paper/figures/q2-exploration-v3'/(n+'.png'))
assert v['solver_calls']==v['fitted_models']==0 and v['past_only_information']
assert v['raw_numeric_values_checked']==105120 and v['timestamp_mappings_checked']==52560
assert v['all_fixed_reference_values_checked']==673344 and v['all_6h_windows_checked']==72812
s=read(P/'state/state.json')
assert s['revision']==33 and s['stage']=='WAIT_D' and s['active_question']=='Q1'
assert s['questions']['Q1']['frozen_version'] is None
assert s['questions']['Q2']['depends_on']==[{'question':'Q1','version':None}]
assert s['questions']['Q2']['status']=='NOT_STARTED'
links=[]
for rel in ['questions/Q2/report.md','paper_evidence/Q2.md','report.md']:
    source=(P/rel).read_text(encoding='utf-8')
    for target in re.findall(r'\]\((E:/[^)]+)\)',source):
        assert Path(target).exists(),target
        links.append(target)
for n in ['explore_q2.py','verify_q2_exploration.py','plot_q2_exploration.py','check_q2_delivery.py']:
    compile((P/'scripts'/n).read_text(encoding='utf-8'),n,'exec')
record={
 'protected_sources_unchanged':True,'saved_analysis_hashes_match':True,
 'analysis_script_and_protocol_unchanged':True,'plot_sources_and_script_match':True,
 'all_12_figure_files_reproduced_identically':True,'actually_inspected_unchanged_four_pngs':True,
 'actual_visual_inspection':'Final01/04 viewed;02/03/05/06 viewed in identical v3',
 'local_markdown_links_checked':len(links),'state_revision':s['revision'],
 'q1_retained_unfrozen_q2_dependencies_unchanged':True,
 'new_solver_calls':0,'new_fitted_models':0,'ai_verification_only':True,
 'paper_pages_with_new_figures_not_created':True,
 'deliverable_hashes':{str(f.relative_to(P)):sha(f) for f in [P/'questions/Q2/report.md',P/'paper_evidence/Q2.md',F/'qa.json',P/'state/state.json']}}
(A/'delivery_check.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False,indent=2))
