# -*- coding: utf-8 -*-
"""Q3: SKU-level assortment, replenishment and pricing for 2023-07-01."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pulp
import seaborn as sns

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


MIN_DISPLAY = 2.5
N_MIN, N_MAX = 27, 33


def candidate_skus(daily_sku, products, loss_sku):
    """SKUs sold during 2023-06-24..30 as available assortment."""
    start, end = pd.Timestamp("2023-06-24"), pd.Timestamp("2023-06-30")
    recent = daily_sku[(daily_sku["销售日期"] >= start) & (daily_sku["销售日期"] <= end)].copy()
    avail = recent["单品编码"].unique().tolist()

    # features from longer window for demand/price
    hist = daily_sku[
        (daily_sku["销售日期"] >= "2023-05-01") & (daily_sku["销售日期"] <= end) & (daily_sku["单品编码"].isin(avail))
    ]
    feat = (
        hist.groupby("单品编码")
        .agg(
            日均销量=("销量", "mean"),
            销量中位数=("销量", "median"),
            均价=("均价", "mean"),
            批发价=("批发价", "median"),
            加成率=("加成率", "median"),
            活跃天=("销售日期", "nunique"),
            总销量=("销量", "sum"),
            毛利合计=("毛利", "sum"),
        )
        .reset_index()
    )
    feat = feat.merge(products[["单品编码", "单品名称", "分类名称"]], on="单品编码", how="left")
    feat = feat.merge(loss_sku[["单品编码", "损耗率(%)"]], on="单品编码", how="left")
    feat["损耗率"] = feat["损耗率(%)"].fillna(feat.groupby("分类名称")["损耗率(%)"].transform("mean")) / 100.0
    feat["损耗率"] = feat["损耗率"].fillna(0.10)
    # fill wholesale
    feat["批发价"] = feat["批发价"].fillna(feat["均价"] / (1 + feat["加成率"].fillna(0.4)))
    feat["批发价"] = feat["批发价"].fillna(feat["均价"] * 0.7)
    feat = feat.dropna(subset=["均价", "批发价", "分类名称"])
    feat = feat[feat["批发价"] > 0]
    feat.to_csv(TAB / "q3_candidate_skus.csv", index=False, encoding="utf-8-sig")
    return feat


def estimate_sku_elasticity(daily_sku, codes):
    """Per-SKU simple log elasticity; fallback to category median."""
    sub = daily_sku[
        (daily_sku["单品编码"].isin(codes))
        & (daily_sku["销售日期"] >= "2022-07-01")
        & (daily_sku["均价"] > 0)
        & (daily_sku["销量"] > 0)
    ]
    elast = {}
    for code, g in sub.groupby("单品编码"):
        if len(g) < 20:
            continue
        x = np.log(g["均价"].values)
        y = np.log(g["销量"].values)
        if np.std(x) < 1e-6:
            continue
        beta = np.polyfit(x, y, 1)[0]
        # clamp
        elast[code] = float(np.clip(beta, -3.0, -0.05))
    return elast


def optimize_assortment(feat, cat_demand, elast_map, cat_elast):
    """Two-stage: (1) score SKUs (2) ILP select 27-33 with min display & category coverage.

    Unit profit proxy at optimal markup grid, with demand Q = Q0*(P/P0)^e
    replenish R = max(MIN_DISPLAY, Q/(1-loss))
    """
    records = []
    for _, r in feat.iterrows():
        code = r["单品编码"]
        C = float(r["批发价"])
        P0 = float(r["均价"])
        Q0 = float(max(r["销量中位数"], r["日均销量"], 0.5))
        loss = float(r["损耗率"])
        e = elast_map.get(code, cat_elast.get(r["分类名称"], -0.8))
        best = None
        for markup in np.linspace(0.1, 1.2, 23):
            P = C * (1 + markup)
            Qd = Q0 * ((P / P0) ** e)
            Qd = max(Qd, 0.1)
            R = max(MIN_DISPLAY, Qd / max(1 - loss, 0.05))
            # if R forced by min display exceeds demand capacity, sales=min
            sales = min(Qd, R * (1 - loss))
            profit = P * sales - C * R
            if best is None or profit > best["单品收益"]:
                best = {
                    "单品编码": code,
                    "单品名称": r["单品名称"],
                    "分类名称": r["分类名称"],
                    "批发价": C,
                    "建议售价": P,
                    "加成率": markup,
                    "弹性": e,
                    "预测需求": Qd,
                    "补货量": R,
                    "损耗率": loss,
                    "预期销量": sales,
                    "单品收益": profit,
                    "历史日均销量": Q0,
                }
        records.append(best)
    scored = pd.DataFrame(records)
    scored.to_csv(TAB / "q3_sku_scored.csv", index=False, encoding="utf-8-sig")

    # ILP
    skus = scored["单品编码"].tolist()
    profit = scored.set_index("单品编码")["单品收益"].to_dict()
    qty = scored.set_index("单品编码")["补货量"].to_dict()
    cat_of = scored.set_index("单品编码")["分类名称"].to_dict()
    demand_share = scored.set_index("单品编码")["预测需求"].to_dict()

    # category demand targets from Q2 Jul1 or hist
    # soft penalty via secondary objective: maximize covered demand closeness
    prob = pulp.LpProblem("sku_assortment", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("sel", skus, cat="Binary")
    # objective: profit + lambda * category coverage score
    # coverage: sum selected demand per cat, reward min(sum, target)
    cat_cover = {}
    for cat in CATEGORIES:
        cat_skus = [s for s in skus if cat_of[s] == cat]
        cat_cover[cat] = pulp.lpSum([demand_share[s] * x[s] for s in cat_skus])

    # use auxiliary vars for min(cover, target)
    lamb = 0.15  # weight on unmet demand penalty (yuan per kg unmet approx via avg margin)
    unmet = pulp.LpVariable.dicts("unmet", CATEGORIES, lowBound=0)
    avg_margin = float(np.median([profit[s] / max(qty[s], 1e-6) for s in skus]))
    prob += pulp.lpSum([profit[s] * x[s] for s in skus]) - lamb * avg_margin * pulp.lpSum(
        [unmet[c] for c in CATEGORIES]
    )

    for cat in CATEGORIES:
        target = float(cat_demand.get(cat, 0))
        # unmet >= target - cover
        prob += unmet[cat] >= target - cat_cover[cat]

    prob += pulp.lpSum([x[s] for s in skus]) >= N_MIN
    prob += pulp.lpSum([x[s] for s in skus]) <= N_MAX

    # diversity: each category at least 1 if candidates exist
    for cat in CATEGORIES:
        cat_skus = [s for s in skus if cat_of[s] == cat]
        if cat_skus:
            prob += pulp.lpSum([x[s] for s in cat_skus]) >= 1

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=60))
    selected = [s for s in skus if x[s].value() > 0.5]
    plan = scored[scored["单品编码"].isin(selected)].copy()
    plan = plan.sort_values(["分类名称", "单品收益"], ascending=[True, False])
    plan.to_csv(TAB / "q3_july1_plan.csv", index=False, encoding="utf-8-sig")

    # baselines
    # A: top profit SKUs without category constraints (greedy top 30)
    greedy = scored.nlargest(30, "单品收益")
    # B: top sales volume 30
    vol = scored.nlargest(30, "历史日均销量")
    # C: random 30 seed
    rng = scored.sample(n=min(30, len(scored)), random_state=42)

    def summarize(df, name):
        return {
            "方案": name,
            "单品数": len(df),
            "总补货量": float(df["补货量"].sum()),
            "总预期销量": float(df["预期销量"].sum()),
            "总收益": float(df["单品收益"].sum()),
            "品类覆盖数": int(df["分类名称"].nunique()),
        }

    cmp = pd.DataFrame(
        [
            summarize(plan, "ILP优化(主模型)"),
            summarize(greedy, "贪心Top收益(基线)"),
            summarize(vol, "贪心Top销量(基线)"),
            summarize(rng, "随机30(基线)"),
        ]
    )
    cmp.to_csv(TAB / "q3_method_compare.csv", index=False, encoding="utf-8-sig")

    cat_cov = (
        plan.groupby("分类名称")
        .agg(单品数=("单品编码", "count"), 补货量=("补货量", "sum"), 预期销量=("预期销量", "sum"), 收益=("单品收益", "sum"))
        .reindex(CATEGORIES)
        .reset_index()
    )
    cat_cov["需求目标"] = cat_cov["分类名称"].map(cat_demand)
    cat_cov["需求满足率"] = cat_cov["预期销量"] / cat_cov["需求目标"]
    cat_cov.to_csv(TAB / "q3_category_coverage.csv", index=False, encoding="utf-8-sig")

    return plan, cmp, cat_cov, pulp.LpStatus[status]


def plots(plan, cmp, cat_cov, scored):
    setup_plot_style()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=cmp, x="方案", y="总收益", ax=ax, palette="muted")
    ax.set_title("单品补货方案收益对比")
    ax.set_ylabel("预期收益/元")
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    fig.savefig(FIG / "q3_method_compare.png")
    plt.close()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=cat_cov, x="分类名称", y="补货量", ax=ax, color="#4C78A8", label="补货")
    ax2 = ax.twinx()
    ax2.plot(range(len(cat_cov)), cat_cov["需求满足率"], "ro-", label="满足率")
    ax.set_title("7月1日各品类补货量与需求满足率")
    ax.set_ylabel("补货量/kg")
    ax2.set_ylabel("需求满足率")
    fig.tight_layout()
    fig.savefig(FIG / "q3_category_coverage.png")
    plt.close()

    fig, ax = plt.subplots(figsize=(10, 6))
    top = plan.sort_values("单品收益", ascending=False)
    ax.barh(top["单品名称"], top["补货量"], color="#72B7B2")
    ax.set_xlabel("补货量/kg")
    ax.set_title(f"7月1日入选单品补货量（共{len(plan)}个）")
    fig.tight_layout()
    fig.savefig(FIG / "q3_sku_replenish.png")
    plt.close()

    fig, ax = plt.subplots(figsize=(8, 5))
    for cat in CATEGORIES:
        s = plan[plan["分类名称"] == cat]
        ax.scatter(s["建议售价"], s["补货量"], s=40, label=cat, alpha=0.8)
    ax.set_xlabel("建议售价")
    ax.set_ylabel("补货量")
    ax.set_title("入选单品：价格—补货散点")
    ax.legend(fontsize=8, ncol=2)
    fig.savefig(FIG / "q3_price_qty_selected.png")
    plt.close()


def main():
    log("=== Q3 SKU Optimization ===")
    daily_sku = pd.read_pickle(PROC / "daily_sku.pkl")
    products = pd.read_pickle(PROC / "products.pkl")
    loss_sku = pd.read_pickle(PROC / "loss_sku.pkl")
    daily_cat = pd.read_pickle(PROC / "daily_cat.pkl")

    feat = candidate_skus(daily_sku, products, loss_sku)
    log(f"Candidates: {len(feat)}")

    elast_map = estimate_sku_elasticity(daily_sku, feat["单品编码"].tolist())
    # category elast from q2 table if exists
    try:
        e_df = pd.read_csv(TAB / "q2_elasticity.csv")
        cat_elast = dict(zip(e_df["品类"], e_df["价格弹性"]))
    except Exception:
        cat_elast = {c: -0.8 for c in CATEGORIES}

    # category demand target: Q2 plan for Jul1 if available else hist median
    try:
        q2 = pd.read_csv(TAB / "q2_week_plan.csv", parse_dates=["日期"])
        d1 = q2[q2["日期"] == "2023-07-01"]
        cat_demand = dict(zip(d1["品类"], d1["预测需求"]))
    except Exception:
        cat_demand = {}
        for cat in CATEGORIES:
            sub = daily_cat[
                (daily_cat["分类名称"] == cat)
                & (daily_cat["销售日期"] >= "2023-05-01")
                & (daily_cat["星期"] == 5)  # Jul1 2023 is Saturday
            ]
            cat_demand[cat] = float(sub["销量"].median()) if len(sub) else 50.0

    plan, cmp, cat_cov, status = optimize_assortment(feat, cat_demand, elast_map, cat_elast)
    plots(plan, cmp, cat_cov, feat)

    total_profit = float(plan["单品收益"].sum())
    n_sku = len(plan)
    base_profit = float(cmp.loc[cmp["方案"] == "贪心Top收益(基线)", "总收益"].values[0])
    lift = (total_profit - base_profit) / abs(base_profit) if base_profit else np.nan

    save_json(
        {
            "status": status,
            "n_sku": n_sku,
            "total_profit": total_profit,
            "total_replenish": float(plan["补货量"].sum()),
            "lift_vs_greedy": lift,
            "min_display": MIN_DISPLAY,
            "n_range": [N_MIN, N_MAX],
            "category_fill_rates": cat_cov[["分类名称", "需求满足率"]].to_dict(orient="records"),
        },
        TAB / "q3_summary.json",
    )

    append_summary("\n## 问题3 单品补货与定价（2023-07-01）\n")
    append_summary(
        f"- 求解状态 **{status}**；入选单品 **{n_sku}** 个（约束27–33），"
        f"均满足最小陈列量 **{MIN_DISPLAY} kg**。\n"
    )
    append_summary(
        f"- 预期总收益 **{total_profit:.2f} 元**，总补货 **{plan['补货量'].sum():.2f} kg**；"
        f"相对贪心Top收益基线提升 **{lift:.2%}**。\n"
    )
    append_summary("- 口径：可售单品来自2023-06-24~30；需求按SKU弹性标定；ILP兼顾收益与品类需求缺口。\n")
    for _, r in cat_cov.iterrows():
        fr = r["需求满足率"]
        fr_s = f"{fr:.2%}" if pd.notna(fr) else "NA"
        append_summary(
            f"- **{r['分类名称']}**：{int(r['单品数']) if pd.notna(r['单品数']) else 0} 个单品，"
            f"补货 **{r['补货量']:.1f} kg**，需求满足率 **{fr_s}**。\n"
        )
    log("Q3 done.")


if __name__ == "__main__":
    main()
