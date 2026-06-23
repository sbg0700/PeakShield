"""01 — Build the engineered feature table from raw data.

raw CSV  ->  features.parquet  (+ reactive_maxima.json)

Pipeline order:
    load -> time -> cyclic -> power -> CO2 restore -> operating flag -> PSI
"""
import json

import _bootstrap  # noqa: F401
from src import config, data_loading, preprocessing, co2_imputation, operating_flag, psi


def main() -> None:
    config.ensure_dirs()

    print(f"Loading raw data: {config.RAW_CSV}")
    df = data_loading.load_raw_steel_data()

    df = preprocessing.add_time_features(df)
    df = preprocessing.add_cyclic_features(df)
    df = preprocessing.add_power_features(df)
    maxima = preprocessing.get_reactive_maxima(df)

    df = co2_imputation.restore_co2(df)
    df = operating_flag.add_operating_flag(df)
    df = psi.add_psi(df)

    df.to_parquet(config.FEATURES_PARQUET)
    with open(config.REACTIVE_MAXIMA_JSON, "w", encoding="utf-8") as f:
        json.dump(maxima, f, indent=2)

    print(f"✅ features: {df.shape[0]:,} rows x {df.shape[1]} cols -> {config.FEATURES_PARQUET}")
    print(f"   reactive maxima -> {config.REACTIVE_MAXIMA_JSON}: {maxima}")
    print(f"   Is_Operating_Flag counts: {df['Is_Operating_Flag'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
