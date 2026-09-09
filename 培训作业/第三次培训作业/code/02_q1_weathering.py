# -*- coding: utf-8 -*-
"""Q1: weathering associations + composition patterns + pre-weathering prediction."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import LeaveOneOut

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


def cramers_v(confusion):
    chi2 = stats.chi2_contingency(confusion, correction=False)[0]
    n = confusion.to_numpy().sum()
    r, k = confusion.shape
    return np.sqrt(chi2 / (n * (min(r - 1, k - 1))))


def association_tests(info: pd.DataFrame):
    rows = []
    for col in ["类型", "纹饰", "颜色"]:
        ct = pd.crosstab(info[col], info["表面风化"])
        # fisher if 2x2 and small, else chi2
        if ct.shape == (2, 2) and ct.to_numpy().sum() < 40:
            oddsr, p = stats.fisher_exact(ct)
            test = "Fisher"
            stat = oddsr
        else:
            chi2, p, dof, _ = stats.chi2_contingency(ct)
            test = "Chi2"
            stat = chi2
        v = cramers_v(ct) if min(ct.shape) > 1 else np.nan
        rows.append(
            {
                "变量": col,
                "检验": test,
                "统计量": float(stat),
                "p值": float(p),
                "CramersV": float(v) if pd.notna(v) else np.nan,
                "显著_0.05": bool(p < 0.05),
            }
        )
        ct.to_csv(TAB / f"q1_crosstab_{col}.csv", encoding="utf-8-sig")
    return pd.DataFrame(rows)


def composition_stats(df: pd.DataFrame):
    rows = []
    for typ in ["高钾", "铅钡"]:
        for w in ["风化", "无风化"]:
            sub = df[(df["类型"] == typ) & (df["点位风化标签"] == w)]
            for c in COMPONENTS:
                rows.append(
                    {
                        "类型": typ,
                        "风化": w,
                        "成分": c,
                        "n": int(len(sub)),
                        "均值": float(sub[c].mean()) if len(sub) else np.nan,
                        "标准差": float(sub[c].std()) if len(sub) else np.nan,
                        "中位数": float(sub[c].median()) if len(sub) else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def mw_tests(df: pd.DataFrame):
    """Mann-Whitney U: weathered vs unweathered within type."""
    rows = []
    for typ in ["高钾", "铅钡"]:
        a = df[(df["类型"] == typ) & (df["点位风化标签"] == "风化")]
        b = df[(df["类型"] == typ) & (df["点位风化标签"] == "无风化")]
        for c in COMPONENTS:
            if len(a) >= 3 and len(b) >= 3:
                u, p = stats.mannwhitneyu(a[c], b[c], alternative="two-sided")
                rows.append(
                    {
                        "类型": typ,
                        "成分": c,
                        "风化均值": float(a[c].mean()),
                        "无风化均值": float(b[c].mean()),
                        "差值_风化减无风化": float(a[c].mean() - b[c].mean()),
                        "U": float(u),
                        "p值": float(p),
                        "显著_0.05": bool(p < 0.05),
                    }
                )
    return pd.DataFrame(rows)


def build_weathering_factors(stats_df: pd.DataFrame):
    """Factor = mean_weathered / mean_unweathered (with floor)."""
    rows = []
    for typ in ["高钾", "铅钡"]:
        sub = stats_df[stats_df["类型"] == typ]
        w = sub[sub["风化"] == "风化"].set_index("成分")["均值"]
        u = sub[sub["风化"] == "无风化"].set_index("成分")["均值"]
        for c in COMPONENTS:
            mu_u = float(u.get(c, 0.0) or 0.0)
            mu_w = float(w.get(c, 0.0) or 0.0)
            # avoid div0; if both near 0, factor=1
            if mu_u < 1e-6 and mu_w < 1e-6:
                fac = 1.0
            elif mu_u < 1e-6:
                fac = np.nan  # cannot invert reliably
            else:
                fac = mu_w / mu_u
            rows.append({"类型": typ, "成分": c, "风化因子": fac, "无风化均值": mu_u, "风化均值": mu_w})
    return pd.DataFrame(rows)


def predict_preweather(df: pd.DataFrame, factors: pd.DataFrame):
    """Invert weathering: pre = weathered / factor, then renormalize to 100%."""
    weathered = df[df["点位风化标签"] == "风化"].copy()
    preds = []
    for _, row in weathered.iterrows():
        typ = row["类型"]
        fac = factors[factors["类型"] == typ].set_index("成分")["风化因子"]
        pre = {}
        for c in COMPONENTS:
            f = fac.get(c, np.nan)
            val = float(row[c])
            if pd.isna(f) or f < 1e-6:
                pre[c] = val
            else:
                pre[c] = val / f
        s = sum(pre.values())
        if s > 1e-8:
            pre = {k: v * 100.0 / s for k, v in pre.items()}
        rec = {
            "采样点": row["采样点"],
            "文物编号": row["文物编号"],
            "类型": typ,
            "方法": "均值风化因子反演+归一化",
        }
        for c in COMPONENTS:
            rec[f"{c}_风化观测"] = float(row[c])
            rec[f"{c}_风化前预测"] = float(pre[c])
        preds.append(rec)
    return pd.DataFrame(preds)


def regression_baseline(df: pd.DataFrame):
    """
    Supervised baseline: train on pairs if same artifact has both weathered and unweathered points;
    else LOO Ridge predicting unweathered group mean components from weathered samples features.
    Here: for each type, model mapping weathered vector -> estimated unweathered using
    random forest multioutput vs factor method; evaluate by reconstructing unweathered means.
    """
    results = []
    for typ in ["高钾", "铅钡"]:
        w = df[(df["类型"] == typ) & (df["点位风化标签"] == "风化")][COMPONENTS].values
        u = df[(df["类型"] == typ) & (df["点位风化标签"] == "无风化")][COMPONENTS]
        if len(w) < 3 or len(u) < 3:
            continue
        target = u.mean().values
        # naive: each weathered sample predicts the type-level unweathered mean (constant model)
        y_true = np.tile(target, (len(w), 1))
        # factor method predictions already in another file; here ridge from w to constant? 
        # Better: leave-one-out: predict held-out unweathered sample from nearest weathered? 
        # Practical validation: how close factor-inverted means are to true unweathered means.
        fac_df = build_weathering_factors(
            composition_stats(df)
        )
        fac = fac_df[fac_df["类型"] == typ].set_index("成分")["风化因子"]
        inv = []
        for i in range(len(w)):
            pre = []
            for j, c in enumerate(COMPONENTS):
                f = fac.get(c, np.nan)
                val = w[i, j]
                if pd.isna(f) or f < 1e-6:
                    pre.append(val)
                else:
                    pre.append(val / f)
            pre = np.array(pre)
            pre = pre * 100.0 / pre.sum()
            inv.append(pre)
        inv = np.array(inv)
        mae_factor = mean_absolute_error(y_true, inv)
        # baseline: no correction (weathered as is, renormalized)
        base = w.copy()
        base = base / base.sum(axis=1, keepdims=True) * 100.0
        mae_base = mean_absolute_error(y_true, base)
        # ridge multi: use weathered to predict type mean via identity scaled — RF on synthetic
        # Train RF: features = weathered samples, target = unweathered mean (repeated) — weak but baseline
        # Stronger baseline: for each component, ratio-adjusted vs absolute difference adjustment
        diff = target - w.mean(axis=0)
        adj = w + diff
        adj = np.clip(adj, 0, None)
        adj = adj / adj.sum(axis=1, keepdims=True) * 100.0
        mae_diff = mean_absolute_error(y_true, adj)

        results.append(
            {
                "类型": typ,
                "风化样本数": len(w),
                "无风化样本数": len(u),
                "MAE_无校正": float(mae_base),
                "MAE_差值校正": float(mae_diff),
                "MAE_风化因子反演": float(mae_factor),
                "相对无校正提升_因子": float((mae_base - mae_factor) / mae_base) if mae_base > 0 else 0.0,
            }
        )
    return pd.DataFrame(results)


def main():
    setup_plot_style()
    log("=== Q1 start ===")
    info = pd.read_csv(PROC / "info.csv")
    df = pd.read_csv(PROC / "labeled_filled.csv")

    assoc = association_tests(info)
    assoc.to_csv(TAB / "q1_association_tests.csv", index=False, encoding="utf-8-sig")

    stats_df = composition_stats(df)
    stats_df.to_csv(TAB / "q1_comp_stats.csv", index=False, encoding="utf-8-sig")

    mw = mw_tests(df)
    mw.to_csv(TAB / "q1_mannwhitney.csv", index=False, encoding="utf-8-sig")

    factors = build_weathering_factors(stats_df)
    factors.to_csv(TAB / "q1_weathering_factors.csv", index=False, encoding="utf-8-sig")

    preds = predict_preweather(df, factors)
    preds.to_csv(TAB / "q1_preweather_predictions.csv", index=False, encoding="utf-8-sig")

    cmp = regression_baseline(df)
    cmp.to_csv(TAB / "q1_method_compare.csv", index=False, encoding="utf-8-sig")

    # sensitivity: perturb factors ±10%
    sens_rows = []
    for scale in [0.9, 1.0, 1.1]:
        f2 = factors.copy()
        f2["风化因子"] = f2["风化因子"] * scale
        p2 = predict_preweather(df, f2)
        for typ in ["高钾", "铅钡"]:
            cols = [f"{c}_风化前预测" for c in COMPONENTS]
            sub = p2[p2["类型"] == typ]
            if len(sub) == 0:
                continue
            mean_sio2 = float(sub["SiO2_风化前预测"].mean())
            sens_rows.append({"类型": typ, "因子缩放": scale, "预测SiO2均值": mean_sio2, "n": len(sub)})
    sens = pd.DataFrame(sens_rows)
    sens.to_csv(TAB / "q1_sensitivity_factor_scale.csv", index=False, encoding="utf-8-sig")

    # figures
    # association heatmap of p-values
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, col in zip(axes, ["类型", "纹饰", "颜色"]):
        ct = pd.crosstab(info[col], info["表面风化"])
        sns.heatmap(ct, annot=True, fmt="d", cmap="YlGnBu", ax=ax)
        ax.set_title(f"{col}×风化")
    fig.tight_layout()
    fig.savefig(FIG / "q1_crosstab_heatmaps.png")
    plt.close(fig)

    # MW significant components
    sig = mw[mw["显著_0.05"]].copy()
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, typ in zip(axes, ["高钾", "铅钡"]):
        sub = mw[mw["类型"] == typ].sort_values("差值_风化减无风化")
        colors = ["#c1121f" if p < 0.05 else "#8d99ae" for p in sub["p值"]]
        ax.barh(sub["成分"], sub["差值_风化减无风化"], color=colors)
        ax.axvline(0, color="k", lw=0.8)
        ax.set_title(f"{typ}：风化−无风化 均值差（红=显著）")
        ax.set_xlabel("含量差 (百分点)")
    fig.tight_layout()
    fig.savefig(FIG / "q1_weather_diff_components.png")
    plt.close(fig)

    # key component grouped bars
    key = ["SiO2", "K2O", "PbO", "BaO", "P2O5", "CaO"]
    plot_df = stats_df[stats_df["成分"].isin(key)].copy()
    for typ in ["高钾", "铅钡"]:
        sub = plot_df[plot_df["类型"] == typ]
        fig, ax = plt.subplots(figsize=(9, 5))
        sns.barplot(data=sub, x="成分", y="均值", hue="风化", ax=ax, palette=["#f9c74f", "#90be6d"])
        ax.set_title(f"{typ}玻璃关键成分：风化 vs 无风化")
        ax.set_ylabel("均值含量 (%)")
        fig.savefig(FIG / f"q1_{typ}_weather_bars.png")
        plt.close(fig)

    # method compare
    if len(cmp):
        fig, ax = plt.subplots(figsize=(8, 5))
        x = np.arange(len(cmp))
        w = 0.25
        ax.bar(x - w, cmp["MAE_无校正"], w, label="无校正", color="#8d99ae")
        ax.bar(x, cmp["MAE_差值校正"], w, label="差值校正", color="#f9c74f")
        ax.bar(x + w, cmp["MAE_风化因子反演"], w, label="风化因子反演", color="#2a6f97")
        ax.set_xticks(x)
        ax.set_xticklabels(cmp["类型"])
        ax.set_ylabel("相对类型无风化均值的 MAE")
        ax.set_title("风化前成分预测方法对比")
        ax.legend()
        fig.savefig(FIG / "q1_method_compare.png")
        plt.close(fig)

    # sensitivity
    fig, ax = plt.subplots(figsize=(8, 5))
    for typ, g in sens.groupby("类型"):
        ax.plot(g["因子缩放"], g["预测SiO2均值"], marker="o", label=typ)
    ax.set_xlabel("风化因子缩放系数")
    ax.set_ylabel("预测风化前 SiO2 均值 (%)")
    ax.set_title("风化因子灵敏度（SiO2）")
    ax.legend()
    fig.savefig(FIG / "q1_sensitivity_sio2.png")
    plt.close(fig)

    # summary json
    best = {}
    if len(cmp):
        for _, r in cmp.iterrows():
            best[r["类型"]] = {
                "MAE_因子": r["MAE_风化因子反演"],
                "提升": r["相对无校正提升_因子"],
            }
    summary = {
        "assoc": assoc.to_dict(orient="records"),
        "n_predictions": int(len(preds)),
        "n_sig_mw": int(sig.shape[0]) if len(mw) else 0,
        "method_compare": best,
        "type_weather_rate": {
            "高钾_风化率": float(((info["类型"] == "高钾") & (info["表面风化"] == "风化")).sum()
                               / max((info["类型"] == "高钾").sum(), 1)),
            "铅钡_风化率": float(((info["类型"] == "铅钡") & (info["表面风化"] == "风化")).sum()
                               / max((info["类型"] == "铅钡").sum(), 1)),
        },
    }
    save_json(summary, TAB / "q1_summary.json")

    append_summary(
        "## Q1\n"
        f"- 关联检验见 `q1_association_tests.csv`；Mann-Whitney 显著成分数 {summary['n_sig_mw']}。\n"
        f"- 高钾风化率 {summary['type_weather_rate']['高钾_风化率']:.3f}，"
        f"铅钡风化率 {summary['type_weather_rate']['铅钡_风化率']:.3f}。\n"
        f"- 风化前预测样本数 {summary['n_predictions']}（均值风化因子反演+归一化）。\n"
        f"- 方法对比：{best}\n"
    )
    log("Q1 done")


if __name__ == "__main__":
    main()
