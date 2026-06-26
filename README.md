# PeakShield — Steel-Process Electricity Peak-Shaving & Cost Optimization

*English · [한국어](README.ko.md)*

A digital-twin simulation that takes 15-minute steel-process electricity data and, using
**surrogate ML models + Bayesian optimization (Optuna)**, re-schedules motor/capacitor
utilization to **minimize the electricity bill (base + energy + power-factor penalty) and
CO₂ emissions**.

The whole analysis is packaged as a **reproducible Python pipeline** — reusable modules plus
ordered entry-point scripts.

## System Architecture

![PeakShield architecture](presentation/1_PeakShield_Architecture_final_en.png)

---

## Project layout

```
PeakShield/
├─ config/
│   └─ electricity_config_master.json   # 8 KEPCO tariff scenarios: TOU / unit prices / PF rules / base_rate
├─ data/
│   ├─ raw/        Steel_industry_data.csv      # input (UCI Steel Industry Energy, 35,040 rows)
│   └─ processed/  # pipeline artifacts (gitignored)
├─ models/         # trained XGBoost models (gitignored)
├─ reports/        # evaluation tables/figures (gitignored)
├─ src/            # reusable modules (pure logic, no plotting)
│   ├─ config.py             paths · column names · feature list · constants
│   ├─ data_loading.py       load CSV + rename columns + chronological sort
│   ├─ preprocessing.py      time / cyclic (sin·cos) / power-derived features
│   ├─ co2_imputation.py     RandomForest restore of the Jan-Tuesday CO2 sensor outage
│   ├─ operating_flag.py     operating-state flag (0 OFF / 1 Wait / 2 Production)
│   ├─ psi.py                Process Stress Index (PSI) + AI before/after comparison
│   ├─ surrogate_model.py    XGBoost training/save/eval for Usage_kWh & PF_Physical
│   ├─ simulator.py          HybridFastSimulator (grid precompute + Optuna fine-tune)
│   ├─ economics.py          KEPCO PF penalty · financial ROI · realtime cost
│   ├─ settlement.py         cheapest voltage/plan settlement (kepco_bill implemented)
│   └─ dashboard_export.py   build streaming CSVs for the dashboard
├─ scripts/        # entry points (run in order)
│   ├─ 01_build_features.py
│   ├─ 02_train_surrogate.py
│   ├─ 03_run_optimization.py
│   ├─ 04_evaluate_roi.py
│   └─ 05_export_dashboard.py
├─ dashboard/      # Flask realtime dashboard (single page, 3 tabs)
│   ├─ app.py      Energy + CO2 server :5001 — the "Process" tab embeds :4444 via iframe
│   ├─ sender.py   replays the result CSV to /ingest every second
│   ├─ static/  templates/
│   └─ process_app/   # process-flow server :4444 (embedded by the 5001 Process tab)
│       ├─ app.py  static/  templates/
├─ presentation/   # architecture diagrams (en / ko)
└─ notebooks/      # exploratory (EDA) / visualization notebooks
```

## Data flow

```
data/raw/Steel_industry_data.csv
        │  01_build_features.py
        ▼
data/processed/features.parquet  (+ reactive_maxima.json)
        │  02_train_surrogate.py
        ▼
models/usage_model.json, models/pf_model.json
        │  03_run_optimization.py   (per config scenario)
        ▼
data/processed/sim_<scenario>.parquet
        │  04_evaluate_roi.py        05_export_dashboard.py
        ▼                                  ▼
reports/ + final_opt3_kepco_ready.csv   final_2018ver.csv / final_2026ver.csv
                                                │  dashboard/sender.py → app.py
                                                ▼
                                        realtime dashboard (http://127.0.0.1:5001)
```

## Quick start

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# full pipeline (default scenarios: 2018 & 2026 opt3)
python scripts/01_build_features.py
python scripts/02_train_surrogate.py
python scripts/03_run_optimization.py
python scripts/04_evaluate_roi.py
python scripts/05_export_dashboard.py

# dashboard — run all three (three terminals)
cp .env.example .env                  # fill in DATA_GO_KR_SERVICE_KEY
python dashboard/app.py               # Energy + CO2 server → http://127.0.0.1:5001
python dashboard/sender.py            # realtime feed
python dashboard/process_app/app.py   # Process server → http://127.0.0.1:4444
```

> With all three running, open **http://127.0.0.1:5001** — a single page with three tabs
> (Energy · Process · CO2). The **"Process" tab embeds the :4444 app via iframe** (loaded on
> first click), presenting two differently-built apps as one dashboard. The embed URL is
> configurable via `PROCESS_APP_URL`; for a single origin/port, a reverse proxy (Nginx, etc.)
> is also an option.

## Tariff scenarios (config/electricity_config_master.json)

8 scenarios: `2018_industrial_HV_A_opt{1,2,3}`, `2026_standard`, `2026_jeju`,
`2026_industrial_HV_A_opt{1,2,3}`. Each has `base_rate`, seasonal `tou_schedule` / `unit_prices`,
power-factor rules `pf_logic` (lag/lead target, active hours), and `additional_fees`
(climate · fuel · fund · VAT). The default analysis uses `*_opt3` (2018 / 2026).

## Data source

`data/raw/Steel_industry_data.csv` — UCI Machine Learning Repository,
*Steel Industry Energy Consumption* (DAEWOO Steel Co., 2018, 15-minute resolution).

## Notes & known constraints

- **`src/settlement.py` → `kepco_bill_300kw_plus()`** is implemented with the 2025-04-01
  industrial (≥300kW) tariff table (high-voltage A/B/C × plan I/II/III), so the monthly
  cheapest-combination settlement (`settlement_kepco_after_optimization`) works. It is an
  **independent, more rigorous settlement tool** separate from the main ROI
  (`economics.calculate_advanced_financial_roi`).
- Korean chart fonts are only needed for EDA/visualization (`src` has no plotting).
- The dashboard's public-data API key is kept in an environment variable
  (`DATA_GO_KR_SERVICE_KEY`), never hardcoded.

## Team & Contributions

A 3-person team, split across data/digital-twin, economics & frontend, and modeling.

- **Myeongseon Kim ([@myeongsun125](https://github.com/myeongsun125))** — Project lead & data/digital-twin. Led the team and overall project direction, and drove the final presentation and project narrative. Technical work: feature engineering (missing-value imputation, process-state modeling), EDA & data visualization, the SVG-based digital-twin process tab, and the UI architecture.
- **Byeonggab Song ([@sbg0700](https://github.com/sbg0700))** — Economics engine & frontend. Target feature engineering, the KEPCO electricity-cost functions, carbon-credit price API integration, and the dashboard frontend (electricity & carbon tabs).
- **Youngmin Kwon ([@Kwonym0814](https://github.com/Kwonym0814))** — Modeling & optimization. XGBoost surrogate hyperparameter search (Grid-search · Optuna) and model fine-tuning.
