# -*- coding: utf-8 -*-
"""Advanced tests: sensitivity, robustness, ablation, tech roadmap."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
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


def tech_roadmap():
    setup_plot_style()
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis("off")
    ax.set_title("技术路线图：评价—关联—预测—优化—分配—检验", fontsize=14, pad=12)

    boxes = [
        (0.3, 5.2, 2.2, 1.2, "数据清洗\nEDA/分布", "#BDD7EE"),
        (3.0, 5.2, 2.2, 1.2, "Q1 关联分析\n相关+Lift+聚类", "#C6EFCE"),
        (5.7, 5.2, 2.2, 1.2, "需求-价格\n弹性建模", "#FFEB9C"),
        (8.4, 5.2, 2.8, 1.2, "成本/季节\n预测", "#F8CBAD"),
        (0.3, 2.8, 2.8, 1.4, "Q2 品类优化\n加成率网格搜索", "#C6EFCE"),
        (3.5, 2.8, 2.8, 1.4, "Q3 单品ILP\n27-33+陈列约束", "#FFEB9C"),
        (6.7, 2.8, 2.4, 1.4, "基线对照\n消融实验", "#BDD7EE"),
        (9.3, 2.8, 2.4, 1.4, "灵敏度/\n鲁棒性检验", "#F8CBAD"),
        (3.5, 0.6, 5.0, 1.2, "Q4 数据补采建议 + 决策闭环", "#D9D9D9"),
    ]
    for x, y, w, h, t, c in boxes:
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03",
                                            facecolor=c, edgecolor="#333", lw=1.2))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=10)

    arrows = [
        ((2.5, 5.8), (3.0, 5.8)),
        ((5.2, 5.8), (5.7, 5.8)),
        ((7.9, 5.8), (8.4, 5.8)),
        ((6.8, 5.2), (4.9, 4.2)),
        ((9.8, 5.2), (8.0, 4.2)),
        ((1.7, 5.2), (1.7, 4.2)),
        ((4.9, 2.8), (4.9, 1.8)),
        ((7.9, 2.8), (6.5, 1.8)),
    ]
    for (x1, y1), (x2, y2) in arrows:
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#444", lw=1.4))
    fig.tight_layout()
    fig.savefig(FIG / "tech_roadmap.png")
    plt.close()


def sensitivity_q2():
    """Sensitivity of week profit to loss rate and elasticity scaling."""
    plan = pd.read_csv(TAB / "q2_week_plan.csv", parse_dates=["日期"])
    elast = pd.read_csv(TAB / "q2_elasticity.csv")
    e_map = dict(zip(elast["品类"], elast["价格弹性"]))

    # analytical local sensitivity around optimum using stored curve
    curve = pd.read_csv(TAB / "q2_profit_markup_curve.csv", parse_dates=["日期"])

    loss_scales = np.linspace(0.7, 1.3, 13)
    rows = []
    base_loss = plan.groupby("品类")["损耗率"].mean().to_dict()
    for scale in loss_scales:
        total = 0.0
        for _, r in plan.iterrows():
            # recompute profit with scaled loss, keep price/demand, adjust R
            loss = float(np.clip(r["损耗率"] * scale, 0.01, 0.6))
            Qd = r["预测需求"]
            P, C = r["售价"], r["批发价"]
            R = Qd / (1 - loss)
            profit = P * Qd - C * R
            total += profit
        rows.append({"损耗率缩放": scale, "周收益": total})
    sens_loss = pd.DataFrame(rows)
    sens_loss.to_csv(TAB / "sens_loss_scale.csv", index=False, encoding="utf-8-sig")

    # markup perturbation around optimum
    markup_delta = np.linspace(-0.2, 0.2, 17)
    rows2 = []
    for dlt in markup_delta:
        total = 0.0
        for cat in CATEGORIES:
            sub = curve[curve["品类"] == cat]
            # use Jul1 curve shape scaled to week approx: 7 * day
            d1 = sub[sub["日期"] == "2023-07-01"]
            if d1.empty:
                continue
            opt_m = float(plan[(plan["品类"] == cat) & (plan["日期"] == "2023-07-01")]["加成率"].iloc[0])
            target_m = np.clip(opt_m + dlt, 0.05, 1.5)
            # nearest
            idx = (d1["加成率"] - target_m).abs().idxmin()
            day_profit = float(d1.loc[idx, "收益"])
            total += day_profit * 7  # approx
        rows2.append({"加成率偏离": dlt, "近似周收益": total})
    sens_m = pd.DataFrame(rows2)
    sens_m.to_csv(TAB / "sens_markup_delta.csv", index=False, encoding="utf-8-sig")

    # elasticity scale
    rows3 = []
    for scale in np.linspace(0.6, 1.4, 9):
        # approximate: demand multiplier (P/P_hist)^(e*(scale-1)) relative to base
        total = 0.0
        for _, r in plan.iterrows():
            e = e_map.get(r["品类"], -0.8) * scale
            e0 = e_map.get(r["品类"], -0.8)
            # adjust demand relative to model demand at same price
            # Q_new / Q_old ≈ (P/C)^(e-e0) roughly using cost as ref — use hist price proxy
            P, C, Q = r["售价"], r["批发价"], r["预测需求"]
            ratio = (P / C) ** (e - e0)
            Qn = Q * ratio
            loss = r["损耗率"]
            Rn = Qn / (1 - loss)
            total += P * Qn - C * Rn
        rows3.append({"弹性缩放": scale, "周收益": total})
    sens_e = pd.DataFrame(rows3)
    sens_e.to_csv(TAB / "sens_elasticity_scale.csv", index=False, encoding="utf-8-sig")

    setup_plot_style()
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    axes[0].plot(sens_loss["损耗率缩放"], sens_loss["周收益"], "o-", color="#4C78A8")
    axes[0].set_title("损耗率缩放灵敏度")
    axes[0].set_xlabel("损耗率 × scale")
    axes[0].set_ylabel("周收益/元")
    axes[1].plot(sens_m["加成率偏离"], sens_m["近似周收益"], "o-", color="#F58518")
    axes[1].set_title("加成率偏离灵敏度")
    axes[1].set_xlabel("相对最优偏离")
    axes[2].plot(sens_e["弹性缩放"], sens_e["周收益"], "o-", color="#54A24B")
    axes[2].set_title("价格弹性缩放灵敏度")
    axes[2].set_xlabel("弹性 × scale")
    fig.tight_layout()
    fig.savefig(FIG / "sens_q2_three_params.png")
    plt.close()
    return sens_loss, sens_m, sens_e


def robustness_monte_carlo(n=200):
    """Perturb demand & cost with noise; evaluate Q2 plan stability."""
    plan = pd.read_csv(TAB / "q2_week_plan.csv", parse_dates=["日期"])
    rng = np.random.default_rng(42)
    profits = []
    for i in range(n):
        # multiplicative noise
        q_noise = rng.lognormal(0, 0.12, len(plan))
        c_noise = rng.lognormal(0, 0.08, len(plan))
        Q = plan["预测需求"].values * q_noise
        C = plan["批发价"].values * c_noise
        P = plan["售价"].values  # fixed pricing decision
        loss = plan["损耗率"].values
        R = Q / np.maximum(1 - loss, 0.05)
        profit = (P * Q - C * R).sum()
        profits.append(profit)
    profits = np.array(profits)
    base = float(plan["预期收益"].sum())
    summary = {
        "mc_n": n,
        "base_profit": base,
        "mc_mean": float(profits.mean()),
        "mc_std": float(profits.std()),
        "mc_p05": float(np.percentile(profits, 5)),
        "mc_p95": float(np.percentile(profits, 95)),
        "prob_above_95pct_base": float((profits >= 0.95 * base).mean()),
    }
    pd.DataFrame({"mc_profit": profits}).to_csv(TAB / "robust_mc_profits.csv", index=False)
    save_json(summary, TAB / "robust_mc_summary.json")

    setup_plot_style()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(profits, bins=30, color="#72B7B2", edgecolor="white")
    ax.axvline(base, color="r", ls="--", label=f"基线方案 {base:.0f}")
    ax.axvline(summary["mc_p05"], color="orange", ls=":", label="5%分位")
    ax.axvline(summary["mc_p95"], color="orange", ls=":", label="95%分位")
    ax.set_title("需求/成本扰动下的周收益鲁棒性（蒙特卡洛）")
    ax.set_xlabel("周收益/元")
    ax.legend()
    fig.savefig(FIG / "robust_mc_profit_hist.png")
    plt.close()

    # Q3 robustness: drop top SKU / noise on scores
    try:
        plan3 = pd.read_csv(TAB / "q3_july1_plan.csv")
        scored = pd.read_csv(TAB / "q3_sku_scored.csv")
        base3 = float(plan3["单品收益"].sum())
        sims = []
        for i in range(n):
            noise = rng.lognormal(0, 0.15, len(scored))
            tmp = scored.copy()
            tmp["扰后收益"] = tmp["单品收益"] * noise
            # re-pick top with category diversity heuristic: top by noisy profit with caps
            picked = []
            for cat in CATEGORIES:
                sub = tmp[tmp["分类名称"] == cat].nlargest(3, "扰后收益")
                picked.append(sub)
            rest = tmp[~tmp["单品编码"].isin(pd.concat(picked)["单品编码"])].nlargest(
                max(0, 30 - sum(len(p) for p in picked)), "扰后收益"
            )
            sel = pd.concat(picked + [rest]).head(30)
            sims.append(float(sel["单品收益"].sum()))  # evaluate true profit of noisy selection
        sims = np.array(sims)
        q3sum = {
            "base_profit": base3,
            "noisy_select_mean": float(sims.mean()),
            "noisy_select_std": float(sims.std()),
            "retention_ratio_mean": float(sims.mean() / base3) if base3 else np.nan,
        }
        save_json(q3sum, TAB / "robust_q3_summary.json")
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.hist(sims, bins=30, color="#E45756", edgecolor="white", alpha=0.85)
        ax.axvline(base3, color="k", ls="--", label=f"ILP方案 {base3:.0f}")
        ax.set_title("单品收益噪声下重选组合的收益分布")
        ax.legend()
        fig.savefig(FIG / "robust_q3_reselect_hist.png")
        plt.close()
    except Exception as e:
        log(f"Q3 robust skip: {e}")
        q3sum = {}
    return summary, q3sum


def ablation_and_compare():
    """Ablation-style comparison tables from existing results."""
    q2 = pd.read_json(TAB / "q2_summary.json", typ="series")
    rows = [
        {"模块": "Q2定价", "方案": "最优加成(主模型)", "指标": "周收益", "数值": q2["week_total_profit"]},
        {"模块": "Q2定价", "方案": "历史加成(消融)", "指标": "周收益", "数值": q2["baseline_hist_profit"]},
        {"模块": "Q2定价", "方案": "固定30%(消融)", "指标": "周收益", "数值": q2["baseline_fixed30_profit"]},
    ]
    q3 = pd.read_csv(TAB / "q3_method_compare.csv")
    for _, r in q3.iterrows():
        rows.append({"模块": "Q3选品", "方案": r["方案"], "指标": "日收益", "数值": r["总收益"]})
    ab = pd.DataFrame(rows)
    ab.to_csv(TAB / "ablation_summary.csv", index=False, encoding="utf-8-sig")

    setup_plot_style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    q2df = ab[ab["模块"] == "Q2定价"]
    axes[0].bar(q2df["方案"], q2df["数值"], color=["#54A24B", "#B8B8B8", "#B8B8B8"])
    axes[0].set_title("Q2 消融：定价策略")
    axes[0].tick_params(axis="x", rotation=20)
    axes[0].set_ylabel("周收益/元")
    q3df = ab[ab["模块"] == "Q3选品"]
    axes[1].bar(q3df["方案"], q3df["数值"], color=["#54A24B"] + ["#B8B8B8"] * (len(q3df) - 1))
    axes[1].set_title("Q3 消融：选品策略")
    axes[1].tick_params(axis="x", rotation=20)
    axes[1].set_ylabel("日收益/元")
    fig.tight_layout()
    fig.savefig(FIG / "ablation_compare.png")
    plt.close()
    return ab


def residual_check():
    """Demand model residual diagnostics for Q2."""
    daily_cat = pd.read_pickle(PROC / "daily_cat.pkl")
    elast = pd.read_csv(TAB / "q2_elasticity.csv")
    # simple residual using log-linear without reloading model: use historical markup relationship
    setup_plot_style()
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    rows = []
    for i, cat in enumerate(CATEGORIES):
        sub = daily_cat[(daily_cat["分类名称"] == cat) & (daily_cat["销售日期"] >= "2022-07-01")].dropna()
        sub = sub[(sub["均价"] > 0) & (sub["销量"] > 0)]
        # fit quick
        X = np.column_stack([np.log(sub["均价"]), np.log(sub["批发均价"].clip(lower=0.01)),
                             pd.get_dummies(sub["星期"], drop_first=True).values])
        y = np.log(sub["销量"].values)
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        pred = X @ beta
        resid = y - pred
        axes.ravel()[i].scatter(pred, resid, s=8, alpha=0.35)
        axes.ravel()[i].axhline(0, color="r", ls="--")
        axes.ravel()[i].set_title(cat)
        axes.ravel()[i].set_xlabel("拟合lnQ")
        axes.ravel()[i].set_ylabel("残差")
        rows.append({"品类": cat, "残差均值": float(resid.mean()), "残差标准差": float(resid.std()),
                     "残差偏度": float(pd.Series(resid).skew())})
    fig.suptitle("需求模型残差诊断")
    fig.tight_layout()
    fig.savefig(FIG / "q2_residual_diagnostics.png")
    plt.close()
    pd.DataFrame(rows).to_csv(TAB / "q2_residual_stats.csv", index=False, encoding="utf-8-sig")


def main():
    log("=== Advanced tests ===")
    tech_roadmap()
    residual_check()
    sens_loss, sens_m, sens_e = sensitivity_q2()
    mc, q3r = robustness_monte_carlo(200)
    ab = ablation_and_compare()

    append_summary("\n## 高级检验（灵敏度/鲁棒/消融）\n")
    append_summary(
        f"- 蒙特卡洛(n={mc['mc_n']})：周收益均值 **{mc['mc_mean']:.2f}**，"
        f"标准差 **{mc['mc_std']:.2f}**，"
        f"5%–95%分位 **[{mc['mc_p05']:.2f}, {mc['mc_p95']:.2f}]**，"
        f"不低于基线95%的概率 **{mc['prob_above_95pct_base']:.2%}**。\n"
    )
    append_summary(
        f"- 损耗率缩放[0.7,1.3]时周收益范围 "
        f"**[{sens_loss['周收益'].min():.2f}, {sens_loss['周收益'].max():.2f}]**。\n"
    )
    if q3r:
        append_summary(
            f"- Q3噪声重选：均值收益 **{q3r['noisy_select_mean']:.2f}**，"
            f"相对ILP保留比 **{q3r['retention_ratio_mean']:.2%}**。\n"
        )
    # innovation file
    innov = """# 创新点（可验证）

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
"""
    with open(Path(__file__).resolve().parents[1] / "output" / "00_innovation.md", "w", encoding="utf-8") as f:
        f.write(innov)
    log("Advanced tests done.")


if __name__ == "__main__":
    main()
