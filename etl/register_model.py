"""
Ghi mô hình churn v1 vào database CRM_Churn (đề tài 18, Mức 1, P4 bước D2).

Script đọc ml/models/churn_model_meta_v1.json (do train.py sinh ra) rồi ghi, trong MỘT transaction:
  1. ModelVersions : một dòng cho mô hình v1 (tên, ngày huấn luyện, ngưỡng, metric, seed,
                     cấu hình, mã băm dữ liệu, phiên bản thư viện).
                     ModelVersions.Threshold = ngưỡng Medium (chốt D-13, 18/10/2026).
  2. RiskConfig    : hai khóa ngưỡng RiskMediumThreshold và RiskHighThreshold
                     (ngưỡng đang áp dụng, Manager/Admin sửa được từ web, R-04).

Quy tắc an toàn:
  - Từ chối chạy nếu ModelVersions đã có dòng cùng Version, hoặc RiskConfig đã có một trong hai
    khóa ngưỡng. Script KHÔNG xóa và KHÔNG ghi đè gì (tránh đè ngưỡng mà người dùng đã sửa trên web).
  - Từ chối chạy nếu chưa đủ CHECK (chưa chạy constraints_bo_sung.sql).
  - Metadata sai (ngưỡng ngoài [0, 1], High không lớn hơn Medium, thiếu khóa...) thì dừng trước khi ghi.
  - Nếu có file CSV gốc thì so SHA-256 với DatasetHash trong metadata; lệch thì dừng.
  - Ghi xong tự đếm lại và đọc lại từ database; một mục KHÁC là ROLLBACK, database không đổi.
  - UpdatedByStaffID để NULL (bảng Staff chưa seed; dòng này do script ghi, không phải nhân viên sửa).

Chạy thử (ghi rồi ROLLBACK, database không đổi):  python register_model.py --dry-run
Chạy thật:                                          python register_model.py
Cần:   pip install pyodbc   (load_telco.py và download_telco.py phải nằm cạnh file này)
Đặt file này ở:  <thư mục dự án>/etl/register_model.py
"""

import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import download_telco
import load_telco

PROJECT_ROOT = load_telco.PROJECT_ROOT
META_FILE = PROJECT_ROOT / "ml" / "models" / "churn_model_meta_v1.json"
RAW_FILE = download_telco.RAW_FILE

# Tên hai khóa ngưỡng trong RiskConfig (chốt 19/10/2026).
# Cả hai khớp mẫu 'Risk%Threshold' của CHECK CK_RiskConfig_Nguong_0_den_1.
KEY_MEDIUM = "RiskMediumThreshold"
KEY_HIGH = "RiskHighThreshold"

# Số chữ số thập phân khi lưu ngưỡng. ModelVersions.Threshold là decimal(5,4) nên lấy 4 chữ số,
# và RiskConfig dùng cùng 4 chữ số để hai nơi luôn bằng nhau.
THRESHOLD_DECIMALS = 4

# Giới hạn độ dài các cột của database
MAX_MODEL_NAME = 50      # ModelVersions.ModelName varchar(50)
MAX_VERSION = 20         # ModelVersions.Version varchar(20)
MAX_LIB_VERSIONS = 500   # ModelVersions.LibVersions varchar(500)
HASH_LENGTH = 64         # ModelVersions.DatasetHash varchar(64), SHA-256 dạng chữ thập lục phân

# Các khóa bắt buộc phải có trong file metadata
REQUIRED_META_KEYS = [
    "model_name", "model_key", "calibrated", "version", "train_date", "seed",
    "threshold", "threshold_medium", "threshold_high", "thresholds_consistent",
    "feature_columns", "numeric_columns", "categorical_columns", "best_params",
    "metrics_cv", "metrics_test", "dataset", "protocol", "library_versions",
]

MODEL_COLUMNS = [
    "ModelName", "Version", "TrainDate", "Threshold", "MetricsJson",
    "Seed", "ConfigJson", "DatasetHash", "LibVersions",
]
CONFIG_COLUMNS = ["ConfigKey", "ConfigValue"]


# ---------------------------------------------------------------
# 1. Đọc và kiểm metadata (chưa đụng database)
# ---------------------------------------------------------------

def load_metadata():
    """Đọc file metadata JSON do train.py sinh ra."""
    with open(META_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def format_threshold(value):
    """Làm tròn ngưỡng về 4 chữ số thập phân và trả về chuỗi, ví dụ 0.3148."""
    return format(round(float(value), THRESHOLD_DECIMALS), "." + str(THRESHOLD_DECIMALS) + "f")


def validate_metadata(meta):
    """Kiểm metadata trước khi ghi. Sai thì ném ValueError."""
    missing_keys = [key for key in REQUIRED_META_KEYS if key not in meta]
    if missing_keys:
        raise ValueError("Metadata thiếu khóa: " + str(missing_keys))

    if len(meta["model_name"]) > MAX_MODEL_NAME:
        raise ValueError("model_name dài hơn " + str(MAX_MODEL_NAME) + " ký tự")
    if len(meta["version"]) > MAX_VERSION:
        raise ValueError("version dài hơn " + str(MAX_VERSION) + " ký tự")
    if len(meta["library_versions"]) > MAX_LIB_VERSIONS:
        raise ValueError("library_versions dài hơn " + str(MAX_LIB_VERSIONS) + " ký tự")

    dataset_hash = meta["dataset"].get("sha256", "")
    if len(dataset_hash) != HASH_LENGTH:
        raise ValueError("dataset.sha256 phải dài đúng " + str(HASH_LENGTH) + " ký tự")

    if meta["threshold_high"] is None:
        raise ValueError("Metadata không có ngưỡng High")
    if not meta["thresholds_consistent"]:
        raise ValueError("Metadata ghi thresholds_consistent = false, phải xử lý tay trước")

    medium = float(meta["threshold_medium"])
    high = float(meta["threshold_high"])
    if not (0 <= medium <= 1) or not (0 <= high <= 1):
        raise ValueError("Ngưỡng phải thuộc [0, 1]")

    # So sánh sau khi làm tròn, vì giá trị lưu vào database là giá trị đã làm tròn
    if not (Decimal(format_threshold(medium)) < Decimal(format_threshold(high))):
        raise ValueError("Sau khi làm tròn, ngưỡng Medium phải nhỏ hơn ngưỡng High")

    # Ngưỡng nhị phân ghi trong metadata phải đúng là ngưỡng Medium (chốt D-13)
    if float(meta["threshold"]) != medium:
        raise ValueError("meta['threshold'] khác threshold_medium, trái quy ước D-13")

    # Ngày huấn luyện phải đọc được
    datetime.fromisoformat(meta["train_date"])


def check_dataset_hash(meta):
    """So SHA-256 của CSV gốc trên máy với DatasetHash trong metadata.
    Trả về chuỗi mô tả kết quả; ném ValueError nếu hai mã khác nhau."""
    if not RAW_FILE.exists():
        return "Không có file CSV gốc trên máy, bỏ qua bước so SHA-256."
    actual_hash = download_telco.calculate_sha256(RAW_FILE)
    if actual_hash != meta["dataset"]["sha256"]:
        raise ValueError(
            "SHA-256 của CSV trên máy (" + actual_hash + ") khác DatasetHash trong metadata ("
            + meta["dataset"]["sha256"] + "). Mô hình được huấn luyện trên bản dữ liệu khác."
        )
    return "SHA-256 của CSV khớp với metadata."


def build_rows(meta):
    """Biến metadata thành dòng ModelVersions và hai dòng RiskConfig.
    Trả về (dòng model, dòng ngưỡng Medium, dòng ngưỡng High)."""
    medium_text = format_threshold(meta["threshold_medium"])
    high_text = format_threshold(meta["threshold_high"])

    # MetricsJson: metric tìm mô hình (CV) và metric trên tập test
    metrics = {
        "cv": meta["metrics_cv"],
        "test": meta["metrics_test"],
    }

    # ConfigJson: mọi thứ cần để tái lập và để FastAPI/web biết mô hình dùng đặc trưng nào
    config = {
        "model_key": meta["model_key"],
        "calibrated": meta["calibrated"],
        "best_params": meta["best_params"],
        "threshold_medium": meta["threshold_medium"],
        "threshold_high": meta["threshold_high"],
        "feature_columns": meta["feature_columns"],
        "numeric_columns": meta["numeric_columns"],
        "categorical_columns": meta["categorical_columns"],
        "protocol": meta["protocol"],
        "dataset": meta["dataset"],
    }

    model_row = (
        meta["model_name"],
        meta["version"],
        datetime.fromisoformat(meta["train_date"]),
        Decimal(medium_text),
        json.dumps(metrics, ensure_ascii=False),
        int(meta["seed"]),
        json.dumps(config, ensure_ascii=False),
        meta["dataset"]["sha256"],
        meta["library_versions"],
    )
    medium_row = (KEY_MEDIUM, medium_text)
    high_row = (KEY_HIGH, high_text)
    return model_row, medium_row, high_row


# ---------------------------------------------------------------
# 2. Làm việc với SQL Server
# ---------------------------------------------------------------

def count_with_params(connection, sql_text, params):
    """Chạy một câu SELECT có tham số (?) và trả về một con số."""
    cursor = connection.cursor()
    cursor.execute(sql_text, params)
    return cursor.fetchone()[0]


def check_ready(connection, config, meta):
    """Phải có đủ bảng, đủ CHECK, và chưa có dữ liệu trùng. Không thì dừng, chưa ghi gì."""
    for table_name in ["ModelVersions", "RiskConfig"]:
        table_exists = load_telco.count_value(
            connection, "SELECT COUNT(*) FROM sys.tables WHERE name = '" + table_name + "'"
        )
        if table_exists == 0:
            raise RuntimeError("Chưa có bảng " + table_name + ". Chạy schema.sql trước.")

    expected_check_count = config["expected"].get("check_constraints", 12)
    check_count = load_telco.count_value(connection, "SELECT COUNT(*) FROM sys.check_constraints")
    if check_count < expected_check_count:
        raise RuntimeError(
            "Database mới có " + str(check_count) + " CHECK, cần " + str(expected_check_count)
            + ". Chạy constraints_bo_sung.sql (sau schema.sql) trước."
        )

    existing_models = count_with_params(
        connection, "SELECT COUNT(*) FROM ModelVersions WHERE Version = ?", [meta["version"]]
    )
    if existing_models > 0:
        raise RuntimeError(
            "ModelVersions đã có " + str(existing_models) + " dòng với Version = '" + meta["version"]
            + "'. Script không xóa và không ghi đè gì."
        )

    existing_keys = count_with_params(
        connection, "SELECT COUNT(*) FROM RiskConfig WHERE ConfigKey IN (?, ?)", [KEY_MEDIUM, KEY_HIGH]
    )
    if existing_keys > 0:
        raise RuntimeError(
            "RiskConfig đã có khóa ngưỡng (" + KEY_MEDIUM + " hoặc " + KEY_HIGH + "). "
            "Script không ghi đè, vì ngưỡng có thể đã được sửa từ web."
        )


def insert_rows(connection, model_row, medium_row, high_row):
    """Ghi ba dòng. Chưa commit; việc commit hay rollback do hàm main quyết."""
    cursor = connection.cursor()
    cursor.execute(load_telco.build_insert_sql("ModelVersions", MODEL_COLUMNS), list(model_row))
    cursor.execute(load_telco.build_insert_sql("RiskConfig", CONFIG_COLUMNS), list(medium_row))
    cursor.execute(load_telco.build_insert_sql("RiskConfig", CONFIG_COLUMNS), list(high_row))


def run_checks(connection, meta, model_row, medium_row, high_row):
    """Đọc lại từ database sau khi ghi (chưa commit). Trả về danh sách (mô tả, thực tế, kỳ vọng)."""
    version = meta["version"]
    threshold_value = model_row[3]
    dataset_hash = model_row[7]

    checks = [
        ("ModelVersions: số dòng có Version = " + version,
         count_with_params(connection, "SELECT COUNT(*) FROM ModelVersions WHERE Version = ?", [version]), 1),

        ("ModelVersions.Threshold đọc lại đúng " + str(threshold_value),
         count_with_params(
             connection,
             "SELECT COUNT(*) FROM ModelVersions WHERE Version = ? AND Threshold = ?",
             [version, threshold_value]), 1),

        ("ModelVersions.DatasetHash đọc lại đúng",
         count_with_params(
             connection,
             "SELECT COUNT(*) FROM ModelVersions WHERE Version = ? AND DatasetHash = ?",
             [version, dataset_hash]), 1),

        ("ModelVersions: MetricsJson và ConfigJson đều là JSON hợp lệ",
         count_with_params(
             connection,
             "SELECT COUNT(*) FROM ModelVersions "
             "WHERE Version = ? AND ISJSON(MetricsJson) = 1 AND ISJSON(ConfigJson) = 1",
             [version]), 1),

        ("RiskConfig: số khóa ngưỡng đã ghi",
         count_with_params(
             connection,
             "SELECT COUNT(*) FROM RiskConfig WHERE ConfigKey IN (?, ?)", [KEY_MEDIUM, KEY_HIGH]), 2),

        (KEY_MEDIUM + " đọc lại đúng " + medium_row[1],
         count_with_params(
             connection,
             "SELECT COUNT(*) FROM RiskConfig WHERE ConfigKey = ? AND ConfigValue = ?",
             [KEY_MEDIUM, medium_row[1]]), 1),

        (KEY_HIGH + " đọc lại đúng " + high_row[1],
         count_with_params(
             connection,
             "SELECT COUNT(*) FROM RiskConfig WHERE ConfigKey = ? AND ConfigValue = ?",
             [KEY_HIGH, high_row[1]]), 1),

        ("RiskConfig: hai khóa ngưỡng có UpdatedByStaffID khác NULL (phải là 0)",
         count_with_params(
             connection,
             "SELECT COUNT(*) FROM RiskConfig "
             "WHERE ConfigKey IN (?, ?) AND UpdatedByStaffID IS NOT NULL", [KEY_MEDIUM, KEY_HIGH]), 0),

        ("Trong database: Medium nhỏ hơn High",
         count_with_params(
             connection,
             "SELECT COUNT(*) FROM RiskConfig m JOIN RiskConfig h "
             "ON m.ConfigKey = ? AND h.ConfigKey = ? "
             "WHERE TRY_CAST(m.ConfigValue AS decimal(9,8)) < TRY_CAST(h.ConfigValue AS decimal(9,8))",
             [KEY_MEDIUM, KEY_HIGH]), 1),

        ("ModelVersions.Threshold bằng " + KEY_MEDIUM + " (D-13)",
         count_with_params(
             connection,
             "SELECT COUNT(*) FROM ModelVersions v JOIN RiskConfig r ON r.ConfigKey = ? "
             "WHERE v.Version = ? AND v.Threshold = TRY_CAST(r.ConfigValue AS decimal(5,4))",
             [KEY_MEDIUM, version]), 1),
    ]
    return checks


# ---------------------------------------------------------------
# 3. Chương trình chính
# ---------------------------------------------------------------

def main():
    dry_run = "--dry-run" in sys.argv
    config = load_telco.load_config()

    print("File metadata :", META_FILE)
    print("Chế độ        :", "CHẠY THỬ (ghi rồi ROLLBACK)" if dry_run else "GHI THẬT vào database")

    # Bước 1: đọc và kiểm metadata (chưa đụng database)
    if not META_FILE.exists():
        print("Chưa có file metadata. Chạy ml\\src\\train.py trước.")
        return
    try:
        meta = load_metadata()
        validate_metadata(meta)
        hash_message = check_dataset_hash(meta)
    except (ValueError, KeyError) as error:
        print("METADATA KHÔNG HỢP LỆ, chưa ghi gì:")
        print(error)
        return
    print("Bước 1: metadata hợp lệ.", hash_message)

    model_row, medium_row, high_row = build_rows(meta)
    print("        mô hình   :", model_row[0], model_row[1])
    print("        Threshold :", model_row[3], "(ngưỡng Medium, D-13)")
    print("        " + KEY_MEDIUM + " =", medium_row[1], "|", KEY_HIGH, "=", high_row[1])
    print("        Seed      :", model_row[5], "| thư viện:", model_row[8])

    # Bước 2: nối database, từ chối nếu thiếu bảng, thiếu CHECK hoặc đã có dữ liệu trùng
    try:
        connection = load_telco.connect_sql_server(config["server"], config["database"])
    except Exception as error:
        print("KẾT NỐI THẤT BẠI:")
        print(error)
        return

    try:
        check_ready(connection, config, meta)
    except RuntimeError as error:
        print("DỪNG, chưa ghi gì:")
        print(error)
        connection.close()
        return
    print("Bước 2: kết nối OK, chưa có dữ liệu trùng, đủ CHECK")

    # Bước 3: ghi, đọc lại, đúng hết mới commit
    try:
        insert_rows(connection, model_row, medium_row, high_row)
        checks = run_checks(connection, meta, model_row, medium_row, high_row)
    except Exception as error:
        connection.rollback()
        connection.close()
        print("LỖI KHI GHI, đã ROLLBACK, database không đổi:")
        print(error)
        return

    failed_count = 0
    print("Bước 3: đối chiếu sau khi ghi (chưa commit)")
    for description, actual, expected_value in checks:
        if actual == expected_value:
            print("  ĐẠT :", description, "=", actual)
        else:
            print("  KHÁC:", description, "= thực tế", actual, ", kỳ vọng", expected_value)
            failed_count += 1

    if failed_count > 0:
        connection.rollback()
        print("CÓ", failed_count, "MỤC KHÁC: đã ROLLBACK, database không đổi. Chụp màn hình gửi tao.")
    elif dry_run:
        connection.rollback()
        print("CHẠY THỬ XONG: mọi mục ĐẠT, đã ROLLBACK, database không đổi.")
    else:
        connection.commit()
        print("GHI XONG: đã commit.")

    connection.close()


if __name__ == "__main__":
    main()
