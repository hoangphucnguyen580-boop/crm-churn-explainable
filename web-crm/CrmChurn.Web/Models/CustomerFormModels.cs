using System.ComponentModel.DataAnnotations;
using System.Globalization;

namespace CrmChurn.Web.Models;

// Giá trị hợp lệ: khớp load_telco.py và FastAPI (đã kiểm ở các bước trước)
public static class DanhMucTelco
{
    public static readonly string[] GioiTinh = { "Male", "Female" };
    public static readonly string[] YesNo = { "Yes", "No" };
    public static readonly string[] NhieuDuongDay = { "Yes", "No", "No phone service" };
    public static readonly string[] Internet = { "DSL", "Fiber optic", "No" };
    public static readonly string[] DichVuInternet = { "Yes", "No", "No internet service" };
    public static readonly string[] HopDong = { "Month-to-month", "One year", "Two year" };
    public static readonly string[] ThanhToan =
    {
        "Electronic check", "Mailed check", "Bank transfer (automatic)", "Credit card (automatic)"
    };

    public const string TrangThaiHoatDong = "Active";
    public const string TrangThaiNgung = "Inactive";   // xóa mềm: khách và lịch sử vẫn còn
}

// ---------- Form thêm khách (hồ sơ + hợp đồng ban đầu) ----------
public class CustomerCreateViewModel
{
    [Required(ErrorMessage = "Nhập mã khách")]
    [StringLength(20, ErrorMessage = "Mã khách tối đa 20 ký tự")]
    [RegularExpression(@"^[A-Za-z0-9\-]+$", ErrorMessage = "Mã khách chỉ gồm chữ, số và dấu gạch ngang")]
    public string? CustomerId { get; set; }

    [Required(ErrorMessage = "Chọn giới tính")]
    public string? Gender { get; set; }
    public bool SeniorCitizen { get; set; }
    public bool Partner { get; set; }
    public bool Dependents { get; set; }

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

    // Mức phí nhập dạng chữ để tự đọc cả "29.85" lẫn "29,85" (máy dùng định dạng số Việt Nam)
    [Required(ErrorMessage = "Nhập mức phí hằng tháng")]
    public string? MonthlyChargesText { get; set; }

    // Kiểm giá trị nằm trong danh sách, mức phí đọc được và nhất quán giữa các cột (BR-15).
    // Trả về danh sách (tên trường, lời báo); mucPhi là số đã đọc được.
    public List<(string Truong, string NoiDung)> KiemTraNghiepVu(out decimal mucPhi)
    {
        var loi = new List<(string, string)>();

        void KiemDanhSach(string truong, string? giaTri, string[] hopLe)
        {
            if (giaTri != null && !hopLe.Contains(giaTri)) loi.Add((truong, "Giá trị không hợp lệ."));
        }
        KiemDanhSach(nameof(Gender), Gender, DanhMucTelco.GioiTinh);
        KiemDanhSach(nameof(PhoneService), PhoneService, DanhMucTelco.YesNo);
        KiemDanhSach(nameof(MultipleLines), MultipleLines, DanhMucTelco.NhieuDuongDay);
        KiemDanhSach(nameof(InternetService), InternetService, DanhMucTelco.Internet);
        KiemDanhSach(nameof(OnlineSecurity), OnlineSecurity, DanhMucTelco.DichVuInternet);
        KiemDanhSach(nameof(OnlineBackup), OnlineBackup, DanhMucTelco.DichVuInternet);
        KiemDanhSach(nameof(DeviceProtection), DeviceProtection, DanhMucTelco.DichVuInternet);
        KiemDanhSach(nameof(TechSupport), TechSupport, DanhMucTelco.DichVuInternet);
        KiemDanhSach(nameof(StreamingTv), StreamingTv, DanhMucTelco.DichVuInternet);
        KiemDanhSach(nameof(StreamingMovies), StreamingMovies, DanhMucTelco.DichVuInternet);
        KiemDanhSach(nameof(Contract), Contract, DanhMucTelco.HopDong);
        KiemDanhSach(nameof(PaperlessBilling), PaperlessBilling, DanhMucTelco.YesNo);
        KiemDanhSach(nameof(PaymentMethod), PaymentMethod, DanhMucTelco.ThanhToan);

        // BR-15: dịch vụ điện thoại
        if (PhoneService == "No" && MultipleLines != null && MultipleLines != "No phone service")
            loi.Add((nameof(MultipleLines), "Không dùng dịch vụ điện thoại thì chọn \"No phone service\"."));
        if (PhoneService == "Yes" && MultipleLines == "No phone service")
            loi.Add((nameof(MultipleLines), "Có dịch vụ điện thoại thì chọn Yes hoặc No."));

        // BR-15: dịch vụ internet (6 dịch vụ đi kèm)
        var dichVuDiKem = new (string Truong, string? GiaTri)[]
        {
            (nameof(OnlineSecurity), OnlineSecurity), (nameof(OnlineBackup), OnlineBackup),
            (nameof(DeviceProtection), DeviceProtection), (nameof(TechSupport), TechSupport),
            (nameof(StreamingTv), StreamingTv), (nameof(StreamingMovies), StreamingMovies)
        };
        foreach (var dv in dichVuDiKem)
        {
            if (dv.GiaTri == null) continue;
            if (InternetService == "No" && dv.GiaTri != "No internet service")
                loi.Add((dv.Truong, "Không dùng internet thì chọn \"No internet service\"."));
            if (InternetService != null && InternetService != "No" && dv.GiaTri == "No internet service")
                loi.Add((dv.Truong, "Có internet thì chọn Yes hoặc No."));
        }

        // Mức phí: số từ 0 đến 9999,99, tối đa 2 chữ số thập phân (cột decimal(8,2))
        mucPhi = 0;
        if (!string.IsNullOrWhiteSpace(MonthlyChargesText))
        {
            string chu = MonthlyChargesText.Trim().Replace(',', '.');
            bool docDuoc = decimal.TryParse(chu, NumberStyles.AllowDecimalPoint,
                                            CultureInfo.InvariantCulture, out mucPhi);
            if (!docDuoc || mucPhi < 0 || mucPhi > 9999.99m || decimal.Round(mucPhi, 2) != mucPhi)
                loi.Add((nameof(MonthlyChargesText), "Mức phí phải là số từ 0 đến 9999,99 (tối đa 2 chữ số thập phân)."));
        }
        return loi;
    }
}

// ---------- Form sửa hồ sơ (CustomerID không sửa được) ----------
public class CustomerEditViewModel
{
    [Required(ErrorMessage = "Chọn giới tính")]
    public string? Gender { get; set; }
    public bool SeniorCitizen { get; set; }
    public bool Partner { get; set; }
    public bool Dependents { get; set; }
}