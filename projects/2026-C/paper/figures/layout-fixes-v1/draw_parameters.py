"""Generate the Q3 parameter-interpretability paper candidate figure."""
from pathlib import Path
import json, hashlib, os

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

HERE = Path(__file__).resolve().parent
R = HERE.parents[2] / 'questions/Q3/runs/20260911-parameter-interpretability-v1'
O = R / "outputs"
OUT = HERE
OUT.mkdir(parents=True, exist_ok=True)
verification = json.loads((O / "verification.json").read_text(encoding="utf-8"))
assert verification["status"] == "checks_completed"
data = pd.read_csv(O / "comparison.csv", float_precision="round_trip")
parameter_families = {"structure_sensitivity", "three_hour_parameter_recheck", "three_hour_parameter_refinement"}
parameter_data = data[data.family.isin(parameter_families)].copy()

font_path = Path("C:/Windows/Fonts/simsun.ttc")
font_name = FontProperties(fname=str(font_path)).get_name()
plt.rcParams.update({
    "font.family": font_name, "font.size": 10.5, "axes.unicode_minus": False,
    "text.color": "black", "axes.labelcolor": "black", "xtick.color": "black",
    "ytick.color": "black", "axes.spines.top": False, "axes.spines.right": False,
    "svg.hashsalt": "q3-parameter-interpretability-v1", "pdf.fonttype": 42
})

fig, axes = plt.subplots(2, 2, figsize=(11.2, 8.2), layout="constrained")
ax, bx, cx, dx = axes.ravel()

# (a) Quantile trade-off under the selected structural setting.
q = parameter_data[(parameter_data.history_days == 28) & (parameter_data.block_hours == 3) & (np.isclose(parameter_data.beta, .7))]
q = q.sort_values("q").drop_duplicates("q")
ordinary, emergency = q.ordinary_cost / 1e4, q.emergency_cost / 1e4
ax.bar(q.q, ordinary, width=.015, color="#4C78A8", label="普通结算")
ax.bar(q.q, emergency, bottom=ordinary, width=.015, color="#E7A35A", label="紧急购电")
best_q = q.loc[q.total_cost.idxmin()]
ax.scatter([best_q.q], [best_q.total_cost/1e4], color="#B22222", zorder=5)
ax.annotate(f"最低：{best_q.q:.2f}", (best_q.q, best_q.total_cost/1e4), xytext=(0, 12), textcoords="offset points", ha="center")
ax.set_xlabel("误差分位位置")
ax.set_ylabel("2—12月费用 / 万元")
ax.set_title("(a) 多准备与紧急补购的取舍", pad=34)
ax.legend(frameon=False, ncol=2, loc='lower center', bbox_to_anchor=(.5,1.01))
ax.set_ylim(0, float((ordinary+emergency).max())*1.14)

# (b) Recency decay comparison at q=.60.
b = parameter_data[(parameter_data.history_days == 28) & (parameter_data.block_hours == 3) & (np.isclose(parameter_data.q, .60))]
b = b.sort_values("beta").drop_duplicates("beta")
bx.plot(b.beta, b.total_cost/1e4, marker="o", color="#4C78A8", linewidth=1.8)
for _, row in b.iterrows():
    bx.annotate(f"{row.total_cost/1e4:.2f}", (row.beta, row.total_cost/1e4), xytext=(-10, 14) if np.isclose(row.beta,.8) else (0,12), textcoords="offset points", ha="right" if np.isclose(row.beta,.8) else "center")
bx.set_xticks([.7, .8, 1.0])
bx.set_xlabel("前一天误差保留的权重")
bx.set_ylabel("2—12月总费用 / 万元")
bx.set_title("(b) 近期误差应占更大作用", pad=34)
bx.margins(x=.12,y=.18)

# (c) Intraday grouping while all other tested factors stay fixed.
c = parameter_data[(parameter_data.history_days == 28) & (np.isclose(parameter_data.q, .65)) & (np.isclose(parameter_data.beta, .7))]
c = c[c.block_hours.isin([1, 2, 3, 4, 6])].sort_values("block_hours").drop_duplicates("block_hours")
cx.plot(c.block_hours, c.total_cost/1e4, marker="o", color="#4C78A8", linewidth=1.8)
best_block = c.loc[c.total_cost.idxmin()]
cx.scatter([best_block.block_hours], [best_block.total_cost/1e4], color="#B22222", zorder=5)
for _, row in c.iterrows():
    cx.annotate(f"{row.total_cost/1e4:.2f}", (row.block_hours, row.total_cost/1e4), xytext=(0, 14), textcoords="offset points", ha="center")
cx.set_xticks([1, 2, 3, 4, 6])
cx.set_xlabel("误差分组宽度 / 小时")
cx.set_ylabel("2—12月总费用 / 万元")
cx.set_title("(c) 三小时分组兼顾细节与稳定性", pad=12)
cx.margins(x=.12,y=.18)

# (d) History-window sensitivity at the two-hour setting, where all three were run.
d = parameter_data[(parameter_data.block_hours == 2) & (np.isclose(parameter_data.q, .65)) & (np.isclose(parameter_data.beta, .7))]
d = d[d.history_days.isin([14, 28, 56])].sort_values("history_days").drop_duplicates("history_days")
reference = float(d.loc[d.history_days == 28, "total_cost"].iloc[0])
change = d.total_cost - reference
colors = np.where(change <= 0, "#4C78A8", "#E7A35A")
dx.bar(d.history_days.astype(str), change, color=colors, width=.55)
dx.axhline(0, color="black", linewidth=.8)
for x, value in zip(range(len(d)), change):
    dx.text(x, value + (1 if value >= 0 else -1), f"{value:+.0f}", ha="center", va="bottom" if value >= 0 else "top")
dx.set_xlabel("历史窗口 / 天")
dx.set_ylabel("相对28天方案的费用差 / 元")
dx.set_title("(d) 14—56天内结果基本稳定", pad=12)
dx.set_ylim(0, float(change.max())+4)

fig.suptitle("问题三误差准备参数的依据（其余条件相同时比较）", fontsize=14)
files = []
for extension in ("png", "svg", "pdf"):
    path = OUT / f"02_Q3_parameter_interpretability.{extension}"
    metadata = {"Date": None} if extension == "svg" else ({"CreationDate": None, "ModDate": None} if extension == "pdf" else None)
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white", metadata=metadata)
    files.append(path)
fig.savefig(OUT/'02_Q3_parameter_interpretability_preview.png',dpi=120,bbox_inches='tight')
plt.close(fig)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


manifest = {
    "figure_id": "Q3-F04",
    "status": "generated_pending_visual_inspection",
    "source": {"outputs/comparison.csv": sha(O / "comparison.csv"), "outputs/verification.json": sha(O / "verification.json")},
    "code_sha256": sha(__file__),
    "outputs": {path.name: sha(path) for path in files},
    "font": font_name,
    "font_file": str(font_path),
    "dpi": 300,
    "not_embedded": True
}
(OUT / "parameter_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"outputs": [str(path) for path in files]}, ensure_ascii=False))
