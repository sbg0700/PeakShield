"""Dashboard streaming export: realtime cost + PSI per 15-minute step.

Produces the slim per-row CSVs consumed by ``dashboard/sender.py``
(final_2018ver.csv / final_2026ver.csv).
"""
from __future__ import annotations

from typing import Dict

import pandas as pd

from . import economics, psi

DASHBOARD_STREAM_COLS = [
    "date",
    "Hour",
    "Current_Unit_Price",
    "Human_Energy_Cost",
    "AI_Energy_Cost",
    "Realtime_Savings_Won",
    "PSI",
    "AI_PSI",
]


def prepare_dashboard_stream_data(
    df_res: pd.DataFrame,
    scenario_config: dict,
    original_max_values: Dict[str, float],
) -> pd.DataFrame:
    """대시보드 실시간 그래프용 통합 데이터프레임 생성 (요금 + PSI) — cells 97-98."""
    df = economics.append_realtime_energy_cost_dynamic(df_res, scenario_config)
    df = psi.calculate_psi_comparison(df, original_max_values)
    return df[DASHBOARD_STREAM_COLS]
