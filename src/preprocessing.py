"""Feature engineering: time, cyclic, and power-derived features.

All functions are pure: they operate on a copy and return a new DataFrame.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from . import config


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """NSM/date-derived calendar features + KEPCO season."""
    df = df.copy()
    df["Hour"] = df["NSM"] // 3600
    df["DayOfWeek"] = df["date"].dt.dayofweek  # 0=Mon, 6=Sun
    df["Month"] = df["date"].dt.month
    df["Year"] = df["date"].dt.year
    df["Is_Weekend"] = df["DayOfWeek"].apply(lambda x: 1 if x >= 5 else 0)

    df["Season"] = df["Month"].map(
        lambda x: "Spring_Fall"
        if x in config.SPRING_FALL_MONTHS
        else "Summer"
        if x in config.SUMMER_MONTHS
        else "Winter"
    )
    return df


def add_cyclic_features(df: pd.DataFrame) -> pd.DataFrame:
    """sin/cos encoding for cyclic columns."""
    df = df.copy()
    for col, period in config.CYCLIC_TARGETS.items():
        df[f"{col}_sin"] = np.sin(2 * np.pi * df[col].astype(float) / period)
        df[f"{col}_cos"] = np.cos(2 * np.pi * df[col].astype(float) / period)
    return df


def add_power_features(df: pd.DataFrame) -> pd.DataFrame:
    """Physical power-quality features.

    Note: ``Motor_Operating_Rate`` / ``Capacitor_Operating_Rate`` are normalized
    against the dataset-wide max reactive power (treated as 100% utilization).
    See :func:`get_reactive_maxima`.
    """
    df = df.copy()
    lag = df["Lagging_Current_Reactive_Power_kVarh"]
    lead = df["Leading_Current_Reactive_Power_kVarh"]
    usage = df["Usage_kWh"]

    # 순무효전력 기반 물리적 역률
    df["Apparent_Power"] = np.sqrt(usage**2 + (lag - lead) ** 2)
    df["PF_Physical"] = np.where(df["Apparent_Power"] > 0, usage / df["Apparent_Power"], 1.0)

    # 지상/진상 각각 역률 (한전 관리용)
    df["PF_Lagging"] = usage / np.sqrt(usage**2 + lag**2)
    df["PF_Leading"] = usage / np.sqrt(usage**2 + lead**2)

    # 전력 사용 변동성 (1시간 = 15분*4 이동 표준편차)
    df["Motor_Moving_Avg_1h_std"] = usage.rolling(window=4, min_periods=2).std().bfill()

    # 모터/커패시터 가동 비중 (%) — 데이터셋 최대 무효전력을 100% 가동으로 가정
    max_lagging = lag.max()
    df["Motor_Operating_Rate"] = (lag / max_lagging) * 100
    max_leading = lead.max()
    df["Capacitor_Operating_Rate"] = (lead / max_leading) * 100

    # 무효전력 총량 및 활성비
    df["Q_total_abs"] = lag + lead
    df["Motor_Ratio"] = lag / df["Q_total_abs"]
    df["Capacitor_Ratio"] = lead / df["Q_total_abs"]

    # 콘덴서 과보상 의심 구간
    df["Over_Correction_Flag"] = (df["Capacitor_Ratio"] > 0.6) & (df["PF_Physical"] > 0.98)
    return df


def get_reactive_maxima(df: pd.DataFrame) -> Dict[str, float]:
    """Dataset-wide maxima needed by the simulator to reconstruct physical kVarh.

    These constants (``max_lagging``/``max_leading``) feed into
    ``HybridFastSimulator`` to reconstruct physical reactive power.
    """
    return {
        "max_lagging": float(df["Lagging_Current_Reactive_Power_kVarh"].max()),
        "max_leading": float(df["Leading_Current_Reactive_Power_kVarh"].max()),
        "max_apparent": float(df["Apparent_Power"].max()),
    }
