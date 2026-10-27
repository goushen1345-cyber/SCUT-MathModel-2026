from pathlib import Path
import re,json,hashlib,shutil
from pypdf import PdfReader
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
src=root/'shumo_1/shumo_backup_20260913_003434'
tmp=root/'tmp/approved-abstract-20260913'
saved=root/'paper/abstract_before_approved_text_20260913'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(src/'main.tex')==sha(saved/'main.tex'),'Main layout was changed'
hashes=json.loads((tmp/'build/source_hashes.json').read_text('utf-8'))
assert all(sha(src/p)==h for p,h in hashes.items())
log=(tmp/'build/main.log').read_text('utf-8',errors='replace')
assert not any(s in log for s in ('Overfull','Missing character','There were undefined references','Label(s) may have changed'))
reader=PdfReader(tmp/'build/main.pdf')
first=reader.pages[0].extract_text() or ''
second=reader.pages[1].extract_text() or ''
tex=(src/'sections/sec_0_abstract.tex').read_text('utf-8-sig')
abstract=tex.split(r'\begin{abstract}',1)[1].split(r'\end{abstract}',1)[0]
abstract=abstract.replace(r'\noindent\hspace*{2em}','')
abstract=re.sub(r'\\textbf\{([^{}]*)\}',r'\1',abstract).replace(r'\%','%')
normalize=lambda s:re.sub(r'\s+','',s)
assert normalize(abstract) in normalize(first),'Abstract text spills or differs'
assert '关键词' in first and '电价预测' in first
assert normalize(second).startswith('一、问题重述')
pdf_target=src/'main.pdf'
locked=[]
try:shutil.copy2(tmp/'build/main.pdf',pdf_target)
except PermissionError:
    locked.append('main.pdf')
    pdf_target=src/'main_摘要更新.pdf'
    shutil.copy2(tmp/'build/main.pdf',pdf_target)
for ext in ('aux','out','log'):
    file=tmp/f'build/main.{ext}'
    if file.exists():
        try:shutil.copy2(file,src/file.name)
        except PermissionError:locked.append(file.name)
assert sha(pdf_target)==sha(tmp/'build/main.pdf')
record={'scope':'User-approved abstract only','pdf_path':str(pdf_target),'locked_existing_files':locked,'pdf_sha256':sha(pdf_target),'tex_sha256':sha(src/'sections/sec_0_abstract.tex'),'pdf_pages':len(reader.pages),'abstract_pages':1,'approved_text_present_in_full':True,'main_tex_unchanged':True,'abstract_stretch':1.22,'visual_review_pages':[1,2],'compiler_warnings_checked':True,'human_final_review':False}
(tmp/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf-8')
entry='''

## 2026-09-13：用户确认的新摘要落稿

- 用户原话“ok，把这个写进shumo_backup_20260913_003434的论文里吧”。采用本轮确认的“随着我国碳达峰、碳中和目标的推进……”全文，保留各问、方法、结果及关键结论的加黑；不重新措辞或改变数字。
- 仅修改实际入口 sections/sec_0_abstract.tex。保留现有主文件和字体；摘要局部行距从1.38收紧至1.22，保持小四字，让全文摘要及关键词完整位于一页。正文主排版未改。
- 修改前摘要、主文件及PDF保存于paper/abstract_before_approved_text_20260913。稳定编译后实际查看第1—2页，加黑、页内完整性和正文衔接正常；无缺字、越界或未定义引用警告。
- 检查记录tmp/approved-abstract-20260913/verification.json；用户已确认摘要文字，页面检查由AI完成，不代表全篇人工通过。未新增研究、求解、改数据或变更state.json。
'''
entry+=f'\n- 实际交付PDF：{pdf_target.relative_to(root)}；未强制关闭占用文件的程序。锁定未覆盖文件：{locked}。\n'
for name in ('decisions.md','ai_usage_log.md'):
    file=root/'state'/name
    prior=file.read_text('utf-8-sig')
    if '用户确认的新摘要落稿' not in prior:file.write_text(prior.rstrip()+entry,'utf-8')
print(json.dumps(record,ensure_ascii=False))
