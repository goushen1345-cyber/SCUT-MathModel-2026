"""Dump compact numbers and rewrite generate_latex to use @@placeholders@@."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "output" / "tables"
CONS = {"A": 0.6, "B": 0.66, "C": 0.72}


def mix(plan: str):
    df = pd.read_csv(TABLE / plan)
    wc = [c for c in df.columns if c.startswith("week_")]
    raw = {m: float(df[df.material == m][wc].sum().sum()) for m in "ABC"}
    prod = {m: raw[m] / CONS[m] for m in raw}
    pt = sum(prod.values()) or 1
    return {m: round(100 * prod[m] / pt, 1) for m in prod}, round(sum(raw.values()), 0)


def main():
    q1 = pd.read_csv(TABLE / "q1_top50_suppliers.csv")
    q2 = pd.read_csv(TABLE / "q2_summary.csv").iloc[0]
    q3 = pd.read_csv(TABLE / "q3_summary.csv").iloc[0]
    q4 = pd.read_csv(TABLE / "q4_summary.csv").iloc[0]
    mc = pd.read_csv(TABLE / "q1_monte_carlo_summary.csv").iloc[0]
    agree = pd.read_csv(TABLE / "q1_method_agreement.csv")
    base = pd.read_csv(TABLE / "q1_baseline_comparison.csv")
    kendall = float(pd.read_csv(TABLE / "q1_kendall.csv").iloc[0, 0])
    wdf = pd.read_csv(TABLE / "q1_weights.csv")
    rob = pd.read_csv(TABLE / "inventory_robustness.csv")
    bn = pd.read_csv(TABLE / "q4_bottleneck.csv")
    q2p, q2t = mix("q2_order_plan.csv")
    q3p, q3t = mix("q3_order_plan.csv")

    top15 = "\n".join(
        f"{int(r['rank'])} & {r['supplier_id']} & {r['material']} & {r['importance_score']:.4f} & "
        f"{r['total_supply']:.0f} & {r['fill_rate']:.3f} \\\\"
        for _, r in q1.head(15).iterrows()
    )
    top50 = "\n".join(
        f"{int(r['rank'])} & {r['supplier_id']} & {r['material']} & {r['importance_score']:.4f} & "
        f"{r['total_supply']:.0f} & {r['mean_supply']:.1f} & {r['fill_rate']:.3f} \\\\"
        for _, r in q1.iterrows()
    )
    wrows = "\n".join(
        f"{r.indicator} & {r.entropy_weight:.4f} & {r.critic_weight:.4f} \\\\" for _, r in wdf.iterrows()
    )
    agree_rows = "\n".join(
        f"{str(r.method).replace('_', '\\_')} & {int(r.overlap_with_entropy_topsis)} & {r.jaccard:.3f} \\\\"
        for _, r in agree.iterrows()
    )
    rob_rows = "\n".join(
        f"{r.scheme} & {r.fill_noise:.2f} & {r.mean_stockout_weeks:.2f} & "
        f"{r.prob_any_stockout:.3f} & {r.mean_min_inventory:.0f} \\\\"
        for _, r in rob.iterrows()
    )
    bn_rows = "\n".join(f"{r.bottleneck} & {r.raw_m3:.1f} \\\\" for _, r in bn.iterrows())

    d = {
        "TOP1": q1.iloc[0].supplier_id,
        "TOP1M": q1.iloc[0].material,
        "TOP1S": f"{q1.iloc[0].importance_score:.4f}",
        "T50FILL": f"{q1.fill_rate.mean():.3f}",
        "T50MEAN": f"{q1.mean_supply.mean():.1f}",
        "MINSUP": str(int(q2.min_suppliers)),
        "Q2ORD": f"{q2.total_order_volume:.0f}",
        "Q2COST": f"{q2.total_cost_index:.0f}",
        "Q3SUP": str(int(q3.suppliers)),
        "Q3ORD": f"{q3.total_order_volume:.0f}",
        "Q3COST": f"{q3.total_cost_index:.0f}",
        "Q4LAM": f"{q4.capacity_multiplier:.4f}",
        "Q4CAP": f"{q4.new_capacity_m3:.0f}",
        "Q4INC": f"{q4.increase_percent:.1f}",
        "Q4SUP": str(int(q4.suppliers_used)),
        "MCMEAN": f"{mc.mean_overlap:.2f}",
        "MCP5": f"{mc.p5_overlap:.0f}",
        "MCJAC": f"{mc.mean_jaccard:.3f}",
        "KENDALL": f"{kendall:.3f}",
        "Q2A": f"{q2p['A']:.1f}",
        "Q2B": f"{q2p['B']:.1f}",
        "Q2C": f"{q2p['C']:.1f}",
        "Q3A": f"{q3p['A']:.1f}",
        "Q3B": f"{q3p['B']:.1f}",
        "Q3C": f"{q3p['C']:.1f}",
        "COSTDROP": f"{100*(q2.total_cost_index-q3.total_cost_index)/q2.total_cost_index:.1f}",
        "VOLDROP": f"{100*(q2.total_order_volume-q3.total_order_volume)/q2.total_order_volume:.1f}",
        "BASEFILL0": f"{base.iloc[0].top50_mean_fill_rate:.3f}",
        "BASEFILL1": f"{base.iloc[1].top50_mean_fill_rate:.3f}",
        "OVERLAPBASE": str(int(agree[agree.method == "total_supply_baseline"].iloc[0].overlap_with_entropy_topsis)),
        "AGAINGAIN": f"{q3p['A']-q2p['A']:.1f}",
        "CDROP": f"{q2p['C']-q3p['C']:.1f}",
        "TOP15": top15,
        "TOP50": top50,
        "WROWS": wrows,
        "AGREEROWS": agree_rows,
        "ROBROWS": rob_rows,
        "BNROWS": bn_rows,
    }
    (ROOT / "logs" / "nums_compact.json").write_text(json.dumps({k: v for k, v in d.items() if k not in ("TOP15", "TOP50", "WROWS", "AGREEROWS", "ROBROWS", "BNROWS")}, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "logs" / "paper_placeholders.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print("placeholders ready", d["TOP1"], d["MINSUP"], d["Q3A"])


if __name__ == "__main__":
    main()
