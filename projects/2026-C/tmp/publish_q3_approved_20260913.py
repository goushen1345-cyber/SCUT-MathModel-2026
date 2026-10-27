from pathlib import Path
import hashlib,json,shutil,re
from pypdf import PdfReader
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
src=root/'shumo_1/shumo_backup_20260913_003434'
backup=Path((root/'tmp/q3_approved_backup_path.txt').read_text('utf-8'))
before=json.loads((backup/'source_hashes.json').read_text('utf-8'))
changed=[rel.replace('\\','/') for rel,h in before.items() if hashlib.sha256((src/rel).read_bytes()).hexdigest()!=h]
assert set(changed)=={'sections/sec_2_problem_analysis.tex','sections/sec_7_q3.tex'},changed
build=root/'tmp/approved-abstract-20260913/build'
log=(build/'main.log').read_text('utf-8',errors='replace')
for warning in ['Overfull','Missing character','There were undefined references','Label(s) may have changed','multiply defined']:
    assert warning not in log,warning
reader=PdfReader(build/'main.pdf')
assert len(reader.pages)==44
text='\n'.join(p.extract_text() for p in reader.pages)
for phrase in ['30.10','15.88','27.22','6.95','Step 1','13014172.33','0.60']:
    assert phrase in text,phrase
shutil.copy2(build/'main.pdf',src/'main.pdf')
record={'scope':'Approved Q3 text revision and overall framework insertion after problem analysis',
        'changed_existing_files':changed,'all_other_tracked_sources_tables_figures_unchanged':True,
        'pdf_pages':len(reader.pages),'framework_page':5,'q3_pages':[27,37],
        'visual_review_pages':[4,5,*range(27,38)],
        'compile_checks':'Stable references, no overfull boxes or missing characters',
        'research_data_or_state_changed':False,'review_status':'AI visual and compilation checks; not human approval',
        'pdf_sha256':hashlib.sha256((src/'main.pdf').read_bytes()).hexdigest()}
(backup/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf-8')
entry='''

## 2026-09-13：确认的问题三修订落稿与整体框架图插入

- 用户授权将本轮聊天确认的问题三完整修订稿写入 shumo_1/shumo_backup_20260913_003434 的论文，并将新版整体框架图放在问题分析之后。
- 修改实际编译的 sections/sec_7_q3.tex：统一基础符号，完善融合权重与动态准备的解释，求解过程改为四个 Step，整合指定日期分析；7.7明确回应是否引入日内预报，写入费用、紧急购电、未利用订单和光伏利用指标；7.8按确认版本修改结论。所有数值来自现有结果，未开展新研究。
- sections/sec_2_problem_analysis.tex 末尾引用已完成的 fig/model.pdf，新图位于第5页、模型假设之前。以 scripts/draw_q3_quantile.py 从现有 derived_values.json 单独重绘准备分位图，保留原复合图与原信息价值图文件，正文移除重复信息价值图。
- 原有3张内嵌对比表、外部表文件、其余章节与旧图均未改。源文件与旧PDF已备份至 BACKUP_PATH；验证记录同目录 verification.json。
- 完整PDF共44页，问题三位于第27—37页。两次编译后引用稳定，无越界、缺字或未定义引用；实际查看第4—5页及第27—37页，核对框架位置、图表、公式和分页。main.pdf已更新。
- 以上为AI文字与排版核对，不代表人工终审；不改 state.json，不推进研究阶段。
'''.replace('BACKUP_PATH',str(backup.relative_to(root)).replace('\\','/'))
for name in ['decisions.md','ai_usage_log.md']:
    with (root/'state'/name).open('a',encoding='utf-8') as f:f.write(entry)
print(json.dumps(record,ensure_ascii=False,indent=2))
