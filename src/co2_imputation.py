"""CO2 sensor-failure detection and RandomForest-based restoration.

The January-Tuesday sensor outage produces rows where Usage_kWh > 0 but
CO2_ppm == 0; these are masked to NaN and predicted from a RandomForest trained
on the clean rows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor


def build_target_mask(df: pd.DataFrame) -> pd.Series:
    """Boolean mask of corrupted CO2 readings."""
    return (
        (df["Month"] == 1)
        & (df["Day_of_week"] == "Tuesday")
        & (df["Usage_kWh"] > 0)
        & (df["CO2_ppm"] == 0)
    )


def restore_co2(df: pd.DataFrame, random_state: int = 42) -> pd.DataFrame:
    """Detect and restore corrupted CO2 readings.

    Requires the ``Hour`` feature (run :func:`preprocessing.add_time_features`
    first). Returns a copy with ``CO2_ppm`` repaired in place.
    """
    df = df.copy()
    target_mask = build_target_mask(df)
    if int(target_mask.sum()) == 0:
        return df

    # Mask corrupted points, then one-hot encode categoricals for the model.
    df.loc[target_mask, "CO2_ppm"] = np.nan
    df_ml = pd.get_dummies(
        df, columns=["WeekStatus", "Day_of_week", "Load_Type"], drop_first=True
    )

    features = ["Usage_kWh", "NSM", "Hour"] + [
        c for c in df_ml.columns if "Load_Type_" in c
    ]
    target = "CO2_ppm"

    train_df = df_ml[df_ml[target].notnull()]
    predict_df = df_ml[df_ml[target].isnull()]

    rf = RandomForestRegressor(n_estimators=100, random_state=random_state, n_jobs=-1)
    rf.fit(train_df[features], train_df[target])

    predicted = rf.predict(predict_df[features])
    df.loc[target_mask, "CO2_ppm"] = predicted
    return df
