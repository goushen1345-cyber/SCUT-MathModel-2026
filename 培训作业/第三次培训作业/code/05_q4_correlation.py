# -*- coding: utf-8 -*-
"""Q4: chemical component correlations by glass type and difference comparison."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

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


def corr_with_p(df, cols, method="spearman"):
    n = len(cols)
    corr = pd.DataFrame(np.eye(n), index=cols, columns=cols, dtype=float)
    pmat = pd.DataFrame(np.zeros((n, n)), index=cols, columns=cols, dtype=float)
    for i, a in enumerate(cols):
        for j, b in enumerate(cols):
            if i >= j:
                continue
            x, y = df[a].values, df[b].values
            if method == "spearman":
                r, p = stats.spearmanr(x, y)
            else:
                r, p = stats.pearsonr(x, y)
            corr.loc[a, b] = corr.loc[b, a] = float(r)
            pmat.loc[a, b] = pmat.loc[b, a] = float(p)
    return corr, pmat


def mantel_test(c1, c2, n_perm=999, rng=None):
    """Simple Mantel test on upper triangles."""
    rng = rng or np.random.default_rng(42)
    v1 = c1.values[np.triu_indices_from(c1.values, k=1)]
    v2 = c2.values[np.triu_indices_from(c2.values, k=1)]
    # use correlation of matrices (not distance); still informative
    obs = np.corrcoef(v1, v2)[0, 1]
    count = 0
    idx = np.arange(c2.shape[0])
    for _ in range(n_perm):
        p = rng.permutation(idx)
        c2p = c2.values[p][:, p]
        v2p = c2p[np.triu_indices_from(c2p, k=1)]
        r = np.corrcoef(v1, v2p)[0, 1]
        if abs(r) >= abs(obs):
            count += 1
    pval = (count + 1) / (n_perm + 1)
    return float(obs), float(pval)


def top_pairs(corr, pmat, n=10, alpha=0.05):
    rows = []
    cols = list(corr.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            rows.append({"成分A": a, "成分B": b, "相关系数": corr.loc[a, b], "p值": pmat.loc[a, b]})
    out = pd.DataFrame(rows).sort_values("相关系数", key=lambda s: s.abs(), ascending=False)
    out["显著"] = out["p值"] < alpha
    return out.head(n), out


def plot_network(corr, pmat, title, path, thr=0.5, alpha=0.05):
    G = nx.Graph()
    cols = list(corr.columns)
    for c in cols:
        G.add_node(c)
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            r = corr.loc[a, b]
            p = pmat.loc[a, b]
            if abs(r) >= thr and p < alpha:
                G.add_edge(a, b, weight=r)
    fig, ax = plt.subplots(figsize=(9, 7))
    if G.number_of_edges() == 0:
        ax.text(0.5, 0.5, "无超过阈值的显著相关边", ha="center")
        ax.set_axis_off()
    else:
        pos = nx.spring_layout(G, seed=42, k=0.8)
        weights = [abs(G[u][v]["weight"]) * 2 for u, v in G.edges()]
        colors = ["#c1121f" if G[u][v]["weight"] > 0 else "#2a6f97" for u, v in G.edges()]
        nx.draw_networkx_nodes(G, pos, node_color="#e9ecef", edgecolors="#333", node_size=900, ax=ax)
        nx.draw_networkx_labels(G, pos, font_size=8, ax=ax)
        nx.draw_networkx_edges(G, pos, width=weights, edge_color=colors, ax=ax)
    ax.set_title(title)
    fig.savefig(path)
    plt.close(fig)


def main():
    setup_plot_style()
    log("=== Q4 start ===")
    df = pd.read_csv(PROC / "labeled_filled.csv")
    # prefer using components with enough non-zero variance
    cols = []
    for c in COMPONENTS:
        if df[c].std() > 1e-6:
            cols.append(c)

    results = {}
    all_pair_diff = []
    corrs = {}
    pmats = {}
    for typ in ["高钾", "铅钡"]:
        sub = df[df["类型"] == typ]
        # drop near-constant within type
        use = [c for c in cols if sub[c].std() > 1e-6]
        corr, pmat = corr_with_p(sub, use, method="spearman")
        corrs[typ] = corr
        pmats[typ] = pmat
        corr.to_csv(TAB / f"q4_spearman_{typ}.csv", encoding="utf-8-sig")
        pmat.to_csv(TAB / f"q4_spearman_p_{typ}.csv", encoding="utf-8-sig")
        top, full = top_pairs(corr, pmat, n=15)
        top.to_csv(TAB / f"q4_top_pairs_{typ}.csv", index=False, encoding="utf-8-sig")
        full.to_csv(TAB / f"q4_all_pairs_{typ}.csv", index=False, encoding="utf-8-sig")
        results[typ] = {
            "n": int(len(sub)),
            "n_features": len(use),
            "n_sig_pairs": int(full["显著"].sum()),
            "max_abs_corr": float(full["相关系数"].abs().max()),
            "top_pair": top.iloc[0].to_dict() if len(top) else {},
        }

        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(corr, cmap="RdBu_r", center=0, ax=ax, square=True)
        ax.set_title(f"{typ}玻璃 Spearman 相关热力图")
        fig.savefig(FIG / f"q4_heatmap_{typ}.png")
        plt.close(fig)

        plot_network(
            corr,
            pmat,
            f"{typ}显著相关网络(|r|≥0.5)",
            FIG / f"q4_network_{typ}.png",
            thr=0.5,
        )

    # compare overlapping features
    common = sorted(set(corrs["高钾"].columns) & set(corrs["铅钡"].columns))
    c1 = corrs["高钾"].loc[common, common]
    c2 = corrs["铅钡"].loc[common, common]
    diff = (c1 - c2).copy()
    diff.to_csv(TAB / "q4_corr_diff_highK_minus_pbba.csv", encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(diff, cmap="RdBu_r", center=0, ax=ax, square=True)
    ax.set_title("相关结构差异：高钾 − 铅钡")
    fig.savefig(FIG / "q4_corr_diff_heatmap.png")
    plt.close(fig)

    mantel_r, mantel_p = mantel_test(c1, c2, n_perm=999)
    # pairwise absolute difference ranking
    rows = []
    for i, a in enumerate(common):
        for b in common[i + 1 :]:
            rows.append(
                {
                    "成分A": a,
                    "成分B": b,
                    "高钾_r": float(c1.loc[a, b]),
                    "铅钡_r": float(c2.loc[a, b]),
                    "差值": float(c1.loc[a, b] - c2.loc[a, b]),
                    "绝对差值": float(abs(c1.loc[a, b] - c2.loc[a, b])),
                }
            )
    diff_pairs = pd.DataFrame(rows).sort_values("绝对差值", ascending=False)
    diff_pairs.to_csv(TAB / "q4_pair_diff_ranked.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(9, 5))
    topd = diff_pairs.head(12).copy()
    topd["pair"] = topd["成分A"] + "-" + topd["成分B"]
    ax.barh(topd["pair"][::-1], topd["绝对差值"][::-1], color="#577590")
    ax.set_xlabel("|Δr|")
    ax.set_title("两类玻璃相关差异最大的成分对")
    fig.savefig(FIG / "q4_top_diff_pairs.png")
    plt.close(fig)

    # baseline: pearson vs spearman consistency
    cons_rows = []
    for typ in ["高钾", "铅钡"]:
        sub = df[df["类型"] == typ]
        use = [c for c in common if sub[c].std() > 1e-6]
        cs, _ = corr_with_p(sub, use, "spearman")
        cp, _ = corr_with_p(sub, use, "pearson")
        v1 = cs.values[np.triu_indices_from(cs.values, k=1)]
        v2 = cp.values[np.triu_indices_from(cp.values, k=1)]
        cons_rows.append({"类型": typ, "Spearman_Pearson一致相关": float(np.corrcoef(v1, v2)[0, 1])})
    cons = pd.DataFrame(cons_rows)
    cons.to_csv(TAB / "q4_spearman_pearson_consistency.csv", index=False, encoding="utf-8-sig")

    summary = {
        "by_type": results,
        "mantel_r": mantel_r,
        "mantel_p": mantel_p,
        "top_diff_pair": diff_pairs.iloc[0].to_dict() if len(diff_pairs) else {},
        "mean_abs_diff": float(diff_pairs["绝对差值"].mean()) if len(diff_pairs) else 0.0,
        "consistency": cons.to_dict(orient="records"),
    }
    save_json(summary, TAB / "q4_summary.json")

    append_summary(
        "## Q4\n"
        f"- 高钾显著相关对数 {results['高钾']['n_sig_pairs']}，铅钡 {results['铅钡']['n_sig_pairs']}。\n"
        f"- Mantel(相关矩阵相似) r={mantel_r:.4f}, p={mantel_p:.4f}。\n"
        f"- 最大结构差异对：{summary['top_diff_pair']}；平均|Δr|={summary['mean_abs_diff']:.4f}。\n"
    )
    log("Q4 done")


if __name__ == "__main__":
    main()
