"""
Kiểm tra chất lượng dữ liệu (data quality) của file Telco CSV gốc.

Script chỉ ĐỌC file trong ml/data/raw/, không sửa file nào, không đụng database.
Cuối báo cáo có bảng đối chiếu với các con số đã kiểm ở P0 (kế hoạch Mục 4.1);
dòng nào ghi KHÁC nghĩa là file tải về khác với file tao đã phân tích.

Chạy:  python data_quality.py
Cần:   pip install pandas
Vị trí đặt file này:  <thư mục dự án>/etl/data_quality.py
"""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = PROJECT_ROOT / "ml" / "data" / "raw" / "Telco-Customer-Churn.csv"

# Các con số đã kiểm trực tiếp trên file CSV (kế hoạch Mục 4.1)
EXPECTED_ROWS = 7043
EXPECTED_COLUMNS = 21
EXPECTED_BLANK_TOTAL_CHARGES = 11
EXPECTED_CHURN_YES = 1869
EXPECTED_CHURN_NO = 5174
CUSTOMER_ID_MAX_LENGTH = 20  # độ dài tối đa của cột Customers.CustomerID trong database


def print_section(title):
    print()
    print("=== " + title + " ===")


def main():
    # Bước 0: phải có file thì mới kiểm
    if not RAW_FILE.exists():
        print("Chưa có file:", RAW_FILE)
        print("Chạy download_telco.py trước.")
        return

    # Bước 1: đọc file.
    # dtype=str            -> giữ nguyên chữ trong file, không để pandas tự đoán kiểu
    # keep_default_na=False -> không âm thầm biến chuỗi như "NA" hay "" thành NaN
    raw_data = pd.read_csv(RAW_FILE, dtype=str, keep_default_na=False)

    # Bước 2: tạo bản đã cắt khoảng trắng đầu và cuối để phát hiện ô "trống giả" (chỉ có dấu cách)
    stripped_data = raw_data.copy()
    for column_name in stripped_data.columns:
        stripped_data[column_name] = stripped_data[column_name].str.strip()

    print_section("1. KÍCH THƯỚC")
    row_count = len(raw_data)
    column_count = len(raw_data.columns)
    print("Số dòng:", row_count)
    print("Số cột :", column_count)

    print_section("2. TRÙNG customerID")
    duplicate_id_count = raw_data["customerID"].duplicated().sum()
    longest_id = raw_data["customerID"].str.len().max()
    print("Số customerID bị trùng:", duplicate_id_count)
    print("customerID dài nhất   :", longest_id, "ký tự")

    print_section("3. Ô TRỐNG (sau khi cắt khoảng trắng)")
    blank_count_per_column = (stripped_data == "").sum()
    columns_with_blank = blank_count_per_column[blank_count_per_column > 0]
    if len(columns_with_blank) == 0:
        print("Không có ô trống.")
    else:
        for column_name, blank_count in columns_with_blank.items():
            print("Cột", column_name, ":", blank_count, "ô trống")

    print_section("4. GIÁ TRỊ CỦA CÁC CỘT PHÂN LOẠI (cột có tối đa 6 giá trị khác nhau)")
    for column_name in raw_data.columns:
        distinct_values = stripped_data[column_name].value_counts()
        if len(distinct_values) <= 6:
            # int(...) để in số thường, không in kiểu np.int64(...) của numpy
            value_to_count = {}
            for value, count in distinct_values.items():
                value_to_count[value] = int(count)
            print(column_name, "->", value_to_count)

    print_section("5. CÁC CỘT SỐ")
    tenure = pd.to_numeric(stripped_data["tenure"])
    monthly_charges = pd.to_numeric(stripped_data["MonthlyCharges"])
    # errors="coerce": ô không đọc được thành số (ví dụ ô trống) sẽ thành NaN thay vì báo lỗi
    total_charges = pd.to_numeric(stripped_data["TotalCharges"], errors="coerce")
    print("tenure         : từ", tenure.min(), "đến", tenure.max(), "(tháng)")
    print("MonthlyCharges : từ", monthly_charges.min(), "đến", monthly_charges.max(),
          ", trung vị", monthly_charges.median())
    print("TotalCharges   : từ", total_charges.min(), "đến", total_charges.max(),
          ", số ô không đọc được thành số:", total_charges.isna().sum())

    print_section("6. PHÂN BỐ NHÃN CHURN")
    churn_counts = stripped_data["Churn"].value_counts()
    churn_yes = churn_counts.get("Yes", 0)
    churn_no = churn_counts.get("No", 0)
    print("Yes:", churn_yes, "(", round(100 * churn_yes / row_count, 1), "% )")
    print("No :", churn_no, "(", round(100 * churn_no / row_count, 1), "% )")

    print_section("7. CẢNH BÁO: TotalCharges so với tenure x MonthlyCharges")
    # Chỉ so với khách có tenure > 0 và TotalCharges đọc được
    comparable = total_charges.notna() & (tenure > 0)
    expected_total = tenure * monthly_charges
    relative_gap = (total_charges - expected_total).abs() / expected_total
    big_gap_count = (relative_gap[comparable] > 0.25).sum()
    print("Số khách có TotalCharges lệch hơn 25% so với tenure x MonthlyCharges:", big_gap_count)
    print("(Chỉ là cảnh báo: giá cước có thể đã đổi theo thời gian, không phải lỗi dữ liệu.)")

    print_section("8. ĐỐI CHIẾU VỚI SỐ ĐÃ KIỂM Ở P0")
    # Các ô trống của TotalCharges: kiểm xem có đúng là khách tenure = 0 không
    total_charges_is_blank = stripped_data["TotalCharges"] == ""
    blank_total_charges_count = total_charges_is_blank.sum()
    blank_rows_tenure_values = set(stripped_data.loc[total_charges_is_blank, "tenure"])

    checks = [
        ("Số dòng = " + str(EXPECTED_ROWS), row_count == EXPECTED_ROWS),
        ("Số cột = " + str(EXPECTED_COLUMNS), column_count == EXPECTED_COLUMNS),
        ("Không trùng customerID", duplicate_id_count == 0),
        ("customerID vừa cột varchar(" + str(CUSTOMER_ID_MAX_LENGTH) + ")",
         longest_id <= CUSTOMER_ID_MAX_LENGTH),
        ("TotalCharges trống đúng " + str(EXPECTED_BLANK_TOTAL_CHARGES) + " ô",
         blank_total_charges_count == EXPECTED_BLANK_TOTAL_CHARGES),
        ("Các ô TotalCharges trống đều thuộc khách tenure = 0", blank_rows_tenure_values == {"0"}),
        ("Chỉ cột TotalCharges có ô trống", set(columns_with_blank.index) == {"TotalCharges"}),
        ("Churn: Yes = " + str(EXPECTED_CHURN_YES) + ", No = " + str(EXPECTED_CHURN_NO),
         churn_yes == EXPECTED_CHURN_YES and churn_no == EXPECTED_CHURN_NO),
        ("SeniorCitizen chỉ có 0 hoặc 1", set(stripped_data["SeniorCitizen"]) <= {"0", "1"}),
        ("Partner chỉ có Yes hoặc No (ETL đổi sang bit)", set(stripped_data["Partner"]) <= {"Yes", "No"}),
        ("Dependents chỉ có Yes hoặc No (ETL đổi sang bit)", set(stripped_data["Dependents"]) <= {"Yes", "No"}),
    ]

    failed_count = 0
    for description, passed in checks:
        if passed:
            print("ĐẠT :", description)
        else:
            print("KHÁC:", description)
            failed_count += 1

    print()
    if failed_count == 0:
        print("KẾT LUẬN: file khớp với số đã kiểm, có thể dùng để nạp.")
    else:
        print("KẾT LUẬN:", failed_count, "mục KHÁC. Chụp màn hình gửi tao trước khi nạp.")


if __name__ == "__main__":
    main()
