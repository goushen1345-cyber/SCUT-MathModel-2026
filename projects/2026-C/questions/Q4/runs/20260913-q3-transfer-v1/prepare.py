"""Record the user's Q3 handoff and bounded Q4-3 rerun before computation."""
from pathlib import Path
import json, hashlib
R=Path(__file__).resolve().parent; P=R.parents[3]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def prepend(rel,body):
 p=P/rel; old=p.read_text('utf-8')
 if body.splitlines()[0] not in old:p.write_text(body+old,encoding='utf-8')
handoff='''## 2026-09-13：问题三深化后的论文交接与问题四引用版本

用户要求“你先把对问题三做的深化和建模记录下来，准备后续论文使用，然后再跑问题四”。本次以20260912-forecast-risk-v1中的EW4_Q60_full作为问题4-3重跑的上游版本；这是指定研究输入，不代替问题三冻结或论文定稿。

后续问题三章节按以下逻辑组织：先解释官方光伏预报仍有误差，因此以历史实测信息融合；再解释高价紧急补购使预测平均误差并非唯一目标，因此加入历史净需求误差准备；随后说明白天已发生的负载偏差值得利用，加入日内负载校正；最后用近期加权的同星期参考，使零点负载判断兼顾近期变化与多周稳定性。各环节继续由滚动线性规划统一安排订单与电池，不能把预测模块和调度写成互不相干的几套模型。

最新可复述模型名为“近期加权与日内校正滚动调度”。索引d表示日期、k表示10分钟区间，时长Δt=1/6小时，r属于0/36/72/108。零点预测为过去四个同星期日负载曲线的加权和，权重按0.5逐周减半并归一化；历史充足时为8/15、4/15、2/15、1/15。日内计算b(d,r)=mean(L_actual(d,k)-L_midnight(d,k),k<r)。对未来3小时组g，利用此前28个完整日拟合θ(r,g)=clip(Σx_j y_j/Σx_j²,0,1)，不足7个有效日或分母近零时回退0；更新L_hat(d,k|r)=max(0,L_midnight(d,k)+θ(r,g)b(d,r))。零点无日内修正，次日辅助负载不直接沿用当天偏差。

净需求历史误差以kWh计，为[(实际负载-实际光伏)-(当时负载预测-当时光伏预测)]Δt。每次决策只收集此前已经兑现的误差，使用28天窗口、3小时分组、每日0.7衰减与0.60加权分位形成非负准备。0.5控制跨周负载参考，0.7控制误差日期权重，0.60控制准备分位，θ由历史回归估计；四者作用不同，不能统称权重，更不是熵权法。

共享调度目标及物理约束沿用原问题三已记录公式：普通订单、相对零点净调整和五倍紧急费分账；实际电价固定，Q3不预测电价。储能范围1200—10800kWh，充放外侧功率上限5000kW，效率各90%，实际库存跨日衔接，不继承Q1日首尾相等。各次只能改未执行订单，光伏可直接供负载，未利用电不产生售电收入。

结果组织必须使用两条不同证据链。模型深化链为13146535.49→13046147.20→13014172.33元；最新信息对照链为13590016.18→13083710.42→13014172.33元，新发布光伏预报的条件收益为69538.10元。前一条解释如何改模型，后一条回答题目要求的新预报价值，不能跨版本拼接。最新新增收益31974.87元、累计132363.16元；不要混淆。

论文验证段应保留：准备0.40/0.50/0.70/0.80均更贵；仅参考上一周更贵；本轮紧急费略增4491.13元，190天便宜、144天更贵，5个月省、6个月增；期末库存价值修正不改变节费方向。全文使用同一年选型，尚无跨年泛化证据。不可执行理想下界12226840.07元仅为研究诊断，不列成可实施对照模型。

对应证据Q3-C27—C34和各轮原始结果、独立验证，详情在本报告后续已有记录。若之后修改论文，需要一起更新负载公式、算法步骤、总费用、费用分解、信息对照、风险段、摘要数字和总体模型框架图；旧PNG/TeX仍是旧版，不可只替换总费。此次仅补全交接记录，未改论文或正式result3。

'''
prepend('questions/Q3/report.md',handoff)
prepend('paper_evidence/Q3.md','''## 2026-09-13：问题三写作输入已汇总

用户明确要求先记录问题三深化，再重跑问题四。最新上游引用EW4_Q60_full（13014172.33元）；新增结构、符号公式、四类参数含义、两条证据链、风险和受影响论文位置已汇总在Q3/report.md开头，对应C27—C34。后续问题三写作需同步更新模型、结果、信息价值、验证及摘要/框架图，旧论文仍为旧版待更新。本条不代表冻结、人工核验或立即起草论文授权。

''')
protocol=dict(id='Q4-Q3-TRANSFER-20260913',authorization='你先把对问题三做的深化和建模记录下来，准备后续论文使用，然后再跑问题四',scope='Q3 evidence handoff, then Q4-3 only as specified in preceding exchange; Q4-2 retained',upstream='Q3/20260912-forecast-risk-v1/EW4_Q60_full',period='2025-02-01..2025-12-31;334days',initial=8592.693560925925,comparison='Replay old Q4-3 P2-full with old price and supply forecasts. Transfer Q3 EW4 learned-prefix load and own margins, refit original full Ridge(alpha10,56-day,weekly) because net forecast is a price feature. Compare quantiles .40/.50/.60/.70/.80 using the same transferred price forecasts. Retain original prices, constraints, settlement and terminal reference. No new scenario model, no future price access.',validation='Source hashes; verify replay against all old orders/trajectories; transfer arrays and margins from verified Q3 evidence; independent price features/time cutoffs, saved Ridge prediction and normal equations; all exported physical execution/locked orders/inventory and Decimal billing; monthly/daily/high-price risk and terminal inventory valuation. Same-year selection is not unseen-year validation.',budget=dict(rolling_lp_max=9000,price_fits_max=60,seconds_max=1800),stop='Deliver verified cost/risk comparison and recommendation; no paper/result4/state cursor replacement, no frozen state.',state_note='Formal revision49 cursor is historical and inconsistent with accumulated local research scopes. Preserve it and record current explicit local authorization without inventing freezes or past approvals.')
files=['state/state.json','data/prepared-v1/actual_price.csv','data/prepared-v1/day_reference.csv','questions/Q4/runs/20260912-three-candidates-v1/run_compare.py','questions/Q4/runs/20260912-three-candidates-v1/outputs/supply_inputs.npz','questions/Q4/runs/20260912-three-candidates-v1/outputs/price_forecasts.npz','questions/Q4/runs/20260912-selected-deepening-v1/outputs/summary.json','questions/Q4/runs/20260912-selected-deepening-v1/outputs/verification.json','questions/Q4/runs/20260912-selected-deepening-v1/outputs/strategies/Q4-3-P2-full.npz','questions/Q4/runs/20260912-selected-deepening-v1/outputs/strategies/Q4-3-P2-full.daily.csv','questions/Q3/runs/20260912-forecast-risk-v1/outputs/verification.json','questions/Q3/runs/20260912-forecast-risk-v1/outputs/load_EW4.npz','questions/Q3/runs/20260912-final-information-v1/outputs/forecasts.npz']
files += [f'questions/Q3/runs/20260912-forecast-risk-v1/outputs/strategies/EW4_Q{q}_full.margin.npz' for q in (40,50,60,70,80)]
protocol['source_sha256']={f:sha(P/f) for f in files}
if not (R/'protocol.json').exists():(R/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
log='''## Q4-Q3-TRANSFER-20260913：问题三记录及问题4-3重跑授权

- 用户原话：“你先把对问题三做的深化和建模记录下来，准备后续论文使用，然后再跑问题四”。按上一条交流具体执行问题4-3重跑，问题4-2保留。
- 先完成Q3研究/论文证据交接，再以EW4_Q60_full上游重跑Q4-3；完整334天，复现旧基线，保留完整岭回归并重训供需特征，比较准备分位0.40/0.50/0.60/0.70/0.80。预算9000次LP、60次价格拟合、1800秒，独立核验/费用风险解释属于本次交付。
- 当前state.json仍是历史revision49游标，结构校验通过，但不反映历次局部授权。保留既有记法，按本条明确局部授权执行隔离研究，不伪造冻结或批准。协议与来源指纹位于questions/Q4/runs/20260913-q3-transfer-v1/protocol.json。
- 旧论文、Q4-2、正式结果表和原始附件只读；不新开候选模型、不运行情景方案、不新增图或写论文。工具为Codex及Python，AI核验与人工确认分别记录。

'''
for f in ['state/decisions.md','state/ai_usage_log.md','questions/Q4/experiments.md']:prepend(f,log)
prepend('questions/Q4/report.md','''## 2026-09-13：接入问题三深化版本的比较与验证计划

按用户明确指令，先整理问题三证据后重跑问题4-3。已完成记录的上游为近期加权同星期负载加日内累计偏差校正，采用各自历史误差准备。问题四仍使用原完整岭回归价格模型（56天、每周重训、正则10），未来电价不可知；供需输入更新，因此历史训练特征与实时价格预测一起重建。

比较：旧P2-full完整复现；新供需结构下准备分位0.40/0.50/0.60/0.70/0.80完整334天。价格预测不因准备分位改变而重复训练。最重要检验是供需改进在波动电价下是否仍省钱，以及是否以更多紧急电或少留末电量换取费用下降。独立检查全部实际10分钟轨迹、费用、锁单、库存与合法价格特征，核对各月/高价时段风险；参数比较属于同年探索，不做跨年泛化声明。上限9000次LP、60次拟合、1800秒，完成后交付建议，不自动填表或改论文。原问题4-2和旧问题4-3作为各自旧版本保留。

''')
print('Q3 paper handoff recorded; Q4-3 protocol and authorization recorded.')
