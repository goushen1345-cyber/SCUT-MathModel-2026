"""Q3: Prefer A, minimize C, low transport loss."""
from __future__ import annotations

import pandas as pd
import matplotlib.pyplot as plt

from config import TABLE_DIR
from optimization import PlanConfig, assign_transport, build_loss_matrix, evaluate_plan, select_min_suppliers, mix_weekly_raw_needs, solve_order_plan
from q1_supplier_importance import rank_suppliers
from q2_order_transport import write_attachment_a, write_attachment_b
from utils import build_supplier_features, ensure_dirs, load_supplier_data, load_transporter_data, setup_logging, setup_matplotlib


def main():
    ensure_dirs()
    logger = setup_logging("q3_prefer_a")
    setup_matplotlib()
    orders, supplies = load_supplier_data()
    trans = load_transporter_data()
    features = build_supplier_features(orders, supplies)
    ranked, _ = rank_suppliers(features)

    cfg = PlanConfig(objective="prefer_a", alpha_a=0.85, alpha_c=0.15)
    needs = mix_weekly_raw_needs(cfg)
    total_raw = sum(needs.values())
    supplier_ids, n = select_min_suppliers(ranked, total_raw, buffer=1.2)

    # prioritize A-material suppliers
    a_ranked = ranked.copy()
    a_ranked["rank"] = a_ranked["rank"] - a_ranked["material"].map({"A": 50, "B": 0, "C": -30}).fillna(0)
    a_ranked = a_ranked.sort_values("rank")
    supplier_ids, n = select_min_suppliers(a_ranked, total_raw, buffer=1.2)

    order_plan = solve_order_plan(features, supplier_ids, cfg)
    loss_mat = build_loss_matrix(trans)
    transport = assign_transport(order_plan, loss_mat)
    metrics = evaluate_plan(order_plan, transport, cfg)

    order_plan.to_csv(TABLE_DIR / "q3_order_plan.csv", index=False, encoding="utf-8-sig")
    transport.to_csv(TABLE_DIR / "q3_transport_plan.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([{"suppliers": n, **metrics}]).to_csv(TABLE_DIR / "q3_summary.csv", index=False, encoding="utf-8-sig")

    write_attachment_a(order_plan, "问题3的订购方案结果")
    write_attachment_b(transport, "问题3的转运方案结果")

    week_cols = [f"week_{i:02d}" for i in range(1, 25)]
    mat_week = order_plan.groupby("material")[week_cols].sum().T
    fig, ax = plt.subplots()
    mat_week.plot(kind="area", ax=ax, stacked=True)
    ax.set_title("Q3 24周分材料订货结构")
    ax.set_xlabel("周")
    ax.set_ylabel("订货量 (m³)")
    fig.tight_layout()
    fig.savefig("output/figures/q3_material_mix.png")
    plt.close(fig)

    # ablation vs Q2
    q2 = pd.read_csv(TABLE_DIR / "q2_summary.csv")
    cmp_df = pd.DataFrame(
        {
            "方案": ["Q2最经济", "Q3偏A少C"],
            "cost_index": [q2["total_cost_index"].iloc[0], metrics["total_cost_index"]],
            "order_volume": [q2["total_order_volume"].iloc[0], metrics["total_order_volume"]],
        }
    )
    cmp_df.to_csv(TABLE_DIR / "q3_ablation.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots()
    ax.bar(cmp_df["方案"], cmp_df["order_volume"], color=["#3498DB", "#E67E22"])
    ax.set_ylabel("总订货量 (m³)")
    ax.set_title("Q3 与Q2方案对比")
    fig.tight_layout()
    fig.savefig("output/figures/q3_vs_q2.png")
    plt.close(fig)

    week_cols = [f"week_{i:02d}" for i in range(1, 25)]
    CONS = {"A": 0.6, "B": 0.66, "C": 0.72}
    raw = {m: order_plan[order_plan["material"] == m][week_cols].sum().sum() for m in "ABC"}
    prod = {m: raw[m] / CONS[m] for m in raw}
    prod_total = sum(prod.values()) or 1
    prod_pct = {m: 100 * prod[m] / prod_total for m in prod}
    logger.info(
        "Q3: 产品当量 A=%.1f%% B=%.1f%% C=%.1f%%, suppliers=%d",
        prod_pct["A"], prod_pct["B"], prod_pct["C"], n,
    )
    return metrics


if __name__ == "__main__":
    main()
