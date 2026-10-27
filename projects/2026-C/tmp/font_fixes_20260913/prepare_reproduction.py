from pathlib import Path
import json,shutil,hashlib

P=Path(__file__).resolve().parents[2]
SOURCE=P/'支撑材料'
DEST=Path(__file__).resolve().parent/'reproduction_package'
files=[Path('code')/s for s in ('fig_q1.py','fig_q3_days.py','fig_q3_quantile.py')]
files += [Path(s) for s in ('results/Q3.npz','figure_inputs/q3_daily.csv','data/inputs.npz','figure_inputs/derived_values.json','figure_inputs/q1/outputs/summary.json')]
summary=json.loads((SOURCE/'figure_inputs/q1/outputs/summary.json').read_text(encoding='utf-8'))
files += [Path('figure_inputs/q1/outputs/schedules')/(r['key']+'.csv') for r in summary['comparison']]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=[]
for rel in dict.fromkeys(files):
    target=DEST/rel;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(SOURCE/rel,target)
    assert sha(SOURCE/rel)==sha(target)
    manifest.append({'relative_path':str(rel),'source':str(SOURCE/rel),'copy':str(target),'sha256':sha(target)})
(DEST/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'copied_files':len(manifest),'root':str(DEST)},ensure_ascii=False))
