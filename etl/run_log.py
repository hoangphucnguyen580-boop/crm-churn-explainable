"""
Ghi LOG CHẠY của các script ETL vào một file riêng (đề tài 18, Mức 1, P4c, yêu cầu Z-12 của cô).

Cô dặn (email 26/10/2026, Câu 5): script ETL và chấm điểm theo lô ghi thẳng vào CSDL, không bắt buộc qua AuditLog,
nhưng phải "lưu log chạy và kết quả đối chiếu riêng".

Cách làm: mọi dòng script in ra màn hình (gồm các dòng ĐẠT/KHÁC của bước đối chiếu, dòng commit/ROLLBACK,
lỗi kết nối) được GHI THÊM vào file  ml/results/etl_run_log.txt , mỗi lần chạy một khối có giờ bắt đầu,
tên script, tham số dòng lệnh, phiên bản Python, giờ kết thúc và kết quả tự nhận diện.

Quy tắc:
  - File log chạy theo kiểu NỐI THÊM (append), không ghi đè: chạy lại thì thêm khối mới, lịch sử các lần
    chạy vẫn còn (kể cả lần bị từ chối vì bảng đã có dữ liệu).
  - Không ghi gì ngoài những gì script vốn đã in ra. Script không in mật khẩu nên log không có mật khẩu (R-06).
  - Không đổi hành vi của script: vẫn in ra màn hình như cũ; lỗi bất ngờ vẫn được ném lên như cũ.

Cách dùng (chỉ cần ở cuối file script):
    if __name__ == "__main__":
        import run_log
        with run_log.log_run("load_telco.py"):
            main()
"""

import platform
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = PROJECT_ROOT / "ml" / "results" / "etl_run_log.txt"

# Dấu hiệu trong dòng in ra để tự nhận diện kết quả (chỉ để tóm tắt; dòng gốc vẫn nằm trong log)
MARKER_COMMITTED = "đã commit"
MARKER_PROBLEMS = ["ROLLBACK", "DỪNG", "THẤT BẠI", "KHÔNG HỢP LỆ", "KHÁC:", "LỖI KHI GHI"]


class _Tee:
    """Bản sao luồng in: ghi vào luồng gốc (màn hình) và cả file log. Thuộc tính khác chuyển cho luồng gốc."""

    def __init__(self, original, log_handle, captured):
        self._original = original
        self._log_handle = log_handle
        self._captured = captured

    def write(self, text):
        self._original.write(text)
        self._log_handle.write(text)
        self._log_handle.flush()      # ghi ngay để lỡ script bị tắt giữa chừng vẫn còn log
        self._captured.append(text)
        return len(text)

    def flush(self):
        self._original.flush()
        self._log_handle.flush()

    def __getattr__(self, name):
        return getattr(self._original, name)


def _summarize(captured_text):
    """Tóm tắt kết quả từ nội dung đã in. Chỉ là nhận diện tự động, người đọc vẫn nên xem các dòng gốc."""
    problems = [marker for marker in MARKER_PROBLEMS if marker in captured_text]
    committed = MARKER_COMMITTED in captured_text
    # Chạy thử (--dry-run) thành công: script tự ROLLBACK nên không tính là bất thường nếu không có dòng KHÁC
    if "CHẠY THỬ XONG" in captured_text and "KHÁC:" not in captured_text:
        return "CHẠY THỬ (--dry-run) hoàn tất, không thấy dòng KHÁC, database không đổi"
    if committed and not problems:
        return "ĐÃ COMMIT, không thấy dòng KHÁC hay ROLLBACK"
    if problems:
        return "CÓ DẤU HIỆU BẤT THƯỜNG (" + ", ".join(problems) + "), xem các dòng phía trên"
    return "KHÔNG thấy dòng 'đã commit' (có thể là chạy thử --dry-run hoặc bị dừng), xem các dòng phía trên"


@contextmanager
def log_run(script_name):
    """Bọc một lần chạy: ghi khối log (đầu, thân, cuối) vào LOG_FILE, vẫn in ra màn hình như thường."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now()
    started_clock = time.time()
    captured = []

    with open(LOG_FILE, "a", encoding="utf-8", newline="\n") as log_handle:
        log_handle.write("\n" + "=" * 78 + "\n")
        log_handle.write("BẮT ĐẦU : " + started_at.strftime("%d/%m/%Y %H:%M:%S") + "\n")
        log_handle.write("Script   : " + script_name + "\n")
        log_handle.write("Tham số  : " + (" ".join(sys.argv[1:]) if len(sys.argv) > 1 else "(không có)") + "\n")
        log_handle.write("Python   : " + platform.python_version() + " | " + platform.platform() + "\n")
        log_handle.write("-" * 78 + "\n")
        log_handle.flush()

        original_stdout = sys.stdout
        sys.stdout = _Tee(original_stdout, log_handle, captured)
        outcome = None
        try:
            yield
        except SystemExit as error:
            outcome = "script gọi thoát (mã " + str(error.code) + ")"
            raise
        except BaseException:
            outcome = "LỖI BẤT NGỜ, đã ném lên (xem traceback phía trên)"
            log_handle.write(traceback.format_exc())
            raise
        finally:
            sys.stdout = original_stdout
            if outcome is None:
                outcome = _summarize("".join(captured))
            elapsed = time.time() - started_clock
            log_handle.write("-" * 78 + "\n")
            log_handle.write("KẾT THÚC : " + datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                             + " (" + format(elapsed, ".1f") + " giây)\n")
            log_handle.write("Kết quả tự nhận diện: " + outcome + "\n")
            log_handle.flush()
