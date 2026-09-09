# -*- coding: utf-8 -*-
"""Common utilities for CUMCM 2022 Problem C (ancient glass)."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROC = DATA / "processed"
FIG = ROOT / "output" / "figures"
TAB = ROOT / "output" / "tables"
OUT = ROOT / "output"
LOG = ROOT / "logs"
LATEX = ROOT / "latex"

for p in (PROC, FIG, TAB, OUT, LOG, LATEX):
    p.mkdir(parents=True, exist_ok=True)

COMPONENTS = [
    "SiO2", "Na2O", "K2O", "CaO", "MgO", "Al2O3", "Fe2O3",
    "CuO", "PbO", "BaO", "P2O5", "SrO", "SnO2", "SO2",
]

COMP_CN = {
    "SiO2": "二氧化硅(SiO2)",
    "Na2O": "氧化钠(Na2O)",
    "K2O": "氧化钾(K2O)",
    "CaO": "氧化钙(CaO)",
    "MgO": "氧化镁(MgO)",
    "Al2O3": "氧化铝(Al2O3)",
    "Fe2O3": "氧化铁(Fe2O3)",
    "CuO": "氧化铜(CuO)",
    "PbO": "氧化铅(PbO)",
    "BaO": "氧化钡(BaO)",
    "P2O5": "五氧化二磷(P2O5)",
    "SrO": "氧化锶(SrO)",
    "SnO2": "氧化锡(SnO2)",
    "SO2": "二氧化硫(SO2)",
}

CN_TO_EN = {v: k for k, v in COMP_CN.items()}


def setup_plot_style():
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 150
    plt.rcParams["savefig.dpi"] = 300
    plt.rcParams["savefig.bbox"] = "tight"


def save_json(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def append_summary(text: str):
    path = OUT / "results_summary.md"
    mode = "a" if path.exists() else "w"
    with open(path, mode, encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


def reset_summary():
    path = OUT / "results_summary.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("# 结果摘要（真实运行产出）\n\n")
        f.write(
            "> 口径说明：化学成分为质量百分比（%）；有效样本要求成分和∈[85%,105%]；"
            "空白按0处理后再做归一化分析时会明确标注；风化预测给出风化前估计值（%）。\n\n"
        )


def log(msg: str):
    print(msg, flush=True)
    with open(LOG / "run.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def composition_sum(df: pd.DataFrame, cols=None) -> pd.Series:
    cols = cols or COMPONENTS
    return df[cols].fillna(0).sum(axis=1)


def valid_mask(df: pd.DataFrame, cols=None) -> pd.Series:
    s = composition_sum(df, cols)
    return (s >= 85.0) & (s <= 105.0)
