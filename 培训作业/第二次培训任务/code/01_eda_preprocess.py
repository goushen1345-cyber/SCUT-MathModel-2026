# -*- coding: utf-8 -*-
"""Step 2: EDA and preprocessing for 2023 CUMCM Problem C."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils_common import (  # noqa: E402
    CATEGORIES,
    DATA,
    FIG,
    PROC,
    TAB,
    append_summary,
    ensure_attach_ascii,
    log,
    setup_plot_style,
)


def load_raw():
    ensure_attach_ascii()
    a1 = pd.read_excel(DATA / "attach1.xlsx")
    a1.columns = ["单品编码", "单品名称", "分类编码", "分类名称"]
    a1["单品编码"] = a1["单品编码"].astype(str)

    log("Loading attach2 (sales) — may take a minute...")
    a2 = pd.read_excel(DATA / "attach2.xlsx")
    a2.columns = [
        "销售日期",
        "扫码销售时间",
        "单品编码",
        "销量(千克)",
        "销售单价(元/千克)",
        "销售类型",
        "是否打折销售",
    ]
    a2["单品编码"] = a2["单品编码"].astype(str)
    a2["销售日期"] = pd.to_datetime(a2["销售日期"])

    a3 = pd.read_excel(DATA / "attach3.xlsx")
    a3.columns = ["日期", "单品编码", "批发价格(元/千克)"]
    a3["单品编码"] = a3["单品编码"].astype(str)
    a3["日期"] = pd.to_datetime(a3["日期"])

    a4_cat = pd.read_excel(DATA / "attach4.xlsx", sheet_name=0)
    a4_cat.columns = ["分类编码", "分类名称", "平均损耗率(%)"]
    a4_sku = pd.read_excel(DATA / "attach4.xlsx", sheet_name=1)
    a4_sku.columns = ["单品编码", "单品名称", "损耗率(%)"]
    a4_sku["单品编码"] = a4_sku["单品编码"].astype(str)

    return a1, a2, a3, a4_cat, a4_sku


def clean_sales(a2: pd.DataFrame) -> pd.DataFrame:
    before = len(a2)
    # keep sales type 销售; drop returns if any coded differently
    df = a2.copy()
    # remove non-positive qty / price
    df = df[(df["销量(千克)"] > 0) & (df["销售单价(元/千克)"] > 0)]
    # clip extreme prices (robust)
    q99 = df["销售单价(元/千克)"].quantile(0.999)
    df = df[df["销售单价(元/千克)"] <= max(q99, 200)]
    after = len(df)
    stats = {
        "raw_rows": before,
        "clean_rows": after,
        "dropped": before - after,
        "drop_rate": (before - after) / before if before else 0,
    }
    pd.DataFrame([stats]).to_csv(TAB / "eda_clean_stats.csv", index=False)
    return df, stats


def build_daily(a1, a2, a3):
    sales = a2.merge(a1[["单品编码", "单品名称", "分类编码", "分类名称"]], on="单品编码", how="left")
    sales["销售额"] = sales["销量(千克)"] * sales["销售单价(元/千克)"]
    sales["是否打折"] = (sales["是否打折销售"].astype(str).str.contains("是")).astype(int)

    # daily SKU
    daily_sku = (
        sales.groupby(["销售日期", "单品编码", "单品名称", "分类名称"], as_index=False)
        .agg(
            销量=("销量(千克)", "sum"),
            销售额=("销售额", "sum"),
            均价=("销售单价(元/千克)", "mean"),
            笔数=("销量(千克)", "count"),
            打折占比=("是否打折", "mean"),
        )
    )
    # weighted avg price
    daily_sku["均价"] = daily_sku["销售额"] / daily_sku["销量"]

    wh = a3.rename(columns={"日期": "销售日期", "批发价格(元/千克)": "批发价"})
    daily_sku = daily_sku.merge(wh, on=["销售日期", "单品编码"], how="left")
    daily_sku["成本"] = daily_sku["销量"] * daily_sku["批发价"]
    daily_sku["毛利"] = daily_sku["销售额"] - daily_sku["成本"]
    daily_sku["加成率"] = np.where(
        daily_sku["批发价"] > 0,
        daily_sku["均价"] / daily_sku["批发价"] - 1,
        np.nan,
    )

    # daily category
    daily_cat = (
        daily_sku.groupby(["销售日期", "分类名称"], as_index=False)
        .agg(
            销量=("销量", "sum"),
            销售额=("销售额", "sum"),
            成本=("成本", "sum"),
            毛利=("毛利", "sum"),
            单品数=("单品编码", "nunique"),
        )
    )
    daily_cat["均价"] = daily_cat["销售额"] / daily_cat["销量"]
    daily_cat["批发均价"] = daily_cat["成本"] / daily_cat["销量"]
    daily_cat["加成率"] = np.where(
        daily_cat["批发均价"] > 0,
        daily_cat["均价"] / daily_cat["批发均价"] - 1,
        np.nan,
    )
    daily_cat["星期"] = daily_cat["销售日期"].dt.dayofweek
    daily_cat["月份"] = daily_cat["销售日期"].dt.month
    daily_cat["年份"] = daily_cat["销售日期"].dt.year

    return sales, daily_sku, daily_cat


def plot_eda(a1, daily_cat, daily_sku, sales, a4_cat):
    setup_plot_style()

    # 1 category sku counts
    fig, ax = plt.subplots(figsize=(8, 4.5))
    cnt = a1["分类名称"].value_counts().reindex(CATEGORIES)
    sns.barplot(x=cnt.index, y=cnt.values, ax=ax, palette="Set2")
    ax.set_title("六大品类单品数量分布")
    ax.set_ylabel("单品数")
    ax.set_xlabel("品类")
    for i, v in enumerate(cnt.values):
        ax.text(i, v + 1, str(int(v)), ha="center")
    fig.savefig(FIG / "eda_category_sku_count.png")
    plt.close()

    # 2 category total sales
    fig, ax = plt.subplots(figsize=(8, 4.5))
    tot = daily_cat.groupby("分类名称")["销量"].sum().reindex(CATEGORIES)
    sns.barplot(x=tot.index, y=tot.values, ax=ax, palette="Set2")
    ax.set_title("各品类累计销量（千克）")
    ax.set_ylabel("累计销量/kg")
    fig.savefig(FIG / "eda_category_total_sales.png")
    plt.close()

    # 3 time series by category
    fig, ax = plt.subplots(figsize=(12, 5))
    for cat in CATEGORIES:
        sub = daily_cat[daily_cat["分类名称"] == cat].sort_values("销售日期").copy()
        # monthly aggregate (avoid deprecated/aliased resample freqs)
        sub["年月"] = sub["销售日期"].dt.to_period("M").dt.to_timestamp()
        m = sub.groupby("年月")["销量"].sum()
        ax.plot(m.index, m.values, label=cat, lw=1.6)
    ax.legend(ncol=3, fontsize=9)
    ax.set_title("各品类月度销量时间序列")
    ax.set_ylabel("月销量/kg")
    fig.savefig(FIG / "eda_monthly_sales_ts.png")
    plt.close()

    # 4 weekday pattern
    fig, ax = plt.subplots(figsize=(8, 4.5))
    wd = daily_cat.groupby("星期")["销量"].mean()
    labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    ax.bar(range(7), [wd.get(i, 0) for i in range(7)], color="#4C78A8")
    ax.set_xticks(range(7))
    ax.set_xticklabels(labels)
    ax.set_title("星期效应：日均销量")
    ax.set_ylabel("日均销量/kg")
    fig.savefig(FIG / "eda_weekday_pattern.png")
    plt.close()

    # 5 loss rates
    fig, ax = plt.subplots(figsize=(8, 4.5))
    loss = a4_cat.set_index("分类名称")["平均损耗率(%)"].reindex(CATEGORIES)
    sns.barplot(x=loss.index, y=loss.values, ax=ax, palette="flare")
    ax.set_title("各品类平均损耗率")
    ax.set_ylabel("损耗率/%")
    fig.savefig(FIG / "eda_loss_rate.png")
    plt.close()

    # 6 price distribution
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sample = sales.sample(min(50000, len(sales)), random_state=42)
    sns.boxplot(data=sample, x="分类名称", y="销售单价(元/千克)", order=CATEGORIES, ax=ax)
    ax.set_title("各品类销售单价分布")
    ax.set_ylabel("单价(元/kg)")
    ax.tick_params(axis="x", rotation=15)
    fig.savefig(FIG / "eda_price_boxplot.png")
    plt.close()

    # 7 clean before-after style summary figure
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].hist(np.log1p(sales["销量(千克)"]), bins=50, color="#72B7B2")
    axes[0].set_title("单笔销量 log1p 分布")
    axes[1].hist(sales["销售单价(元/千克)"].clip(0, 80), bins=50, color="#E45756")
    axes[1].set_title("销售单价分布（截断80）")
    fig.savefig(FIG / "eda_qty_price_dist.png")
    plt.close()

    # descriptive table
    desc = (
        daily_cat.groupby("分类名称")
        .agg(
            天数=("销售日期", "nunique"),
            日均销量=("销量", "mean"),
            日均销售额=("销售额", "mean"),
            日均毛利=("毛利", "mean"),
            平均加成率=("加成率", "mean"),
            销量标准差=("销量", "std"),
        )
        .reindex(CATEGORIES)
        .reset_index()
    )
    desc.to_csv(TAB / "eda_category_desc.csv", index=False, encoding="utf-8-sig")

    # monthly seasonality table
    season = (
        daily_cat.groupby(["分类名称", "月份"])["销量"].mean().unstack("月份").reindex(CATEGORIES)
    )
    season.to_csv(TAB / "eda_monthly_seasonality.csv", encoding="utf-8-sig")

    return desc


def main():
    log("=== EDA & Preprocess ===")
    a1, a2, a3, a4_cat, a4_sku = load_raw()
    a2c, stats = clean_sales(a2)
    log(f"Clean: {stats}")

    sales, daily_sku, daily_cat = build_daily(a1, a2c, a3)
    log(f"daily_sku={len(daily_sku)}, daily_cat={len(daily_cat)}")

    # save processed
    a1.to_pickle(PROC / "products.pkl")
    a4_cat.to_pickle(PROC / "loss_cat.pkl")
    a4_sku.to_pickle(PROC / "loss_sku.pkl")
    daily_sku.to_pickle(PROC / "daily_sku.pkl")
    daily_cat.to_pickle(PROC / "daily_cat.pkl")
    # also parquet-like csv samples
    daily_cat.to_csv(PROC / "daily_cat.csv", index=False, encoding="utf-8-sig")

    # keep sales light: only needed columns for association
    basket = sales[["销售日期", "扫码销售时间", "单品编码", "分类名称"]].copy()
    basket.to_pickle(PROC / "basket_raw.pkl")

    desc = plot_eda(a1, daily_cat, daily_sku, sales, a4_cat)

    append_summary("## EDA 预处理\n")
    append_summary(
        f"- 原始流水 {stats['raw_rows']} 行，清洗后 {stats['clean_rows']} 行，"
        f"剔除 {stats['dropped']} 行（{stats['drop_rate']:.2%}）。\n"
    )
    append_summary(
        f"- 单品 {len(a1)} 个，覆盖品类 {a1['分类名称'].nunique()} 个；"
        f"日品类面板 {len(daily_cat)} 行。\n"
    )
    for _, r in desc.iterrows():
        append_summary(
            f"- **{r['分类名称']}**：日均销量 **{r['日均销量']:.2f} kg**，"
            f"日均毛利 **{r['日均毛利']:.2f} 元**，平均加成率 **{r['平均加成率']:.2%}**。\n"
        )
    log("EDA done.")


if __name__ == "__main__":
    from utils_common import reset_summary

    reset_summary()
    main()
