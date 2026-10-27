from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,re
import pypdfium2 as pdf
import pdfplumber
from PIL import Image,ImageDraw

root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
base=root/'shumo_1/shumo_backup_20260913_003434'
path=base/'main(图像压缩版）.pdf'
out=Path(__file__).parent
pages=out/'pages';pages.mkdir(exist_ok=True)
doc=pdf.PdfDocument(path)
for i in range(len(doc)):
    im=doc[i].render(scale=1.4 if i<37 else 0.9).to_pil()
    im.save(pages/f'p{i+1:03d}.png')
for start in range(0,len(doc),6):
    canvas=Image.new('RGB',(1500,1450),'#DDD')
    for i in range(start,min(start+6,len(doc))):
        im=Image.open(pages/f'p{i+1:03d}.png');im.thumbnail((490,690))
        x=(i-start)%3*500;y=(i-start)//3*725
        canvas.paste(im,(x,y+20));ImageDraw.Draw(canvas).text((x+8,y),str(i+1),fill='black')
    canvas.save(pages/f'contact_{start+1:03d}.jpg')
summary=[];total=Counter();bad=[];examples=defaultdict(list)
with pdfplumber.open(path) as book:
    for i,p in enumerate(book.pages):
        sizes=Counter();fonts=Counter();outside=[]
        for c in p.chars:
            if not c['text'].strip(): continue
            key=(re.sub(r'^[A-Z]{6}\+','',c['fontname']),round(c['size'],2))
            total[key]+=1;fonts[key[0]]+=1;sizes[key[1]]+=1
            if i<31 and len(examples[key])<10:examples[key].append([i+1,c['text']])
            if c['top']<69 or c['x0']<69 or c['x1']>p.width-69 or (c['bottom']>p.height-69 and c['top']<790):
                outside.append({'text':c['text'],'bbox':[round(c[k],1) for k in ['x0','top','x1','bottom']]})
        text=p.extract_text()
        if '\ufffd' in text:bad.append(i+1)
        summary.append({'page':i+1,'sizes':sizes.most_common(),'fonts':fonts.most_common(),'outside_body_margin':outside[:25]})
        p.close()
stats={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'build_sha256':hashlib.sha256((base/'图像压缩版/build_appendix/main.pdf').read_bytes()).hexdigest(),'pages':len(doc),'font_sizes':[{'font':k[0],'size':k[1],'count':v,'examples':examples[k]} for k,v in total.most_common()],'replacement_character_pages':bad,'page_stats':summary}
(out/'audit.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps({k:v for k,v in stats.items() if k not in ['page_stats','font_sizes']},ensure_ascii=False,indent=2))
print(json.dumps(stats['font_sizes'][:35],ensure_ascii=False,indent=2))
