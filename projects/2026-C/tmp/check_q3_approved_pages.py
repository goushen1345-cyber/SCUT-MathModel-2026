from pathlib import Path
import subprocess,json
from pypdf import PdfReader
from PIL import Image,ImageOps,ImageDraw
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
pdf=root/'tmp/approved-abstract-20260913/build/main.pdf'
out=root/'tmp/q3_approved_page_check';out.mkdir(exist_ok=True)
reader=PdfReader(pdf)
print('PDF pages:',len(reader.pages))
pages=[4,5,*range(27,38)]
exe='C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe'
for n in pages:
    subprocess.run([exe,'-f',str(n),'-l',str(n),'-scale-to','1600','-png','-singlefile',str(pdf),str(out/f'p{n:02}')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
for group in [pages[:2],pages[2:6],pages[6:10],pages[10:]]:
    tiles=[]
    for n in group:
        im=Image.open(out/f'p{n:02}.png').convert('RGB');im.thumbnail((730,1040))
        tile=Image.new('RGB',(750,1080),'#dddddd');tile.paste(im,((750-im.width)//2,30))
        ImageDraw.Draw(tile).text((12,8),f'PDF page {n}',fill='black');tiles.append(tile)
    sheet=Image.new('RGB',(750*len(tiles),1080),'white')
    for i,tile in enumerate(tiles): sheet.paste(tile,(750*i,0))
    sheet.save(out/f'contact_{group[0]}_{group[-1]}.png')
(out/'page_text.json').write_text(json.dumps({n:reader.pages[n-1].extract_text() for n in pages},ensure_ascii=False,indent=2),'utf-8')
print('Rendered pages',pages)
