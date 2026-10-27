"""Interpret verified Q4 deepening results and create reproducible figures."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager

R = Path(__file__).resolve().parent
P = R.parents[3]
OLD = R.parent / "20260912-three-candidates-v1"
O = R / "outputs"
A = R / "analysis"
F = R / "figures-v1"
A.mkdir(exist_ok=True)
F.mkdir(exist_ok=True)
START = 31


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


font_path = Path(r"C:\Windows\Fonts\simsun.ttc")
if font_path.exists():
    font_manager.fontManager.addfont(font_path)
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=font_path).get_name()
plt.rcParams.update({"axes.unicode_minus": False, "font.size": 9.5, "axes.titlesize": 11.5,
                     "savefig.dpi": 300, "figure.dpi": 140})

summary = json.loads((O / "summary.json").read_text(encoding="utf-8"))
results = pd.DataFrame(summary["results"])
verification = json.loads((O / "verification.json").read_text(encoding="utf-8"))


def row(branch, strategy):
    return results[(results.branch == branch) & (results.strategy == strategy)].iloc[0]


def old_row(branch, candidate):
    old = json.loads((OLD / "outputs/common_start/summary.json").read_text(encoding="utf-8"))["results"]
    return pd.DataFrame(old).query("branch == @branch and candidate == @candidate").iloc[0]


def read_daily(branch, strategy):
    return pd.read_csv(O / "strategies" / f"{branch}-{strategy}.daily.csv", float_precision="round_trip")


def read_trace(branch, strategy):
    return dict(np.load(O / "strategies" / f"{branch}-{strategy}.npz"))


def old_daily(branch, candidate):
    return pd.read_csv(OLD / "outputs/common_start" / f"{branch}-{candidate}.daily.csv", float_precision="round_trip")


def old_trace(branch, candidate):
    return dict(np.load(OLD / "outputs/common_start" / f"{branch}-{candidate}.npz"))


# Core validation comparison tables.
q42_names = ["P3-full", "P3-no-net", "P3-history-only", "P3-window28", "P3-window84", "P3-leaves7", "P3-leaves31"]
q43_structure = ["P2-full", "P2-residual-a10", "P2-residual-no-net", "P2-residual-a1", "P2-residual-a100"]
q43_info = ["P2-full", "P2-freeze-midnight-price", "P2-omit-06-price-update", "P2-omit-12-price-update", "P2-omit-18-price-update"]

q42 = results[(results.branch == "Q4-2") & results.strategy.isin(q42_names)].copy()
q42["cost_change_vs_full"] = q42.total_cost - row("Q4-2", "P3-full").total_cost
q42["emergency_change_vs_full"] = q42.emergency_kwh - row("Q4-2", "P3-full").emergency_kwh
q42.to_csv(A / "q42_feature_parameter_comparison.csv", index=False, encoding="utf-8-sig")

q43s = results[(results.branch == "Q4-3") & results.strategy.isin(q43_structure)].copy()
q43s["cost_change_vs_full"] = q43s.total_cost - row("Q4-3", "P2-full").total_cost
q43s["emergency_change_vs_full"] = q43s.emergency_kwh - row("Q4-3", "P2-full").emergency_kwh
q43s.to_csv(A / "q43_structure_comparison.csv", index=False, encoding="utf-8-sig")

q43i = results[(results.branch == "Q4-3") & results.strategy.isin(q43_info)].copy()
q43i["cost_change_vs_full"] = q43i.total_cost - row("Q4-3", "P2-full").total_cost
q43i["emergency_change_vs_full"] = q43i.emergency_kwh - row("Q4-3", "P2-full").emergency_kwh
q43i.to_csv(A / "q43_price_update_value.csv", index=False, encoding="utf-8-sig")

# Monthly and daily reversals for the meaningful comparisons.
monthly_rows = []
pair_rows = []
comparisons = [
    ("Q4-2", "P3-leaves31", "P3-full"),
    ("Q4-2", "P3-window28", "P3-full"),
    ("Q4-2", "P3-history-only", "P3-full"),
    ("Q4-3", "P2-residual-a10", "P2-full"),
    ("Q4-3", "P2-freeze-midnight-price", "P2-full"),
    ("Q4-3", "P2-omit-12-price-update", "P2-full"),
]
for branch, test, base_name in comparisons:
    a = read_daily(branch, test)
    b = read_daily(branch, base_name)
    diff = b.total_cost - a.total_cost
    dates = pd.to_datetime(a.date)
    for month, values in pd.DataFrame({"month": dates.dt.month, "saving": diff}).groupby("month"):
        monthly_rows.append({"branch": branch, "test": test, "base": base_name,
                             "month": int(month), "saving": float(values.saving.sum())})
    pair_rows.append({
        "branch": branch, "test": test, "base": base_name, "saving": float(diff.sum()),
        "cheaper_days": int((diff > 1e-8).sum()), "dearer_days": int((diff < -1e-8).sum()),
        "same_days": int((abs(diff) <= 1e-8).sum()), "median_daily_saving": float(diff.median()),
        "best_day": str(a.loc[diff.idxmax(), "date"]), "best_day_saving": float(diff.max()),
        "worst_day": str(a.loc[diff.idxmin(), "date"]), "worst_day_saving": float(diff.min()),
    })
pd.DataFrame(monthly_rows).to_csv(A / "monthly_paired_comparison.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(pair_rows).to_csv(A / "daily_paired_comparison.csv", index=False, encoding="utf-8-sig")

# Terminal inventory valuation.  The 1200-kWh reserve is not deliverable; 90%
# of inventory above it is valued at observed official-period price quantiles.
price_frame = pd.read_csv(P / "data/prepared-v1/actual_price.csv", float_precision="round_trip")
price_frame["day"] = (pd.to_datetime(price_frame.source_date) - pd.Timestamp("2025-01-01")).dt.days
price_frame["slot"] = (price_frame.source_minute.astype(int) % 1440) // 10
price = price_frame.pivot(index="day", columns="slot", values="price_yuan_per_kwh").reindex(
    index=range(365), columns=range(144)
).to_numpy()
values = {"p05": float(np.quantile(price[START:], .05)),
          "median": float(np.quantile(price[START:], .5)),
          "p95": float(np.quantile(price[START:], .95))}
terminal_candidates = [
    ("Q4-2", "P3-leaves31", row("Q4-2", "P3-leaves31")),
    ("Q4-2", "P3-full", row("Q4-2", "P3-full")),
    ("Q4-2", "P2-challenger", old_row("Q4-2", "P2")),
    ("Q4-3", "P2-full", row("Q4-3", "P2-full")),
    ("Q4-3", "P3-challenger", old_row("Q4-3", "P3")),
]
terminal_rows = []
for branch, name, item in terminal_candidates:
    for label, value in values.items():
        deliverable = .9 * max(float(item.final_kwh) - 1200, 0)
        terminal_rows.append({"branch": branch, "strategy": name, "value_case": label,
                              "price_value": value, "total_cost": float(item.total_cost),
                              "final_kwh": float(item.final_kwh), "deliverable_terminal_kwh": deliverable,
                              "inventory_adjusted_cost": float(item.total_cost) - value * deliverable})
terminal = pd.DataFrame(terminal_rows)
terminal.to_csv(A / "terminal_inventory_valuation.csv", index=False, encoding="utf-8-sig")

# High-price interval and observed consecutive-block risk summaries.
threshold = float(np.quantile(price[START:], .95))
strategy_sources = [
    ("Q4-2", "P3-leaves31", read_trace("Q4-2", "P3-leaves31")),
    ("Q4-2", "P3-full", read_trace("Q4-2", "P3-full")),
    ("Q4-2", "P2-challenger", old_trace("Q4-2", "P2")),
    ("Q4-3", "P2-full", read_trace("Q4-3", "P2-full")),
    ("Q4-3", "P3-challenger", old_trace("Q4-3", "P3")),
]
high_rows = []
block_rows = []
blocks = []
for di, day in enumerate(range(START, 365)):
    mask = price[day] >= threshold
    start = None
    for slot in range(145):
        active = slot < 144 and mask[slot]
        if active and start is None:
            start = slot
        if not active and start is not None:
            if slot - start >= 6:
                blocks.append((di, day, start, slot))
            start = None
for branch, name, trace in strategy_sources:
    execution = trace["execution"]
    order = trace["order"] if branch == "Q4-2" else trace["versions"][:, -1]
    q0 = np.zeros_like(order) if branch == "Q4-2" else trace["q0"]
    high = price[START:] >= threshold
    ordinary = price[START:] * order
    adjustment = 0 if branch == "Q4-2" else .5 * price[START:] * abs(order - q0)
    emergency = 5 * price[START:] * execution[:, :, 8]
    high_rows.append({
        "branch": branch, "strategy": name, "threshold": threshold,
        "high_intervals": int(high.sum()), "ordinary_cost_high": float(ordinary[high].sum()),
        "adjustment_cost_high": 0.0 if branch == "Q4-2" else float(adjustment[high].sum()),
        "emergency_cost_high": float(emergency[high].sum()),
        "emergency_kwh_high": float(execution[:, :, 8][high].sum()),
        "minimum_storage_high_start": float(execution[:, :, 0][high].min()),
    })
    for di, day, start, stop in blocks:
        p = price[day, start:stop]
        cost = float((p * order[di, start:stop]).sum())
        if branch == "Q4-3":
            cost += float((.5 * p * abs(order[di, start:stop] - q0[di, start:stop])).sum())
        cost += float((5 * p * execution[di, start:stop, 8]).sum())
        block_rows.append({"branch": branch, "strategy": name, "date": str((pd.Timestamp('2025-01-01') + pd.Timedelta(days=day)).date()),
                           "start_slot": start, "end_slot_exclusive": stop, "intervals": stop-start,
                           "mean_price": float(p.mean()), "start_storage_kwh": float(execution[di, start, 0]),
                           "emergency_kwh": float(execution[di, start:stop, 8].sum()), "block_cost": cost})
pd.DataFrame(high_rows).to_csv(A / "high_price_interval_risk.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(block_rows).to_csv(A / "consecutive_high_price_blocks.csv", index=False, encoding="utf-8-sig")

# Perfect-price information gap, with terminal value sensitivity kept explicit.
ideal_rows = []
for branch, selected_name in (("Q4-2", "P3-leaves31"), ("Q4-3", "P2-full")):
    selected = row(branch, selected_name)
    ideal = row(branch, "perfect-price-info")
    ideal_rows.append({"branch": branch, "selected": selected_name,
                       "selected_cost": float(selected.total_cost), "ideal_cost": float(ideal.total_cost),
                       "raw_gap": float(selected.total_cost - ideal.total_cost),
                       "raw_gap_percent": float((selected.total_cost - ideal.total_cost) / selected.total_cost * 100),
                       "selected_final_kwh": float(selected.final_kwh), "ideal_final_kwh": float(ideal.final_kwh),
                       "boundary": "unavailable future true prices; last-day beyond-year prices retain selected forecast"})
pd.DataFrame(ideal_rows).to_csv(A / "perfect_price_information_gap.csv", index=False, encoding="utf-8-sig")

# Concise machine-readable conclusions.
pair = pd.DataFrame(pair_rows).set_index(["branch", "test"])
conclusions = {
    "verification": verification["status"],
    "Q4-2": {
        "recommended_version": "P3-leaves31",
        "saving_vs_P3_full": float(row("Q4-2", "P3-full").total_cost - row("Q4-2", "P3-leaves31").total_cost),
        "mae_change": float(row("Q4-2", "P3-leaves31").price_mae - row("Q4-2", "P3-full").price_mae),
        "top5_mae_change": float(row("Q4-2", "P3-leaves31").top5_price_mae - row("Q4-2", "P3-full").top5_price_mae),
        "cheaper_days": int(pair.loc[("Q4-2", "P3-leaves31"), "cheaper_days"]),
        "dearer_days": int(pair.loc[("Q4-2", "P3-leaves31"), "dearer_days"]),
        "feature_boundary": "history-only nearly matches total cost but has worse price errors; tree-feature contributions interact and are not causal",
    },
    "Q4-3": {
        "recommended_version": "P2-full",
        "residual_a10_cost_increase": float(row("Q4-3", "P2-residual-a10").total_cost - row("Q4-3", "P2-full").total_cost),
        "residual_a10_emergency_increase_kwh": float(row("Q4-3", "P2-residual-a10").emergency_kwh - row("Q4-3", "P2-full").emergency_kwh),
        "freeze_midnight_cost_increase": float(row("Q4-3", "P2-freeze-midnight-price").total_cost - row("Q4-3", "P2-full").total_cost),
        "omit_12_cost_change": float(row("Q4-3", "P2-omit-12-price-update").total_cost - row("Q4-3", "P2-full").total_cost),
        "information_boundary": "release omissions overlap and must not be added; supply and inventory updates remain enabled",
    },
    "perfect_price_information": ideal_rows,
    "cross_year_boundary": "one 2025 rolling year; no external-year generalization",
}
dump(A / "summary.json", conclusions)

# Figure 1: model deepening and validation trade-offs.
labels42 = {"P3-no-net": "去掉净负荷", "P3-history-only": "仅历史价格",
            "P3-window28": "28天窗口", "P3-window84": "84天窗口",
            "P3-leaves7": "7叶节点", "P3-leaves31": "31叶节点"}
labels43 = {"P2-residual-a10": "残差式\nλ=10", "P2-residual-no-net": "残差式\n无净负荷",
            "P2-residual-a1": "残差式\nλ=1", "P2-residual-a100": "残差式\nλ=100"}
fig, axes = plt.subplots(2, 2, figsize=(11.4, 7.5))
part = q42[q42.strategy != "P3-full"].set_index("strategy").loc[list(labels42)]
colors = ["#2E86AB" if v < 0 else "#D95F02" for v in part.cost_change_vs_full]
axes[0,0].bar(range(len(part)), part.cost_change_vs_full / 1e4, color=colors)
axes[0,0].axhline(0, color="black", linewidth=.8)
axes[0,0].set_xticks(range(len(part)), [labels42[x] for x in part.index], rotation=18, ha="right")
axes[0,0].set_ylabel("相对原方案费用变化（万元）")
axes[0,0].set_title("零点分支：特征与参数变化")

x = np.arange(len(part)); w=.36
axes[0,1].bar(x-w/2, part.price_mae, w, label="全部时段", color="#4C78A8")
axes[0,1].bar(x+w/2, part.top5_price_mae, w, label="真实高价前5%", color="#F58518")
axes[0,1].axhline(row("Q4-2", "P3-full").price_mae, color="#4C78A8", linestyle="--", linewidth=1)
axes[0,1].axhline(row("Q4-2", "P3-full").top5_price_mae, color="#F58518", linestyle="--", linewidth=1)
axes[0,1].set_xticks(x, [labels42[z] for z in part.index], rotation=18, ha="right")
axes[0,1].set_ylabel("价格平均绝对误差（元/kWh）")
axes[0,1].set_title("费用接近不代表价格误差接近")
axes[0,1].legend(frameon=False)

part = q43s[q43s.strategy != "P2-full"].set_index("strategy").loc[list(labels43)]
colors = ["#2E86AB" if v < 0 else "#D95F02" for v in part.cost_change_vs_full]
axes[1,0].bar(range(len(part)), part.cost_change_vs_full / 1e4, color=colors)
axes[1,0].axhline(0, color="black", linewidth=.8)
axes[1,0].set_xticks(range(len(part)), [labels43[x] for x in part.index])
axes[1,0].set_ylabel("相对原方案费用变化（万元）")
axes[1,0].set_title("日内分支：残差式简化没有降低费用")

part = q43i[q43i.strategy != "P2-full"].copy()
info_labels = ["只用零点\n价格判断", "取消6点\n价格更新", "取消12点\n价格更新", "取消18点\n价格更新"]
axes[1,1].bar(range(len(part)), part.cost_change_vs_full, color=["#D95F02" if v>0 else "#2E86AB" for v in part.cost_change_vs_full])
axes[1,1].axhline(0, color="black", linewidth=.8)
axes[1,1].set_xticks(range(len(part)), info_labels)
axes[1,1].set_ylabel("相对完整方案费用变化（元）")
axes[1,1].set_title("日内价格更新的边际价值很小")
for ax in axes.ravel():
    ax.grid(axis="y", color="#DDDDDD", linewidth=.7)
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(F / f"01_deepening_validation.{ext}", bbox_inches="tight")
plt.close(fig)

# Figure 2: terminal valuation and perfect-information headroom.
fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.5))
for branch, names, colors in [
    ("Q4-2", ["P3-leaves31", "P3-full", "P2-challenger"], ["#D95319", "#F0A35E", "#2878B5"]),
    ("Q4-3", ["P2-full", "P3-challenger"], ["#2878B5", "#D95319"]),
]:
    sub = terminal[terminal.branch == branch]
    ax = axes[0] if branch == "Q4-2" else axes[1]
    for name, color in zip(names, colors):
        p = sub[sub.strategy == name].sort_values("price_value")
        ax.plot(p.price_value, p.inventory_adjusted_cost / 1e4, marker="o", label=name, color=color)
    ideal = row(branch, "perfect-price-info")
    ax.axhline(ideal.total_cost / 1e4, color="#777777", linestyle="--", label="完美价格信息（未计期末值）")
    ax.set_xlabel("期末可用电量估值（元/kWh）")
    ax.set_ylabel("扣除期末电量价值后的费用（万元）")
    ax.set_title("零点一次订电" if branch == "Q4-2" else "日内可调整")
    ax.grid(color="#DDDDDD", linewidth=.7)
    ax.legend(frameon=False, fontsize=8)
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(F / f"02_terminal_value_and_information_gap.{ext}", bbox_inches="tight")
plt.close(fig)

inputs = [O / "summary.json", O / "verification.json", P / "data/prepared-v1/actual_price.csv"]
outputs = sorted(list(A.glob("*")) + list(F.glob("*.png")) + list(F.glob("*.pdf")))

def display_path(path):
    """Keep run-local paths short and project inputs traceable."""
    try:
        return str(path.relative_to(R))
    except ValueError:
        return str(path.relative_to(P))

dump(F / "manifest.json", {
    "status": "generated_from_verified_results_no_fit_no_solve",
    "script": {"path": "analyze_results.py", "sha256": sha(__file__)},
    "inputs": [{"path": display_path(x), "sha256": sha(x)} for x in inputs],
    "outputs": [{"path": display_path(x), "sha256": sha(x)} for x in outputs],
    "boundary": "Observed 2025 results and explicit perfect-price information references only; no candidate 4, refitting or optimization added."
})
print(json.dumps({"status": "complete", "analysis_files": len(list(A.iterdir())), "figures": 2}, ensure_ascii=False))
