from pathlib import Path
import json,hashlib,shutil
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
orig=root/'shumo_1/shumo_backup_20260913_003434'
audit=Path((root/'tmp/compressed_paper_audit_path.txt').read_text('utf-8').strip())
hashes=json.loads((audit/'original_hashes.json').read_text('utf-8'))
assert all(hashlib.sha256((orig/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
target=orig/'main（压缩版）.pdf'
assert not target.exists(),'Inspect existing deliverable before replacing'
shutil.copy2(audit/'build/main.pdf',target)
verification=json.loads((audit/'verification.json').read_text('utf-8'))
verification.update({'visual_review':'Rendered all 37 final pages and inspected contact sheets; no observed overlaps or clipping. Original font size and line spacing retained.','delivered_pdf':str(target),'pdf_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'original_unchanged_after_delivery':True})
(audit/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),'utf-8')
entry='''

## 2026-09-13：独立论文压缩版落稿

- 用户授权将聊天确认的合理压缩稿写入独立论文，PDF名称后加“（压缩版）”，不得覆盖原 main.pdf。
- 独立源文件位于 shumo_1/shumo_backup_20260913_003434/压缩版/，入口 main.tex，正文在 sections/。修改问题分析、数据章节及四问正文，合并重复小节与约束说明，保留必要解释、求解步骤、参数依据和指定结果。
- 四问小节数分别为4、5、6、5；19个原结果表环境及全部表数据逐字保留。正文仅移除问题三重复月度费用图，保留14幅图，原图文件均保留。摘要、背景、模型假设和符号内容、模型评价文字保持原样，仅取消模型假设后的强制换页。
- 新文件 main（压缩版）.pdf 共37页，原版42页。保留原字号、行距与页边距；两次稳定编译，无缺字、越界或未定义引用提示。已渲染全部37页并查看页面总览，核对图表与公式排版。原PDF、原正文、表文件和图文件的SHA256核对均未变化。
- 核对记录、编译日志和渲染页面保存在 tmp/compressed_paper_20260913_134417。未新增实验，未改模型、结果或state.json，不推进研究阶段；本次为AI文字和版面核对，不代表人工终审。
'''
for name in ['decisions.md','ai_usage_log.md']:
    with (root/'state'/name).open('a',encoding='utf-8') as f:f.write(entry)
print(str(target))
print('37 pages; original PDF and all tracked paper files unchanged.')
