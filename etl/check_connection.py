"""
Kiểm tra kết nối Python -> SQL Server (database CRM_Churn).

Đây là bước chuẩn bị cho ETL (nạp dữ liệu Telco). Script chỉ ĐỌC,
không thêm, sửa hay xóa gì trong database.

Chạy:  python check_connection.py
Cần:   pip install pyodbc
"""

import sys

import pyodbc

# Tên server đúng như thấy ở Object Explorer của SSMS: Admin-PC
SERVER = "Admin-PC"
DATABASE = "CRM_Churn"

# Các bảng sẽ đếm số dòng để xem database đang trống hay đã có dữ liệu
TABLES_TO_COUNT = ["AuditLog", "ChurnPredictions", "Role", "Staff", "Customers", "CustomerSnapshots", "Interactions", "ModelVersions", "RiskConfig", "Tickets"]


def choose_driver(installed_drivers):
    """Chọn driver ODBC của SQL Server: ưu tiên bản 18, không có thì dùng bản 17."""
    if "ODBC Driver 18 for SQL Server" in installed_drivers:
        return "ODBC Driver 18 for SQL Server"
    if "ODBC Driver 17 for SQL Server" in installed_drivers:
        return "ODBC Driver 17 for SQL Server"
    return None


def main():
    # Bước 1: in phiên bản để ghi vào README/báo cáo sau này (R-08)
    print("Python:", sys.version.split()[0])
    print("pyodbc:", pyodbc.version)

    # Bước 2: liệt kê driver ODBC có trên máy
    installed_drivers = pyodbc.drivers()
    print("Driver ODBC tìm thấy trên máy:")
    for driver_name in installed_drivers:
        print("  -", driver_name)

    # Bước 3: chọn driver; không có driver SQL Server nào thì dừng và báo rõ
    driver_name = choose_driver(installed_drivers)
    if driver_name is None:
        print("KHÔNG có 'ODBC Driver 17/18 for SQL Server'. Cần cài driver trước khi nối.")
        return
    print("Sẽ dùng driver:", driver_name)

    # Bước 4: ghép chuỗi kết nối
    #   Trusted_Connection=yes       -> đăng nhập bằng tài khoản Windows, giống SSMS
    #   TrustServerCertificate=yes   -> bỏ qua kiểm chứng chỉ; CHỈ dùng cho máy dev
    #                                   (driver 18 bật mã hóa mặc định, chứng chỉ máy dev là tự ký)
    connection_string = (
        "DRIVER={" + driver_name + "};"
        "SERVER=" + SERVER + ";"
        "DATABASE=" + DATABASE + ";"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )

    # Bước 5: nối thử, nếu lỗi thì in nguyên văn lỗi để gửi cho tao
    try:
        connection = pyodbc.connect(connection_string, timeout=10)
    except pyodbc.Error as error:
        print("KẾT NỐI THẤT BẠI:")
        print(error)
        return

    cursor = connection.cursor()

    # Bước 6: hỏi server đang nối vào database nào
    cursor.execute("SELECT DB_NAME()")
    print("Đang nối vào database:", cursor.fetchone()[0])

    # Bước 7: đếm bảng (phải là 10)
    cursor.execute("SELECT COUNT(*) FROM sys.tables")
    print("Số bảng:", cursor.fetchone()[0])

    # Bước 8: đếm số dòng từng bảng (hiện tại phải toàn 0)
    print("Số dòng hiện có:")
    for table_name in TABLES_TO_COUNT:
        cursor.execute("SELECT COUNT(*) FROM " + table_name)
        print("  -", table_name, ":", cursor.fetchone()[0])

    connection.close()
    print("KẾT NỐI OK")


if __name__ == "__main__":
    main()
