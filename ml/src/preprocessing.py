"""
Đọc dữ liệu IBM Telco và dựng bộ tiền xử lý (Pipeline) cho bài toán dự báo churn.

Module này dùng chung cho: train.py (huấn luyện), notebook 03 (phân tích kết quả)
và FastAPI /predict (bước sau). Danh sách 19 cột đặc trưng nằm MỘT chỗ ở đây,
nên web và mô hình luôn thống nhất tên cột.

Quy tắc (D-04, R-05):
  - Chỉ dùng cột gốc của file CSV Telco. KHÔNG dùng customerID, nhãn Churn làm đặc trưng,
    KHÔNG dùng dữ liệu mô phỏng Interactions/Tickets.
  - Điền thiếu, chuẩn hóa, one-hot đều nằm TRONG Pipeline, chỉ fit trên tập train.
"""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEED = 42
TEST_SIZE = 0.20

ID_COLUMN = "customerID"
TARGET_COLUMN = "Churn"

# 4 cột số (SeniorCitizen là 0/1, coi như số như hướng dẫn của cô)
NUMERIC_COLUMNS = ["SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges"]

# 15 cột phân loại (có cả Partner, Dependents dạng chữ Yes/No)
CATEGORICAL_COLUMNS = [
    "gender", "Partner", "Dependents", "PhoneService", "MultipleLines",
    "InternetService", "OnlineSecurity", "OnlineBackup", "DeviceProtection",
    "TechSupport", "StreamingTV", "StreamingMovies", "Contract",
    "PaperlessBilling", "PaymentMethod",
]

# 19 đặc trưng, đúng thứ tự này khi gửi JSON tới /predict
FEATURE_COLUMNS = NUMERIC_COLUMNS + CATEGORICAL_COLUMNS


def sha256_of_file(file_path):
    """Mã băm SHA-256 của file (lưu vào ModelVersions.DatasetHash để chứng minh cùng một bản dữ liệu)."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as file:
        while True:
            block = file.read(1024 * 1024)
            if not block:
                break
            hasher.update(block)
    return hasher.hexdigest()


def load_raw_data(csv_path):
    """Đọc CSV Telco gốc, trả về (features, target, customer_ids).

    - features: DataFrame đúng 19 cột FEATURE_COLUMNS (cột phân loại ở dạng object).
    - target  : Series 0/1 (Churn = Yes -> 1).
    - customer_ids: Series customerID, cùng chỉ số với features (chỉ để tra cứu, KHÔNG làm đặc trưng).
    """
    raw = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    data = raw.copy()
    for column_name in data.columns:
        data[column_name] = data[column_name].str.strip()

    missing_columns = [c for c in FEATURE_COLUMNS + [ID_COLUMN, TARGET_COLUMN] if c not in data.columns]
    if missing_columns:
        raise ValueError("CSV thiếu cột: " + str(missing_columns))

    data["SeniorCitizen"] = data["SeniorCitizen"].astype(int)
    data["tenure"] = data["tenure"].astype(int)
    data["MonthlyCharges"] = data["MonthlyCharges"].astype(float)

    # TotalCharges có ô trống (11 khách tenure = 0). errors="coerce" chỉ được phép biến ô TRỐNG thành NaN
    blank_count = int((data["TotalCharges"] == "").sum())
    data["TotalCharges"] = pd.to_numeric(data["TotalCharges"], errors="coerce")
    if int(data["TotalCharges"].isna().sum()) != blank_count:
        raise ValueError("Có ô TotalCharges lỗi ngoài ô trống")

    features = data[FEATURE_COLUMNS].copy()
    for column_name in CATEGORICAL_COLUMNS:
        features[column_name] = features[column_name].astype(object)

    target = (data[TARGET_COLUMN] == "Yes").astype(int)
    customer_ids = data[ID_COLUMN]
    return features, target, customer_ids


def split_train_test(features, target, seed=SEED, test_size=TEST_SIZE):
    """Chia 80/20 có stratify theo nhãn (cố định seed để tái lập, R-05)."""
    return train_test_split(features, target, test_size=test_size, stratify=target, random_state=seed)


def build_preprocessor():
    """Bộ tiền xử lý: số -> điền trung vị + chuẩn hóa; phân loại -> điền giá trị phổ biến + one-hot."""
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    return ColumnTransformer([
        ("num", numeric_pipeline, NUMERIC_COLUMNS),
        ("cat", categorical_pipeline, CATEGORICAL_COLUMNS),
    ])


def records_to_frame(records):
    """Biến danh sách dict (JSON gửi tới /predict) thành DataFrame đúng 19 cột, đúng kiểu.

    Dùng ở FastAPI: tránh lỗi âm thầm do web gửi sai tên cột hay kiểu dữ liệu.
    TotalCharges rỗng/None được chấp nhận (Pipeline sẽ điền trung vị).
    """
    frame = pd.DataFrame(records)
    missing_columns = [c for c in FEATURE_COLUMNS if c not in frame.columns]
    if missing_columns:
        raise ValueError("Thiếu đặc trưng: " + str(missing_columns))
    frame = frame[FEATURE_COLUMNS].copy()
    for column_name in NUMERIC_COLUMNS:
        frame[column_name] = pd.to_numeric(frame[column_name], errors="raise")
    for column_name in CATEGORICAL_COLUMNS:
        frame[column_name] = frame[column_name].astype(object)
    return frame
