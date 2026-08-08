# -*- coding: utf-8 -*-
"""Q2: Category-level replenishment & pricing optimization (2023-07-01~07)."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils_common import (  # noqa: E402
    CATEGORIES,
    FIG,
    PROC,
    TAB,
    append_summary,
    log,
    save_json,
    setup_plot_style,
)


def prepare_elasticity(daily_cat: pd.DataFrame):
    """Estimate category demand-price elasticity with controls."""
    df = daily_cat.dropna(subset=["均价", "销量", "批发均价", "加成率"]).copy()
    df = df[(df["均价"] > 0) & (df["销量"] > 0) & (df["批发均价"] > 0)]
    df["lnQ"] = np.log(df["销量"])
    df["lnP"] = np.log(df["均价"])
    df["lnC"] = np.log(df["批发均价"])
    # weekday dummies
    for d in range(7):
        df[f"wd{d}"] = (df["星期"] == d).astype(int)
    for m in range(1, 13):
        df[f"m{m}"] = (df["月份"] == m).astype(int)

    results = []
    models = {}
    for cat in CATEGORIES:
        sub = df[df["分类名称"] == cat].sort_values("销售日期")
        feat_cols = ["lnP", "lnC"] + [f"wd{d}" for d in range(1, 7)] + [f"m{m}" for m in range(2, 13)]
        X = sub[feat_cols].values
        y = sub["lnQ"].values
        # time-series CV
        tscv = TimeSeriesSplit(n_splits=5)
        maes, r2s = [], []
        for tr, te in tscv.split(X):
            reg = Ridge(alpha=1.0).fit(X[tr], y[tr])
            pred = reg.predict(X[te])
            maes.append(mean_absolute_error(np.exp(y[te]), np.exp(pred)))
            r2s.append(r2_score(y[te], pred))
        reg = Ridge(alpha=1.0).fit(X, y)
        # baseline: only mean
        baseline_mae = mean_absolute_error(np.exp(y), np.full_like(y, np.exp(y).mean()))
        elast = float(reg.coef_[0])
        models[cat] = {"model": reg, "feat_cols": feat_cols, "elasticity": elast}
        results.append(
            {
                "品类": cat,
                "价格弹性": elast,
                "CV_MAE": float(np.mean(maes)),
                "CV_R2_ln": float(np.mean(r2s)),
                "基线MAE_均值预测": float(baseline_mae),
                "相对提升": float(1 - np.mean(maes) / baseline_mae) if baseline_mae > 0 else np.nan,
                "样本天数": len(sub),
                "历史平均加成率": float(sub["加成率"].mean()),
                "历史平均日销量": float(sub["销量"].mean()),
                "历史平均售价": float(sub["均价"].mean()),
                "历史平均批发价": float(sub["批发均价"].mean()),
            }
        )
    res = pd.DataFrame(results)
    res.to_csv(TAB / "q2_elasticity.csv", index=False, encoding="utf-8-sig")

    setup_plot_style()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=res, x="品类", y="价格弹性", ax=ax, palette="viridis")
    ax.axhline(0, color="gray", ls="--")
    ax.set_title("各品类需求价格弹性（Ridge，含星期/月份控制）")
    ax.set_ylabel("∂lnQ / ∂lnP")
    fig.savefig(FIG / "q2_elasticity.png")
    plt.close()

    # scatter price vs qty for one illustration
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    for i, cat in enumerate(CATEGORIES):
        sub = df[df["分类名称"] == cat]
        axes.ravel()[i].scatter(sub["均价"], sub["销量"], s=8, alpha=0.35)
        axes.ravel()[i].set_title(cat)
        axes.ravel()[i].set_xlabel("均价")
        axes.ravel()[i].set_ylabel("销量")
    fig.suptitle("品类价格—销量散点（原始）")
    fig.tight_layout()
    fig.savefig(FIG / "q2_price_qty_scatter.png")
    plt.close()
    return df, models, res


def forecast_cost_and_season(daily_cat: pd.DataFrame, loss_cat: pd.DataFrame):
    """Forecast wholesale cost and seasonal demand factor for 2023-07-01..07."""
    targets = pd.date_range("2023-07-01", "2023-07-07", freq="D")
    rows = []
    for cat in CATEGORIES:
        sub = daily_cat[daily_cat["分类名称"] == cat].sort_values("销售日期")
        # recent wholesale
        recent = sub[sub["销售日期"] >= "2023-06-01"]
        # same weekday historical July
        july_hist = sub[(sub["月份"] == 7) & (sub["销售日期"] < "2023-07-01")]
        for d in targets:
            wd = d.dayofweek
            # cost: last 14d median of wholesale, fallback overall
            last14 = sub[sub["销售日期"] >= "2023-06-17"]["批发均价"].median()
            if np.isnan(last14):
                last14 = sub["批发均价"].median()
            # seasonal base demand: same weekday in recent 8 weeks + July hist
            same_wd = sub[(sub["星期"] == wd) & (sub["销售日期"] >= "2023-05-01")]["销量"]
            july_wd = july_hist[july_hist["星期"] == wd]["销量"]
            base_q = float(same_wd.median()) if len(same_wd) else float(sub["销量"].median())
            if len(july_wd):
                base_q = 0.6 * base_q + 0.4 * float(july_wd.median())
            hist_markup = float(recent["加成率"].median()) if len(recent) else float(sub["加成率"].median())
            hist_price = float(recent["均价"].median()) if len(recent) else float(sub["均价"].median())
            rows.append(
                {
                    "日期": d,
                    "品类": cat,
                    "星期": wd,
                    "预测批发价": float(last14),
                    "基准需求": base_q,
                    "历史加成率": hist_markup,
                    "历史售价": hist_price,
                }
            )
    fore = pd.DataFrame(rows)
    loss_map = loss_cat.set_index("分类名称")["平均损耗率(%)"].to_dict()
    fore["损耗率"] = fore["品类"].map(loss_map) / 100.0
    fore.to_csv(TAB / "q2_forecast_inputs.csv", index=False, encoding="utf-8-sig")
    return fore


def predict_demand(models, cat, price, cost, date, hist_ref: pd.DataFrame):
    m = models[cat]
    feat = {c: 0.0 for c in m["feat_cols"]}
    feat["lnP"] = np.log(max(price, 1e-6))
    feat["lnC"] = np.log(max(cost, 1e-6))
    wd = date.dayofweek
    mon = date.month
    if f"wd{wd}" in feat:
        feat[f"wd{wd}"] = 1.0
    if f"m{mon}" in feat:
        feat[f"m{mon}"] = 1.0
    x = np.array([[feat[c] for c in m["feat_cols"]]])
    lnq = float(m["model"].predict(x)[0])
    q = float(np.exp(lnq))
    # calibrate to recent level (weekday-aware, keep dow variation)
    recent = hist_ref[(hist_ref["分类名称"] == cat) & (hist_ref["销售日期"] >= "2023-05-01")]
    if len(recent):
        p0 = float(recent["均价"].median())
        feat0 = feat.copy()
        feat0["lnP"] = np.log(max(p0, 1e-6))
        x0 = np.array([[feat0[c] for c in m["feat_cols"]]])
        q0 = float(np.exp(m["model"].predict(x0)[0]))
        same_wd = recent[recent["星期"] == date.dayofweek]["销量"]
        target = float(same_wd.median()) if len(same_wd) else float(recent["销量"].median())
        if q0 > 0:
            q *= target / q0
    return max(q, 0.1)


def optimize_week(fore, models, daily_cat, elast_df):
    """Grid search markup rate per category-day to max expected profit.

    Profit = P * sales - C * replenish
    sales = min(demand(P), replenish * (1 - loss))
    Optimal replenish given P: R* = demand / (1-loss)  (sell-out matching)
    Then profit = (P - C/(1-loss)) * demand(P)
    """
    plan_rows = []
    compare_rows = []
    for _, r in fore.iterrows():
        cat, date, C, loss = r["品类"], r["日期"], r["预测批发价"], r["损耗率"]
        hist_m = r["历史加成率"]
        # category-specific feasible markup band from recent history
        sub_hist = daily_cat[
            (daily_cat["分类名称"] == cat)
            & (daily_cat["销售日期"] >= "2023-01-01")
            & (daily_cat["加成率"].notna())
        ]["加成率"]
        if len(sub_hist) >= 20:
            lo = float(np.clip(sub_hist.quantile(0.10), 0.08, 0.6))
            hi = float(np.clip(sub_hist.quantile(0.90), lo + 0.05, 1.0))
        else:
            lo, hi = 0.15, 0.80
        # search markup within historically observed band (+ small expand)
        lo = max(0.08, lo - 0.05)
        hi = min(1.0, hi + 0.05)
        best = None
        curve = []
        for markup in np.linspace(lo, hi, 41):
            P = C * (1 + markup)
            Qd = predict_demand(models, cat, P, C, date, daily_cat)
            R = Qd / max(1 - loss, 0.05)
            sales = Qd  # matched
            profit = P * sales - C * R
            curve.append((markup, P, Qd, R, profit))
            if best is None or profit > best["预期收益"]:
                best = {
                    "日期": date,
                    "品类": cat,
                    "批发价": C,
                    "加成率": markup,
                    "售价": P,
                    "预测需求": Qd,
                    "补货量": R,
                    "损耗率": loss,
                    "预期销量": sales,
                    "预期收益": profit,
                    "预期收入": P * sales,
                    "预期成本": C * R,
                    "加成下界": lo,
                    "加成上界": hi,
                }
        # baselines
        # 1) historical markup
        P_h = C * (1 + hist_m)
        Q_h = predict_demand(models, cat, P_h, C, date, daily_cat)
        R_h = Q_h / max(1 - loss, 0.05)
        profit_h = P_h * Q_h - C * R_h
        # 2) fixed 30% markup
        P_f = C * 1.30
        Q_f = predict_demand(models, cat, P_f, C, date, daily_cat)
        R_f = Q_f / max(1 - loss, 0.05)
        profit_f = P_f * Q_f - C * R_f
        # 3) elasticity closed-form approx: for Q=A*P^e, optimal etc — use grid as main

        best["基线_历史加成收益"] = profit_h
        best["基线_固定30%收益"] = profit_f
        best["相对历史加成提升"] = (best["预期收益"] - profit_h) / abs(profit_h) if profit_h else np.nan
        plan_rows.append(best)

        for markup, P, Qd, R, profit in curve[::3]:
            compare_rows.append(
                {"日期": date, "品类": cat, "加成率": markup, "售价": P, "收益": profit, "需求": Qd}
            )

    plan = pd.DataFrame(plan_rows)
    plan.to_csv(TAB / "q2_week_plan.csv", index=False, encoding="utf-8-sig")
    curve_df = pd.DataFrame(compare_rows)
    curve_df.to_csv(TAB / "q2_profit_markup_curve.csv", index=False, encoding="utf-8-sig")

    # summary by category
    cat_sum = (
        plan.groupby("品类")
        .agg(
            周补货总量=("补货量", "sum"),
            周预期销量=("预期销量", "sum"),
            周收益=("预期收益", "sum"),
            平均加成率=("加成率", "mean"),
            平均售价=("售价", "mean"),
            平均批发价=("批发价", "mean"),
            相对历史提升=("相对历史加成提升", "mean"),
        )
        .reindex(CATEGORIES)
        .reset_index()
    )
    cat_sum.to_csv(TAB / "q2_category_week_summary.csv", index=False, encoding="utf-8-sig")

    day_sum = (
        plan.groupby("日期")
        .agg(日补货总量=("补货量", "sum"), 日收益=("预期收益", "sum"), 日销量=("预期销量", "sum"))
        .reset_index()
    )
    day_sum.to_csv(TAB / "q2_daily_week_summary.csv", index=False, encoding="utf-8-sig")

    # plots
    setup_plot_style()
    fig, ax = plt.subplots(figsize=(9, 5))
    pivot = plan.pivot_table(index="日期", columns="品类", values="补货量")
    pivot = pivot.reindex(columns=CATEGORIES)
    pivot.index = pd.to_datetime(pivot.index).strftime("%m-%d")
    pivot.plot(kind="bar", stacked=True, ax=ax, colormap="Set2")
    ax.set_title("未来一周各品类日补货量")
    ax.set_ylabel("补货量/kg")
    ax.legend(ncol=3, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "q2_replenish_stacked.png")
    plt.close()

    fig, ax = plt.subplots(figsize=(9, 5))
    pivot_p = plan.pivot_table(index="日期", columns="品类", values="售价").reindex(columns=CATEGORIES)
    pivot_p.index = pd.to_datetime(pivot_p.index).strftime("%m-%d")
    pivot_p.plot(ax=ax, marker="o")
    ax.set_title("未来一周各品类建议售价")
    ax.set_ylabel("售价(元/kg)")
    ax.legend(ncol=3, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "q2_price_strategy.png")
    plt.close()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=cat_sum, x="品类", y="周收益", ax=ax, palette="Set2")
    ax.set_title("各品类周预期收益")
    ax.set_ylabel("收益/元")
    fig.savefig(FIG / "q2_category_profit.png")
    plt.close()

    # profit vs markup for 2023-07-01
    d0 = pd.Timestamp("2023-07-01")
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    for i, cat in enumerate(CATEGORIES):
        sub = curve_df[(curve_df["品类"] == cat) & (curve_df["日期"] == d0)]
        axes.ravel()[i].plot(sub["加成率"], sub["收益"], lw=2)
        opt = plan[(plan["品类"] == cat) & (plan["日期"] == d0)].iloc[0]
        axes.ravel()[i].axvline(opt["加成率"], color="r", ls="--", label="最优")
        axes.ravel()[i].set_title(cat)
        axes.ravel()[i].set_xlabel("加成率")
        axes.ravel()[i].set_ylabel("收益")
    fig.suptitle("2023-07-01 加成率—收益曲线")
    fig.tight_layout()
    fig.savefig(FIG / "q2_markup_profit_curve.png")
    plt.close()

    return plan, cat_sum, day_sum


def main():
    log("=== Q2 Category Optimization ===")
    daily_cat = pd.read_pickle(PROC / "daily_cat.pkl")
    loss_cat = pd.read_pickle(PROC / "loss_cat.pkl")

    df, models, elast = prepare_elasticity(daily_cat)
    fore = forecast_cost_and_season(daily_cat, loss_cat)
    plan, cat_sum, day_sum = optimize_week(fore, models, daily_cat, elast)

    total_profit = float(plan["预期收益"].sum())
    total_replenish = float(plan["补货量"].sum())
    base_hist = float(plan["基线_历史加成收益"].sum())
    base_fix = float(plan["基线_固定30%收益"].sum())
    lift_hist = (total_profit - base_hist) / abs(base_hist) if base_hist else np.nan
    lift_fix = (total_profit - base_fix) / abs(base_fix) if base_fix else np.nan

    save_json(
        {
            "week_total_profit": total_profit,
            "week_total_replenish": total_replenish,
            "baseline_hist_profit": base_hist,
            "baseline_fixed30_profit": base_fix,
            "lift_vs_hist": lift_hist,
            "lift_vs_fixed30": lift_fix,
            "avg_markup": float(plan["加成率"].mean()),
        },
        TAB / "q2_summary.json",
    )

    append_summary("\n## 问题2 品类补货与定价（2023-07-01~07）\n")
    append_summary(
        f"- 周预期总收益 **{total_profit:.2f} 元**，周补货总量 **{total_replenish:.2f} kg**，"
        f"平均最优加成率 **{plan['加成率'].mean():.2%}**。\n"
    )
    append_summary(
        f"- 对照基线：历史加成收益 **{base_hist:.2f} 元**（提升 **{lift_hist:.2%}**）；"
        f"固定30%加成收益 **{base_fix:.2f} 元**（提升 **{lift_fix:.2%}**）。\n"
    )
    append_summary("- 口径：补货量=预测需求/(1−损耗率)；收益=售价×预期销量−批发价×补货量。\n")
    for _, r in cat_sum.iterrows():
        append_summary(
            f"- **{r['品类']}**：周补货 **{r['周补货总量']:.1f} kg**，"
            f"平均加成 **{r['平均加成率']:.2%}**，周收益 **{r['周收益']:.2f} 元**。\n"
        )
    for _, r in elast.iterrows():
        append_summary(
            f"- 弹性 **{r['品类']}** = **{r['价格弹性']:.3f}**，"
            f"时序CV-MAE=**{r['CV_MAE']:.2f}**，相对均值基线提升 **{r['相对提升']:.2%}**。\n"
        )
    log("Q2 done.")


if __name__ == "__main__":
    main()
