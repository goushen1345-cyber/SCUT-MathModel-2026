# 问题二四候选实跑 v1

授权Q2-TRIAL-047；已完成，无需为查看结果重跑。研究报告统一在questions/Q2/report.md当前v3，实验索引在questions/Q2/experiments.md。保留数据和Q1原版本；删除昨日独立候选，分别预测负载与光伏。Q1未冻结，本批按用户明确请求固定已有Q1订单哈希执行，不代表取得上游冻结。

本轮主选择T4，2—6月150天总费5875441.26元，较T1少590169.34元。范围、参数/权重、规则、预算及停止点见protocol.json，风险见报告。未运行全年、未填result2、未进入Q3。

## 文件入口

- outputs/comparison.csv：四策略费用、误差、紧急电、库存和未利用量。
- outputs/january_selection.json与period_metrics.csv：13设置的1月参数选择，含不支持加余量的反证。
- outputs/forecast_plans.csv.gz与execution.csv.gz：零点预测及48h计划，逐段实际执行、普通订单和五倍补电账。
- outputs/history_weights.jsonl：参考日期、各时段可用样本数与等权规则。
- outputs/fit_log.jsonl：独立负载/PV模型、训练截止、标准化参数、回归系数和树特征分裂计数；models/保存真实模型。
- outputs/historical_risk_errors.csv.gz、risk_margins.jsonl：完整有符号历史误差、取样时段、经验分位与余量。
- verification.json：不调用主程序计算函数的独立复核；0新增训练/0求解。
- interpretation/：月份、日型、配对日费用和最大正反差异两天。只从已有轨迹汇总。
- figures-v2/：正式本批两幅PNG300dpi和PDF，manifest/qa追踪来源、复现和实际查看；v1保留排版迭代。
- paper_section.tex：局部论文依据；完整新稿在paper/q2_comparison_manuscript_v1。
- delivery_checks.json：末次交付核对，不替代真实计算或人工核验。

outputs/summary.json的独立核查pending是运行结束时状态，后续verification.json为最新核查；图manifest的视觉pending由qa.json补记。保留锁定研究输出，避免改动其指纹造成版本混淆。

## 复现说明

使用outputs/environment.json所列Python3.13.5、NumPy2.5.1、pandas3.0.5、SciPy1.18.0、scikit-learn1.9.0，绘图Matplotlib3.11.1，SimSun；主程序设置单线程与种子2026。在本运行目录执行如下命令；python需指向上述本机环境。

```text
python -X utf8 run_compare.py --output reproduction-new
```

该命令会重新训练与求解，必须纳入后续授权预算。输出目录必须不存在，不覆盖本次outputs；verify.py当前绑定已交付outputs，如核查另一次运行应明确另建对应验证副本，不擅自改交付核验器引用。

只检查本批已有文件，且不重新运行研究：

```text
python -X utf8 verify.py
python -X utf8 check_delivery.py --final
```

check_delivery.py需捆绑Python的pdfplumber/Pillow；其--final绑定本次revision35，后续状态自然更新时不要重跑旧版断言判当前项目错误。图形复现也只读取保存结果：

```text
python -X utf8 plot_results.py --output ../../../../tmp/q2-trial-fig-reproduction-new
```

论文新稿已构建并检查，不再执行只创建一次目录的build_paper.py；修稿后在论文目录依build_record.json的XeLaTeX两遍及xdvipdfmx命令重新生成并查看实际页面。

## 检查说明

135792实际区间、271296规划区间、542592预测值及136个拟合模型均已独立核查。原7个保护输入/结果与157个锁定输出一致；两图四个最终PDF/PNG在tmp/q2-trial-fig-reproduction-v1独立复现哈希一致。论文新增15—17页和边界14页实际查看；前14页渲染像素与原稿全部一致，第10页求和符号的文字提取编码差异经实际页面确认不影响显示。

上述为AI执行的计算与排版检查，不是人工审查通过。全部研究结论限于本批协议，主方案选择不构成冻结。
