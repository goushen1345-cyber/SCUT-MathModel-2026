"""Q1: Supplier importance ranking and top-50 selection."""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from config import PROCESSED_DIR, TABLE_DIR, TOP_K_Q1
from utils import (
    build_supplier_features,
    entropy_weights,
    load_supplier_data,
    setup_logging,
    setup_matplotlib,
    topsis_score,
    ensure_dirs,
)


def rank_suppliers(features: pd.DataFrame) -> pd.DataFrame:
    """Entropy-TOPSIS composite importance model."""
    # material bonus: A/C most cost-effective per product volume
    mat_score = features["material"].map({"A": 1.0, "B": 0.95, "C": 1.0}).fillna(0.9)

    X = np.column_stack(
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
    benefit = np.array([True, True, True, True, True, True, True, True])
    w = entropy_weights(X)
    score = topsis_score(X, w, benefit)

    out = features.copy()
    out["importance_score"] = score
    out["rank"] = out["importance_score"].rank(ascending=False, method="min").astype(int)
    out = out.sort_values("rank")
    return out, w


def baseline_rank(features: pd.DataFrame) -> pd.DataFrame:
    """Baseline: rank by total supply only."""
    b = features.copy()
    b["baseline_score"] = b["total_supply"]
    b["baseline_rank"] = b["baseline_score"].rank(ascending=False, method="min").astype(int)
    return b.sort_values("baseline_rank")


def main():
    ensure_dirs()
    logger = setup_logging("q1_supplier_importance")
    setup_matplotlib()
    orders, supplies = load_supplier_data()
    features = build_supplier_features(orders, supplies)

    ranked, weights = rank_suppliers(features)
    ranked.to_csv(TABLE_DIR / "q1_supplier_scores.csv", index=False, encoding="utf-8-sig")
    top50 = ranked.head(TOP_K_Q1).copy()
    top50.to_csv(TABLE_DIR / "q1_top50_suppliers.csv", index=False, encoding="utf-8-sig")
    top50[["rank", "supplier_id", "material", "importance_score", "total_supply", "fill_rate"]].to_csv(
        PROCESSED_DIR / "top50_suppliers.csv", index=False, encoding="utf-8-sig"
    )

    # baseline comparison
    base = baseline_rank(features)
    overlap = len(set(top50["supplier_id"]) & set(base.head(TOP_K_Q1)["supplier_id"]))
    cmp_df = pd.DataFrame(
        {
            "method": ["TOPSIS综合", "累计供货量基准"],
            "top50_mean_fill_rate": [
                top50["fill_rate"].mean(),
                base.head(TOP_K_Q1)["fill_rate"].mean(),
            ],
            "top50_mean_supply": [
                top50["mean_supply"].mean(),
                base.head(TOP_K_Q1)["mean_supply"].mean(),
            ],
        }
    )
    cmp_df.to_csv(TABLE_DIR / "q1_baseline_comparison.csv", index=False, encoding="utf-8-sig")

    # figures
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(top50["supplier_id"].iloc[::-1][:20], top50["importance_score"].iloc[::-1][:20], color="#2980B9")
    ax.set_title("Q1 重要性得分 Top20 供应商")
    ax.set_xlabel("TOPSIS贴近度")
    ax.set_ylabel("供应商ID")
    fig.tight_layout()
    fig.savefig("output/figures/q1_top20_scores.png")
    plt.close(fig)

    fig, ax = plt.subplots()
    ax.scatter(ranked["fill_rate"], ranked["importance_score"], c=ranked["material"].map({"A": "r", "B": "b", "C": "g"}), alpha=0.5, s=15)
    ax.set_xlabel("供货满足率")
    ax.set_ylabel("重要性得分")
    ax.set_title("Q1 供应商重要性分布")
    fig.tight_layout()
    fig.savefig("output/figures/q1_score_scatter.png")
    plt.close(fig)

    # sensitivity: weight perturbation on fill_rate dimension
    sens = []
    for delta in np.linspace(-0.3, 0.3, 13):
        w2 = weights.copy()
        w2[3] = max(w2[3] + delta, 0.01)
        w2 = w2 / w2.sum()
        X = np.column_stack(
            [
                features["total_supply"].values,
                features["mean_supply"].values,
                features["max_supply"].values,
                features["fill_rate"].values,
                features["stability"].values,
                features["active_weeks"].values,
                features["recent_supply"].values,
                features["material"].map({"A": 1.0, "B": 0.95, "C": 1.0}).fillna(0.9).values,
            ]
        )
        sc = topsis_score(X, w2, np.ones(8, dtype=bool))
        top_ids = features.iloc[np.argsort(-sc)[:TOP_K_Q1]]["supplier_id"].tolist()
        sens.append({"delta_fill_weight": delta, "overlap_with_base": len(set(top_ids) & set(top50["supplier_id"]))})

    sens_df = pd.DataFrame(sens)
    sens_df.to_csv(TABLE_DIR / "q1_sensitivity.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots()
    ax.plot(sens_df["delta_fill_weight"], sens_df["overlap_with_base"], "o-")
    ax.set_xlabel("满足率权重扰动")
    ax.set_ylabel("Top50重叠数量")
    ax.set_title("Q1 权重灵敏度分析")
    fig.tight_layout()
    fig.savefig("output/figures/q1_sensitivity.png")
    plt.close(fig)

    logger.info("Q1 done: top supplier %s score=%.4f, baseline overlap=%d/50", top50.iloc[0]["supplier_id"], top50.iloc[0]["importance_score"], overlap)
    return ranked, top50


if __name__ == "__main__":
    main()
