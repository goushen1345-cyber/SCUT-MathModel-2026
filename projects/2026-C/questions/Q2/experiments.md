# 问题二实验索引

## 最新：20260911-targeted-validation-v1（Q2-ROBUST-053）

已完成V07—V09，本批独立于此前年度8156次。protocol.json在运行前登记三情景、两个固定方案、历史连续误差片段及每14天3天事件设计；2004次LP、0拟合，约14.38秒，未超2200/30分钟。run_validation.py复用已验证Planner/实际执行逻辑，只对诊断输入及对应历史误差记账；未改原模型、数据、result2或论文。

- outputs/保存72次预设事件取样记录、3套情景预测和事后误差、6套334天完整计划/实际轨迹、分位及求解日志、日/总费用、来源和输出哈希。
- 负载与联合各9次无合格历史块，实际施加附加误差为45天；PV72天。所有无扰动事件均保留，不重采以造不利结果。outputs/summary中的72是计划事件日，解释见interpretation.json。
- analyze_results.py只从原年度与本批已保存结果统计月/季节/星期、事件与恢复期、各自紧急费最差17天、配对增费最差17天；analysis/保存全日、分组、配对、尾部日期及摘要。explain_validation.py补充有效暴露日期/月份与明确限制，无新求解。
- verify_results.py独立核对历史来源、裁切、情景误差更新、所有物理与费用、保存日表/分组/尾部；verification.json通过，0新LP/拟合。前一批科学文件与原材料指纹保持。
- 三情景近期方案总费14000141.60/13735149.31/14048148.20元，对等权省3.52%/3.09%/3.39%，单日反转和受扰覆盖缺口保留；原年度主结果13583810.84元不变。全年已用于方法选择，分组和合成情景不作独立跨年验证。
- 交付主报告Q2-validation-v5、paper_evidence/Q2.md和原框架的验证材料更新；无正文/PDF/新图，未冻结/跨Q3。

---

## 当前：20260911-annual-validation-v1（Q2-ANNUAL-050）

完整全年回放与结果交付完成，主报告Q2-annual-v4。本轮没有新增论文正文或PDF；下文原945次/150天批次保留为历史。所有新研究在本隔离目录，原始附件、prepared-v1、Q1、旧157输出不变。

| 实际操作 | 输入/范围 | 新LP/拟合 | 证据 |
|---|---|---:|---|
| 四候选延续 | 原1月设置及6月各自库存/最后拟合，7—12月184天 | 736 /104 | annual/summary.json、comparison.csv、fit_log、forecast_plans、execution |
| 固定敏感性15组 | 2—12月334天，α/视野/估值/误差窗口/分组/历史权重 | 5010 /0 | validation/summary.json、comparison.csv、schedules/ |
| 近期误差权重细化 | β三档1月8—31日；β=.7/.9各334天，.8复用前项 | 740 /0 | refinement/selection.json、comparison.csv、schedules/ |
| 最终方案补充5对照 | 等权阶梯CDF归因，最终α=.6/.8、24h、无期末估值 | 1670 /0 | supplement/protocol.json、summary.json、comparison.csv、schedules/ |
| 独立验证 | 全部新研究及旧来源/既有结果保护 | 0 /0 | verification.json、delivery_verification.json |
| 结果整理与XLSX导出 | 334天逐段、6组/日库存和紧急事件、4个指定日 | 0 /0 | delivery_data/、deliverables/result2.xlsx、result2_填写说明.md |
| 论文框架 | 已验证的全年模型、结果和边界 | 0 /0 | paper_evidence/问题二论文框架.md；无正文/PDF |

本批合计8156次LP、104个单目标拟合，实际研究计算计时约95.80秒；总硬预算8500/60分钟未超。补充5对照合计1670用于关闭最终主张缺口，见独立事前协议；未扩为新模型家族，未再选最终α/β。与先前945次合计9101次，不应把旧批重复计入本批预算。

最终本轮选择近期加权误差方案（β=.7、α=.7），正式334天费用13583810.84元；24小时同方案低3215.61元但紧急暴露更大，未隐藏。1月选定参数/全年用于诊断的边界、等权分位插值差异控制、全部不改善对照均保留。来源/产物每子批次output_hashes.json，最终delivery_manifest.json登记。

---

## 历史：四候选150天批次

当前批次：20260911-four-candidates-v1；依据Q2-TRIAL-047。只列真实执行，不将先前候选或后续验证计划写成结果。

| 记录 | 输入与范围 | 实际操作 | 产物与状态 |
|---|---|---|---|
| 先前独立探索 | prepared-v1附件1/2；主期2—12月 | 描述统计、7种固定历史参照和2组连续误差；0拟合/0调度 | audit/q2-exploration-v1；详见Q2/report历史v2 |
| 本批小例核对 | 明确构造的手算供需/库存小例 | 4个实际执行器例和3次简单LP | runs/20260911-four-candidates-v1/preflight/checks.json；全部达预期 |
| 公共初始化 | 1月1日6000；Q1既定订单；首段参考标记 | 1月1—31日连续运行，30次LP | outputs/initialization.json、execution.csv.gz的initialization；2月起点8592.69356093 |
| 有限参数比较 | 1月8—31日，各方案同一1月8日起点 | 13组×24日=312次LP；参数按真实费用选择 | outputs/january_selection.json、period_metrics.csv；正余量三档均比零余量贵 |
| 四候选费用比较 | 2月1—6月30日150天；共同起点、设备/价格/控制 | 4×150=600次LP，只有零点普通订单；136个拟合含参数期 | outputs/comparison.csv、forecast_plans.csv.gz、execution.csv.gz、daily_metrics.csv |
| 独立复核 | 全部保存的预测、模型、订单/实际轨迹 | 0训练/0求解；核对历史资格、542592预测值、实际/规划区间、费用 | verification.json；AI核查通过，不是人工已审 |
| 比较解释/代码图 | 只读已保存轨迹 | 汇总费用/月份/日型/最大正反差异日；2图 | interpretation/、figures-v2/；四PDF/PNG复现哈希一致，qa.json |
| 局部论文 | 当前比较、权重、原Q1稿 | 新稿追加第15—17页，无新研究计算 | paper/q2_comparison_manuscript_v1；源文件/17页PDF/qa.json |

主批942次LP，另小例3次，共945次；136次单目标拟合。主批约35.97秒，未超1200次/30分钟。初始单线程环境/版本、参数与输入指纹在outputs/environment.json和protocol.json。pandas可选numexpr版本提示不影响本次完成，见AI日志。

T4总费5875441.26元，本轮选择为主方案；T1为简单对照/备用，T3、T2分别为6420075.29、6750499.17元。不是全部预测模型与余量的交叉搜索；未跑7—12月或新灵敏度检查，后续建议见report当前第8节。

状态说明：用户已明确授权本批实跑并要求据比较选方案；Q1未冻结，上游Q1订单按内容哈希固定使用，局部例外详见047。state保持真实未冻结依赖，不把执行完成改写为冻结或人工认可。
