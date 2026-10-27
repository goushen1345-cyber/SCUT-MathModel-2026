"""Record validated transfer results in the existing Q4 research/evidence entries."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parent;P=R.parents[3];O=R/'outputs'
read=lambda p:json.loads(Path(p).read_text('utf-8'))
s=read(O/'summary.json');v=read(O/'verification.json')
assert v['status']=='verified_by_independent_AI_program_not_human_approval'
a,b=s['baseline'],s['winner'];t=v['analyses'][b['label']];oldrisk=v['analyses'][a['label']]
tab='|方案|334天总费用/元|紧急购电费/元|紧急购电日数|\n|---|---:|---:|---:|\n'
for x in [a,*sorted(s['candidates'],key=lambda c:c['quantile'])]:
 name='旧问题4-3完整复现' if x is a else f"新供需结构，准备分位{x['quantile']:.2f}"
 tab+=f"|{name}|{x['total_cost']:.2f}|{x['emergency_cost']:.2f}|{x['emergency_days']}|\n"
body=f'''## 2026-09-13 最新：接入问题三深化结构后，问题4-3重跑完成

按用户“先记录问题三，再跑问题四”的明确要求，已先将问题三新增结构、符号公式、参数解释、演化与信息价值两条证据链及风险写作要点汇总至Q3/report.md和paper_evidence/Q3.md，再对问题4-3执行本次比较。当前推荐“近期负载校正与岭回归电价预测的滚动调度”，334天总费{b['total_cost']:.2f}元，比旧{a['total_cost']:.2f}元减少{t['saving']:.2f}元（{t['saving_percent']:.4f}%）。这是本轮同条件比较推荐，不是全部可能模型中的全局最优，也不代表已经冻结或替换论文。

### 从问题三继承什么，问题四再增加什么

供需预测继承问题三20260912-forecast-risk-v1的EW4_Q60_full：零点使用四个同星期历史负载，权重依次8/15、4/15、2/15、1/15；6/12/18点用当天已发生的累计负载偏差，并用过去28个完整日学习其在未来3小时组中的延续程度。光伏采用原历史误差融合；新的负载预测对应新的净需求历史误差准备。具体公式与参数解释引用Q3/report.md的2026-09-13交接，不复制一套不一致的定义。

问题四增加价格预测。保留团队原选完整岭回归，而不是旧深化中未胜出的残差式岭回归：以过去56天的合法特征样本，每7天更新一次拟合；仅在当前训练窗标准化，正则系数10。对历史价格曲线、星期/季节、当时预测净负载及当天已经发生的价格偏差进行线性组合，预测未来价格。模型为p_hat=max(0.001,b0+x_std^T b)，系数求解min Σ(p_j-b0-z_j^T b)^2+10||b||²。正则项限制高度相关特征的系数过度放大；系数是预测关联，不是价格形成的因果系数。

由于预测净负载是价格模型的一项输入，不能只改调度侧负载而继续使用旧价格曲线。本轮按新供需预测重建各历史决策时的训练特征，重新拟合49个每周价格模型，并生成1336次价格预报。训练目标只保留在该次训练截止之前已经实际发生的价格；6/12/18点的价格反馈只包含当前时刻之前的真实价格。附件4未来电价从未用于可执行计划。

新的供需预测及误差准备进入原滚动线性规划；新预测价格进入规划目标，执行后的账单用附件4真实价格复算。价格和供需仍分开建模。实际区间费用为p*q_final+0.5*p*abs(q_final-q_zero)+5*p*e，其中p为执行区间真实电价；多次改约相对零点净变化只结算一次。当前日及次日辅助规划、已执行订单锁定、共同2月1日起点8592.69356093kWh、效率各90%、储能/功率约束、实际库存跨日继承、无售电收益及既有末库存参考价值全部不变。

### 公平比较和准备量检查

先完整重跑旧完整岭回归版本，旧订单、四次版本和实际电池轨迹逐值复现，旧总费{a['total_cost']:.2f}元也一致。再在同一新供需与价格结构下比较五档准备量。准备来自问题三已独立核验的自身误差缓存；分位改变不改变价格预测，因此49个价格拟合复用到五档策略，不做无意义的重复训练。

{tab}

0.60分位在本批波动电价下仍最低，不能因为问题三选择了0.60就跳过这次核对。0.40/0.50准备不足引起更多五倍电价补购，0.70/0.80虽然降低紧急量，却需要较多普通购电。以上说明成本折中，不证明0.60是连续范围或其他年份的唯一最优点。

### 为什么费用下降，以及风险是否一起改善

普通订单费减少{a['ordinary_cost']-b['ordinary_cost']:.2f}元，调整费增加{b['adjustment_cost']-a['adjustment_cost']:.2f}元，紧急费减少{a['emergency_cost']-b['emergency_cost']:.2f}元，合计省{t['saving']:.2f}元。未接收订单由{a['unused_order_kwh']:.2f}降至{b['unused_order_kwh']:.2f}kWh，说明少买到用不上的合同电量是本轮观察到的重要改善。价格MAE仅从{a['price_mae']:.8f}变为{b['price_mae']:.8f}元/kWh，不宜把约12.70万元全部归为价格预测更准确。本轮比较的是供需校正及其价格特征重建的组合增量，没有另做单独固定价格特征的消融，因此不将二者贡献强行拆成百分比。

紧急购电量从{a['emergency_kwh']:.2f}降至{b['emergency_kwh']:.2f}kWh，减少{100*(a['emergency_kwh']-b['emergency_kwh'])/a['emergency_kwh']:.2f}%；紧急购电日期却从{a['emergency_days']}增至{b['emergency_days']}天，表示总量更少但临时补购更频繁，不能写成风险全部下降。真实价格最高5%区间的紧急量从{oldrisk['high_price_emergency_kwh']:.2f}降至{t['high_price_emergency_kwh']:.2f}kWh；最大小区间紧急量从{oldrisk['max_interval_emergency_kwh']:.2f}降至{t['max_interval_emergency_kwh']:.2f}kWh。最长连续紧急补购从{oldrisk['longest_emergency_minutes']}降至{t['longest_emergency_minutes']}分钟；补购不是停电。

逐日{t['cheaper_days']}天更便宜、{t['costlier_days']}天更贵；8个月总费下降，4/8/11月分别增加1283.36/3014.88/1989.40元。最大单日增费{t['max_cost_increase']:.2f}元（{t['max_cost_increase_date']}），最大单日节费{t['max_saving']:.2f}元（{t['max_saving_date']}）。9月贡献55372.85元、7月贡献35881.14元，收益并非各月均匀。期末电量只比旧版少{-t['final_inventory_difference']:.6f}kWh，按既有参考价值调整仍省{t['terminal_reference_saving']:.2f}元；按本年度价格5%/50%/95%分位估值，节省仍在{min(t['terminal_savings_range']):.2f}—{max(t['terminal_savings_range']):.2f}元之间，未靠最后透支电池制造节费。

### 核验结论、可写范围与后续影响

本轮运行{s['lp_calls']}次线性规划、{s['price_fits']}次价格拟合，计算{s['elapsed_seconds']:.2f}秒，未超过预设9000/60/1800预算。独立程序不重新求解或拟合，重构全部价格特征、检查49个已保存岭回归的训练标准化与正规方程、1336次预测、6套完整策略的288576个10分钟实际区间，以及8016条求解状态。实际账单Decimal复算最大差{v['max_errors']['total_bill']:.3g}元；供需、锁单、电池状态和计费与保存结果一致，旧基线轨迹精确复现。原始输入和上游指纹保持一致。AI程序复核不等于人工审阅。

所有参数仍在已看过的2025年数据内比较，只能支持当前年度结果，不能宣称跨年泛化、每天必省或全局最优。原论文中完整岭回归与提升树的2273.23元差距只属于旧供需输入；本轮没有用新供需重跑提升树，不可拿新岭回归费用与旧提升树费用来证明价格模型家族优劣。若需要更新模型对比表，应保留它作为历史选型证据，并单列当前深化对照。

问题4-2原推荐56天、31叶提升树的14248570.87元结果保留，本轮没有改变它的供需预测、日内权限或重新运行。问题4-3已验证能接入问题三深化结构；若后续更新论文，应将Q3和Q4-3相关公式、费用、费用分解、风险段、摘要/结论、总体框架图与相关图表同步更新。旧问题四价格更新消融与理想价格参照仍属于旧供需版本，不能自动套给本轮；本轮未新增这些对照。

推荐以新0.60分位版本作为问题4-3的费用优先候选成果，保留紧急补购日增加的取舍。未自动改论文、正式result4-3或冻结；未运行问题四情景方案。研究及可写证据位于`runs/20260913-q3-transfer-v1/`的protocol、run、verify和outputs；计算摘要保留计算结束时pending快照，独立核验及本交接以verification.json和delivery.json为准。

'''
def prepend(rel,heading,text):
 p=P/rel;old=p.read_text('utf-8')
 if heading not in old:p.write_text(text+old,encoding='utf-8')
prepend('questions/Q4/report.md','## 2026-09-13 最新：接入问题三深化结构后',body)
evidence=f'''## 2026-09-13：问题4-3继承问题三深化的新增证据

- **Q4-T01（结构与输入，已计算核验）**：上游Q3 EW4_Q60_full近期加权同星期负载与日内累计偏差学习，配套自身历史准备。保留旧完整岭回归56天/每周更新/正则10，重建供需价格特征并拟合49个价格模型；未来真实价格不进入计划。原优化/物理/净调整结算不变，旧基线轨迹逐值复现。
- **Q4-T02（费用和准备比较，支持）**：新0.60分位总费{b['total_cost']:.2f}元，比旧{a['total_cost']:.2f}元减少{t['saving']:.2f}元（{t['saving_percent']:.4f}%）。0.40/0.50/0.70/0.80均更贵。是当前年度有限比较，不是全球或跨年最优。
- **Q4-T03（风险和反例）**：普通费少{a['ordinary_cost']-b['ordinary_cost']:.2f}元，调整费多{b['adjustment_cost']-a['adjustment_cost']:.2f}元，紧急费少{a['emergency_cost']-b['emergency_cost']:.2f}元；紧急量下降约16.96%，紧急日期167→188，212天省/122天增，4/8/11月增费。最高价5%区间紧急量14665.07→10743.34kWh。期末估值后仍省约12.70万元。必须保留取舍。
- **Q4-T04（可信度与论文边界）**：8016次LP、49次拟合；独立重构价格特征、检验保存岭回归正规方程/1336次预报/288576实际区间/账单，最大总账差{v['max_errors']['total_bill']:.3g}元。AI复核不代表人工批准。旧提升树对比、各次价格更新消融和理想价格参照仍只对应旧供需；不得与新费混用。
- **写作交接**：问题四章节应先引用新版问题三供需结构，再说明岭回归电价预测和滚动安排；费用/风险/摘要与图表须同步更新。问题4-2保留14248570.87元。本轮只沉淀证据，未改论文、图表或正式result4；未冻结。
- 来源：`questions/Q4/runs/20260913-q3-transfer-v1/outputs/summary.json`、`verification.json`及各策略轨迹与每日账单，完整解释已并入Q4/report.md最新段。

'''
prepend('paper_evidence/Q4.md','## 2026-09-13：问题4-3继承问题三深化的新增证据',evidence)
log=f'''## Q4-Q3-TRANSFER-20260913-RESULT：问题三记录与问题4-3重跑完成

- 已先完成Q3新增模型、公式、参数与论文证据交接，再按当前明确授权重跑Q4-3；Q4-2保留，原state.json revision49未改。
- Q4-3推荐EW4_P2_Q60，总费{b['total_cost']:.2f}元，比完整复现旧基线省{t['saving']:.2f}元（{t['saving_percent']:.4f}%）；五档准备比较0.60最低。紧急总量下降但发生日期167→188；各月反例和库存估值已记录。
- 8016次LP、49次拟合、{s['elapsed_seconds']:.2f}研究秒；独立核验49个价格模型正规方程、1336次预测和288576实际区间/账单。AI核验不记人工核验或冻结。
- 来源questions/Q4/runs/20260913-q3-transfer-v1/；已并入Q4/report、experiments和paper_evidence/Q4。旧论文、正式结果表、问题4-2和原始附件保持，后续写作需同步更新两问而不能只改数字。

'''
for rel in ['questions/Q4/experiments.md','state/decisions.md','state/ai_usage_log.md']:prepend(rel,'## Q4-Q3-TRANSFER-20260913-RESULT',log)
files=[R/'protocol.json',R/'run.py',R/'verify.py',O/'summary.json',O/'verification.json',O/'comparison.csv',O/'supply.npz',O/'prices.npz',O/f"strategies/{b['label']}.npz",O/f"strategies/{b['label']}.daily.csv"]
delivery=dict(status='verified_recommendation_not_frozen',upstream='Q3 EW4_Q60_full',q43_recommended=b['label'],cost=b['total_cost'],saving=t['saving'],saving_percent=t['saving_percent'],Q42='unchanged',paper='not_modified; Q3 and Q4-3 pending coherent update',formal_state='unchanged historical revision49; explicit scope in decisions log',sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files})
(O/'delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(delivery,ensure_ascii=False))
