from pathlib import Path
import subprocess, hashlib, json, shutil
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
src=root/'shumo_1/shumo'
out=root/'tmp/shumo-supplements-20260913/build'
out.mkdir(parents=True,exist_ok=True)
inputs=[src/'main.tex',*sorted((src/'sections').glob('*.tex'))]
before={str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
cmd=['C:/Program Files/Latex/miktex/bin/x64/xelatex.exe','-interaction=nonstopmode','-halt-on-error','-no-shell-escape',f'-output-directory={out}','main.tex']
for n in range(1,4):
    r=subprocess.run(cmd,cwd=src,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (out/f'pass{n}.txt').write_bytes(r.stdout)
    if r.returncode: raise RuntimeError(r.stdout.decode('utf-8',errors='replace')[-2500:])
    log=(out/'main.log').read_text('utf-8',errors='replace')
    print(f'Pass {n}: '+ '\n'.join(x for x in log.splitlines() if any(s in x for s in ['Output written','Overfull','Missing character','undefined','Label(s)'])),flush=True)
    if n>=2 and 'Label(s) may have changed' not in log and 'There were undefined references' not in log: break
after={str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
assert before==after,'Sources changed during compilation'
(out/'source_hashes.json').write_text(json.dumps(after,indent=2),'utf-8')
print('Stable build: '+str(out/'main.pdf'))
