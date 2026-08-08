"""Advanced analyses for national-award level paper: multi-method comparison,
robustness (Monte Carlo), sensitivity, flowchart, and richer tables/figures."""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from config import FIG_DIR, TABLE_DIR, TOP_K_Q1, CONSUMPTION, WEEKLY_CAPACITY, TRANSPORT_CAP
from utils import (
    build_supplier_features,
    entropy_weights,
    ensure_dirs,
    load_supplier_data,
    load_transporter_data,
    setup_logging,
    setup_matplotlib,
    topsis_score,
)
from q1_supplier_importance import rank_suppliers, baseline_rank


def critic_weights(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    std = X.std(axis=0) + 1e-12
    corr = np.corrcoef(X.T)
    conflict = np.sum(1 - np.abs(corr), axis=1)
    info = std * conflict
    return info / info.sum()


def grey_relational(X: np.ndarray, rho: float = 0.5) -> np.ndarray:
    """Grey relational degree to ideal (max) reference."""
    X = np.asarray(X, dtype=float)
    ref = X.max(axis=0)
    Xn = (X - X.min(axis=0)) / (X.max(axis=0) - X.min(axis=0) + 1e-12)
    rn = (ref - X.min(axis=0)) / (X.max(axis=0) - X.min(axis=0) + 1e-12)
    delta = np.abs(rn - Xn)
    dmin, dmax = delta.min(), delta.max() + 1e-12
    xi = (dmin + rho * dmax) / (delta + rho * dmax)
    return xi.mean(axis=1)


def feature_matrix(features: pd.DataFrame) -> np.ndarray:
    mat_score = features["material"].map({"A": 1.0, "B": 0.95, "C": 1.0}).fillna(0.9)
    return np.column_stack(
        [
            features["total_supply"].values,
            features["mean_supply"].values,
            features["max_supply"].values,
            features["fill_rate"].values,
            features["stability"].values,
            features["active_weeks"].values,
            features["recent_supply"].values,
            mat_score.values,
        ]
    )


def multi_method_ranking(features: pd.DataFrame) -> pd.DataFrame:
    X = feature_matrix(features)
    benefit = np.ones(X.shape[1], dtype=bool)

    w_ent = entropy_weights(X)
    s_ent = topsis_score(X, w_ent, benefit)

    w_cri = critic_weights(X)
    s_cri = topsis_score(X, w_cri, benefit)

    s_grey = grey_relational(X)

    # PCA-like: first principal component scores (via SVD on standardized X)
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-12)
    _, _, Vt = np.linalg.svd(Xs, full_matrices=False)
    s_pca = Xs @ Vt[0]
    s_pca = (s_pca - s_pca.min()) / (s_pca.max() - s_pca.min() + 1e-12)

    out = features[["supplier_id", "material"]].copy()
    out["entropy_topsis"] = s_ent
    out["critic_topsis"] = s_cri
    out["grey"] = s_grey
    out["pca"] = s_pca
    # ensemble: average of ranks
    for col in ["entropy_topsis", "critic_topsis", "grey", "pca"]:
        out[f"rank_{col}"] = out[col].rank(ascending=False, method="min").astype(int)
    out["ensemble_rank"] = out[[f"rank_{c}" for c in ["entropy_topsis", "critic_topsis", "grey", "pca"]]].mean(axis=1)
    out = out.sort_values("ensemble_rank")
    return out, {"entropy": w_ent, "critic": w_cri}


def kendall_tau(r1: np.ndarray, r2: np.ndarray) -> float:
    """Simple Kendall tau for rank agreement (O(n^2))."""
    n = len(r1)
    concord = 0
    total = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += 1
            s1 = np.sign(r1[i] - r1[j])
            s2 = np.sign(r2[i] - r2[j])
            if s1 * s2 > 0:
                concord += 1
            elif s1 * s2 < 0:
                pass
            else:
                concord += 0.5
    return 2 * concord / total - 1 if total else 0.0


def monte_carlo_robustness(features: pd.DataFrame, n_sim: int = 200, seed: int = 42) -> pd.DataFrame:
    """Perturb fill_rate and stability, recompute top50 overlap with baseline TOPSIS."""
    rng = np.random.default_rng(seed)
    ranked, _ = rank_suppliers(features)
    base_top = set(ranked.head(TOP_K_Q1)["supplier_id"])
    rows = []
    for i in range(n_sim):
        f2 = features.copy()
        f2["fill_rate"] = np.clip(f2["fill_rate"] * rng.normal(1.0, 0.08, len(f2)), 0.2, 1.5)
        f2["stability"] = np.clip(f2["stability"] * rng.normal(1.0, 0.08, len(f2)), 0.05, 1.0)
        f2["mean_supply"] = np.clip(f2["mean_supply"] * rng.normal(1.0, 0.1, len(f2)), 0, None)
        r2, _ = rank_suppliers(f2)
        top = set(r2.head(TOP_K_Q1)["supplier_id"])
        rows.append({"sim": i, "overlap": len(top & base_top), "jaccard": len(top & base_top) / len(top | base_top)})
    return pd.DataFrame(rows)


def draw_flowchart():
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 7)
    ax.axis("off")
    boxes = [
        (0.5, 5.5, "数据预处理\nEDA"),
        (3.0, 5.5, "特征工程\n8维指标"),
        (5.5, 5.5, "多准则评价\n熵权/CRITIC/灰关联"),
        (8.0, 5.5, "Q1 Top50\n供应商"),
        (0.5, 3.2, "最少供应商\n集合覆盖"),
        (3.0, 3.2, "Q2 经济订购\n库存约束LP"),
        (5.5, 3.2, "损耗优先\n转运分配"),
        (8.0, 3.2, "实施效果\n分析"),
        (0.5, 0.9, "Q3 多目标\n偏A少C"),
        (3.0, 0.9, "Q4 产能上界\n双瓶颈搜索"),
        (5.5, 0.9, "灵敏度/\n鲁棒性检验"),
        (8.0, 0.9, "方案输出\n附件A/B"),
    ]
    for x, y, t in boxes:
        ax.add_patch(FancyBboxPatch((x, y), 2.0, 1.1, boxstyle="round,pad=0.05", facecolor="#E8F4FD", edgecolor="#2C3E50", lw=1.5))
        ax.text(x + 1.0, y + 0.55, t, ha="center", va="center", fontsize=9)
    # arrows row1
    for i in range(3):
        ax.annotate("", xy=(boxes[i + 1][0], 6.05), xytext=(boxes[i][0] + 2.0, 6.05),
                    arrowprops=dict(arrowstyle="->", color="#34495E", lw=1.5))
    for i in range(3):
        ax.annotate("", xy=(boxes[4 + i + 1][0], 3.75), xytext=(boxes[4 + i][0] + 2.0, 3.75),
                    arrowprops=dict(arrowstyle="->", color="#34495E", lw=1.5))
    for i in range(3):
        ax.annotate("", xy=(boxes[8 + i + 1][0], 1.45), xytext=(boxes[8 + i][0] + 2.0, 1.45),
                    arrowprops=dict(arrowstyle="->", color="#34495E", lw=1.5))
    ax.annotate("", xy=(9.0, 4.3), xytext=(9.0, 5.5), arrowprops=dict(arrowstyle="->", color="#E74C3C", lw=1.5))
    ax.set_title("整体技术路线：评价—优化—检验一体化框架", fontsize=13, pad=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "flowchart_overall.png")
    plt.close(fig)


def inventory_simulation(order_plan: pd.DataFrame, fill_noise: float = 0.1, n: int = 100, seed: int = 0) -> dict:
    """Simulate inventory under fill-rate noise; return stockout weeks stats."""
    rng = np.random.default_rng(seed)
    week_cols = [c for c in order_plan.columns if c.startswith("week_")]
    mats = order_plan["material"].values
    Q = order_plan[week_cols].values  # (n_s, 24)
    fill_base = np.ones(len(order_plan))  # approximate; use 1.0 if no fill in plan
    # use mean fill from features if available via material-agnostic 1.0
    stockouts = []
    min_inv = []
    for _ in range(n):
        I = 2 * WEEKLY_CAPACITY
        so = 0
        miv = I
        for t in range(24):
            recv = 0.0
            for i, m in enumerate(mats):
                eta = max(0.3, rng.normal(1.0, fill_noise))
                recv += Q[i, t] * eta / CONSUMPTION[m]
            I = I + recv - WEEKLY_CAPACITY
            miv = min(miv, I)
            if I < 2 * WEEKLY_CAPACITY - 1e-6:
                so += 1
                I = max(I, 0)
        stockouts.append(so)
        min_inv.append(miv)
    return {
        "mean_stockout_weeks": float(np.mean(stockouts)),
        "p95_stockout_weeks": float(np.percentile(stockouts, 95)),
        "mean_min_inventory": float(np.mean(min_inv)),
        "prob_any_stockout": float(np.mean(np.array(stockouts) > 0)),
    }


def main():
    ensure_dirs()
    logger = setup_logging("05_advanced_analysis")
    setup_matplotlib()
    orders, supplies = load_supplier_data()
    features = build_supplier_features(orders, supplies)
    ranked, w_ent = rank_suppliers(features)
    multi, weights = multi_method_ranking(features)
    multi.to_csv(TABLE_DIR / "q1_multimethod_scores.csv", index=False, encoding="utf-8-sig")

    # method agreement on top50
    methods = ["entropy_topsis", "critic_topsis", "grey", "pca"]
    top_sets = {m: set(multi.nlargest(TOP_K_Q1, m)["supplier_id"]) for m in methods}
    ent_top = top_sets["entropy_topsis"]
    agree = []
    for m in methods:
        agree.append({
            "method": m,
            "overlap_with_entropy_topsis": len(top_sets[m] & ent_top),
            "jaccard": len(top_sets[m] & ent_top) / len(top_sets[m] | ent_top),
        })
    # also baseline
    base = baseline_rank(features)
    agree.append({
        "method": "total_supply_baseline",
        "overlap_with_entropy_topsis": len(set(base.head(TOP_K_Q1)["supplier_id"]) & ent_top),
        "jaccard": len(set(base.head(TOP_K_Q1)["supplier_id"]) & ent_top) / len(set(base.head(TOP_K_Q1)["supplier_id"]) | ent_top),
    })
    pd.DataFrame(agree).to_csv(TABLE_DIR / "q1_method_agreement.csv", index=False, encoding="utf-8-sig")

    # Kendall tau between entropy and critic ranks
    tau = kendall_tau(multi["rank_entropy_topsis"].values, multi["rank_critic_topsis"].values)
    pd.DataFrame([{"kendall_entropy_critic": tau}]).to_csv(TABLE_DIR / "q1_kendall.csv", index=False, encoding="utf-8-sig")

    # weight table
    names = ["累计供货", "周均供货", "峰值供货", "满足率", "稳定性", "活跃周", "近期供货", "材料"]
    wdf = pd.DataFrame({"indicator": names, "entropy_weight": weights["entropy"], "critic_weight": weights["critic"]})
    wdf.to_csv(TABLE_DIR / "q1_weights.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(names))
    ax.bar(x - 0.2, wdf["entropy_weight"], 0.4, label="熵权", color="#2980B9")
    ax.bar(x + 0.2, wdf["critic_weight"], 0.4, label="CRITIC", color="#E67E22")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha="right")
    ax.set_ylabel("权重")
    ax.set_title("Q1 指标权重：熵权法 vs CRITIC")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "q1_weight_compare.png")
    plt.close(fig)

    fig, ax = plt.subplots()
    ax.bar([a["method"] for a in agree], [a["overlap_with_entropy_topsis"] for a in agree], color="#27AE60")
    ax.axhline(40, color="r", ls="--", label="重叠=40")
    ax.set_ylabel("与熵权TOPSIS的Top50重叠数")
    ax.set_title("多方法Top50一致性对比")
    ax.set_xticklabels([a["method"] for a in agree], rotation=25, ha="right")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "q1_method_overlap.png")
    plt.close(fig)

    # Monte Carlo robustness
    mc = monte_carlo_robustness(features, n_sim=200)
    mc.to_csv(TABLE_DIR / "q1_monte_carlo.csv", index=False, encoding="utf-8-sig")
    mc_summary = {
        "mean_overlap": mc["overlap"].mean(),
        "std_overlap": mc["overlap"].std(),
        "p5_overlap": mc["overlap"].quantile(0.05),
        "p95_overlap": mc["overlap"].quantile(0.95),
        "mean_jaccard": mc["jaccard"].mean(),
    }
    pd.DataFrame([mc_summary]).to_csv(TABLE_DIR / "q1_monte_carlo_summary.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots()
    ax.hist(mc["overlap"], bins=15, color="#8E44AD", edgecolor="white")
    ax.axvline(mc_summary["mean_overlap"], color="r", ls="--", label=f"均值={mc_summary['mean_overlap']:.1f}")
    ax.set_xlabel("Top50重叠数")
    ax.set_ylabel("频数")
    ax.set_title("Q1 蒙特卡洛鲁棒性（n=200）")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "q1_monte_carlo.png")
    plt.close(fig)

    # Q2/Q3 inventory robustness
    q2 = pd.read_csv(TABLE_DIR / "q2_order_plan.csv")
    q3 = pd.read_csv(TABLE_DIR / "q3_order_plan.csv")
    rob_rows = []
    for name, plan, noise in [("Q2", q2, 0.05), ("Q2", q2, 0.10), ("Q2", q2, 0.15),
                               ("Q3", q3, 0.05), ("Q3", q3, 0.10), ("Q3", q3, 0.15)]:
        s = inventory_simulation(plan, fill_noise=noise, n=80)
        rob_rows.append({"scheme": name, "fill_noise": noise, **s})
    rob_df = pd.DataFrame(rob_rows)
    rob_df.to_csv(TABLE_DIR / "inventory_robustness.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots()
    for sch, c in [("Q2", "#3498DB"), ("Q3", "#E67E22")]:
        sub = rob_df[rob_df["scheme"] == sch]
        ax.plot(sub["fill_noise"], sub["prob_any_stockout"], "o-", label=sch, color=c)
    ax.set_xlabel("供货满足率扰动强度")
    ax.set_ylabel("出现库存不足概率")
    ax.set_title("订购方案库存鲁棒性检验")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "robustness_inventory.png")
    plt.close(fig)

    # price sensitivity for Q2 cost index
    PRICE = {"A": 1.2, "B": 1.1, "C": 1.0}
    week_cols = [c for c in q2.columns if c.startswith("week_")]
    sens_price = []
    for delta in np.linspace(-0.2, 0.2, 9):
        cost = 0.0
        for _, r in q2.iterrows():
            p = PRICE[r["material"]] * (1 + delta if r["material"] == "A" else 1.0)
            cost += p * r[week_cols].sum()
        sens_price.append({"a_price_delta": delta, "cost_index": cost})
    spd = pd.DataFrame(sens_price)
    spd.to_csv(TABLE_DIR / "q2_price_sensitivity.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots()
    ax.plot(spd["a_price_delta"] * 100, spd["cost_index"], "s-", color="#C0392B")
    ax.set_xlabel("A类相对价格变动 (%)")
    ax.set_ylabel("成本指数")
    ax.set_title("Q2 对A类价格的灵敏度")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "q2_price_sensitivity.png")
    plt.close(fig)

    # transport capacity utilization
    for qn in ["q2", "q3", "q4"]:
        tr = pd.read_csv(TABLE_DIR / f"{qn}_transport_plan.csv")
        util = tr.groupby(["week", "transporter"])["volume"].sum().reset_index()
        util["util_rate"] = util["volume"] / TRANSPORT_CAP
        util.to_csv(TABLE_DIR / f"{qn}_transport_util.csv", index=False, encoding="utf-8-sig")
        if qn == "q2":
            piv = util.pivot_table(index="week", columns="transporter", values="util_rate", fill_value=0)
            fig, ax = plt.subplots(figsize=(9, 4))
            im = ax.imshow(piv.T.values, aspect="auto", cmap="YlOrRd", vmin=0, vmax=1.2)
            ax.set_yticks(range(8))
            ax.set_yticklabels([f"T{i}" for i in range(1, 9)])
            ax.set_xlabel("周")
            ax.set_ylabel("转运商")
            ax.set_title("Q2 转运商周利用率热力图")
            fig.colorbar(im, ax=ax, label="利用率")
            fig.tight_layout()
            fig.savefig(FIG_DIR / "q2_transport_util_heatmap.png")
            plt.close(fig)

    draw_flowchart()

    # capacity bottleneck decomposition for Q4
    q4 = pd.read_csv(TABLE_DIR / "q4_summary.csv").iloc[0]
    # supplier capacity sum (product equiv of top)
    from optimization import estimate_supplier_weekly_capacity, mix_weekly_raw_needs, PlanConfig
    caps = estimate_supplier_weekly_capacity(ranked)
    # convert approx A-equivalent
    supply_ceiling_raw = caps.sum()
    transport_ceiling = 8 * TRANSPORT_CAP
    demand_at_max = WEEKLY_CAPACITY * q4["capacity_multiplier"] * 0.6
    bottleneck = pd.DataFrame([
        {"bottleneck": "供应商供货能力(周)", "raw_m3": supply_ceiling_raw},
        {"bottleneck": "转运能力8×6000", "raw_m3": transport_ceiling},
        {"bottleneck": "Q4方案周需求(A当量近似)", "raw_m3": demand_at_max},
    ])
    bottleneck.to_csv(TABLE_DIR / "q4_bottleneck.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots()
    ax.barh(bottleneck["bottleneck"], bottleneck["raw_m3"], color=["#3498DB", "#E74C3C", "#2ECC71"])
    ax.set_xlabel("周原材料量 (m³)")
    ax.set_title("Q4 产能提升瓶颈分解")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "q4_bottleneck.png")
    plt.close(fig)

    logger.info("Advanced analysis done. MC mean overlap=%.1f, Kendall=%.3f", mc_summary["mean_overlap"], tau)
    return mc_summary


if __name__ == "__main__":
    main()
