from pathlib import Path
import json,re,hashlib
from pypdf import PdfReader
import pypdfium2 as pdf
from PIL import Image

root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
work=Path(__file__).parent
base=root/'shumo_1/shumo_backup_20260913_003434'
src=base/'图像压缩版'
path=src/'build_appendix/main.pdf'
r=PdfReader(path);doc=pdf.PdfDocument(path)
texts=[p.extract_text() for p in r.pages]
assert len(r.pages)==91
assert all('??' not in t and '[?]' not in t and '[?,?]' not in t for t in texts[:31])
assert '关键词' in texts[0] and '附录 A' in texts[31]
assert all(str(i+1)==t.strip().splitlines()[-1].strip() for i,t in enumerate(texts))
assert all(abs(float(p.mediabox.width)-595.276)<1 and abs(float(p.mediabox.height)-841.89)<1 for p in r.pages)
log=(src/'build_appendix/main.log').read_text('utf-8',errors='replace')
bad=[s for s in ['Overfull','Missing character:','undefined references','Label(s) may have changed','Citation `','Font shape'] if s in log and (s!='Font shape' or 'undefined' in log)]
assert not bad,bad
assert (src/'main.tex').read_bytes()==(work/'before_main.tex').read_bytes()
assert all(f.read_bytes()==(work/'before_sections'/f.name).read_bytes() for f in (src/'sections').glob('*.tex'))
fonts={};seen=set()
def scan(resources):
    if not resources:return
    resources=resources.get_object()
    for f in resources.get('/Font',{}).get_object().values() if resources.get('/Font') else []:
        f=f.get_object();key=str(f.get('/BaseFont','Type3'))
        if key in fonts:continue
        if f.get('/Subtype')=='/Type3':
            embedded=bool(f.get('/CharProcs'))
        else:
            font=f.get('/DescendantFonts',[f])[0].get_object()
            desc=font.get('/FontDescriptor',{}).get_object() if font.get('/FontDescriptor') else {}
            embedded=any(desc.get(k) for k in ['/FontFile','/FontFile2','/FontFile3'])
        fonts[key]={'embedded':embedded,'subtype':str(f.get('/Subtype'))}
    for xref in resources.get('/XObject',{}).get_object().values() if resources.get('/XObject') else []:
        xid=(getattr(xref,'idnum',None),getattr(xref,'generation',None))
        if xid in seen:continue
        seen.add(xid);x=xref.get_object()
        if x.get('/Resources'):scan(x['/Resources'])
for p in r.pages:scan(p.get('/Resources'))
assert all(f['embedded'] for f in fonts.values()),fonts
citations={k:r.get_destination_page_number(d)+1 for k,d in r.named_destinations.items() if k.startswith('cite.')}
assert len(citations)==9 and set(citations.values())=={31}
out=work/'final_pages';out.mkdir(exist_ok=True)
diff=[]
for i in range(31):
    im=doc[i].render(scale=1.25).to_pil()
    old=root/f'tmp/language_refs_20260913/pages/p{i+1:03d}.png'
    if im.tobytes()!=Image.open(old).tobytes():diff.append(i+1)
    if i in [0,8,10,19,23,24,25,27,28,29,30]:
        doc[i].render(scale=1.6).to_pil().save(out/f'p{i+1:03d}.png')
before=pdf.PdfDocument(work/'before.pdf')
appendix_unchanged=all(doc[i].render(scale=1).to_pil().tobytes()==before[i].render(scale=1).to_pil().tobytes() for i in range(31,91))
assert appendix_unchanged
summary={'pages':91,'abstract_pages':1,'body_pages_including_references':30,'appendix_pages':60,'all_fonts_embedded':True,'font_resource_count':len(fonts),'font_resources':fonts,'unresolved_references':False,'bibliography_targets':citations,'source_files_unchanged':True,'appendix_pixels_unchanged':True,'body_pages_different_from_previous_verified_render':diff,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(work/'final_qa.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='font_resources'},ensure_ascii=False,indent=2))
