"""
Chấm điểm churn theo LÔ cho toàn bộ khách hàng và ghi vào ChurnPredictions
(đề tài 18, Mức 1, P4 bước D4). Đây là đường DỰ PHÒNG khi web chưa gọi được FastAPI /predict
(D-06), và để dashboard có phân bố Low/Medium/High (F-11, mục 1.6.6).

Cách làm (mỗi điểm đều bám kế hoạch):
  - Nạp thẳng ml/models/churn_pipeline_v1.joblib (KHÔNG cần bật API).
  - Đặc trưng lấy từ DATABASE (G1b, D-19): Customers (gender, SeniorCitizen, Partner, Dependents)
    + CustomerContracts dòng đang hiệu lực (EffectiveTo IS NULL: dịch vụ, hợp đồng, thanh toán, MonthlyCharges)
    + CustomerSnapshots (tenure, TotalCharges). Partner/Dependents là bit nên đổi về 'Yes'/'No'.
    Lần nạp đầu các giá trị này trùng CSV Telco, nên điểm phải trùng test_scores.csv của train.py.
  - Mức Low/Medium/High do SCRIPT gán theo ngưỡng đọc từ bảng RiskConfig (R-04), không hard-code:
        High   nếu Probability >= RiskHighThreshold
        Medium nếu Probability >= RiskMediumThreshold
        Low    còn lại
  - ModelVersionID đọc từ ModelVersions theo Version (không gán cứng, vì identity có thể đã nhích).
  - InputJson lưu đủ 19 đặc trưng đã dùng (đúng tên cột như payload của /predict), để kiểm tra lại
    sau này kể cả khi hợp đồng của khách đã đổi.
  - TopFactorsJson để NULL (SHAP thuộc Mức 2). Mọi dòng của một lô dùng chung PredictionTime.

Quy tắc an toàn:
  - Từ chối chạy nếu ChurnPredictions đã có dòng chấm của mô hình này (CustomerID khác NULL).
    Script KHÔNG xóa và KHÔNG ghi đè gì (Phúc chọn 20/10/2026).
  - Từ chối chạy nếu thiếu bảng, chưa đủ CHECK, thiếu khóa ngưỡng, Medium không nhỏ hơn High,
    khách không có đúng một dòng hợp đồng đang hiệu lực hoặc đúng một snapshot, hoặc giá trị lạ/NULL.
  - Ghi trong MỘT transaction, tự đọc lại và đối chiếu; một mục KHÁC là ROLLBACK, database không đổi.
  - Batch ghi thẳng database nên KHÔNG qua AuditLog (kế hoạch Mục 6.2).
  - Không dùng nhãn Churn ở bất kỳ bước nào (D-04). Không diễn giải điểm là nhân quả (R-02).

Chạy thử (ghi rồi ROLLBACK):  python ml\\src\\score_batch.py --dry-run
Chạy thật:                      python ml\\src\\score_batch.py
Cần:   pip install pyodbc   (cùng môi trường đã cài pandas, scikit-learn, joblib)
Đặt file này ở:  <thư mục dự án>/ml/src/score_batch.py   (cần etl/load_telco.py của dự án)
"""

import json
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

import preprocessing

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Dùng lại hàm nối SQL Server, đọc config và danh sách giá trị hợp lệ của etl/load_telco.py
sys.path.insert(0, str(PROJECT_ROOT / "etl"))
import load_telco  # noqa: E402  (phải import sau khi thêm đường dẫn)

MODEL_VERSION = "v1"
MODELS_FOLDER = PROJECT_ROOT / "ml" / "models"
MODEL_FILE = MODELS_FOLDER / ("churn_pipeline_" + MODEL_VERSION + ".joblib")
META_FILE = MODELS_FOLDER / ("churn_model_meta_" + MODEL_VERSION + ".json")
TEST_SCORES_FILE = PROJECT_ROOT / "ml" / "results" / "predictions" / "test_scores.csv"
REPORT_FILE = PROJECT_ROOT / "ml" / "results" / "score_batch_report.txt"

KEY_MEDIUM = "RiskMediumThreshold"
KEY_HIGH = "RiskHighThreshold"

# Dung sai khi so điểm (số thực) với test_scores.csv: hai bên cùng pipeline, cùng đặc trưng
TOLERANCE_FLOAT = 1e-9
# Probability trong database làm tròn 8 chữ số thập phân nên chênh tối đa 5e-9 so với số thực
TOLERANCE_ROUNDED = 1e-8

INSERT_CHUNK_SIZE = 1000

# Câu SELECT đặt bí danh ĐÚNG tên 19 đặc trưng Telco (thêm customerID để biết dòng của ai).
# JOIN thường: khách thiếu dòng hợp đồng đang hiệu lực hoặc thiếu snapshot sẽ rớt khỏi kết quả,
# và hàm kiểm số dòng phía dưới sẽ báo lỗi thay vì chấm thiếu âm thầm.
FEATURE_SQL = """
SELECT  c.CustomerID      AS customerID,
        c.SeniorCitizen   AS SeniorCitizen,
        s.Tenure          AS tenure,
        k.MonthlyCharges  AS MonthlyCharges,
        s.TotalCharges    AS TotalCharges,
        c.Gender          AS gender,
        c.Partner         AS Partner,
        c.Dependents      AS Dependents,
        k.PhoneService    AS PhoneService,
        k.MultipleLines   AS MultipleLines,
        k.InternetService AS InternetService,
        k.OnlineSecurity  AS OnlineSecurity,
        k.OnlineBackup    AS OnlineBackup,
        k.DeviceProtection AS DeviceProtection,
        k.TechSupport     AS TechSupport,
        k.StreamingTV     AS StreamingTV,
        k.StreamingMovies AS StreamingMovies,
        k.Contract        AS Contract,
        k.PaperlessBilling AS PaperlessBilling,
        k.PaymentMethod   AS PaymentMethod
FROM Customers c
JOIN CustomerContracts k ON k.CustomerID = c.CustomerID AND k.EffectiveTo IS NULL
JOIN CustomerSnapshots s ON s.CustomerID = c.CustomerID
ORDER BY c.CustomerID
"""

PREDICTION_COLUMNS = ["ModelVersionID", "CustomerID", "PredictionTime", "Probability", "RiskLevel", "InputJson"]


# ---------------------------------------------------------------
# 1. Mô hình và metadata
# ---------------------------------------------------------------

def load_model_and_meta():
    """Nạp pipeline và metadata; kiểm danh sách đặc trưng khớp preprocessing."""
    if not MODEL_FILE.exists():
        raise RuntimeError("Chưa có file mô hình " + str(MODEL_FILE) + ". Chạy ml\\src\\train.py trước.")
    if not META_FILE.exists():
        raise RuntimeError("Chưa có file metadata " + str(META_FILE) + ". Chạy ml\\src\\train.py trước.")

    with open(META_FILE, "r", encoding="utf-8") as file:
        meta = json.load(file)

    if meta.get("version") != MODEL_VERSION:
        raise RuntimeError("Metadata ghi version " + str(meta.get("version")) + ", script kỳ vọng " + MODEL_VERSION)
    if list(meta["feature_columns"]) != list(preprocessing.FEATURE_COLUMNS):
        raise RuntimeError("feature_columns trong metadata khác preprocessing.FEATURE_COLUMNS")

    return joblib.load(MODEL_FILE), meta


# ---------------------------------------------------------------
# 2. Đọc đặc trưng từ database và đổi sang đúng kiểu của pipeline
# ---------------------------------------------------------------

def bit_to_yes_no(value, customer_id, column_name):
    """bit (bool trong pyodbc) -> 'Yes'/'No'. NULL hoặc giá trị khác thì dừng, không đoán."""
    if value is True or value == 1:
        return "Yes"
    if value is False or value == 0:
        return "No"
    raise ValueError("Khách " + str(customer_id) + ": cột " + column_name + " không phải bit 0/1: " + repr(value))


def rows_to_records(rows):
    """Biến các dòng SELECT thành danh sách (customerID, dict 19 đặc trưng) đúng như payload của /predict.

    Hàm thuần (không đụng database) để thử được bằng dữ liệu giả. Giá trị lạ hoặc NULL -> ValueError.
    """
    allowed_values = load_telco.ALLOWED_VALUES
    records = []
    for row in rows:
        customer_id = getattr(row, "customerID")
        record = {}
        for column_name in preprocessing.FEATURE_COLUMNS:
            value = getattr(row, column_name)

            if column_name == "TotalCharges":
                # Duy nhất cột này được phép NULL (11 khách tenure = 0); pipeline điền trung vị
                record[column_name] = None if value is None else float(value)
            elif value is None:
                raise ValueError("Khách " + str(customer_id) + ": cột " + column_name + " là NULL")
            elif column_name == "SeniorCitizen":
                if int(value) not in (0, 1):
                    raise ValueError("Khách " + str(customer_id) + ": SeniorCitizen ngoài {0, 1}: " + repr(value))
                record[column_name] = int(value)
            elif column_name == "tenure":
                if int(value) < 0:
                    raise ValueError("Khách " + str(customer_id) + ": tenure âm: " + repr(value))
                record[column_name] = int(value)
            elif column_name == "MonthlyCharges":
                if float(value) < 0:
                    raise ValueError("Khách " + str(customer_id) + ": MonthlyCharges âm: " + repr(value))
                record[column_name] = float(value)
            elif column_name in ("Partner", "Dependents"):
                record[column_name] = bit_to_yes_no(value, customer_id, column_name)
            else:
                text_value = str(value).strip()
                if text_value not in allowed_values[column_name]:
                    raise ValueError(
                        "Khách " + str(customer_id) + ": cột " + column_name + " có giá trị lạ: " + repr(value)
                    )
                record[column_name] = text_value
        records.append((customer_id, record))
    return records


def score_records(pipeline, records):
    """Chấm điểm: trả về mảng xác suất churn (cùng thứ tự records)."""
    frame = preprocessing.records_to_frame([record for _, record in records])
    probability = pipeline.predict_proba(frame)[:, 1]
    if np.isnan(probability).any() or (probability < 0).any() or (probability > 1).any():
        raise ValueError("Có xác suất NaN hoặc ngoài [0, 1]")
    return probability


# ---------------------------------------------------------------
# 3. Mức risk theo ngưỡng
# ---------------------------------------------------------------

def to_decimal_probability(value):
    """Làm tròn xác suất về 8 chữ số thập phân (cột Probability là decimal(9,8))."""
    return Decimal(format(float(value), ".8f"))


def risk_level(probability, medium, high):
    """High nếu >= ngưỡng High; Medium nếu >= ngưỡng Medium; còn lại Low (cùng quy ước >= với train.py)."""
    if probability >= high:
        return "High"
    if probability >= medium:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------
# 4. Làm việc với SQL Server
# ---------------------------------------------------------------

def count_with_params(connection, sql_text, params):
    """Chạy một câu SELECT có tham số (?) và trả về một con số."""
    cursor = connection.cursor()
    cursor.execute(sql_text, params)
    return cursor.fetchone()[0]


def read_thresholds(connection):
    """Đọc hai ngưỡng từ RiskConfig (R-04). Thiếu khóa, không phải số, ngoài [0, 1] hoặc Medium >= High thì dừng."""
    cursor = connection.cursor()
    cursor.execute("SELECT ConfigKey, ConfigValue FROM RiskConfig WHERE ConfigKey IN (?, ?)", [KEY_MEDIUM, KEY_HIGH])
    found = {row[0]: row[1] for row in cursor.fetchall()}
    for key in (KEY_MEDIUM, KEY_HIGH):
        if key not in found:
            raise RuntimeError("RiskConfig chưa có khóa " + key + ". Chạy etl\\register_model.py trước.")
    try:
        medium = Decimal(found[KEY_MEDIUM])
        high = Decimal(found[KEY_HIGH])
    except InvalidOperation:
        raise RuntimeError("Giá trị ngưỡng trong RiskConfig không phải số: " + str(found))
    if not (0 <= medium <= 1) or not (0 <= high <= 1):
        raise RuntimeError("Ngưỡng trong RiskConfig phải thuộc [0, 1]")
    if not (medium < high):
        raise RuntimeError("Ngưỡng Medium (" + str(medium) + ") phải nhỏ hơn High (" + str(high) + ")")
    return medium, high


def check_ready(connection, config):
    """Kiểm điều kiện trước khi chấm. Trả về (ModelVersionID, ngưỡng Medium, ngưỡng High, số khách)."""
    for table_name in ["Customers", "CustomerContracts", "CustomerSnapshots",
                       "ChurnPredictions", "ModelVersions", "RiskConfig"]:
        exists = load_telco.count_value(
            connection, "SELECT COUNT(*) FROM sys.tables WHERE name = '" + table_name + "'")
        if exists == 0:
            raise RuntimeError("Chưa có bảng " + table_name + ". Chạy schema.sql trước.")

    expected_check_count = config["expected"].get("check_constraints", 12)
    check_count = load_telco.count_value(connection, "SELECT COUNT(*) FROM sys.check_constraints")
    if check_count < expected_check_count:
        raise RuntimeError("Database mới có " + str(check_count) + " CHECK, cần " + str(expected_check_count)
                           + ". Chạy constraints_bo_sung.sql trước.")

    customer_count = load_telco.count_value(connection, "SELECT COUNT(*) FROM Customers")
    if customer_count != config["expected"]["rows"]:
        raise RuntimeError("Customers có " + str(customer_count) + " dòng, kỳ vọng "
                           + str(config["expected"]["rows"]) + ". Chạy load_telco.py trước.")

    # Mỗi khách phải có ĐÚNG MỘT dòng hợp đồng đang hiệu lực và ĐÚNG MỘT snapshot (không đoán dòng nào đúng)
    bad_contract = load_telco.count_value(
        connection,
        "SELECT COUNT(*) FROM (SELECT c.CustomerID AS CustomerID, COUNT(k.ContractRecordID) AS Dem "
        "FROM Customers c LEFT JOIN CustomerContracts k ON k.CustomerID = c.CustomerID AND k.EffectiveTo IS NULL "
        "GROUP BY c.CustomerID) AS T WHERE T.Dem <> 1")
    if bad_contract > 0:
        raise RuntimeError(str(bad_contract) + " khách không có đúng một dòng hợp đồng đang hiệu lực.")
    bad_snapshot = load_telco.count_value(
        connection,
        "SELECT COUNT(*) FROM (SELECT c.CustomerID AS CustomerID, COUNT(s.SnapshotID) AS Dem "
        "FROM Customers c LEFT JOIN CustomerSnapshots s ON s.CustomerID = c.CustomerID "
        "GROUP BY c.CustomerID) AS T WHERE T.Dem <> 1")
    if bad_snapshot > 0:
        raise RuntimeError(str(bad_snapshot) + " khách không có đúng một snapshot.")

    # Mô hình phải đã đăng ký; lấy ModelVersionID thật
    model_count = count_with_params(
        connection, "SELECT COUNT(*) FROM ModelVersions WHERE Version = ?", [MODEL_VERSION])
    if model_count != 1:
        raise RuntimeError("ModelVersions có " + str(model_count) + " dòng với Version = '" + MODEL_VERSION
                           + "', cần đúng 1. Chạy etl\\register_model.py trước.")
    model_version_id = count_with_params(
        connection, "SELECT ModelVersionID FROM ModelVersions WHERE Version = ?", [MODEL_VERSION])

    medium, high = read_thresholds(connection)

    # Từ chối nếu đã có lô chấm của mô hình này (Phúc chọn 20/10/2026)
    existing = count_with_params(
        connection,
        "SELECT COUNT(*) FROM ChurnPredictions WHERE ModelVersionID = ? AND CustomerID IS NOT NULL",
        [model_version_id])
    if existing > 0:
        raise RuntimeError(
            "ChurnPredictions đã có " + str(existing) + " dòng chấm của mô hình này (ModelVersionID = "
            + str(model_version_id) + "). Script không xóa và không ghi đè gì.")

    return model_version_id, medium, high, customer_count


def fetch_rows(connection):
    cursor = connection.cursor()
    cursor.execute(FEATURE_SQL)
    return cursor.fetchall()


def insert_predictions(connection, prediction_rows):
    """Ghi các dòng chấm điểm theo khối. Chưa commit."""
    sql_text = load_telco.build_insert_sql("ChurnPredictions", PREDICTION_COLUMNS)
    cursor = connection.cursor()
    for start in range(0, len(prediction_rows), INSERT_CHUNK_SIZE):
        chunk = prediction_rows[start:start + INSERT_CHUNK_SIZE]
        cursor.executemany(sql_text, chunk)
        print("  ChurnPredictions :", min(start + INSERT_CHUNK_SIZE, len(prediction_rows)), "/", len(prediction_rows))


def run_database_checks(connection, model_version_id, prediction_time, medium, high, expected_count,
                        memory_scores):
    """Đọc lại từ database (chưa commit). Trả về (danh sách (mô tả, thực tế, kỳ vọng), phân bố mức risk)."""
    base = "FROM ChurnPredictions WHERE ModelVersionID = ? AND CustomerID IS NOT NULL AND PredictionTime = ?"
    base_params = [model_version_id, prediction_time]

    checks = [
        ("ChurnPredictions: số dòng của lô",
         count_with_params(connection, "SELECT COUNT(*) " + base, base_params), expected_count),
        ("ChurnPredictions: số khách khác nhau trong lô",
         count_with_params(connection, "SELECT COUNT(DISTINCT CustomerID) " + base, base_params), expected_count),
        ("Lô có Probability ngoài [0, 1]",
         count_with_params(connection, "SELECT COUNT(*) " + base + " AND (Probability < 0 OR Probability > 1)",
                           base_params), 0),
        ("Lô có RiskLevel ngoài Low/Medium/High",
         count_with_params(connection, "SELECT COUNT(*) " + base + " AND RiskLevel NOT IN ('Low','Medium','High')",
                           base_params), 0),
        ("Lô có RiskLevel không khớp ngưỡng RiskConfig (" + str(medium) + " / " + str(high) + ")",
         count_with_params(
             connection,
             "SELECT COUNT(*) " + base + " AND NOT ((Probability >= ? AND RiskLevel = 'High') "
             "OR (Probability < ? AND Probability >= ? AND RiskLevel = 'Medium') "
             "OR (Probability < ? AND RiskLevel = 'Low'))",
             base_params + [high, high, medium, medium]), 0),
        ("Lô có InputJson NULL hoặc không phải JSON hợp lệ",
         count_with_params(connection, "SELECT COUNT(*) " + base + " AND (InputJson IS NULL OR ISJSON(InputJson) = 0)",
                           base_params), 0),
        ("Lô có TopFactorsJson khác NULL (Mức 2, phải để trống)",
         count_with_params(connection, "SELECT COUNT(*) " + base + " AND TopFactorsJson IS NOT NULL",
                           base_params), 0),
    ]

    # Đọc lại điểm đã ghi, so với điểm số thực trong bộ nhớ (chỉ lệch do làm tròn 8 chữ số)
    cursor = connection.cursor()
    cursor.execute("SELECT CustomerID, Probability " + base, base_params)
    max_rounding_gap = 0.0
    for customer_id, stored in cursor.fetchall():
        max_rounding_gap = max(max_rounding_gap, abs(float(stored) - memory_scores[customer_id]))
    checks.append(("Điểm đọc lại từ database lệch điểm trong bộ nhớ tối đa < " + str(TOLERANCE_ROUNDED)
                   + " (chênh lớn nhất " + format(max_rounding_gap, ".2e") + ")",
                   int(max_rounding_gap < TOLERANCE_ROUNDED), 1))

    # Phân bố mức risk (để in và đưa vào báo cáo, không phải mục đạt/khác)
    cursor.execute("SELECT RiskLevel, COUNT(*) " + base + " GROUP BY RiskLevel", base_params)
    distribution = {row[0]: row[1] for row in cursor.fetchall()}
    return checks, distribution


def compare_with_train_scores(memory_scores):
    """So điểm chấm từ DATABASE với cột 'selected' của test_scores.csv (do train.py ghi từ CSV gốc).
    Trả về (mô tả, thực tế, kỳ vọng) hoặc None nếu không có file."""
    if not TEST_SCORES_FILE.exists():
        return None
    test_scores = pd.read_csv(TEST_SCORES_FILE)
    max_gap = 0.0
    compared = 0
    for _, test_row in test_scores.iterrows():
        customer_id = str(test_row["customerID"])
        if customer_id not in memory_scores:
            raise RuntimeError("Khách " + customer_id + " trong test_scores.csv không có trong lô chấm")
        max_gap = max(max_gap, abs(memory_scores[customer_id] - float(test_row["selected"])))
        compared += 1
    return ("Điểm từ database trùng cột 'selected' của test_scores.csv trên " + str(compared)
            + " khách test (chênh lớn nhất " + format(max_gap, ".2e") + ")",
            int(max_gap < TOLERANCE_FLOAT), 1)


# ---------------------------------------------------------------
# 5. Báo cáo
# ---------------------------------------------------------------

def write_report(lines):
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------
# 6. Chương trình chính
# ---------------------------------------------------------------

def main():
    dry_run = "--dry-run" in sys.argv
    config = load_telco.load_config()

    print("Mô hình      :", MODEL_FILE)
    print("Chế độ       :", "CHẠY THỬ (ghi rồi ROLLBACK)" if dry_run else "GHI THẬT vào database")

    # Bước 1: nạp mô hình (chưa đụng database)
    try:
        pipeline, meta = load_model_and_meta()
    except RuntimeError as error:
        print("DỪNG, chưa ghi gì:")
        print(error)
        return
    print("Bước 1: đã nạp", meta["model_name"], meta["version"],
          "| scikit-learn hiện tại", sklearn.__version__, "| lúc huấn luyện:", meta.get("library_versions"))

    # Bước 2: nối database, kiểm điều kiện
    try:
        connection = load_telco.connect_sql_server(config["server"], config["database"])
    except Exception as error:
        print("KẾT NỐI THẤT BẠI:")
        print(error)
        return

    try:
        model_version_id, medium, high, customer_count = check_ready(connection, config)
    except RuntimeError as error:
        print("DỪNG, chưa ghi gì:")
        print(error)
        connection.close()
        return
    print("Bước 2: kết nối OK. ModelVersionID =", model_version_id, "| ngưỡng Medium", medium, "| High", high,
          "| số khách", customer_count)

    # Bước 3: đọc đặc trưng từ database và chấm điểm (vẫn chưa ghi)
    try:
        rows = fetch_rows(connection)
        if len(rows) != customer_count:
            raise RuntimeError("Đọc được " + str(len(rows)) + " dòng đặc trưng, kỳ vọng " + str(customer_count))
        records = rows_to_records(rows)
        probability = score_records(pipeline, records)
    except (RuntimeError, ValueError) as error:
        print("DỪNG, chưa ghi gì:")
        print(error)
        connection.close()
        return
    print("Bước 3: đã đọc", len(records), "khách từ database và chấm điểm")

    # Điểm số thực của từng khách (dùng để đối chiếu ở bước 5)
    memory_scores = {}
    for position in range(len(records)):
        memory_scores[records[position][0]] = float(probability[position])

    train_check = compare_with_train_scores(memory_scores)

    # Bước 4: dựng các dòng ghi, gán mức risk theo RiskConfig
    prediction_time = datetime.now().replace(microsecond=0)  # dùng chung cho cả lô
    prediction_rows = []
    for position in range(len(records)):
        customer_id, record = records[position]
        stored_probability = to_decimal_probability(probability[position])
        prediction_rows.append((
            model_version_id,
            customer_id,
            prediction_time,
            stored_probability,
            risk_level(stored_probability, medium, high),
            json.dumps(record, ensure_ascii=False),
        ))

    # Bước 5: ghi, đọc lại, đúng hết mới commit
    try:
        print("Bước 4: ghi vào database (chưa commit)")
        insert_predictions(connection, prediction_rows)
        checks, distribution = run_database_checks(
            connection, model_version_id, prediction_time, medium, high, customer_count, memory_scores)
    except Exception as error:
        connection.rollback()
        connection.close()
        print("LỖI KHI GHI, đã ROLLBACK, database không đổi:")
        print(error)
        return

    if train_check is not None:
        checks.append(train_check)
    else:
        print("BỎ QUA: không có test_scores.csv để so với điểm của train.py")

    failed_count = 0
    check_lines = []
    print("Bước 5: đối chiếu (chưa commit)")
    for description, actual, expected_value in checks:
        if actual == expected_value:
            line = "  ĐẠT : " + description + " = " + str(actual)
        else:
            line = "  KHÁC: " + description + " = thực tế " + str(actual) + ", kỳ vọng " + str(expected_value)
            failed_count += 1
        check_lines.append(line)
        print(line)

    distribution_lines = []
    for level in ["Low", "Medium", "High"]:
        count = distribution.get(level, 0)
        distribution_lines.append("    " + level + " = " + str(count) + " ("
                                  + format(100.0 * count / customer_count, ".1f") + "%)")
    print("Phân bố mức risk của lô (chỉ để xem, không phải mục đạt/khác):")
    for line in distribution_lines:
        print(line)

    if failed_count > 0:
        connection.rollback()
        connection.close()
        print("CÓ", failed_count, "MỤC KHÁC: đã ROLLBACK, database không đổi. Chụp màn hình gửi tao.")
        return
    if dry_run:
        connection.rollback()
        connection.close()
        print("CHẠY THỬ XONG: mọi mục ĐẠT, đã ROLLBACK, database không đổi.")
        return

    connection.commit()
    connection.close()
    print("CHẤM XONG: đã commit.")

    # Bước 6: ghi báo cáo (chỉ khi đã commit thành công)
    report_lines = [
        "BÁO CÁO CHẤM ĐIỂM THEO LÔ (đề tài 18, Mức 1)",
        "Điểm chỉ hỗ trợ chăm sóc khách hàng, không phải quan hệ nhân quả (R-02, R-07).",
        "Đặc trưng lấy từ database: Customers + CustomerContracts (đang hiệu lực) + CustomerSnapshots.",
        "Không dùng nhãn Churn và không dùng dữ liệu mô phỏng Interactions/Tickets (D-04).",
        "",
        "Tham số:",
        "  mô hình              = " + str(meta["model_name"]) + " " + str(meta["version"]),
        "  ModelVersionID       = " + str(model_version_id),
        "  PredictionTime (lô)  = " + prediction_time.isoformat(sep=" "),
        "  ngưỡng Medium / High = " + str(medium) + " / " + str(high) + " (đọc từ RiskConfig)",
        "  số khách đã chấm     = " + str(customer_count),
        "  scikit-learn         = " + sklearn.__version__,
        "",
        "Đối chiếu trong database (trước khi commit):",
    ] + check_lines + ["", "Phân bố mức risk:"] + distribution_lines
    write_report(report_lines)
    print("Đã ghi báo cáo:", REPORT_FILE)


if __name__ == "__main__":
    main()
