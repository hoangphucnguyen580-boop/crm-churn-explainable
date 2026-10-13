"""
Tạo GÓI SCRIPT SQL THUẦN để gửi cô: cô chỉ cần SQL Server + SSMS, KHÔNG cần Python.

Script đọc:
  - ml/data/raw/Telco-Customer-Churn.csv   (bản gốc, không sửa)
  - database/schema.sql                     (PDM sinh ra từ PowerDesigner)
  - database/staging.sql                    (tạo bảng TelcoRaw)
  - database/kiem_tra_sau_nap.sql           (kiểm tra sau khi nạp)
  - etl/config.json                         (SnapshotDate và các số kỳ vọng)

Script ghi ra (UTF-8 có BOM, xuống dòng kiểu Windows):
  delivery/scripts/00_create_database.sql
  delivery/scripts/01_schema.sql
  delivery/scripts/02_staging.sql
  delivery/scripts/03_load_telco.sql        <- sinh từ CSV, khoảng 1 MB
  delivery/scripts/04_kiem_tra_sau_nap.sql
  delivery/scripts/README_chay.txt
  delivery/CRM_Churn_scripts.zip            <- 6 file trên gói lại để gửi cô

Script này KHÔNG nối SQL Server, KHÔNG ghi gì vào database.

Chạy:  python build_delivery.py
Cần:   pandas (load_telco.py phải nằm cạnh file này, trong thư mục etl)
"""

import sys
import zipfile
from pathlib import Path

# load_telco.py nằm cùng thư mục etl nên import trực tiếp được.
# Dùng lại đúng các hàm đọc CSV và kiểm dữ liệu để hai đường nạp (Python và SQL)
# chấp nhận cùng một luật.
import load_telco

PROJECT_ROOT = load_telco.PROJECT_ROOT
DATABASE_FOLDER = PROJECT_ROOT / "database"
DELIVERY_FOLDER = PROJECT_ROOT / "delivery"
SCRIPT_FOLDER = DELIVERY_FOLDER / "scripts"
ZIP_FILE = DELIVERY_FOLDER / "CRM_Churn_scripts.zip"

# SQL Server cho phép tối đa 1000 dòng trong một câu INSERT ... VALUES
ROWS_PER_INSERT = 1000


# ---------------------------------------------------------------
# Hàm đọc và ghi file
# ---------------------------------------------------------------

def read_sql_file(file_path):
    """Đọc file SQL. Thử UTF-8 (có hoặc không BOM), rồi UTF-16, rồi cp1252."""
    file_bytes = file_path.read_bytes()
    for encoding_name in ["utf-8-sig", "utf-16", "cp1252"]:
        try:
            return file_bytes.decode(encoding_name)
        except UnicodeError:
            continue
    raise ValueError("Không đọc được file (không rõ bảng mã): " + str(file_path))


def to_windows_line_endings(text):
    """Đổi mọi kiểu xuống dòng về CRLF để SSMS và Notepad hiển thị đúng."""
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    return text.replace("\n", "\r\n")


def write_sql_file(file_path, text):
    """Ghi file UTF-8 có BOM (SSMS đọc đúng tiếng Việt trong chú thích và PRINT)."""
    text = to_windows_line_endings(text)
    with open(file_path, "w", encoding="utf-8-sig", newline="") as file:
        file.write(text)


def has_use_statement(text, database_name):
    """Kiểm tra file đã có dòng USE <database> chưa (không phân biệt hoa thường)."""
    wanted = ("use " + database_name).lower()
    for line in text.replace("\r\n", "\n").split("\n"):
        cleaned = line.strip().lower().replace("[", "").replace("]", "").rstrip(";")
        if cleaned == wanted:
            return True
    return False


def ensure_use_statement(text, database_name):
    """Thêm 'USE <database>; GO' vào đầu file nếu file chưa có."""
    if has_use_statement(text, database_name):
        return text
    header = "USE " + database_name + ";\nGO\n\n"
    return header + text.replace("\r\n", "\n")


def sql_quote(value):
    """Biến một chuỗi Python thành chuỗi SQL: 'abc'. Dấu ' được nhân đôi thành ''."""
    if not value.isascii():
        # TelcoRaw là varchar; ký tự ngoài ASCII sẽ bị đổi sai nên dừng luôn
        raise ValueError("CSV có ký tự ngoài ASCII, cần xem lại: " + repr(value))
    return "'" + value.replace("'", "''") + "'"


# ---------------------------------------------------------------
# Hàm sinh nội dung từng file SQL
# ---------------------------------------------------------------

def build_create_database_sql(database_name):
    return (
        "/* 00 - Tạo database " + database_name + " (bỏ qua nếu đã có) */\n"
        "IF DB_ID(N'" + database_name + "') IS NULL\n"
        "    CREATE DATABASE " + database_name + ";\n"
        "GO\n"
    )


def build_insert_raw_statements(raw_data):
    """Sinh các câu INSERT ... VALUES vào TelcoRaw, mỗi câu tối đa 1000 dòng.

    Ghi NGUYÊN VĂN từng ô của CSV (chưa cắt khoảng trắng), giống load_telco.py.
    """
    column_list = ", ".join(load_telco.CSV_COLUMNS)
    all_rows = [tuple(row) for row in raw_data.itertuples(index=False, name=None)]

    statements = []
    for start in range(0, len(all_rows), ROWS_PER_INSERT):
        block = all_rows[start:start + ROWS_PER_INSERT]
        value_lines = []
        for row in block:
            quoted_cells = [sql_quote(cell) for cell in row]
            value_lines.append("(" + ", ".join(quoted_cells) + ")")
        statement = (
            "INSERT INTO dbo.TelcoRaw (" + column_list + ") VALUES\n"
            + ",\n".join(value_lines) + ";\n"
        )
        statements.append(statement)
    return statements


def trimmed(column_name):
    """Biểu thức SQL cắt khoảng trắng hai đầu của một cột."""
    return "LTRIM(RTRIM(" + column_name + "))"


def build_yes_no_bit(column_name):
    """Yes -> 1, No -> 0, giá trị khác -> NULL (sẽ bị chặn ở bước kiểm)."""
    return (
        "CASE " + trimmed(column_name)
        + " WHEN 'Yes' THEN 1 WHEN 'No' THEN 0 END"
    )


def build_load_sql(raw_data, config):
    """Sinh file 03_load_telco.sql: nạp TelcoRaw, Customers, CustomerSnapshots."""
    database_name = config["database"]
    expected = config["expected"]
    snapshot_compact = config["snapshot_date"].replace("-", "")  # 2026-09-30 -> 20260930

    raw_statements = build_insert_raw_statements(raw_data)
    raw_block = "\n".join(raw_statements)

    # Các cột dịch vụ giữ nguyên chữ (có 3 giá trị), chỉ cắt khoảng trắng
    service_columns = [
        "PhoneService", "MultipleLines", "InternetService", "OnlineSecurity",
        "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV",
        "StreamingMovies", "Contract", "PaperlessBilling", "PaymentMethod",
    ]
    service_select = ",\n            ".join(trimmed(name) for name in service_columns)
    service_insert = ", ".join(service_columns)

    head = (
        "USE " + database_name + ";\n"
        "GO\n"
        "\n"
        "/* 03 - Nạp dữ liệu IBM Telco Customer Churn (sample dataset)\n"
        "   Nguồn: https://github.com/IBM/telco-customer-churn-on-icp4d\n"
        "   Script này được SINH TỰ ĐỘNG từ file CSV gốc bằng etl/build_delivery.py.\n"
        "\n"
        "   Làm 3 việc trong MỘT transaction:\n"
        "     1. Chép nguyên văn CSV vào TelcoRaw (21 cột, kiểu chuỗi)\n"
        "     2. Làm sạch rồi nạp Customers (hồ sơ khách)\n"
        "     3. Làm sạch rồi nạp CustomerSnapshots (dịch vụ, hợp đồng, nhãn Churn)\n"
        "   Đếm lại 9 mục; đúng hết mới COMMIT, sai một mục là ROLLBACK (không đổi gì).\n"
        "   Script TỪ CHỐI chạy nếu TelcoRaw, Customers hoặc CustomerSnapshots đã có dòng. */\n"
        "\n"
        "SET NOCOUNT ON;\n"
        "SET XACT_ABORT ON;\n"
        "\n"
        "/* Ngày chụp cố định. EstimatedJoinDate chỉ là NGÀY ƯỚC LƯỢNG = ngày chụp - tenure tháng\n"
        "   (Telco không có ngày đăng ký thật). DATEADD(month) tự lùi về cuối tháng nếu ngày không tồn tại. */\n"
        "DECLARE @SnapshotDate datetime = '" + snapshot_compact + "';\n"
        "DECLARE @KetQua TABLE (MoTa nvarchar(100) NOT NULL, ThucTe int NOT NULL, KyVong int NOT NULL);\n"
        "\n"
        "BEGIN TRY\n"
        "\n"
        "    /* Bước 0: từ chối nếu đã có dữ liệu */\n"
        "    IF EXISTS (SELECT 1 FROM dbo.TelcoRaw)\n"
        "       OR EXISTS (SELECT 1 FROM dbo.Customers)\n"
        "       OR EXISTS (SELECT 1 FROM dbo.CustomerSnapshots)\n"
        "    BEGIN\n"
        "        THROW 50001, N'DỪNG: TelcoRaw, Customers hoặc CustomerSnapshots đã có dữ liệu. Script không xóa gì.', 1;\n"
        "    END;\n"
        "\n"
        "    BEGIN TRANSACTION;\n"
        "\n"
        "    /* Bước 1: chép nguyên văn CSV vào TelcoRaw (8 câu INSERT, mỗi câu tối đa 1000 dòng) */\n"
    )

    clean_part = (
        "\n"
        "    /* Bước 2: Customers. CustomerStatus và CreatedAt để SQL Server tự điền bằng DEFAULT.\n"
        "       Partner, Dependents: Yes -> 1, No -> 0. */\n"
        "    INSERT INTO dbo.Customers (CustomerID, Gender, SeniorCitizen, Partner, Dependents, EstimatedJoinDate)\n"
        "    SELECT\n"
        "            " + trimmed("customerID") + ",\n"
        "            " + trimmed("gender") + ",\n"
        "            CASE " + trimmed("SeniorCitizen") + " WHEN '1' THEN 1 WHEN '0' THEN 0 END,\n"
        "            " + build_yes_no_bit("Partner") + ",\n"
        "            " + build_yes_no_bit("Dependents") + ",\n"
        "            DATEADD(month, 0 - CAST(" + trimmed("tenure") + " AS int), @SnapshotDate)\n"
        "    FROM dbo.TelcoRaw;\n"
        "\n"
        "    /* Bước 3: CustomerSnapshots, mỗi khách một dòng.\n"
        "       TotalCharges rỗng (chỉ có dấu cách, 11 khách tenure = 0) -> NULL. */\n"
        "    INSERT INTO dbo.CustomerSnapshots\n"
        "        (CustomerID, SnapshotDate, Tenure, " + service_insert + ",\n"
        "         MonthlyCharges, TotalCharges, ChurnLabel)\n"
        "    SELECT\n"
        "            " + trimmed("customerID") + ",\n"
        "            @SnapshotDate,\n"
        "            CAST(" + trimmed("tenure") + " AS int),\n"
        "            " + service_select + ",\n"
        "            CAST(" + trimmed("MonthlyCharges") + " AS decimal(8,2)),\n"
        "            TRY_CAST(NULLIF(" + trimmed("TotalCharges") + ", '') AS decimal(10,2)),\n"
        "            " + trimmed("Churn") + "\n"
        "    FROM dbo.TelcoRaw;\n"
        "\n"
        "    /* Bước 4: đếm lại 9 mục (chưa COMMIT) */\n"
        "    INSERT INTO @KetQua (MoTa, ThucTe, KyVong)\n"
        "    SELECT N'TelcoRaw: số dòng', COUNT(*), " + str(expected["rows"]) + " FROM dbo.TelcoRaw\n"
        "    UNION ALL\n"
        "    SELECT N'Customers: số dòng', COUNT(*), " + str(expected["rows"]) + " FROM dbo.Customers\n"
        "    UNION ALL\n"
        "    SELECT N'CustomerSnapshots: số dòng', COUNT(*), " + str(expected["rows"]) + " FROM dbo.CustomerSnapshots\n"
        "    UNION ALL\n"
        "    SELECT N'CustomerSnapshots: TotalCharges NULL', COUNT(*), " + str(expected["blank_total_charges"]) + "\n"
        "        FROM dbo.CustomerSnapshots WHERE TotalCharges IS NULL\n"
        "    UNION ALL\n"
        "    SELECT N'ChurnLabel = Yes', COUNT(*), " + str(expected["churn_yes"]) + "\n"
        "        FROM dbo.CustomerSnapshots WHERE ChurnLabel = 'Yes'\n"
        "    UNION ALL\n"
        "    SELECT N'ChurnLabel = No', COUNT(*), " + str(expected["churn_no"]) + "\n"
        "        FROM dbo.CustomerSnapshots WHERE ChurnLabel = 'No'\n"
        "    UNION ALL\n"
        "    SELECT N'Snapshot mồ côi (không có khách)', COUNT(*), 0\n"
        "        FROM dbo.CustomerSnapshots s\n"
        "        LEFT JOIN dbo.Customers c ON s.CustomerID = c.CustomerID\n"
        "        WHERE c.CustomerID IS NULL\n"
        "    UNION ALL\n"
        "    SELECT N'Customers có CustomerStatus khác Active', COUNT(*), 0\n"
        "        FROM dbo.Customers WHERE CustomerStatus <> 'Active'\n"
        "    UNION ALL\n"
        "    SELECT N'Customers có EstimatedJoinDate NULL', COUNT(*), 0\n"
        "        FROM dbo.Customers WHERE EstimatedJoinDate IS NULL;\n"
        "\n"
        "    SELECT\n"
        "        MoTa, ThucTe, KyVong,\n"
        "        CASE WHEN ThucTe = KyVong THEN N'ĐẠT' ELSE N'KHÁC' END AS KetQua\n"
        "    FROM @KetQua;\n"
        "\n"
        "    IF EXISTS (SELECT 1 FROM @KetQua WHERE ThucTe <> KyVong)\n"
        "    BEGIN\n"
        "        THROW 50002, N'Có mục KHÁC kỳ vọng. Đã ROLLBACK, database không đổi.', 1;\n"
        "    END;\n"
        "\n"
        "    COMMIT TRANSACTION;\n"
        "    PRINT N'NẠP XONG: đã COMMIT.';\n"
        "\n"
        "END TRY\n"
        "BEGIN CATCH\n"
        "    IF @@TRANCOUNT > 0\n"
        "        ROLLBACK TRANSACTION;\n"
        "    THROW;  -- ném lại đúng lỗi gốc để SSMS hiện ra\n"
        "END CATCH;\n"
        "GO\n"
    )

    return head + raw_block + clean_part


def build_readme(config, row_count):
    database_name = config["database"]
    return (
        "GÓI SCRIPT SQL - DATABASE " + database_name + " (Đề tài 18: CRM tích hợp dự báo khách hàng rời bỏ)\n"
        "Sinh viên: Nguyễn Hoàng Phúc - lớp CC25TTH - MSSV 25TH2517\n"
        "\n"
        "NỘI DUNG: schema 10 bảng của hệ thống CRM + bảng đổ tạm TelcoRaw, và dữ liệu\n"
        "IBM Telco Customer Churn sample dataset (" + str(row_count) + " khách hàng, 21 cột).\n"
        "Nguồn dữ liệu: https://github.com/IBM/telco-customer-churn-on-icp4d\n"
        "Đây là bộ dữ liệu mẫu phục vụ minh họa/giáo dục, không phải dữ liệu vận hành thực tế.\n"
        "\n"
        "CẦN: SQL Server (script sinh cho SQL Server 2017; máy tác giả chạy bản 2022) và SSMS.\n"
        "      Không cần Python.\n"
        "\n"
        "CÁCH CHẠY: mở lần lượt từng file trong SSMS, bấm Execute (F5), ĐÚNG THỨ TỰ 00 -> 04.\n"
        "Nên chạy trên một server chưa có database " + database_name + " (hoặc database đang trống).\n"
        "\n"
        "  1. 00_create_database.sql   Tạo database " + database_name + " nếu chưa có.\n"
        "  2. 01_schema.sql            Tạo 10 bảng, khóa ngoại, default, ràng buộc.\n"
        "  3. 02_staging.sql           Tạo bảng TelcoRaw (chứa bản sao nguyên văn của CSV).\n"
        "  4. 03_load_telco.sql        Nạp dữ liệu. Chạy hơi lâu hơn các file kia (file khoảng 1 MB).\n"
        "                              Cuối file hiện bảng đối chiếu 9 dòng; cột KetQua phải là ĐẠT hết\n"
        "                              và tab Messages hiện 'NẠP XONG: đã COMMIT.'\n"
        "  5. 04_kiem_tra_sau_nap.sql  Chỉ đọc: số dòng từng bảng, số khách Churn Yes/No, 5 khách đầu.\n"
        "\n"
        "SỐ LIỆU PHẢI KHỚP: TelcoRaw, Customers, CustomerSnapshots đều " + str(row_count) + " dòng;\n"
        "ChurnLabel Yes " + str(config["expected"]["churn_yes"]) + ", No " + str(config["expected"]["churn_no"]) + "; "
        "TotalCharges NULL " + str(config["expected"]["blank_total_charges"]) + " dòng (khách tenure = 0).\n"
        "\n"
        "LƯU Ý:\n"
        "  - 03_load_telco.sql từ chối chạy nếu 3 bảng đã có dòng và KHÔNG xóa gì. Muốn nạp lại thì\n"
        "    xóa database rồi chạy lại từ 00.\n"
        "  - Sai một mục đối chiếu thì script tự ROLLBACK, database không bị đổi.\n"
        "  - EstimatedJoinDate là NGÀY ƯỚC LƯỢNG = 30/09/2026 trừ tenure (tháng), vì Telco không có ngày đăng ký thật.\n"
        "  - Các bảng Interactions, Tickets (dữ liệu mô phỏng) và các bảng khác hiện còn trống; sẽ nạp ở bước sau.\n"
    )


# ---------------------------------------------------------------
# Chương trình chính
# ---------------------------------------------------------------

def main():
    config = load_telco.load_config()
    database_name = config["database"]
    csv_path = PROJECT_ROOT / config["csv_relative_path"]

    # Bước 1: kiểm các file đầu vào có đủ không
    required_files = [
        csv_path,
        DATABASE_FOLDER / "schema.sql",
        DATABASE_FOLDER / "staging.sql",
        DATABASE_FOLDER / "kiem_tra_sau_nap.sql",
    ]
    missing_files = [path for path in required_files if not path.exists()]
    if missing_files:
        print("THIẾU FILE, chưa tạo gì:")
        for path in missing_files:
            print("  -", path)
        sys.exit(1)

    # Bước 2: đọc và kiểm CSV bằng đúng luật của load_telco.py
    raw_data = load_telco.read_csv_raw(csv_path)
    stripped_data = load_telco.strip_all_columns(raw_data)
    try:
        load_telco.validate_data(raw_data, stripped_data, config["expected"]["rows"])
    except ValueError as error:
        print("DỮ LIỆU KHÔNG HỢP LỆ, chưa tạo gì:")
        print(error)
        sys.exit(1)
    print("Bước 1: CSV hợp lệ,", len(raw_data), "dòng")

    # Bước 3: ghép nội dung 6 file
    schema_text = read_sql_file(DATABASE_FOLDER / "schema.sql")
    staging_text = read_sql_file(DATABASE_FOLDER / "staging.sql")
    check_text = read_sql_file(DATABASE_FOLDER / "kiem_tra_sau_nap.sql")

    files_to_write = [
        ("00_create_database.sql", build_create_database_sql(database_name)),
        ("01_schema.sql", ensure_use_statement(schema_text, database_name)),
        ("02_staging.sql", ensure_use_statement(staging_text, database_name)),
        ("03_load_telco.sql", build_load_sql(raw_data, config)),
        ("04_kiem_tra_sau_nap.sql", ensure_use_statement(check_text, database_name)),
        ("README_chay.txt", build_readme(config, len(raw_data))),
    ]

    # Bước 4: ghi từng file ra delivery/scripts
    SCRIPT_FOLDER.mkdir(parents=True, exist_ok=True)
    for file_name, content in files_to_write:
        write_sql_file(SCRIPT_FOLDER / file_name, content)
        size_kb = (SCRIPT_FOLDER / file_name).stat().st_size / 1024
        print("  đã ghi", file_name, "(" + format(size_kb, ".1f") + " KB)")

    # Bước 5: gói 6 file thành một file zip
    with zipfile.ZipFile(ZIP_FILE, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, _ in files_to_write:
            zip_file.write(SCRIPT_FOLDER / file_name, arcname=file_name)
    zip_size_kb = ZIP_FILE.stat().st_size / 1024
    print("Bước 2: đã tạo", ZIP_FILE, "(" + format(zip_size_kb, ".1f") + " KB)")
    print("XONG. Chưa chạy gì trên SQL Server; việc kiểm là việc tiếp theo.")


if __name__ == "__main__":
    main()
