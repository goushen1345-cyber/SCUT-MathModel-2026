from pathlib import Path
import hashlib,json,difflib,shutil
from pypdf import PdfReader
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
src=root/'shumo_1/shumo'; backup=root/'shumo_1/shumo_backup_20260913_003434'
out=root/'tmp/shumo-supplements-20260913'; build=out/'build'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected=json.loads((build/'source_hashes.json').read_text('utf-8'))
assert all(sha(src/f)==h for f,h in expected.items()), 'Source changed since verified build'
changed=[];diff=[]
for p in backup.rglob('*'):
    if not p.is_file():continue
    rel=p.relative_to(backup); live=src/rel
    assert live.exists(), f'Missing live file {rel}'
    if sha(p)!=sha(live):
        changed.append(rel.as_posix())
        if p.suffix=='.tex':diff.extend(difflib.unified_diff(p.read_text('utf-8').splitlines(True),live.read_text('utf-8').splitlines(True),fromfile='backup/'+rel.as_posix(),tofile='shumo/'+rel.as_posix()))
allowed={f'sections/sec_{x}.tex' for x in ['4_data_preprocessing','5_q1','6_q2','7_q3','8_q4']}
assert {f for f in changed if f.endswith('.tex')}==allowed
assert all(f in allowed or f in ['main.pdf','main.log','main.out','main.aux','main.synctex.gz'] for f in changed), changed
log=(build/'main.log').read_text('utf-8',errors='replace')
for bad in ['Overfull','Missing character','There were undefined references','Label(s) may have changed']:
    assert bad not in log,bad
pdf=PdfReader(build/'main.pdf'); assert len(pdf.pages)==55
for ext in ['pdf','aux','out','log']:
    shutil.copy2(build/f'main.{ext}',src/f'main.{ext}')
assert sha(src/'main.pdf')==sha(build/'main.pdf')
(out/'final.diff').write_text(''.join(diff),'utf-8')
audit={'backup':str(backup),'backup_file_count':len([p for p in backup.rglob('*') if p.is_file()]),'backup_hashes':{p.relative_to(backup).as_posix():sha(p) for p in backup.rglob('*') if p.is_file()},'edited_tex':sorted(allowed),'source_hashes':expected,'pdf_sha256':sha(src/'main.pdf'),'pages':len(pdf.pages),'visual_review':{'overview_pages':'1-55','detail_pages':[28,31,37,43,49,52]},'compile_checks':'no undefined references, missing characters, overfull boxes or unstable labels','research_state_modified':False}
(out/'verification.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),'utf-8')
p=root/'state/ai_usage_log.md'
with p.open('a',encoding='utf-8') as f:
    f.write('\n\n## 2026-09-13 shumo 备份与已批准补充文字落稿\n\n- 用户授权：先备份 shumo 文件夹，再将上一轮列明的补充内容精准加入 TeX。\n- 工具与用途：Codex、cumcm-paper-builder、PDF 工具；文件逐项定位、SHA256备份核对、XeLaTeX编译、Poppler页面检查。\n- 备份：shumo_1/shumo_backup_20260913_003434，完整34文件，复制时逐一哈希一致。\n- 修改：仅实际引用的五个正文源文件（数据章节及四问），完成清单39处插入/替换，恢复紧急购电表及Q4指定日结果表；另修正四问的中文货币单位字体和局部表宽/长行。未修改外层重复TeX、图片、研究代码、数据或正式state.json。\n- 验证：独立目录编译两遍并核对源文件哈希稳定；55页PDF总览及第28、31、37、43、49、52页细查；无未定义引用、缺字、越出版心和标签变化警告。成果同步回shumo/main.pdf。\n- 差异与核对记录：tmp/shumo-supplements-20260913/final.diff、verification.json。\n- 采用与人工核验：本次为用户授权编辑，AI完成上述检查，用户最终人工审阅待进行；不代表论文提交批准或研究冻结。\n')
print(json.dumps({'edited_tex':sorted(allowed),'backup':str(backup),'pdf':str(src/'main.pdf'),'pages':55,'checks':'passed'},ensure_ascii=False))
