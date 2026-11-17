// ============================================================
// File: Models/RiskConfigViewModels.cs
// Mục đích: Hằng số tên khóa ngưỡng, hàm đọc/gán mức rủi ro (BR-06) và model trang cấu hình ngưỡng (UC-10)
//           Dùng chung cho PredictionsController và RiskConfigController để hai nơi luôn cùng một luật.
// ============================================================
using System.Globalization;

namespace CrmChurn.Web.Models;

public static class NguongRuiRo
{
    public const string KhoaTrungBinh = "RiskMediumThreshold";
    public const string KhoaCao = "RiskHighThreshold";
    public const int SoChuSoThapPhan = 4;   // khớp ModelVersions.Threshold decimal(5,4) và giá trị đã nạp (0.3148)

    // Đọc hai chuỗi lấy từ RiskConfig. Trả về null nếu hợp lệ, ngược lại trả về lời báo lỗi (UC-05, 6a).
    public static string? DocHaiNguong(string? chuTrungBinh, string? chuCao, out decimal trungBinh, out decimal cao)
    {
        trungBinh = 0;
        cao = 0;

        if (chuTrungBinh == null || chuCao == null)
        {
            return "Cấu hình ngưỡng rủi ro bị thiếu khóa " + KhoaTrungBinh + " hoặc " + KhoaCao + ". Hãy báo quản trị viên.";
        }

        bool docTb = decimal.TryParse(chuTrungBinh, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out trungBinh);
        bool docCao = decimal.TryParse(chuCao, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out cao);
        if (!docTb || !docCao)
        {
            return "Giá trị ngưỡng trong cấu hình không phải số. Hãy báo quản trị viên.";
        }

        // Cần 0 <= Medium < High <= 1
        if (trungBinh < 0 || cao > 1 || trungBinh >= cao)
        {
            return "Ngưỡng rủi ro trong cấu hình không hợp lệ (cần 0 ≤ Medium < High ≤ 1). Hãy báo quản trị viên.";
        }
        return null;
    }

    // BR-06: High nếu xác suất >= High; Medium nếu >= Medium; còn lại Low
    public static string GanMuc(decimal xacSuat, decimal trungBinh, decimal cao)
    {
        if (xacSuat >= cao) return "High";
        if (xacSuat >= trungBinh) return "Medium";
        return "Low";
    }

    // Đọc ngưỡng người dùng gõ vào form: chấp nhận "0,3148" lẫn "0.3148"; từ 0 đến 1; tối đa 4 chữ số thập phân
    public static bool TryDocTuForm(string? chu, out decimal giaTri)
    {
        giaTri = 0;
        if (string.IsNullOrWhiteSpace(chu)) return false;

        string sach = chu.Trim().Replace(',', '.');
        if (!decimal.TryParse(sach, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out giaTri)) return false;

        return giaTri >= 0 && giaTri <= 1 && decimal.Round(giaTri, SoChuSoThapPhan) == giaTri;
    }
}

// Model trang cấu hình ngưỡng. MediumText và HighText là hai ô nhập; các trường còn lại chỉ để hiển thị.
public class RiskConfigViewModel
{
    public string? MediumText { get; set; }
    public string? HighText { get; set; }

    public DateTime? CapNhatLuc { get; set; }
    public string? CapNhatBoi { get; set; }

    // Có giá trị nghĩa là thiếu khóa trong RiskConfig: View chỉ hiện lời báo, không hiện form
    public string? ThongBaoThieuKhoa { get; set; }
}