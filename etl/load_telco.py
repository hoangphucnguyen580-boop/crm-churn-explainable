"""
Nạp dữ liệu IBM Telco (CSV gốc) vào database CRM_Churn.

Script ghi vào 4 bảng, trong MỘT transaction:
  1. TelcoRaw          : bản sao NGUYÊN VĂN của CSV (21 cột, kiểu chuỗi)
  2. Customers         : hồ sơ khách (7.043 dòng)
  3. CustomerSnapshots : ảnh chụp dịch vụ và hợp đồng (7.043 dòng, mỗi khách một dòng)
  4. CustomerContracts : hợp đồng/dịch vụ NGHIỆP VỤ (D-19), lần nạp đầu chép từ snapshot:
                         mỗi khách một dòng đang hiệu lực (EffectiveTo = NULL),
                         EffectiveFrom = SnapshotDate. Web sửa hợp đồng ở bảng này,
                         KHÔNG sửa CustomerSnapshots (R-14).

Quy tắc an toàn:
  - Từ chối chạy nếu TelcoRaw, Customers, CustomerSnapshots hoặc CustomerContracts đã có dòng.
    Script KHÔNG xóa gì. Muốn nạp lại thì xóa database rồi chạy lại các file SQL.
  - Từ chối chạy nếu chưa chạy constraints_bo_sung.sql (database chưa đủ số CHECK).
  - Dữ liệu lạ (giá trị ngoài danh sách, ID trùng, ...) thì DỪNG trước khi ghi.
  - Nạp xong tự đếm lại; một con số sai là ROLLBACK, database không đổi gì.

Chạy:  python load_telco.py
Cần:   pip install pandas pyodbc
Đặt file này ở:  <thư mục dự án>/etl/load_telco.py
Đọc cấu hình từ: <thư mục dự án>/etl/config.json
"""

import calendar
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "etl" / "config.json"

# 21 cột của CSV gốc, đúng thứ tự trong file
CSV_COLUMNS = [
    "customerID", "gender", "SeniorCitizen", "Partner", "Dependents", "tenure",
    "PhoneService", "MultipleLines", "InternetService", "OnlineSecurity",
    "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV",
    "StreamingMovies", "Contract", "PaperlessBilling", "PaymentMethod",
    "MonthlyCharges", "TotalCharges", "Churn",
]

# Các cột phải thuộc một danh sách giá trị đã biết (đã kiểm ở data_quality.py).
# Gặp giá trị ngoài danh sách thì dừng, để không nạp dữ liệu lạ mà không biết.
ALLOWED_VALUES = {
    "gender": {"Male", "Female"},
    "SeniorCitizen": {"0", "1"},
    "Partner": {"Yes", "No"},
    "Dependents": {"Yes", "No"},
    "PhoneService": {"Yes", "No"},
    "MultipleLines": {"Yes", "No", "No phone service"},
    "InternetService": {"DSL", "Fiber optic", "No"},
    "OnlineSecurity": {"Yes", "No", "No internet service"},
    "OnlineBackup": {"Yes", "No", "No internet service"},
    "DeviceProtection": {"Yes", "No", "No internet service"},
    "TechSupport": {"Yes", "No", "No internet service"},
    "StreamingTV": {"Yes", "No", "No internet service"},
    "StreamingMovies": {"Yes", "No", "No internet service"},
    "Contract": {"Month-to-month", "One year", "Two year"},
    "PaperlessBilling": {"Yes", "No"},
    "PaymentMethod": {
        "Electronic check", "Mailed check",
        "Bank transfer (automatic)", "Credit card (automatic)",
    },
    "Churn": {"Yes", "No"},
}

# Cột của bảng Customers. KHÔNG có CustomerStatus và CreatedAt:
# hai cột này để SQL Server tự điền bằng DEFAULT ('Active' và giờ hiện tại).
CUSTOMER_COLUMNS = [
    "CustomerID", "Gender", "SeniorCitizen", "Partner", "Dependents",
    "EstimatedJoinDate",
]

# 12 cột dịch vụ, hợp đồng, thanh toán: có ở CẢ CustomerSnapshots LẪN CustomerContracts
SERVICE_COLUMNS = [
    "PhoneService", "MultipleLines", "InternetService", "OnlineSecurity",
    "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV",
    "StreamingMovies", "Contract", "PaperlessBilling", "PaymentMethod",
]

# Cột của bảng CustomerSnapshots (không có SnapshotID vì là identity tự tăng)
SNAPSHOT_COLUMNS = (
    ["CustomerID", "SnapshotDate", "Tenure"]
    + SERVICE_COLUMNS
    + ["MonthlyCharges", "TotalCharges", "ChurnLabel"]
)

# Cột của bảng CustomerContracts.
# KHÔNG có ContractRecordID (identity), EffectiveTo (để NULL = đang hiệu lực)
# và UpdatedByStaffID (để NULL vì dòng này do script nạp, không phải nhân viên sửa).
CONTRACT_COLUMNS = (
    ["CustomerID", "EffectiveFrom"]
    + SERVICE_COLUMNS
    + ["MonthlyCharges"]
)

# Các bảng phải có và phải đang trống trước khi nạp
TABLES_MUST_BE_EMPTY = ["TelcoRaw", "Customers", "CustomerSnapshots", "CustomerContracts"]


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def yes_no_to_bit(value):
    """Yes -> 1, No -> 0. Giá trị khác thì dừng (không đoán)."""
    if value == "Yes":
        return 1
    if value == "No":
        return 0
    raise ValueError("Giá trị Yes/No không hợp lệ: " + repr(value))


def subtract_months(date_value, months):
    """Trừ một số tháng khỏi ngày; nếu tháng đích ngắn hơn thì lùi về ngày cuối tháng.

    Ví dụ: 30/09/2026 trừ 7 tháng = 28/02/2026 (tháng 2 không có ngày 30).
    """
    total_months = date_value.year * 12 + (date_value.month - 1) - months
    new_year = total_months // 12
    new_month = total_months % 12 + 1
    last_day_of_month = calendar.monthrange(new_year, new_month)[1]
    new_day = min(date_value.day, last_day_of_month)
    return datetime(new_year, new_month, new_day)


def read_csv_raw(csv_path):
    """Đọc CSV giữ nguyên chữ trong file (không để pandas tự đoán kiểu)."""
    return pd.read_csv(csv_path, dtype=str, keep_default_na=False)


def strip_all_columns(raw_data):
    """Tạo bản đã cắt khoảng trắng đầu và cuối ở mọi cột."""
    stripped = raw_data.copy()
    for column_name in stripped.columns:
        stripped[column_name] = stripped[column_name].str.strip()
    return stripped


def validate_data(raw_data, stripped_data, expected_rows):
    """Kiểm dữ liệu trước khi ghi. Có lỗi thì ném ValueError, chưa đụng database."""
    if list(raw_data.columns) != CSV_COLUMNS:
        raise ValueError("Tên hoặc thứ tự cột của CSV khác dự kiến: " + str(list(raw_data.columns)))

    if len(raw_data) != expected_rows:
        raise ValueError(
            "Số dòng CSV là " + str(len(raw_data)) + ", kỳ vọng " + str(expected_rows)
        )

    if stripped_data["customerID"].duplicated().any():
        raise ValueError("customerID bị trùng")

    if stripped_data["customerID"].str.len().max() > 20:
        raise ValueError("customerID dài hơn 20 ký tự, không vừa cột varchar(20)")

    for column_name, allowed in ALLOWED_VALUES.items():
        found_values = set(stripped_data[column_name])
        unknown_values = found_values - allowed
        if unknown_values:
            raise ValueError("Cột " + column_name + " có giá trị lạ: " + str(unknown_values))

    # tenure phải là số nguyên không âm
    for tenure_text in stripped_data["tenure"]:
        if not tenure_text.isdigit():
            raise ValueError("tenure không phải số nguyên không âm: " + repr(tenure_text))

    # MonthlyCharges phải đọc được thành số
    for charge_text in stripped_data["MonthlyCharges"]:
        Decimal(charge_text)

    # TotalCharges: hoặc trống (sau khi cắt khoảng trắng), hoặc đọc được thành số
    for total_text in stripped_data["TotalCharges"]:
        if total_text != "":
            Decimal(total_text)


def build_rows(stripped_data, snapshot_date):
    """Biến dữ liệu đã làm sạch thành 3 danh sách dòng:
    Customers, CustomerSnapshots và CustomerContracts."""
    customer_rows = []
    snapshot_rows = []
    contract_rows = []

    for _, record in stripped_data.iterrows():
        customer_id = record["customerID"]
        tenure_months = int(record["tenure"])

        # Ngày tham gia ước lượng = ngày chụp trừ số tháng đã dùng (D-05):
        # Telco KHÔNG có ngày thật nên đây chỉ là ước lượng.
        estimated_join_date = subtract_months(snapshot_date, tenure_months)

        customer_rows.append((
            customer_id,
            record["gender"],
            int(record["SeniorCitizen"]),
            yes_no_to_bit(record["Partner"]),
            yes_no_to_bit(record["Dependents"]),
            estimated_join_date,
        ))

        # TotalCharges trống (11 khách tenure = 0) thì lưu NULL
        if record["TotalCharges"] == "":
            total_charges = None
        else:
            total_charges = Decimal(record["TotalCharges"])

        monthly_charges = Decimal(record["MonthlyCharges"])

        # 12 giá trị dịch vụ/hợp đồng/thanh toán, theo đúng thứ tự SERVICE_COLUMNS
        service_values = [record[column_name] for column_name in SERVICE_COLUMNS]

        snapshot_rows.append(
            (customer_id, snapshot_date, tenure_months)
            + tuple(service_values)
            + (monthly_charges, total_charges, record["Churn"])
        )

        # CustomerContracts (D-19): chép từ snapshot, một dòng đang hiệu lực mỗi khách.
        # EffectiveFrom = SnapshotDate (không dùng EstimatedJoinDate, đề xuất chờ Phúc xác nhận ở G1b).
        contract_rows.append(
            (customer_id, snapshot_date)
            + tuple(service_values)
            + (monthly_charges,)
        )

    return customer_rows, snapshot_rows, contract_rows


def build_insert_sql(table_name, column_names):
    """Ghép câu INSERT có dấu ? cho từng cột (pyodbc dùng dấu ?)."""
    placeholders = ", ".join(["?"] * len(column_names))
    return (
        "INSERT INTO " + table_name + " (" + ", ".join(column_names) + ") "
        "VALUES (" + placeholders + ")"
    )


def build_contract_mismatch_sql():
    """Câu SELECT đếm số khách mà dòng CustomerContracts KHÁC snapshot.

    Dùng chung cho load_telco.py và build_delivery.py (file 03). Kết quả phải là 0.
    So sánh bằng <> với từng cột; không cột nào được NULL ở các cột này nên không lọt NULL.
    """
    conditions = ["k.EffectiveFrom <> s.SnapshotDate", "k.MonthlyCharges <> s.MonthlyCharges"]
    for column_name in SERVICE_COLUMNS:
        conditions.append("k." + column_name + " <> s." + column_name)
    return (
        "SELECT COUNT(*) FROM CustomerContracts k "
        "JOIN CustomerSnapshots s ON k.CustomerID = s.CustomerID "
        "WHERE " + " OR ".join(conditions)
    )


def insert_all(connection, raw_data, customer_rows, snapshot_rows, contract_rows):
    """Ghi 4 bảng. Chưa commit; việc commit hay rollback do hàm main quyết."""
    cursor = connection.cursor()

    # TelcoRaw: chép nguyên văn từng ô của CSV (chưa cắt khoảng trắng)
    raw_rows = [tuple(row) for row in raw_data.itertuples(index=False, name=None)]
    cursor.executemany(build_insert_sql("TelcoRaw", CSV_COLUMNS), raw_rows)

    # Customers phải vào trước vì hai bảng sau có khóa ngoại tới nó
    cursor.executemany(build_insert_sql("Customers", CUSTOMER_COLUMNS), customer_rows)
    cursor.executemany(build_insert_sql("CustomerSnapshots", SNAPSHOT_COLUMNS), snapshot_rows)
    cursor.executemany(build_insert_sql("CustomerContracts", CONTRACT_COLUMNS), contract_rows)


def count_value(connection, sql_text):
    """Chạy một câu SELECT trả về một con số."""
    cursor = connection.cursor()
    cursor.execute(sql_text)
    return cursor.fetchone()[0]


def run_checks(connection, expected):
    """Đếm lại sau khi ghi. Trả về danh sách (mô tả, thực tế, kỳ vọng)."""
    rows = expected["rows"]
    checks = [
        ("TelcoRaw: số dòng",
         count_value(connection, "SELECT COUNT(*) FROM TelcoRaw"), rows),
        ("Customers: số dòng",
         count_value(connection, "SELECT COUNT(*) FROM Customers"), rows),
        ("CustomerSnapshots: số dòng",
         count_value(connection, "SELECT COUNT(*) FROM CustomerSnapshots"), rows),
        ("CustomerContracts: số dòng",
         count_value(connection, "SELECT COUNT(*) FROM CustomerContracts"), rows),
        ("CustomerSnapshots: TotalCharges NULL",
         count_value(connection,
                     "SELECT COUNT(*) FROM CustomerSnapshots WHERE TotalCharges IS NULL"),
         expected["blank_total_charges"]),
        ("ChurnLabel = Yes",
         count_value(connection,
                     "SELECT COUNT(*) FROM CustomerSnapshots WHERE ChurnLabel = 'Yes'"),
         expected["churn_yes"]),
        ("ChurnLabel = No",
         count_value(connection,
                     "SELECT COUNT(*) FROM CustomerSnapshots WHERE ChurnLabel = 'No'"),
         expected["churn_no"]),
        ("Snapshot mồ côi (không có khách)",
         count_value(connection,
                     "SELECT COUNT(*) FROM CustomerSnapshots s "
                     "LEFT JOIN Customers c ON s.CustomerID = c.CustomerID "
                     "WHERE c.CustomerID IS NULL"),
         0),
        ("CustomerContracts có EffectiveTo khác NULL (phải là 0: ai cũng đang hiệu lực)",
         count_value(connection,
                     "SELECT COUNT(*) FROM CustomerContracts WHERE EffectiveTo IS NOT NULL"),
         0),
        ("CustomerContracts khác snapshot (dịch vụ, hợp đồng, mức phí, ngày)",
         count_value(connection, build_contract_mismatch_sql()),
         0),
        ("Customers có CustomerStatus khác 'Active' (D3: phải là 0)",
         count_value(connection,
                     "SELECT COUNT(*) FROM Customers WHERE CustomerStatus <> 'Active'"),
         0),
        ("Customers có EstimatedJoinDate NULL",
         count_value(connection,
                     "SELECT COUNT(*) FROM Customers WHERE EstimatedJoinDate IS NULL"),
         0),
    ]
    return checks


# ---------------------------------------------------------------
# Phần dưới chỉ dùng khi chạy thật với SQL Server (pyodbc)
# ---------------------------------------------------------------

def choose_driver(installed_drivers):
    """Chọn driver ODBC của SQL Server: ưu tiên bản 18, không có thì bản 17."""
    if "ODBC Driver 18 for SQL Server" in installed_drivers:
        return "ODBC Driver 18 for SQL Server"
    if "ODBC Driver 17 for SQL Server" in installed_drivers:
        return "ODBC Driver 17 for SQL Server"
    return None


def connect_sql_server(server, database):
    """Nối SQL Server bằng tài khoản Windows, giống check_connection.py."""
    import pyodbc  # import ở đây để các hàm phía trên chạy thử được khi chưa cài pyodbc

    driver_name = choose_driver(pyodbc.drivers())
    if driver_name is None:
        raise RuntimeError("Không có 'ODBC Driver 17/18 for SQL Server' trên máy")

    # TrustServerCertificate=yes: bỏ qua kiểm chứng chỉ, CHỈ dùng cho máy dev
    connection_string = (
        "DRIVER={" + driver_name + "};"
        "SERVER=" + server + ";"
        "DATABASE=" + database + ";"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    connection = pyodbc.connect(connection_string, timeout=10)
    connection.autocommit = False  # tự quản transaction: ghi xong kiểm rồi mới commit
    return connection


def check_tables_ready(connection, expected_check_count):
    """Phải có đủ 4 bảng, cả 4 đang trống, và đã chạy constraints_bo_sung.sql. Không thì dừng."""
    for table_name in TABLES_MUST_BE_EMPTY:
        table_exists = count_value(
            connection, "SELECT COUNT(*) FROM sys.tables WHERE name = '" + table_name + "'"
        )
        if table_exists == 0:
            if table_name == "TelcoRaw":
                raise RuntimeError("Chưa có bảng TelcoRaw. Chạy database/staging.sql trong SSMS trước.")
            raise RuntimeError(
                "Chưa có bảng " + table_name + ". Chạy schema.sql (bản mới, có đủ 11 bảng nghiệp vụ) trước."
            )

        row_count = count_value(connection, "SELECT COUNT(*) FROM " + table_name)
        if row_count > 0:
            raise RuntimeError(
                "Bảng " + table_name + " đã có " + str(row_count) + " dòng. "
                "Script không xóa gì. Muốn nạp lại: xóa database, chạy lại các file SQL rồi chạy script này."
            )

    # Đã chạy constraints_bo_sung.sql chưa? (6 CHECK nhiều cột nằm ở file đó)
    check_count = count_value(connection, "SELECT COUNT(*) FROM sys.check_constraints")
    if check_count < expected_check_count:
        raise RuntimeError(
            "Database mới có " + str(check_count) + " CHECK, cần " + str(expected_check_count) + ". "
            "Chạy database/constraints_bo_sung.sql (sau schema.sql) rồi chạy lại script này."
        )


def main():
    config = load_config()
    csv_path = PROJECT_ROOT / config["csv_relative_path"]
    snapshot_date = datetime.strptime(config["snapshot_date"], "%Y-%m-%d")
    # Số CHECK đúng khi đã chạy cả schema.sql và constraints_bo_sung.sql (6 + 6)
    expected_check_count = config["expected"].get("check_constraints", 12)

    print("File CSV     :", csv_path)
    print("SnapshotDate :", config["snapshot_date"], "(ngày cố định, EstimatedJoinDate là ngày ước lượng)")

    # Bước 1: đọc và kiểm CSV (chưa đụng database)
    if not csv_path.exists():
        print("Không thấy file CSV. Chạy download_telco.py trước.")
        return
    raw_data = read_csv_raw(csv_path)
    stripped_data = strip_all_columns(raw_data)
    try:
        validate_data(raw_data, stripped_data, config["expected"]["rows"])
    except ValueError as error:
        print("DỮ LIỆU KHÔNG HỢP LỆ, chưa ghi gì vào database:")
        print(error)
        return
    print("Bước 1: CSV hợp lệ,", len(raw_data), "dòng")

    # Bước 2: biến đổi thành các dòng sẽ ghi
    customer_rows, snapshot_rows, contract_rows = build_rows(stripped_data, snapshot_date)
    print("Bước 2: đã chuẩn bị", len(customer_rows), "khách,", len(snapshot_rows),
          "snapshot và", len(contract_rows), "dòng hợp đồng nghiệp vụ")

    # Bước 3: nối database, từ chối nếu thiếu bảng, thiếu CHECK hoặc đã có dữ liệu
    try:
        connection = connect_sql_server(config["server"], config["database"])
    except Exception as error:
        print("KẾT NỐI THẤT BẠI:")
        print(error)
        return

    try:
        check_tables_ready(connection, expected_check_count)
    except RuntimeError as error:
        print("DỪNG, chưa ghi gì:")
        print(error)
        connection.close()
        return
    print("Bước 3: kết nối OK, đủ 4 bảng đích đang trống, đủ", expected_check_count, "CHECK")

    # Bước 4: ghi, đếm lại, đúng hết mới commit
    try:
        insert_all(connection, raw_data, customer_rows, snapshot_rows, contract_rows)
        checks = run_checks(connection, config["expected"])
    except Exception as error:
        connection.rollback()
        connection.close()
        print("LỖI KHI GHI, đã ROLLBACK, database không đổi:")
        print(error)
        return

    failed_count = 0
    print("Bước 4: đối chiếu sau khi ghi (chưa commit)")
    for description, actual, expected_value in checks:
        if actual == expected_value:
            print("  ĐẠT :", description, "=", actual)
        else:
            print("  KHÁC:", description, "= thực tế", actual, ", kỳ vọng", expected_value)
            failed_count += 1

    if failed_count == 0:
        connection.commit()
        print("NẠP XONG: đã commit.")
    else:
        connection.rollback()
        print("CÓ", failed_count, "MỤC KHÁC: đã ROLLBACK, database không đổi. Chụp màn hình gửi tao.")

    connection.close()


if __name__ == "__main__":
    main()
