"""Surrogate models: XGBoost regressors for Usage_kWh and PF_Physical.

Monotonic constraints force usage/PF to be non-decreasing in the *_Operating_Rate
control variables, encoding the physical prior used by the optimizer.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, r2_score

from . import config

_XGB_PARAMS = dict(
    n_estimators=1500,
    learning_rate=0.03,
    max_depth=10,
    subsample=0.8,
    colsample_bytree=0.4,
    n_jobs=-1,
    random_state=42,
    enable_categorical=True,
    early_stopping_rounds=50,
)


def _build_model(monotone_constraints: Dict[str, int]) -> xgb.XGBRegressor:
    return xgb.XGBRegressor(monotone_constraints=monotone_constraints, **_XGB_PARAMS)


def _cast_categoricals(df: pd.DataFrame, features: List[str]) -> pd.DataFrame:
    df = df.copy()
    for col in config.CATEGORICAL_FEATURES:
        if col in features:
            df[col] = df[col].astype("category")
    return df


def train_surrogates(
    df: pd.DataFrame,
    features: Optional[List[str]] = None,
    target_usage: str = config.TARGET_USAGE,
    target_pf: str = config.TARGET_PF,
    train_split: float = config.TRAIN_SPLIT,
) -> Tuple[xgb.XGBRegressor, xgb.XGBRegressor, Dict[str, float]]:
    """Train the Usage and PF surrogate models on a chronological split.

    Returns ``(model_usage, model_pf, metrics)`` where metrics holds test-set
    MAE/R2 for both targets.
    """
    features = features or config.FEATURES
    target_df = _cast_categoricals(df, features)

    # Monotonic constraint: +1 for control rates, 0 otherwise.
    monotone_constraints = {f: 1 if "Operating_Rate" in f else 0 for f in features}

    split_idx = int(len(target_df) * train_split)
    train_df = target_df.iloc[:split_idx]
    test_df = target_df.iloc[split_idx:]

    X_train, X_test = train_df[features], test_df[features]
    y_train_usage, y_test_usage = train_df[target_usage], test_df[target_usage]
    y_train_pf, y_test_pf = train_df[target_pf], test_df[target_pf]

    model_usage = _build_model(monotone_constraints)
    model_usage.fit(X_train, y_train_usage, eval_set=[(X_test, y_test_usage)], verbose=False)

    model_pf = _build_model(monotone_constraints)
    model_pf.fit(X_train, y_train_pf, eval_set=[(X_test, y_test_pf)], verbose=False)

    preds_usage = model_usage.predict(X_test)
    preds_pf = model_pf.predict(X_test)
    metrics = {
        "usage_mae": float(mean_absolute_error(y_test_usage, preds_usage)),
        "usage_r2": float(r2_score(y_test_usage, preds_usage)),
        "pf_mae": float(mean_absolute_error(y_test_pf, preds_pf)),
        "pf_r2": float(r2_score(y_test_pf, preds_pf)),
    }
    return model_usage, model_pf, metrics


def feature_importances(model: xgb.XGBRegressor, features: List[str]) -> pd.Series:
    """Return feature importances as a sorted Series (no plot)."""
    return pd.Series(model.feature_importances_, index=features).sort_values(ascending=False)


def save_models(
    model_usage: xgb.XGBRegressor,
    model_pf: xgb.XGBRegressor,
    usage_path: Path = config.USAGE_MODEL_PATH,
    pf_path: Path = config.PF_MODEL_PATH,
) -> None:
    Path(usage_path).parent.mkdir(parents=True, exist_ok=True)
    model_usage.save_model(str(usage_path))
    model_pf.save_model(str(pf_path))


def load_models(
    usage_path: Path = config.USAGE_MODEL_PATH,
    pf_path: Path = config.PF_MODEL_PATH,
) -> Tuple[xgb.XGBRegressor, xgb.XGBRegressor]:
    model_usage = xgb.XGBRegressor(enable_categorical=True)
    model_usage.load_model(str(usage_path))
    model_pf = xgb.XGBRegressor(enable_categorical=True)
    model_pf.load_model(str(pf_path))
    return model_usage, model_pf
