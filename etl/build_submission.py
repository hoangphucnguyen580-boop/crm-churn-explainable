"""
Tạo FILE ZIP NỘP TIẾN ĐỘ cho cô (Y-NOP, D-20): một file .zip chứa toàn bộ source liên quan.

Script chỉ ĐỌC các file trong dự án, KHÔNG sửa file nào, KHÔNG nối SQL Server.

Zip gồm (đặt trong thư mục gốc crm-churn-explainable/ bên trong zip):
  README.md, README_CHAY.docx, requirements.txt, .gitignore
  database/   (schema.sql, constraints_bo_sung.sql, staging.sql, các file kiểm tra)
  etl/        (script tải, kiểm tra, nạp, mô phỏng, đăng ký mô hình, build)
  ml/         (src, notebooks, models gồm cả .joblib, results; KHÔNG có CSV gốc)
  ml-api/     (FastAPI)
  web-crm/    (ASP.NET Core MVC; KHÔNG có bin, obj, .vs, *.user, appsettings.Development.json)
  docs/       (ERD, PowerDesigner, ...)
  sql_only/   (chép từ delivery/scripts: gói SQL thuần 00 đến 04, cô chỉ cần SQL Server + SSMS)
  MANIFEST.txt (danh sách file và kích thước, script tự sinh)

Quy tắc an toàn (R-06, R-15, cô dặn: không đưa mật khẩu, khóa bí mật, dữ liệu nhạy cảm):
  - Loại: .git, __pycache__, .venv, bin, obj, .vs, *.user, *.bak, *.bacpac, .env,
    appsettings.Development.json, secrets.json, CSV gốc trong ml/data/raw, ml/_quick.
  - QUÉT nội dung mọi file chữ trước khi nén: gặp chuỗi nghi là mật khẩu/khóa thì DỪNG, không tạo zip.
  - Tùy chọn --scan-password: script hỏi mật khẩu demo (không hiện lên màn hình, không lưu),
    rồi dò xem mật khẩu đó có nằm trong file nào sắp nén không.

Chạy:         python etl\build_submission.py
Chạy kèm dò:  python etl\build_submission.py --scan-password
Chỉ kiểm tra: python etl\build_submission.py --dry-run   (liệt kê, quét, KHÔNG tạo zip)
Cần:          chỉ thư viện chuẩn của Python
Đặt file này ở:  <thư mục dự án>/etl/build_submission.py
"""

import getpass
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DELIVERY_FOLDER = PROJECT_ROOT / "delivery"
SQL_ONLY_SOURCE = DELIVERY_FOLDER / "scripts"
ZIP_ROOT_NAME = "crm-churn-explainable"

# Thư mục và file ở gốc dự án được đưa vào zip (cái nào không có thì bỏ qua và báo)
INCLUDE_FOLDERS = ["database", "etl", "ml", "ml-api", "web-crm", "docs"]
INCLUDE_ROOT_FILES = ["README.md", "README_CHAY.docx", "requirements.txt", ".gitignore"]

# Tên thư mục bị loại ở BẤT KỲ cấp nào
EXCLUDED_FOLDER_NAMES = {
    ".git", "__pycache__", ".venv", "venv", "bin", "obj", ".vs", ".idea",
    "_quick", ".ipynb_checkpoints", "node_modules",
}
# Đuôi file bị loại
EXCLUDED_SUFFIXES = {".pyc", ".bak", ".bacpac", ".user", ".suo", ".log"}
# Tên file bị loại
EXCLUDED_FILE_NAMES = {".env", "secrets.json", "appsettings.Development.json"}
# Đường dẫn (so với gốc dự án, dấu /) bị loại
EXCLUDED_RELATIVE_PREFIXES = ["ml/data/raw/"]

# Đuôi file chữ sẽ được quét tìm mật khẩu/khóa bí mật
TEXT_SUFFIXES = {
    ".py", ".cs", ".cshtml", ".csproj", ".sln", ".json", ".md", ".txt", ".sql",
    ".ipynb", ".config", ".mermaid", ".css", ".js", ".html", ".yml", ".yaml", ".ini",
}

# Mẫu nghi ngờ là bí mật. Cố ý chặt để không báo nhầm tên cột PasswordHash.
SECRET_PATTERNS = [
    ("chuỗi kết nối có mật khẩu", re.compile(r"\b(?:Password|Pwd)\s*=\s*[^;\s\"']+", re.IGNORECASE)),
    ("chuỗi kết nối có User ID", re.compile(r"\bUser\s*Id\s*=\s*[^;\s\"']+", re.IGNORECASE)),
    ("DemoPassword có giá trị", re.compile(r"DemoPassword\"?\s*[:=]\s*\"[^\"]+\"", re.IGNORECASE)),
    ("khóa API", re.compile(r"\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)\b\s*[:=]\s*[\"'][^\"']{8,}", re.IGNORECASE)),
    ("khóa riêng", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

BIG_FILE_BYTES = 10 * 1024 * 1024  # file lớn hơn 10 MB thì cảnh báo


def relative_posix(path):
    """Đường dẫn so với gốc dự án, dùng dấu / cho dễ so khớp."""
    return path.relative_to(PROJECT_ROOT).as_posix()


def is_excluded(path):
    """True nếu file này không được đưa vào zip."""
    relative = relative_posix(path)
    parts = relative.split("/")
    for folder_name in parts[:-1]:
        if folder_name in EXCLUDED_FOLDER_NAMES:
            return True
    if path.name in EXCLUDED_FILE_NAMES:
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if path.name.startswith("~$"):  # file tạm của Office
        return True
    for prefix in EXCLUDED_RELATIVE_PREFIXES:
        if relative.startswith(prefix):
            return True
    return False


def collect_files():
    """Trả về (danh sách (đường dẫn thật, đường dẫn trong zip), danh sách cảnh báo, danh sách bị loại)."""
    entries = []
    warnings = []
    skipped = []

    # File ở gốc dự án
    for file_name in INCLUDE_ROOT_FILES:
        path = PROJECT_ROOT / file_name
        if path.exists():
            entries.append((path, file_name))
        else:
            warnings.append("Thiếu file ở gốc dự án: " + file_name)

    # Các thư mục
    for folder_name in INCLUDE_FOLDERS:
        folder = PROJECT_ROOT / folder_name
        if not folder.exists():
            warnings.append("Thiếu thư mục: " + folder_name)
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            if is_excluded(path):
                skipped.append(relative_posix(path))
                continue
            entries.append((path, relative_posix(path)))

    # Gói SQL thuần: chép từ delivery/scripts vào sql_only/
    if SQL_ONLY_SOURCE.exists():
        sql_files = sorted(p for p in SQL_ONLY_SOURCE.iterdir() if p.is_file())
        for path in sql_files:
            entries.append((path, "sql_only/" + path.name))
        # Cảnh báo nếu gói SQL cũ hơn schema hiện tại (chưa chạy lại build_delivery.py)
        load_file = SQL_ONLY_SOURCE / "03_load_telco.sql"
        if load_file.exists():
            for sql_path in (PROJECT_ROOT / "database").glob("*.sql"):
                if sql_path.stat().st_mtime > load_file.stat().st_mtime:
                    warnings.append(
                        "database/" + sql_path.name + " mới hơn delivery/scripts/03_load_telco.sql: "
                        "nên chạy lại etl\\build_delivery.py trước khi nén."
                    )
    else:
        warnings.append("Chưa có delivery/scripts: chạy etl\\build_delivery.py trước nếu muốn kèm gói SQL thuần.")

    # Cảnh báo mục ở gốc dự án không nằm trong danh sách (để mình biết có thứ bị bỏ sót)
    known = set(INCLUDE_FOLDERS) | set(INCLUDE_ROOT_FILES) | {"delivery", ".git"}
    for item in sorted(PROJECT_ROOT.iterdir()):
        if item.name not in known and item.name not in EXCLUDED_FOLDER_NAMES:
            warnings.append("Mục ở gốc dự án KHÔNG được đưa vào zip: " + item.name)

    return entries, warnings, skipped


def read_text_or_none(path):
    """Đọc file chữ (UTF-8, có hoặc không BOM). Không đọc được thì trả None."""
    try:
        return path.read_bytes().decode("utf-8-sig")
    except UnicodeError:
        return None


def scan_for_secrets(entries, typed_password):
    """Quét nội dung file chữ. Trả về danh sách lỗi (đường dẫn trong zip, loại, đoạn khớp đã rút gọn)."""
    problems = []
    for path, zip_name in entries:
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = read_text_or_none(path)
        if text is None:
            continue
        for label, pattern in SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                snippet = match.group(0)
                if len(snippet) > 40:
                    snippet = snippet[:40] + "..."
                problems.append((zip_name, label, snippet))
        if typed_password and typed_password in text:
            # Không in mật khẩu ra màn hình, chỉ báo là có
            problems.append((zip_name, "chứa đúng mật khẩu demo vừa nhập", "(đã ẩn)"))
    return problems


def build_manifest(entries):
    lines = [
        "MANIFEST - gói nộp tiến độ đề tài 18 (CRM tích hợp dự báo churn, Mức 1)",
        "Sinh viên: Nguyễn Hoàng Phúc - CC25TTH - 25TH2517",
        "Tạo lúc: " + datetime.now().strftime("%d/%m/%Y %H:%M"),
        "Số file: " + str(len(entries)),
        "",
    ]
    for path, zip_name in entries:
        lines.append(format(path.stat().st_size, ">12,d") + "  " + zip_name)
    return "\n".join(lines) + "\n"


def main():
    dry_run = "--dry-run" in sys.argv
    scan_password = "--scan-password" in sys.argv

    print("Thư mục dự án:", PROJECT_ROOT)
    typed_password = ""
    if scan_password:
        typed_password = getpass.getpass("Nhập mật khẩu demo để dò (không hiện, không lưu): ").strip()

    entries, warnings, skipped = collect_files()
    print("Bước 1: gom được", len(entries), "file;", len(skipped), "file bị loại theo quy tắc")

    for warning in warnings:
        print("  CẢNH BÁO:", warning)

    # File lớn
    for path, zip_name in entries:
        if path.stat().st_size > BIG_FILE_BYTES:
            print("  CẢNH BÁO: file lớn hơn 10 MB:", zip_name, "(", path.stat().st_size // 1024, "KB )")

    # Bước 2: quét bí mật, có vấn đề là dừng
    problems = scan_for_secrets(entries, typed_password)
    if problems:
        print("Bước 2: QUÉT BÍ MẬT: DỪNG, KHÔNG tạo zip. Các chỗ nghi ngờ:")
        for zip_name, label, snippet in problems:
            print("  -", zip_name, "|", label, "|", snippet)
        print("Xem từng chỗ: nếu là bí mật thật thì xóa khỏi file; nếu báo nhầm thì gửi ảnh cho tao chỉnh mẫu quét.")
        sys.exit(1)
    print("Bước 2: quét bí mật: không thấy chuỗi nghi ngờ" + (" (đã dò cả mật khẩu demo)" if typed_password else ""))

    if dry_run:
        print("CHẠY THỬ XONG: KHÔNG tạo zip. Đã loại", len(skipped), "file; ví dụ 10 file đầu bị loại:")
        for name in skipped[:10]:
            print("   ", name)
        return

    # Bước 3: nén
    DELIVERY_FOLDER.mkdir(parents=True, exist_ok=True)
    zip_path = DELIVERY_FOLDER / ("CRM_Churn_TienDo_" + datetime.now().strftime("%Y%m%d") + ".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for path, zip_name in entries:
            zip_file.write(path, arcname=ZIP_ROOT_NAME + "/" + zip_name)
        zip_file.writestr(ZIP_ROOT_NAME + "/MANIFEST.txt", build_manifest(entries))

    # Bước 4: mở lại zip để kiểm
    with zipfile.ZipFile(zip_path, "r") as zip_file:
        bad_member = zip_file.testzip()
        names = zip_file.namelist()
    if bad_member is not None:
        print("ZIP LỖI ở file:", bad_member)
        sys.exit(1)

    required_in_zip = ["README_CHAY.docx", "requirements.txt", "database/schema.sql", "ml/models/churn_pipeline_v1.joblib"]
    missing = [n for n in required_in_zip if (ZIP_ROOT_NAME + "/" + n) not in names]
    print("Bước 3: đã tạo", zip_path, "(" + format(zip_path.stat().st_size / 1024, ".1f") + " KB,", len(names), "mục)")
    for name in missing:
        print("  CẢNH BÁO: trong zip THIẾU", name)
    print("XONG. Giải nén sang thư mục khác và làm đúng README_CHAY.docx để thử trước khi gửi cô.")


if __name__ == "__main__":
    main()
