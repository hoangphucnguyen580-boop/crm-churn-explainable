"""
Vá MỘT LẦN các script để chúng ghi log chạy qua etl/run_log.py (P4c, Z-12). Chạy xong có thể xóa file này.

Script thay đoạn cuối mỗi file:
    if __name__ == "__main__":
        main()
bằng:
    if __name__ == "__main__":
        import run_log  # log chạy vào ml/results/etl_run_log.txt (Z-12)
        with run_log.log_run("<tên file>"):
            main()

An toàn: chạy lại nhiều lần được (file đã vá thì bỏ qua); giữ nguyên kiểu xuống dòng (CRLF hay LF) và BOM;
mẫu không khớp đúng một chỗ thì KHÔNG sửa file đó và báo rõ. Không đụng database.

Chạy:  python etl\apply_p4c.py
"""

import codecs
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 4 script ghi thẳng vào database. load_telco và register_model là hai script còn thiếu log (Z-12);
# simulate_interactions và score_batch đã có báo cáo riêng, thêm log chạy để đủ lịch sử một chỗ.
TARGETS = [
    PROJECT_ROOT / "etl" / "load_telco.py",
    PROJECT_ROOT / "etl" / "register_model.py",
    PROJECT_ROOT / "etl" / "simulate_interactions.py",
    PROJECT_ROOT / "ml" / "src" / "score_batch.py",
]

# Khớp đúng khối cuối file, chấp nhận dấu cách thừa
PATTERN = re.compile(r'if __name__ == "__main__":[ \t]*\n[ \t]+main\(\)[ \t]*\n?\s*$')


def patch_one(path):
    if not path.exists():
        return "BỎ QUA : không thấy file " + str(path)

    raw = path.read_bytes()
    has_bom = raw.startswith(codecs.BOM_UTF8)
    text = raw.decode("utf-8-sig")
    uses_crlf = "\r\n" in text
    text = text.replace("\r\n", "\n")

    if "run_log.log_run" in text:
        return "ĐÃ VÁ  : " + path.name + " (bỏ qua)"

    matches = PATTERN.findall(text)
    if len(matches) != 1:
        return "KHÔNG VÁ: " + path.name + " (không thấy đúng một khối 'if __name__ ... main()' ở cuối file)"

    new_block = (
        'if __name__ == "__main__":\n'
        '    import run_log  # log chạy vào ml/results/etl_run_log.txt (Z-12)\n'
        '    with run_log.log_run("' + path.name + '"):\n'
        '        main()\n'
    )
    patched = PATTERN.sub(new_block, text)
    if uses_crlf:
        patched = patched.replace("\n", "\r\n")

    data = patched.encode("utf-8")
    if has_bom:
        data = codecs.BOM_UTF8 + data
    path.write_bytes(data)
    return "ĐÃ VÁ   : " + path.name


def main():
    for path in TARGETS:
        print(patch_one(path))


if __name__ == "__main__":
    main()
