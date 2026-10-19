"""
Kiểm tra dịch vụ FastAPI (ml-api/main.py). Không cần bật server: dùng TestClient chạy trong cùng tiến trình.

Nội dung kiểm:
  1. /health đúng định dạng.
  2. /predict trả đúng 3 khóa {churn_probability, model_version, latency_ms}, KHÔNG có mức risk (R-04).
  3. 300 khách đầu của CSV: xác suất API trùng pipeline gọi trực tiếp (chênh < 1e-9).
  4. Nếu có ml/results/predictions/test_scores.csv: 100 khách tập test đầu tiên, xác suất API trùng
     cột 'selected' do train.py ghi (chứng minh API tái hiện đúng điểm lúc huấn luyện).
  5. Các ca phải bị chặn 422: giá trị phân loại lạ (Partner = 1), thiếu cột, thừa cột (customerID, Churn),
     số âm, SeniorCitizen = 2, chữ thay cho số. TotalCharges = null phải được chấp nhận.
  6. Đo latency 200 lần gọi: latency_ms trong API và thời gian trọn vòng gọi (chưa gồm mạng thật).

Chạy:   python ml-api\\test_api.py
Cần:    pip install httpx   (TestClient của FastAPI dùng httpx)
Đặt file này ở:  <thư mục dự án>/ml-api/test_api.py
"""

import copy
import statistics
import sys
import time
from pathlib import Path

import joblib
import pandas as pd
from fastapi.testclient import TestClient

import main

PROJECT_ROOT = main.PROJECT_ROOT
RAW_FILE = PROJECT_ROOT / "ml" / "data" / "raw" / "Telco-Customer-Churn.csv"
TEST_SCORES_FILE = PROJECT_ROOT / "ml" / "results" / "predictions" / "test_scores.csv"

TOLERANCE = 1e-9
ROWS_TO_COMPARE = 300
ROWS_TO_COMPARE_WITH_TRAIN = 100
LATENCY_CALLS = 200


def row_to_payload(row):
    """Một dòng DataFrame -> dict JSON gửi tới /predict (đổi kiểu numpy về kiểu Python, NaN -> None)."""
    payload = {}
    for column_name in main.preprocessing.FEATURE_COLUMNS:
        value = row[column_name]
        if column_name == "TotalCharges":
            payload[column_name] = None if pd.isna(value) else float(value)
        elif column_name == "MonthlyCharges":
            payload[column_name] = float(value)
        elif column_name in ("SeniorCitizen", "tenure"):
            payload[column_name] = int(value)
        else:
            payload[column_name] = str(value)
    return payload


def percentile(values, fraction):
    """Phân vị đơn giản (không nội suy): giá trị ở vị trí fraction của danh sách đã sắp."""
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def main_test():
    results = []  # danh sách (mô tả, đạt hay không)

    def record(description, passed, detail=""):
        results.append((description, passed))
        print(("ĐẠT : " if passed else "KHÁC: ") + description + ((" -> " + str(detail)) if detail != "" else ""))

    if not RAW_FILE.exists():
        print("Chưa có CSV gốc:", RAW_FILE, "- chạy etl\\download_telco.py trước.")
        return 1

    features, target, customer_ids = main.preprocessing.load_raw_data(RAW_FILE)
    pipeline_direct = joblib.load(main.MODEL_FILE)

    # `with` để FastAPI chạy lifespan (nạp mô hình) như khi chạy thật
    with TestClient(main.app) as client:

        # --- 1. /health ---
        response = client.get("/health")
        body = response.json()
        record("/health trả 200, status ok, đúng model_version và 19 đặc trưng",
               response.status_code == 200 and body.get("status") == "ok"
               and body.get("model_version") == main.MODEL_VERSION and body.get("feature_count") == 19, body)

        # --- 2. /predict một khách ---
        sample = row_to_payload(features.iloc[0])
        response = client.post("/predict", json=sample)
        body = response.json()
        record("/predict khách đầu: 200 và đúng 3 khóa",
               response.status_code == 200
               and set(body.keys()) == {"churn_probability", "model_version", "latency_ms"}, body)
        record("/predict: xác suất thuộc [0, 1]", 0.0 <= body["churn_probability"] <= 1.0)
        record("/predict: KHÔNG trả mức risk (R-04)",
               "risk_level" not in body and "RiskLevel" not in body)

        # --- 3. Trùng pipeline gọi trực tiếp ---
        direct_scores = pipeline_direct.predict_proba(features.iloc[:ROWS_TO_COMPARE])[:, 1]
        max_difference = 0.0
        for position in range(ROWS_TO_COMPARE):
            api_score = client.post("/predict", json=row_to_payload(features.iloc[position])).json()["churn_probability"]
            max_difference = max(max_difference, abs(api_score - direct_scores[position]))
        record("API trùng pipeline gọi trực tiếp trên " + str(ROWS_TO_COMPARE) + " khách đầu của CSV",
               max_difference < TOLERANCE, "chênh lớn nhất " + format(max_difference, ".2e"))

        # --- 4. Trùng điểm test do train.py ghi ---
        if TEST_SCORES_FILE.exists() and not main.MODEL_STATE["meta"].get("calibrated", False):
            test_scores = pd.read_csv(TEST_SCORES_FILE)
            test_part = test_scores.head(ROWS_TO_COMPARE_WITH_TRAIN)
            max_difference = 0.0
            for _, test_row in test_part.iterrows():
                payload = row_to_payload(features.loc[int(test_row["row_index"])])
                api_score = client.post("/predict", json=payload).json()["churn_probability"]
                max_difference = max(max_difference, abs(api_score - float(test_row["selected"])))
            record("API trùng cột 'selected' của test_scores.csv (" + str(ROWS_TO_COMPARE_WITH_TRAIN) + " khách test)",
                   max_difference < TOLERANCE, "chênh lớn nhất " + format(max_difference, ".2e"))
        else:
            print("BỎ QUA: so với test_scores.csv (không có file, hoặc mô hình đã hiệu chuẩn)")

        # --- 5. Các ca phải bị chặn 422, và ca phải được chấp nhận ---
        def mutated(**changes):
            payload = copy.deepcopy(sample)
            payload.update(changes)
            return payload

        def without(column_name):
            payload = copy.deepcopy(sample)
            del payload[column_name]
            return payload

        must_be_rejected = [
            ("Partner = 1 (bit thay cho Yes/No)", mutated(Partner=1)),
            ("Partner = 'Maybe'", mutated(Partner="Maybe")),
            ("Contract lạ", mutated(Contract="Three year")),
            ("InternetService lạ", mutated(InternetService="Cable")),
            ("PaymentMethod lạ", mutated(PaymentMethod="Cash")),
            ("gender lạ", mutated(gender="Other")),
            ("SeniorCitizen = 2", mutated(SeniorCitizen=2)),
            ("tenure âm", mutated(tenure=-1)),
            ("MonthlyCharges âm", mutated(MonthlyCharges=-5.0)),
            ("MonthlyCharges là chữ", mutated(MonthlyCharges="abc")),
            ("thiếu tenure", without("tenure")),
            ("thiếu TotalCharges (phải có mặt, được phép null)", without("TotalCharges")),
            ("thừa customerID", mutated(customerID="7590-VHVEG")),
            ("thừa Churn", mutated(Churn="Yes")),
            ("thừa ChurnLabel", mutated(ChurnLabel="Yes")),
        ]
        for description, payload in must_be_rejected:
            status_code = client.post("/predict", json=payload).status_code
            record("422 khi " + description, status_code == 422, "nhận " + str(status_code))

        status_code = client.post("/predict", json=mutated(TotalCharges=None)).status_code
        record("200 khi TotalCharges = null", status_code == 200, "nhận " + str(status_code))

        # --- 6. Đo latency ---
        inside_api = []
        round_trip = []
        for position in range(LATENCY_CALLS):
            payload = row_to_payload(features.iloc[position])
            started_at = time.perf_counter()
            body = client.post("/predict", json=payload).json()
            round_trip.append((time.perf_counter() - started_at) * 1000)
            inside_api.append(body["latency_ms"])

        print()
        print("Latency trên", LATENCY_CALLS, "lần gọi /predict (mili giây):")
        print("  trong API (latency_ms) : trung vị %.2f | p95 %.2f | lớn nhất %.2f" % (
            statistics.median(inside_api), percentile(inside_api, 0.95), max(inside_api)))
        print("  trọn vòng gọi          : trung vị %.2f | p95 %.2f | lớn nhất %.2f" % (
            statistics.median(round_trip), percentile(round_trip, 0.95), max(round_trip)))
        print("  (trọn vòng ở đây là TestClient trong cùng tiến trình, chưa có độ trễ mạng thật;")
        print("   số dùng cho báo cáo phải đo từ web ASP.NET qua HTTP thật.)")

    # --- Tóm tắt ---
    failed_count = sum(1 for _, passed in results if not passed)
    print()
    if failed_count == 0:
        print("KẾT LUẬN: tất cả", len(results), "mục ĐẠT.")
        return 0
    print("KẾT LUẬN:", failed_count, "mục KHÁC. Chụp màn hình gửi tao.")
    return 1


if __name__ == "__main__":
    sys.exit(main_test())
