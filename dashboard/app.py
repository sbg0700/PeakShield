# dashboard/app.py
# Flask realtime dashboard (SSE stream + monthly cost + KAU25 public-data proxy).
# Secret key, port, and data CSV path are read from the environment (.env),
# never hardcoded.
import datetime
import json
import logging
import os
import queue
import random
import time
from pathlib import Path

import pandas as pd
import requests
from flask import Flask, Response, jsonify, render_template, request

# ---------------------------------------------------------------------------
# Config via environment (.env at repo root is loaded if present)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv(REPO_ROOT / ".env")

SERVICE_KEY = os.environ.get("DATA_GO_KR_SERVICE_KEY", "")
BASE_URL = "https://apis.data.go.kr/1160100/service/GetGeneralProductInfoService/getCertifiedEmissionReductionPriceInfo"
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "5001"))
DATA_CSV = os.environ.get(
    "DASHBOARD_DATA_CSV", str(REPO_ROOT / "data" / "processed" / "final_2026ver.csv")
)
# 공정(process) 탭에서 임베드할 별도 공정 앱 주소 (기본: 로컬 4444)
PROCESS_APP_URL = os.environ.get(
    "PROCESS_APP_URL", f"http://127.0.0.1:{os.environ.get('DASHBOARD_PROCESS_PORT', '4444')}"
)

app = Flask(__name__)

# [로그 끄기] Werkzeug 접속 로그를 ERROR 레벨로 낮춤
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# 데이터를 임시 저장할 큐 (최대 100개)
stream_queue = queue.Queue(maxsize=100)
recent_cost_history = []

# [누적 변수] 서버가 켜져 있는 동안 수치를 계속 합산함
total_human_cost = 0.0
total_ai_cost = 0.0
current_month = None
monthly_human_data = []
monthly_ai_data = []


def load_csv_to_globals():
    """서버 기동 시 1회 실행: 월별 비용 차트 데이터 로드."""
    global monthly_human_data, monthly_ai_data
    try:
        df = pd.read_csv(DATA_CSV)
        df["date"] = pd.to_datetime(df["date"])
        df["Month"] = df["date"].dt.month

        m_fate = df.groupby("Month").sum(numeric_only=True)
        human_list = (m_fate["Human_Energy_Cost"] + m_fate["Current_Unit_Price"]).astype(int).tolist()
        ai_list = (m_fate["AI_Energy_Cost"] + m_fate["Current_Unit_Price"]).astype(int).tolist()

        monthly_human_data = (human_list + [0] * 12)[:12]
        monthly_ai_data = (ai_list + [0] * 12)[:12]
        print(f"✅ CSV 데이터 임포트 완료: {DATA_CSV}")
    except Exception as e:
        print(f"❌ 데이터 로드 실패({DATA_CSV}): {e}")
        monthly_human_data = [0] * 12
        monthly_ai_data = [0] * 12


load_csv_to_globals()


def event_stream():
    """큐에 쌓인 최적화 결과를 하나씩 꺼내 SSE 형식으로 전송."""
    while True:
        data = stream_queue.get()
        yield f"data: {json.dumps(data)}\n\n"


@app.route("/stream")
def stream():
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/ingest", methods=["POST"])
def ingest_data():
    global total_human_cost, total_ai_cost, current_month

    raw_row = request.json
    if not raw_row:
        return jsonify({"error": "No data"}), 400

    today = datetime.date.today()
    if current_month is None:
        current_month = today.month
    elif current_month != today.month:
        total_human_cost = 0.0
        total_ai_cost = 0.0
        current_month = today.month

    try:
        merged_data = {
            "type": "all_in_one",
            "time": raw_row.get("timestamp", time.strftime("%H:%M:%S")),
            "cost": {},
            "processes": [],
        }

        if "Human_Energy_Cost" in raw_row:
            human_cost = float(raw_row.get("Human_Energy_Cost") or 0)
            ai_cost = float(raw_row.get("AI_Energy_Cost") or human_cost)
            total_human_cost += human_cost
            total_ai_cost += ai_cost

            merged_data["cost"] = {
                "actual": human_cost,
                "projected": ai_cost,
                "psi_before": float(raw_row.get("PSI") or 0),
                "psi_after": float(raw_row.get("AI_PSI") or 0),
                "total_human_cost": total_human_cost,
                "total_ai_cost": total_ai_cost,
            }

            recent_cost_history.append({"time": merged_data["time"], **merged_data["cost"]})
            if len(recent_cost_history) > 20:
                recent_cost_history.pop(0)

        if "Motor_Operating_Rate" in raw_row:
            motor_rate = float(raw_row["Motor_Operating_Rate"])
            iron_ore_value = 50 + (motor_rate * 0.6) + random.uniform(-5.0, 5.0)
            temp_value = 1600 - (motor_rate * 0.5) + random.uniform(-8.0, 8.0)
            merged_data["processes"].extend([
                {"module": "Motor Rate", "value": round(motor_rate, 1), "unit": "%"},
                {"module": "Iron Ore Feed", "value": round(iron_ore_value, 1), "unit": "ton/h"},
                {"module": "Furnace Temp", "value": round(temp_value, 0), "unit": "°C"},
            ])

        if merged_data["cost"] or merged_data["processes"]:
            stream_queue.put(merged_data, timeout=0.1)

        return jsonify({"status": "success"}), 200

    except queue.Full:
        pass
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid value format"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.template_filter("fmt")
def fmt(v):
    try:
        return f"{int(v):,}"
    except Exception:
        return v


@app.get("/")
def home():
    global total_human_cost, total_ai_cost, recent_cost_history

    previous_month_cost = 15159144  # 전체 전기료 월평균 기준값

    if previous_month_cost > 0:
        change_pct = ((total_human_cost - previous_month_cost) / previous_month_cost) * 100
    else:
        change_pct = 0.0
    is_inc = total_human_cost > previous_month_cost

    if recent_cost_history:
        display_trend_data = recent_cost_history[-10:]
    else:
        display_trend_data = [
            {"time": "09:00", "actual": 28500, "projected": 28500},
            {"time": "10:00", "actual": 32000, "projected": 30500},
            {"time": "11:00", "actual": 35000, "projected": 31800},
            {"time": "12:00", "actual": 38500, "projected": 33200},
            {"time": "13:00", "actual": 42000, "projected": 34500},
            {"time": "14:00", "actual": 35000, "projected": 30100},
            {"time": "15:00", "actual": 33000, "projected": 28800},
            {"time": "16:00", "actual": 37000, "projected": 31500},
        ]

    return render_template(
        "index.html",
        current_cost=total_human_cost,
        previous_cost=previous_month_cost,
        potential_savings=total_human_cost - total_ai_cost,
        unit="원",
        is_increase=is_inc,
        change_percentage=round(abs(change_pct), 1),
        cost_trend_data=display_trend_data,
        processes=[],
        monthly_human_data=monthly_human_data,
        monthly_ai_data=monthly_ai_data,
        process_app_url=PROCESS_APP_URL,
    )


@app.post("/api/simulate_report")
def api_simulate_report():
    """현재 설정된 5대 파라미터로 종합 리포트 데이터를 생성."""
    params = request.get_json(silent=True) or {}

    iron_ore = float(params.get("stage-1", 100))
    temp = float(params.get("stage-2", 1550))
    motor = float(params.get("stage-3", 85))
    cap = float(params.get("stage-4", 90))
    carbon = float(params.get("stage-5", 0.18))  # noqa: F841 (kept for parity)

    sim_usage = 1200 + (iron_ore - 100) * 2.5 + (temp - 1500) * 1.5
    temp_stress = max(0, (1550 - temp) * 0.4)
    pf_stress = max(0, motor - cap) * 0.5
    sim_psi = (motor * 0.5) + temp_stress + pf_stress
    sim_psi = max(0, min(100, sim_psi))

    kwh_saved = max(0, 1200 - sim_usage)
    co2_saved = kwh_saved * 0.466

    insights = []
    if sim_psi > 80:
        insights.append("- ⚠️ **위험**: 공정 스트레스(PSI)가 높습니다. 온도 상향 또는 모터 부하 분산이 필요합니다.")
    elif kwh_saved > 0:
        insights.append(f"- ✅ **효율**: AI 제어를 통해 시간당 {kwh_saved:.1f} kWh의 에너지를 절감 중입니다.")
    if temp < 1500:
        insights.append("- ⚠️ **품질 경고**: 로(Furnace) 온도가 너무 낮아 탄소 성분 제어(0.18%)에 실패할 확률이 높습니다.")

    return jsonify({
        "status": "success",
        "parameters": params,
        "results": {
            "usage_kwh": round(sim_usage, 1),
            "psi": round(sim_psi, 1),
            "co2_saved_kg": round(co2_saved, 1),
        },
        "insights": insights,
    })


@app.post("/api/analyze")
def api_analyze():
    data = request.get_json(silent=True) or {}
    module_name = (data.get("module") or "").strip()
    try:
        user_value = float(data.get("value", 0))
    except Exception:
        user_value = 0.0

    trend_data = [round(user_value * (1 + random.uniform(-0.05, 0.05)), 1) for _ in range(7)]

    status = "정상 작동 중"
    if module_name == "제선" and user_value > 1500:
        status = "고온 경고! 냉각 필요"
    elif module_name == "압연" and user_value < 5:
        status = "두께 부족! 공정 재확인"

    return jsonify({
        "module": module_name,
        "status": status,
        "trend": trend_data,
        "labels": ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00"],
    })


@app.get("/api/kau25-monthly")
def api_kau25_monthly():
    start_ym = "202502"
    end_ym = "202602"

    def month_range(yyyymm_start, yyyymm_end):
        ys, ms = int(yyyymm_start[:4]), int(yyyymm_start[4:])
        ye, me = int(yyyymm_end[:4]), int(yyyymm_end[4:])
        out = []
        y, m = ys, ms
        while (y < ye) or (y == ye and m <= me):
            out.append(f"{y:04d}{m:02d}")
            m += 1
            if m == 13:
                y += 1
                m = 1
        return out

    months_full = month_range(start_ym, end_ym)

    def extract_items(data):
        items = (
            data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        )
        if isinstance(items, dict):
            return [items]
        if isinstance(items, list):
            return items
        return []

    date_keys = ["basDt", "trdDd", "date"]
    close_keys = ["clpr", "close", "clsPrc"]
    name_keys = ["itmsNm", "itemName", "prodNm"]

    def pick(d, keys):
        for k in keys:
            v = d.get(k)
            if v not in (None, ""):
                return v
        return None

    monthly_best = {}  # ym -> (yyyymmdd, close)

    page = 1
    max_pages = 20
    while page <= max_pages:
        params = {
            "serviceKey": SERVICE_KEY,
            "pageNo": page,
            "numOfRows": 1000,
            "resultType": "json",
        }
        r = requests.get(BASE_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()

        items = extract_items(data)
        if not items:
            break

        for it in items:
            nm = pick(it, name_keys)
            if nm and "KAU25" not in str(nm):
                continue

            raw_dt = pick(it, date_keys)
            raw_close = pick(it, close_keys)
            if raw_dt is None or raw_close is None:
                continue

            sdt = str(raw_dt).replace("-", "").replace(".", "").replace("/", "").strip()
            if len(sdt) >= 8:
                sdt = sdt[:8]
            else:
                continue

            ym = sdt[:6]
            if ym < start_ym or ym > end_ym:
                continue

            try:
                close_v = float(str(raw_close).replace(",", ""))
            except Exception:
                continue

            prev = monthly_best.get(ym)
            if (prev is None) or (sdt > prev[0]):
                monthly_best[ym] = (sdt, close_v)

        page += 1

    labels = [f"{m[:4]}/{m[4:]}" for m in months_full]
    closes = [monthly_best[m][1] if m in monthly_best else None for m in months_full]
    return jsonify({"labels": labels, "closes": closes})


if __name__ == "__main__":
    app.run(debug=True, port=DASHBOARD_PORT)
