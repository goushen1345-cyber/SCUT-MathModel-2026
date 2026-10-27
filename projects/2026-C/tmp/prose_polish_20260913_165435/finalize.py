from pathlib import Path
import json, shutil, hashlib

project = Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
work = project/'tmp/prose_polish_20260913_165435'
paper = project/'shumo_1/shumo_backup_20260913_003434'
pdf = work/'build/main.pdf'
destination = paper/'main(图像压缩版）.pdf'
report = json.loads((work/'verification.json').read_text(encoding='utf-8'))
assert hashlib.sha256(pdf.read_bytes()).hexdigest() == report['pdf_sha256']
assert destination.read_bytes() in [(work/'before.pdf').read_bytes(),pdf.read_bytes()], 'Destination changed since backup; inspect before overwrite.'
shutil.copy2(pdf,destination)
assert pdf.read_bytes() == destination.read_bytes()
report['visual_check'] += ' Primary agent additionally inspected final contact sheets covering all 34 pages; protected background and framework figures and appendix boundary intact.'
report['delivered_pdf'] = str(destination)
report['copied_pdf_hash_verified'] = True
(work/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
entry = '''

## 2026-09-13：图像压缩版优化叙述衔接与模型优势并更新题名

- 按用户本轮明确授权，将题名改为“融合多源预测的微网经济调度与线性优化研究”。摘要正文逐字保留，背景、微网立体图及总体框架图保留；不扩展研究授权。
- 修正图表前后段落边界，并对少数跨页段落作局部调整，消除图表插入半句话的问题。问题三7.1开头解释负载校正、光伏融合与插值、误差准备的各自作用；问题一、二、四的选择说明突出已有费用与风险依据。仅在问题二保留48小时规划及问题四选择岭回归两处使用“我们”。
- 模型评价三项优势调整为以实际费用检验预测价值、单独量化新增信息的节费贡献、统一储能约束并支持连续运行核验。保留同年参数比较等证据边界；局限与推广段落原文不变。未新增实验或夸大模型适用范围。
- 源文件位于shumo_1/shumo_backup_20260913_003434/图像压缩版，已更新同级main(图像压缩版）.pdf。最终34页（摘要1页、正文30页、附录3页），字号、行距与页边距不变。与本轮备份逐项比对，39个模型公式环境、全部行内表格主体、38个图表资产文件及五个主要总费用均保持一致。两次稳定编译后无越界、缺字或未定义引用提示。
- 全34页已渲染并检查总览，重点页实际检查；独立只读核对第11、12、23、29、30页未发现图表插断句子、文字重叠或截断。AI检查不代替人工终审。修改前源文件与PDF、差异、编译和检查记录位于tmp/prose_polish_20260913_165435。未改变state.json或研究进度。
'''
log = project/'state/ai_usage_log.md'
if '## 2026-09-13：图像压缩版优化叙述衔接与模型优势并更新题名' not in log.read_text(encoding='utf-8-sig'):
    with log.open('a',encoding='utf-8') as f:
        f.write(entry)
print('Delivered 34-page PDF; content invariants and copied hash verified; usage record appended.')
