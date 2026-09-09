# -*- coding: utf-8 -*-
"""Q2: high-K vs Pb-Ba classification rules + subclass clustering + sensitivity."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.cluster.hierarchy import dendrogram, linkage
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    silhouette_score,
)
from sklearn.model_selection import LeaveOneOut, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier, export_text

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


def rule_baseline(df: pd.DataFrame):
    """Simple chemical rule: PbO+BaO high -> 铅钡; else if K2O high -> 高钾."""
    score = df["PbO"] + df["BaO"]
    pred = np.where(score >= 5.0, "铅钡", "高钾")
    # refine: if both low, use K2O
    both_low = score < 5.0
    pred = pred.copy()
    pred[both_low & (df["K2O"].values >= 2.0)] = "高钾"
    pred[both_low & (df["K2O"].values < 2.0) & (df["SiO2"].values < 60)] = "铅钡"
    return pred


def train_classifiers(X, y):
    models = {
        "决策树": DecisionTreeClassifier(max_depth=3, random_state=42),
        "随机森林": RandomForestClassifier(n_estimators=200, random_state=42),
        "SVM_RBF": SVC(kernel="rbf", probability=True, random_state=42),
    }
    rows = []
    fitted = {}
    loo = LeaveOneOut()
    for name, clf in models.items():
        y_pred = np.empty(len(y), dtype=object)
        for train, test in loo.split(X):
            clf.fit(X[train], y[train])
            y_pred[test] = clf.predict(X[test])
        acc = accuracy_score(y, y_pred)
        f1 = f1_score(y, y_pred, average="macro")
        cm = confusion_matrix(y, y_pred, labels=["高钾", "铅钡"])
        rows.append({"方法": name, "LOO准确率": acc, "MacroF1": f1})
        fitted[name] = {
            "model": clf.fit(X, y),
            "y_pred": y_pred,
            "cm": cm,
            "acc": acc,
            "f1": f1,
        }
    # rule baseline
    # need original df for rule - handled outside
    return pd.DataFrame(rows), fitted


def select_subclass_k(X, k_range=range(2, 6)):
    best_k, best_s = 2, -1
    records = []
    for k in k_range:
        if len(X) <= k:
            continue
        lab = KMeans(n_clusters=k, n_init=20, random_state=42).fit_predict(X)
        s = silhouette_score(X, lab)
        records.append({"k": k, "silhouette": s})
        if s > best_s:
            best_k, best_s = k, s
    return best_k, best_s, pd.DataFrame(records)


def subclass_for_type(df, typ, feature_cols):
    sub = df[df["类型"] == typ].copy()
    X = StandardScaler().fit_transform(sub[feature_cols].values)
    best_k, best_s, ks = select_subclass_k(X)
    km = KMeans(n_clusters=best_k, n_init=20, random_state=42)
    sub["亚类"] = [f"{typ}-C{i+1}" for i in km.fit_predict(X)]
    # also hierarchical for comparison
    if len(sub) >= 4:
        link = linkage(X, method="ward")
        fig, ax = plt.subplots(figsize=(10, 5))
        dendrogram(link, labels=sub["采样点"].astype(str).values, leaf_rotation=90, ax=ax)
        ax.set_title(f"{typ}玻璃层次聚类树状图")
        fig.savefig(FIG / f"q2_dendrogram_{typ}.png")
        plt.close(fig)
    centers = sub.groupby("亚类")[feature_cols].mean()
    return sub, best_k, best_s, ks, centers


def main():
    setup_plot_style()
    log("=== Q2 start ===")
    df = pd.read_csv(PROC / "labeled_filled.csv")
    # use unweathered-preferring or all valid? Use all valid filled; also make unweathered-only ablation
    y = df["类型"].values
    feats = [c for c in FEATURE_MAIN if c in df.columns]
    scaler = StandardScaler()
    X = scaler.fit_transform(df[feats].values)

    rule_pred = rule_baseline(df)
    rule_acc = accuracy_score(y, rule_pred)
    rule_f1 = f1_score(y, rule_pred, average="macro")
    rule_cm = confusion_matrix(y, rule_pred, labels=["高钾", "铅钡"])

    cmp, fitted = train_classifiers(X, y)
    cmp = pd.concat(
        [
            pd.DataFrame([{"方法": "化学阈值规则", "LOO准确率": rule_acc, "MacroF1": rule_f1}]),
            cmp,
        ],
        ignore_index=True,
    )
    cmp.to_csv(TAB / "q2_method_compare.csv", index=False, encoding="utf-8-sig")

    # decision tree text rules
    dt = DecisionTreeClassifier(max_depth=3, random_state=42).fit(df[feats].values, y)
    rules_txt = export_text(dt, feature_names=feats)
    (TAB / "q2_decision_tree_rules.txt").write_text(rules_txt, encoding="utf-8")

    # feature importance
    rf = fitted["随机森林"]["model"]
    imp = pd.DataFrame({"成分": feats, "重要性": rf.feature_importances_}).sort_values(
        "重要性", ascending=False
    )
    imp.to_csv(TAB / "q2_feature_importance.csv", index=False, encoding="utf-8-sig")

    # confusion matrices
    for name, pack in [("化学阈值规则", {"cm": rule_cm}), *fitted.items()]:
        cm = pack["cm"]
        pd.DataFrame(cm, index=["真高钾", "真铅钡"], columns=["预测高钾", "预测铅钡"]).to_csv(
            TAB / f"q2_cm_{name}.csv", encoding="utf-8-sig"
        )

    # PCA scatter
    pca = PCA(n_components=2, random_state=42)
    Z = pca.fit_transform(X)
    fig, ax = plt.subplots(figsize=(8, 6))
    for typ, color in [("高钾", "#2a6f97"), ("铅钡", "#c1121f")]:
        m = y == typ
        ax.scatter(Z[m, 0], Z[m, 1], c=color, label=typ, alpha=0.8, edgecolors="white")
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)")
    ax.set_title("高钾/铅钡 PCA 投影")
    ax.legend()
    fig.savefig(FIG / "q2_pca_types.png")
    plt.close(fig)

    # method compare bar
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(cmp["方法"], cmp["LOO准确率"], color="#2a6f97")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("留一法准确率")
    ax.set_title("分类方法对比（LOO）")
    for i, v in enumerate(cmp["LOO准确率"]):
        ax.text(i, v + 0.02, f"{v:.3f}", ha="center")
    fig.savefig(FIG / "q2_method_compare.png")
    plt.close(fig)

    # importance
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=imp, x="重要性", y="成分", ax=ax, color="#577590")
    ax.set_title("随机森林成分重要性")
    fig.savefig(FIG / "q2_feature_importance.png")
    plt.close(fig)

    # subclass
    # choose features per type based on importance / domain
    sub_feats_k = ["SiO2", "K2O", "CaO", "Al2O3", "Fe2O3", "CuO"]
    sub_feats_pb = ["SiO2", "PbO", "BaO", "P2O5", "CuO", "Al2O3"]
    all_sub = []
    sub_summary = {}
    for typ, fcols in [("高钾", sub_feats_k), ("铅钡", sub_feats_pb)]:
        sub, k, s, ks, centers = subclass_for_type(df, typ, fcols)
        all_sub.append(sub)
        ks.to_csv(TAB / f"q2_subclass_kselect_{typ}.csv", index=False, encoding="utf-8-sig")
        centers.to_csv(TAB / f"q2_subclass_centers_{typ}.csv", encoding="utf-8-sig")
        sub_summary[typ] = {"best_k": int(k), "silhouette": float(s), "features": fcols, "n": int(len(sub))}
        # PCA colored by subclass
        Xs = StandardScaler().fit_transform(sub[fcols].values)
        Zs = PCA(2, random_state=42).fit_transform(Xs)
        fig, ax = plt.subplots(figsize=(8, 6))
        for lab in sorted(sub["亚类"].unique()):
            m = sub["亚类"].values == lab
            ax.scatter(Zs[m, 0], Zs[m, 1], label=lab, alpha=0.85)
        ax.legend()
        ax.set_title(f"{typ}亚类划分（K={k}, silhouette={s:.3f}）")
        fig.savefig(FIG / f"q2_subclass_pca_{typ}.png")
        plt.close(fig)

    labeled_sub = pd.concat(all_sub, ignore_index=True)
    labeled_sub.to_csv(TAB / "q2_subclass_labels.csv", index=False, encoding="utf-8-sig")

    # sensitivity: feature noise
    rng = np.random.default_rng(42)
    sens_rows = []
    best_name = cmp.sort_values("LOO准确率", ascending=False).iloc[0]["方法"]
    base_model = RandomForestClassifier(n_estimators=200, random_state=42)
    for noise in [0.0, 0.02, 0.05, 0.10, 0.15]:
        accs = []
        for _ in range(30):
            Xn = df[feats].values * (1 + rng.normal(0, noise, size=df[feats].shape))
            Xn = np.clip(Xn, 0, None)
            Xn = scaler.fit_transform(Xn)
            # LOO expensive; use 5-fold style via RF OOB-ish: train/test split repeated
            from sklearn.model_selection import StratifiedKFold

            skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=None)
            fold_acc = []
            for tr, te in skf.split(Xn, y):
                base_model.fit(Xn[tr], y[tr])
                fold_acc.append(accuracy_score(y[te], base_model.predict(Xn[te])))
            accs.append(np.mean(fold_acc))
        sens_rows.append(
            {
                "噪声水平": noise,
                "准确率均值": float(np.mean(accs)),
                "准确率标准差": float(np.std(accs)),
            }
        )
    sens = pd.DataFrame(sens_rows)
    sens.to_csv(TAB / "q2_sensitivity_noise.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(sens["噪声水平"], sens["准确率均值"], yerr=sens["准确率标准差"], marker="o", color="#2a6f97")
    ax.set_xlabel("相对噪声 σ")
    ax.set_ylabel("5折准确率")
    ax.set_title("分类鲁棒性：成分相对噪声扰动")
    fig.savefig(FIG / "q2_sensitivity_noise.png")
    plt.close(fig)

    # threshold sensitivity for rule
    thr_rows = []
    for thr in np.linspace(1, 15, 15):
        score = df["PbO"] + df["BaO"]
        pred = np.where(score >= thr, "铅钡", "高钾")
        thr_rows.append({"PbO+BaO阈值": thr, "准确率": accuracy_score(y, pred)})
    thr_df = pd.DataFrame(thr_rows)
    thr_df.to_csv(TAB / "q2_rule_threshold_sensitivity.csv", index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(thr_df["PbO+BaO阈值"], thr_df["准确率"], marker="o")
    ax.set_xlabel("PbO+BaO 判定阈值")
    ax.set_ylabel("准确率")
    ax.set_title("化学规则阈值灵敏度")
    fig.savefig(FIG / "q2_rule_threshold_sensitivity.png")
    plt.close(fig)

    best_row = cmp.sort_values("LOO准确率", ascending=False).iloc[0]
    summary = {
        "best_method": best_row["方法"],
        "best_loo_acc": float(best_row["LOO准确率"]),
        "best_f1": float(best_row["MacroF1"]),
        "rule_acc": float(rule_acc),
        "top_features": imp.head(5)["成分"].tolist(),
        "subclass": sub_summary,
        "pca_var": [float(x) for x in pca.explained_variance_ratio_],
        "noise_acc_at_0": float(sens.loc[sens["噪声水平"] == 0.0, "准确率均值"].iloc[0]),
        "noise_acc_at_0.1": float(sens.loc[sens["噪声水平"] == 0.10, "准确率均值"].iloc[0]),
    }
    save_json(summary, TAB / "q2_summary.json")

    append_summary(
        "## Q2\n"
        f"- 最佳分类：{summary['best_method']}，LOO准确率 {summary['best_loo_acc']:.4f}，"
        f"Macro-F1 {summary['best_f1']:.4f}；化学规则准确率 {summary['rule_acc']:.4f}。\n"
        f"- 重要成分 Top5：{summary['top_features']}。\n"
        f"- 亚类：高钾 K={sub_summary['高钾']['best_k']}（轮廓 {sub_summary['高钾']['silhouette']:.3f}），"
        f"铅钡 K={sub_summary['铅钡']['best_k']}（轮廓 {sub_summary['铅钡']['silhouette']:.3f}）。\n"
        f"- 噪声10%时准确率 {summary['noise_acc_at_0.1']:.4f}（相对0噪声 {summary['noise_acc_at_0']:.4f}）。\n"
    )
    log("Q2 done")


if __name__ == "__main__":
    main()
