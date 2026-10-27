from pathlib import Path
import subprocess,json
from pypdf import PdfReader
from PIL import Image, ImageDraw
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C/tmp/backup-final-model-20260913')
pdf=root/'build/main.pdf'
out=root/'pages'
out.mkdir(exist_ok=True)
reader=PdfReader(pdf)
texts=[page.extract_text() or '' for page in reader.pages]
(root/'page_text.json').write_text(json.dumps(texts,ensure_ascii=False,indent=2),encoding='utf-8')
poppler=Path('C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe')
subprocess.run([str(poppler),'-r','80','-png',str(pdf),str(out/'page')],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
files=sorted(out.glob('page-*.png'))
for offset in range(0,len(files),12):
    batch=files[offset:offset+12]
    canvas=Image.new('RGB',(4*300,3*446),'#bbbbbb')
    draw=ImageDraw.Draw(canvas)
    for j,file in enumerate(batch):
        im=Image.open(file).convert('RGB')
        im.thumbnail((292,414))
        x=(j%4)*300+(300-im.width)//2
        y=(j//4)*446+25
        canvas.paste(im,(x,y))
        draw.text(((j%4)*300+12,(j//4)*446+7),f'Page {offset+j+1}',fill='black')
    canvas.save(root/f'overview-{offset//12+1}.png')
print(json.dumps({'pages':len(reader.pages),'page_map':[{'page':i+1,'start':t[:100].replace('\n',' ')} for i,t in enumerate(texts)]},ensure_ascii=False))
