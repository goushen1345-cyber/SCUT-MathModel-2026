# -*- coding: utf-8 -*-
"""Q3: classify unknown glass samples + sensitivity."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils_common import (  # noqa: E402
    COMPONENTS,
    FIG,
    PROC,
    TAB,
    append_summary,
    log,
    save_json,
    setup_plot_style,
)

FEATURE_MAIN = ["SiO2", "K2O", "PbO", "BaO", "CaO", "Al2O3", "P2O5", "CuO", "Fe2O3", "MgO"]


def rule_predict(df):
    score = df["PbO"] + df["BaO"]
    pred = np.where(score >= 5.0, "铅钡", "高钾")
    return pred


def main():
    setup_plot_style()
    log("=== Q3 start ===")
    train = pd.read_csv(PROC / "labeled_filled.csv")
    unk = pd.read_csv(PROC / "unknown_filled.csv")
    feats = [c for c in FEATURE_MAIN if c in train.columns]

    Xtr = train[feats].values
    ytr = train["类型"].values
    Xte = unk[feats].values

    scaler = StandardScaler().fit(Xtr)
    Xtr_s = scaler.transform(Xtr)
    Xte_s = scaler.transform(Xte)

    rf = RandomForestClassifier(n_estimators=300, random_state=42)
    rf.fit(Xtr_s, ytr)
    proba = rf.predict_proba(Xte_s)
    classes = list(rf.classes_)
    pred_rf = rf.predict(Xte_s)

    svm = SVC(kernel="rbf", probability=True, random_state=42)
    svm.fit(Xtr_s, ytr)
    pred_svm = svm.predict(Xte_s)
    proba_svm = svm.predict_proba(Xte_s)

    pred_rule = rule_predict(unk)

    rows = []
    for i, r in unk.iterrows():
        idx = list(unk.index).index(i)
        p_rf = dict(zip(classes, proba[idx]))
        p_svm = dict(zip(list(svm.classes_), proba_svm[idx]))
        rows.append(
            {
                "文物编号": r["文物编号"],
                "表面风化": r["表面风化"],
                "规则预测": pred_rule[idx],
                "RF预测": pred_rf[idx],
                "SVM预测": pred_svm[idx],
                "RF_高钾概率": float(p_rf.get("高钾", 0)),
                "RF_铅钡概率": float(p_rf.get("铅钡", 0)),
                "SVM_高钾概率": float(p_svm.get("高钾", 0)),
                "SVM_铅钡概率": float(p_svm.get("铅钡", 0)),
                "最终判定": pred_rf[idx],
                "置信度": float(max(p_rf.values())),
                "SiO2": float(r["SiO2"]),
                "K2O": float(r["K2O"]),
                "PbO": float(r["PbO"]),
                "BaO": float(r["BaO"]),
                "成分和": float(r["成分和"]),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(TAB / "q3_predictions.csv", index=False, encoding="utf-8-sig")

    # agreement
    agree = {
        "RF_vs_SVM": float((out["RF预测"] == out["SVM预测"]).mean()),
        "RF_vs_规则": float((out["RF预测"] == out["规则预测"]).mean()),
        "n": int(len(out)),
        "n_high_k": int((out["最终判定"] == "高钾").sum()),
        "n_pb_ba": int((out["最终判定"] == "铅钡").sum()),
        "mean_confidence": float(out["置信度"].mean()),
        "min_confidence": float(out["置信度"].min()),
    }

    # sensitivity: retrain after dropping each train sample / noise on test
    rng = np.random.default_rng(0)
    flip_counts = {aid: 0 for aid in out["文物编号"]}
    n_mc = 100
    for _ in range(n_mc):
        Xn = Xte * (1 + rng.normal(0, 0.05, size=Xte.shape))
        Xn = np.clip(Xn, 0, None)
        Xn_s = scaler.transform(Xn)
        pred = rf.predict(Xn_s)
        for aid, p0, p1 in zip(out["文物编号"], out["最终判定"], pred):
            if p0 != p1:
                flip_counts[aid] += 1
    sens = out[["文物编号", "最终判定", "置信度"]].copy()
    sens["翻转次数_噪声5pct_100次"] = sens["文物编号"].map(flip_counts)
    sens["翻转率"] = sens["翻转次数_噪声5pct_100次"] / n_mc
    sens.to_csv(TAB / "q3_sensitivity_flip.csv", index=False, encoding="utf-8-sig")

    # leave-one-train-out stability of predictions
    from sklearn.model_selection import LeaveOneOut

    loo = LeaveOneOut()
    stab = np.zeros((len(unk), 2))  # count highK / pb
    for tr, te in loo.split(Xtr_s):
        rf2 = RandomForestClassifier(n_estimators=100, random_state=42)
        rf2.fit(Xtr_s[tr], ytr[tr])
        pr = rf2.predict(Xte_s)
        for i, p in enumerate(pr):
            if p == "高钾":
                stab[i, 0] += 1
            else:
                stab[i, 1] += 1
    stab_df = out[["文物编号"]].copy()
    stab_df["LOO训练_高钾票数"] = stab[:, 0]
    stab_df["LOO训练_铅钡票数"] = stab[:, 1]
    stab_df["稳定标签"] = np.where(stab[:, 0] >= stab[:, 1], "高钾", "铅钡")
    stab_df["稳定比例"] = np.maximum(stab[:, 0], stab[:, 1]) / stab.sum(axis=1)
    stab_df.to_csv(TAB / "q3_loo_train_stability.csv", index=False, encoding="utf-8-sig")

    # figures
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(out))
    ax.bar(x - 0.2, out["RF_高钾概率"], 0.4, label="高钾概率", color="#2a6f97")
    ax.bar(x + 0.2, out["RF_铅钡概率"], 0.4, label="铅钡概率", color="#c1121f")
    ax.set_xticks(x)
    ax.set_xticklabels(out["文物编号"])
    ax.set_ylabel("概率")
    ax.set_title("未知样本随机森林类别概率")
    ax.legend()
    fig.savefig(FIG / "q3_rf_proba.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=sens, x="文物编号", y="翻转率", hue="最终判定", dodge=False, ax=ax)
    ax.set_title("未知样本分类灵敏度（5%相对噪声，翻转率）")
    ax.set_ylabel("翻转率")
    fig.savefig(FIG / "q3_flip_rate.png")
    plt.close(fig)

    # scatter PbO+BaO vs K2O with train+unk
    fig, ax = plt.subplots(figsize=(8, 6))
    for typ, c in [("高钾", "#2a6f97"), ("铅钡", "#c1121f")]:
        m = train["类型"] == typ
        ax.scatter(train.loc[m, "K2O"], train.loc[m, "PbO"] + train.loc[m, "BaO"], c=c, alpha=0.5, label=f"训练-{typ}")
    for _, r in out.iterrows():
        ax.scatter(r["K2O"], r["PbO"] + r["BaO"], marker="*", s=180, edgecolors="k",
                   c="#2a6f97" if r["最终判定"] == "高钾" else "#c1121f")
        ax.text(r["K2O"] + 0.1, r["PbO"] + r["BaO"] + 0.3, r["文物编号"], fontsize=8)
    ax.set_xlabel("K2O (%)")
    ax.set_ylabel("PbO+BaO (%)")
    ax.set_title("未知样本在关键成分平面上的位置")
    ax.legend()
    fig.savefig(FIG / "q3_feature_plane.png")
    plt.close(fig)

    agree["mean_flip_rate"] = float(sens["翻转率"].mean())
    agree["mean_loo_stability"] = float(stab_df["稳定比例"].mean())
    save_json(agree, TAB / "q3_summary.json")

    append_summary(
        "## Q3\n"
        f"- 未知有效样本 {agree['n']}：判定高钾 {agree['n_high_k']}，铅钡 {agree['n_pb_ba']}。\n"
        f"- RF与SVM一致率 {agree['RF_vs_SVM']:.3f}，RF与规则一致率 {agree['RF_vs_规则']:.3f}；"
        f"平均置信度 {agree['mean_confidence']:.3f}，最低 {agree['min_confidence']:.3f}。\n"
        f"- 5%噪声平均翻转率 {agree['mean_flip_rate']:.3f}；训练LOO平均稳定比例 {agree['mean_loo_stability']:.3f}。\n"
    )
    log("Q3 done")


if __name__ == "__main__":
    main()
