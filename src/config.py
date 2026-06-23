"""Central configuration: paths, column names, feature lists, constants.

All other modules import from here so the pipeline has a single source of truth.
"""
from __future__ import annotations

from pathlib import Path

# ----------------------------------------------------------------------------
# Paths (resolved relative to the repo root = parent of this src/ directory)
# ----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"

RAW_CSV = RAW_DIR / "Steel_industry_data.csv"
CONFIG_JSON = CONFIG_DIR / "electricity_config_master.json"

# Pipeline artifacts
FEATURES_PARQUET = PROCESSED_DIR / "features.parquet"
REACTIVE_MAXIMA_JSON = PROCESSED_DIR / "reactive_maxima.json"
USAGE_MODEL_PATH = MODELS_DIR / "usage_model.json"
PF_MODEL_PATH = MODELS_DIR / "pf_model.json"

# ----------------------------------------------------------------------------
# Raw schema — positional rename applied right after read_csv
# ----------------------------------------------------------------------------
COLUMN_NAMES = [
    "date",
    "Usage_kWh",
    "Lagging_Current_Reactive_Power_kVarh",
    "Leading_Current_Reactive_Power_kVarh",
    "CO2_ppm",
    "Lagging_Current_Power_Factor",
    "Leading_Current_Power_Factor",
    "NSM",
    "WeekStatus",
    "Day_of_week",
    "Load_Type",
]

# ----------------------------------------------------------------------------
# Feature engineering constants
# ----------------------------------------------------------------------------
# Cyclic-encoded columns -> period
CYCLIC_TARGETS = {"Month": 12, "DayOfWeek": 7}

# KEPCO seasons
SUMMER_MONTHS = [6, 7, 8]
SPRING_FALL_MONTHS = [3, 4, 5, 9, 10]
# everything else -> Winter

# ----------------------------------------------------------------------------
# Surrogate model: feature list + targets
# ----------------------------------------------------------------------------
FEATURES = [
    "Hour",
    "Is_Weekend",
    "Month_sin",
    "Month_cos",
    "DayOfWeek_sin",
    "DayOfWeek_cos",
    "Motor_Operating_Rate",
    "Capacitor_Operating_Rate",
    "Is_Operating_Flag",
    "Motor_Moving_Avg_1h_std",
]
TARGET_USAGE = "Usage_kWh"
TARGET_PF = "PF_Physical"

# XGBoost categorical columns
CATEGORICAL_FEATURES = ["Hour", "Is_Weekend", "Is_Operating_Flag"]

# Time-ordered train/test split ratio
TRAIN_SPLIT = 0.8

# ----------------------------------------------------------------------------
# Optimization / simulation defaults
# ----------------------------------------------------------------------------
DEFAULT_SCENARIOS = [
    "2018_industrial_HV_A_opt3",
    "2026_industrial_HV_A_opt3",
]
DEFAULT_LABOR_PREMIUM = 20.0  # 야간 인건비 할증 (원/kWh)


def ensure_dirs() -> None:
    """Create output directories if missing (idempotent)."""
    for d in (PROCESSED_DIR, MODELS_DIR, REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
