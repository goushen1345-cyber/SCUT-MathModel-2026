from pathlib import Path
import re,json,hashlib
from PIL import Image,ImageDraw
import pypdf,pypdfium2 as pdf
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
src=root/'shumo_1/shumo_backup_20260913_003434/图像压缩版'
t=Path(__file__).parent
path=src/'build_appendix/main.pdf'
reader=pypdf.PdfReader(path);old=pypdf.PdfReader(t/'before.pdf')
texts=[p.extract_text() for p in reader.pages]
log=(src/'build_appendix/main.log').read_text('utf-8',errors='replace')
bad=[x for x in ['Missing character:','Overfull','undefined references','Label(s) may have changed','Citation `'] if x in log]
appendix_start=next(i for i,s in enumerate(texts) if '附录 A 问题四指定日期的详细调度结果' in s)
assert not bad,bad
assert appendix_start<=31,appendix_start
assert '关键词' in texts[0]
assert '一、 问题重述' in texts[1]
assert all(str(i+1)==s.strip().splitlines()[-1].strip() for i,s in enumerate(texts))
assert len(re.findall(r'\\bibitem\{', (src/'sections/references.tex').read_text('utf-8')))==9
assert not re.search(r'SCUT|华南理工|wxid_|Users[/\\]Rog',''.join(texts),re.I)
assert path.stat().st_size<20_000_000
assert all(abs(float(p.mediabox.width)-595.276)<1 and abs(float(p.mediabox.height)-841.89)<1 for p in reader.pages)
for f in ['appendix_support.tex','appendix_q4_details.tex']:
    assert (src/'sections'/f).read_bytes()==(t/'before_source/sections'/f).read_bytes()
# Mathematical expressions and supplied table sources must not be changed by language editing.
env=re.compile(r'\\begin\{(equation|align)\*?\}.*?\\end\{\1\*?\}',re.S)
for f in (src/'sections').glob('sec_[3-8]*.tex'):
    a=env.findall(f.read_text('utf-8'))
    current=[m.group(0) for m in env.finditer(f.read_text('utf-8'))]
    original=[m.group(0) for m in env.finditer((t/'before_source/sections'/f.name).read_text('utf-8'))]
    assert current==original,f.name
for f in (src/'tables').glob('*.tex'):
    assert f.read_bytes()==(t/'before_source/tables'/f.name).read_bytes()
doc=pdf.PdfDocument(path);before=pdf.PdfDocument(t/'before.pdf')
changed=[]
v=t/'pages';v.mkdir(exist_ok=True)
for i in range(len(doc)):
    im=doc[i].render(scale=1.25).to_pil()
    changed_pixel=i>=len(before) or im.tobytes()!=before[i].render(scale=1.25).to_pil().tobytes()
    if changed_pixel:
        changed.append(i+1)
    if i<appendix_start+6 or changed_pixel:
        im.save(v/f'p{i+1:03d}.png')
for start in range(0,appendix_start+6,6):
    canvas=Image.new('RGB',(1680,1580),'#DDD')
    for i in range(start,min(start+6,appendix_start+6)):
        im=Image.open(v/f'p{i+1:03d}.png');im.thumbnail((550,760))
        x=(i-start)%3*560;y=(i-start)//3*790
        canvas.paste(im,(x,y+20));ImageDraw.Draw(canvas).text((x+8,y),str(i+1),fill='black')
    canvas.save(v/f'contact_{start+1:03d}.jpg')
(t/'final_text.txt').write_text('\n\n'.join(f'=== PDF第{i+1}页 ===\n{s}' for i,s in enumerate(texts[:appendix_start+6])),encoding='utf-8')
summary={'pages':len(reader.pages),'abstract_pages':1,'body_pages_including_declaration_references':appendix_start-1,'appendix_start_pdf_page':appendix_start+1,'bytes':path.stat().st_size,'bibliography_items':9,'bad_log_flags':bad,'changed_pixel_pages':changed,'equations_and_tables_unchanged':True,'appendix_sources_unchanged':True,'a4':True,'continuous_numbering':True,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(t/'qa.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
