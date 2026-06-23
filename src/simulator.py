"""Digital-twin optimizer: HybridFastSimulator.

Ported verbatim from notebook cell 70 (logic unchanged).

Two-stage optimization per 15-minute step:
  1. Grid search over a precomputed (motor x capacitor) utilization grid using the
     surrogate models, with a monthly cumulative power-factor penalty/reward.
  2. Optuna fine-tuning around the grid optimum for peak/mid TOU periods.

Production deficits are tracked and repaid; cumulative lagging/leading reactive
"mileage" is accumulated per month to defend the KEPCO power-factor target.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
import optuna
from tqdm.auto import tqdm

# Optuna 로그 숨기기 (루프 내 과도한 출력 방지)
optuna.logging.set_verbosity(optuna.logging.WARNING)


class HybridFastSimulator:
    def __init__(self, model_usage, model_pf, features, json_config_path, max_lagging, max_leading):
        self.model_usage = model_usage
        self.model_pf = model_pf
        self.features = features
        self.max_lagging = max_lagging    # 방향 판별용 상수 1
        self.max_leading = max_leading    # 방향 판별용 상수 2

        # 요금제 JSON 로드
        with open(json_config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def _get_tou_price(self, scenario, month, hour):
        """계절 및 시간대별 전력 단가와 TOU 타입(off, mid, peak) 반환"""
        if month in [6, 7, 8]:
            season = "summer"
        elif month in [11, 12, 1, 2]:
            season = "winter"
        else:
            season = "spring_fall"

        schedule = scenario["tou_schedule"][season]
        prices = scenario["unit_prices"][season]

        for tou_type, time_ranges in schedule.items():
            for start, end in time_ranges:
                # 야간 시간대(예: 22~8)가 자정을 넘기는 경우 처리
                if start > end:
                    if hour >= start or hour < end:
                        return prices[tou_type], tou_type
                else:
                    if start <= hour < end:
                        return prices[tou_type], tou_type
        return prices["off"], "off"  # 기본값

    def precompute_grid(self, df):
        """1단계: 전체 시간에 대한 그리드 배치 추론 (연산 속도의 핵심)"""
        print("⏳ 1단계: 대리 모델(XGBoost) 기반 가동률 그리드 사전 연산 중...")
        start_time = time.time()

        # 그리드 해상도: 모터 1% 단위 (101개), 콘덴서 10% 단위 (11개)
        self.motor_rates = np.linspace(0, 100, 101)
        self.cap_rates = np.linspace(0, 100, 11)
        M_grid, C_grid = np.meshgrid(self.motor_rates, self.cap_rates, indexing="ij")
        self.M_flat = M_grid.flatten()
        self.C_flat = C_grid.flatten()

        num_combinations = len(self.M_flat)
        N = len(df)

        self.usage_matrix = np.zeros((N, num_combinations))
        self.pf_matrix = np.zeros((N, num_combinations))
        self.q_sign_matrix = np.zeros((N, num_combinations))  # 물리적 부호(+/-) 저장

        X_base = df[self.features].values
        m_idx = self.features.index("Motor_Operating_Rate")
        c_idx = self.features.index("Capacitor_Operating_Rate")

        for i in tqdm(range(num_combinations), desc="Grid Precomputing", unit="comb"):
            X_temp = X_base.copy()
            X_temp[:, m_idx] = self.M_flat[i]
            X_temp[:, c_idx] = self.C_flat[i]

            self.usage_matrix[:, i] = self.model_usage.predict(X_temp)
            self.pf_matrix[:, i] = self.model_pf.predict(X_temp)

            # 부호(방향) 판별기: 지상(+)인지 진상(-)인지만 물리 수식으로 계산
            q_lag = (self.M_flat[i] / 100.0) * self.max_lagging
            q_lead = (self.C_flat[i] / 100.0) * self.max_leading
            self.q_sign_matrix[:, i] = np.sign(q_lag - q_lead)

        print(f"✅ 사전 연산 완료! (소요 시간: {time.time() - start_time:.2f}초)")

    def fine_tune_optuna(self, X_row, m_idx, c_idx, base_m, base_c, current_price,
                         target_prod, target_pf, is_lag_period, cum_kWh, cum_q):
        """2단계: 그리드에서 찾은 최적점 주변을 베이지안으로 미세 조정"""
        def objective(trial):
            # 그리드 최적점 주변 ±2.5% 범위 내에서 정밀 탐색
            m_rate = trial.suggest_float("m_rate", max(target_prod, base_m - 2.5), min(100.0, base_m + 2.5))
            c_rate = trial.suggest_float("c_rate", max(0.0, base_c - 5.0), min(100.0, base_c + 5.0))

            X_temp = X_row.copy()
            X_temp[m_idx] = m_rate
            X_temp[c_idx] = c_rate

            usage = self.model_usage.predict(X_temp.reshape(1, -1))[0]
            pf_val = self.model_pf.predict(X_temp.reshape(1, -1))[0]
            pf_val = np.clip(pf_val, -1.0, 1.0)

            # AI 예측 역률(PF)로부터 순간 무효전력(kVarh) 물리적 역산
            q_mag = usage * np.sqrt(max(0, 1.0 / (pf_val**2 + 1e-9) - 1.0))

            q_lag_opt = (m_rate / 100.0) * self.max_lagging
            q_lead_opt = (c_rate / 100.0) * self.max_leading
            is_lagging_state = (q_lag_opt - q_lead_opt) >= 0

            q_eval = q_mag if (is_lag_period and is_lagging_state) or (not is_lag_period and not is_lagging_state) else 0.0

            # 월 누적 역률(Projected Cumulative PF) 계산
            proj_cum_kWh = cum_kWh + usage
            proj_cum_q = cum_q + q_eval
            proj_app = np.sqrt(proj_cum_kWh**2 + proj_cum_q**2)
            proj_pf = proj_cum_kWh / proj_app if proj_app > 0 else 1.0

            cost = usage * current_price
            cost += (m_rate * 0.001)  # 모터 과가동 억제 앵커

            if proj_pf < target_pf:
                cost += (target_pf - proj_pf) * 1000000.0  # 격차만큼 강력한 그라디언트 페널티

            # Optuna 내부 지상 역률 보상 유도
            if is_lag_period and proj_pf > target_pf:
                reward_pf_cap = min(proj_pf, 0.95)
                reward_rate = (reward_pf_cap - target_pf) * 100 * 0.002
                cost -= (usage * current_price * reward_rate * 50)

            return cost

        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=5)  # 5번만 빠르게 탐색

        return study.best_params["m_rate"], study.best_params["c_rate"]

    def run_scenario(self, df, scenario_key, labor_premium=20.0):
        """전체 시뮬레이션 루프 실행"""
        print(f"\n🚀 시뮬레이션 시작: {scenario_key} (야간 인건비 할증: {labor_premium}원/kWh)")
        scenario = self.config["scenarios"][scenario_key]

        # JSON에서 시나리오별 역률 규정 자동 로드
        pf_logic = scenario.get("pf_logic", {"lag_target": 90, "lead_target": 95, "lag_start": 9, "lag_end": 23})
        lag_target = pf_logic["lag_target"] / 100.0
        lead_target = pf_logic["lead_target"] / 100.0
        lag_start = pf_logic["lag_start"]
        lag_end = pf_logic["lag_end"]

        results = []
        current_deficit = 0.0

        # 월별 누적 마일리지 통장 개설
        current_month = None
        cum_kWh_lag, cum_q_lag = 0.0, 0.0
        cum_kWh_lead, cum_q_lead = 0.0, 0.0

        m_idx = self.features.index("Motor_Operating_Rate")
        c_idx = self.features.index("Capacitor_Operating_Rate")
        X_base = df[self.features].values

        for t in tqdm(range(len(df)), desc=f"Simulating {scenario_key}", unit="step"):
            row = df.iloc[t]
            month = row["Month"]

            # 월이 바뀌면 누적 통장 초기화
            if month != current_month:
                current_month = month
                cum_kWh_lag, cum_q_lag = 0.0, 0.0
                cum_kWh_lead, cum_q_lead = 0.0, 0.0

            # 시간 정보 및 기간 판별
            current_hour = row["Hour"]
            is_lag_period = (lag_start <= current_hour < lag_end)

            current_price, tou_type = self._get_tou_price(scenario, month, current_hour)
            is_night = (tou_type == "off")
            effective_price = current_price + (labor_premium if is_night else 0.0)

            # AI 예측 PF로부터 물리적 무효전력(kVarh) 역산 (Vectorized)
            pf_clipped = np.clip(self.pf_matrix[t], -1.0, 1.0)
            q_mag_grid = self.usage_matrix[t] * np.sqrt(np.maximum(0, 1.0 / (pf_clipped**2 + 1e-9) - 1.0))

            # 실시간 그리드별 '예상 누적 역률' 계산
            if is_lag_period:
                q_eval_grid = np.where(self.q_sign_matrix[t] >= 0, q_mag_grid, 0.0)
                proj_cum_kWh = cum_kWh_lag + self.usage_matrix[t]
                proj_cum_q = cum_q_lag + q_eval_grid
                target_pf = lag_target
            else:
                q_eval_grid = np.where(self.q_sign_matrix[t] < 0, q_mag_grid, 0.0)
                proj_cum_kWh = cum_kWh_lead + self.usage_matrix[t]
                proj_cum_q = cum_q_lead + q_eval_grid
                target_pf = lead_target

            proj_app_grid = np.sqrt(proj_cum_kWh**2 + proj_cum_q**2)
            proj_pf_grid = np.where(proj_app_grid > 0, proj_cum_kWh / proj_app_grid, 1.0)

            # 누적 타겟 미달 시 연속형 페널티 부여
            pf_penalty_mask = proj_pf_grid < target_pf
            pf_penalty = np.where(pf_penalty_mask, (target_pf - proj_pf_grid) * 1000000.0, 0.0)

            # 지상 역률 보상 (주간에만 적용, 누적 역률 90% 초과 시)
            pf_reward = np.zeros_like(proj_pf_grid)
            if is_lag_period:
                reward_pf_cap = np.clip(proj_pf_grid, target_pf, 0.95)
                reward_rate = (reward_pf_cap - target_pf) * 100 * 0.002
                pf_reward = self.usage_matrix[t] * effective_price * reward_rate * 10

            # 최종 비용 = 전기료 + 페널티 - 역률 보상금
            cost_matrix = self.usage_matrix[t] * effective_price + pf_penalty - pf_reward

            # 조업 하한선 현실화 로직 (시간대별 최소 유지 가동률)
            if tou_type == "peak":
                min_prod_rate = 0.70  # 최대부하: 과감하게 70%까지 낮춰 피크 컷 유도
            elif tou_type == "mid":
                min_prod_rate = 0.85  # 중간부하: 85% 수준 완만한 절감
            else:
                min_prod_rate = 0.95  # 경부하(야간): 95% 유지

            # 목표 생산량 계산 (하한선 적용)
            target_production = row["Motor_Operating_Rate"] * min_prod_rate

            if current_deficit > 0:
                target_production = min(95.0, target_production + current_deficit)

            valid_mask = self.M_flat >= target_production
            cost_matrix = np.where(valid_mask, cost_matrix, np.inf)

            # 1차 그리드 서치 최적점 도출
            best_idx = np.argmin(cost_matrix)
            grid_m = self.M_flat[best_idx]
            grid_c = self.C_flat[best_idx]

            # 미세 조정 (peak/mid 구간만 Optuna)
            if tou_type in ["peak", "mid"]:
                passed_cum_kWh = cum_kWh_lag if is_lag_period else cum_kWh_lead
                passed_cum_q = cum_q_lag if is_lag_period else cum_q_lead

                final_m, final_c = self.fine_tune_optuna(
                    X_base[t], m_idx, c_idx, grid_m, grid_c, current_price, target_production,
                    target_pf, is_lag_period, passed_cum_kWh, passed_cum_q
                )

                X_temp = X_base[t].copy()
                X_temp[m_idx] = final_m
                X_temp[c_idx] = final_c
                final_usage = self.model_usage.predict(X_temp.reshape(1, -1))[0]
                final_pf = self.model_pf.predict(X_temp.reshape(1, -1))[0]

                # 최종 확정된 값으로 무효전력 역산
                final_pf_clipped = np.clip(final_pf, -1.0, 1.0)
                final_q_mag = final_usage * np.sqrt(max(0, 1.0 / (final_pf_clipped**2 + 1e-9) - 1.0))

                q_lag_opt = (final_m / 100.0) * self.max_lagging
                q_lead_opt = (final_c / 100.0) * self.max_leading
                is_lag_opt = (q_lag_opt - q_lead_opt) >= 0
                q_eval_final = final_q_mag if (is_lag_period and is_lag_opt) or (not is_lag_period and not is_lag_opt) else 0.0

            else:
                final_m, final_c = grid_m, grid_c
                final_usage = self.usage_matrix[t][best_idx]
                final_pf = self.pf_matrix[t][best_idx]
                q_eval_final = q_eval_grid[best_idx]

            # 상태 및 누적 통장(Tracker) 업데이트
            actual_production_gap = row["Motor_Operating_Rate"] - final_m
            current_deficit = max(0.0, current_deficit + actual_production_gap)

            if is_lag_period:
                cum_kWh_lag += final_usage
                cum_q_lag += q_eval_final
            else:
                cum_kWh_lead += final_usage
                cum_q_lead += q_eval_final

            # 결과 기록
            new_row = row.copy()
            new_row["AI_Motor_Operating_Rate"] = final_m
            new_row["AI_Capacitor_Operating_Rate"] = final_c
            new_row["AI_Usage_kWh"] = final_usage
            new_row["AI_PF"] = final_pf
            new_row["Deficit_Status"] = current_deficit
            results.append(new_row)

        return pd.DataFrame(results)
