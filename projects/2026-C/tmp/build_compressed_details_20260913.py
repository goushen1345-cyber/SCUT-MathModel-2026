from pathlib import Path
import subprocess,hashlib,json,shutil,re
from pypdf import PdfReader
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
orig=root/'shumo_1/shumo_backup_20260913_003434'
src=orig/'压缩版'
audit=Path((root/'tmp/compressed_details_audit_path.txt').read_text('utf-8').strip())
out=audit/'build';out.mkdir(exist_ok=True)
stage=audit/'compile_source';stage.mkdir(exist_ok=True)
shutil.copy2(src/'main.tex',stage/'main.tex')
for folder in ('sections','tables','fig'):shutil.copytree(src/folder,stage/folder,dirs_exist_ok=True)
hashes=json.loads((audit/'original_hashes.json').read_text('utf-8'))
assert all(hashlib.sha256((orig/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),'Original changed'
def text_all(base):return '\n'.join(p.read_text('utf-8') for d in ['sections','tables'] for p in sorted((base/d).glob('*.tex')))
old,new=text_all(orig),text_all(src)
def tables(s):return re.findall(r'\\begin\{table\}.*?\\end\{table\}',s,re.S)
oldcells=re.findall(r'\\begin\{tabular\}.*?\\end\{tabular\}',old,re.S)
newcells=re.findall(r'\\begin\{tabular\}.*?\\end\{tabular\}',new,re.S)
assert len(oldcells)==19 and len(newcells)==26
assert all(t in newcells for t in oldcells),'Original table numbers changed or removed'
oldfig=set(re.findall(r'\\label\{(fig:[^}]+)\}',old));newfig=set(re.findall(r'\\label\{(fig:[^}]+)\}',new))
assert oldfig-newfig=={'fig:q3_monthly'} and not newfig-oldfig
assert '@@{' not in new
counts={q:len(re.findall(r'\\subsection\{',(src/f'sections/sec_{q+4}_q{q}.tex').read_text('utf-8'))) for q in range(1,5)}
assert list(counts.values())==[4,5,6,5],counts
cmd=['C:/Program Files/Latex/miktex/bin/x64/xelatex.exe','-interaction=nonstopmode','-halt-on-error','-no-shell-escape',f'-output-directory={out}','main.tex']
for n in range(1,4):
    result=subprocess.run(cmd,cwd=stage,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (out/f'pass{n}.txt').write_bytes(result.stdout)
    if result.returncode:raise RuntimeError(result.stdout.decode('utf-8',errors='replace')[-4000:])
    log=(out/'main.log').read_text('utf-8',errors='replace')
    print(f'Pass {n}: '+'\n'.join(x for x in log.splitlines() if any(t in x for t in ['Output written','Overfull','Missing character','undefined','Label(s)'])),flush=True)
    if n>=2 and 'Label(s) may have changed' not in log and 'There were undefined references' not in log:break
assert 'There were undefined references' not in log
reader=PdfReader(out/'main.pdf')
report={'original_pages':len(PdfReader(orig/'main.pdf').pages),'compressed_pages':len(reader.pages),'tables_preserved':len(tables(new)),'figures':len(newfig),'subsection_counts':counts,'original_unchanged':True,'warnings':[x for x in log.splitlines() if any(t in x for t in ['Overfull','Missing character','undefined'])]}
(audit/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
(audit/'pages.txt').write_text('\n\n'.join(f'PAGE {i+1}\n{p.extract_text()}' for i,p in enumerate(reader.pages)),'utf-8')
print(json.dumps(report,ensure_ascii=False))
print('Built PDF: '+str(out/'main.pdf'))
