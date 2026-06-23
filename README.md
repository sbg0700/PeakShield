# Steel Process Energy-Cost Optimization

철강 공정의 15분 단위 전력 사용량 데이터를 기반으로, **Surrogate(대리) ML 모델 + 베이지안 최적화(Optuna)** 로
모터/콘덴서 가동률을 재스케줄링하여 **전기요금(기본료·전력량요금·역률 페널티)과 탄소배출을 최소화**하는
디지털 트윈 시뮬레이션 프로젝트입니다.

원본은 2개의 Jupyter 노트북으로 작성되었고, 이 저장소는 그 분석을 **재현 가능한 Python 파이프라인**으로 분할한 것입니다.

---

## 프로젝트 구조

```
steel-energy-optimization/
├─ config/
│   └─ electricity_config_master.json   # 한전 요금제(8개 시나리오): TOU/단가/역률규정/base_rate
├─ data/
│   ├─ raw/        Steel_industry_data.csv      # 입력 (UCI Steel Industry Energy, 35,040행)
│   └─ processed/  # 파이프라인 산출물 (gitignore)
├─ models/         # 학습된 XGBoost 모델 (gitignore)
├─ reports/        # 평가 그림/표 (gitignore)
├─ src/            # 재사용 모듈 (plot 없음, 순수 로직)
│   ├─ config.py             경로·컬럼명·피처 목록·상수
│   ├─ data_loading.py       CSV 로드 + 컬럼 재명명 + 시간 정렬
│   ├─ preprocessing.py      시간/순환(sin·cos)/전력 파생 피처
│   ├─ co2_imputation.py     센서 고장(1월 화요일 CO2=0) RandomForest 복원
│   ├─ operating_flag.py     가동상태 플래그(0 OFF / 1 Wait / 2 Production)
│   ├─ psi.py                공정 스트레스 지수(PSI) 산출 + AI 전후 비교
│   ├─ surrogate_model.py    Usage_kWh·PF_Physical XGBoost 학습/저장/평가
│   ├─ simulator.py          HybridFastSimulator (그리드 사전연산 + Optuna 미세조정)
│   ├─ economics.py          한전 역률 페널티·재무 ROI·실시간 요금
│   ├─ settlement.py         전압/요금제 조합 최저비용 정산 (kepco_bill 슬롯)
│   └─ dashboard_export.py   대시보드용 스트리밍 CSV 생성
├─ scripts/        # 실행 진입점 (순서대로)
│   ├─ 01_build_features.py
│   ├─ 02_train_surrogate.py
│   ├─ 03_run_optimization.py
│   ├─ 04_evaluate_roi.py
│   └─ 05_export_dashboard.py
├─ dashboard/      # Flask 실시간 대시보드
│   ├─ app.py      서버(SSE 스트림 + 월별 비용 + KAU25 공공API)
│   ├─ sender.py   결과 CSV를 1초 간격으로 /ingest 에 송신
│   ├─ static/  templates/
└─ notebooks/      # 원본 노트북 보존 + EDA 분리본
```

## 데이터 흐름

```
data/raw/Steel_industry_data.csv
        │  01_build_features.py
        ▼
data/processed/features.parquet  (+ reactive_maxima.json)
        │  02_train_surrogate.py
        ▼
models/usage_model.json, models/pf_model.json
        │  03_run_optimization.py   (config 시나리오별)
        ▼
data/processed/sim_<scenario>.parquet
        │  04_evaluate_roi.py        05_export_dashboard.py
        ▼                                  ▼
reports/ + final_opt3_kepco_ready.csv   final_2018ver.csv / final_2026ver.csv
                                                │  dashboard/sender.py → app.py
                                                ▼
                                        실시간 대시보드 (http://127.0.0.1:5001)
```

## 빠른 시작

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 전체 파이프라인 (기본 시나리오: 2018·2026 opt3)
python scripts/01_build_features.py
python scripts/02_train_surrogate.py
python scripts/03_run_optimization.py
python scripts/04_evaluate_roi.py
python scripts/05_export_dashboard.py

# 대시보드 (터미널 2개)
cp .env.example .env          # DATA_GO_KR_SERVICE_KEY 채우기
python dashboard/app.py       # 터미널 A
python dashboard/sender.py    # 터미널 B
```

## 요금 시나리오 (config/electricity_config_master.json)

8개 시나리오: `2018_industrial_HV_A_opt{1,2,3}`, `2026_standard`, `2026_jeju`,
`2026_industrial_HV_A_opt{1,2,3}`. 각 시나리오는 `base_rate`, 계절별 `tou_schedule`/`unit_prices`,
역률 규정 `pf_logic`(lag/lead target, 적용 시간대), `additional_fees`(기후·연료·기금·부가세)를 가집니다.
노트북 기본 분석은 `*_opt3`(2018/2026)을 사용합니다.

## 데이터 출처

`data/raw/Steel_industry_data.csv` — UCI Machine Learning Repository,
*Steel Industry Energy Consumption* (DAEWOO Steel Co., 2018, 15분 단위).

## 알려진 의존성/제약

- **`src/settlement.py`의 `kepco_bill_300kw_plus()`는 placeholder(미구현)** 입니다.
  원본 가격 노트북에 정의가 유실되어 있어, 전압(A/B/C)×요금제(I/II/III) **조합 탐색 정산** 기능만
  골격을 비워둔 상태입니다. 메인 ROI(`economics.calculate_advanced_financial_roi`)는 자급자족이라
  이 함수 없이도 전체 결과가 재현됩니다. 함수 본체 확보 시 drop-in 교체하세요.
- 한글 차트 폰트는 EDA 노트북에서만 필요합니다(`src`는 plot 미포함).
- 대시보드의 공공데이터 인증키는 환경변수(`DATA_GO_KR_SERVICE_KEY`)로 분리되어 있습니다.
