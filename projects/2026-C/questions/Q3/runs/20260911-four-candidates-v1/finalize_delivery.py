"""Finalize evidence references and figure reproducibility, without research runs."""
from pathlib import Path
import json, hashlib
R=Path(__file__).resolve().parent; P=R.parents[3]; O=R/'outputs'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
v=read(O/'verification.json');s=read(O/'summary.json');assert v['status']=='checks_completed'
assert sha(R/'verify.py')==v['code_sha256']
assert all(sha(R/name)==fingerprint for name,fingerprint in s['code'].items())
protected=read(O/'protected_sources.json')
assert all(sha(P/name)==fingerprint for name,fingerprint in protected.items())
fig=R/'figures-v1';repro=P/'tmp/q3-trial-figure-reproduction-v1'
fm=read(fig/'manifest.json');rm=read(repro/'manifest.json')
assert fm['code_sha256']==rm['code_sha256']==sha(R/'plot_results.py')
same={name:sha(fig/name)==sha(repro/name)==fingerprint==rm['outputs'][name] for name,fingerprint in fm['outputs'].items()}
assert all(same.values())
assert all(sha(R/name)==fingerprint for name,fingerprint in fm['sources'].items())
qa=dict(status='source_and_reproduction_checks_completed',outputs_identical=same,reproduction_path=str(repro.relative_to(P)),
    actual_visual_inspection=dict(assessor='primary AI; not human review',files=['01_candidate_costs_and_months.png','02_information_value.png'],
        findings='Readable Chinese labels, units and legends; negative months retained; S4 alias identified; information-control scope stated; no clipping seen.',
        vector_pages_separately_rendered=False,manuscript_embedded=False,human_timed_test=False),
    no_new_fit_or_optimization=True)
save(fig/'qa.json',qa)
scope=read(R/'interpretation/findings.json')
save(O/'delivery.json',dict(status='trial_comparison_delivered_waiting_user_main_choice',authorization='Q3-TRIAL-062',record='Q3-COMPARISON-063',
    recommendation='S2_fused as initial main candidate; not selected by user',period_days=334,
    candidate4='zero margin selected in January; exact alias of S2_fused',candidate5='not run',
    source_summary_sha256=sha(O/'summary.json'),summary_pending_note='Immutable solver-end snapshot predates final independent read-back; verification.json records subsequent completion.',
    verification_sha256=sha(O/'verification.json'),protected_files_unchanged=len(protected),budget=read(O/'budget.json'),
    previous_failure='Floating weighted-CDF equality corrected; original failure and caches preserved. Nine January costs unchanged; annual traces unchanged.',
    numeric_correction_sha256=sha(R/'interpretation/numeric_correction_comparison.json'),figures_qa_sha256=sha(fig/'qa.json'),
    findings_sha256=sha(R/'interpretation/findings.json'),code_sha256=sha(__file__),
    important_limit='Q3 initial best still costs 504894.82 yuan more than refined Q2; no automatic refinement, final selection, paper, official workbook, freeze or Q4.',
    human_approval=False,independent_agent_review=False))
print(json.dumps(dict(protected_unchanged=len(protected),figure_files_reproduced=len(same),delivery_status='trial_comparison_delivered_waiting_user_main_choice'),ensure_ascii=False))
