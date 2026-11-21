"""
Bảng KỊCH BẢN chăm sóc: so cách phân nhóm Medium/High hiện tại với "chỉ chăm sóc top 10% hoặc top 20% khách
có điểm cao nhất" (đề tài 18, Mức 1, P4c, yêu cầu Z-11 của cô).

Cô dặn (email 26/10/2026, Câu 4):
  - Giữ nguyên hai ngưỡng đã chọn: Medium = 0,3148 và High = 0,3866.
  - Medium chỉ chiếm 6,8% và High đến 29,5% nên phân nhóm chưa thuận lợi cho nghiệp vụ chăm sóc.
  - Thêm bảng so sánh với phương án ưu tiên top 10% hoặc top 20% khi nhân viên có nguồn lực hạn chế.
  - Bảng này CHỈ minh họa lựa chọn nghiệp vụ, KHÔNG dùng để đổi ngưỡng hay đổi kết quả test đã khóa.

Quy tắc đã cài vào code:
  - Script chỉ ĐỌC 3 file có sẵn: oof_train.csv, test_scores.csv, churn_model_meta_v1.json
    (và Telco-Customer-Churn.csv để lấy cột Contract). KHÔNG đụng database, KHÔNG huấn luyện lại,
    KHÔNG chọn lại ngưỡng (hai ngưỡng đọc từ metadata).
  - Bảng chính tính trên điểm OUT-OF-FOLD của tập train (5.634 khách): mỗi khách được chấm bởi mô hình
    không thấy khách đó lúc học, nên là cơ sở để cân nhắc nghiệp vụ. Bảng trên tập test (1.409 khách) chỉ
    để đối chiếu, giống cách train.py đã báo top-K coverage trên test.
  - Định nghĩa top-K giống evaluate.top_k_coverage: K = ceil(tỷ lệ x số khách), xếp điểm giảm dần (ổn định).
  - Điểm chỉ hỗ trợ chăm sóc khách hàng, không phải quan hệ nhân quả (R-02, R-07).

Chạy:   python ml\\src\\scenario_topk.py
Cần:    pip install pandas numpy   (đã có sau khi chạy train.py)
Ghi ra: ml/results/metrics/scenario_01_so_sanh_kich_ban.csv
        ml/results/metrics/scenario_02_phan_bo_muc_rui_ro.csv
        ml/results/metrics/scenario_03_recall_theo_hop_dong.csv
        ml/results/scenario_report.txt
Đặt file này ở:  <thư mục dự án>/ml/src/scenario_topk.py
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREDICTIONS_FOLDER = PROJECT_ROOT / "ml" / "results" / "predictions"
OOF_FILE = PREDICTIONS_FOLDER / "oof_train.csv"
TEST_FILE = PREDICTIONS_FOLDER / "test_scores.csv"
META_FILE = PROJECT_ROOT / "ml" / "models" / "churn_model_meta_v1.json"
RAW_FILE = PROJECT_ROOT / "ml" / "data" / "raw" / "Telco-Customer-Churn.csv"
METRICS_FOLDER = PROJECT_ROOT / "ml" / "results" / "metrics"
REPORT_FILE = PROJECT_ROOT / "ml" / "results" / "scenario_report.txt"

TOP_FRACTIONS = (0.10, 0.20)          # hai kịch bản cô nêu
CONTRACT_ORDER = ["Month-to-month", "One year", "Two year"]
MIN_CHURNERS_RELIABLE = 30            # nhóm có ít nhãn churn hơn mức này thì Recall không đáng tin


# ---------------------------------------------------------------
# 1. Đọc dữ liệu
# ---------------------------------------------------------------

def load_inputs():
    """Đọc điểm out-of-fold, điểm test, ngưỡng và cột Contract. Thiếu file thì dừng với thông báo rõ."""
    for path in (OOF_FILE, TEST_FILE, META_FILE):
        if not path.exists():
            raise FileNotFoundError("Chưa có file " + str(path) + ". Chạy ml\\src\\train.py trước.")

    with open(META_FILE, "r", encoding="utf-8") as file:
        meta = json.load(file)
    medium = float(meta["threshold_medium"])
    high = None if meta.get("threshold_high") is None else float(meta["threshold_high"])

    # Cột 'selected' là điểm của mô hình được chọn (bản gốc hoặc bản hiệu chuẩn), cùng cột train.py ghi
    oof = pd.read_csv(OOF_FILE)[["customerID", "y_true", "selected"]]
    test = pd.read_csv(TEST_FILE)[["customerID", "y_true", "selected"]]

    # Contract lấy từ CSV gốc (chỉ để mô tả nhóm được chọn, KHÔNG dùng làm đặc trưng)
    if RAW_FILE.exists():
        contract = pd.read_csv(RAW_FILE, dtype=str, keep_default_na=False, usecols=["customerID", "Contract"])
        contract["Contract"] = contract["Contract"].str.strip()
        oof = oof.merge(contract, on="customerID", how="left")
        test = test.merge(contract, on="customerID", how="left")
    else:
        oof["Contract"] = np.nan
        test["Contract"] = np.nan

    return meta, medium, high, oof, test


# ---------------------------------------------------------------
# 2. Chọn nhóm theo từng kịch bản
# ---------------------------------------------------------------

def select_by_threshold(frame, threshold):
    """Kịch bản theo ngưỡng: chọn mọi khách có điểm >= ngưỡng. Trả về mảng bool."""
    return (frame["selected"].values >= threshold)


def select_top_fraction(frame, fraction):
    """Kịch bản top-K: chọn K = ceil(fraction x số khách) khách có điểm cao nhất (xếp ổn định, như evaluate.py)."""
    count = len(frame)
    k = int(math.ceil(fraction * count))
    order = np.argsort(-frame["selected"].values, kind="stable")
    mask = np.zeros(count, dtype=bool)
    mask[order[:k]] = True
    return mask


def build_scenarios(frame, medium, high):
    """Danh sách (tên kịch bản, mảng bool) cho một tập khách. High có thể None nếu metadata không có."""
    scenarios = []
    if high is not None:
        scenarios.append(("Hiện tại: chỉ nhóm High (điểm >= ngưỡng High)", select_by_threshold(frame, high)))
    scenarios.append(("Hiện tại: Medium + High (điểm >= ngưỡng Medium)", select_by_threshold(frame, medium)))
    for fraction in TOP_FRACTIONS:
        label = "Top " + str(round(fraction * 100)) + "% điểm cao nhất"
        scenarios.append((label, select_top_fraction(frame, fraction)))
    return scenarios


# ---------------------------------------------------------------
# 3. Tính bảng
# ---------------------------------------------------------------

def summarize_selection(frame, mask):
    """Chỉ tiêu của một nhóm được chọn chăm sóc."""
    y = frame["y_true"].values
    total = len(frame)
    churners = int(y.sum())
    base_rate = churners / total

    selected = int(mask.sum())
    true_positive = int((mask & (y == 1)).sum())
    false_positive = selected - true_positive
    precision = true_positive / selected if selected > 0 else 0.0
    recall = true_positive / churners if churners > 0 else 0.0
    lift = precision / base_rate if base_rate > 0 else float("nan")

    lowest_score = float(frame["selected"].values[mask].min()) if selected > 0 else float("nan")
    month_share = float("nan")
    if selected > 0 and frame["Contract"].notna().any():
        month_share = float((frame["Contract"].values[mask] == "Month-to-month").mean())

    return {
        "Số khách được chọn": selected,
        "Tỷ lệ khách (%)": round(100 * selected / total, 1),
        "Điểm thấp nhất trong nhóm": round(lowest_score, 4),
        "Số khách nhãn churn bắt được (TP)": true_positive,
        "Số khách nhãn No bị chọn (FP)": false_positive,
        "Precision": round(precision, 4),
        "Recall (coverage)": round(recall, 4),
        "Lift so với chọn ngẫu nhiên": round(lift, 2),
        "Tỷ lệ Month-to-month trong nhóm (%)": round(100 * month_share, 1) if not math.isnan(month_share) else None,
    }


def scenario_table(frame, set_name, medium, high):
    """Bảng 1: so sánh các kịch bản trên một tập (OOF hoặc test)."""
    rows = []
    for name, mask in build_scenarios(frame, medium, high):
        row = {"Tập dữ liệu": set_name, "Kịch bản": name}
        row.update(summarize_selection(frame, mask))
        rows.append(row)
    return pd.DataFrame(rows)


def risk_band_table(frame, set_name, medium, high):
    """Bảng 2: phân bố Low/Medium/High theo hai ngưỡng hiện tại, kèm tỷ lệ nhãn churn trong từng mức.
    Cho thấy vì sao Medium chỉ chiếm ít khách: khoảng điểm giữa hai ngưỡng hẹp."""
    score = frame["selected"].values
    y = frame["y_true"].values
    total = len(frame)

    if high is None:
        bands = [("Low", score < medium), ("Medium trở lên", score >= medium)]
    else:
        bands = [
            ("Low", score < medium),
            ("Medium", (score >= medium) & (score < high)),
            ("High", score >= high),
        ]

    rows = []
    for name, mask in bands:
        count = int(mask.sum())
        churners = int((mask & (y == 1)).sum())
        rows.append({
            "Tập dữ liệu": set_name,
            "Mức rủi ro": name,
            "Số khách": count,
            "Tỷ lệ khách (%)": round(100 * count / total, 1),
            "Số khách nhãn churn": churners,
            "Tỷ lệ nhãn churn trong mức (%)": round(100 * churners / count, 1) if count > 0 else None,
        })
    return pd.DataFrame(rows)


def contract_recall_table(frame, set_name, medium, high):
    """Bảng 3: Recall theo loại hợp đồng cho từng kịch bản (liên quan hạn chế Z-14: mô hình chủ yếu bắt
    nhóm Month-to-month). Nhóm ít khách nhãn churn thì Recall không đáng tin, có cột cảnh báo."""
    if not frame["Contract"].notna().any():
        return pd.DataFrame()

    y = frame["y_true"].values
    rows = []
    for name, mask in build_scenarios(frame, medium, high):
        for contract in CONTRACT_ORDER:
            in_group = (frame["Contract"].values == contract)
            churners = int((in_group & (y == 1)).sum())
            caught = int((in_group & (y == 1) & mask).sum())
            rows.append({
                "Tập dữ liệu": set_name,
                "Kịch bản": name,
                "Hợp đồng": contract,
                "Số khách nhãn churn": churners,
                "Số khách bắt được": caught,
                "Recall": round(caught / churners, 3) if churners > 0 else None,
                "Độ tin cậy": "đủ mẫu" if churners >= MIN_CHURNERS_RELIABLE else "ÍT MẪU, không kết luận",
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------
# 4. Ghi kết quả
# ---------------------------------------------------------------

def save_table(table, file_name):
    METRICS_FOLDER.mkdir(parents=True, exist_ok=True)
    path = METRICS_FOLDER / file_name
    table.to_csv(path, index=False, encoding="utf-8-sig")
    print("  đã ghi", path)


def main():
    try:
        meta, medium, high, oof, test = load_inputs()
    except FileNotFoundError as error:
        print("DỪNG:", error)
        return

    print("Mô hình      :", meta.get("model_name"), "| hiệu chuẩn:", meta.get("calibrated"))
    print("Ngưỡng       : Medium", round(medium, 4), "| High", None if high is None else round(high, 4),
          "(đọc từ metadata, KHÔNG chọn lại)")
    print("Tập OOF train:", len(oof), "khách | tỷ lệ nhãn churn", round(oof["y_true"].mean(), 4))
    print("Tập test     :", len(test), "khách | tỷ lệ nhãn churn", round(test["y_true"].mean(), 4))

    # Bảng 1: kịch bản; bảng chính là OOF, test để đối chiếu
    table_1 = pd.concat([
        scenario_table(oof, "OOF train (bảng chính)", medium, high),
        scenario_table(test, "Test (đối chiếu)", medium, high),
    ], ignore_index=True)

    # Bảng 2: phân bố mức rủi ro
    table_2 = pd.concat([
        risk_band_table(oof, "OOF train", medium, high),
        risk_band_table(test, "Test", medium, high),
    ], ignore_index=True)

    # Bảng 3: Recall theo hợp đồng
    table_3 = pd.concat([
        contract_recall_table(oof, "OOF train", medium, high),
        contract_recall_table(test, "Test", medium, high),
    ], ignore_index=True)

    print("\nGhi kết quả")
    save_table(table_1, "scenario_01_so_sanh_kich_ban.csv")
    save_table(table_2, "scenario_02_phan_bo_muc_rui_ro.csv")
    if len(table_3) > 0:
        save_table(table_3, "scenario_03_recall_theo_hop_dong.csv")

    # Báo cáo văn bản (đưa vào gói nộp)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    lines = [
        "BẢNG KỊCH BẢN CHĂM SÓC (đề tài 18, Mức 1, P4c, yêu cầu Z-11)",
        "Chỉ minh họa lựa chọn nghiệp vụ. KHÔNG đổi ngưỡng, KHÔNG đổi kết quả test đã khóa.",
        "Điểm chỉ hỗ trợ chăm sóc khách hàng, không phải quan hệ nhân quả (R-02, R-07).",
        "",
        "Mô hình: " + str(meta.get("model_name")) + " | hiệu chuẩn: " + str(meta.get("calibrated")),
        "Ngưỡng Medium = " + format(medium, ".4f") + " | ngưỡng High = "
        + ("không có" if high is None else format(high, ".4f")) + " (đọc từ metadata)",
        "Tập OOF train: " + str(len(oof)) + " khách; tập test: " + str(len(test)) + " khách",
        "",
        "BẢNG 1. SO SÁNH KỊCH BẢN",
        table_1.to_string(index=False),
        "",
        "BẢNG 2. PHÂN BỐ MỨC RỦI RO THEO HAI NGƯỠNG HIỆN TẠI",
        table_2.to_string(index=False),
        "",
        "BẢNG 3. RECALL THEO LOẠI HỢP ĐỒNG (liên quan Z-14)",
        table_3.to_string(index=False) if len(table_3) > 0 else "(không có cột Contract)",
    ]
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(lines) + "\n")
    print("  đã ghi", REPORT_FILE)

    print("\n=== BẢNG 1 (rút gọn) ===")
    short = ["Tập dữ liệu", "Kịch bản", "Số khách được chọn", "Tỷ lệ khách (%)", "Precision",
             "Recall (coverage)", "Lift so với chọn ngẫu nhiên"]
    print(table_1[short].to_string(index=False))
    print("\n=== BẢNG 2 ===")
    print(table_2.to_string(index=False))


if __name__ == "__main__":
    main()
