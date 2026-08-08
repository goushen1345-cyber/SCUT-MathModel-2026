"""Q4: Maximum capacity expansion and 24-week plans."""
from __future__ import annotations

import pandas as pd
import matplotlib.pyplot as plt

from config import TABLE_DIR, WEEKLY_CAPACITY
from optimization import (
    PlanConfig,
    assign_transport,
    build_loss_matrix,
    evaluate_plan,
    max_capacity_search,
    mix_weekly_raw_needs,
    select_min_suppliers,
    solve_order_plan,
)
from q1_supplier_importance import rank_suppliers
from q2_order_transport import write_attachment_a, write_attachment_b
from utils import build_supplier_features, ensure_dirs, load_supplier_data, load_transporter_data, setup_logging, setup_matplotlib


def main():
    ensure_dirs()
    logger = setup_logging("q4_capacity")
    setup_matplotlib()
    orders, supplies = load_supplier_data()
    trans = load_transporter_data()
    features = build_supplier_features(orders, supplies)
    ranked, _ = rank_suppliers(features)

    mult = max_capacity_search(ranked, trans)
    new_capacity = WEEKLY_CAPACITY * mult
    increase_pct = (mult - 1) * 100

    cfg = PlanConfig(objective="capacity", capacity_multiplier=mult)
    needs = mix_weekly_raw_needs(cfg)
    total_raw = sum(needs.values())
    supplier_ids, n = select_min_suppliers(ranked, total_raw, buffer=1.1)

    order_plan = solve_order_plan(features, supplier_ids, cfg)
    loss_mat = build_loss_matrix(trans)
    transport = assign_transport(order_plan, loss_mat)
    metrics = evaluate_plan(order_plan, transport, cfg)

    summary = {
        "capacity_multiplier": mult,
        "original_capacity": WEEKLY_CAPACITY,
        "new_capacity_m3": new_capacity,
        "increase_percent": increase_pct,
        "suppliers_used": n,
        **metrics,
    }
    pd.DataFrame([summary]).to_csv(TABLE_DIR / "q4_summary.csv", index=False, encoding="utf-8-sig")
    order_plan.to_csv(TABLE_DIR / "q4_order_plan.csv", index=False, encoding="utf-8-sig")
    transport.to_csv(TABLE_DIR / "q4_transport_plan.csv", index=False, encoding="utf-8-sig")

    write_attachment_a(order_plan, "问题4的订购方案结果")
    write_attachment_b(transport, "问题4的转运方案结果")

    # sensitivity on capacity
    sens = []
    for m in [1.0, 1.05, 1.1, 1.15, mult]:
        c = PlanConfig(capacity_multiplier=m)
        raw = sum(mix_weekly_raw_needs(c).values())
        _, ns = select_min_suppliers(ranked, raw)
        sens.append({"multiplier": m, "capacity": WEEKLY_CAPACITY * m, "min_suppliers": ns})
    sens_df = pd.DataFrame(sens)
    sens_df.to_csv(TABLE_DIR / "q4_sensitivity.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots()
    ax.plot(sens_df["capacity"], sens_df["min_suppliers"], "s-", color="#C0392B")
    ax.set_xlabel("周产能 (m³)")
    ax.set_ylabel("最少供应商数")
    ax.set_title("Q4 产能提升与供应商需求灵敏度")
    fig.tight_layout()
    fig.savefig("output/figures/q4_capacity_sensitivity.png")
    plt.close(fig)

    fig, ax = plt.subplots()
    ax.bar(["原产能", "提升后"], [WEEKLY_CAPACITY, new_capacity], color=["#95A5A6", "#E74C3C"])
    ax.set_ylabel("周产能 (m³)")
    ax.set_title(f"Q4 产能提升 {increase_pct:.1f}%")
    fig.tight_layout()
    fig.savefig("output/figures/q4_capacity_compare.png")
    plt.close(fig)

    logger.info("Q4: max multiplier=%.3f, new capacity=%.0f (+%.1f%%)", mult, new_capacity, increase_pct)
    return summary


if __name__ == "__main__":
    main()
