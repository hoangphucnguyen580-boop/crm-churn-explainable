using System.ComponentModel.DataAnnotations;
using System.Globalization;

namespace CrmChurn.Web.Models;

public class ContractChangeViewModel
{
    // Id dòng hợp đồng đang hiệu lực LÚC MỞ FORM, dùng để phát hiện có người khác vừa đổi (UC-08, 5b)
    public long HopDongId { get; set; }

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

    // Nhập dạng chữ để đọc được cả "29.85" lẫn "29,85"
    [Required(ErrorMessage = "Nhập mức phí hằng tháng")]
    public string? MonthlyChargesText { get; set; }

    // Điền sẵn form từ dòng hợp đồng đang hiệu lực
    public static ContractChangeViewModel TuHopDong(CustomerContract hd)
    {
        return new ContractChangeViewModel
        {
            HopDongId = hd.ContractRecordId,
            PhoneService = hd.PhoneService,
            MultipleLines = hd.MultipleLines,
            InternetService = hd.InternetService,
            OnlineSecurity = hd.OnlineSecurity,
            OnlineBackup = hd.OnlineBackup,
            DeviceProtection = hd.DeviceProtection,
            TechSupport = hd.TechSupport,
            StreamingTv = hd.StreamingTv,
            StreamingMovies = hd.StreamingMovies,
            Contract = hd.Contract,
            PaperlessBilling = hd.PaperlessBilling,
            PaymentMethod = hd.PaymentMethod,
            MonthlyChargesText = hd.MonthlyCharges.ToString("0.00", CultureInfo.InvariantCulture)
        };
    }

    // Kiểm giá trị trong danh sách, mức phí đọc được, nhất quán giữa các cột (BR-15).
    // Mượn CustomerCreateViewModel làm bộ kiểm: chỉ điền các trường dịch vụ, Gender để trống (bị bỏ qua).
    public List<(string Truong, string NoiDung)> KiemTraNghiepVu(out decimal mucPhi)
    {
        var boKiem = new CustomerCreateViewModel
        {
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
        return boKiem.KiemTraNghiepVu(out mucPhi);
    }

    // Có ít nhất một trường khác dòng hợp đồng hiện tại không? (UC-08, 4a)
    public bool KhacHopDong(CustomerContract hd, decimal mucPhi)
    {
        return PhoneService != hd.PhoneService
            || MultipleLines != hd.MultipleLines
            || InternetService != hd.InternetService
            || OnlineSecurity != hd.OnlineSecurity
            || OnlineBackup != hd.OnlineBackup
            || DeviceProtection != hd.DeviceProtection
            || TechSupport != hd.TechSupport
            || StreamingTv != hd.StreamingTv
            || StreamingMovies != hd.StreamingMovies
            || Contract != hd.Contract
            || PaperlessBilling != hd.PaperlessBilling
            || PaymentMethod != hd.PaymentMethod
            || mucPhi != hd.MonthlyCharges;
    }
}