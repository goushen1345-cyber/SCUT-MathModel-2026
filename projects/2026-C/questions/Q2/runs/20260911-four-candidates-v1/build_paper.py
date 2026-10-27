"""Add the authorized Q2 parameter/comparison section to a new manuscript version."""
from pathlib import Path
import shutil,json,hashlib,subprocess,sys
import csv
R=Path(__file__).resolve().parent;P=R.parents[3];OLD=P/'paper/q1_manuscript_v1';NEW=P/'paper/q2_comparison_manuscript_v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not NEW.exists();assert json.loads((R/'verification.json').read_text(encoding='utf-8'))['status']=='passed'
NEW.mkdir();(NEW/'sections').mkdir();(NEW/'figures').mkdir();(NEW/'build').mkdir();(NEW/'preview').mkdir()
source={}
for f in [OLD/'result_values.tex',*sorted((OLD/'sections').glob('*.tex')),
          *sorted((OLD/'figures').glob('*.pdf')),OLD/'figures/energy_paths.tex']:
    dest=NEW/f.relative_to(OLD);shutil.copy2(f,dest);source[str(f.relative_to(P))]=sha(f)
main=(OLD/'问题一论文草稿.tex').read_text(encoding='utf-8')
main=main.replace('\\input{result_values.tex}','\\input{result_values.tex}\n\\input{q2_values.tex}')
main=main.replace('\\end{document}','\\input{sections/question2_comparison.tex}\n\\end{document}')
name='论文草稿_含问题二候选比较';(NEW/(name+'.tex')).write_text(main,encoding='utf-8')
source[str((OLD/'问题一论文草稿.tex').relative_to(P))]=sha(OLD/'问题一论文草稿.tex')
shutil.copy2(R/'paper_section.tex',NEW/'sections/question2_comparison.tex')
shutil.copy2(R/'figures-v2/01_cost_and_months.pdf',NEW/'figures/q2_cost_and_months.pdf')
source[str((R/'paper_section.tex').relative_to(P))]=sha(R/'paper_section.tex')
source[str((R/'figures-v2/01_cost_and_months.pdf').relative_to(P))]=sha(R/'figures-v2/01_cost_and_months.pdf')
summary=json.loads((R/'interpretation/summary.json').read_text(encoding='utf-8'))
init=json.loads((R/'outputs/initialization.json').read_text(encoding='utf-8'))
with (R/'outputs/comparison.csv').open(encoding='utf-8-sig',newline='') as f:comp={r['variant']:r for r in csv.DictReader(f)}
values={'QTwoInitialStorage':init['feb1_initial'],'QTwoOrdinaryIncrease':summary['ordinary_cost_increase']/1e4,
        'QTwoEmergencyReduction':summary['emergency_cost_reduction']/1e4,'QTwoSaving':summary['total_saving_vs_T1']/1e4,
        'QTwoSavingPct':summary['saving_pct_vs_T1'],'QTwoStorageDifference':summary['final_storage_T4_minus_T1']}
for kind,tag in [('T1','Base'),('T2','Ridge'),('T3','Tree'),('T4','Risk')]:
    for field,suffix in [('ordinary_cost','Ordinary'),('emergency_cost','Emergency'),('total_cost','Total')]:
        values['QTwo'+tag+suffix]=float(comp[kind][field])/1e4
(NEW/'q2_values.tex').write_text('\n'.join('\\newcommand{\\'+k+'}{'+f'{v:.2f}'+'}' for k,v in values.items())+'\n',encoding='utf-8')
LATEX=Path('C:/Program Files/Latex/miktex/bin/x64');DEPS=Path('C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies')
commands=[]
for i in [1,2]:
    cmd=[str(LATEX/'xelatex.exe'),'--disable-installer','-interaction=nonstopmode','-halt-on-error','-no-pdf',
         '-output-directory='+str(NEW/'build'),name+'.tex'];commands.append(cmd)
    with (NEW/'build'/f'pass{i}.txt').open('w',encoding='utf-8') as log:subprocess.run(cmd,cwd=NEW,stdout=log,stderr=subprocess.STDOUT,check=True)
pdf=NEW/(name+'.pdf');cmd=[str(LATEX/'xdvipdfmx.exe'),'-q','-o',str(pdf),str(NEW/'build'/(name+'.xdv'))];commands.append(cmd)
subprocess.run(cmd,cwd=NEW,check=True)
cmd=[str(DEPS/'native/poppler/Library/bin/pdftoppm.exe'),'-r','120','-png',str(pdf),str(NEW/'preview/page')];commands.append(cmd)
subprocess.run(cmd,check=True)
record={'scope':'Q2 separate forecast,weights/parameters and verified150day comparison; not a completeQ2/finalpaper',
        'old_manuscript_unchanged':sha(OLD/'问题一论文草稿.pdf'),'source_sha256':source,'numeric_macros':values,
        'comparison_sha256':sha(R/'outputs/comparison.csv'),'commands':commands,'pdf_sha256':sha(pdf),
        'new_tex_sha256':{str(f.relative_to(NEW)):sha(f) for f in NEW.rglob('*.tex')}}
(NEW/'build_record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(str(pdf))
