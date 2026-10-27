"""Export the six existing manuscript figures at 300 dpi; no research or re-layout."""
from pathlib import Path
import argparse, hashlib, json, math, subprocess
from PIL import Image

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
REPO=PROJECT.parents[1]
POPPLER=Path('C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,default=HERE/'figures/png')
args=parser.parse_args()
out=args.output.resolve()
assert out.is_relative_to(PROJECT.resolve()) and not out.exists(), 'Use a new output directory inside project'
paper=HERE/'问题一论文草稿.pdf'
record=json.loads((HERE/'build/build_record.json').read_text(encoding='utf-8'))
assert sha(paper)==record['pdf_sha256'], 'Reinspect diagram coordinates if the manuscript changed'
recorded_inputs={k.replace('\\','/'):v for k,v in record['input_sha256'].items()}
assert sha(HERE/'figures/energy_paths.tex')==recorded_inputs['figures/energy_paths.tex']
specs=[
 ('图1_代表日供需与电价的时间错配','01_reference_day.pdf','EDA-F01',PROJECT/'paper/figures/eda-v2/01_reference_day.pdf'),
 ('图2_负载光伏与电价的年内变化','02_year_and_month.pdf','EDA-F02',PROJECT/'paper/figures/eda-v2/02_year_and_month.pdf'),
 ('图3_星期用电差异与电价波动','06_prices_and_weekdays.pdf','EDA-F06',PROJECT/'paper/figures/eda-v2/06_prices_and_weekdays.pdf'),
 ('图4_光伏预报误差与更新效果','07_forecast_accuracy.pdf','EDA-F07',PROJECT/'paper/figures/eda-v2/07_forecast_accuracy.pdf'),
 ('图5_问题一电量分配关系',None,'Q1-F03',HERE/'figures/energy_paths.tex'),
 ('图6_三种策略的购电与储能安排','q1_daily_dispatch.pdf','Q1-F01',PROJECT/'questions/Q1/runs/20260911-compare-v1/figures-v4/01_daily_dispatch.pdf')]
protected=[paper,HERE/'问题一论文草稿.tex',HERE/'figures/energy_paths.tex',PROJECT/'questions/Q1/runs/20260911-close-v1/deliverables/result1.xlsx']
hashes={str(p.relative_to(PROJECT)):sha(p) for p in protected}
out.mkdir(parents=True)
entries=[]
for name,filename,fig_id,source in specs:
    prefix=out/name
    if filename:
        pdf=HERE/'figures'/filename
        assert sha(pdf)==sha(source),filename
        command=[str(POPPLER),'-f','1','-l','1','-r','300','-singlefile','-png',str(pdf),str(prefix)]
        crop=None
    else:
        pdf=paper
        # Bounds reviewed on manuscript page9, in PDF points, excluding the caption.
        crop=[106,493,487,640]
        x,y=math.floor(crop[0]*300/72),math.floor(crop[1]*300/72)
        w,h=math.ceil(crop[2]*300/72)-x,math.ceil(crop[3]*300/72)-y
        command=[str(POPPLER),'-f','9','-l','9','-r','300','-x',str(x),'-y',str(y),'-W',str(w),'-H',str(h),'-singlefile','-png',str(pdf),str(prefix)]
    subprocess.run(command,check=True,capture_output=True)
    target=prefix.with_suffix('.png')
    with Image.open(target) as im:
        size=im.size
        assert size[0]>1000 and size[1]>500
        assert im.getbbox() is not None
        dpi=im.info.get('dpi')
    entries.append(dict(figure_id=fig_id,png=target.name,png_sha256=sha(target),pixels=size,dpi=dpi,
        source_pdf=str(pdf.relative_to(PROJECT)),source_pdf_sha256=sha(pdf),
        original_source=str(source.relative_to(PROJECT)),original_source_sha256=sha(source),
        crop_pdf_points=crop,command=command))
assert all(sha(PROJECT/k)==v for k,v in hashes.items())
manifest=dict(dpi=300,figures=entries,protected_sha256=hashes,
    script_sha256=sha(__file__),renderer=str(POPPLER),
    rendering='Existing vector PDFs rasterized with Poppler; figure5 uses its reviewed region in page9, not a low-resolution screenshot',
    source_models_or_data_changed=False,visual_qa='pending actual PNG inspection')
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([dict(file=e['png'],pixels=e['pixels'],dpi=e['dpi']) for e in entries],ensure_ascii=False))
