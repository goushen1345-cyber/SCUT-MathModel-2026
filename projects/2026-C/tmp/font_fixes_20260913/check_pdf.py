from pathlib import Path
import re,json,hashlib
from pypdf import PdfReader
import pypdfium2 as pdf
from PIL import Image,ImageDraw
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
w=Path(__file__).parent
src=root/'shumo_1/shumo_backup_20260913_003434/图像压缩版'
path=src/'build_appendix/main.pdf'
r=PdfReader(path);texts=[p.extract_text() for p in r.pages]
appendix=next(i for i,t in enumerate(texts) if '附录 A 问题四指定日期的详细调度结果' in t)
assert appendix==31 and '关键词' in texts[0]
assert all('??' not in t and '[?]' not in t for t in texts[:31])
assert all(str(i+1)==t.strip().splitlines()[-1].strip() for i,t in enumerate(texts))
assert all(abs(float(p.mediabox.width)-595.276)<1 and abs(float(p.mediabox.height)-841.89)<1 for p in r.pages)
log=(src/'build_appendix/main.log').read_text('utf-8',errors='replace')
bad=[s for s in ['Overfull','Missing character:','undefined references','Label(s) may have changed','Citation `'] if s in log]
assert not bad,bad
def unformat(s):
    for c in ['textbf','mbox']:
        s=re.sub(r'\\'+c+r'\{([^{}]*)\}',r'\1',s)
    s=s.replace('\\urlstyle{same}','')
    return re.sub(r'\s+','',s)
for f in (w/'before_source/sections').glob('*.tex'):
    assert unformat(f.read_text('utf-8'))==unformat((src/'sections'/f.name).read_text('utf-8')),f.name
for f in (w/'before_source/tables').glob('*.tex'):
    assert f.read_bytes()==(src/'tables'/f.name).read_bytes()
assert (w/'before_source/main.tex').read_bytes()==(src/'main.tex').read_bytes()
citations={k:r.get_destination_page_number(v)+1 for k,v in r.named_destinations.items() if k.startswith('cite.')}
assert len(citations)==9 and set(citations.values())=={31}
doc=pdf.PdfDocument(path);old=pdf.PdfDocument(w/'before.pdf')
out=w/'pages';out.mkdir(exist_ok=True)
changed=[]
for i in range(len(doc)):
    im=doc[i].render(scale=1.4).to_pil()
    if i>=len(old) or im.tobytes()!=old[i].render(scale=1.4).to_pil().tobytes():
        changed.append(i+1);im.save(out/f'p{i+1:03d}.png')
for start in range(0,len(changed),6):
    canvas=Image.new('RGB',(1500,1450),'#DDD')
    for j,n in enumerate(changed[start:start+6]):
        im=Image.open(out/f'p{n:03d}.png');im.thumbnail((490,690))
        x=j%3*500;y=j//3*725
        canvas.paste(im,(x,y+20));ImageDraw.Draw(canvas).text((x+8,y),str(n),fill='black')
    canvas.save(out/f'contact_{start//6+1:02d}.jpg')
(w/'body_text.txt').write_text('\n\n'.join(f'PAGE {i+1}\n{t}' for i,t in enumerate(texts[:31])),'utf-8')
res={'total_pages':len(r.pages),'abstract_pages':1,'body_pages':30,'appendix_pages':len(r.pages)-31,'bytes':path.stat().st_size,'bad_log_flags':bad,'all_source_text_formulas_and_numbers_unchanged':True,'table_sources_unchanged':True,'citation_count':9,'changed_pages':changed,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(w/'pdf_qa.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
