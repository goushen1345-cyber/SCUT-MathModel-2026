# -*- coding: utf-8 -*-
"""Common utilities for CUMCM 2023 Problem C."""
from __future__ import annotations

import json
import os
import sys
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

CATEGORIES = ["花叶类", "花菜类", "水生根茎类", "茄类", "辣椒类", "食用菌"]


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
        f.write("> 口径说明：销量单位为千克；收益=销售收入−批发成本；"
                "损耗按附件4损耗率计入可售量；定价采用成本加成。\n\n")


def ensure_attach_ascii():
    """Ensure ASCII-named copies of attachments exist."""
    mapping = {
        "attach1.xlsx": 17803,
        "attach2.xlsx": 39150980,
        "attach3.xlsx": 1150765,
        "attach4.xlsx": 18678,
    }
    # Prefer exact names; else match by approximate size
    files = list(DATA.glob("*.xlsx"))
    by_size = {f.stat().st_size: f for f in files}
    for name, sz in mapping.items():
        dst = DATA / name
        if dst.exists():
            continue
        # nearest size
        if sz in by_size:
            import shutil
            shutil.copy2(by_size[sz], dst)


def log(msg: str):
    print(msg, flush=True)
    with open(LOG / "run.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")
