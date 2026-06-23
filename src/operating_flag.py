"""Operating-state flag derived from CO2 + motor utilization.

  0 = OFF        (no CO2 -> not operating)
  2 = Production  (CO2 present AND motor utilization > 5%)
  1 = Wait/Idle   (default)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MOTOR_PRODUCTION_THRESHOLD = 5.0


def add_operating_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Add the 3-state ``Is_Operating_Flag`` column.

    Requires ``CO2_ppm`` (restored) and ``Motor_Operating_Rate`` (power feature).
    """
    df = df.copy()
    conditions = [
        (df["CO2_ppm"] == 0),  # OFF
        (df["CO2_ppm"] > 0) & (df["Motor_Operating_Rate"] > MOTOR_PRODUCTION_THRESHOLD),
    ]
    choices = [0, 2]
    df["Is_Operating_Flag"] = np.select(conditions, choices, default=1)
    return df
