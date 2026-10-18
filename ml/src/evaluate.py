"""
Các hàm đánh giá mô hình churn: metric, chọn ngưỡng, top-K coverage, metric theo nhóm.

Quy tắc (R-03, R-05):
  - Churn lệch lớp nên dùng PR-AUC, Recall, F1 bên cạnh ROC-AUC; có Brier để kiểm xác suất.
  - Ngưỡng chỉ được chọn bằng điểm out-of-fold của tập train (CV), KHÔNG chọn trên tập test.
"""

import math

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
)


def compute_metrics(y_true, probability, threshold):
    """Metric tại một ngưỡng: Precision, Recall, F1, ROC-AUC, PR-AUC, Brier, confusion matrix.

    zero_division = 0: nếu mô hình không gắn cờ khách nào thì Precision/Recall tính là 0 (không báo lỗi).
    """
    y_true = np.asarray(y_true)
    probability = np.asarray(probability)
    predicted = (probability >= threshold).astype(int)

    true_negative, false_positive, false_negative, true_positive = confusion_matrix(
        y_true, predicted, labels=[0, 1]
    ).ravel()

    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "threshold": float(threshold),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "roc_auc": float(roc_auc_score(y_true, probability)),
        "pr_auc": float(average_precision_score(y_true, probability)),
        "brier": float(brier_score_loss(y_true, probability)),
        "tn": int(true_negative),
        "fp": int(false_positive),
        "fn": int(false_negative),
        "tp": int(true_positive),
        "flagged_rate": float(predicted.mean()),
    }


def select_threshold_for_recall(y_true, probability, min_recall):
    """Chọn ngưỡng CAO NHẤT mà Recall vẫn >= min_recall (tức Precision lớn nhất trong các ngưỡng đạt).

    Trả về (ngưỡng, precision đạt được, recall đạt được) hoặc None nếu không ngưỡng nào đạt.
    """
    precision, recall, thresholds = precision_recall_curve(y_true, probability)
    precision, recall = precision[:-1], recall[:-1]  # điểm cuối (precision = 1, recall = 0) không có ngưỡng
    candidates = np.where(recall >= min_recall)[0]
    if len(candidates) == 0:
        return None
    best = candidates[-1]  # recall giảm dần khi ngưỡng tăng, nên ứng viên cuối là ngưỡng cao nhất
    return float(thresholds[best]), float(precision[best]), float(recall[best])


def select_threshold_for_precision(y_true, probability, min_precision, min_flagged):
    """Chọn ngưỡng THẤP NHẤT mà Precision >= min_precision (tức Recall lớn nhất trong các ngưỡng đạt).

    min_flagged: số khách tối thiểu bị gắn cờ, để không chọn nhầm ngưỡng ở đuôi chỉ có vài khách
    (Precision của vài khách rất nhiễu).
    Trả về (ngưỡng, precision, recall) hoặc None nếu không ngưỡng nào đạt.
    """
    probability = np.asarray(probability)
    precision, recall, thresholds = precision_recall_curve(y_true, probability)
    precision, recall = precision[:-1], recall[:-1]
    sorted_scores = np.sort(probability)
    flagged_counts = len(probability) - np.searchsorted(sorted_scores, thresholds, side="left")
    candidates = np.where((precision >= min_precision) & (flagged_counts >= min_flagged))[0]
    if len(candidates) == 0:
        return None
    best = candidates[0]
    return float(thresholds[best]), float(precision[best]), float(recall[best])


def top_k_coverage(y_true, probability, fraction):
    """Top-K coverage: trong `fraction` khách có điểm cao nhất, có bao nhiêu phần trăm số khách churn.

    Chọn ngẫu nhiên thì xấp xỉ bằng `fraction` (ví dụ 10% khách cho khoảng 10% số churner).
    """
    y_true = np.asarray(y_true)
    probability = np.asarray(probability)
    k = int(math.ceil(fraction * len(y_true)))
    order = np.argsort(-probability, kind="stable")
    caught = y_true[order[:k]].sum()
    return float(caught / y_true.sum())


def metrics_by_group(frame, y_true, probability, threshold, group_column, group_label, group_order=None):
    """Bảng metric theo nhóm (Contract, nhóm tenure, InternetService, PaymentMethod).

    Chỉ để xem mô hình yếu ở nhóm nào, KHÔNG dùng để đối xử khác biệt với khách hàng (R-07).
    """
    work = pd.DataFrame({
        "group": frame[group_column].astype(str).values,
        "y": np.asarray(y_true),
        "p": np.asarray(probability),
    })
    work["flagged"] = (work["p"] >= threshold).astype(int)

    groups = group_order if group_order is not None else sorted(work["group"].unique())
    rows = []
    for group_value in groups:
        part = work[work["group"] == str(group_value)]
        if len(part) == 0:
            continue
        true_positive = int(((part["flagged"] == 1) & (part["y"] == 1)).sum())
        false_positive = int(((part["flagged"] == 1) & (part["y"] == 0)).sum())
        false_negative = int(((part["flagged"] == 0) & (part["y"] == 1)).sum())
        flagged = true_positive + false_positive
        actual_churn = true_positive + false_negative
        rows.append({
            "Chỉ tiêu nhóm": group_label,
            "Nhóm": group_value,
            "Số khách": len(part),
            "Số khách nhãn churn": actual_churn,
            "Tỷ lệ nhãn churn (%)": round(part["y"].mean() * 100, 2),
            "Tỷ lệ bị gắn cờ (%)": round(part["flagged"].mean() * 100, 2),
            "Precision": round(true_positive / flagged, 3) if flagged > 0 else float("nan"),
            "Recall": round(true_positive / actual_churn, 3) if actual_churn > 0 else float("nan"),
            "FP": false_positive,
            "FN": false_negative,
        })
    return pd.DataFrame(rows)
