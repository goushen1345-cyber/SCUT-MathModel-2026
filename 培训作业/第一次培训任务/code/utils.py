"""Shared utilities: I/O, plotting, logging."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import FIG_DIR, LOG_DIR, PROCESSED_DIR, TABLE_DIR, WEEK_COLS_HIST


def setup_logging(name: str) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(LOG_DIR / f"{name}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def setup_matplotlib():
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.sans-serif": ["SimHei", "Microsoft YaHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.figsize": (8, 5),
        }
    )


def ensure_dirs():
    for d in [PROCESSED_DIR, FIG_DIR, TABLE_DIR, LOG_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def save_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_supplier_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    from config import ATTACH1

    orders = pd.read_excel(ATTACH1, sheet_name="企业的订货量（m³）")
    supplies = pd.read_excel(ATTACH1, sheet_name="供应商的供货量（m³）")
    return orders, supplies


def load_transporter_data() -> pd.DataFrame:
    from config import ATTACH2

    df = pd.read_excel(ATTACH2)
    return df


def build_supplier_features(orders: pd.DataFrame, supplies: pd.DataFrame) -> pd.DataFrame:
    oid = orders["供应商ID"].astype(str)
    mat = orders["材料分类"].astype(str).str.upper()
    O = orders[WEEK_COLS_HIST].fillna(0).astype(float).values
    S = supplies[WEEK_COLS_HIST].fillna(0).astype(float).values

    active = (S > 0).sum(axis=1)
    order_weeks = (O > 0).sum(axis=1)
    total_supply = S.sum(axis=1)
    total_order = O.sum(axis=1)
    mean_supply = np.where(active > 0, total_supply / np.maximum(active, 1), 0)
    max_supply = S.max(axis=1)

    with np.errstate(divide="ignore", invalid="ignore"):
        fill_rate = np.where(O > 0, S / np.maximum(O, 1e-9), np.nan)
    fill_mean = np.nanmean(fill_rate, axis=1)
    fill_mean = np.nan_to_num(fill_mean, nan=0.0)

    std_supply = S.std(axis=1)
    cv = np.where(mean_supply > 0, std_supply / mean_supply, 1.0)
    stability = 1.0 / (1.0 + cv)

    recent_supply = S[:, -24:].sum(axis=1)
    recent_active = (S[:, -24:] > 0).sum(axis=1)

    return pd.DataFrame(
        {
            "supplier_id": oid.values,
            "material": mat.values,
            "total_supply": total_supply,
            "total_order": total_order,
            "active_weeks": active,
            "order_weeks": order_weeks,
            "mean_supply": mean_supply,
            "max_supply": max_supply,
            "fill_rate": fill_mean,
            "stability": stability,
            "recent_supply": recent_supply,
            "recent_active": recent_active,
        }
    )


def entropy_weights(X: np.ndarray) -> np.ndarray:
    """Entropy weight method; X shape (n_samples, n_features), all >= 0."""
    X = np.asarray(X, dtype=float)
    X = X - X.min(axis=0, keepdims=True)
    X = X + 1e-12
    P = X / X.sum(axis=0, keepdims=True)
    k = 1.0 / np.log(len(X))
    E = -k * np.nansum(P * np.log(P + 1e-12), axis=0)
    d = 1 - E
    w = d / d.sum()
    return w


def topsis_score(X: np.ndarray, weights: np.ndarray, benefit: np.ndarray) -> np.ndarray:
    """TOPSIS closeness; benefit bool array True if larger is better."""
    X = np.asarray(X, dtype=float)
    norm = X / np.sqrt((X**2).sum(axis=0) + 1e-12)
    weighted = norm * weights
    ideal_best = np.where(benefit, weighted.max(axis=0), weighted.min(axis=0))
    ideal_worst = np.where(benefit, weighted.min(axis=0), weighted.max(axis=0))
    d_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
    d_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))
    return d_worst / (d_best + d_worst + 1e-12)
