"""
Dịch vụ FastAPI dự báo churn (đề tài 18, Mức 1, P4 bước D3).

Hai điểm vào:
  GET  /health   -> {status, model_version, model_name, feature_count}
  POST /predict  -> {churn_probability, model_version, latency_ms}

Quy tắc đã cài vào code:
  - API chỉ trả XÁC SUẤT. KHÔNG trả mức Low/Medium/High và KHÔNG có ngưỡng nào trong file này:
    mức risk do web gán theo bảng RiskConfig (R-04, D-06). Mẫu code của cô hard-code 0,70/0,40,
    đề cương cấm hard-code ngưỡng nên không làm theo chỗ đó.
  - Nhận ĐÚNG 19 đặc trưng Telco (preprocessing.FEATURE_COLUMNS). Thiếu cột, thừa cột
    (ví dụ customerID, Churn, ChurnLabel) hoặc giá trị phân loại lạ (ví dụ Partner = 1)
    đều bị trả lỗi 422, không dự báo âm thầm (kế hoạch Mục 12, D-04).
  - TotalCharges bắt buộc có mặt nhưng được phép là null (11 khách tenure = 0); pipeline điền trung vị.
  - API KHÔNG đọc và KHÔNG ghi database. Việc ghi ChurnPredictions do web làm.
  - Chỉ nạp file .joblib do chính mình tạo (tài liệu scikit-learn nêu giới hạn bảo mật của pickle/joblib).
  - Chạy trên 127.0.0.1, chỉ cho web ở cùng máy gọi (cô không yêu cầu xác thực cho API).
  - latency_ms là thời gian suy luận bên trong API (tạo DataFrame + predict_proba), KHÔNG gồm
    thời gian mạng và web. Web vẫn đo toàn chuỗi bằng Stopwatch (kế hoạch Mục 7.4).

Chạy:   python ml-api\\main.py
   hoặc: cd ml-api  rồi  uvicorn main:app --host 127.0.0.1 --port 8000
Cần:    pip install fastapi uvicorn   (cùng môi trường đã cài pandas, scikit-learn, joblib)
Xem tài liệu tự sinh của FastAPI: http://127.0.0.1:8000/docs
Đặt file này ở:  <thư mục dự án>/ml-api/main.py
"""

import json
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

import joblib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# preprocessing.py nằm ở ml/src; dùng chung để web và mô hình thống nhất tên 19 cột
sys.path.insert(0, str(PROJECT_ROOT / "ml" / "src"))
import preprocessing  # noqa: E402  (phải import sau khi thêm đường dẫn)

MODEL_VERSION = "v1"
MODELS_FOLDER = PROJECT_ROOT / "ml" / "models"
MODEL_FILE = MODELS_FOLDER / ("churn_pipeline_" + MODEL_VERSION + ".joblib")
META_FILE = MODELS_FOLDER / ("churn_model_meta_" + MODEL_VERSION + ".json")

# Các giá trị phân loại hợp lệ của Telco (đã kiểm ở data_quality.py và load_telco.py)
YesNo = Literal["Yes", "No"]
YesNoNoInternet = Literal["Yes", "No", "No internet service"]


# ---------------------------------------------------------------
# 1. Khuôn dữ liệu vào và ra
# ---------------------------------------------------------------

class CustomerFeatures(BaseModel):
    """19 đặc trưng gửi tới /predict. Tên cột đúng như CSV Telco."""

    # extra="forbid": gửi thừa cột (customerID, Churn, ...) là lỗi 422
    model_config = ConfigDict(extra="forbid")

    # --- 4 cột số ---
    SeniorCitizen: Literal[0, 1]
    tenure: int = Field(ge=0)
    MonthlyCharges: float = Field(ge=0)
    TotalCharges: Optional[float] = Field(ge=0)  # bắt buộc có mặt, được phép null

    # --- 15 cột phân loại ---
    gender: Literal["Male", "Female"]
    Partner: YesNo
    Dependents: YesNo
    PhoneService: YesNo
    MultipleLines: Literal["Yes", "No", "No phone service"]
    InternetService: Literal["DSL", "Fiber optic", "No"]
    OnlineSecurity: YesNoNoInternet
    OnlineBackup: YesNoNoInternet
    DeviceProtection: YesNoNoInternet
    TechSupport: YesNoNoInternet
    StreamingTV: YesNoNoInternet
    StreamingMovies: YesNoNoInternet
    Contract: Literal["Month-to-month", "One year", "Two year"]
    PaperlessBilling: YesNo
    PaymentMethod: Literal[
        "Electronic check", "Mailed check",
        "Bank transfer (automatic)", "Credit card (automatic)",
    ]


class PredictionResult(BaseModel):
    """Kết quả /predict. Cố ý KHÔNG có mức risk (R-04)."""

    churn_probability: float
    model_version: str
    latency_ms: float


# ---------------------------------------------------------------
# 2. Nạp mô hình lúc khởi động
# ---------------------------------------------------------------

# Nơi giữ mô hình sau khi nạp (điền ở load_model)
MODEL_STATE = {}


def load_model():
    """Nạp pipeline và metadata. Thiếu file hoặc lệch cột thì dừng với thông báo rõ."""
    if not MODEL_FILE.exists():
        raise RuntimeError("Chưa có file mô hình " + str(MODEL_FILE) + ". Chạy ml\\src\\train.py trước.")
    if not META_FILE.exists():
        raise RuntimeError("Chưa có file metadata " + str(META_FILE) + ". Chạy ml\\src\\train.py trước.")

    with open(META_FILE, "r", encoding="utf-8") as file:
        meta = json.load(file)

    if meta.get("version") != MODEL_VERSION:
        raise RuntimeError(
            "Metadata ghi version " + str(meta.get("version")) + ", API đang kỳ vọng " + MODEL_VERSION
        )

    # Danh sách đặc trưng lúc huấn luyện phải đúng bằng danh sách API nhận
    if list(meta["feature_columns"]) != list(preprocessing.FEATURE_COLUMNS):
        raise RuntimeError("feature_columns trong metadata khác preprocessing.FEATURE_COLUMNS")
    if list(CustomerFeatures.model_fields.keys()) != list(preprocessing.FEATURE_COLUMNS):
        raise RuntimeError("Khuôn CustomerFeatures khác preprocessing.FEATURE_COLUMNS")

    MODEL_STATE["pipeline"] = joblib.load(MODEL_FILE)
    MODEL_STATE["meta"] = meta
    print("Đã nạp mô hình", meta.get("model_name"), meta.get("version"), "từ", MODEL_FILE)


@asynccontextmanager
async def lifespan(app):
    load_model()
    yield
    MODEL_STATE.clear()


app = FastAPI(
    title="CRM Churn - dịch vụ dự báo",
    description="Trả xác suất churn của một khách hàng. Chỉ hỗ trợ chăm sóc khách hàng, "
                "không phải quan hệ nhân quả và không dùng để tự động ra quyết định (R-02, R-07).",
    version=MODEL_VERSION,
    lifespan=lifespan,
)


# ---------------------------------------------------------------
# 3. Hai điểm vào
# ---------------------------------------------------------------

@app.get("/health")
def health():
    meta = MODEL_STATE["meta"]
    return {
        "status": "ok",
        "model_version": meta["version"],
        "model_name": meta["model_name"],
        "feature_count": len(preprocessing.FEATURE_COLUMNS),
    }


@app.post("/predict", response_model=PredictionResult)
def predict(features: CustomerFeatures):
    started_at = time.perf_counter()

    # Bước 1: một dòng dict -> DataFrame đúng 19 cột, đúng kiểu (dùng chung với lúc huấn luyện)
    record = features.model_dump()
    frame = preprocessing.records_to_frame([record])

    # Bước 2: pipeline gồm cả tiền xử lý lẫn mô hình, nên đưa thẳng DataFrame vào
    try:
        probability = float(MODEL_STATE["pipeline"].predict_proba(frame)[:, 1][0])
    except Exception as error:
        raise HTTPException(status_code=500, detail="Lỗi khi dự báo: " + str(error))

    elapsed_ms = (time.perf_counter() - started_at) * 1000

    # Bước 3: xác suất phải thuộc [0, 1]; ngoài khoảng là lỗi của mô hình, không trả đi tiếp
    if not (0.0 <= probability <= 1.0):
        raise HTTPException(status_code=500, detail="Xác suất ngoài [0, 1]: " + str(probability))

    return PredictionResult(
        churn_probability=probability,
        model_version=MODEL_STATE["meta"]["version"],
        latency_ms=round(elapsed_ms, 3),
    )


if __name__ == "__main__":
    import uvicorn

    # Chỉ bind 127.0.0.1: chỉ web chạy cùng máy gọi được
    uvicorn.run(app, host="127.0.0.1", port=8000)
