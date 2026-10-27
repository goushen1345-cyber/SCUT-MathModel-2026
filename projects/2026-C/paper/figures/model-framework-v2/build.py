"""Reproduce the four-panel black/white model diagram with TikZ."""
from pathlib import Path
import subprocess, hashlib, json, shutil

HERE = Path(__file__).resolve().parent
LATEX = Path('C:/Program Files/Latex/miktex/bin/x64')
POPPLER = Path('C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin')
build = HERE/'build'
build.mkdir(exist_ok=True)
cmd = [str(LATEX/'xelatex.exe'), '--disable-installer', '-interaction=nonstopmode', '-halt-on-error', '-no-pdf', f'-output-directory={build}', 'framework.tex']
with (build/'compile.log').open('w', encoding='utf-8') as f:
    subprocess.run(cmd, cwd=HERE, stdout=f, stderr=subprocess.STDOUT, check=True)
pdf = HERE/'四问整体模型框架图.pdf'
subprocess.run([str(LATEX/'xdvipdfmx.exe'), '-q', '-o', str(pdf), str(build/'framework.xdv')], cwd=HERE, check=True)
subprocess.run([str(POPPLER/'pdftoppm.exe'), '-singlefile', '-gray', '-r', '300', '-png', str(pdf), str(HERE/'四问整体模型框架图')], check=True)
subprocess.run([str(POPPLER/'pdftoppm.exe'), '-singlefile', '-gray', '-r', '150', '-png', str(pdf), str(HERE/'preview')], check=True)
sources = [HERE/'framework.tex', HERE/'build.py'] + [HERE.parent.parent/'complete_manuscript_v1'/f'q{i}.tex' for i in range(1,5)]
outputs = [pdf, HERE/'四问整体模型框架图.png']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
(HERE/'manifest.json').write_text(json.dumps({'tool':'TikZ / XeLaTeX / Poppler', 'fonts':['SimSun','SimHei','Times New Roman'], 'sources':{str(p):sha(p) for p in sources}, 'outputs':{p.name:sha(p) for p in outputs}, 'scope':'Existing model structure only; no research or state changes', 'png_dpi':300}, ensure_ascii=False, indent=2), encoding='utf-8')
print(str(pdf))
