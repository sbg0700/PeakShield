"""Economic evaluation: KEPCO power-factor penalty, financial ROI, realtime cost.

Ported from notebook cells 78 (monthly PF penalty), 79 (regulation-form PF
columns / defense), 82 (advanced ROI), 96 (vectorized realtime energy cost),
and 91-92 (final KEPCO-ready dataframe).

Plotting from the original cells is intentionally omitted (kept in EDA notebooks);
the pure computations the pipeline depends on are preserved.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 1) 월별 한전 역률 페널티 (기본요금 가감률) — cell 78
# ---------------------------------------------------------------------------
def calculate_monthly_kepco_pf_penalty(
    df_result: pd.DataFrame, scenario_config: dict, verbose: bool = False
) -> pd.DataFrame:
    """월별 지상(낮)/진상(밤) 역률과 기본요금 증감률(%)을 산출 (cell 78).

    AI 가정: 사용량(P)만 AI_Usage_kWh로 바뀌고 무효전력(Q)은 원본 kvarh 유지.
    """
    pf_logic = scenario_config.get(
        "pf_logic", {"lag_target": 90, "lead_target": 95, "lag_start": 9, "lag_end": 23}
    )
    lag_target_pct = pf_logic["lag_target"]
    lead_target_pct = pf_logic["lead_target"]
    lag_start = pf_logic["lag_start"]
    lag_end = pf_logic["lag_end"]

    df = df_result.copy()
    time_col = "hour" if "hour" in df.columns else "Hour"

    def calc_lag_penalty(pf):
        pf_pct = np.floor(pf * 100)
        if pf_pct < lag_target_pct:
            return (lag_target_pct - pf_pct) * 0.2
        elif lag_target_pct <= pf_pct <= 95:
            return (lag_target_pct - pf_pct) * 0.2
        else:
            return -1.0 if pf_pct > 95 else 0.0

    def calc_lead_penalty(pf):
        pf_pct = np.floor(pf * 100)
        if pf_pct < lead_target_pct:
            return (lead_target_pct - pf_pct) * 0.2
        return 0.0

    monthly_results = []
    for month, group in df.groupby("Month"):
        day_mask = (group[time_col] >= lag_start) & (group[time_col] < lag_end)
        day_group = group.loc[day_mask]
        night_group = group.loc[~day_mask]

        # Human PF (규정형)
        P_day_h = day_group["Usage_kWh"].sum()
        Q_day_h = day_group["Lagging_Current_Reactive_Power_kVarh"].sum()
        human_lag_pf = P_day_h / np.sqrt(P_day_h**2 + Q_day_h**2) if P_day_h > 0 else 1.0

        P_night_h = night_group["Usage_kWh"].sum()
        Q_night_h = night_group["Leading_Current_Reactive_Power_kVarh"].sum()
        human_lead_pf = P_night_h / np.sqrt(P_night_h**2 + Q_night_h**2) if P_night_h > 0 else 1.0

        # AI PF (P만 AI로, Q는 원본 유지)
        P_day_ai = day_group["AI_Usage_kWh"].sum()
        ai_lag_pf = P_day_ai / np.sqrt(P_day_ai**2 + Q_day_h**2) if P_day_ai > 0 else 1.0

        P_night_ai = night_group["AI_Usage_kWh"].sum()
        ai_lead_pf = P_night_ai / np.sqrt(P_night_ai**2 + Q_night_h**2) if P_night_ai > 0 else 1.0

        h_penalty = calc_lag_penalty(human_lag_pf) + calc_lead_penalty(human_lead_pf)
        ai_penalty = calc_lag_penalty(ai_lag_pf) + calc_lead_penalty(ai_lead_pf)

        monthly_results.append({
            "Month": month,
            "Human_Lag_PF(%)": round(human_lag_pf * 100, 2),
            "AI_Lag_PF(%)": round(ai_lag_pf * 100, 2),
            "Human_Lead_PF(%)": round(human_lead_pf * 100, 2),
            "AI_Lead_PF(%)": round(ai_lead_pf * 100, 2),
            "Human_BaseRate_Adj(%)": round(h_penalty, 2),
            "AI_BaseRate_Adj(%)": round(ai_penalty, 2),
        })

    result_df = pd.DataFrame(monthly_results).set_index("Month")
    if verbose:
        print(result_df)
    return result_df


# ---------------------------------------------------------------------------
# 2) 규정형 PF 컬럼 생성 + 방어율 검증 — cell 79
# ---------------------------------------------------------------------------
def analyze_kepco_pf_defense(
    df_result: pd.DataFrame,
    lag_start: int = 9,
    lag_end: int = 23,
    lag_th: float = 0.90,
    lead_th: float = 0.95,
    verbose: bool = False,
) -> pd.DataFrame:
    """규정형(시간대별 지상/진상 분리) PF 컬럼을 df에 추가하고 반환 (cell 79, plot 제외).

    낮(지상): PF = P / sqrt(P^2 + Q_lag^2);  밤(진상): PF = P / sqrt(P^2 + Q_lead^2).
    AI는 Usage만 AI로 바뀌고 Q는 원본 유지하는 보수 가정.
    """
    df = df_result.copy()
    time_col = "hour" if "hour" in df.columns else "Hour"

    day_mask = (df[time_col] >= lag_start) & (df[time_col] < lag_end)
    night_mask = ~day_mask

    P_h = df["Usage_kWh"].to_numpy()
    Q_lag = df["Lagging_Current_Reactive_Power_kVarh"].to_numpy()
    Q_lead = df["Leading_Current_Reactive_Power_kVarh"].to_numpy()

    denom_h_day = np.sqrt(P_h**2 + Q_lag**2)
    human_pf_day = np.where(denom_h_day > 0, P_h / denom_h_day, 1.0)
    denom_h_night = np.sqrt(P_h**2 + Q_lead**2)
    human_pf_night = np.where(denom_h_night > 0, P_h / denom_h_night, 1.0)

    P_ai = df["AI_Usage_kWh"].to_numpy()
    denom_ai_day = np.sqrt(P_ai**2 + Q_lag**2)
    ai_pf_day = np.where(denom_ai_day > 0, P_ai / denom_ai_day, 1.0)
    denom_ai_night = np.sqrt(P_ai**2 + Q_lead**2)
    ai_pf_night = np.where(denom_ai_night > 0, P_ai / denom_ai_night, 1.0)

    df["Human_PF_KEPCO_Day"] = np.clip(human_pf_day, 0, 1.0)
    df["Human_PF_KEPCO_Night"] = np.clip(human_pf_night, 0, 1.0)
    df["AI_PF_KEPCO_Day"] = np.clip(ai_pf_day, 0, 1.0)
    df["AI_PF_KEPCO_Night"] = np.clip(ai_pf_night, 0, 1.0)

    if verbose:
        human_day_pen = df[day_mask & (df["Human_PF_KEPCO_Day"] < lag_th)]
        human_night_pen = df[night_mask & (df["Human_PF_KEPCO_Night"] < lead_th)]
        ai_day_pen = df[day_mask & (df["AI_PF_KEPCO_Day"] < lag_th)]
        ai_night_pen = df[night_mask & (df["AI_PF_KEPCO_Night"] < lead_th)]
        print("=== 한전 기준(지상/진상) 역률 방어율 [규정형 PF] ===")
        print(f"[Original] 주간 페널티 {len(human_day_pen):,d}h / 야간 {len(human_night_pen):,d}h")
        print(f"[AI]       주간 페널티 {len(ai_day_pen):,d}h / 야간 {len(ai_night_pen):,d}h")

    return df


# ---------------------------------------------------------------------------
# 3) 고도화된 재무 ROI — cell 82
# ---------------------------------------------------------------------------
def calculate_advanced_financial_roi(
    df_result: pd.DataFrame, scenario_config: dict, labor_premium: float = 20.0
) -> Dict[str, float]:
    """월 누적 역률 기반 기본요금 가감을 반영한 재무 평가 (cell 82)."""
    base_rate = scenario_config["base_rate"]
    time_col = "hour" if "hour" in df_result.columns else "Hour"

    # 1. 월별 기본요금 (월 최대 피크 * 4 -> kW)
    monthly_human_peak = df_result.groupby("Month")["Usage_kWh"].max() * 4
    monthly_ai_peak = df_result.groupby("Month")["AI_Usage_kWh"].max() * 4

    df_pf_report = calculate_monthly_kepco_pf_penalty(df_result, scenario_config)

    human_base_cost = 0.0
    ai_base_cost = 0.0
    for month in monthly_human_peak.index:
        h_peak = monthly_human_peak[month]
        a_peak = monthly_ai_peak[month]
        h_adj = df_pf_report.loc[month, "Human_BaseRate_Adj(%)"] / 100.0
        a_adj = df_pf_report.loc[month, "AI_BaseRate_Adj(%)"] / 100.0
        human_base_cost += h_peak * base_rate * (1 + h_adj)
        ai_base_cost += a_peak * base_rate * (1 + a_adj)

    # 2. 전력량 요금 (시간대별 단가)
    def get_price(row):
        season = (
            "summer" if row["Month"] in [6, 7, 8]
            else "winter" if row["Month"] in [11, 12, 1, 2]
            else "spring_fall"
        )
        schedule = scenario_config["tou_schedule"][season]
        prices = scenario_config["unit_prices"][season]
        hour = row[time_col]
        for t_type, times in schedule.items():
            for s, e in times:
                if s > e:
                    if hour >= s or hour < e:
                        return prices[t_type], t_type
                else:
                    if s <= hour < e:
                        return prices[t_type], t_type
        return prices["off"], "off"

    prices_and_types = df_result.apply(lambda x: get_price(x), axis=1, result_type="expand")
    df_result["Unit_Price"] = prices_and_types[0]
    df_result["TOU_Type"] = prices_and_types[1]

    human_energy_cost = (df_result["Usage_kWh"] * df_result["Unit_Price"]).sum()
    ai_energy_cost = (df_result["AI_Usage_kWh"] * df_result["Unit_Price"]).sum()

    # 3. 추가 인건비 (야간 조업 증가분)
    night_mask = df_result["TOU_Type"] == "off"
    ai_extra_night_usage = np.maximum(
        0, df_result.loc[night_mask, "AI_Usage_kWh"] - df_result.loc[night_mask, "Usage_kWh"]
    )
    extra_labor_cost = (ai_extra_night_usage * labor_premium).sum()

    # 4. 세분화된 ROI
    base_savings = human_base_cost - ai_base_cost
    energy_savings = human_energy_cost - ai_energy_cost
    human_total_bill = human_base_cost + human_energy_cost
    ai_total_bill = ai_base_cost + ai_energy_cost
    net_elec_savings = human_total_bill - ai_total_bill
    real_roi = net_elec_savings - extra_labor_cost

    return {
        "Human_Total": human_total_bill,
        "AI_Total": ai_total_bill,
        "Base_Savings": base_savings,
        "Energy_Savings": energy_savings,
        "Net_Elec_Savings": net_elec_savings,
        "Extra_Labor": extra_labor_cost,
        "Final_Real_ROI": real_roi,
    }


# ---------------------------------------------------------------------------
# 4) 벡터화 실시간 전력량 요금 — cell 96
# ---------------------------------------------------------------------------
def append_realtime_energy_cost_dynamic(
    df: pd.DataFrame,
    scenario_config: dict,
    usage_col: str = "Usage_kWh",
    ai_usage_col: str = "AI_Usage_kWh",
) -> pd.DataFrame:
    """config의 단가표를 읽어 15분 단위 실시간 전력량 요금을 벡터 연산 (cell 96)."""
    df = df.copy()

    if "Month" not in df.columns:
        df["Month"] = df["date"].dt.month
    if "Hour" not in df.columns:
        df["Hour"] = df["date"].dt.hour

    cond_summer = df["Month"].isin([6, 7, 8])
    cond_winter = df["Month"].isin([11, 12, 1, 2])
    cond_spring_fall = df["Month"].isin([3, 4, 5, 9, 10])

    cond_offpeak = (df["Hour"] >= 23) | (df["Hour"] < 9)
    cond_peak_summer_sf = ((df["Hour"] >= 10) & (df["Hour"] < 12)) | ((df["Hour"] >= 13) & (df["Hour"] < 17))
    cond_peak_winter = (
        ((df["Hour"] >= 10) & (df["Hour"] < 12))
        | ((df["Hour"] >= 17) & (df["Hour"] < 20))
        | ((df["Hour"] >= 22) & (df["Hour"] < 23))
    )

    conditions = [
        cond_summer & cond_offpeak, cond_summer & cond_peak_summer_sf,
        cond_summer & ~cond_offpeak & ~cond_peak_summer_sf,
        cond_winter & cond_offpeak, cond_winter & cond_peak_winter,
        cond_winter & ~cond_offpeak & ~cond_peak_winter,
        cond_spring_fall & cond_offpeak, cond_spring_fall & cond_peak_summer_sf,
        cond_spring_fall & ~cond_offpeak & ~cond_peak_summer_sf,
    ]

    up = scenario_config["unit_prices"]
    choices = [
        up["summer"]["off"], up["summer"]["peak"], up["summer"]["mid"],
        up["winter"]["off"], up["winter"]["peak"], up["winter"]["mid"],
        up["spring_fall"]["off"], up["spring_fall"]["peak"], up["spring_fall"]["mid"],
    ]

    df["Current_Unit_Price"] = np.select(conditions, choices, default=up["spring_fall"]["off"])
    df["Human_Energy_Cost"] = df[usage_col] * df["Current_Unit_Price"]

    if ai_usage_col in df.columns:
        df["AI_Energy_Cost"] = df[ai_usage_col] * df["Current_Unit_Price"]
        df["Realtime_Savings_Won"] = df["Human_Energy_Cost"] - df["AI_Energy_Cost"]

    return df


# ---------------------------------------------------------------------------
# 5) 최종 KEPCO-ready DF (PF 컬럼 + 월 페널티 merge + 플래그) — cells 91-92
# ---------------------------------------------------------------------------
def build_final_kepco_df(df_opt: pd.DataFrame, scenario_config: dict) -> pd.DataFrame:
    """규정형 PF 컬럼 + 월별 PF/페널티 + HourType/페널티 플래그가 결합된 DF (cells 91-92)."""
    df_pf = analyze_kepco_pf_defense(df_opt)
    monthly_df = calculate_monthly_kepco_pf_penalty(df_pf, scenario_config).reset_index()
    final_df = df_pf.merge(monthly_df, on="Month", how="left")

    time_col = "hour" if "hour" in final_df.columns else "Hour"
    pf_logic = scenario_config.get("pf_logic", {})
    lag_start = pf_logic.get("lag_start", 9)
    lag_end = pf_logic.get("lag_end", 23)
    day_mask = (final_df[time_col] >= lag_start) & (final_df[time_col] < lag_end)

    final_df["HourType"] = np.where(day_mask, "Day(Lag)", "Night(Lead)")
    final_df["Human_PF_KEPCO"] = np.where(
        day_mask, final_df["Human_PF_KEPCO_Day"], final_df["Human_PF_KEPCO_Night"]
    )
    final_df["AI_PF_KEPCO"] = np.where(
        day_mask, final_df["AI_PF_KEPCO_Day"], final_df["AI_PF_KEPCO_Night"]
    )

    lag_th = pf_logic.get("lag_target", 90) / 100
    lead_th = pf_logic.get("lead_target", 95) / 100
    final_df["Human_Penalty_Flag"] = np.where(
        day_mask, final_df["Human_PF_KEPCO"] < lag_th, final_df["Human_PF_KEPCO"] < lead_th
    )
    final_df["AI_Penalty_Flag"] = np.where(
        day_mask, final_df["AI_PF_KEPCO"] < lag_th, final_df["AI_PF_KEPCO"] < lead_th
    )
    return final_df
