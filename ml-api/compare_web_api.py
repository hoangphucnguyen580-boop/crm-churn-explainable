"""
Đối chiếu xác suất do WEB lưu với xác suất gọi trực tiếp FastAPI /predict (FR-28, Z-06).

Ý nghĩa: chứng minh tích hợp Web -> FastAPI -> SQL Server KHÔNG làm đổi kết quả.
  1. Lấy các dự báo do Web ghi (CustomerID khác NULL, loại dòng của lô chấm điểm theo PredictionTime).
  2. Mỗi khách (dòng mới nhất): gửi lại ĐÚNG InputJson tới /predict, so với Probability đã lưu.
     Probability lưu 8 chữ số thập phân nên chênh tối đa 5e-9; dung sai dùng 1e-8.
  3. So InputJson với 19 đặc trưng đọc từ database theo cách của score_batch.py
     (chỉ để cảnh báo: nếu hợp đồng của khách đã đổi sau lúc dự báo thì khác là đúng).
  Cần >= 20 khách khác nhau. Script chỉ ĐỌC database, không ghi gì.

Chạy:   python ml-api\compare_web_api.py
Cần:    FastAPI đang chạy (python ml-api\main.py), pip install pyodbc
Đặt ở:  <thư mục dự án>/ml-api/compare_web_api.py
"""

import json
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "etl"))
sys.path.insert(0, str(PROJECT_ROOT / "ml" / "src"))

import load_telco   # noqa: E402  (nối SQL Server, đọc config)
import score_batch  # noqa: E402  (dùng lại FEATURE_SQL và rows_to_records)

API_URL = "http://127.0.0.1:8000/predict"
MIN_CUSTOMERS = 20
TOLERANCE = 1e-8
REPORT_FILE = PROJECT_ROOT / "ml" / "results" / "web_api_compare_report.txt"

# Dòng do Web ghi: CustomerID khác NULL và PredictionTime KHÔNG thuộc nhóm có > 100 dòng (lô chấm điểm)
WEB_ROWS_SQL = """
SELECT TOP 500 PredictionID, CustomerID, PredictionTime, Probability, InputJson
FROM ChurnPredictions
WHERE CustomerID IS NOT NULL
  AND PredictionTime NOT IN (SELECT PredictionTime FROM ChurnPredictions
                             GROUP BY PredictionTime HAVING COUNT(*) > 100)
ORDER BY PredictionTime DESC, PredictionID DESC
"""


def call_api(payload):
    """Gửi một payload tới /predict, trả về xác suất."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        API_URL, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        return float(json.loads(response.read().decode("utf-8"))["churn_probability"])


def main():
    config = load_telco.load_config()
    try:
        connection = load_telco.connect_sql_server(config["server"], config["database"])
    except Exception as error:
        print("KẾT NỐI THẤT BẠI:")
        print(error)
        return 1

    cursor = connection.cursor()
    cursor.execute(WEB_ROWS_SQL)
    web_rows = cursor.fetchall()

    # Mỗi khách giữ dòng MỚI NHẤT (danh sách đã sắp mới nhất trước)
    latest_by_customer = {}
    for row in web_rows:
        if row.CustomerID not in latest_by_customer:
            latest_by_customer[row.CustomerID] = row

    # Đặc trưng đọc từ database theo cách của score_batch.py (để so InputJson)
    db_records = {customer_id: record
                  for customer_id, record in score_batch.rows_to_records(score_batch.fetch_rows(connection))}
    connection.close()

    lines = []
    failed = 0

    def record(description, passed, detail=""):
        nonlocal failed
        text = ("ĐẠT : " if passed else "KHÁC: ") + description + ((" -> " + detail) if detail else "")
        lines.append(text)
        print(text)
        if not passed:
            failed += 1

    record("Số khách khác nhau có dự báo do Web ghi >= " + str(MIN_CUSTOMERS),
           len(latest_by_customer) >= MIN_CUSTOMERS, "hiện có " + str(len(latest_by_customer)))

    max_gap = 0.0
    api_errors = 0
    json_mismatch = []
    for customer_id, row in latest_by_customer.items():
        payload = json.loads(row.InputJson)

        try:
            api_probability = call_api(payload)
        except Exception as error:
            api_errors += 1
            print("  Lỗi gọi API cho", customer_id, ":", error)
            continue
        max_gap = max(max_gap, abs(api_probability - float(row.Probability)))

        db_record = db_records.get(customer_id)
        if db_record is None or db_record != payload:
            json_mismatch.append(customer_id)

    record("Gọi API thành công cho mọi khách", api_errors == 0, "lỗi: " + str(api_errors))
    record("Xác suất Web đã lưu trùng gọi trực tiếp /predict (chênh lớn nhất " + format(max_gap, ".2e") + ")",
           api_errors == 0 and max_gap < TOLERANCE)
    record("InputJson do Web gửi trùng đặc trưng đọc từ database theo cách score_batch.py",
           len(json_mismatch) == 0,
           "khác ở " + str(json_mismatch[:10]) + " (nếu hợp đồng khách đã đổi sau lúc dự báo thì khác là bình thường)"
           if json_mismatch else "")

    print()
    print("KẾT LUẬN:", "tất cả mục ĐẠT." if failed == 0 else str(failed) + " mục KHÁC. Chụp màn hình gửi tao.")

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8", newline="\n") as file:
        file.write("ĐỐI CHIẾU WEB VÀ FASTAPI (FR-28)\n" + "\n".join(lines) + "\n")
    print("Đã ghi báo cáo:", REPORT_FILE)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())