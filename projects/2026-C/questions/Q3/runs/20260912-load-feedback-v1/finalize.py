"""Attach verified findings to existing project research/evidence logs."""
from pathlib import Path
import json
R=Path(__file__).resolve().parent;P=R.parents[3];O=R/'outputs'
read=lambda p:json.loads(Path(p).read_text('utf-8'))
s=read(O/'summary.json');v=read(O/'verification.json')
assert v['status']=='verified_by_AI_not_human_approval'
a=s['baseline'];b=s['winner'];label=b['label'];analysis=v['candidate_analysis'][label]
names={'PERSIST_PREFIX':'直接延续当天累计偏差','LEARN_PREFIX':'历史学习当天累计偏差的延续程度','LEARN_RECENT':'历史学习最近3小时偏差的延续程度','LEARN_PREFIX_HALF':'累计偏差学习方案，修正幅度减半'}
table='|方案|334天总费用/元|较原方案节省/元|紧急购电量/kWh|紧急天数|\n|---|---:|---:|---:|---:|\n'
table+=f"|原最终模型|{a['total_cost']:.2f}|0.00|{a['emergency_kwh']:.2f}|{a['emergency_days']}|\n"
for r in s['candidates']:
    table+=f"|{names.get(r['label'],r['label'])}|{r['total_cost']:.2f}|{a['total_cost']-r['total_cost']:.2f}|{r['emergency_kwh']:.2f}|{r['emergency_days']}|\n"
info=v['updated_information_comparison']
text=f'''## 2026-09-12 最新：日内负载修正深化结果（AI推荐，未替换旧成果）

用户明确授权继续深化问题三。本轮固定现有光伏融合、设备、结算、准备量构造规则和共同2月1日库存，以日内负载修正为唯一新增预测模块。完整334天比较后，推荐“日内偏差校正滚动调度”：{names.get(label,label)}。现有模型与论文、问题四均保留，本节不是自动冻结或采用确认。

### 本轮具体改了什么，为什么有用

旧模型当天负载判断主要来自零点的同星期历史曲线，即使上午实际用电持续偏高或偏低，之后的负载基础预测仍不修正。新方案在6/12/18点计算当天零点至当前已结束时段的平均负载误差，再根据过去28个完整日的类似误差，判断这种偏差能延续到当天各个未来3小时组多少。比如上午平均比预计多100 kW，而历史拟合的延续系数为0.6，就将相应未来组上调60 kW；这里的0.6只是解释例子，不是实际固定系数。

定义b为当天已发生的平均负载误差，theta为对应发布时间与未来3小时组的延续系数。theta=clip(sum(x_i*y_i)/sum(x_i^2),0,1)，其中x_i是历史日同一已观察区间的平均误差，y_i是该历史日目标3小时组的平均误差。预测更新为Lnew=max(0,Lmidnight+theta*b)。只利用此前28个完整日，至少7日有效样本才拟合；零点不修正，次日辅助预测也不直接沿用当天偏差。theta可以随日期、决策时刻和目标组变化，不是每天指定一个常数。

不设截距使“当前没有观察到偏差”对应不主动改动；系数限制0—1，意味着按原方向传递历史显示会延续的偏差，既可上调也可下调，不额外放大或反向传播。它是保守结构假设，不是题面规定。所有候选都从自身新预测重新形成历史净需求误差，再使用原28天、3小时、0.60分位、0.7衰减构造准备，防止改善预测后继续使用旧误差多加一遍准备。没有偷偷去掉准备量或降低物理约束。

### 同条件费用比较

{table}

本批最佳总费用{b['total_cost']:.2f}元，比原{a['total_cost']:.2f}元减少{s['saving']:.2f}元，降幅{analysis['percent']:.4f}%。把同一学习方案的修正幅度减半后，费用回升，故在已比较的两个幅度中保留完整修正。未搜索其他任意放大倍数或联合重调准备参数，不能称为全部模型空间最优。

费用分解：普通订单费减少{a['normal_cost']-b['normal_cost']:.2f}元，调整费增加{b['adjustment_cost']-a['adjustment_cost']:.2f}元，合计普通结算仍减少{a['ordinary_cost']-b['ordinary_cost']:.2f}元；紧急费再减少{a['emergency_cost']-b['emergency_cost']:.2f}元。未接收订单从{a['unused_order_kwh']:.2f}降至{b['unused_order_kwh']:.2f} kWh。预测修正让少买和多买同时有所减少，节费不是单靠更频繁改约。

### 预测改善与风险代价

在6点、12点、18点各次决策后的下一个6小时内，负载MAE分别由163.47、195.04、216.41 kW降至120.27、140.30、155.65 kW。最近3小时学习方案在部分时段的预测误差更低，但实际费用高于累计偏差学习方案，说明仍须看费用而非只看拟合误差。

紧急购电总量从{a['emergency_kwh']:.2f}降至{b['emergency_kwh']:.2f} kWh，减少{100*(a['emergency_kwh']-b['emergency_kwh'])/a['emergency_kwh']:.2f}%；但发生紧急购电的日期从{a['emergency_days']}增至{b['emergency_days']}天。这是量减少、发生天数增加的取舍，不能写成所有可靠性指标都改善。所选方案最大小区间紧急量{analysis['max_emergency_interval_kwh']:.2f} kWh，最长连续紧急补购{analysis['longest_emergency_minutes']}分钟。

逐日{analysis['cheaper_days']}天节费、{analysis['costlier_days']}天增费；2、3、4月分别增费1450.42、222.52、1016.88元，其余8个月节费。最大单日节费{analysis['max_saving']:.2f}元（{analysis['max_saving_date']}），最大单日增费{analysis['max_increase']:.2f}元（{analysis['max_increase_date']}）。期末库存差仅{analysis['terminal_stock_difference']:.6f} kWh，按既有参考价值调整后仍节省{analysis['saving_with_terminal_reference']:.2f}元，不是靠最后少留电量实现改善。

原模型最大小区间紧急购电为910.17 kWh，最长连续紧急补购同为100分钟；新方案减少了最大小区间补购，但最长持续时间未改善。紧急购电日数增加不是发生停电的天数增加，模型仍逐段由紧急购电补足供需；但这表示临时补购发生得更频繁，不能忽略其运行代价。

本轮是在已看过的2025年数据内进行有界深化，并由334天费用选择方案；历史学习过程逐时遵守信息可用性，但全年评价不构成未见年份独立测试。不能宣称跨年泛化或每日稳定节费。

### 同步更新新版模型的信息价值，避免沿用旧表

若团队采用这一新版，信息对照须使用：零点锁单{info['zero_only_cost']/10000:.2f}万元→反馈改约但无后发官方预报{info['no_new_cost']/10000:.2f}万元→完整后发预报{info['full_cost']/10000:.2f}万元。零点锁单轨迹可以复用，因为本轮零点负载与误差准备均不变；中间组则已用新负载和自身受限预报误差完整重跑。

新版下新增光伏预报额外节省{info['new_PV_saving']:.2f}元，约{info['new_PV_saving_percent']:.4f}%。这与前版2.55万元、初始直接预报版21.78万元分别属于不同模型，不能相互拼接；本轮日内负载修正带来的{s['saving']:.2f}元也不能全部归于光伏新预报。主模型演化可以表述为“原融合准备模型1314.65万元→加入历史学习的日内负载修正1304.61万元”，对应一处新增结构。

### 核验和交接

本批{s['lp_calls']}次LP、0树拟合，研究执行{s['elapsed_seconds']:.2f}秒。独立程序不调用求解器，核对{v['counts']['strategies']}套策略、{v['counts']['actual_intervals']}个实际区间、{v['counts']['regression_groups']}组负载修正系数和{v['counts']['margin_groups']}组准备量。全年账单最大复算差{v['max_errors']['total_bill']:.3g}元，物理、信息时点、已执行订单锁定、跨日库存均符合记录；这是AI独立程序核验，不是人工审查。

本轮推荐采用上述累计偏差学习方案作为新候选主版本，等待用户决定是否用于论文及提交结果。若采用，问题三模型说明、结果与信息价值表需要更新；问题四若要继承新负载模块，须单独评估和重算，不能把旧问题四结果说成已经使用了新模块。旧论文、正式结果、问题四与state.json未修改。

复现与证据：`runs/20260912-load-feedback-v1/protocol.json`、`run.py`、`verify.py`；`outputs/summary.json`、`comparison.csv`、`verification.json`以及各策略预测/系数/误差/准备缓存、逐日账单和10分钟轨迹。

'''
def prepend(path,heading,body):
    p=P/path;old=p.read_text('utf-8')
    if heading not in old:p.write_text(body+old,encoding='utf-8')
prepend(Path('questions/Q3/report.md'),'## 2026-09-12 最新：日内负载修正深化结果',text)
evidence=f'''## 2026-09-12 最新增量：日内负载偏差校正（推荐未自动采用）

- **Q3-C27：结构增量与费用。** 在原最终模型上只新增因果日内负载修正，重新计算各方案自身误差准备。累计偏差历史学习方案总费{b['total_cost']:.2f}元，减少{s['saving']:.2f}元（{analysis['percent']:.4f}%）；不是重新定义中间数值。
- **Q3-C28：解释与反例。** 历史28个完整日估计有界无截距斜率，0/6/12/18信息边界不变。半幅修正费用更高；最近3小时方案部分预测误差更小却费用更高。紧急电量降低、紧急日期164→189，211天省、123天增，2/3/4月总体增费。禁止写为全方面风险下降或跨年最优。
- **Q3-C29：新版信息价值。** 若采用新负载模型，三组费用应为{info['zero_only_cost']/10000:.2f}/{info['no_new_cost']/10000:.2f}/{info['full_cost']/10000:.2f}万元；新光伏预报条件增量为{info['new_PV_saving']:.2f}元。旧三组仍作为各自版本证据保留，不跨版本拼接。
- **Q3-C30：正确性。** {s['lp_calls']}次LP后独立回读{v['counts']['actual_intervals']}实际区间、{v['counts']['regression_groups']}组系数、{v['counts']['margin_groups']}组准备量；信息、物理、锁单与实际账单一致。AI复核不等于人工批准。
- 来源`questions/Q3/runs/20260912-load-feedback-v1/outputs/summary.json`、`verification.json`。详细模型、费用分解和风险解释已并入Q3/report.md。未改论文、result3、Q4和正式状态；采用决定属于用户。

'''
prepend(Path('paper_evidence/Q3.md'),'## 2026-09-12 最新增量：日内负载偏差校正',evidence)
log=f'''## 2026-09-12：问题三日内负载修正深化完成

- 用户明确继续深化；三候选+最佳方案半幅敏感性+新主方案无后发光伏预报对照，共{s['lp_calls']}次LP、0树拟合、{s['elapsed_seconds']:.2f}秒。全部334天、同起点同设备同计费。
- 推荐累计偏差历史学习，总费{b['total_cost']:.2f}元，节省{s['saving']:.2f}元；紧急总量下降但天数增加，反例完整保留。新预报增量{info['new_PV_saving']:.2f}元，仅限新版模型条件。
- 独立核验{v['counts']['actual_intervals']}实际区间、{v['counts']['regression_groups']}系数组和{v['counts']['margin_groups']}准备组，未导入求解器重跑；核验者为AI，不记人工批准。来源questions/Q3/runs/20260912-load-feedback-v1/。
- 在已有报告、实验索引及论文证据沉淀，不覆盖原模型、论文或正式结果，不自动把Q4改用新负载模块，不冻结或修改正式状态游标。

'''
for path in ('questions/Q3/experiments.md','state/decisions.md','state/ai_usage_log.md'):
    prepend(Path(path),'## 2026-09-12：问题三日内负载修正深化完成',log)
print(json.dumps(dict(recorded=True,winner=label,cost=b['total_cost'],saving=s['saving']),ensure_ascii=False))
