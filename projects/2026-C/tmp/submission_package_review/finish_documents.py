from pathlib import Path
import json,shutil,re,hashlib
P=Path(__file__).resolve().parents[2];D=P/'支撑材料';C=P/'paper/提交配套';C.mkdir(exist_ok=True)
original=P/'paper/submission_support_v1/AI工具使用详情.tex'
s=original.read_text('utf-8').replace('2026年9月10日至12日','2026年9月10日至13日')
s=s.replace('参考文献核查。\\\\','参考文献核查、提交材料整理。\\\\')
s=s.replace('区分日内反馈和后发预报带来的费用变化。','区分日内反馈和后发预报带来的费用变化；按后续要求加入近期同星期负载加权和日内偏差校正，再完成三组信息条件的同口径比较。')
s=s.replace('并补充特征、参数及风险分析。','并补充特征、参数及风险分析；问题三更新后，重新运行问题4-3并核对全年结果。')
s=s.replace('当前版本的最终采用以队伍提交文件为准。','队员还要求保留必要解释，压缩重复文字与图表、统一求解步骤及约束标题。当前版本的最终采用以队伍提交文件为准。')
s=s.replace('结果表回读、参数对照及PDF页面检查。','结果表回读、参数对照及PDF页面检查。9月13日按队员要求整理支撑材料，导出五个完整结果工作簿，并独立复算整理后的最终程序。')
(C/'AI工具使用详情.tex').write_text(s,encoding='utf-8')
# Portable original preprocessing source, retaining original XLSX numeric strings.
s=(P/'scripts/prepare_source_tables.py').read_text('utf-8-sig')
s=s.replace('python -X utf8 projects/2026-C/scripts/prepare_source_tables.py','python code/prepare_source_tables.py')
s=s.replace("audit=json.loads((ROOT/'audit/data_audit_v1.json').read_text(encoding='utf-8'))\n    expected=audit['source_sha256']", "expected=json.loads((ROOT/'data/raw_hashes.json').read_text(encoding='utf-8'))")
s=s.replace("default='data/prepared-v1'","default='reproduced/source_tables'")
(D/'code/prepare_source_tables.py').write_text(s,encoding='utf-8')
hashes=json.loads((P/'audit/data_audit_v1.json').read_text('utf-8'))['source_sha256']
# Only the raw source hashes used by this program need to travel with it.
(D/'data/raw_hashes.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
readme=(D/'使用说明.md').read_text('utf-8')
readme=readme.replace('第一条数据命令重建', '若需从原始Excel重新核对整理过程，将题目附件1—4及附件5按原目录结构放在`data/raw/C题/附件/`，并将题面放在`data/raw/C题/C题.pdf`，运行`python code/prepare_source_tables.py`。原始附件不重复放入支撑包；原数值和来源单元格已保留在随包CSV中。\n\n第一条数据命令重建')
(D/'使用说明.md').write_text(readme,encoding='utf-8')
shutil.copy2(P/'tmp/submission_package_review/full_reproduction/reproduction_check.json',D/'evidence/reproduction_check.json')
# External AI usage cannot be inferred from a sample report or a currently marketed version.
(C/'提交前待补事项.md').write_text('''# 提交前待补事项

1. AI使用详情已按本项目真实聊天更新至9月13日，保留OpenAI Codex（GPT-6）记录。团队提出使用DeepSeek，但尚未提供实际版本、使用日期、用途及交互记录。需按真实使用补充后，才能作为全队完整AI使用报告；不能把本聊天的Codex工作改署为DeepSeek。
2. 本次查阅DeepSeek官方API文档，Flash入口对应DeepSeek-V4.1-Flash，并列有DeepSeek-V4-Pro。网址：https://api-docs.deepseek.com/ 。这只是查阅时官网说明，不是团队实际使用版本的证明。
3. 当前图像压缩版论文已有的附录是结果表，还须加入本次生成的支撑材料文件列表和完整程序。可将“支撑材料附录.tex”中的内容合入现有附录；正文30页不因此增加。
4. 第一次通知引用了另行发布的AI工具使用规定，但本次提供的两个规范PDF不包含该规定全文。提交前需再核对赛区通知和AI专项要求，尤其是团队完整使用信息。
5. 按用户要求本次先整理文件夹，未替队伍上传或提交。压缩时使用WinRAR，压成一个不超过20MB的ZIP或RAR。电子论文另交，不放进支撑材料。
''',encoding='utf-8')
print(C)
