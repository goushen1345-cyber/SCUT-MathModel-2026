"""Compile the two submission-support PDFs and render every page for inspection."""
from pathlib import Path
import subprocess, hashlib, json
HERE=Path(__file__).resolve().parent
LATEX=Path('C:/Program Files/Latex/miktex/bin/x64')
POPPLER=Path('C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin')
BUILD=HERE/'build'; BUILD.mkdir(exist_ok=True)
PREVIEW=HERE/'preview'; PREVIEW.mkdir(exist_ok=True)
jobs=[('AI工具使用详情','AI工具使用详情'),('参考文献_独立页','参考文献_核验版')]
for stem,name in jobs:
 for repeat in range(2):
  with (BUILD/(stem+f'-{repeat+1}.log')).open('w',encoding='utf-8') as f:
   subprocess.run([str(LATEX/'xelatex.exe'),'--disable-installer','-interaction=nonstopmode','-halt-on-error','-no-pdf',f'-output-directory={BUILD}',stem+'.tex'],cwd=HERE,stdout=f,stderr=subprocess.STDOUT,check=True)
 pdf=HERE/(name+'.pdf')
 subprocess.run([str(LATEX/'xdvipdfmx.exe'),'-q','-o',str(pdf),str(BUILD/(stem+'.xdv'))],cwd=HERE,check=True)
 subprocess.run([str(POPPLER/'pdftoppm.exe'),'-r','110','-png',str(pdf),str(PREVIEW/name)],check=True)
 subprocess.run([str(POPPLER/'pdfinfo.exe'),str(pdf)],check=True)
sources=list(HERE.glob('*.tex'))+[HERE/'参考文献核查报告.md',HERE.parents[1]/'state/ai_usage_log.md']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(HERE/'manifest.json').write_text(json.dumps({'scope':'AI-use disclosure and reference verification; no research rerun',
 'sources':{str(p):sha(p) for p in sources},'outputs':{p.name:sha(p) for p in HERE.glob('*.pdf')},
 'human_final_review':'not_confirmed','team_other_AI_usage':'awaiting_user_information',
 'official_rule':'https://www.mcm.edu.cn/html_cn/node/fef94648f2836ab6cc81586f4c38512b.html'},ensure_ascii=False,indent=2),'utf-8')
