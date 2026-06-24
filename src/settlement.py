"""KEPCO bill settlement: voltage/plan combination search (As-Is vs To-Be).

Finds the cheapest voltage (A/B/C) x plan (I/II/III) combination per month and
compares the pre- vs post-optimization bill.

The main ROI path does NOT use this module — see
``economics.calculate_advanced_financial_roi``, which is self-contained.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Literal, Tuple

import numpy as np
import pandas as pd

Season = Literal["summer", "spring_fall", "winter"]
Voltage = Literal["A", "B", "C"]
Plan = Literal["I", "II", "III"]


# ---------------------------------------------------------------------------
# Rounding helpers (per KEPCO billing rules)
# ---------------------------------------------------------------------------
def round_half_up_won(x: float) -> int:
    """원 단위 4사5입 (소수 첫째에서 반올림)."""
    return int(x + 0.5)


def truncate_under_10won(x: float) -> int:
    """10원 미만 절사."""
    return int(x // 10 * 10)


# ---------------------------------------------------------------------------
# 2025.04.01 시행 요금표: 계약전력 300kW 이상 산업용(을), 고압 A/B/C × 선택 I/II/III
# base_kw: 기본요금(원/kW), kwh: 계절별 시간대(경 off / 중 mid / 최 peak) 단가(원/kWh)
# ---------------------------------------------------------------------------
RATES_300KW_PLUS = {
    "A": {  # 고압 A
        "I":  {"base_kw": 7220, "kwh": {"summer": {"off": 116.4, "mid": 169.3, "peak": 251.4},
                                        "spring_fall": {"off": 116.4, "mid": 138.9, "peak": 169.6},
                                        "winter": {"off": 123.4, "mid": 169.5, "peak": 227.0}}},
        "II": {"base_kw": 8320, "kwh": {"summer": {"off": 110.9, "mid": 163.8, "peak": 245.9},
                                        "spring_fall": {"off": 110.9, "mid": 133.4, "peak": 164.1},
                                        "winter": {"off": 117.9, "mid": 164.0, "peak": 221.5}}},
        "III":{"base_kw": 9810, "kwh": {"summer": {"off": 110.0, "mid": 163.2, "peak": 233.5},
                                        "spring_fall": {"off": 110.0, "mid": 132.1, "peak": 155.8},
                                        "winter": {"off": 117.3, "mid": 163.4, "peak": 210.3}}},
    },
    "B": {  # 고압 B
        "I":  {"base_kw": 6630, "kwh": {"summer": {"off": 126.3, "mid": 178.6, "peak": 259.8},
                                        "spring_fall": {"off": 126.3, "mid": 148.6, "peak": 178.9},
                                        "winter": {"off": 133.3, "mid": 178.6, "peak": 234.8}}},
        "II": {"base_kw": 7380, "kwh": {"summer": {"off": 122.5, "mid": 174.8, "peak": 256.0},
                                        "spring_fall": {"off": 122.5, "mid": 144.8, "peak": 175.1},
                                        "winter": {"off": 129.5, "mid": 174.8, "peak": 231.0}}},
        "III":{"base_kw": 8190, "kwh": {"summer": {"off": 120.8, "mid": 173.1, "peak": 254.4},
                                        "spring_fall": {"off": 120.8, "mid": 143.2, "peak": 173.5},
                                        "winter": {"off": 127.9, "mid": 173.1, "peak": 229.3}}},
    },
    "C": {  # 고압 C
        "I":  {"base_kw": 6590, "kwh": {"summer": {"off": 125.8, "mid": 178.7, "peak": 259.6},
                                        "spring_fall": {"off": 125.8, "mid": 148.7, "peak": 179.1},
                                        "winter": {"off": 132.7, "mid": 178.3, "peak": 234.9}}},
        "II": {"base_kw": 7520, "kwh": {"summer": {"off": 121.1, "mid": 174.0, "peak": 254.9},
                                        "spring_fall": {"off": 121.1, "mid": 144.0, "peak": 174.4},
                                        "winter": {"off": 128.0, "mid": 173.6, "peak": 230.2}}},
        "III":{"base_kw": 8090, "kwh": {"summer": {"off": 120.0, "mid": 172.9, "peak": 253.8},
                                        "spring_fall": {"off": 120.0, "mid": 142.9, "peak": 173.3},
                                        "winter": {"off": 126.9, "mid": 172.5, "peak": 229.1}}},
    },
}


@dataclass
class BillInputs:
    """Inputs for a single monthly KEPCO bill (>=300kW high-voltage)."""
    billing_demand_kw: float  # 청구(최대)수요전력 kW — 기본요금에 곱해지는 값
    kwh_off: float            # 경부하 사용량(kWh)
    kwh_mid: float            # 중간부하 사용량(kWh)
    kwh_peak: float           # 최대부하 사용량(kWh)
    season: Season            # summer / spring_fall / winter
    voltage: Voltage          # A / B / C
    plan: Plan                # I / II / III
    # 기후환경요금·연료비조정 단가는 변동값이라 입력으로 받음
    climate_unit_won_per_kwh: float = 0.0
    fuel_adj_unit_won_per_kwh: float = 0.0


def kepco_bill_300kw_plus(x: "BillInputs") -> Dict[str, int]:
    """KEPCO 산업용(을) 300kW 이상 월 청구액 계산.

    반환: base/energy/climate/fuel/electric/vat/fund/total 각 원(整) 단위.
    """
    rate = RATES_300KW_PLUS[x.voltage][x.plan]
    base_rate = rate["base_kw"]
    unit = rate["kwh"][x.season]

    # 1) 기본요금
    base_charge = x.billing_demand_kw * base_rate

    # 2) 전력량요금
    energy_charge = (
        x.kwh_off * unit["off"]
        + x.kwh_mid * unit["mid"]
        + x.kwh_peak * unit["peak"]
    )

    # 3) 기후환경요금 & 연료비조정요금
    total_kwh = x.kwh_off + x.kwh_mid + x.kwh_peak
    climate_charge = x.climate_unit_won_per_kwh * total_kwh
    fuel_adj_charge = x.fuel_adj_unit_won_per_kwh * total_kwh

    # 4) 세전 전기요금
    electric_charge = base_charge + energy_charge + climate_charge + fuel_adj_charge

    # 5) 부가가치세 (10%)
    vat = round_half_up_won(electric_charge * 0.10)

    # 6) 전력산업기반기금 (2.7%, 10원 미만 절사)
    fund = truncate_under_10won(electric_charge * 0.027)

    # 7) 최종요금
    total_bill = round_half_up_won(electric_charge) + vat + fund

    return {
        "base_charge_won": round_half_up_won(base_charge),
        "energy_charge_won": round_half_up_won(energy_charge),
        "climate_charge_won": round_half_up_won(climate_charge),
        "fuel_adj_charge_won": round_half_up_won(fuel_adj_charge),
        "electric_charge_won": round_half_up_won(electric_charge),
        "vat_won": vat,
        "fund_won": fund,
        "total_bill_won": total_bill,
    }


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
