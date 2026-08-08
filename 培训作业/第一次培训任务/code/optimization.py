"""Shared optimization routines for Q2-Q4."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
import pulp

from config import (
    CONSUMPTION,
    INVENTORY_WEEKS,
    PLAN_WEEKS,
    PRICE_REL,
    TRANSPORT_CAP,
    WEEKLY_CAPACITY,
)


@dataclass
class PlanConfig:
    objective: Literal["cost", "prefer_a", "capacity"] = "cost"
    capacity_multiplier: float = 1.0
    alpha_a: float = 0.5  # target share of product from A (rest mostly C)
    alpha_c: float = 0.5


def weekly_raw_demand(material: str, capacity: float = WEEKLY_CAPACITY) -> float:
    return capacity * CONSUMPTION[material]


def product_equivalent(volume: float, material: str) -> float:
    return volume / CONSUMPTION[material]


def mix_weekly_raw_needs(cfg: PlanConfig) -> dict[str, float]:
    cap = WEEKLY_CAPACITY * cfg.capacity_multiplier
    if cfg.objective == "cost":
        # A minimizes transport/storage volume at equal material cost
        return {"A": cap * CONSUMPTION["A"], "B": 0.0, "C": 0.0}
    if cfg.objective == "prefer_a":
        pa = cap * cfg.alpha_a
        pc = cap * cfg.alpha_c
        return {"A": pa * CONSUMPTION["A"], "B": 0.0, "C": pc * CONSUMPTION["C"]}
    # capacity mode uses same mix as cost unless overridden
    return {"A": cap * CONSUMPTION["A"], "B": 0.0, "C": 0.0}


def inventory_target_product_equiv(cfg: PlanConfig) -> float:
    return INVENTORY_WEEKS * WEEKLY_CAPACITY * cfg.capacity_multiplier


def estimate_supplier_weekly_capacity(features: pd.DataFrame) -> pd.Series:
    return np.minimum(features["max_supply"], features["mean_supply"] * 1.5)


def select_min_suppliers(
    ranked: pd.DataFrame,
    weekly_need: float,
    buffer: float = 1.15,
) -> tuple[list[str], int]:
    ranked = ranked.sort_values("rank")
    caps = estimate_supplier_weekly_capacity(ranked)
    target = weekly_need * buffer
    chosen, cum = [], 0.0
    for idx, row in ranked.iterrows():
        chosen.append(row["supplier_id"])
        cum += caps.loc[idx]
        if cum >= target:
            break
    return chosen, len(chosen)


def build_loss_matrix(trans: pd.DataFrame, weeks: int = PLAN_WEEKS) -> np.ndarray:
    tcols = [c for c in trans.columns if str(c).startswith("W")][-weeks:]
    loss = trans[tcols].replace(0, np.nan).astype(float).values
    loss = np.nan_to_num(loss, nan=np.nanmean(loss))
    return loss  # shape (8, weeks)


def solve_order_plan(
    suppliers: pd.DataFrame,
    supplier_ids: list[str],
    cfg: PlanConfig,
) -> pd.DataFrame:
    """LP for 24-week ordering with inventory constraints (product-equivalent)."""
    sub = suppliers[suppliers["supplier_id"].isin(supplier_ids)].copy()
    sub = sub.set_index("supplier_id").loc[supplier_ids]
    mats = sub["material"].values
    fill = sub["fill_rate"].clip(0.3, 1.2).values
    cap = estimate_supplier_weekly_capacity(sub).values

    needs = mix_weekly_raw_needs(cfg)
    total_raw = sum(needs.values())
    inv_target = inventory_target_product_equiv(cfg)

    prob = pulp.LpProblem("order_plan", pulp.LpMinimize)
    ids = list(sub.index)
    weeks = range(PLAN_WEEKS)

    Q = pulp.LpVariable.dicts("q", (ids, weeks), lowBound=0)
    I = pulp.LpVariable.dicts("I", weeks, lowBound=0)

    # cost objective
    cost_coef = np.array([PRICE_REL[m] for m in mats])
    prob += pulp.lpSum(Q[i][t] * cost_coef[idx] for idx, i in enumerate(ids) for t in weeks)

    # inventory dynamics (product equivalent)
    for t in weeks:
        recv_equiv = pulp.lpSum(
            Q[i][t] * fill[idx] * (1.0 / CONSUMPTION[mats[idx]]) for idx, i in enumerate(ids)
        )
        consume = WEEKLY_CAPACITY * cfg.capacity_multiplier
        if t == 0:
            prob += I[t] == inv_target + recv_equiv - consume
        else:
            prob += I[t] == I[t - 1] + recv_equiv - consume
        prob += I[t] >= inv_target
        for idx, i in enumerate(ids):
            prob += Q[i][t] <= cap[idx]

    # meet weekly raw material demand (soft via minimum total orders)
    for t in weeks:
        prob += pulp.lpSum(Q[i][t] * fill[idx] for idx, i in enumerate(ids)) >= total_raw * 0.95

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    rows = []
    for i in ids:
        row = {"supplier_id": i, "material": sub.loc[i, "material"]}
        for t in weeks:
            row[f"week_{t+1:02d}"] = pulp.value(Q[i][t]) or 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def assign_transport(
    order_plan: pd.DataFrame,
    loss_mat: np.ndarray,
) -> pd.DataFrame:
    """Greedy transport assignment: one primary transporter per supplier-week."""
    transporters = [f"T{i}" for i in range(1, 9)]
    records = []
    for _, row in order_plan.iterrows():
        sid = row["supplier_id"]
        for w in range(PLAN_WEEKS):
            qty = row.get(f"week_{w+1:02d}", 0) or 0
            if qty <= 0:
                for ti, tname in enumerate(transporters):
                    records.append({"supplier_id": sid, "week": w + 1, "transporter": tname, "volume": 0.0})
                continue
            losses = loss_mat[:, w]
            order_t = np.argsort(losses)
            remaining = qty
            assign = {t: 0.0 for t in transporters}
            for ti in order_t:
                if remaining <= 0:
                    break
                take = min(remaining, TRANSPORT_CAP)
                assign[transporters[ti]] = take
                remaining -= take
            for tname in transporters:
                records.append({"supplier_id": sid, "week": w + 1, "transporter": tname, "volume": assign[tname]})
    return pd.DataFrame(records)


def evaluate_plan(order_plan: pd.DataFrame, transport: pd.DataFrame, cfg: PlanConfig) -> dict:
    week_cols = [f"week_{i:02d}" for i in range(1, PLAN_WEEKS + 1)]
    total_order = order_plan[week_cols].sum().sum()
    cost = sum(
        order_plan[f"week_{t:02d}"].sum() * PRICE_REL[m]
        for t in range(1, PLAN_WEEKS + 1)
        for m in order_plan["material"].unique()
        if f"week_{t:02d}" in order_plan.columns
    )
    # more accurate cost
    cost = 0.0
    for _, r in order_plan.iterrows():
        p = PRICE_REL[r["material"]]
        cost += p * sum(r[c] for c in week_cols)

    trans_vol = transport.groupby(["week", "transporter"])["volume"].sum().reset_index()
    cap_viol = (trans_vol["volume"] > TRANSPORT_CAP + 1e-6).sum()

    return {
        "total_order_volume": float(total_order),
        "total_cost_index": float(cost),
        "transport_capacity_violations": int(cap_viol),
        "weekly_capacity": WEEKLY_CAPACITY * cfg.capacity_multiplier,
    }


def max_capacity_search(ranked: pd.DataFrame, trans: pd.DataFrame, max_mult: float = 2.5) -> float:
    """Binary search max capacity multiplier feasible with suppliers + transporters."""
    lo, hi = 1.0, max_mult
    for _ in range(12):
        mid = (lo + hi) / 2
        cfg = PlanConfig(objective="capacity", capacity_multiplier=mid)
        needs = mix_weekly_raw_needs(cfg)
        total_raw = sum(needs.values())
        _, n = select_min_suppliers(ranked, total_raw)
        if n <= 402:
            lo = mid
        else:
            hi = mid
    # transport bottleneck: 8 * 6000 = 48000 m3/week raw max
    trans_limit = 8 * TRANSPORT_CAP
    raw_at_lo = sum(mix_weekly_raw_needs(PlanConfig(capacity_multiplier=lo)).values())
    if raw_at_lo > trans_limit:
        lo = lo * trans_limit / raw_at_lo
    return round(lo, 4)
