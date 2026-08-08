# 创新点（可验证）

1. **品类共现提升度 + 相关双检验联动**  
   将 Pearson/Spearman 相关与小票级 Lift 关联规则结合，识别“相关但未必共购 / 共购但弱相关”的差异结构。  
   证据：`q1_category_corr_heatmap.png`、`q1_association_lift.png`、`q1_association_rules.csv`。

2. **时序交叉验证的弹性需求 + 成本加成网格寻优**  
   在星期/月份控制下用 Ridge 估计价格弹性，并以时序CV相对“均值基线”量化预测增益；再对加成率网格最大化含损耗的利润。  
   证据：`q2_elasticity.csv`、`q2_markup_profit_curve.png`、`ablation_compare.png`（相对历史加成/固定30%的收益提升见 `q2_summary.json`）。

3. **收益—品类需求缺口双目标的单品ILP**  
   在27–33单品与2.5kg陈列约束下，显式惩罚品类需求 unmet，对比贪心Top收益/Top销量/随机基线。  
   证据：`q3_method_compare.png`、`q3_category_coverage.png`、`q3_method_compare.csv`。

4. **多参数灵敏度 + 蒙特卡洛鲁棒性闭环**  
   对损耗率、加成偏离、弹性缩放做灵敏度，并对需求/成本对数正态扰动评估收益分位与达标概率。  
   证据：`sens_q2_three_params.png`、`robust_mc_profit_hist.png`、`robust_mc_summary.json`。

5. **残差诊断驱动的数据补采建议（Q4）**  
   由星期变异系数与打折强度图，论证客流/天气/促销档期等外生数据对纠偏截断需求的价值。  
   证据：`q4_weekday_cv_heatmap.png`、`q4_discount_impact.png`、`q2_residual_diagnostics.png`。
