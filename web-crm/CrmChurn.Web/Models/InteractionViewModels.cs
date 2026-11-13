using System.ComponentModel.DataAnnotations;

namespace CrmChurn.Web.Models;

// Giá trị hợp lệ của tương tác: khớp simulation_config.json và UC-03.
// Bảng Interactions KHÔNG có CHECK cho 3 cột này nên web phải tự kiểm.
public static class DanhMucTuongTac
{
    public static readonly string[] Kenh = { "Phone", "Email", "Chat", "Web" };
    public static readonly string[] Loai = { "Inquiry", "Support", "Complaint", "Renewal" };
    public static readonly string[] KetQua = { "Resolved", "Follow-up", "Escalated" };

    public const int MoTaToiDa = 1000;     // cột Description là nvarchar(1000)
    public const int DungSaiPhut = 5;      // cho phép giờ trình duyệt lệch giờ máy chủ tối đa 5 phút
}

// ---------- Form dùng chung cho Sửa; Ghi nhận kế thừa thêm CustomerId ----------
public class InteractionFormModel
{
    [Required(ErrorMessage = "Chọn kênh")]
    public string? Channel { get; set; }

    [Required(ErrorMessage = "Chọn loại tương tác")]
    public string? InteractionType { get; set; }

    // Có sẵn giờ hiện tại nhưng người dùng sửa được (UC-03, bước 4)
    [Required(ErrorMessage = "Nhập thời điểm tương tác")]
    public DateTime? InteractionDate { get; set; }

    [StringLength(DanhMucTuongTac.MoTaToiDa, ErrorMessage = "Mô tả tối đa 1.000 ký tự")]
    public string? Description { get; set; }

    // Cột Result cho phép NULL nên không bắt buộc
    public string? Result { get; set; }

    // Kiểm danh sách giá trị và thời điểm. ngayThamGia = EstimatedJoinDate của khách (có thể null).
    public List<(string Truong, string NoiDung)> KiemTraNghiepVu(DateTime? ngayThamGia)
    {
        var loi = new List<(string, string)>();

        if (Channel != null && !DanhMucTuongTac.Kenh.Contains(Channel))
            loi.Add((nameof(Channel), "Kênh không hợp lệ."));
        if (InteractionType != null && !DanhMucTuongTac.Loai.Contains(InteractionType))
            loi.Add((nameof(InteractionType), "Loại tương tác không hợp lệ."));
        if (Result != null && !DanhMucTuongTac.KetQua.Contains(Result))
            loi.Add((nameof(Result), "Kết quả không hợp lệ."));

        if (InteractionDate.HasValue)
        {
            DateTime gio = InteractionDate.Value;
            DateTime gioMay = DateTime.Now;

            if (gio > gioMay.AddMinutes(DanhMucTuongTac.DungSaiPhut))
            {
                loi.Add((nameof(InteractionDate), "Thời điểm không được ở tương lai."));
            }
            else if (ngayThamGia.HasValue && gio < ngayThamGia.Value)
            {
                loi.Add((nameof(InteractionDate),
                    "Thời điểm không được sớm hơn ngày tham gia ước lượng của khách ("
                    + ngayThamGia.Value.ToString("dd/MM/yyyy") + ")."));
            }
        }
        return loi;
    }
}

public class InteractionCreateModel : InteractionFormModel
{
    [Required(ErrorMessage = "Nhập mã khách")]
    [StringLength(20, ErrorMessage = "Mã khách tối đa 20 ký tự")]
    public string? CustomerId { get; set; }
}

// ---------- Trang danh sách ----------
public class InteractionListItem
{
    public long InteractionId { get; set; }
    public string CustomerId { get; set; } = "";
    public DateTime InteractionDate { get; set; }
    public string Channel { get; set; } = "";
    public string InteractionType { get; set; } = "";
    public string? Description { get; set; }
    public string? Result { get; set; }
    public string? StaffName { get; set; }
    public bool IsSimulated { get; set; }
}

public class InteractionListViewModel
{
    public List<InteractionListItem> Items { get; set; } = new();

    // Giá trị bộ lọc hiện tại (để form và liên kết phân trang giữ nguyên)
    public string? CustomerId { get; set; }
    public string? Type { get; set; }
    public string? Channel { get; set; }
    public DateTime? TuNgay { get; set; }
    public DateTime? DenNgay { get; set; }

    public int Page { get; set; } = 1;
    public int PageSize { get; set; } = 20;
    public int TongSoDong { get; set; }
    public int TongTrang => Math.Max(1, (int)Math.Ceiling(TongSoDong / (double)PageSize));

    public string? ThongBaoLoc { get; set; }   // ví dụ "từ ngày lớn hơn đến ngày"
}