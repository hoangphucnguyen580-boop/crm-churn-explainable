"""
Tải file CSV "IBM Telco Customer Churn sample dataset" về máy.

- Lưu vào  <thư mục dự án>/ml/data/raw/Telco-Customer-Churn.csv
- File trong raw/ là BẢN GỐC, không bao giờ sửa tay.
- Nếu file đã có thì KHÔNG tải lại, chỉ in thông tin để đối chiếu.
- In mã băm SHA-256 của file: sau này lưu vào ModelVersions.DatasetHash
  để chứng minh mọi lần huấn luyện dùng cùng một bản dữ liệu (R-05).

Chạy:  python download_telco.py
Vị trí đặt file này:  <thư mục dự án>/etl/download_telco.py
"""

import hashlib
import urllib.request
from pathlib import Path

# Nguồn dữ liệu (repo IBM đã archive từ 22/07/2024, chỉ đọc)
CSV_URL = (
    "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/"
    "master/data/Telco-Customer-Churn.csv"
)

# Thư mục dự án = thư mục cha của thư mục etl chứa file này
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_FOLDER = PROJECT_ROOT / "ml" / "data" / "raw"
RAW_FILE = RAW_FOLDER / "Telco-Customer-Churn.csv"


def calculate_sha256(file_path):
    """Tính mã băm SHA-256 của file, đọc từng khối 1 MB để không tốn RAM."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as file:
        while True:
            block = file.read(1024 * 1024)
            if not block:
                break
            hasher.update(block)
    return hasher.hexdigest()


def count_text_lines(file_path):
    """Đếm số dòng của file văn bản (gồm cả dòng tiêu đề)."""
    line_count = 0
    with open(file_path, "r", encoding="utf-8") as file:
        for _ in file:
            line_count += 1
    return line_count


def main():
    # Bước 1: tạo thư mục raw nếu chưa có
    RAW_FOLDER.mkdir(parents=True, exist_ok=True)

    # Bước 2: chỉ tải khi file chưa tồn tại
    if RAW_FILE.exists():
        print("File đã có, KHÔNG tải lại:", RAW_FILE)
    else:
        print("Đang tải từ:", CSV_URL)
        urllib.request.urlretrieve(CSV_URL, RAW_FILE)
        print("Đã lưu vào:", RAW_FILE)

    # Bước 3: in thông tin để đối chiếu
    file_size = RAW_FILE.stat().st_size
    line_count = count_text_lines(RAW_FILE)
    sha256_value = calculate_sha256(RAW_FILE)

    print("Kích thước :", file_size, "byte")
    print("Số dòng    :", line_count, "(gồm 1 dòng tiêu đề, kỳ vọng 7044)")
    print("SHA-256    :", sha256_value)


if __name__ == "__main__":
    main()
