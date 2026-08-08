"""Step 2: EDA and data preprocessing."""
from __future__ import annotations

import numpy as np
import pandas as pd
import seaborn as sns

from config import PROCESSED_DIR
from utils import (
    build_supplier_features,
    ensure_dirs,
    load_supplier_data,
    load_transporter_data,
    setup_logging,
    setup_matplotlib,
)
import matplotlib.pyplot as plt


def main():
    ensure_dirs()
    logger = setup_logging("01_eda_preprocess")
    setup_matplotlib()
    orders, supplies = load_supplier_data()
    trans = load_transporter_data()

    features = build_supplier_features(orders, supplies)
    features.to_csv(PROCESSED_DIR / "supplier_features.csv", index=False, encoding="utf-8-sig")

    # descriptive stats
    desc = features.describe().T
    desc.to_csv(PROCESSED_DIR / "descriptive_stats.csv", encoding="utf-8-sig")

    # material distribution
    fig, ax = plt.subplots()
    features["material"].value_counts().sort_index().plot(kind="bar", ax=ax, color=["#4C72B0", "#55A868", "#C44E52"])
    ax.set_title("402家供应商材料类型分布")
    ax.set_xlabel("材料类型")
    ax.set_ylabel("供应商数量")
    fig.tight_layout()
    fig.savefig("output/figures/eda_material_distribution.png")
    plt.close(fig)

    # supply distribution
    fig, ax = plt.subplots()
    sns.histplot(features["total_supply"], bins=40, kde=True, ax=ax)
    ax.set_title("供应商5年累计供货量分布")
    ax.set_xlabel("累计供货量 (m³)")
    fig.tight_layout()
    fig.savefig("output/figures/eda_supply_distribution.png")
    plt.close(fig)

    # correlation heatmap
    num_cols = ["total_supply", "mean_supply", "max_supply", "fill_rate", "stability", "active_weeks"]
    corr = features[num_cols].corr()
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdYlBu_r", ax=ax)
    ax.set_title("供应商特征相关性热力图")
    fig.tight_layout()
    fig.savefig("output/figures/eda_correlation_heatmap.png")
    plt.close(fig)

    # fill rate vs mean supply
    fig, ax = plt.subplots()
    for m, c in zip(["A", "B", "C"], ["#E74C3C", "#3498DB", "#2ECC71"]):
        sub = features[features["material"] == m]
        ax.scatter(sub["mean_supply"], sub["fill_rate"], alpha=0.6, s=20, label=f"类{m}", c=c)
    ax.set_xlabel("周均供货量 (m³)")
    ax.set_ylabel("供货满足率")
    ax.set_title("供货量与满足率关系")
    ax.legend()
    fig.tight_layout()
    fig.savefig("output/figures/eda_fillrate_vs_supply.png")
    plt.close(fig)

    # transporter loss stats
    tcols = [c for c in trans.columns if str(c).startswith("W")]
    loss = trans[tcols].replace(0, np.nan)
    loss_mean = loss.mean(axis=1)
    loss_df = pd.DataFrame({"transporter": trans.iloc[:, 0], "mean_loss_pct": loss_mean.values})
    loss_df.to_csv(PROCESSED_DIR / "transporter_loss_stats.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots()
    ax.bar(loss_df["transporter"].astype(str), loss_df["mean_loss_pct"], color="#8E44AD")
    ax.set_title("8家转运商平均损耗率")
    ax.set_xlabel("转运商")
    ax.set_ylabel("平均损耗率 (%)")
    fig.tight_layout()
    fig.savefig("output/figures/eda_transporter_loss.png")
    plt.close(fig)

    # weekly loss trend (recent 24 weeks)
    recent_loss = loss.iloc[:, -24:].mean(axis=0)
    fig, ax = plt.subplots()
    ax.plot(range(1, 25), recent_loss.values, marker="o")
    ax.set_title("近24周市场平均转运损耗率趋势")
    ax.set_xlabel("周序号")
    ax.set_ylabel("平均损耗率 (%)")
    fig.tight_layout()
    fig.savefig("output/figures/eda_loss_trend.png")
    plt.close(fig)

    # save processed weekly panels
    orders.to_csv(PROCESSED_DIR / "orders.csv", index=False, encoding="utf-8-sig")
    supplies.to_csv(PROCESSED_DIR / "supplies.csv", index=False, encoding="utf-8-sig")
    trans.to_csv(PROCESSED_DIR / "transporters.csv", index=False, encoding="utf-8-sig")

    logger.info("EDA complete: %d suppliers, features saved", len(features))
    return features


if __name__ == "__main__":
    main()
