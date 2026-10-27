from pathlib import Path
import subprocess
from PIL import Image,ImageOps,ImageDraw
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
audit=Path((root/'tmp/compressed_paper_audit_path.txt').read_text('utf-8').strip())
out=audit/'render-final';out.mkdir(exist_ok=True)
cmd=['C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe','-scale-to','1200','-png',str(audit/'build/main.pdf'),str(out/'page')]
subprocess.run(cmd,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
files=sorted(out.glob('page-*.png'))
for start in range(0,len(files),6):
    sheet=Image.new('RGB',(1800,1740),'#cccccc');draw=ImageDraw.Draw(sheet)
    for j,p in enumerate(files[start:start+6]):
        im=Image.open(p).convert('RGB');im.thumbnail((584,830))
        x=(j%3)*600+(600-im.width)//2;y=(j//3)*870+25
        sheet.paste(im,(x,y));draw.text(((j%3)*600+15,(j//3)*870+5),p.stem,fill='black')
    sheet.save(out/f'contact-{start//6+1}.jpg',quality=92)
print(out)
