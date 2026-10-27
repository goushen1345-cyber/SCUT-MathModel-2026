from pathlib import Path
import re, json, difflib, shutil
from pypdf import PdfReader

project = Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
work = project/'tmp/focus_revision_20260913_153623'
paper = project/'shumo_1/shumo_backup_20260913_003434'
src = paper/'图像压缩版'
old = work/'source_before'
read = lambda p: p.read_text(encoding='utf-8-sig')
a, b = read(old/'sections/sec_0_abstract.tex'), read(src/'sections/sec_0_abstract.tex')
assert re.search(r'\\title\{[^\n]*', a).group() == re.search(r'\\title\{[^\n]*', b).group()
first = lambda s: s.split(r'\begin{abstract}',1)[1].split(r'\textbf{针对问题一}',1)[0]
assert first(a) == first(b)
assert (old/'main.tex').read_bytes() == (src/'main.tex').read_bytes()
for folder in ['fig','tables']:
    for p in (old/folder).rglob('*'):
        if p.is_file(): assert p.read_bytes() == (src/p.relative_to(old)).read_bytes(), str(p)
formulas = lambda s: re.findall(r'\\begin\{(equation\*?|align\*?)\}([\s\S]*?)\\end\{\1\}',s)
for name in ['sec_5_q1.tex','sec_6_q2.tex','sec_7_q3.tex','sec_8_q4.tex']:
    assert formulas(read(old/'sections'/name)) == formulas(read(src/'sections'/name)), name
pdf = work/'build/main.pdf'
r = PdfReader(pdf)
assert len(r.pages) == 34
text = ''.join(p.extract_text() for p in r.pages)
for number in ['35126.85','13583810.84','13014172.33','14248570.87','13695929.70']:
    assert number in text, number
log = read(work/'build/main.log')
for error in ['Overfull','Missing character','undefined references','Label(s) may have changed']:
    assert error not in log, error
changes = []
diff = []
for p in sorted((src/'sections').glob('*.tex')):
    prior = old/'sections'/p.name
    if prior.exists() and read(prior) != read(p):
        changes.append(p.name)
        diff.extend(difflib.unified_diff(read(prior).splitlines(True),read(p).splitlines(True),fromfile=p.name+' before',tofile=p.name+' after'))
(work/'changes.diff').write_text(''.join(diff),encoding='utf-8')
report = {'pages':34,'abstract_pages':1,'body_pages':30,'appendix_pages':3,'changed_chapters':changes,'title_and_abstract_first_paragraph_unchanged':True,'main_tex_unchanged':True,'all_figure_and_table_files_unchanged':True,'all_model_formula_environments_unchanged':True,'no_overfull_missing_char_or_unresolved_reference':True,'environment_notices':'Existing LaTeX release and CJK font-family redefinition warnings only','visual_check':'All pages rendered; page overviews checked before final local compression, final pages 1,2,8,15,16,17,23,29,31 inspected in detail. Final section 9 fits page 31.'}
(work/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
destination = paper/'main(图像压缩版）.pdf'
shutil.copy2(pdf,destination)
assert pdf.read_bytes() == destination.read_bytes()
with (project/'state/ai_usage_log.md').open('a',encoding='utf-8') as f:
    f.write('''\n\n## 2026-09-13：图像压缩版突出论文主线与关键贡献\n\n- 按用户确认方案修订既有论文；标题不变，摘要首段逐字保留，背景仅轻微压缩，微网立体图及总体框架图保留。保留源文件中最新的约束编号和求解步骤。\n- 摘要与问题分析突出预测服务于实际购电费用的主线；问题二说明近期加权准备的费用机制及同年诊断边界，补清衰减参数下限未经全年实跑；问题三将信息价值对照提前为7.4，明确50.63万元与6.95万元的不同来源；问题四突出费用、预测误差与紧急补购的取舍。减少零散加粗，精简末章重复解释。\n- 未改四问模型公式环境、图资产或外部结果表文件；主要总费用核对一致。更新 main(图像压缩版）.pdf，34页（摘要1页、正文30页、附录3页），字号、行距和页边距不变。交叉引用稳定，无越界、缺字或未定义引用提示。所有页面已渲染并检查总览，重点复核摘要、背景、问题二比较、问题三信息价值、问题四比较及正文末页。\n- 原源文件与旧PDF备份、修改差异、编译日志和检查记录保存在 tmp/focus_revision_20260913_153623。未进行新实验，未改变研究状态。本轮为AI文字与版面核对，不代表人工终审；参考文献补入和完整提交检查仍为此前待办。\n''')
print(json.dumps({'output':str(destination),'source':str(src),'pages':34,'changed_chapters':changes},ensure_ascii=False,indent=2))
