namespace CrmChurn.Web.Models;

public static class CsvImportConfig
{
    // Giới hạn tệp: chặn tệp quá lớn để request không treo (lưu từng dòng riêng nên chậm hơn lưu cả lô)
    public const int MaxBytes = 512 * 1024;
    public const int MaxRows = 1000;

    // Lưu lỗi liên tiếp quá số này thì dừng hẳn (ví dụ mất SQL Server), khỏi thử nốt hàng trăm dòng
    public const int MaxConsecutiveSaveFailures = 3;

    // 18 cột của tệp mẫu (UC-07): 5 cột hồ sơ + 12 cột dịch vụ/hợp đồng/thanh toán + MonthlyCharges
    public static readonly string[] CacCot =
    {
        "CustomerID", "Gender", "SeniorCitizen", "Partner", "Dependents",
        "PhoneService", "MultipleLines", "InternetService", "OnlineSecurity", "OnlineBackup",
        "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies",
        "Contract", "PaperlessBilling", "PaymentMethod", "MonthlyCharges"
    };
}

// Một dòng bị từ chối
public class CsvImportError
{
    public int Dong { get; set; }                 // số dòng trong tệp (dòng tiêu đề là dòng 1)
    public string CustomerId { get; set; } = "";
    public string LyDo { get; set; } = "";
}

public class CsvImportResult
{
    public int TongDong { get; set; }             // số dòng dữ liệu (không tính tiêu đề, dòng trống)
    public int ThanhCong { get; set; }
    public int ChuaXuLy { get; set; }             // dòng chưa xử lý vì phải dừng giữa chừng
    public List<CsvImportError> Loi { get; set; } = new();
    public int SoThatBai => Loi.Count;
}

// Model của trang Import: lúc mở trang KetQua = null
public class CsvImportPageViewModel
{
    public string? ThongBaoLoi { get; set; }      // lỗi làm từ chối CẢ tệp
    public CsvImportResult? KetQua { get; set; }
}