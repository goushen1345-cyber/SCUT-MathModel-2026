from pathlib import Path
import json,hashlib,re
import pypdf,pypdfium2 as pdf
from PIL import Image,ImageDraw

P=Path(__file__).resolve().parents[2];T=Path(__file__).parent
S=P/'shumo_1/shumo_backup_20260913_003434/图像压缩版';D=P/'支撑材料'
path=S/'build_appendix/main.pdf';r=pypdf.PdfReader(path)
old=pypdf.PdfReader(T/'before/main(图像压缩版）.pdf')
doc=pdf.PdfDocument(path);before=pdf.PdfDocument(T/'before/main(图像压缩版）.pdf')
text_diffs=[];pixel_diffs=[]
for i in range(34):
 if r.pages[i].extract_text()!=old.pages[i].extract_text():text_diffs.append(i+1)
 if doc[i].render(scale=1).to_pil().tobytes()!=before[i].render(scale=1).to_pil().tobytes():pixel_diffs.append(i+1)
assert not text_diffs,text_diffs
assert not pixel_diffs,pixel_diffs
manifest=json.loads((T/'manifest.json').read_text('utf-8'))
actual=sorted(p.relative_to(D).as_posix() for p in D.rglob('*') if p.is_file() and not p.name.startswith('~$') and '__pycache__' not in p.parts)
assert actual==sorted(manifest['file_hashes']), 'Supporting file list changed'
for name in manifest['source_files']:
 assert hashlib.sha256((D/name).read_bytes()).hexdigest()==manifest['file_hashes'][name],name
source=(S/'sections/appendix_support.tex').read_text('utf-8')
assert source.count('\\VerbatimInput[')==20
assert source.count('\\item ')==86
assert not re.search(r'firstline=|lastline=',source)
log=(S/'build_appendix/main.log').read_text('utf-8',errors='replace')
assert not any(v in log for v in ['Missing character:','Overfull','undefined references','Label(s) may have changed'])
texts=[p.extract_text() for p in r.pages]
assert not re.search(r'SCUT|华南理工|wxid_|Users[/\\]Rog',''.join(texts[34:]),re.I)
assert path.stat().st_size<20_000_000
assert all(abs(float(p.mediabox.width)-595.276)<1 and abs(float(p.mediabox.height)-841.89)<1 for p in r.pages)
assert all(str(i+1)==p.extract_text().strip().splitlines()[-1].strip() for i,p in enumerate(r.pages)), 'footer numbering'
V=T/'final_pages';V.mkdir(exist_ok=True)
for i in range(34,len(doc)):doc[i].render(scale=1.3).to_pil().save(V/f'p{i+1:03d}.png')
for start in range(34,len(doc),6):
 canvas=Image.new('RGB',(1680,1580),'#DDD')
 for i in range(start,min(start+6,len(doc))):
  im=Image.open(V/f'p{i+1:03d}.png');im.thumbnail((550,760));x=(i-start)%3*560;y=(i-start)//3*790;canvas.paste(im,(x,y+20));ImageDraw.Draw(canvas).text((x+8,y),str(i+1),fill='black')
 canvas.save(V/f'contact_{start+1:03d}.jpg')
summary=dict(pages=len(r.pages),bytes=path.stat().st_size,abstract_pages=1,body_pages=30,appendix_pages=len(r.pages)-31,original_34_pages_text_and_pixels_identical=True,source_files=20,support_files=86,all_code_read_directly_from_unchanged_sources=True,continuous_page_numbers=True,a4=True,no_missing_glyphs_or_overflow=True)
(T/'final_qa.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
