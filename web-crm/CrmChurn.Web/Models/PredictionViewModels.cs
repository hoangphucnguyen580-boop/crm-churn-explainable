// ============================================================
// File: Models/PredictionViewModels.cs
// Mục đích: DTO gửi tới FastAPI (đúng 19 đặc trưng), form nhập thủ công và model các trang dự báo (UC-05)
// ============================================================
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.Text.Json.Serialization;

namespace CrmChurn.Web.Models;

// 19 đặc trưng gửi tới /predict. Tên JSON PHẢI đúng tên cột Telco (FastAPI dùng extra="forbid", sai tên là lỗi 422).
// Thứ tự khai báo = thứ tự trong JSON và trong InputJson lưu ở ChurnPredictions.
public class PredictFeatures
{
    [JsonPropertyName("SeniorCitizen")] public int SeniorCitizen { get; set; }          // số 0 hoặc 1
    [JsonPropertyName("tenure")] public int Tenure { get; set; }
    [JsonPropertyName("MonthlyCharges")] public decimal MonthlyCharges { get; set; }
    [JsonPropertyName("TotalCharges")] public decimal? TotalCharges { get; set; }       // null được phép (11 khách tenure = 0)

    [JsonPropertyName("gender")] public string Gender { get; set; } = "";
    [JsonPropertyName("Partner")] public string Partner { get; set; } = "";             // "Yes" hoặc "No", KHÔNG phải bit
    [JsonPropertyName("Dependents")] public string Dependents { get; set; } = "";
    [JsonPropertyName("PhoneService")] public string PhoneService { get; set; } = "";
    [JsonPropertyName("MultipleLines")] public string MultipleLines { get; set; } = "";
    [JsonPropertyName("InternetService")] public string InternetService { get; set; } = "";
    [JsonPropertyName("OnlineSecurity")] public string OnlineSecurity { get; set; } = "";
    [JsonPropertyName("OnlineBackup")] public string OnlineBackup { get; set; } = "";
    [JsonPropertyName("DeviceProtection")] public string DeviceProtection { get; set; } = "";
    [JsonPropertyName("TechSupport")] public string TechSupport { get; set; } = "";
    [JsonPropertyName("StreamingTV")] public string StreamingTv { get; set; } = "";
    [JsonPropertyName("StreamingMovies")] public string StreamingMovies { get; set; } = "";
    [JsonPropertyName("Contract")] public string Contract { get; set; } = "";
    [JsonPropertyName("PaperlessBilling")] public string PaperlessBilling { get; set; } = "";
    [JsonPropertyName("PaymentMethod")] public string PaymentMethod { get; set; } = "";
}

// ---------- Form nhập thủ công (FR-29) ----------
public class PredictionManualModel
{
    public bool SeniorCitizen { get; set; }
    public bool Partner { get; set; }
    public bool Dependents { get; set; }

    [Required(ErrorMessage = "Chọn giới tính")]
    public string? Gender { get; set; }

    [Required(ErrorMessage = "Nhập số tháng sử dụng (tenure)")]
    [Range(0, 120, ErrorMessage = "Số tháng sử dụng phải từ 0 đến 120")]
    public int? Tenure { get; set; }

    // Nhập dạng chữ để đọc được cả "29.85" lẫn "29,85"
    [Required(ErrorMessage = "Nhập mức phí hằng tháng")]
    public string? MonthlyChargesText { get; set; }

    // Có thể để trống (khách mới, tenure = 0): khi đó gửi null, pipeline điền trung vị
    public string? TotalChargesText { get; set; }

    [Required(ErrorMessage = "Chọn dịch vụ điện thoại")] public string? PhoneService { get; set; }
    [Required(ErrorMessage = "Chọn nhiều đường dây")] public string? MultipleLines { get; set; }
    [Required(ErrorMessage = "Chọn loại internet")] public string? InternetService { get; set; }
    [Required(ErrorMessage = "Chọn bảo mật trực tuyến")] public string? OnlineSecurity { get; set; }
    [Required(ErrorMessage = "Chọn sao lưu trực tuyến")] public string? OnlineBackup { get; set; }
    [Required(ErrorMessage = "Chọn bảo vệ thiết bị")] public string? DeviceProtection { get; set; }
    [Required(ErrorMessage = "Chọn hỗ trợ kỹ thuật")] public string? TechSupport { get; set; }
    [Required(ErrorMessage = "Chọn truyền hình trực tuyến")] public string? StreamingTv { get; set; }
    [Required(ErrorMessage = "Chọn phim trực tuyến")] public string? StreamingMovies { get; set; }
    [Required(ErrorMessage = "Chọn loại hợp đồng")] public string? Contract { get; set; }
    [Required(ErrorMessage = "Chọn hóa đơn điện tử")] public string? PaperlessBilling { get; set; }
    [Required(ErrorMessage = "Chọn phương thức thanh toán")] public string? PaymentMethod { get; set; }

    // Kiểm danh sách giá trị + BR-15 + mức phí bằng cách MƯỢN bộ kiểm của form thêm khách (không viết lại luật).
    // Nếu không có lỗi thì trả thêm đối tượng đặc trưng sẵn sàng gửi API (dacTrung != null).
    public List<(string Truong, string NoiDung)> KiemTraNghiepVu(out PredictFeatures? dacTrung)
    {
        dacTrung = null;

        var boKiem = new CustomerCreateViewModel
        {
            Gender = Gender,
            PhoneService = PhoneService,
            MultipleLines = MultipleLines,
            InternetService = InternetService,
            OnlineSecurity = OnlineSecurity,
            OnlineBackup = OnlineBackup,
            DeviceProtection = DeviceProtection,
            TechSupport = TechSupport,
            StreamingTv = StreamingTv,
            StreamingMovies = StreamingMovies,
            Contract = Contract,
            PaperlessBilling = PaperlessBilling,
            PaymentMethod = PaymentMethod,
            MonthlyChargesText = MonthlyChargesText
        };
        List<(string Truong, string NoiDung)> loi = boKiem.KiemTraNghiepVu(out decimal mucPhi);

        // Tổng phí: không bắt buộc; có thì phải là số từ 0 đến 99.999.999,99 (tối đa 2 chữ số thập phân)
        decimal? tongPhi = null;
        if (!string.IsNullOrWhiteSpace(TotalChargesText))
        {
            string chu = TotalChargesText.Trim().Replace(',', '.');
            bool docDuoc = decimal.TryParse(chu, NumberStyles.AllowDecimalPoint,
                                            CultureInfo.InvariantCulture, out decimal giaTri);
            if (!docDuoc || giaTri < 0 || giaTri > 99999999.99m || decimal.Round(giaTri, 2) != giaTri)
                loi.Add((nameof(TotalChargesText), "Tổng phí phải là số không âm, tối đa 2 chữ số thập phân (hoặc để trống)."));
            else
                tongPhi = giaTri;
        }

        // Còn lỗi, hoặc còn thiếu trường bắt buộc (Required sẽ báo riêng) thì chưa dựng đặc trưng
        string?[] cacChu = { Gender, PhoneService, MultipleLines, InternetService, OnlineSecurity, OnlineBackup,
                             DeviceProtection, TechSupport, StreamingTv, StreamingMovies, Contract,
                             PaperlessBilling, PaymentMethod, MonthlyChargesText };
        if (loi.Count > 0 || !Tenure.HasValue || cacChu.Any(x => x == null)) return loi;

        dacTrung = new PredictFeatures
        {
            SeniorCitizen = SeniorCitizen ? 1 : 0,
            Tenure = Tenure.Value,
            MonthlyCharges = mucPhi,
            TotalCharges = tongPhi,
            Gender = Gender!,
            Partner = Partner ? "Yes" : "No",
            Dependents = Dependents ? "Yes" : "No",
            PhoneService = PhoneService!,
            MultipleLines = MultipleLines!,
            InternetService = InternetService!,
            OnlineSecurity = OnlineSecurity!,
            OnlineBackup = OnlineBackup!,
            DeviceProtection = DeviceProtection!,
            TechSupport = TechSupport!,
            StreamingTv = StreamingTv!,
            StreamingMovies = StreamingMovies!,
            Contract = Contract!,
            PaperlessBilling = PaperlessBilling!,
            PaymentMethod = PaymentMethod!
        };
        return loi;
    }
}

// ---------- Trang đầu: chọn khách + 10 dự báo gần nhất ----------
public class PredictionHistoryRow
{
    public long PredictionId { get; set; }
    public string? CustomerId { get; set; }          // null = nhập thủ công
    public DateTime PredictionTime { get; set; }
    public decimal Probability { get; set; }
    public string RiskLevel { get; set; } = "";
    public string ModelVersion { get; set; } = "";
}

public class PredictionIndexViewModel
{
    public List<PredictionHistoryRow> GanDay { get; set; } = new();
}

// ---------- Trang kết quả: đọc LẠI từ database sau khi đã lưu ----------
public class PredictionResultViewModel
{
    public long PredictionId { get; set; }
    public string? CustomerId { get; set; }
    public DateTime PredictionTime { get; set; }
    public decimal Probability { get; set; }
    public string RiskLevel { get; set; } = "";
    public string ModelName { get; set; } = "";
    public string ModelVersion { get; set; } = "";

    public List<AuditValueRow> DacTrung { get; set; } = new();   // 19 đặc trưng đã gửi (từ InputJson)

    // Hai số đo lúc gọi (chuỗi đã định dạng); null nếu mở lại trang sau đó (TempData đã hết)
    public string? ApiMs { get; set; }       // thời gian suy luận BÊN TRONG API (latency_ms)
    public string? TongMs { get; set; }      // thời gian toàn chuỗi gọi từ Web (gồm mạng)
}