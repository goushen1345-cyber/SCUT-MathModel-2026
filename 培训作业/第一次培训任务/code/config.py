"""Global constants for CUMCM 2021-C."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = ROOT / "output"
FIG_DIR = OUTPUT_DIR / "figures"
TABLE_DIR = OUTPUT_DIR / "tables"
LOG_DIR = ROOT / "logs"
LATEX_DIR = ROOT / "latex"


def _find_data(keyword: str) -> Path:
    matches = sorted(DATA_DIR.glob(f"*{keyword}*.xlsx"))
    if not matches:
        raise FileNotFoundError(f"No xlsx matching '{keyword}' in {DATA_DIR}")
    return matches[0]


ATTACH1 = _find_data("402")
ATTACH2 = _find_data("转运商")
ATTACH_A = _find_data("附件A")
ATTACH_B = _find_data("附件B")

WEEKLY_CAPACITY = 28200.0  # m^3 product per week
CONSUMPTION = {"A": 0.6, "B": 0.66, "C": 0.72}
PRICE_REL = {"A": 1.2, "B": 1.1, "C": 1.0}
TRANSPORT_CAP = 6000.0
PLAN_WEEKS = 24
INVENTORY_WEEKS = 2
TOP_K_Q1 = 50

MATERIALS = ["A", "B", "C"]
WEEK_COLS_HIST = [f"W{i:03d}" for i in range(1, 241)]
PLAN_WEEK_LABELS = [f"第{i:02d}周" for i in range(1, PLAN_WEEKS + 1)]
