# 问题二全年研究交付索引

授权Q2-ANNUAL-050，研究解释统一在../../report.md的Q2-annual-v4；本页只索引复现材料，不另写重复研究报告。当前本批完成，等待论文框架确认，无正文/PDF/Q3/冻结。

## 复现来源与顺序

研究环境E:/Anaconda/python.exe：Python3.13.5、numpy2.5.1、pandas3.0.5、scipy1.18.0、scikit-learn1.9.0；见annual/environment.json。每次LP以HiGHS求解，10秒上限，单线程固定；树种子2026。原始prepared-v1和Q1已保留输入指纹以及旧批157个输出记录均受保护。

不要在此目录直接重跑研究脚本覆盖已完成结果。需要重现时在同级另建隔离运行目录，复制本目录的源码与协议，保留旧批20260911-four-candidates-v1和项目原输入可读；各脚本R按自身位置、P按项目目录定位。按annual.py→validate_variants.py→refine.py→supplement.py依次执行；其输出目录存在即停止，防止覆写。研究再运行需在届时授权范围内，本次只给复现方法。

core.py是原四候选核心的365日扩展，Planner支持24/48小时与期末值开关；annual.py先验证原输入与旧结果哈希，再恢复T2/T3最近6月模型并接续原频率。原2—6月轨迹直接使用，不重拟或反向调参。最终算法源与执行环境指纹保存在各子批summary、output_hashes。

## 输出与计算量

- annual/：736次LP、104拟合，约42.73秒；包含原四候选334天汇总、新184天逐段计划/执行、训练参数/系数/模型、原输入映射。
- validation/：15固定单项敏感性，各334天，5010次LP，约34.82秒；全部方案、日记录、风险余量与求解日志保留。
- refinement/：β=.7/.8/.9各1月24天比较，再补.7/.9各334天，.8复用validation；740次LP，约6.54秒。selection.json仅数值选择来自1月，方法家族来自年度诊断的限制另有明确说明。
- supplement/：为分位取法归因及最终α、视野、期末设置增加5控制，共1670次LP，约11.70秒；协议在运行前保存。累计本批8156次LP，硬上限8500未超。
- verification.json：独立来源/预测/权重/拟合信息/物理/费用核查前6486次LP相关输出。
- delivery_verification.json：独立核查补充1670次LP，并从保存XLSX XML核对48096计划值、2004充放电组、668库存端点、439紧急行与Decimal费用；不新训练或求解。
- delivery_data/：最终逐段/每日/月度、配对日费用、紧急事件、指定日期表1—3、参数/权重/风险/归因汇总。prepare_delivery.py→finish_summary.py只整理现有输出。
- deliverables/result2.xlsx与result2_填写说明.md：完整334天模板输出，主结果13583810.84元；文件SHA256在delivery_verification.json和delivery_manifest.json。
- previews/：原模板及实际输出局部渲染，仅用于视觉检查，非论文图。

XLSX作者为bundled Node的@oai/artifact-tool，workbook.mjs import原模板后填值；源模板只读。先inspect原表，export前执行一次spreadsheets mark，再导出、查看、独立回读。已查看首段、午夜列、年末行、储能/紧急表，修正扩展行对齐后重导出；存完整精度，显示两位小数。

## 当前主张与限制

选定α=.7、β=.7、负载4个同星期/PV近7天、28天误差窗/4h分组、48h规划只执行24h普通订单。权重改变及分位取法贡献分别验证。24h成本略低但库存/紧急暴露更差，期末估值无实际费用贡献，原预测窗口与误差窗有更便宜反例，均保留；不称通用最优或未见年份验证。

未新增图像或论文正文。paper_evidence/问题二论文框架.md规划图位和章节，旧150天稿保持历史；Q1未冻结，既定Q1订单仅绑定本批内容哈希，正常依赖仍如实保存。独立核查是不同计算路径的AI数值验证，不是另一位人或人工已审。
