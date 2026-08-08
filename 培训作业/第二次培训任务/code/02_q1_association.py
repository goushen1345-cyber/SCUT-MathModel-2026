# -*- coding: utf-8 -*-
"""Q1: Distribution, correlation and association analysis."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils_common import (  # noqa: E402
    CATEGORIES,
    FIG,
    PROC,
    TAB,
    append_summary,
    log,
    save_json,
    setup_plot_style,
)


def category_correlation(daily_cat: pd.DataFrame):
    pivot = (
        daily_cat.pivot_table(index="销售日期", columns="分类名称", values="销量", aggfunc="sum")
        .reindex(columns=CATEGORIES)
        .fillna(0)
    )
    pearson = pivot.corr(method="pearson")
    spearman = pivot.corr(method="spearman")
    pearson.to_csv(TAB / "q1_corr_pearson.csv", encoding="utf-8-sig")
    spearman.to_csv(TAB / "q1_corr_spearman.csv", encoding="utf-8-sig")

    setup_plot_style()
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    sns.heatmap(pearson, annot=True, fmt=".2f", cmap="RdBu_r", center=0, ax=axes[0],
                vmin=-1, vmax=1)
    axes[0].set_title("品类日销量 Pearson 相关")
    sns.heatmap(spearman, annot=True, fmt=".2f", cmap="RdBu_r", center=0, ax=axes[1],
                vmin=-1, vmax=1)
    axes[1].set_title("品类日销量 Spearman 相关")
    fig.tight_layout()
    fig.savefig(FIG / "q1_category_corr_heatmap.png")
    plt.close()
    return pivot, pearson, spearman


def distribution_fit(daily_cat: pd.DataFrame):
    rows = []
    setup_plot_style()
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    axes = axes.ravel()
    for i, cat in enumerate(CATEGORIES):
        x = daily_cat.loc[daily_cat["分类名称"] == cat, "销量"].dropna().values
        # lognormal vs gamma vs normal on positive
        candidates = {}
        for name, dist in [("norm", stats.norm), ("lognorm", stats.lognorm), ("gamma", stats.gamma)]:
            try:
                params = dist.fit(x)
                kstest = stats.kstest(x, dist.cdf, args=params)
                candidates[name] = {"ks": kstest.statistic, "p": kstest.pvalue, "params": params}
            except Exception:
                pass
        best = min(candidates.items(), key=lambda kv: kv[1]["ks"]) if candidates else ("none", {})
        rows.append(
            {
                "品类": cat,
                "均值": float(np.mean(x)),
                "标准差": float(np.std(x)),
                "偏度": float(stats.skew(x)),
                "峰度": float(stats.kurtosis(x)),
                "最优分布": best[0],
                "KS统计量": best[1].get("ks", np.nan),
                "KS_p值": best[1].get("p", np.nan),
            }
        )
        axes[i].hist(x, bins=40, density=True, alpha=0.7, color="#4C78A8")
        axes[i].set_title(f"{cat} 日销量分布")
        axes[i].set_xlabel("销量/kg")
    fig.tight_layout()
    fig.savefig(FIG / "q1_category_dist_fit.png")
    plt.close()
    df = pd.DataFrame(rows)
    df.to_csv(TAB / "q1_distribution_fit.csv", index=False, encoding="utf-8-sig")
    return df


def association_rules(basket_raw: pd.DataFrame, products: pd.DataFrame):
    """Category co-occurrence by approximate receipt (date+time minute)."""
    log("Building category association rules...")
    basket = basket_raw.copy()
    # receipt proxy: date + time truncated to minute + round seconds group
    basket["时刻"] = basket["扫码销售时间"].astype(str).str[:8]  # HH:MM:SS
    basket["小票"] = basket["销售日期"].astype(str) + "_" + basket["时刻"].str[:5]
    # to reduce noise, use date+time to 1-min and require multi-item
    tickets = basket.groupby("小票")["分类名称"].apply(lambda s: sorted(set(s)))
    tickets = tickets[tickets.map(len) >= 2]
    # sample if too many
    if len(tickets) > 80000:
        tickets = tickets.sample(80000, random_state=42)

    # support / confidence / lift among categories
    cats = CATEGORIES
    n = len(tickets)
    support = {c: 0 for c in cats}
    pair_sup = {(ca, cb): 0 for i, ca in enumerate(cats) for cb in cats[i + 1 :]}
    for items in tickets:
        items = [c for c in items if c in support]
        for c in items:
            support[c] += 1
        for i, ca in enumerate(items):
            for cb in items[i + 1 :]:
                key = (ca, cb) if (ca, cb) in pair_sup else (cb, ca)
                if key in pair_sup:
                    pair_sup[key] += 1

    rules = []
    for (ca, cb), cnt in pair_sup.items():
        sa, sb = support[ca] / n, support[cb] / n
        sab = cnt / n
        if sa == 0 or sb == 0 or sab == 0:
            continue
        conf_ab = sab / sa
        conf_ba = sab / sb
        lift = sab / (sa * sb)
        rules.append(
            {
                "前项": ca,
                "后项": cb,
                "支持度": sab,
                "置信度_A→B": conf_ab,
                "置信度_B→A": conf_ba,
                "提升度": lift,
                "共现次数": cnt,
            }
        )
        rules.append(
            {
                "前项": cb,
                "后项": ca,
                "支持度": sab,
                "置信度_A→B": conf_ba,
                "置信度_B→A": conf_ab,
                "提升度": lift,
                "共现次数": cnt,
            }
        )
    rdf = pd.DataFrame(rules).sort_values("提升度", ascending=False)
    rdf.to_csv(TAB / "q1_association_rules.csv", index=False, encoding="utf-8-sig")

    # lift heatmap
    lift_mat = pd.DataFrame(1.0, index=cats, columns=cats)
    for _, r in rdf.iterrows():
        lift_mat.loc[r["前项"], r["后项"]] = r["提升度"]
    setup_plot_style()
    fig, ax = plt.subplots(figsize=(7.5, 6))
    sns.heatmap(lift_mat, annot=True, fmt=".2f", cmap="YlOrRd", ax=ax)
    ax.set_title("品类共现提升度（Lift）热力图")
    fig.tight_layout()
    fig.savefig(FIG / "q1_association_lift.png")
    plt.close()

    # top SKU pairs by co-occurrence (sample recent year for speed)
    log("SKU co-occurrence (recent year sample)...")
    b2 = basket[basket["销售日期"] >= "2022-07-01"].copy()
    b2["小票"] = b2["销售日期"].astype(str) + "_" + b2["时刻"].str[:5]
    # top 40 SKUs by sales frequency
    top_sku = b2["单品编码"].value_counts().head(40).index.tolist()
    b2 = b2[b2["单品编码"].isin(top_sku)]
    tickets2 = b2.groupby("小票")["单品编码"].apply(lambda s: sorted(set(s)))
    tickets2 = tickets2[tickets2.map(len) >= 2]
    if len(tickets2) > 30000:
        tickets2 = tickets2.sample(30000, random_state=42)
    from collections import Counter

    pair_cnt = Counter()
    for items in tickets2:
        items = [x for x in items if x in top_sku]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                pair_cnt[(items[i], items[j])] += 1
    name_map = products.set_index("单品编码")["单品名称"].to_dict()
    cat_map = products.set_index("单品编码")["分类名称"].to_dict()
    top_pairs = []
    for (a, b_), c in pair_cnt.most_common(20):
        top_pairs.append(
            {
                "单品A": name_map.get(a, a),
                "单品B": name_map.get(b_, b_),
                "品类A": cat_map.get(a, ""),
                "品类B": cat_map.get(b_, ""),
                "共现次数": c,
            }
        )
    pd.DataFrame(top_pairs).to_csv(TAB / "q1_sku_copurchase_top20.csv", index=False, encoding="utf-8-sig")

    # bar of top lift rules
    top = rdf.drop_duplicates(["前项", "后项"]).head(12)
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = [f"{r.前项}→{r.后项}" for r in top.itertuples()]
    ax.barh(labels[::-1], top["提升度"].values[::-1], color="#F58518")
    ax.set_xlabel("提升度 Lift")
    ax.set_title("品类关联规则 Top（按提升度）")
    fig.tight_layout()
    fig.savefig(FIG / "q1_top_lift_rules.png")
    plt.close()
    return rdf


def sku_clustering(daily_sku: pd.DataFrame, products: pd.DataFrame):
    """Cluster SKUs by sales features (baseline: kmeans)."""
    # last year features
    sub = daily_sku[daily_sku["销售日期"] >= "2022-07-01"]
    feat = (
        sub.groupby("单品编码")
        .agg(
            日均销量=("销量", "mean"),
            销量波动=("销量", "std"),
            日均价=("均价", "mean"),
            活跃天数=("销售日期", "nunique"),
            平均加成=("加成率", "mean"),
        )
        .fillna(0)
    )
    feat = feat[feat["活跃天数"] >= 30]
    X = StandardScaler().fit_transform(feat.values)
    best_k, best_score = 3, -1
    for k in range(3, 7):
        lab = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(X)
        sc = silhouette_score(X, lab)
        if sc > best_score:
            best_k, best_score = k, sc
    labels = KMeans(n_clusters=best_k, random_state=42, n_init=10).fit_predict(X)
    feat = feat.reset_index()
    feat["聚类"] = labels
    feat = feat.merge(products[["单品编码", "单品名称", "分类名称"]], on="单品编码", how="left")
    feat.to_csv(TAB / "q1_sku_clusters.csv", index=False, encoding="utf-8-sig")

    setup_plot_style()
    fig, ax = plt.subplots(figsize=(8, 6))
    for c in sorted(feat["聚类"].unique()):
        s = feat[feat["聚类"] == c]
        ax.scatter(s["日均销量"], s["日均价"], s=20, alpha=0.7, label=f"簇{c}")
    ax.set_xlabel("日均销量/kg")
    ax.set_ylabel("日均价(元/kg)")
    ax.set_title(f"单品销售特征聚类 (K={best_k}, silhouette={best_score:.3f})")
    ax.legend()
    ax.set_xscale("log")
    fig.savefig(FIG / "q1_sku_clusters.png")
    plt.close()
    return best_k, best_score


def main():
    log("=== Q1 Association ===")
    daily_cat = pd.read_pickle(PROC / "daily_cat.pkl")
    daily_sku = pd.read_pickle(PROC / "daily_sku.pkl")
    products = pd.read_pickle(PROC / "products.pkl")
    basket = pd.read_pickle(PROC / "basket_raw.pkl")

    pivot, pearson, spearman = category_correlation(daily_cat)
    dist_df = distribution_fit(daily_cat)
    rules = association_rules(basket, products)
    k, sil = sku_clustering(daily_sku, products)

    # baseline: simple pearson vs spearman consistency
    upper = np.triu_indices(len(CATEGORIES), 1)
    p_vals = pearson.values[upper]
    s_vals = spearman.values[upper]
    consist = float(np.corrcoef(p_vals, s_vals)[0, 1])

    save_json(
        {
            "best_cluster_k": int(k),
            "silhouette": float(sil),
            "pearson_spearman_consistency": consist,
            "top_lift": rules.head(5).to_dict(orient="records"),
            "max_pearson_pair": {
                "pair": [
                    pearson.stack().drop_duplicates().sort_values(ascending=False).index[1][0],
                    pearson.stack().drop_duplicates().sort_values(ascending=False).index[1][1],
                ],
                "value": float(pearson.stack().drop_duplicates().sort_values(ascending=False).iloc[1]),
            },
        },
        TAB / "q1_summary.json",
    )

    # max off-diagonal pearson
    pm = pearson.copy()
    arr = pm.values.copy()
    np.fill_diagonal(arr, np.nan)
    pm = pd.DataFrame(arr, index=pm.index, columns=pm.columns)
    max_pair = pm.stack().idxmax()
    max_val = pm.stack().max()
    min_pair = pm.stack().idxmin()
    min_val = pm.stack().min()

    top_rule = rules.iloc[0]

    append_summary("\n## 问题1 分布与关联\n")
    append_summary(
        f"- 品类日销量最强正相关：**{max_pair[0]}–{max_pair[1]}**，Pearson=**{max_val:.3f}**；"
        f"最弱/负相关：**{min_pair[0]}–{min_pair[1]}**，Pearson=**{min_val:.3f}**。\n"
    )
    append_summary(
        f"- Pearson 与 Spearman 上三角一致性相关系数 **{consist:.3f}**（稳健性）。\n"
    )
    append_summary(
        f"- 关联规则最高提升度：**{top_rule['前项']}→{top_rule['后项']}**，"
        f"Lift=**{top_rule['提升度']:.3f}**，支持度=**{top_rule['支持度']:.4f}**。\n"
    )
    append_summary(
        f"- 单品聚类最优 K=**{k}**，轮廓系数=**{sil:.3f}**（对照基线：单簇无效）。\n"
    )
    for _, r in dist_df.iterrows():
        append_summary(
            f"- **{r['品类']}** 日销量偏度 **{r['偏度']:.2f}**，最优拟合 **{r['最优分布']}**"
            f"（KS={r['KS统计量']:.3f}）。\n"
        )
    log("Q1 done.")


if __name__ == "__main__":
    main()
