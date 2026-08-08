# -*- coding: utf-8 -*-
import json
from pathlib import Path

import numpy as np
import pandas as pd

TAB = Path("output/tables")
OUT = Path("output")

q1 = json.loads((TAB / "q1_summary.json").read_text(encoding="utf-8"))
q2 = json.loads((TAB / "q2_summary.json").read_text(encoding="utf-8"))
q3 = json.loads((TAB / "q3_summary.json").read_text(encoding="utf-8"))
mc = json.loads((TAB / "robust_mc_summary.json").read_text(encoding="utf-8"))
elast = pd.read_csv(TAB / "q2_elasticity.csv")
cat = pd.read_csv(TAB / "q2_category_week_summary.csv")
cov = pd.read_csv(TAB / "q3_category_coverage.csv")
pear = pd.read_csv(TAB / "q1_corr_pearson.csv", index_col=0)
arr = pear.values.copy()
np.fill_diagonal(arr, np.nan)
pm = pd.DataFrame(arr, index=pear.index, columns=pear.columns)
mx = pm.stack().idxmax()
mn = pm.stack().idxmin()
top = q1["top_lift"][0]

lines = [
    "# 结果摘要（真实运行产出）\n\n",
    "> 口径：销量/补货单位为千克；收益=销售收入−批发成本（按补货量）；"
    "补货量=预测需求/(1−损耗率)；加成率在各品类历史分位可行域内寻优；"
    "Q3可售集合=2023-06-24~30。\n\n",
    "## EDA\n",
    "- 流水清洗：878503→878042 行；单品251；日品类面板6474行。\n\n",
    "## Q1\n",
    f"- 最强相关：{mx[0]}–{mx[1]}，Pearson={pm.stack().max():.3f}；"
    f"最弱：{mn[0]}–{mn[1]}，Pearson={pm.stack().min():.3f}。\n",
    f"- 聚类K={q1['best_cluster_k']}，轮廓系数={q1['silhouette']:.3f}；"
    f"Pearson-Spearman一致性={q1['pearson_spearman_consistency']:.3f}。\n",
    f"- Top Lift：{top['前项']}→{top['后项']}，Lift={top['提升度']:.3f}，"
    f"支持度={top['支持度']:.4f}。\n\n",
    "## Q2（2023-07-01~07）\n",
    f"- 周收益 **{q2['week_total_profit']:.2f}** 元；周补货 **{q2['week_total_replenish']:.2f}** kg；"
    f"平均加成 **{q2['avg_markup']:.2%}**。\n",
    f"- 对照：历史加成收益 {q2['baseline_hist_profit']:.2f}（提升 {q2['lift_vs_hist']:.2%}）；"
    f"固定30%收益 {q2['baseline_fixed30_profit']:.2f}（提升 {q2['lift_vs_fixed30']:.2%}）。\n",
]
for _, r in cat.iterrows():
    lines.append(
        f"- {r['品类']}：周补货 {r['周补货总量']:.1f} kg，加成 {r['平均加成率']:.2%}，周收益 {r['周收益']:.2f} 元。\n"
    )
for _, r in elast.iterrows():
    lines.append(f"- 弹性 {r['品类']}={r['价格弹性']:.3f}，CV-MAE={r['CV_MAE']:.2f}。\n")
lines += [
    "\n## Q3（2023-07-01）\n",
    f"- 入选 **{q3['n_sku']}** 个单品；收益 **{q3['total_profit']:.2f}** 元；"
    f"补货 **{q3['total_replenish']:.2f}** kg；相对贪心Top收益提升 **{q3['lift_vs_greedy']:.2%}**。\n",
]
for _, r in cov.iterrows():
    lines.append(
        f"- {r['分类名称']}：{int(r['单品数'])}个，补货{r['补货量']:.1f}kg，需求满足率{r['需求满足率']:.2%}。\n"
    )
lines += [
    "\n## 鲁棒性\n",
    f"- MC(n={mc['mc_n']})：均值 {mc['mc_mean']:.2f}，std {mc['mc_std']:.2f}，"
    f"P05–P95 [{mc['mc_p05']:.2f},{mc['mc_p95']:.2f}]，"
    f"≥95%基线概率 {mc['prob_above_95pct_base']:.2%}。\n",
]
(OUT / "results_summary.md").write_text("".join(lines), encoding="utf-8")
print("ok")
