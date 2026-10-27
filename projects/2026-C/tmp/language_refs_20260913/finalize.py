from pathlib import Path
import difflib, hashlib, json, shutil
from pypdf import PdfReader

root = Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
work = Path(__file__).parent
src = root / 'shumo_1/shumo_backup_20260913_003434/图像压缩版'
pdf = src / 'build_appendix/main.pdf'
qa = json.loads((work / 'qa.json').read_text('utf-8'))
assert hashlib.sha256(pdf.read_bytes()).hexdigest() == qa['sha256']
assert qa['body_pages_including_declaration_references'] == 30
assert all(p <= 31 for p in qa['changed_pixel_pages'])
reader = PdfReader(pdf)
destinations = reader.named_destinations
citations = sorted(k for k in destinations if k.startswith('cite.'))
assert len(citations) == 9, citations
assert all(reader.get_destination_page_number(destinations[k]) == 30 for k in citations)
links = []
for i, page in enumerate(reader.pages[:30]):
    for entry in page.get('/Annots', []):
        annotation = entry.get_object()
        action = annotation.get('/A', {})
        if hasattr(action, 'get_object'):
            action = action.get_object()
        target = annotation.get('/Dest', action.get('/D', ''))
        if isinstance(target, str) and target.startswith('cite.'):
            assert target in destinations
            links.append({'pdf_page': i + 1, 'target': target})
assert set(x['target'] for x in links) == set(citations), links
diffs = []
for current in sorted(src.rglob('*.tex')):
    if 'build_appendix' in current.parts:
        continue
    rel = current.relative_to(src)
    old = work / 'before_source' / rel
    previous = old.read_text('utf-8') if old.exists() else ''
    now = current.read_text('utf-8')
    if now != previous:
        diffs.extend(difflib.unified_diff(previous.splitlines(True), now.splitlines(True), fromfile=f'before/{rel}', tofile=f'after/{rel}'))
(work / 'final_changes.diff').write_text(''.join(diffs), 'utf-8')
target = src.parent / 'main(图像压缩版）.pdf'
shutil.copy2(pdf, target)
assert hashlib.sha256(target.read_bytes()).hexdigest() == qa['sha256']
qa.update({'delivered_pdf': str(target), 'citation_destinations': citations, 'body_citation_links': links, 'visual_review': 'All revised body pages checked; no overlapping, clipping, intrusive floats or abnormal empty pages found. Appendix pages 32-91 pixel-identical to previous PDF.'})
(work / 'qa.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), 'utf-8')
print(json.dumps({'delivered_pdf': str(target), 'body_pages': 30, 'total_pages': len(reader.pages), 'citation_keys': len(citations), 'citation_links': len(links), 'sha256': qa['sha256']}, ensure_ascii=False, indent=2))
