# 待主执行者合并的图登记条目

本文件仅交接五张新版结果图，不替代项目唯一图索引。来源与全部文件SHA-256见同目录 `result_figures_manifest.json`。代码为 `update_result_figures.py`；表格和 `derived_values.json` 同样由该脚本从保存轨迹生成。

复现环境：Python 3.13.5（实际版本以manifest为准）、matplotlib 3.11.1、Times New Roman及SimSun。执行 `E:/Anaconda/python.exe -X utf8 scripts/update_result_figures.py --output-root scripts/reproduction_check`。独立目录的5张PDF、5张PNG、4张TeX表及derived JSON与论文目标文件全部哈希一致。原始研究输入只读，没有训练、求解、补实验或更改研究状态。

| Figure ID | 图/输出（相对本论文目录，PDF与PNG） | 来源 | 图文用途与真实结论 | 边界 |
|---|---|---|---|---|
| FIG-Q3-FINAL-MONTHLY-20260913 | fig/q3_final_monthly | Q3 20260912-forecast-risk-v1，EW4_Q60_full.daily.csv | Why：说明全年费用如何分布；What：2—12月普通结算与紧急费；So What：4月最低、12月最高，普通结算占主要部分；Then What：将总费落到不同月份的实际供电成本。 | 仅最终费用结构，不声称各月较某对照均节省；月天数不同。 |
| FIG-Q3-FINAL-DAYS-20260913 | fig/q3_final_days | 同版本EW4_Q60_full.npz及20260911-four-candidates-v1/sources.npz实际负载PV | Why：解释订单与电池怎样补缺；What：3/20、9/23供需、零点/最终订单、内部库存、每10分钟补缺；So What：库存和放电功率都会限制补缺，9/23 20:30尚有库存仍达放电功率上限；Then What：说明全天电量充足不能保证每个时段免于紧急购电。 | 功率图将订单kWh乘6；库存画边界值；按已排序时段直接绘图，未再循环位移。 |
| FIG-Q3-FINAL-INFORMATION-20260913 | fig/q3_final_information | 同版本EW4_Q60_full_ZERO、EW4_Q60_no_new、EW4_Q60_full，summary.json | Why：单独评价日内新预报；What：三种信息条件334天总费；So What：1359.00、1308.37、1301.42万元；新预报边际省6.95万元；Then What：区分共同反馈调整收益和后发预报收益。 | 各组保持自身因果误差准备；第一步不是单纯光伏预报价值，差额不能全部归因于官方预报。 |
| FIG-Q3-FINAL-VALIDATION-20260913 | fig/q3_final_validation | 同版本W1/W2/EW4分位0.6及EW4五分位；四周等权来自20260912-load-feedback-v1的LEARN_PREFIX | Why：解释负载参考和准备量选择；What：同日内校正下四种同星期参考和0.4—0.8准备分位；So What：四周偏重近期更便宜；低准备增加紧急成本，高准备增加普通成本，0.6费用最低；Then What：支持适度准备。 | 四周等权为同结构已核验对照的复用；比较的是结构，不呈现修改时间线；非跨年泛化证明。 |
| FIG-Q4-FINAL-VALIDATION-20260913 | fig/q4_final_validation | Q4 20260912-selected-deepening-v1/comparison.csv的Q4-2 leaves7/full/leaves31；20260913-q3-transfer-v1的五分位 | Why：分别解释两分支选型；What：Q4-2树复杂度、Q4-3准备分位的实际费用；So What：31叶相对15叶省6605.53元；Q4-3仍0.6费用最低；Then What：电价变化后仍需要费用与紧急风险权衡。 | 左右属于各自分支，纵轴不同，不能横向比较曲线高低；不复用旧Q4-3价格更新时间检验为新版结论。 |

图像验收：五张实际PNG已由AI逐张查看。两张验证图初稿边缘标签过近，现已留足横向间距并重新查看。所有图中文字为黑色，颜色用于数据类别，PDF为矢量；柱图纵轴从零开始，参考类别用散点不伪造连续趋势。未进行真人读图或人工模型核验。论文嵌入页由主执行者检查。

表格：`tables/q3_original.tex`、`q3_final.tex`、`q3_storage.tex`、`q3_emergency.tex` 均可直接 `\input`。储能表充电为外部输入侧、放电为负载输出侧，内部库存单列。紧急购电表列全部实际发生时段，6/21明确无紧急购电。各项分别舍入后可能与合计相差0.01，合计均从未舍入原始数据计算。
