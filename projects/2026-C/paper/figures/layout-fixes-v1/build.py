"""Rebuild three layout repairs, checking that their source data remain unchanged."""
from pathlib import Path
import hashlib, json, subprocess, sys
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
sources = [
 'paper/q3_manuscript_v2/prepare.py',
 'questions/Q1/runs/20260911-compare-v1/present.py',
 'questions/Q1/runs/20260911-compare-v1/outputs/summary.json',
 'questions/Q3/runs/20260911-parameter-interpretability-v1/plot.py',
 'questions/Q3/runs/20260911-parameter-interpretability-v1/outputs/comparison.csv',
 'questions/Q3/runs/20260911-parameter-interpretability-v1/outputs/verification.json',
 'questions/Q3/runs/20260911-parameter-interpretability-v1/outputs/strategies/M_q60_b070_w28_h03.npz',
 'questions/Q3/runs/20260911-four-candidates-v1/outputs/sources.npz',
]
for name in ['C03-p07','C04','C10-p05']:
    sources.append(f'questions/Q1/runs/20260911-compare-v1/outputs/schedules/{name}.csv')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
before = {name:sha(PROJECT/name) for name in sources}
for script in ['prepare_sources.py','draw_specified_days.py','draw_parameters.py','draw_dispatch.py']:
    subprocess.run([sys.executable,str(HERE/script)],check=True,cwd=HERE)
assert before == {name:sha(PROJECT/name) for name in sources}
# Preview the actual vector PDFs, also avoiding a small-size SimSun raster issue.
poppler = Path('C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe')
for pdf in HERE.glob('*.pdf'):
    subprocess.run([str(poppler),'-singlefile','-r','140','-png',str(pdf),str(pdf.with_name(pdf.stem+'_preview'))],check=True)
(HERE/'manifest.json').write_text(json.dumps({
    'scope':'Matplotlib layout corrections only; no fitting or optimization',
    'source_sha256':before,'sources_unchanged_after_render':True,
    'python':sys.version,
    'code_sha256':{p.name:sha(p) for p in HERE.glob('*.py')},
    'output_sha256':{p.name:sha(p) for p in HERE.iterdir() if p.suffix in ['.pdf','.png','.svg']},
    'png_dpi':300,'preview_dpi':140,'previews_rendered_from_pdf':True,
},ensure_ascii=False,indent=2),'utf-8')
print('All three figures generated; original source and result hashes unchanged.')
