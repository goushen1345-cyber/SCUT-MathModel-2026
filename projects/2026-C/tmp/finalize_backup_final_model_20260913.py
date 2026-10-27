from pathlib import Path
import json,hashlib,shutil,re,difflib
from pypdf import PdfReader
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
src=root/'shumo_1/shumo_backup_20260913_003434'
tmp=root/'tmp/backup-final-model-20260913'
prior=root/'paper/shumo_before_final_model_update_20260913'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((prior/'preservation_manifest.json').read_text('utf-8'))
assert all(sha(prior/name)==value for name,value in manifest.items()),'Preserved originals changed'
compiled=json.loads((tmp/'build/source_hashes.json').read_text('utf-8'))
assert all(sha(src/name)==value for name,value in compiled.items()),'Paper source changed after build'
log=(tmp/'build/main.log').read_text('utf-8',errors='replace')
for problem in ('Overfull','Missing character','There were undefined references','Label(s) may have changed'):
    assert problem not in log,problem
reader=PdfReader(tmp/'build/main.pdf')
texts=[p.extract_text() or '' for p in reader.pages]
flat=re.sub(r'\s+','', ''.join(texts))
for value in ('13014172.33','13695929.70','14248570.87','35126.85','13583810.84','1359.00','1308.37','1301.42'):
    assert value in flat,('Missing result',value)
q3=(src/'sections/sec_7_q3.tex').read_text('utf-8')
for old in ('1314.65','13146535.49','21.78','175.51','197.28','1614.80','1439.29','返工','重跑'):
    assert old not in q3,('Stale Q3 claim',old)
for name in ('sec_0_abstract.tex','sec_2_problem_analysis.tex','sec_9_create.tex'):
    text=(src/'sections'/name).read_text('utf-8')
    for old in ('1314.65','21.78','175.51','197.28','1382.29'):
        assert old not in text,(name,old)
diff=[]
changed=[]
for rel in compiled:
    old=prior/rel
    now=src/rel
    if not old.exists() or sha(old)!=sha(now):
        changed.append(rel)
        diff.extend(difflib.unified_diff(old.read_text('utf-8-sig').splitlines(keepends=True) if old.exists() else [],now.read_text('utf-8-sig').splitlines(keepends=True),fromfile='preserved/'+rel,tofile='revised/'+rel))
(tmp/'content.diff').write_text(''.join(diff),'utf-8')
for suffix in ('pdf','aux','out','log'):
    p=tmp/f'build/main.{suffix}'
    if p.exists():shutil.copy2(p,src/p.name)
assert sha(src/'main.pdf')==sha(tmp/'build/main.pdf')
review=dict(
    status='AI_checked_for_this_revision_not_human_approval',
    target=str(src),pdf=str(src/'main.pdf'),pages=len(reader.pages),
    preserved_originals=str(prior),preserved_files_verified=len(manifest),
    changed_compiled_sources=changed,source_hashes=compiled,pdf_sha256=sha(src/'main.pdf'),
    checks={'latest_q3_q43_results':True,'global_claims_same_version':True,'q2_emergency_table_restored':True,'no_overfull_or_missing_glyph_or_undefined_reference':True,'all_page_overviews_read':True,'q3_detail_pages_read':[30,31,36,37,38,39],'q4_detail_pages_read':[40,41,42,43,44],'state_json_unmodified_by_task':True},
    research_changes={'new_forecast_training':0,'new_dispatch_solves':0,'raw_data_edits':0,'result_workbook_edits':0},
    state_sha256=sha(root/'state/state.json'),
    boundary='Local authorized paper revision; no freeze, submission, or human review asserted. Earlier standalone source copies and historical research outputs retained.'
)
(tmp/'verification.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),'utf-8')
tag='2026-09-13：指定备份论文按最终问题三与问题4-3修订'
def append(path,body):
    current=path.read_text('utf-8-sig')
    if tag not in current:path.write_text(current.rstrip()+'\n\n## '+tag+'\n\n'+body.strip()+'\n','utf-8')
append(root/'state/decisions.md',f'''
- 用户授权：严读 shumo_backup_20260913_003434 后直接修改，沿用原文语言与排版；问题三直接呈现最终方案，问题四直接承接，不写返工时间线。本轮属于局部论文修订及关联文字同步，不扩大研究许可。
- 原目录已逐文件保留至 paper/shumo_before_final_model_update_20260913，{len(manifest)}项原文件哈希复核一致。采用当前宋体/黑体、Times与1.38行距，未覆盖为其他稿件样式。
- 实际修改 main.tex 引用的 sections 正文：Q3完整负载预测、日内校正、光伏融合、匹配准备、LP约束、费用、同条件比较和信息价值；Q4-3承接同版Q3，保持Q4-2。摘要、分析、信息假设、评价同步。旧候选比较保留实际固定条件，不编造模型第一次建立即成功。
- Q3总费13014172.33元，Q4-3总费13695929.70元；Q4-2保持14248570.87元。新预报条件收益69538.10元，与日内反馈/改约收益506305.76元分开解释。
- 从保存轨迹重绘5图，保留PDF/PNG和代码；更新Q3指定日4表。发现原Q2紧急表也误填为普通订单，按既有正式Q2轨迹恢复为3/20 329.52、9/23 6.38 kWh；Q1/Q2仅另修中文单位和越界排版，模型与真实结果不变。
- XeLaTeX稳定编译，{len(reader.pages)}页；全页总览、Q3重点页和Q4第40—44页实际查看，未发现裁切重叠，无缺字、越界或未定义引用警告。差异及取数检查见 tmp/backup-final-model-20260913/verification.json。
- 未新增模型训练、调度求解或正式结果工作簿填写；不改state.json的旧游标，不生成冻结或人工通过。成果 main.pdf 已更新，仍由团队人工审稿。
''')
append(root/'state/ai_usage_log.md',f'''
- 用户要求在指定备份中修订最终Q3/Q4并保持论文语言，使用cumcm-paper-builder、figure-support与PDF工具；工具用于读取源稿、核对既有代码和结果、修订LaTeX、复现图表与页面检查。
- AI主执行修订问题三和关联章节；只读代理核对最终Q3数学口径；并行代理修订Q4、生成图表并恢复错置的Q2紧急表。代理同意不替代人工核验。
- 本轮没有运行新的预测训练、优化求解或候选实验；五图和表均从已存在数据派生。保存可复现脚本、来源指纹、独立重建一致性与修改前全目录。
- 最终PDF {len(reader.pages)}页，编译无缺字/越界/未定义引用警告。全页总览与重点页实际查看，读图和内容核对均为AI完成；用户人工采用及最终审阅未代填。
- 输出：shumo_1/shumo_backup_20260913_003434/main.pdf；真正参与编译的正文在sections/，表在tables/。内部变更和检查记录位于tmp/backup-final-model-20260913。
''')
append(root/'paper_evidence/Q3.md','''
- 本次正文采用 Q3 runs/20260912-forecast-risk-v1 的 EW4_Q60_full 及 verification.json，覆盖旧C22/C23作为“最终结果”的用途，历史证据仍保留。
- 零点四周同星期权重8/15、4/15、2/15、1/15；日内累计已结束负载偏差，过去28完整日无截距斜率限定[0,1]；只修正当天未来。光伏先整点融合再插值，合法观测锚点，超24h历史辅助。误差准备按相同发布钟点、目标3h组、预报距发布24h内外分池，0.7日衰减与0.60分位作用分别说明。
- 普通订单12572280.982668025、调整280616.15556198894、紧急161275.18678334932，总13014172.325013366元；紧急28627.317075652918 kWh、185天。LP明确放电与充电上限、富余约束、变量非负；零点及次日辅助无调整罚款。
- 三组信息同版13590016.178693619/13083710.421174563/13014172.325013366元；反馈与改约506305.757519055、新预报69538.09616119787元；后两组期末库存相同，209天省125天增。
- 保留三种光伏方法在固定等权负载/无日内校正/无准备下的真实比较；负载参照与准备分位另用最终配套误差的比较。不将旧参数消融冒称新供需结构验证，不写返工史。
- Q3指定日期表和5图中的4幅Q3图由目标论文 scripts/update_result_figures.py 生成，数值与来源在derived_values.json及result_figures_manifest.json。正文澄清9/23 20:30功率不足，3/20两次补购为库存下限；不把时初尚有余电误判为必然功率瓶颈。
- 字体、公式、表图和篇章实际检查见tmp/backup-final-model-20260913/verification.json；保持同年度比较边界，不宣称全局最优或人工冻结。
''')
append(root/'paper_evidence/Q4.md','''
- 本次问题4-3正文采用 runs/20260913-q3-transfer-v1 的 EW4_P2_Q60及核验结果，直接承接最终Q3结构。没有叙述返工、重跑或版本迁移；历史研究记录保留。
- 价格采用完整岭回归，lambda_p=10，56日训练窗、每7日重训、当前窗标准化、0/6/12/18更新可知特征；不写成失败的残差式岭回归。零点分支仍为31叶提升树，保留原Q2供需与权限。
- Q4-3普通13212221.004366718、调整299775.47455566755、紧急183933.22141504733，总13695929.700337432元，紧急32162.75537837529 kWh、188天。Q4-2总14248570.873613387元，两完整策略差552641.173275955元约3.88%，不能归因单一预报或改单权限。
- 旧价格候选表注明四周同星期等权、无日内负载校正与15叶树的固定条件；没有把最新岭回归费用与旧树直接当同条件比较。旧价格更新时间消融移出正文，改用本结构已执行五分位验证；0.70虽补购更少但总费多约4.41万元。
- fig/q4_final_validation.pdf/png左为Q4-2既有复杂度验证，右为最终Q4-3五分位；代码与来源指纹见目标论文scripts/。实际第40—44页由AI查看无裁切重叠，非人工批准。
''')
registry=root/'paper_evidence/figure_registry.md'
entries=(src/'scripts/figure_registry_entries.md').read_text('utf-8-sig')
append(registry,entries.replace('# 待主执行者合并的图登记条目','### 最终Q3/Q4论文图登记').replace('论文嵌入页由主执行者检查。','论文嵌入页已由主执行者实际查看；Q4页另由只读代理查看。'))
print(json.dumps({'pdf':str(src/'main.pdf'),'pages':len(reader.pages),'changed_sources':changed,'verification':str(tmp/'verification.json')},ensure_ascii=False))
