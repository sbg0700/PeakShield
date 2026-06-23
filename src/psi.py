"""Process Stress Index (PSI) — infrastructure vs operational, and AI comparison.

PSI (operational, the adopted metric):
    PSI = 0.5*Motor_Operating_Rate + 0.3*(100 - PF_Physical) + 0.2*Motor_Volatility_Scaled
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

ROLLING_WINDOW = 4  # 1 hour at 15-minute resolution


def add_psi(df: pd.DataFrame) -> pd.DataFrame:
    """Compute PSI_Infrastructure / PSI_Operational / PSI / PSI_Delta.

    Requires ``Motor_Operating_Rate``, ``PF_Physical`` and ``Apparent_Power``.
    """
    df = df.copy()

    # Volatility (rolling std of motor utilization) scaled to 0-100.
    df["Motor_Volatility"] = (
        df["Motor_Operating_Rate"].rolling(window=ROLLING_WINDOW).std().fillna(0)
    )
    vol_min = df["Motor_Volatility"].min()
    vol_max = df["Motor_Volatility"].max()
    df["Motor_Volatility_Scaled"] = (
        (df["Motor_Volatility"] - vol_min) / (vol_max - vol_min)
    ) * 100

    # 1안: 물리적 한계 기반 (Infrastructure)
    max_apparent = df["Apparent_Power"].max()
    df["PSI_Infrastructure"] = (df["Apparent_Power"] / max_apparent) * 100

    # 2안: 복합 운영 스트레스 (Operational) — 채택 지표
    df["PSI_Operational"] = (
        (df["Motor_Operating_Rate"] * 0.5)
        + ((100 - df["PF_Physical"]) * 0.3)
        + (df["Motor_Volatility_Scaled"] * 0.2)
    )
    df["PSI"] = df["PSI_Operational"].clip(0, 100)
    df["PSI_Delta"] = df["PSI_Operational"] - df["PSI_Infrastructure"]
    return df


def get_psi_baseline_maxima(df: pd.DataFrame) -> Dict[str, float]:
    """Baseline (human/as-is) maxima used to scale the AI-side PSI."""
    return {
        "max_lagging": float(df["Lagging_Current_Reactive_Power_kVarh"].max()),
        "max_leading": float(df["Leading_Current_Reactive_Power_kVarh"].max()),
        "max_apparent": float(df["Apparent_Power"].max()),
        "max_volatility": float(
            df["Motor_Operating_Rate"].rolling(window=ROLLING_WINDOW).std().max()
        ),
    }


def calculate_psi_comparison(
    df_res: pd.DataFrame, original_max_values: Dict[str, float]
) -> pd.DataFrame:
    """Reconstruct AI-side physical quantities and AI_PSI on the same scale.

    ``df_res`` must contain the simulator outputs ``AI_Motor_Operating_Rate``,
    ``AI_Capacitor_Operating_Rate`` and ``AI_Usage_kWh``.
    """
    df = df_res.copy()
    max_lag = original_max_values["max_lagging"]
    max_lead = original_max_values["max_leading"]

    df["AI_Lagging_kVarh"] = (df["AI_Motor_Operating_Rate"] / 100) * max_lag
    df["AI_Leading_kVarh"] = (df["AI_Capacitor_Operating_Rate"] / 100) * max_lead

    df["AI_Apparent_Power"] = np.sqrt(
        df["AI_Usage_kWh"] ** 2 + (df["AI_Lagging_kVarh"] - df["AI_Leading_kVarh"]) ** 2
    )
    df["AI_PF_Physical"] = np.where(
        df["AI_Apparent_Power"] > 0,
        (df["AI_Usage_kWh"] / df["AI_Apparent_Power"]) * 100,
        100,
    )

    df["AI_Motor_Volatility"] = (
        df["AI_Motor_Operating_Rate"].rolling(window=ROLLING_WINDOW).std().fillna(0)
    )
    vol_max = original_max_values["max_volatility"]
    df["AI_Motor_Volatility_Scaled"] = (df["AI_Motor_Volatility"] / vol_max) * 100

    df["AI_PSI"] = (
        (df["AI_Motor_Operating_Rate"] * 0.5)
        + ((100 - df["AI_PF_Physical"]) * 0.3)
        + (df["AI_Motor_Volatility_Scaled"] * 0.2)
    ).clip(0, 100)
    return df
