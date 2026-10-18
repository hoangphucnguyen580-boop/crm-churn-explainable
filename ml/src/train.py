"""
Huấn luyện và đánh giá mô hình dự báo churn (đề tài 18, Mức 1, P4 bước 3).

Protocol (hướng dẫn của cô, Mục 6.1 và 7; kế hoạch Mục 7.4):
  1. Chia 80/20 có stratify, seed 42. Tập test CHỈ dùng ở bước đánh giá cuối.
  2. Trên 80% train: StratifiedKFold 5 fold. Mọi bước điền thiếu, chuẩn hóa, one-hot nằm trong Pipeline.
  3. 4 mô hình: Dummy, Logistic Regression, Random Forest, Gradient Boosting.
     Mỗi mô hình (trừ Dummy) tinh chỉnh tham số bằng lưới nhỏ GridSearchCV, chấm bằng PR-AUC, CHỈ trên train.
  4. Chọn mô hình có PR-AUC CV (trung bình 5 fold) cao nhất.
  5. Kiểm calibration: so Brier của bản gốc và bản hiệu chuẩn sigmoid (cùng 5 fold); chỉ dùng bản
     hiệu chuẩn khi Brier giảm đáng kể.
  6. Chọn hai ngưỡng bằng điểm out-of-fold của train (D-13):
       Medium = ngưỡng cao nhất mà Recall >= 0,75
       High   = ngưỡng thấp nhất mà Precision >= 0,60 (kèm số khách gắn cờ tối thiểu)
     Ngưỡng Medium cũng là ModelVersions.Threshold (ngưỡng phân loại nhị phân).
  7. Huấn luyện lại trên toàn bộ train, xem test MỘT lần, lưu mô hình + metadata + kết quả.

Không dùng dữ liệu mô phỏng Interactions/Tickets (D-04). Không diễn giải kết quả là nhân quả (R-02).

Chạy:   python ml\\src\\train.py            (đầy đủ, vài phút)
Thử:    python ml\\src\\train.py --quick    (lưới rất nhỏ, ghi vào ml\\_quick, để kiểm lỗi)
Cần:    pip install pandas scikit-learn joblib
"""

import argparse
import json
import platform
import time
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline

import evaluate
import preprocessing

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FILE = PROJECT_ROOT / "ml" / "data" / "raw" / "Telco-Customer-Churn.csv"

MODEL_VERSION = "v1"
CV_FOLDS = 5
MIN_RECALL_MEDIUM = 0.75      # ví dụ của cô (hướng dẫn Mục 7.2)
MIN_PRECISION_HIGH = 0.60     # Phúc chọn 17/10/2026
MIN_FLAGGED_HIGH = 100        # không chọn ngưỡng High ở đuôi chỉ có vài khách
CALIBRATION_MIN_GAIN = 0.001  # Brier phải giảm ít nhất chừng này mới dùng bản hiệu chuẩn
TOP_K_FRACTIONS = (0.10, 0.20)

MODEL_KEYS = ["Dummy", "LogisticRegression", "RandomForest", "GradientBoosting"]
DISPLAY_NAMES = {
    "Dummy": "Dummy",
    "LogisticRegression": "Logistic Regression",
    "RandomForest": "Random Forest",
    "GradientBoosting": "Gradient Boosting",
}


# ---------------------------------------------------------------
# 1. Không gian tham số (lưới nhỏ)
# ---------------------------------------------------------------

def make_search_spaces(quick):
    """Mỗi mô hình: (estimator, lưới tham số). Lưới rỗng nghĩa là không tinh chỉnh (Dummy)."""
    if quick:
        return {
            "Dummy": (DummyClassifier(strategy="prior"), {}),
            "LogisticRegression": (
                LogisticRegression(max_iter=2000, random_state=preprocessing.SEED),
                {"C": [0.1, 1], "class_weight": [None]},
            ),
            "RandomForest": (
                RandomForestClassifier(n_estimators=50, random_state=preprocessing.SEED, n_jobs=1),
                {"max_depth": [6], "min_samples_leaf": [10], "class_weight": ["balanced"]},
            ),
            "GradientBoosting": (
                GradientBoostingClassifier(random_state=preprocessing.SEED),
                {"n_estimators": [50], "learning_rate": [0.1], "max_depth": [3]},
            ),
        }
    return {
        "Dummy": (DummyClassifier(strategy="prior"), {}),
        "LogisticRegression": (
            LogisticRegression(max_iter=2000, random_state=preprocessing.SEED),
            {"C": [0.01, 0.1, 1, 10], "class_weight": [None, "balanced"]},
        ),
        "RandomForest": (
            RandomForestClassifier(n_estimators=300, random_state=preprocessing.SEED, n_jobs=1),
            {"max_depth": [6, 10, None], "min_samples_leaf": [1, 5, 10], "class_weight": [None, "balanced"]},
        ),
        "GradientBoosting": (
            GradientBoostingClassifier(random_state=preprocessing.SEED),
            {"n_estimators": [100, 200], "learning_rate": [0.05, 0.1], "max_depth": [2, 3]},
        ),
    }


def make_pipeline(estimator):
    """Pipeline = tiền xử lý + mô hình. Tiền xử lý chỉ fit trên dữ liệu train của từng fold."""
    return Pipeline([("prep", preprocessing.build_preprocessor()), ("model", estimator)])


def apply_params(pipeline, best_params):
    tuned = clone(pipeline)
    if best_params:
        tuned.set_params(**{"model__" + key: value for key, value in best_params.items()})
    return tuned


def search_best_params(name, pipeline, grid, X_train, y_train, cv, n_jobs):
    """Tìm tham số tốt nhất bằng PR-AUC trong CV (chỉ trên train). Trả về (tham số, bảng các tổ hợp)."""
    if not grid:
        return {}, []

    param_grid = {"model__" + key: values for key, values in grid.items()}
    search = GridSearchCV(
        pipeline, param_grid, scoring="average_precision", cv=cv, n_jobs=n_jobs, refit=False
    )
    search.fit(X_train, y_train)

    results = pd.DataFrame(search.cv_results_)
    best_row = results.sort_values("rank_test_score").iloc[0]
    best_params = {key[len("model__"):]: value for key, value in best_row["params"].items()}

    grid_rows = []
    for _, row in results.iterrows():
        clean_params = {key[len("model__"):]: value for key, value in row["params"].items()}
        grid_rows.append({
            "Mô hình": DISPLAY_NAMES[name],
            "Tham số": json.dumps(clean_params, ensure_ascii=False, default=str),
            "PR-AUC CV (trung bình 5 fold)": round(float(row["mean_test_score"]), 4),
            "Độ lệch chuẩn giữa các fold": round(float(row["std_test_score"]), 4),
            "Hạng": int(row["rank_test_score"]),
        })
    return best_params, grid_rows


def out_of_fold_scores(estimator, X_train, y_train, cv):
    """Điểm xác suất out-of-fold: mỗi khách được chấm bởi mô hình KHÔNG thấy khách đó lúc học.
    Trả về (mảng xác suất, PR-AUC từng fold)."""
    out_of_fold = np.zeros(len(y_train))
    fold_scores = []
    for train_index, valid_index in cv.split(X_train, y_train):
        fold_model = clone(estimator)
        fold_model.fit(X_train.iloc[train_index], y_train.iloc[train_index])
        fold_probability = fold_model.predict_proba(X_train.iloc[valid_index])[:, 1]
        out_of_fold[valid_index] = fold_probability
        fold_scores.append(average_precision_score(y_train.iloc[valid_index], fold_probability))
    return out_of_fold, np.array(fold_scores)


def choose_thresholds(y_train, out_of_fold):
    """Chọn ngưỡng Medium và High từ điểm out-of-fold. Mỗi ngưỡng: (ngưỡng, precision, recall) hoặc None."""
    medium = evaluate.select_threshold_for_recall(y_train, out_of_fold, MIN_RECALL_MEDIUM)
    high = evaluate.select_threshold_for_precision(
        y_train, out_of_fold, MIN_PRECISION_HIGH, MIN_FLAGGED_HIGH
    )
    return medium, high


# ---------------------------------------------------------------
# 2. Hàm phụ ghi file
# ---------------------------------------------------------------

def to_builtin(value):
    """Đổi kiểu numpy sang kiểu Python thường để ghi JSON."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.ndarray,)):
        return value.tolist()
    return str(value)


def save_table(table, folder, file_name):
    folder.mkdir(parents=True, exist_ok=True)
    table.to_csv(folder / file_name, index=False, encoding="utf-8-sig")
    print("  đã ghi", folder / file_name)


def library_versions_text():
    """Chuỗi phiên bản thư viện (ModelVersions.LibVersions là varchar(500))."""
    return ";".join([
        "python=" + platform.python_version(),
        "scikit-learn=" + sklearn.__version__,
        "pandas=" + pd.__version__,
        "numpy=" + np.__version__,
        "joblib=" + joblib.__version__,
    ])


def parse_arguments():
    parser = argparse.ArgumentParser(description="Huấn luyện mô hình churn (Mức 1)")
    parser.add_argument("--quick", action="store_true", help="lưới rất nhỏ để kiểm lỗi, ghi vào ml/_quick")
    parser.add_argument("--n-jobs", type=int, default=-1, help="số tiến trình cho GridSearchCV (mặc định: tất cả lõi)")
    return parser.parse_args()


# ---------------------------------------------------------------
# 3. Chương trình chính
# ---------------------------------------------------------------

def main():
    arguments = parse_arguments()
    started_at = time.time()

    output_root = PROJECT_ROOT / "ml" / ("_quick" if arguments.quick else "")
    metrics_folder = output_root / "results" / "metrics"
    predictions_folder = output_root / "results" / "predictions"
    models_folder = output_root / "models"
    models_folder.mkdir(parents=True, exist_ok=True)

    print("Chế độ        :", "THỬ NHANH (--quick), ghi vào " + str(output_root) if arguments.quick else "ĐẦY ĐỦ")
    print("Thư viện      :", library_versions_text())

    if not RAW_FILE.exists():
        print("Chưa có file dữ liệu:", RAW_FILE)
        print("Chạy etl\\download_telco.py trước.")
        return

    # --- Bước 1: dữ liệu và chia train/test ---
    features, target, customer_ids = preprocessing.load_raw_data(RAW_FILE)
    X_train, X_test, y_train, y_test = preprocessing.split_train_test(features, target)
    assert set(X_train.index).isdisjoint(set(X_test.index)), "train và test bị trùng khách"
    dataset_hash = preprocessing.sha256_of_file(RAW_FILE)
    print("Bước 1: dữ liệu", len(features), "khách; train", len(X_train), "| test", len(X_test),
          "| tỷ lệ churn train", round(y_train.mean(), 4), "| test", round(y_test.mean(), 4))
    print("        SHA-256 CSV:", dataset_hash)

    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=preprocessing.SEED)
    spaces = make_search_spaces(arguments.quick)

    # --- Bước 2: với mỗi mô hình, tìm tham số, tính điểm out-of-fold, chọn ngưỡng ---
    per_model = {}
    all_grid_rows = []
    for key in MODEL_KEYS:
        estimator, grid = spaces[key]
        print("\nBước 2:", DISPLAY_NAMES[key])
        step_start = time.time()
        pipeline = make_pipeline(estimator)

        best_params, grid_rows = search_best_params(key, pipeline, grid, X_train, y_train, cv, arguments.n_jobs)
        all_grid_rows.extend(grid_rows)
        tuned = apply_params(pipeline, best_params)

        out_of_fold, fold_scores = out_of_fold_scores(tuned, X_train, y_train, cv)
        if key == "Dummy":
            # Dummy cho điểm hằng số nên chọn ngưỡng là vô nghĩa; dùng ngưỡng 0,5 như mốc (dự đoán mọi khách Ở LẠI)
            medium, high = None, None
        else:
            medium, high = choose_thresholds(y_train, out_of_fold)

        per_model[key] = {
            "pipeline": tuned,
            "best_params": best_params,
            "out_of_fold": out_of_fold,
            "cv_pr_mean": float(fold_scores.mean()),
            "cv_pr_std": float(fold_scores.std(ddof=1)),
            "medium": medium,
            "high": high,
        }
        print("  tham số tốt nhất:", best_params)
        print("  PR-AUC CV: %.4f (độ lệch chuẩn giữa fold %.4f)" % (
            per_model[key]["cv_pr_mean"], per_model[key]["cv_pr_std"]))
        print("  ngưỡng Medium:", None if medium is None else round(medium[0], 4),
              "| High:", None if high is None else round(high[0], 4),
              "| %.0f giây" % (time.time() - step_start))

    # --- Bước 3: chọn mô hình theo PR-AUC CV (không dùng test) ---
    ranked = sorted([k for k in MODEL_KEYS if k != "Dummy"], key=lambda k: -per_model[k]["cv_pr_mean"])
    best_key, runner_up_key = ranked[0], ranked[1]
    gap = per_model[best_key]["cv_pr_mean"] - per_model[runner_up_key]["cv_pr_mean"]
    best_std = per_model[best_key]["cv_pr_std"]
    if gap < best_std:
        selection_note = (
            "PR-AUC CV của " + DISPLAY_NAMES[best_key] + " hơn " + DISPLAY_NAMES[runner_up_key]
            + " %.4f, nhỏ hơn một độ lệch chuẩn giữa các fold (%.4f): chưa đủ cơ sở nói mô hình này hơn đáng kể." % (gap, best_std)
        )
    else:
        selection_note = (
            "PR-AUC CV của " + DISPLAY_NAMES[best_key] + " hơn " + DISPLAY_NAMES[runner_up_key]
            + " %.4f, lớn hơn một độ lệch chuẩn giữa các fold (%.4f)." % (gap, best_std)
        )
    print("\nBước 3: mô hình được chọn theo PR-AUC CV:", DISPLAY_NAMES[best_key])
    print("        ", selection_note)

    # --- Bước 4: kiểm calibration (so Brier của bản gốc và bản hiệu chuẩn sigmoid, cùng 5 fold) ---
    base_pipeline = per_model[best_key]["pipeline"]
    base_oof = per_model[best_key]["out_of_fold"]
    base_brier = float(brier_score_loss(y_train, base_oof))

    print("\nBước 4: kiểm calibration của", DISPLAY_NAMES[best_key], "(sigmoid, 5 fold)")
    calibrated_pipeline = CalibratedClassifierCV(estimator=clone(base_pipeline), method="sigmoid", cv=5)
    calibrated_oof, _ = out_of_fold_scores(calibrated_pipeline, X_train, y_train, cv)
    calibrated_brier = float(brier_score_loss(y_train, calibrated_oof))
    use_calibration = (base_brier - calibrated_brier) >= CALIBRATION_MIN_GAIN
    print("  Brier out-of-fold: bản gốc %.4f | bản hiệu chuẩn %.4f -> %s" % (
        base_brier, calibrated_brier, "DÙNG bản hiệu chuẩn" if use_calibration else "giữ bản gốc"))

    if use_calibration:
        selected_estimator = calibrated_pipeline
        selected_oof = calibrated_oof
        selected_label = DISPLAY_NAMES[best_key] + " + hiệu chuẩn sigmoid"
    else:
        selected_estimator = base_pipeline
        selected_oof = base_oof
        selected_label = DISPLAY_NAMES[best_key]

    # --- Bước 5: ngưỡng của mô hình được chọn (từ điểm out-of-fold của bản được chọn) ---
    selected_medium, selected_high = choose_thresholds(y_train, selected_oof)
    if selected_medium is None:
        raise RuntimeError("Không tìm được ngưỡng Medium đạt Recall >= " + str(MIN_RECALL_MEDIUM))
    thresholds_consistent = selected_high is not None and selected_high[0] > selected_medium[0]
    print("\nBước 5: ngưỡng của", selected_label)
    print("  Medium (Recall >= %.2f): %.4f (OOF precision %.3f, recall %.3f)" % (
        MIN_RECALL_MEDIUM, selected_medium[0], selected_medium[1], selected_medium[2]))
    if selected_high is None:
        print("  High: KHÔNG có ngưỡng đạt Precision >= %.2f với >= %d khách gắn cờ" % (
            MIN_PRECISION_HIGH, MIN_FLAGGED_HIGH))
    else:
        print("  High (Precision >= %.2f): %.4f (OOF precision %.3f, recall %.3f)" % (
            MIN_PRECISION_HIGH, selected_high[0], selected_high[1], selected_high[2]))
    if not thresholds_consistent:
        print("  CẢNH BÁO: High không lớn hơn Medium, phải xử lý tay trước khi seed RiskConfig.")

    # --- Bước 6: huấn luyện lại trên toàn bộ train, xem test MỘT lần ---
    print("\nBước 6: huấn luyện lại trên toàn bộ train và đánh giá test (xem một lần)")
    test_scores = {}
    fitted_models = {}
    for key in MODEL_KEYS:
        fitted = clone(per_model[key]["pipeline"]).fit(X_train, y_train)
        fitted_models[key] = fitted
        test_scores[key] = fitted.predict_proba(X_test)[:, 1]
    selected_fitted = clone(selected_estimator).fit(X_train, y_train)
    selected_test_score = selected_fitted.predict_proba(X_test)[:, 1]

    # --- Bảng kết quả ---
    cv_rows = []
    for key in MODEL_KEYS:
        information = per_model[key]
        oof_metrics = evaluate.compute_metrics(y_train, information["out_of_fold"], 0.5)
        cv_rows.append({
            "Mô hình": DISPLAY_NAMES[key],
            "Tham số tốt nhất": json.dumps(information["best_params"], ensure_ascii=False, default=str),
            "PR-AUC CV (trung bình 5 fold)": round(information["cv_pr_mean"], 4),
            "Độ lệch chuẩn giữa các fold": round(information["cv_pr_std"], 4),
            "ROC-AUC (out-of-fold)": round(oof_metrics["roc_auc"], 4),
            "F1 tại ngưỡng 0,5 (out-of-fold)": round(oof_metrics["f1"], 4),
            "Brier (out-of-fold)": round(oof_metrics["brier"], 4),
            "Ngưỡng Recall >= 0,75": None if information["medium"] is None else round(information["medium"][0], 4),
        })

    test_rows = []
    test_metrics_by_key = {}
    for key in MODEL_KEYS:
        medium = per_model[key]["medium"]
        threshold = medium[0] if medium is not None else 0.5
        metrics = evaluate.compute_metrics(y_test, test_scores[key], threshold)
        test_metrics_by_key[key] = metrics
        row = {
            "Mô hình": DISPLAY_NAMES[key],
            "Precision": round(metrics["precision"], 4), "Recall": round(metrics["recall"], 4),
            "F1": round(metrics["f1"], 4), "ROC-AUC": round(metrics["roc_auc"], 4),
            "PR-AUC": round(metrics["pr_auc"], 4), "Brier": round(metrics["brier"], 4),
            "Ngưỡng": round(threshold, 4),
            "TN": metrics["tn"], "FP": metrics["fp"], "FN": metrics["fn"], "TP": metrics["tp"],
            "Tỷ lệ khách bị gắn cờ": round(metrics["flagged_rate"], 4),
            "Được chọn": "Có" if (key == best_key and not use_calibration) else "",
        }
        for fraction in TOP_K_FRACTIONS:
            if key == "Dummy":
                # Dummy cho điểm hằng số nên thứ tự khách là tùy ý, coverage không có nghĩa: để trống
                row["Top %d%% coverage" % round(fraction * 100)] = None
            else:
                row["Top %d%% coverage" % round(fraction * 100)] = round(
                    evaluate.top_k_coverage(y_test, test_scores[key], fraction), 4)
        test_rows.append(row)

    if use_calibration:
        metrics = evaluate.compute_metrics(y_test, selected_test_score, selected_medium[0])
        row = {
            "Mô hình": selected_label,
            "Precision": round(metrics["precision"], 4), "Recall": round(metrics["recall"], 4),
            "F1": round(metrics["f1"], 4), "ROC-AUC": round(metrics["roc_auc"], 4),
            "PR-AUC": round(metrics["pr_auc"], 4), "Brier": round(metrics["brier"], 4),
            "Ngưỡng": round(selected_medium[0], 4),
            "TN": metrics["tn"], "FP": metrics["fp"], "FN": metrics["fn"], "TP": metrics["tp"],
            "Tỷ lệ khách bị gắn cờ": round(metrics["flagged_rate"], 4),
            "Được chọn": "Có",
        }
        for fraction in TOP_K_FRACTIONS:
            row["Top %d%% coverage" % round(fraction * 100)] = round(
                evaluate.top_k_coverage(y_test, selected_test_score, fraction), 4)
        test_rows.append(row)

    # Ngưỡng của mô hình được chọn: kết quả trên out-of-fold (lúc chọn) và trên test (xem một lần)
    threshold_rows = []
    confusion_rows = []
    for level_name, selection, rule_text in [
        ("Medium", selected_medium, "Recall >= %.2f trên điểm out-of-fold" % MIN_RECALL_MEDIUM),
        ("High", selected_high, "Precision >= %.2f trên điểm out-of-fold, gắn cờ >= %d khách" % (
            MIN_PRECISION_HIGH, MIN_FLAGGED_HIGH)),
    ]:
        if selection is None:
            threshold_rows.append({"Mức": level_name, "Quy tắc chọn": rule_text, "Ngưỡng": None})
            continue
        metrics = evaluate.compute_metrics(y_test, selected_test_score, selection[0])
        threshold_rows.append({
            "Mức": level_name, "Quy tắc chọn": rule_text, "Ngưỡng": round(selection[0], 4),
            "Precision (out-of-fold)": round(selection[1], 4), "Recall (out-of-fold)": round(selection[2], 4),
            "Precision (test)": round(metrics["precision"], 4), "Recall (test)": round(metrics["recall"], 4),
            "F1 (test)": round(metrics["f1"], 4), "Tỷ lệ khách bị gắn cờ (test)": round(metrics["flagged_rate"], 4),
        })
        confusion_rows.append({
            "Ngưỡng": level_name + " (" + format(selection[0], ".4f") + ")",
            "TN": metrics["tn"], "FP": metrics["fp"], "FN": metrics["fn"], "TP": metrics["tp"],
        })

    # --- Ghi kết quả ---
    print("\nGhi kết quả")
    save_table(pd.DataFrame(all_grid_rows), metrics_folder, "model_01_luoi_tham_so_cv.csv")
    save_table(pd.DataFrame(cv_rows), metrics_folder, "model_02_so_sanh_cv.csv")
    save_table(pd.DataFrame(test_rows), metrics_folder, "model_03_so_sanh_test.csv")
    save_table(pd.DataFrame(threshold_rows), metrics_folder, "model_04_nguong.csv")
    save_table(pd.DataFrame(confusion_rows), metrics_folder, "model_05_confusion_matrix.csv")

    oof_table = pd.DataFrame({"row_index": X_train.index, "customerID": customer_ids.loc[X_train.index].values,
                              "y_true": y_train.values})
    test_table = pd.DataFrame({"row_index": X_test.index, "customerID": customer_ids.loc[X_test.index].values,
                               "y_true": y_test.values})
    for key in MODEL_KEYS:
        oof_table[key] = per_model[key]["out_of_fold"]
        test_table[key] = test_scores[key]
    oof_table["selected"] = selected_oof
    test_table["selected"] = selected_test_score
    save_table(oof_table, predictions_folder, "oof_train.csv")
    save_table(test_table, predictions_folder, "test_scores.csv")

    model_path = models_folder / ("churn_pipeline_" + MODEL_VERSION + ".joblib")
    joblib.dump(selected_fitted, model_path)
    print("  đã ghi", model_path)

    selected_test_metrics = evaluate.compute_metrics(y_test, selected_test_score, selected_medium[0])
    metadata = {
        "model_name": selected_label,
        "model_key": best_key,
        "calibrated": bool(use_calibration),
        "version": MODEL_VERSION,
        "train_date": datetime.now().isoformat(timespec="seconds"),
        "seed": preprocessing.SEED,
        "threshold": selected_medium[0],
        "threshold_medium": selected_medium[0],
        "threshold_high": None if selected_high is None else selected_high[0],
        "thresholds_consistent": bool(thresholds_consistent),
        "feature_columns": preprocessing.FEATURE_COLUMNS,
        "numeric_columns": preprocessing.NUMERIC_COLUMNS,
        "categorical_columns": preprocessing.CATEGORICAL_COLUMNS,
        "best_params": per_model[best_key]["best_params"],
        "selection_note": selection_note,
        "metrics_cv": {
            "pr_auc_mean": per_model[best_key]["cv_pr_mean"],
            "pr_auc_std_between_folds": per_model[best_key]["cv_pr_std"],
            "brier_out_of_fold_base": base_brier,
            "brier_out_of_fold_calibrated": calibrated_brier,
        },
        "metrics_test": selected_test_metrics,
        "dataset": {"file": "Telco-Customer-Churn.csv", "sha256": dataset_hash, "rows": int(len(features)),
                    "train_rows": int(len(X_train)), "test_rows": int(len(X_test))},
        "protocol": {
            "test_size": preprocessing.TEST_SIZE, "stratify": True, "cv_folds": CV_FOLDS,
            "cv_shuffle": True, "scoring_for_selection": "average_precision",
            "min_recall_medium": MIN_RECALL_MEDIUM, "min_precision_high": MIN_PRECISION_HIGH,
            "min_flagged_high": MIN_FLAGGED_HIGH, "calibration_min_gain_brier": CALIBRATION_MIN_GAIN,
            "searched_grids": {k: spaces[k][1] for k in MODEL_KEYS},
        },
        "library_versions": library_versions_text(),
        "note": "Dữ liệu IBM Telco là dữ liệu mẫu. Điểm chỉ hỗ trợ chăm sóc khách hàng, không phải quan hệ nhân quả.",
    }
    metadata_path = models_folder / ("churn_model_meta_" + MODEL_VERSION + ".json")
    with open(metadata_path, "w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2, default=to_builtin)
    print("  đã ghi", metadata_path)

    # --- Tóm tắt ---
    print("\n=== TÓM TẮT ===")
    print(pd.DataFrame(cv_rows)[["Mô hình", "PR-AUC CV (trung bình 5 fold)", "Độ lệch chuẩn giữa các fold",
                                  "ROC-AUC (out-of-fold)", "Brier (out-of-fold)"]].to_string(index=False))
    print()
    print(pd.DataFrame(test_rows)[["Mô hình", "Precision", "Recall", "F1", "ROC-AUC", "PR-AUC", "Brier",
                                    "Ngưỡng", "Được chọn"]].to_string(index=False))
    print("\nMô hình được chọn:", selected_label)
    print("Tổng thời gian: %.0f giây" % (time.time() - started_at))


if __name__ == "__main__":
    main()
