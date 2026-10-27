"""Attach this verified, bounded Q3 comparison to existing research records."""
from pathlib import Path
import json

R = Path(__file__).resolve().parent
P = R.parents[3]
O = R / 'outputs'
s = json.loads((O / 'summary.json').read_text('utf-8'))
v = json.loads((O / 'verification.json').read_text('utf-8'))
assert v['status'] == 'verified_by_AI_not_human_approval'
a, b = s['baseline'], s['winner']
t = v['analyses'][b['label']]
i = v['information']
original = 13146535.488467809
names = {'W1': '最近1个同星期日', 'W2': '最近2个同星期日等权', 'EW4': '最近4个同星期日，逐周权重减半'}
table = '|零点负载参考|准备分位|334天总费用/元|\n|---|---:|---:|\n'
table += f"|原4个同星期日等权|0.60|{a['total_cost']:.2f}|\n"
for c in s['candidates']:
    table += f"|{names[c['family']]}|{c['q']:.2f}|{c['total_cost']:.2f}|\n"
body = f'''## 2026-09-12 最新：近期负载加权与准备量再比较（推荐未替换正式成果）

用户明确要求继续降低问题三费用。本轮完成2025年2月1日至12月31日全部334天比较，最低总费为{b['total_cost']:.2f}元，比上一轮{a['total_cost']:.2f}元再省{t['saving']:.2f}元（{t['saving_percent']:.4f}%）。相对原融合准备版本{original:.2f}元，两轮累计省{original-b['total_cost']:.2f}元（{100*(original-b['total_cost'])/original:.4f}%）。本轮增量和累计增量必须分开，不能把累计降幅说成本轮效果。

### 为什么改零点负载参考

原方案把前四个同星期日看得一样重要。如果最近的用电水平已经变化，较早三周会拖慢预测更新；但只参考上一周又容易把某一天的偶然波动带入计划。因此，本轮比较保留1周、2周，以及保留4周但让较近日期占更大权重。

本批最低方案保留4个同星期日，权重依次为8/15、4/15、2/15、1/15，即约53.33%、26.67%、13.33%、6.67%。计算规则为w_j=0.5^(j-1)/sum(0.5^(k-1))，j=1表示最近的同星期日；历史不足时仅对已有同星期日重新归一化，其他初始化沿用记录中的回退口径。这里每远一周乘0.5是预先列入比较的结构设定，不是理论最优常数，也不是误差样本每老一天乘0.7的日期衰减参数。

日内仍使用上一轮的累计负载偏差学习修正。每种零点参考都重建自身历史预测、日内修正系数、净需求误差和准备量，没有换了预测却继续套用旧误差。光伏历史融合、供需和设备约束、充放各90%、结算方式、共同起始电量{b['initial']:.6f} kWh均保持一致。计划只读取当时可用的信息；当日未来实际负载和光伏仅用于事后执行核验。

### 实际比较与解释

{table}

只用上一周反而更贵，两周均值略有改善，近期加权的四周参考本批最低。这支持在跟随近期变化的同时保留多周参照。它是费用层面的比较，不能未经额外指标直接写成每个时刻预测都更准。

进一步把准备分位从0.60降到0.50或0.40，总费用升高：少订的普通电不足以补偿新增紧急购电费用。提高到0.70或0.80虽减少紧急补购，却提高普通购电总支出。因此本批仍保留0.60；这是五个预设分位的实测比较，不是连续参数范围的全局最优证明。

### 节省来自哪里，付出了什么代价

相对上一轮，普通订单费减少{a['normal_cost']-b['normal_cost']:.2f}元，调整费减少{a['adjustment_cost']-b['adjustment_cost']:.2f}元，但紧急费增加{b['emergency_cost']-a['emergency_cost']:.2f}元。三者合计净省{t['saving']:.2f}元。未接收订单电量减少{a['unused_order_kwh']-b['unused_order_kwh']:.2f} kWh。

紧急购电量由{a['emergency_kwh']:.2f}升至{b['emergency_kwh']:.2f} kWh，增加{b['emergency_kwh']-a['emergency_kwh']:.2f} kWh；紧急购电日期从{a['emergency_days']}降至{b['emergency_days']}天。不能写成风险全面改善，也不能把紧急购电日等同于停电日。

逐日{t['cheaper_days']}天更便宜、{t['costlier_days']}天更贵；11个月中5个月省钱、6个月增费，9月贡献{t['monthly_saving']['9']:.2f}元，改善集中在部分月份。最大单日增费{t['max_increase']:.2f}元（{t['max_increase_date']}）；最大单日节费{t['max_saving']:.2f}元（{t['max_saving_date']}）。末库存比上轮少{a['final']-b['final']:.6f} kWh，按既有参考电价折算后净节省仍为{t['terminal_reference_saving']:.2f}元，库存差不足以解释本轮节费。

本轮使用已分析过的同一年数据比较并选择方案。逐时预测没有使用未来值，不等于选型结果已经经过未见年份验证；不能宣称跨年泛化或逐月稳定占优。

### 新版的两条论文逻辑必须区分

模型深化链：原融合准备1314.65万元→加入日内负载修正1304.61万元→改用近期加权同星期参考1301.42万元。它回答为何逐步改进模型，不是官方新预报的单独收益。

同版信息对照链：零点锁单{i['zero_cost']/10000:.2f}万元→可日内反馈调整但不使用零点后发布的官方光伏预报{i['no_new_cost']/10000:.2f}万元→加入后发官方预报{i['full_cost']/10000:.2f}万元。零点组也已重新计算，因为本轮改变零点预测。最后两组期末库存相同，新预报额外省{i['new_PV_saving']:.2f}元（{i['new_PV_saving_percent']:.4f}%）；前两组的差异含反馈、负载校正和改约等共同作用。新预报收益仍约0.53%，本轮没有把它人为变大。不得将任何旧版本的中间值与本轮最终值拼接。

### 还有多少可能空间

为诊断而单独求解的乐观费用下界为{v['hindsight']['cost']:.2f}元，约1222.68万元，比当前方案低{v['hindsight']['room_from_winner']:.2f}元（当前费用的{100*v['hindsight']['room_from_winner']/b['total_cost']:.2f}%）。该计算预先知道全部未来实际负载和光伏，按普通电价安排整个区间，取消调整和紧急溢价，并允许最后库存降至1200 kWh。它放松了真实信息和合同条件，是不可执行的物理费用下界，绝不能作为可实现方案或填写提交表。

这一差距只能说明尚有理论空间，不能承诺再省这些钱，也不能说当前已达全局最优。本批较简单的参考窗口与准备分位改动只再省约3.20万元。如果继续争取更大改善，值得研究的是在规划时同时考虑多种连续供需偏差，让电池跨时段准备直接与不同情形的预期费用协调；这是后续建议，本轮未实施，也没有效果证据。

### 复核、记录与交接

本轮共{s['lp_calls']}次滚动线性规划，加1次理想下界计算，研究计算用时{s['elapsed_seconds']:.2f}秒。独立程序复算9条完整策略、{v['counts']['actual_intervals']}个实际区间、{v['counts']['preparation_groups']}组准备量和3组负载结构，核对历史信息时点、精确加权分位、已执行订单锁定、跨日储能、供需和费用。全年账单最大复算差{v['max_errors']['total_bill']:.3g}元。下界另经物理可行性和对偶核验。源文件及此前成果的指纹链一致。此为AI程序复核，不是人工批准。

推荐将本批“近期加权—日内偏差校正滚动调度”列为费用优先的新候选版本。保留旧论文、正式result3、问题四和state.json；若最终用于论文或提交，应同步更新相关数值与模型说明，不能只替换最低总数。本轮全部结果并入现有报告和证据，不额外起草论文。

复现入口：`runs/20260912-forecast-risk-v1/protocol.json`、`run.py`、`verify.py`。原始计算摘要为`outputs/summary.json`（其中pending状态表示计算结束时快照），后续独立复核以`outputs/verification.json`为准；各策略预测、系数、误差、准备、10分钟轨迹、逐日账单及理想下界另存于同一outputs目录。

'''

def prepend(relative, heading, content):
    p = P / relative
    old = p.read_text('utf-8')
    if heading not in old:
        p.write_text(content + old, encoding='utf-8')

prepend('questions/Q3/report.md', '## 2026-09-12 最新：近期负载加权与准备量再比较', body)
evidence = f'''## 2026-09-12 最新增量：近期加权与费用空间（推荐未自动采用）

- **Q3-C31：模型增量与反例。** 同星期4周按0.5逐周衰减，配合原日内累计偏差学习，各结构重建自身误差准备。总费{b['total_cost']:.2f}元，比上轮再省{t['saving']:.2f}元（{t['saving_percent']:.4f}%），相对原13146535.49元累计省{original-b['total_cost']:.2f}元。1周、2周和等权4周费用均高于本批推荐；分位0.40/0.50/0.70/0.80也均高于0.60。0.5是预设候选参数，不能称理论最优；不与误差每日0.7衰减混淆。
- **Q3-C32：风险和选型边界。** 紧急费增加{b['emergency_cost']-a['emergency_cost']:.2f}元、紧急量增加{b['emergency_kwh']-a['emergency_kwh']:.2f} kWh，紧急日189→185。190天节费、144天增费，5个月省、6个月增，优势主要集中9月；库存价值修正后仍省{t['terminal_reference_saving']:.2f}元。全年已用于选型，不证明跨年泛化。
- **Q3-C33：同版预报价值。** 三组全部重跑：{i['zero_cost']:.2f}→{i['no_new_cost']:.2f}→{i['full_cost']:.2f}元。新官方光伏预报条件增量{i['new_PV_saving']:.2f}元（{i['new_PV_saving_percent']:.4f}%），后两组期末库存一致。不得和原模型演化链混用。
- **Q3-C34：可复核性与乐观下界。** {s['lp_calls']}次滚动LP和1次理想LP，独立核对432864实际区间及170820准备组。理想下界{v['hindsight']['cost']:.2f}元放松未来信息、合同费用和末库存条件，差距{v['hindsight']['room_from_winner']:.2f}元不是可承诺节省。AI核验不构成人工批准。
- 证据：`questions/Q3/runs/20260912-forecast-risk-v1/outputs/summary.json`、`verification.json`、`hindsight.json`和逐策略记录。详细解释并入Q3/report.md；未改论文、提交结果、问题四或正式状态。

'''
prepend('paper_evidence/Q3.md', '## 2026-09-12 最新增量：近期加权与费用空间', evidence)
log = f'''## 2026-09-12：问题三近期负载加权深化完成

- 授权：用户“能不能继续深化模型看看还能不能再低呢，百分之0.6还是太低了”；执行既有Q3局部深化，保留正式revision49游标，不虚构小问冻结或批准。
- 完整334天、同物理和结算口径，7个候选新计算及2个信息对照；{s['lp_calls']}次滚动LP和1次理想LP。推荐EW4_Q60_full，总费{b['total_cost']:.2f}元，比上一轮再省{t['saving']:.2f}元（{t['saving_percent']:.4f}%）。
- 保留紧急费略增、6个月增费、同年选型局限，以及准备量过高过低均增费的反例。新版新预报增量{i['new_PV_saving']:.2f}元；乐观下界不可执行，不冒充方案。
- 独立核验432864实际区间、170820准备组及信息边界、原始来源指纹、费用和库存；最大总账差{v['max_errors']['total_bill']:.3g}元。AI复核不记人工认可。
- 来源：questions/Q3/runs/20260912-forecast-risk-v1/。解释、选择证据和限制并入已有Q3报告/实验索引/paper_evidence；论文、result3、Q4、正式state.json未改。

'''
for p in ('questions/Q3/experiments.md', 'state/decisions.md', 'state/ai_usage_log.md'):
    prepend(p, '## 2026-09-12：问题三近期负载加权深化完成', log)
print(json.dumps({'recorded': True, 'winner': b['label'], 'cost': b['total_cost'], 'saving': t['saving']}, ensure_ascii=False))
