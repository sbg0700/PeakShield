# dashboard/sender.py
# Reads a streaming CSV row-by-row and POSTs each row to the dashboard /ingest
# endpoint, simulating a realtime feed. Data path / URL / interval via env.
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = REPO_ROOT / "data" / "processed" / "final_2026ver.csv"


def send_with_retry(url, data, max_retries=3, backoff_factor=1):
    """재시도(지수 백오프) 로직이 포함된 전송 함수."""
    for i in range(max_retries):
        try:
            response = requests.post(url, json=data, timeout=2)
            if response.status_code == 200:
                return True
            print(f"  [경고] 서버 응답 오류 ({response.status_code}). {i+1}회차 재시도...")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            print(f"  [오류] 서버 연결 불가. {i+1}회차 재시도...")
        time.sleep(backoff_factor * (2 ** i))
    return False


def stream_factory_data(file_path, target_url, interval=1):
    """파일을 읽어 실시간으로 데이터를 전송하는 핵심 루프."""
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"[치명적] {file_path} 파일을 찾을 수 없습니다.")
        return

    print(f"🚀 실시간 데이터 전송 시작 (총 {len(df)}행, 주기: {interval}초)")

    for index, row in df.iterrows():
        payload = row.to_dict()
        payload["timestamp"] = datetime.now().strftime("%H:%M:%S")

        if not send_with_retry(target_url, payload):
            print(f"❌ [{payload['timestamp']}] {index}번 로우 최종 전송 실패 (건너뜀)")

        time.sleep(interval)


if __name__ == "__main__":
    port = os.environ.get("DASHBOARD_PORT", "5001")
    config = {
        "DATA_PATH": os.environ.get("DASHBOARD_DATA_CSV", str(DEFAULT_CSV)),
        "API_URL": os.environ.get("INGEST_URL", f"http://127.0.0.1:{port}/ingest"),
        "INTERVAL": float(os.environ.get("SEND_INTERVAL", "1")),
    }
    try:
        stream_factory_data(
            file_path=config["DATA_PATH"],
            target_url=config["API_URL"],
            interval=config["INTERVAL"],
        )
    except KeyboardInterrupt:
        print("\n⏹ 사용자에 의해 전송이 중단되었습니다.")
