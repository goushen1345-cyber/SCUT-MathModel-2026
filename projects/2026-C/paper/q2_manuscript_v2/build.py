"""Compile and render this standalone Q2 chapter only."""
from pathlib import Path
import hashlib,json,subprocess
HERE=Path(__file__).resolve().parent
NAME='问题二的模型建立与求解'
LATEX=Path('C:/Program Files/Latex/miktex/bin/x64')
POPPLER=Path('C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin')
build=HERE/'build';preview=HERE/'preview'
build.mkdir(exist_ok=True);preview.mkdir(exist_ok=True)
commands=[]
for number in (1,2):
    cmd=[str(LATEX/'xelatex.exe'),'--disable-installer','-interaction=nonstopmode','-halt-on-error','-no-pdf',f'-output-directory={build}',NAME+'.tex']
    commands.append(cmd)
    with (build/f'pass{number}.txt').open('w',encoding='utf-8') as log:
        subprocess.run(cmd,cwd=HERE,stdout=log,stderr=subprocess.STDOUT,check=True)
pdf=HERE/(NAME+'.pdf')
cmd=[str(LATEX/'xdvipdfmx.exe'),'-q','-o',str(pdf),str(build/(NAME+'.xdv'))]
commands.append(cmd);subprocess.run(cmd,cwd=HERE,check=True)
cmd=[str(POPPLER/'pdftoppm.exe'),'-r','115','-png',str(pdf),str(preview/'page')]
commands.append(cmd);subprocess.run(cmd,cwd=HERE,check=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=list(HERE.glob('*.tex'))+list((HERE/'tables').glob('*.tex'))+list((HERE/'figures').glob('*.pdf'))+[HERE/'prepare.py',HERE/'build.py']
(build/'record.json').write_text(json.dumps({'commands':commands,'input_sha256':{str(p.relative_to(HERE)):sha(p) for p in inputs},'pdf_sha256':sha(pdf),'scope':'local writing only'},ensure_ascii=False,indent=2),'utf-8')
print(json.dumps({'pdf':str(pdf),'rendered_pages':len(list(preview.glob('page-*.png')))},ensure_ascii=False))
