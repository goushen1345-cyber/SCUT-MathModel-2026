from pathlib import Path
import pypdfium2 as pdf
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parents[2];T=Path(__file__).resolve().parent/'final_pages';T.mkdir(exist_ok=True)
for name,pages in [('AI工具使用详情',[1,2,3]),('支撑材料附录',[1,2,3,4,19,30,40,49])]:
 doc=pdf.PdfDocument(str(P/'paper/提交配套'/f'{name}.pdf'))
 for n in pages:
  if n<=len(doc):doc[n-1].render(scale=1.6).to_pil().save(T/f'{name}_{n}.png')
 for j in range(0,len(pages),4):
  canvas=Image.new('RGB',(1400,2040),'#ddd');draw=ImageDraw.Draw(canvas)
  for k,n in enumerate(pages[j:j+4]):
   im=Image.open(T/f'{name}_{n}.png').convert('RGB');im.thumbnail((690,980));x=k%2*700;y=k//2*1020;canvas.paste(im,(x,y+25));draw.text((x+10,y+3),f'page {n}',fill='black')
  canvas.save(T/f'{name}_contact{j//4+1}.jpg')
 print(name,len(doc))
