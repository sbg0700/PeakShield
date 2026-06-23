"""Raw data loading + column normalization + chronological ordering."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from . import config


def load_raw_steel_data(path: Optional[Path] = None) -> pd.DataFrame:
    """Load the raw 15-minute steel-industry energy CSV.

    The raw header varies slightly between exported versions, so columns are
    overridden *positionally* with :data:`config.COLUMN_NAMES`. The ``date``
    column is then parsed
    (day-first), sorted ascending, and the index reset.
    """
    path = Path(path) if path is not None else config.RAW_CSV
    df = pd.read_csv(path)

    if len(df.columns) != len(config.COLUMN_NAMES):
        raise ValueError(
            f"Expected {len(config.COLUMN_NAMES)} columns, got {len(df.columns)} "
            f"in {path}. Columns: {list(df.columns)}"
        )
    df.columns = config.COLUMN_NAMES

    # Chronological ordering is the critical precondition for rolling features.
    df["date"] = pd.to_datetime(df["date"], dayfirst=True)
    df = df.sort_values(by="date", ascending=True).reset_index(drop=True)
    return df
