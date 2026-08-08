# -*- coding: utf-8 -*-
"""Q4: Additional data collection recommendations + supporting evidence plots."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils_common import FIG, PROC, TAB, append_summary, log, setup_plot_style  # noqa: E402


RECS = [
    {
        "数据项": "实时库存与当日剩余量",
        "采集频率": "小时级/日终盘点",
        "对问题帮助": "把“销量”与“需求”解耦，修正损耗与缺货截断偏差，提升Q2/Q3补货精度",
        "优先级": "高",
    },
    {
        "数据项": "客流量与转化率（进店/路过）",
        "采集频率": "小时",
        "对问题帮助": "解释星期与节假日波动，改进需求外生驱动项，降低仅用价格解释的偏误",
        "优先级": "高",
    },
    {
        "数据项": "天气（温度/降雨）与节假日标记",
        "采集频率": "日",
        "对问题帮助": "蔬菜需求强天气敏感；可显著提升短期预测R²与鲁棒性",
        "优先级": "高",
    },
    {
        "数据项": "供应商可靠度、到货准时率、品质等级",
        "采集频率": "批次",
        "对问题帮助": "支持Q3单品筛选与风险约束，避免只按历史销量选品",
        "优先级": "中",
    },
    {
        "数据项": "陈列面积/货架位置与促销档期",
        "采集频率": "日",
        "对问题帮助": "刻画空间约束与交叉弹性，使27–33单品组合更贴近真实货架",
        "优先级": "中",
    },
    {
        "数据项": "竞品商超价格与替代品价格",
        "采集频率": "日",
        "对问题帮助": "完善价格弹性识别，避免内生性导致弹性低估/高估",
        "优先级": "中",
    },
    {
        "数据项": "顾客画像与复购（会员）",
        "采集频率": "交易级",
        "对问题帮助": "细分需求、个性化组合；支撑问题1关联规则的因果解释",
        "优先级": "低",
    },
]


def evidence_plots(daily_cat):
    setup_plot_style()
    # weekday CV as proxy for need of traffic data
    rows = []
    for cat in daily_cat["分类名称"].unique():
        sub = daily_cat[daily_cat["分类名称"] == cat]
        for wd, g in sub.groupby("星期"):
            rows.append({"品类": cat, "星期": wd, "变异系数": g["销量"].std() / (g["销量"].mean() + 1e-6)})
    cv = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(9, 5))
    pivot = cv.pivot_table(index="品类", columns="星期", values="变异系数")
    im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(7))
    ax.set_xticklabels(["一", "二", "三", "四", "五", "六", "日"])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("各品类星期销量变异系数（说明需引入客流/天气外生变量）")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(FIG / "q4_weekday_cv_heatmap.png")
    plt.close()

    # discount impact
    daily_sku = pd.read_pickle(PROC / "daily_sku.pkl")
    # approximate: higher discount share days
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sub = daily_sku[daily_sku["销售日期"] >= "2023-01-01"]
    sub = sub.dropna(subset=["打折占比"])
    bins = pd.cut(sub["打折占比"], bins=[-0.01, 0.05, 0.2, 0.5, 1.0], labels=["低", "中", "高", "极高"])
    g = sub.groupby(bins, observed=False)["销量"].mean()
    ax.bar(g.index.astype(str), g.values, color="#E45756")
    ax.set_title("打折强度与日均销量（需系统采集促销档期）")
    ax.set_ylabel("日均销量/kg")
    fig.savefig(FIG / "q4_discount_impact.png")
    plt.close()


def main():
    log("=== Q4 Recommendations ===")
    daily_cat = pd.read_pickle(PROC / "daily_cat.pkl")
    df = pd.DataFrame(RECS)
    df.to_csv(TAB / "q4_data_recommendations.csv", index=False, encoding="utf-8-sig")
    evidence_plots(daily_cat)

    append_summary("\n## 问题4 数据采集建议\n")
    for r in RECS:
        append_summary(f"- **{r['数据项']}**（{r['优先级']}）：{r['对问题帮助']}。\n")
    log("Q4 done.")


if __name__ == "__main__":
    main()
