from pathlib import Path
import zipfile,json
import pypdfium2 as pdf
from PIL import Image,ImageDraw
from pypdf import PdfReader
R=Path(__file__).resolve().parent
S=Path('E:/文档/xwechat_files/wxid_9cspft7j507912_dc1e/temp/RWTemp/2026-09/c3fdd19327d183da9a0ef2999900bf5e')
with zipfile.ZipFile(S/'范例-支撑材料.zip') as z:
 for i in z.infolist():
  name=i.filename
  if not i.flag_bits&0x800:
   try:name=name.encode('cp437').decode('gbk')
   except (UnicodeError,LookupError):pass
  p=(R/'sample_support'/name).resolve()
  assert p.is_relative_to((R/'sample_support').resolve())
  if not i.is_dir():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(i))
files={'notice':Path('E:/Projects/SCUT-MathModel-2026-backup-20260906/docs/2026高教社杯全国大学生数学建模竞赛第一次通知 (1).pdf'),'sample':S/'范例-论文.pdf','sample_ai':next((R/'sample_support').glob('*.pdf'))}
for name,path in files.items():
 doc=pdf.PdfDocument(str(path));out=R/name;out.mkdir(exist_ok=True)
 texts=[]
 for i,page in enumerate(doc):
  im=page.render(scale=1.6).to_pil().convert('RGB');im.save(out/f'p{i+1:02}.png')
  texts.append(page.get_textpage().get_text_range())
 (out/'text.txt').write_text('\n\n'.join(texts),encoding='utf-8')
 for j in range(0,len(doc),4):
  canvas=Image.new('RGB',(1200,1750),'#ccc');d=ImageDraw.Draw(canvas)
  for k in range(j,min(j+4,len(doc))):
   im=Image.open(out/f'p{k+1:02}.png');im.thumbnail((590,842));x=(k-j)%2*600;y=(k-j)//2*875
   canvas.paste(im,(x,y+22));d.text((x+10,y+3),f'{name} page {k+1}',fill='black')
  canvas.save(out/f'contact{j//4+1:02}.jpg')
 print(name,len(doc),len(''.join(texts)),flush=True)
