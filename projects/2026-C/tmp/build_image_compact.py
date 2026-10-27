from pathlib import Path
import subprocess, re, json, hashlib
from pypdf import PdfReader
P=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
audit=Path((P/'tmp/image_compact_audit_path.txt').read_text('utf-8').strip())
base=P/'shumo_1/shumo_backup_20260913_003434';src=base/'图像压缩版'
out=audit/'build';out.mkdir(exist_ok=True)
for rel,h in json.loads((audit/'protected_hashes.json').read_text('utf-8')).items():
    assert hashlib.sha256((base/rel).read_bytes()).hexdigest()==h,rel
assert (src/'sections/appendix_q4_details.tex').read_bytes()==(base/'压缩版/sections/appendix_q4_details.tex').read_bytes()
cmd=['C:/Program Files/Latex/miktex/bin/x64/xelatex.exe','-interaction=nonstopmode','-halt-on-error','-no-shell-escape',f'-output-directory={out}','main.tex']
for n in range(1,4):
    r=subprocess.run(cmd,cwd=src,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (out/f'pass{n}.txt').write_bytes(r.stdout)
    if r.returncode:raise RuntimeError(r.stdout.decode('utf-8',errors='replace')[-3500:])
    log=(out/'main.log').read_text('utf-8',errors='replace')
    print(f'Pass {n}: '+'\n'.join(x for x in log.splitlines() if any(t in x for t in ['Output written','Overfull','Missing character','undefined','Label(s)'])),flush=True)
    if n>=2 and 'Label(s) may have changed' not in log and 'There were undefined references' not in log:break
r=PdfReader(out/'main.pdf');texts=[x.extract_text() for x in r.pages]
app=next(i+1 for i,t in enumerate(texts) if '附录A' in t.replace(' ', '').replace('\n','') and '详细调度结果' in t and '表' in t)
v={'total_pages':len(r.pages),'abstract_pages':1,'body_pages':app-2,'appendix_start_page':app,'appendix_pages':len(r.pages)-app+1,
'warnings':[x for x in log.splitlines() if any(t in x for t in ['Overfull','Missing character','undefined'])], 'protected_files_unchanged':True,'appendix_unchanged':True}
(audit/'verification.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf-8')
(audit/'pages.txt').write_text('\n\n'.join(f'PAGE {i+1}\n{t}' for i,t in enumerate(texts)),'utf-8')
print(json.dumps(v,ensure_ascii=False))
