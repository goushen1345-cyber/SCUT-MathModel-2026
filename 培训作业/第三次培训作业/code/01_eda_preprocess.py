# -*- coding: utf-8 -*-
"""EDA and preprocessing for 2022 CUMCM C."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils_common import (  # noqa: E402
    COMP_CN,
    COMPONENTS,
    CN_TO_EN,
    DATA,
    FIG,
    PROC,
    TAB,
    append_summary,
    composition_sum,
    log,
    reset_summary,
    save_json,
    setup_plot_style,
    valid_mask,
)


def parse_sample_id(s: str):
    """Parse artifact id and site note from 文物采样点."""
    s = str(s).strip()
    m = re.match(r"^(\d+)(.*)$", s)
    if not m:
        return s, "", s
    aid = m.group(1).zfill(2) if m.group(1).isdigit() else m.group(1)
    note = m.group(2).strip()
    return aid, note, s


def load_raw():
    xlsx = DATA / "附件.xlsx"
    info = pd.read_excel(xlsx, sheet_name="表单1")
    comp = pd.read_excel(xlsx, sheet_name="表单2")
    unk = pd.read_excel(xlsx, sheet_name="表单3")

    info = info.rename(
        columns={
            "文物编号": "文物编号",
            "纹饰": "纹饰",
            "类型": "类型",
            "颜色": "颜色",
            "表面风化": "表面风化",
        }
    )
    info["文物编号"] = info["文物编号"].astype(str).str.zfill(2)
    info["颜色"] = info["颜色"].fillna("未知")

    # rename components
    rename2 = {"文物采样点": "采样点"}
    for cn, en in CN_TO_EN.items():
        if cn in comp.columns:
            rename2[cn] = en
    comp = comp.rename(columns=rename2)
    parsed = comp["采样点"].map(parse_sample_id)
    comp["文物编号"] = [p[0] for p in parsed]
    comp["部位备注"] = [p[1] for p in parsed]
    comp["文物编号"] = comp["文物编号"].astype(str).str.zfill(2)

    rename3 = {"文物编号": "文物编号", "表面风化": "表面风化"}
    for cn, en in CN_TO_EN.items():
        if cn in unk.columns:
            rename3[cn] = en
    unk = unk.rename(columns=rename3)
    unk["文物编号"] = unk["文物编号"].astype(str)

    return info, comp, unk


def merge_labeled(info, comp):
    df = comp.merge(info, on="文物编号", how="left", suffixes=("", "_info"))
    df["成分和"] = composition_sum(df)
    df["有效"] = valid_mask(df)
    # weathering label from info (artifact-level), with site overrides
    note = df["部位备注"].fillna("")
    df["点位风化标签"] = df["表面风化"]
    df.loc[note.str.contains("未风化"), "点位风化标签"] = "无风化"
    df.loc[note.str.contains("严重风化"), "点位风化标签"] = "风化"
    return df


def main():
    setup_plot_style()
    reset_summary()
    log("=== EDA preprocess start ===")
    info, comp, unk = load_raw()
    labeled = merge_labeled(info, comp)

    # unknown validity
    unk["成分和"] = composition_sum(unk)
    unk["有效"] = valid_mask(unk)

    info.to_csv(PROC / "info.csv", index=False, encoding="utf-8-sig")
    labeled.to_csv(PROC / "labeled_raw.csv", index=False, encoding="utf-8-sig")
    unk.to_csv(PROC / "unknown_raw.csv", index=False, encoding="utf-8-sig")

    valid = labeled[labeled["有效"]].copy()
    valid.to_csv(PROC / "labeled_valid.csv", index=False, encoding="utf-8-sig")
    unk_valid = unk[unk["有效"]].copy()
    unk_valid.to_csv(PROC / "unknown_valid.csv", index=False, encoding="utf-8-sig")

    # fill NA with 0 for modeling copies
    for df, name in [(valid, "labeled_filled"), (unk_valid, "unknown_filled")]:
        d = df.copy()
        d[COMPONENTS] = d[COMPONENTS].fillna(0.0)
        d.to_csv(PROC / f"{name}.csv", index=False, encoding="utf-8-sig")

    # stats
    stats_rows = []
    for name, df in [("labeled_all", labeled), ("labeled_valid", valid), ("unknown_all", unk), ("unknown_valid", unk_valid)]:
        stats_rows.append(
            {
                "数据集": name,
                "样本数": len(df),
                "成分和均值": float(df["成分和"].mean()) if len(df) else np.nan,
                "成分和标准差": float(df["成分和"].std()) if len(df) else np.nan,
                "无效样本数": int((~df["有效"]).sum()) if "有效" in df else 0,
            }
        )
    pd.DataFrame(stats_rows).to_csv(TAB / "eda_clean_stats.csv", index=False, encoding="utf-8-sig")

    # invalid list
    invalid = labeled[~labeled["有效"]][["采样点", "文物编号", "类型", "表面风化", "成分和"]]
    invalid.to_csv(TAB / "eda_invalid_samples.csv", index=False, encoding="utf-8-sig")

    # descriptive by type x weathering
    filled = valid.copy()
    filled[COMPONENTS] = filled[COMPONENTS].fillna(0.0)
    desc = (
        filled.groupby(["类型", "点位风化标签"])[COMPONENTS]
        .agg(["mean", "std", "count"])
    )
    # flatten
    desc_flat = filled.groupby(["类型", "点位风化标签"])[COMPONENTS].mean().reset_index()
    desc_flat.to_csv(TAB / "eda_mean_by_type_weather.csv", index=False, encoding="utf-8-sig")

    # info contingency
    info_counts = {
        "n_artifacts": int(len(info)),
        "n_high_k": int((info["类型"] == "高钾").sum()),
        "n_pb_ba": int((info["类型"] == "铅钡").sum()),
        "n_weathered": int((info["表面风化"] == "风化").sum()),
        "n_unweathered": int((info["表面风化"] == "无风化").sum()),
        "n_comp_all": int(len(labeled)),
        "n_comp_valid": int(len(valid)),
        "n_comp_invalid": int(len(invalid)),
        "n_unknown": int(len(unk)),
        "n_unknown_valid": int(len(unk_valid)),
    }
    save_json(info_counts, TAB / "eda_summary.json")

    # ---- figures ----
    # 1 composition sum hist
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(labeled["成分和"], bins=20, color="#2a6f97", edgecolor="white", alpha=0.9)
    ax.axvline(85, color="#c1121f", ls="--", label="85% 有效下界")
    ax.axvline(105, color="#c1121f", ls="--", label="105% 有效上界")
    ax.set_xlabel("成分比例累加和 (%)")
    ax.set_ylabel("样本数")
    ax.set_title("化学成分累加和分布与有效区间")
    ax.legend()
    fig.savefig(FIG / "eda_sum_hist.png")
    plt.close(fig)

    # 2 type-weather stacked
    ct = pd.crosstab(info["类型"], info["表面风化"])
    ct.to_csv(TAB / "eda_type_weather_crosstab.csv", encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(7, 5))
    ct.plot(kind="bar", stacked=True, ax=ax, color=["#90be6d", "#f9c74f"])
    ax.set_xlabel("玻璃类型")
    ax.set_ylabel("文物数")
    ax.set_title("类型 × 表面风化 分布")
    ax.legend(title="表面风化")
    ax.tick_params(axis="x", rotation=0)
    fig.savefig(FIG / "eda_type_weather_stack.png")
    plt.close(fig)

    # 3 decor-weather
    ct2 = pd.crosstab(info["纹饰"], info["表面风化"])
    fig, ax = plt.subplots(figsize=(7, 5))
    ct2.plot(kind="bar", ax=ax, color=["#90be6d", "#f9c74f"])
    ax.set_xlabel("纹饰")
    ax.set_ylabel("文物数")
    ax.set_title("纹饰 × 表面风化")
    ax.tick_params(axis="x", rotation=0)
    fig.savefig(FIG / "eda_decor_weather.png")
    plt.close(fig)

    # 4 color-weather
    ct3 = pd.crosstab(info["颜色"], info["表面风化"])
    fig, ax = plt.subplots(figsize=(10, 5))
    ct3.plot(kind="bar", ax=ax, color=["#90be6d", "#f9c74f"])
    ax.set_xlabel("颜色")
    ax.set_ylabel("文物数")
    ax.set_title("颜色 × 表面风化")
    fig.savefig(FIG / "eda_color_weather.png")
    plt.close(fig)

    # 5 correlation heatmap overall
    corr = filled[COMPONENTS].corr()
    fig, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(corr, cmap="RdBu_r", center=0, ax=ax, square=True)
    ax.set_title("有效样本化学成分 Pearson 相关热力图")
    fig.savefig(FIG / "eda_corr_heatmap.png")
    plt.close(fig)

    # 6 key oxides box by type
    key = ["SiO2", "K2O", "PbO", "BaO", "CaO", "Al2O3"]
    melt = filled.melt(id_vars=["类型"], value_vars=key, var_name="成分", value_name="含量")
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.boxplot(data=melt, x="成分", y="含量", hue="类型", ax=ax)
    ax.set_title("关键氧化物含量按玻璃类型分布")
    fig.savefig(FIG / "eda_key_oxides_box.png")
    plt.close(fig)

    # 7 missingness
    miss = labeled[COMPONENTS].isna().mean().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(9, 5))
    miss.plot(kind="bar", ax=ax, color="#577590")
    ax.set_ylabel("缺失比例")
    ax.set_title("各化学成分未检出（缺失）比例")
    fig.savefig(FIG / "eda_missing_rate.png")
    plt.close(fig)
    miss.to_csv(TAB / "eda_missing_rate.csv", encoding="utf-8-sig", header=["缺失比例"])

    # normality quick check on SiO2
    shapiro_rows = []
    for typ in ["高钾", "铅钡"]:
        for w in ["风化", "无风化"]:
            x = filled[(filled["类型"] == typ) & (filled["点位风化标签"] == w)]["SiO2"]
            if len(x) >= 3:
                # use normaltest for larger; shapiro if n<=50
                if len(x) <= 50:
                    stat, p = stats.shapiro(x)
                    test = "shapiro"
                else:
                    stat, p = stats.normaltest(x)
                    test = "normaltest"
                shapiro_rows.append({"类型": typ, "风化": w, "n": len(x), "检验": test, "统计量": stat, "p值": p})
    pd.DataFrame(shapiro_rows).to_csv(TAB / "eda_sio2_normality.csv", index=False, encoding="utf-8-sig")

    append_summary(
        "## EDA\n"
        f"- 文物数 {info_counts['n_artifacts']}（高钾 {info_counts['n_high_k']}，铅钡 {info_counts['n_pb_ba']}）；"
        f"风化 {info_counts['n_weathered']}，无风化 {info_counts['n_unweathered']}。\n"
        f"- 成分样本 {info_counts['n_comp_all']}，有效 {info_counts['n_comp_valid']}，无效 {info_counts['n_comp_invalid']} "
        f"（有效口径：成分和∈[85%,105%]）。\n"
        f"- 未知类别样本 {info_counts['n_unknown']}，有效 {info_counts['n_unknown_valid']}。\n"
    )
    log(f"EDA done: valid={info_counts['n_comp_valid']}, invalid={info_counts['n_comp_invalid']}")


if __name__ == "__main__":
    main()
