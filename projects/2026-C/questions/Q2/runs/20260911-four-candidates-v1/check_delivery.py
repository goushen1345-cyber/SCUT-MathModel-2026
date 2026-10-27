"""Read-only numerical/source checks plus delivery QA; never train or dispatch."""
from pathlib import Path
import json, hashlib, csv, re, subprocess, sys, argparse
import pdfplumber
from PIL import Image, ImageChops

R = Path(__file__).resolve().parent
P = R.parents[3]
N = P/'paper/q2_comparison_manuscript_v1'
OLD = P/'paper/q1_manuscript_v1'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
def save(p, x):
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')

args = argparse.ArgumentParser()
args.add_argument('--final', action='store_true')
opt = args.parse_args()
protected = read(R/'outputs/source_hashes.json')
for f, h in protected.items(): assert sha(P/f) == h, f
outputs = read(R/'outputs/output_hashes.json')
for f, h in outputs.items(): assert sha(R/'outputs'/f) == h, f
verification = read(R/'verification.json')
assert verification['status'] == 'passed' and verification['ai_verification_only']
assert verification['new_fits'] == verification['new_solver_calls'] == 0

F = R/'figures-v2'
fm = read(F/'manifest.json')
rep = P/'tmp/q2-trial-fig-reproduction-v1'
for f, h in fm['sources'].items(): assert sha(R/f) == h, f
assert sha(R/'plot_results.py') == fm['script_sha256']
for f, h in fm['outputs'].items():
    assert sha(F/f) == h and sha(rep/f) == h, f
first_unchanged = {ext: sha(F/f'01_cost_and_months.{ext}') == sha(R/f'figures-v1/01_cost_and_months.{ext}') for ext in ['png','pdf']}
assert all(first_unchanged.values())
fq = {'status':'passed','date':'2026-09-11','ai_visual_check':True,'human_review':False,
      'viewed':['02_paired_extreme_days.png (final v2)', '01_cost_and_months.png (v1, identical hash to v2)',
                '01_cost_and_months embedded on new manuscript page17'],
      'checks':'Units, signed monthly savings, date labels, legends, storage limits and axes legible. External orders are not subject to the battery5000kW cap.',
      'first_figure_unchanged_from_viewed_v1':first_unchanged,
      'all_four_pdf_png_reproduction_hashes_match':True,'reproduction_directory':str(rep),
      'source_hashes':fm['sources'],'outputs':fm['outputs'],
      'boundary':'Two paired days are selected extrema with own inherited storage, not random typical days; monthly counterexample retained.'}
save(F/'qa.json',fq)

br = read(N/'build_record.json')
for f, h in br['source_sha256'].items(): assert sha(P/f) == h, f
for f, h in br['new_tex_sha256'].items(): assert sha(N/f) == h, f
assert sha(OLD/'问题一论文草稿.pdf') == br['old_manuscript_unchanged']
assert sha(N/'论文草稿_含问题二候选比较.pdf') == br['pdf_sha256']
assert sha(R/'outputs/comparison.csv') == br['comparison_sha256']
with (R/'outputs/comparison.csv').open(encoding='utf-8-sig',newline='') as f:
    comp = {r['variant']:r for r in csv.DictReader(f)}
s = read(R/'interpretation/summary.json')
init = read(R/'outputs/initialization.json')
values = {'QTwoInitialStorage':init['feb1_initial'], 'QTwoOrdinaryIncrease':s['ordinary_cost_increase']/1e4,
          'QTwoEmergencyReduction':s['emergency_cost_reduction']/1e4,'QTwoSaving':s['total_saving_vs_T1']/1e4,
          'QTwoSavingPct':s['saving_pct_vs_T1'],'QTwoStorageDifference':s['final_storage_T4_minus_T1']}
for k, tag in [('T1','Base'),('T2','Ridge'),('T3','Tree'),('T4','Risk')]:
    for fld, suffix in [('ordinary_cost','Ordinary'),('emergency_cost','Emergency'),('total_cost','Total')]:
        values['QTwo'+tag+suffix] = float(comp[k][fld])/1e4
assert values == br['numeric_macros']
macro = (N/'q2_values.tex').read_text(encoding='utf-8')
for k,v in values.items(): assert '\\newcommand{\\'+k+'}{'+f'{v:.2f}'+'}' in macro
with pdfplumber.open(OLD/'问题一论文草稿.pdf') as old, pdfplumber.open(N/'论文草稿_含问题二候选比较.pdf') as new:
    assert len(old.pages)==14 and len(new.pages)==17
    old_pages_match = [(a.extract_text()==b.extract_text()) for a,b in zip(old.pages,new.pages[:14])]
    # CMEX10 sum has a different ToUnicode extraction in this font subset.
    # Permit only the observed sum/X extraction pair, then require pixel equality.
    def samechar(a,b):
        return a['text']==b['text'] or (a['fontname'].endswith('+CMEX10') and b['fontname'].endswith('+CMEX10') and (a['text'],b['text'])==('∑','X'))
    coords_unchanged = all(
        len(a.chars)==len(b.chars) and all(samechar(ca,cb) and max(abs(ca[z]-cb[z]) for z in ['x0','x1','top','bottom'])<1e-6
                                       for ca,cb in zip(a.chars,b.chars))
        for a,b in zip(old.pages,new.pages[:14]))
    assert coords_unchanged
    for i in range(1,15):
        a=Image.open(OLD/f'preview/page-{i:02d}.png').convert('RGB')
        b=Image.open(N/f'preview/page-{i:02d}.png').convert('RGB')
        assert a.size==b.size and ImageChops.difference(a,b).getbbox() is None,i
    colors=set();body='';outside=[]
    for i,page in enumerate(new.pages,1):
        for c in page.chars:
            if c['text'].strip():
                if c['x0']<-1 or c['x1']>page.width+1 or c['top']<-1 or c['bottom']>page.height+1: outside.append(i)
                colors.add(str(c.get('non_stroking_color')))
        if i>=15: body+=page.extract_text()+'\n'
    assert not outside
    black_values={'0', '0.0','(0,)','(0.0,)','(0, 0, 0)','(0.0, 0.0, 0.0)','(0, 0, 0, 1)','(0.0, 0.0, 0.0, 1.0)', 'None'}
    assert colors.issubset(black_values),colors
    for v in values.values(): assert f'{v:.2f}' in body, v
    for txt in ['130.72','153.62','168.20','189.95','16.31','4.68','89','45','16','0.58','17.51','39.41']:
        assert txt in body,txt
    for forbidden in ['G0','Skill','审批','冻结','run ID','Q2-TRIAL','T1','T4']:
        assert forbidden not in body,forbidden
log=(N/'build/论文草稿_含问题二候选比较.log').read_text(encoding='utf-8',errors='replace')
bad=[line for line in log.splitlines() if any(s in line for s in ['Overfull','undefined','Missing character'])]
assert not bad,bad
pq={'status':'passed','pdf_sha256':br['pdf_sha256'],'pages':17,
    'new_section_pages':[15,16,17],'actual_visual_pages':[10,14,15,16,17],
    'prior14_pages_character_positions_and_rendered_pixels_unchanged':True,
    'text_extraction_difference':'Page10 has5 CMEX10 sum symbols extracted asX by pdfplumber in new font subset. Source identical; inspected page10 sums correct; all14 pages pixels identical at120dpi.',
    'prior14_pages_visual':'Previously reviewed Q1 manuscript; page14 re-viewed at boundary. Appending preserves existing Q1 end-page whitespace.',
    'visual_findings':'New pages legible; equations, table4 and figure7 have no clipping/overlap or missing glyphs. Page16 paragraph continues normally on17. New section starts15.',
    'numeric_macros_verified':len(values),'all_page_text_black':True,'text_color_values':sorted(colors),
    'all_page_characters_within_canvas':True,'undefined_overfull_missing_glyph_warnings':bad,
    'new_section_has_no_internal_workflow_terms':True,'ai_check_only':True,'human_review':False,
    'scope':'Local Q2 parameters and comparison draft; no annual/final-paper or official-submission compliance approval.'}
save(N/'qa.json',pq)

state=read(P/'state/state.json')
if opt.final:
    assert state['revision']==35 and state['stage']=='WAIT_D' and state['active_question']=='Q1'
    assert state['questions']['Q1']['frozen_version'] is None
    assert state['questions']['Q2']['frozen_version'] is None
    assert state['questions']['Q2']['depends_on']==[{'question':'Q1','version':None}]
    assert '5875441.26' in state['pending_gate']['summary']
    for f in ['questions/Q2/report.md','questions/Q2/experiments.md','paper_evidence/Q2.md',
              'paper_evidence/figure_registry.md','report.md','state/decisions.md','state/ai_usage_log.md']:
        assert (P/f).is_file(),f
    assert (P/'questions/Q2/report.md').read_text(encoding='utf-8').startswith('# 问题二：四候选实跑')
    rc=subprocess.run([sys.executable,str(P.parents[1]/'workflow/scripts/statectl.py'),'validate',str(P)],capture_output=True,text=True,encoding='utf-8')
    assert rc.returncode==0,rc.stdout+rc.stderr
result={'status':'passed','final_record_check':opt.final,'source_files_unchanged':len(protected),
        'locked_output_files_unchanged':len(outputs),'original_q1_pdf_unchanged':True,
        'figure_reproduction':'4 of4 exact hashes','new_pdf_pages':17,'new_pdf_visual_pages':[14,15,16,17],
        'numeric_macros':len(values),'state_revision':state['revision'],
        'new_training_runs':0,'new_solver_calls':0,'human_review':False}
save(R/'delivery_checks.json',result)
print(json.dumps(result,ensure_ascii=False))
