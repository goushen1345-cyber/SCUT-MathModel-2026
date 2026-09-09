# -*- coding: utf-8 -*-
"""Advanced comparisons, ablation, robustness, and roadmap figure."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import LeaveOneOut
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils_common import (  # noqa: E402
    COMPONENTS,
    FIG,
    OUT,
    PROC,
    TAB,
    append_summary,
    load_json,
    log,
    save_json,
    setup_plot_style,
)

FEATURE_MAIN = ["SiO2", "K2O", "PbO", "BaO", "CaO", "Al2O3", "P2O5", "CuO", "Fe2O3", "MgO"]


def ablation_features(df):
    y = df["类型"].values
    feats_sets = {
        "仅SiO2+K2O": ["SiO2", "K2O"],
        "仅PbO+BaO": ["PbO", "BaO"],
        "核心四成分": ["SiO2", "K2O", "PbO", "BaO"],
        "全部主特征": FEATURE_MAIN,
    }
    rows = []
    loo = LeaveOneOut()
    for name, feats in feats_sets.items():
        X = StandardScaler().fit_transform(df[feats].values)
        pred = np.empty(len(y), dtype=object)
        clf = RandomForestClassifier(n_estimators=150, random_state=42)
        for tr, te in loo.split(X):
            clf.fit(X[tr], y[tr])
            pred[te] = clf.predict(X[te])
        rows.append(
            {
                "特征集": name,
                "LOO准确率": float(accuracy_score(y, pred)),
                "MacroF1": float(f1_score(y, pred, average="macro")),
                "特征数": len(feats),
            }
        )
    return pd.DataFrame(rows)


def weathering_stratified_acc(df):
    """Train on all, evaluate LOO overall and by weathering."""
    feats = FEATURE_MAIN
    X = StandardScaler().fit_transform(df[feats].values)
    y = df["类型"].values
    pred = np.empty(len(y), dtype=object)
    loo = LeaveOneOut()
    clf = RandomForestClassifier(n_estimators=200, random_state=42)
    for tr, te in loo.split(X):
        clf.fit(X[tr], y[tr])
        pred[te] = clf.predict(X[te])
    rows = [{"子集": "全体", "n": len(y), "准确率": float(accuracy_score(y, pred))}]
    for w in ["风化", "无风化"]:
        m = df["点位风化标签"].values == w
        if m.sum():
            rows.append({"子集": w, "n": int(m.sum()), "准确率": float(accuracy_score(y[m], pred[m]))})
    return pd.DataFrame(rows), pred


def mc_robust_classification(df, n=200, noise=0.08):
    rng = np.random.default_rng(123)
    feats = FEATURE_MAIN
    y = df["类型"].values
    scaler = StandardScaler().fit(df[feats].values)
    X0 = scaler.transform(df[feats].values)
    clf = RandomForestClassifier(n_estimators=120, random_state=42).fit(X0, y)
    accs = []
    for _ in range(n):
        Xn = df[feats].values * (1 + rng.normal(0, noise, size=df[feats].shape))
        Xn = np.clip(Xn, 0, None)
        pred = clf.predict(scaler.transform(Xn))
        accs.append(accuracy_score(y, pred))
    return {
        "mc_n": n,
        "noise": noise,
        "mean": float(np.mean(accs)),
        "std": float(np.std(accs)),
        "p05": float(np.quantile(accs, 0.05)),
        "p95": float(np.quantile(accs, 0.95)),
        "prob_above_0.9": float(np.mean(np.array(accs) >= 0.9)),
        "accs": accs,
    }


def draw_roadmap():
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6)
    ax.axis("off")
    boxes = [
        (0.3, 3.5, "数据清洗\n有效成分和\n[85%,105%]"),
        (2.5, 3.5, "Q1 风化关联\n与成分反演"),
        (4.7, 3.5, "Q2 类型分类\n与亚类划分"),
        (6.9, 3.5, "Q3 未知鉴别\n与置信度"),
        (9.1, 3.5, "Q4 相关结构\n差异比较"),
        (4.7, 1.2, "检验闭环：对照/消融/灵敏度/蒙特卡洛鲁棒"),
    ]
    for x, y, t in boxes:
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (x, y), 1.9, 1.5, boxstyle="round,pad=0.05,rounding_size=0.15",
                facecolor="#dceaf5", edgecolor="#2a6f97", lw=1.5
            )
        )
        ax.text(x + 0.95, y + 0.75, t, ha="center", va="center", fontsize=10)
    for x1, x2 in [(2.2, 2.5), (4.4, 4.7), (6.6, 6.9), (8.8, 9.1)]:
        ax.annotate("", xy=(x2, 4.25), xytext=(x1, 4.25),
                    arrowprops=dict(arrowstyle="->", color="#333", lw=1.5))
    ax.annotate("", xy=(5.65, 2.7), xytext=(5.65, 3.5),
                arrowprops=dict(arrowstyle="->", color="#c1121f", lw=1.5))
    ax.set_title("技术路线：评价风化—筛选分类—优化亚类—鉴别未知—比较关联—闭环检验", fontsize=12)
    fig.savefig(FIG / "roadmap_pipeline.png")
    plt.close(fig)


def write_innovation(ab, mc, q1, q2, q3, q4, strat):
    # compute lifts
    full = float(ab.loc[ab["特征集"] == "全部主特征", "LOO准确率"].iloc[0])
    core4 = float(ab.loc[ab["特征集"] == "核心四成分", "LOO准确率"].iloc[0])
    only_pb = float(ab.loc[ab["特征集"] == "仅PbO+BaO", "LOO准确率"].iloc[0])
    text = f"""# 创新点（可验证）

1. **风化分层统计 + 类型条件风化因子反演**  
   相对“无校正直接把风化样品当原始成分”，对高钾/铅钡分别估计风化因子并归一化反演；方法对比见 `q1_method_compare.csv` / `q1_method_compare.png`。  
   证据：Q1 方法对比中风化因子反演 MAE 低于无校正（见 `output/tables/q1_method_compare.csv`）。

2. **可解释规则与机器学习双轨分类，并做特征消融**  
   化学阈值规则（PbO+BaO）与随机森林/决策树并行；消融显示“全部主特征/核心四成分”相对“仅PbO+BaO”的增益。  
   证据：`q2_method_compare.png`，`ablation_features.csv`：全部主特征 LOO={full:.4f}，核心四成分={core4:.4f}，仅PbO+BaO={only_pb:.4f}。

3. **未知样本多模型一致性 + 噪声翻转率 + 训练LOO稳定性**  
   对附件3给出 RF/SVM/规则三路判定，并以5%相对噪声蒙特卡洛翻转率与训练留一稳定性量化敏感性。  
   证据：`q3_rf_proba.png`，`q3_flip_rate.png`，`q3_sensitivity_flip.csv`；平均翻转率见 `q3_summary.json`。

4. **类别条件 Spearman 网络 + Mantel 相关结构差异性检验**  
   不只给两张热力图，还用 Mantel 检验与 |Δr| 排序定量比较高钾/铅钡关联结构差异。  
   证据：`q4_corr_diff_heatmap.png`，`q4_top_diff_pairs.png`，Mantel r={q4['mantel_r']:.4f}, p={q4['mantel_p']:.4f}。

5. **风化分层分类准确率与整体噪声鲁棒性闭环**  
   检验分类是否被风化状态“带偏”，并给出噪声扰动下准确率分布。  
   证据：`adv_weather_stratified_acc.csv`，`adv_mc_acc_hist.png`；MC均值={mc['mean']:.4f}，P05–P95=[{mc['p05']:.4f},{mc['p95']:.4f}]。
"""
    (OUT / "00_innovation.md").write_text(text, encoding="utf-8")


def main():
    setup_plot_style()
    log("=== Advanced tests ===")
    df = pd.read_csv(PROC / "labeled_filled.csv")
    draw_roadmap()

    ab = ablation_features(df)
    ab.to_csv(TAB / "ablation_features.csv", index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(ab["特征集"], ab["LOO准确率"], color="#2a6f97")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("LOO准确率")
    ax.set_title("特征消融对比")
    for i, v in enumerate(ab["LOO准确率"]):
        ax.text(i, v + 0.02, f"{v:.3f}", ha="center")
    fig.savefig(FIG / "adv_ablation_features.png")
    plt.close(fig)

    strat, _ = weathering_stratified_acc(df)
    strat.to_csv(TAB / "adv_weather_stratified_acc.csv", index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(strat["子集"], strat["准确率"], color=["#577590", "#f9c74f", "#90be6d"])
    ax.set_ylim(0, 1.05)
    ax.set_title("分类准确率：全体 / 风化 / 无风化")
    fig.savefig(FIG / "adv_weather_stratified_acc.png")
    plt.close(fig)

    mc = mc_robust_classification(df)
    accs = mc.pop("accs")
    save_json(mc, TAB / "robust_mc_summary.json")
    pd.DataFrame({"acc": accs}).to_csv(TAB / "robust_mc_acc_samples.csv", index=False)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(accs, bins=15, color="#2a6f97", edgecolor="white")
    ax.axvline(mc["mean"], color="#c1121f", ls="--", label=f"均值{mc['mean']:.3f}")
    ax.set_xlabel("扰动后准确率")
    ax.set_ylabel("次数")
    ax.set_title(f"分类鲁棒性蒙特卡洛（相对噪声σ={mc['noise']}）")
    ax.legend()
    fig.savefig(FIG / "adv_mc_acc_hist.png")
    plt.close(fig)

    # aggregate existing summaries
    q1 = load_json(TAB / "q1_summary.json")
    q2 = load_json(TAB / "q2_summary.json")
    q3 = load_json(TAB / "q3_summary.json")
    q4 = load_json(TAB / "q4_summary.json")
    write_innovation(ab, mc, q1, q2, q3, q4, strat)

    # combined comparison table
    cmp = pd.read_csv(TAB / "q2_method_compare.csv")
    cmp.to_csv(TAB / "adv_method_compare_main.csv", index=False, encoding="utf-8-sig")

    append_summary(
        "## 高级检验\n"
        f"- 特征消融见 `ablation_features.csv`。\n"
        f"- 风化分层准确率：{strat.to_dict(orient='records')}\n"
        f"- MC鲁棒：均值 {mc['mean']:.4f}，P05 {mc['p05']:.4f}，P95 {mc['p95']:.4f}，"
        f"≥0.9 概率 {mc['prob_above_0.9']:.3f}。\n"
    )
    log("Advanced done")


if __name__ == "__main__":
    main()
