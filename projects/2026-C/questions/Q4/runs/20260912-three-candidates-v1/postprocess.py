"""Explain and plot the saved Q4 P1--P3 comparison without refitting or resolving.

All cost comparisons use the common 2025-02-01 storage state.  This script only
reads saved forecasts, models and dispatch traces; it creates summaries and
figures for interpretation.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import hashlib
import json

import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager


R = Path(__file__).resolve().parent
O = R / "outputs"
C = O / "common_start"
I = R / "interpretation"
F = R / "figures-v1"
I.mkdir(exist_ok=True)
F.mkdir(exist_ok=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


font_path = Path(r"C:\Windows\Fonts\simsun.ttc")
if font_path.exists():
    font_manager.fontManager.addfont(font_path)
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=font_path).get_name()
plt.rcParams.update({
    "axes.unicode_minus": False,
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "legend.fontsize": 9,
    "figure.dpi": 140,
    "savefig.dpi": 300,
})


common = json.loads((C / "summary.json").read_text(encoding="utf-8"))
rows = pd.DataFrame(common["results"])
rows["branch_label"] = rows.branch.map({"Q4-2": "零点一次订电", "Q4-3": "日内可调整"})

# Common-start daily and monthly comparisons.
daily_frames = []
for branch in ("Q4-2", "Q4-3"):
    for candidate in ("P1", "P2", "P3"):
        frame = pd.read_csv(C / f"{branch}-{candidate}.daily.csv", float_precision="round_trip")
        frame["date"] = pd.to_datetime(frame.date)
        frame["month"] = frame.date.dt.month
        daily_frames.append(frame)
daily = pd.concat(daily_frames, ignore_index=True)
monthly = daily.groupby(["branch", "candidate", "month"], as_index=False).agg(
    total_cost=("total_cost", "sum"),
    ordinary_cost=("ordinary_cost", "sum"),
    adjustment_cost=("adjustment_cost", "sum"),
    emergency_cost=("emergency_cost", "sum"),
    emergency_kwh=("emergency_kwh", "sum"),
)
base_month = monthly[monthly.candidate == "P1"][["branch", "month", "total_cost"]].rename(
    columns={"total_cost": "p1_total_cost"}
)
monthly = monthly.merge(base_month, on=["branch", "month"])
monthly["saving_vs_p1"] = monthly.p1_total_cost - monthly.total_cost
monthly.to_csv(I / "monthly_common_start.csv", index=False, encoding="utf-8-sig")

wide = daily.pivot(index=["branch", "date"], columns="candidate", values="total_cost").reset_index()
for candidate in ("P2", "P3"):
    wide[f"saving_{candidate}_vs_P1"] = wide.P1 - wide[candidate]
wide.to_csv(I / "daily_pairwise_common_start.csv", index=False, encoding="utf-8-sig")

# Ridge coefficients across rolling fits.  Because several curve features are
# strongly related, the table is descriptive and must not be read causally.
fit_rows = [json.loads(x) for x in (O / "price_fit_log.jsonl").read_text(encoding="utf-8").splitlines()]
p2_long = []
for record in fit_rows:
    if record["candidate"] != "P2":
        continue
    for feature, coefficient in record["coefficients_original"].items():
        p2_long.append({
            "branch": record["branch"], "cutoff_day": record["cutoff_day"],
            "feature": feature, "coefficient": coefficient,
        })
p2_long = pd.DataFrame(p2_long)
p2_summary = p2_long.groupby(["branch", "feature"], as_index=False).coefficient.agg(
    fits="count", median="median", mean="mean", std="std", minimum="min", maximum="max",
)
sign = p2_long.assign(positive=lambda x: x.coefficient > 0).groupby(
    ["branch", "feature"], as_index=False
).positive.mean().rename(columns={"positive": "positive_share"})
p2_summary = p2_summary.merge(sign, on=["branch", "feature"])
p2_summary.to_csv(I / "p2_coefficient_stability.csv", index=False, encoding="utf-8-sig")

# Count which features appear in P3 tree splits.  Split frequency describes the
# fitted algorithm's use of a feature; it is not a causal or permutation effect.
p3_usage = []
for record in fit_rows:
    if record["candidate"] != "P3":
        continue
    item = joblib.load(R / record["model_path"])
    model, features = item["model"], item["features"]
    counts = Counter()
    gains = Counter()
    for stage in model._predictors:
        for predictor in stage:
            nodes = predictor.nodes
            fields = nodes.dtype.names
            nonleaf = nodes["is_leaf"] == 0
            for node in nodes[nonleaf]:
                feature = features[int(node["feature_idx"])]
                counts[feature] += 1
                if "gain" in fields and np.isfinite(float(node["gain"])):
                    gains[feature] += max(float(node["gain"]), 0.0)
    for feature in features:
        p3_usage.append({
            "branch": record["branch"], "cutoff_day": record["cutoff_day"],
            "feature": feature, "split_count": counts[feature], "nonnegative_gain_sum": gains[feature],
        })
p3_usage = pd.DataFrame(p3_usage)
p3_summary = p3_usage.groupby(["branch", "feature"], as_index=False).agg(
    split_count=("split_count", "sum"), gain_sum=("nonnegative_gain_sum", "sum"), fits=("cutoff_day", "count")
)
p3_summary["split_share"] = p3_summary.split_count / p3_summary.groupby("branch").split_count.transform("sum")
p3_summary["gain_share"] = p3_summary.gain_sum / p3_summary.groupby("branch").gain_sum.transform("sum")
p3_summary.to_csv(I / "p3_split_usage.csv", index=False, encoding="utf-8-sig")

# Metrics from the causal full run are unaffected by the common storage-state
# control because the price forecasts are identical.
forecast_metrics = pd.DataFrame(json.loads((O / "summary.json").read_text(encoding="utf-8"))["candidates"])[
    ["branch", "candidate", "price_mae", "price_rmse", "top5_price_mae", "evening_price_mae", "price_bias"]
]
forecast_metrics.to_csv(I / "price_forecast_metrics.csv", index=False, encoding="utf-8-sig")


def result(branch: str, candidate: str) -> pd.Series:
    return rows[(rows.branch == branch) & (rows.candidate == candidate)].iloc[0]


analysis = {"comparison_basis": {
    "period": common["official_period"],
    "common_initial_kwh": common["common_initial_kwh"],
    "price_models_refit": 0,
    "lp_calls_in_common_start_control": common["lp_calls"],
    "independent_verification": json.loads((O / "verification.json").read_text(encoding="utf-8"))["status"],
}, "branches": {}}
for branch in ("Q4-2", "Q4-3"):
    b = {}
    p1, p2, p3 = (result(branch, x) for x in ("P1", "P2", "P3"))
    for label, row in (("P1", p1), ("P2", p2), ("P3", p3)):
        b[label] = {k: float(row[k]) if k != "emergency_days" else int(row[k]) for k in (
            "total_cost", "ordinary_cost", "adjustment_cost", "emergency_cost",
            "emergency_kwh", "unused_order_kwh", "unused_pv_kwh", "emergency_days",
        )}
    b["P2_vs_P1"] = {
        "saving_yuan": float(p1.total_cost - p2.total_cost),
        "saving_percent": float((p1.total_cost - p2.total_cost) / p1.total_cost * 100),
    }
    b["P3_vs_P2"] = {
        "saving_yuan": float(p2.total_cost - p3.total_cost),
        "saving_percent": float((p2.total_cost - p3.total_cost) / p2.total_cost * 100),
        "emergency_kwh_change": float(p3.emergency_kwh - p2.emergency_kwh),
        "emergency_days_change": int(p3.emergency_days - p2.emergency_days),
    }
    analysis["branches"][branch] = b
analysis["interpretation_boundary"] = [
    "P2 coefficients summarize rolling associations after standard ridge fitting; correlated curve features prevent a causal reading of any one coefficient.",
    "P3 split counts and gain shares only show where the fitted trees split; they do not prove causal contribution.",
    "All results are an in-year rolling comparison on 2025 data and do not establish cross-year generalization.",
]
dump(I / "analysis.json", analysis)


# Figure 1: total cost and non-ordinary components.
colors = {"P1": "#999999", "P2": "#2878B5", "P3": "#D95319"}
fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), gridspec_kw={"width_ratios": [1.12, 1]})
ax = axes[0]
x = np.arange(2)
width = 0.24
for j, candidate in enumerate(("P1", "P2", "P3")):
    vals = [result(branch, candidate).total_cost / 1e4 for branch in ("Q4-2", "Q4-3")]
    bars = ax.bar(x + (j - 1) * width, vals, width, label=candidate, color=colors[candidate])
    ax.bar_label(bars, labels=[f"{v:.2f}" for v in vals], padding=3, fontsize=8)
ax.set_xticks(x, ["零点一次订电", "日内可调整"])
ax.set_ylabel("2—12月总费用（万元）")
ax.set_title("同一起始储电量下的总费用")
ax.set_ylim(0, max(rows.total_cost) / 1e4 * 1.13)
ax.grid(axis="y", color="#DDDDDD", linewidth=.7)
ax.legend(frameon=False, ncol=3, loc="upper center")

ax = axes[1]
labels, emergency, adjustment, barcolors = [], [], [], []
for branch in ("Q4-2", "Q4-3"):
    for candidate in ("P1", "P2", "P3"):
        row = result(branch, candidate)
        labels.append(f"{candidate}\n{'零点' if branch == 'Q4-2' else '日内'}")
        emergency.append(row.emergency_cost / 1e4)
        adjustment.append(row.adjustment_cost / 1e4)
        barcolors.append(colors[candidate])
xx = np.arange(len(labels))
ax.bar(xx, emergency, color=barcolors, label="紧急购电费")
ax.bar(xx, adjustment, bottom=emergency, color=barcolors, alpha=.42, hatch="///", label="调整费")
ax.set_xticks(xx, labels)
ax.set_ylabel("费用（万元）")
ax.set_title("紧急购电费与调整费")
ax.grid(axis="y", color="#DDDDDD", linewidth=.7)
ax.legend(frameon=False, loc="upper right")
fig.tight_layout()
for suffix in ("png", "pdf"):
    fig.savefig(F / f"01_candidate_costs.{suffix}", bbox_inches="tight")
plt.close(fig)

# Figure 2: monthly savings and price-prediction errors.
fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.6))
ax = axes[0]
styles = {"Q4-2": "-", "Q4-3": "--"}
for branch in ("Q4-2", "Q4-3"):
    for candidate in ("P2", "P3"):
        part = monthly[(monthly.branch == branch) & (monthly.candidate == candidate)].sort_values("month")
        ax.plot(part.month, part.saving_vs_p1 / 1e4, marker="o", linewidth=1.8,
                color=colors[candidate], linestyle=styles[branch],
                label=f"{candidate}·{'零点' if branch == 'Q4-2' else '日内'}")
ax.axhline(0, color="black", linewidth=.8)
ax.set_xticks(range(2, 13))
ax.set_xlabel("月份")
ax.set_ylabel("相对P1节省（万元）")
ax.set_title("节费并非每个月都稳定出现")
ax.grid(color="#DDDDDD", linewidth=.7)
ax.legend(frameon=False, ncol=2, fontsize=8)

ax = axes[1]
metrics = ["price_mae", "top5_price_mae", "evening_price_mae"]
metric_labels = ["全部时段", "真实高价前5%", "19—22时"]
xx = np.arange(len(metrics))
width = .12
positions = []
for bi, branch in enumerate(("Q4-2", "Q4-3")):
    for ci, candidate in enumerate(("P1", "P2", "P3")):
        row = forecast_metrics[(forecast_metrics.branch == branch) & (forecast_metrics.candidate == candidate)].iloc[0]
        offset = (bi * 3 + ci - 2.5) * width
        ax.bar(xx + offset, [row[m] for m in metrics], width,
               color=colors[candidate], alpha=1 if branch == "Q4-2" else .48,
               hatch=None if branch == "Q4-2" else "///",
               label=f"{candidate}·{'零点' if branch == 'Q4-2' else '日内'}")
ax.set_xticks(xx, metric_labels)
ax.set_ylabel("价格平均绝对误差（元/kWh）")
ax.set_title("P3预测更准，但费用优势很小")
ax.grid(axis="y", color="#DDDDDD", linewidth=.7)
ax.legend(frameon=False, ncol=2, fontsize=7.5)
fig.tight_layout()
for suffix in ("png", "pdf"):
    fig.savefig(F / f"02_savings_and_price_errors.{suffix}", bbox_inches="tight")
plt.close(fig)


inputs = [C / "summary.json", C / "comparison.csv", O / "summary.json", O / "price_fit_log.jsonl", O / "verification.json"]
outputs = sorted([p for p in I.iterdir() if p.is_file()] + [p for p in F.iterdir() if p.is_file()])
manifest = {
    "status": "generated_from_verified_saved_results_no_refit_no_resolve",
    "script": {"path": str(Path(__file__).relative_to(R)), "sha256": sha256(Path(__file__))},
    "inputs": [{"path": str(p.relative_to(R)), "sha256": sha256(p)} for p in inputs],
    "outputs": [{"path": str(p.relative_to(R)), "sha256": sha256(p)} for p in outputs],
    "figure_notes": {
        "01_candidate_costs": "Common-start total costs and billed non-ordinary components for P1--P3 in both branches.",
        "02_savings_and_price_errors": "Monthly savings versus P1 and causal rolling price forecast errors; negative savings are retained.",
    },
    "boundary": "The charts summarize saved runs; they do not add candidates, refit models, rerun optimization, or prove cross-year generalization.",
}
dump(F / "manifest.json", manifest)
print(json.dumps({"status": "complete", "interpretation_files": len(list(I.iterdir())), "figures": 2}, ensure_ascii=False))
