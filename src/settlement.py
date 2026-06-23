"""KEPCO bill settlement: voltage/plan combination search (As-Is vs To-Be).

Ported from the price notebook (`최종가격산출함수.ipynb`).

⚠️ KNOWN GAP: the inner tariff calculator ``kepco_bill_300kw_plus()`` and its
``BillInputs`` payload were *called but never defined* in the original notebook
(the definition was lost). Everything around it — season/TOU assignment, monthly
bill-input aggregation, contract recommendation, and the combination-search
settlement — is ported faithfully. Drop the real implementation into
``kepco_bill_300kw_plus`` (and extend ``BillInputs`` if needed) to enable
``settlement_kepco_after_optimization``.

The MAIN ROI path does NOT use this module — see
``economics.calculate_advanced_financial_roi``, which is self-contained.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Tariff calculator payload + placeholder (lost from the original notebook)
# ---------------------------------------------------------------------------
@dataclass
class BillInputs:
    """Inputs for a single monthly KEPCO bill (>=300kW high-voltage)."""
    billing_demand_kw: float
    kwh_off: float
    kwh_mid: float
    kwh_peak: float
    season: str
    voltage: str
    plan: str
    climate_unit_won_per_kwh: float = 0.0
    fuel_adj_unit_won_per_kwh: float = 0.0


def kepco_bill_300kw_plus(x: "BillInputs") -> Dict[str, float]:
    """Compute a KEPCO industrial (>=300kW) monthly bill from :class:`BillInputs`.

    PLACEHOLDER — definition was lost from the original notebook. When restored,
    it must return at least:
        {"total_bill_won": ..., "base_charge_won": ..., "energy_charge_won": ...}
    """
    raise NotImplementedError(
        "kepco_bill_300kw_plus() is a placeholder. The original definition was "
        "lost from the price notebook. Provide the tariff table lookup "
        "(voltage A/B/C x plan I/II/III base+energy charges) to enable "
        "settlement_kepco_after_optimization(). The main ROI path "
        "(economics.calculate_advanced_financial_roi) does not need this."
    )


# ---------------------------------------------------------------------------
# 1) 15분 DF -> season/tou 부여 (2018 기준)
# ---------------------------------------------------------------------------
def _season_from_month(m: int) -> str:
    if m in (6, 7, 8):
        return "summer"
    if m in (3, 4, 5, 9, 10):
        return "spring_fall"
    return "winter"


def _add_season_tou(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col).reset_index(drop=True)

    df["season"] = df[date_col].dt.month.map(_season_from_month)

    hhmm = df[date_col].dt.hour * 60 + df[date_col].dt.minute

    def in_range(x, sh, sm, eh, em):
        return (x >= sh * 60 + sm) & (x < eh * 60 + em)

    offpeak = (hhmm >= 23 * 60) | (hhmm < 9 * 60)  # 경부하 공통
    peak_sf_smmr = in_range(hhmm, 10, 0, 12, 0) | in_range(hhmm, 13, 0, 17, 0)
    peak_winter = in_range(hhmm, 10, 0, 12, 0) | in_range(hhmm, 17, 0, 20, 0) | in_range(hhmm, 22, 0, 23, 0)

    tou = np.full(len(df), "mid", dtype=object)
    tou[offpeak.values] = "off"

    is_winter = (df["season"] == "winter").values
    tou[(~is_winter) & (peak_sf_smmr.values)] = "peak"
    tou[(is_winter) & (peak_winter.values)] = "peak"

    df["tou"] = tou
    return df


# ---------------------------------------------------------------------------
# 2) 월별 청구 입력값 생성
# ---------------------------------------------------------------------------
def _build_monthly_bill_inputs(
    df_15m: pd.DataFrame,
    date_col: str,
    usage_col: str,
    contract_kw_fixed: float,
    demand_rule: str = "max(contract, peak)",
) -> pd.DataFrame:
    df = _add_season_tou(df_15m, date_col=date_col)
    df["year_month"] = df[date_col].dt.to_period("M")

    pivot = (
        df.pivot_table(index=["year_month", "season"], columns="tou", values=usage_col,
                       aggfunc="sum", fill_value=0)
        .reset_index()
    )
    for c in ("off", "mid", "peak"):
        if c not in pivot.columns:
            pivot[c] = 0.0

    df["kw_15m"] = df[usage_col] * 4.0
    peak_kw = df.groupby("year_month")["kw_15m"].max().rename("measured_peak_kw").reset_index()

    out = pivot.merge(peak_kw, on="year_month", how="left")
    out = out.rename(columns={"off": "kwh_off", "mid": "kwh_mid", "peak": "kwh_peak"})

    if demand_rule == "peak":
        out["billing_demand_kw"] = out["measured_peak_kw"]
    else:
        out["billing_demand_kw"] = np.maximum(contract_kw_fixed, out["measured_peak_kw"])

    return out


# ---------------------------------------------------------------------------
# 3) 계약전력 자동 추천(옵션)
# ---------------------------------------------------------------------------
def _recommend_contract_kw(measured_peak_kw: float, mode: str = "ceil_10kw") -> float:
    if mode == "exact":
        return float(measured_peak_kw)
    if mode == "headroom_5pct":
        return float(measured_peak_kw * 1.05)
    if mode == "ceil_50kw":
        return float(np.ceil(measured_peak_kw / 50.0) * 50.0)
    return float(np.ceil(measured_peak_kw / 10.0) * 10.0)


# ---------------------------------------------------------------------------
# 4) 월별 최저비용 조합 탐색 + As-Is vs To-Be 절감액
# ---------------------------------------------------------------------------
def settlement_kepco_after_optimization(
    df_before_15m: pd.DataFrame,
    df_after_15m: pd.DataFrame,
    date_col: str = "date",
    usage_col: str = "Usage_kWh",
    contract_mode: str = "fixed",
    contract_kw_fixed: float = 660.0,
    contract_reco_mode: str = "ceil_10kw",
    voltages: Iterable[str] = ("A", "B", "C"),
    plans: Iterable[str] = ("I", "II", "III"),
    climate_unit_won_per_kwh: float = 0.0,
    fuel_adj_unit_won_per_kwh: float = 0.0,
    demand_rule: str = "max(contract, peak)",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """월별 As-Is vs To-Be 최적조합/비용/절감액과 전체 조합 그리드를 반환.

    Requires a working :func:`kepco_bill_300kw_plus` (currently a placeholder).
    """
    base_month = _build_monthly_bill_inputs(
        df_before_15m, date_col, usage_col, contract_kw_fixed=contract_kw_fixed, demand_rule=demand_rule
    )
    opt_month = _build_monthly_bill_inputs(
        df_after_15m, date_col, usage_col, contract_kw_fixed=contract_kw_fixed, demand_rule=demand_rule
    )

    combos = [(v, p) for v in voltages for p in plans]

    def _eval_monthly_grid(month_df: pd.DataFrame, tag: str) -> pd.DataFrame:
        local_rows = []
        for _, r in month_df.iterrows():
            ym = r["year_month"]
            season = r["season"]
            kwh_off = float(r["kwh_off"])
            kwh_mid = float(r["kwh_mid"])
            kwh_peak = float(r["kwh_peak"])
            measured_peak_kw = float(r["measured_peak_kw"])

            if contract_mode == "auto":
                contract_kw_used = _recommend_contract_kw(measured_peak_kw, mode=contract_reco_mode)
                billing_demand_kw = max(contract_kw_used, measured_peak_kw)
            else:
                contract_kw_used = float(contract_kw_fixed)
                billing_demand_kw = float(r["billing_demand_kw"])

            for voltage, plan in combos:
                x = BillInputs(
                    billing_demand_kw=billing_demand_kw,
                    kwh_off=kwh_off,
                    kwh_mid=kwh_mid,
                    kwh_peak=kwh_peak,
                    season=season,
                    voltage=voltage,
                    plan=plan,
                    climate_unit_won_per_kwh=float(climate_unit_won_per_kwh),
                    fuel_adj_unit_won_per_kwh=float(fuel_adj_unit_won_per_kwh),
                )
                bill = kepco_bill_300kw_plus(x)

                local_rows.append({
                    "tag": tag,
                    "year_month": ym,
                    "season": season,
                    "measured_peak_kw": measured_peak_kw,
                    "contract_kw_used": contract_kw_used,
                    "billing_demand_kw": billing_demand_kw,
                    "voltage": voltage,
                    "plan": plan,
                    "kwh_off": kwh_off,
                    "kwh_mid": kwh_mid,
                    "kwh_peak": kwh_peak,
                    "kwh_total": kwh_off + kwh_mid + kwh_peak,
                    "total_bill_won": bill["total_bill_won"],
                    "base_charge_won": bill["base_charge_won"],
                    "energy_charge_won": bill["energy_charge_won"],
                })
        return pd.DataFrame(local_rows)

    grid_base = _eval_monthly_grid(base_month, tag="before")
    grid_opt = _eval_monthly_grid(opt_month, tag="after")
    month_grid = pd.concat([grid_base, grid_opt], axis=0).reset_index(drop=True)

    best = (
        month_grid.sort_values(["tag", "year_month", "total_bill_won"], ascending=[True, True, True])
        .groupby(["tag", "year_month"], as_index=False)
        .head(1)
        .reset_index(drop=True)
    )

    before_best = best[best["tag"] == "before"].drop(columns=["tag"]).rename(
        columns=lambda c: f"{c}_before" if c != "year_month" else c
    )
    after_best = best[best["tag"] == "after"].drop(columns=["tag"]).rename(
        columns=lambda c: f"{c}_after" if c != "year_month" else c
    )

    compare = before_best.merge(after_best, on="year_month", how="inner")
    compare["won_saved"] = compare["total_bill_won_before"] - compare["total_bill_won_after"]
    compare["kwh_saved"] = compare["kwh_total_before"] - compare["kwh_total_after"]
    compare["peak_kw_saved"] = compare["measured_peak_kw_before"] - compare["measured_peak_kw_after"]
    compare = compare.sort_values("year_month").reset_index(drop=True)

    return compare, month_grid
