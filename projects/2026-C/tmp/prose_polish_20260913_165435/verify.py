from pathlib import Path
import re, json, difflib, hashlib
from pypdf import PdfReader
from PIL import Image, ImageOps, ImageDraw

project = Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
work = project/'tmp/prose_polish_20260913_165435'
paper = project/'shumo_1/shumo_backup_20260913_003434'
src = paper/'图像压缩版'
old = work/'source_before'
read = lambda p: p.read_text(encoding='utf-8-sig')
a, b = read(old/'sections/sec_0_abstract.tex'), read(src/'sections/sec_0_abstract.tex')
title = '融合多源预测的微网经济调度与线性优化研究'
assert re.search(r'\\title\{([^\n]*)\}',b).group(1) == title
assert a.split(r'\begin{abstract}',1)[1] == b.split(r'\begin{abstract}',1)[1]
assert (old/'main.tex').read_bytes() == (src/'main.tex').read_bytes()
assets = 0
for folder in ['fig','tables']:
    for p in (old/folder).rglob('*'):
        if p.is_file():
            assert p.read_bytes() == (src/p.relative_to(old)).read_bytes(), str(p)
            assets += 1
    assert sorted(str(p.relative_to(old/folder)) for p in (old/folder).rglob('*') if p.is_file()) == sorted(str(p.relative_to(src/folder)) for p in (src/folder).rglob('*') if p.is_file())
formulas = lambda s: re.findall(r'\\begin\{(equation\*?|align\*?|gather\*?|multline\*?)\}([\s\S]*?)\\end\{\1\}',s)
tabulars = lambda s: re.findall(r'\\begin\{(tabular\*?|longtable)\}([\s\S]*?)\\end\{\1\}',s)
formula_count = 0
for p in sorted((src/'sections').glob('*.tex')):
    before = old/'sections'/p.name
    assert before.exists(), p.name
    assert formulas(read(before)) == formulas(read(p)), p.name+' formulas'
    assert tabulars(read(before)) == tabulars(read(p)), p.name+' tabulars'
    formula_count += len(formulas(read(p)))
tail = lambda s: s.split(r'\subsection{模型局限与改进方向}',1)[1]
assert tail(read(old/'sections/sec_9_create.tex')) == tail(read(src/'sections/sec_9_create.tex'))
allsource = '\n'.join(read(p) for p in (src/'sections').glob('*.tex'))
assert allsource.count('我们') == 2
pdf = work/'build/main.pdf'
r = PdfReader(pdf)
assert len(r.pages) == 34
pdftext = '\n'.join(p.extract_text() for p in r.pages)
assert title in re.sub(r'\s+', '', r.pages[0].extract_text())
for number in ['35126.85','13583810.84','13014172.33','14248570.87','13695929.70']:
    assert number in pdftext, number
log = read(work/'build/main.log')
for error in ['Overfull','Missing character','undefined references','Label(s) may have changed']:
    assert error not in log, error
assert not re.search(r'(Reference|Citation).*undefined',log)
changes, diff = [], []
for p in sorted((src/'sections').glob('*.tex')):
    prior = old/'sections'/p.name
    if read(prior) != read(p):
        changes.append(p.name)
        diff.extend(difflib.unified_diff(read(prior).splitlines(True),read(p).splitlines(True),fromfile=p.name+' before',tofile=p.name+' after'))
(work/'changes.diff').write_text(''.join(diff),encoding='utf-8')
report = {
    'title': title, 'pages':34, 'abstract_pages':1, 'body_pages':30, 'appendix_pages':3,
    'changed_chapters':changes, 'abstract_body_unchanged':True, 'main_tex_unchanged':True,
    'unchanged_figure_and_table_asset_files':assets, 'unchanged_formula_environments':formula_count,
    'inline_table_bodies_unchanged':True, 'limitations_and_promotion_unchanged':True,
    'key_total_costs_unchanged':True, 'author_we_occurrences':2,
    'no_overfull_missing_char_or_unresolved_reference':True,
    'environment_notices':'Existing LaTeX release and CJK font-family redefinition warnings only',
    'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
    'visual_check':'All final pages rendered; final pages 1,9,16,17,18,24,31 inspected in detail. Independent read-only check of final pages 11,12,23,29,30 found no sentence interruptions, overlap or clipping.'
}
(work/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
for group in range(3):
    pages = list(range(group*12+1, min(group*12+13,35)))
    contact = Image.new('RGB',(1920,2220),'#cccccc')
    draw = ImageDraw.Draw(contact)
    for i, n in enumerate(pages):
        im=Image.open(work/f'final-page-{n:02d}.png').convert('RGB')
        im=ImageOps.contain(im,(466,700))
        x=(i%4)*480+(480-im.width)//2
        y=(i//4)*740+28
        contact.paste(im,(x,y))
        draw.text(((i%4)*480+12,(i//4)*740+6),f'Final PDF page {n}',fill='black')
    contact.save(work/f'final-contact-{group+1}.png')
print(json.dumps(report,ensure_ascii=False,indent=2))
