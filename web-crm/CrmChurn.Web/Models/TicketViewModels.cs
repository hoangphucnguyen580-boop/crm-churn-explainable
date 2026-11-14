using System.ComponentModel.DataAnnotations;

namespace CrmChurn.Web.Models;

// Giá trị hợp lệ của ticket: khớp CHECK trong database (Category, Priority, Status)
public static class DanhMucTicket
{
    public static readonly string[] Loai = { "Billing", "Technical", "Service" };
    public static readonly string[] UuTien = { "Low", "Medium", "High" };
    public static readonly string[] TrangThai = { "Open", "InProgress", "Closed" };

    public const string Open = "Open";
    public const string InProgress = "InProgress";
    public const string Closed = "Closed";

    public const int KetQuaToiDa = 1000;     // Tickets.Resolution là nvarchar(1000)
    public const int LyDoMoLaiToiDa = 500;   // Tickets.ReopenReason là nvarchar(500)
}

// Hàm hiển thị dùng chung cho các View của ticket
public static class HienThiTicket
{
    // Lớp CSS của Bootstrap cho huy hiệu trạng thái
    public static string LopTrangThai(string? trangThai)
    {
        return trangThai switch
        {
            "Open" => "bg-primary",
            "InProgress" => "bg-warning text-dark",
            "Closed" => "bg-success",
            _ => "bg-secondary"
        };
    }

    public static string LopUuTien(string? uuTien)
    {
        return uuTien switch
        {
            "High" => "bg-danger",
            "Medium" => "bg-warning text-dark",
            _ => "bg-secondary"
        };
    }

    // Thời gian xử lý = ClosedAt trừ CreatedAt (FR-27). Chưa đóng thì trả về dấu gạch.
    public static string ThoiGianXuLy(DateTime taoLuc, DateTime? dongLuc)
    {
        if (!dongLuc.HasValue) return "—";
        TimeSpan khoang = dongLuc.Value - taoLuc;
        if (khoang.TotalMinutes < 1) return "dưới 1 phút";
        if (khoang.TotalHours < 1) return ((int)khoang.TotalMinutes) + " phút";
        if (khoang.TotalDays < 1) return ((int)khoang.TotalHours) + " giờ " + khoang.Minutes + " phút";
        return ((int)khoang.TotalDays) + " ngày " + khoang.Hours + " giờ";
    }
}

// Một nhân viên trong ô chọn: CHỈ lấy mã và tên, không bao giờ nạp cả entity Staff (có PasswordHash)
public class StaffOption
{
    public int StaffId { get; set; }
    public string FullName { get; set; } = "";
}

// ---------- Form mở ticket ----------
public class TicketCreateModel
{
    [Required(ErrorMessage = "Nhập mã khách")]
    [StringLength(20, ErrorMessage = "Mã khách tối đa 20 ký tự")]
    public string? CustomerId { get; set; }

    [Required(ErrorMessage = "Chọn loại ticket")]
    public string? Category { get; set; }

    [Required(ErrorMessage = "Chọn mức ưu tiên")]
    public string? Priority { get; set; }

    // Bảng Tickets có CHECK cho hai cột này, nhưng kiểm ở web để báo lỗi thân thiện
    public List<(string Truong, string NoiDung)> KiemTraNghiepVu()
    {
        var loi = new List<(string, string)>();
        if (Category != null && !DanhMucTicket.Loai.Contains(Category))
            loi.Add((nameof(Category), "Loại ticket không hợp lệ."));
        if (Priority != null && !DanhMucTicket.UuTien.Contains(Priority))
            loi.Add((nameof(Priority), "Mức ưu tiên không hợp lệ."));
        return loi;
    }
}

// ---------- Form đóng ticket ----------
public class TicketCloseModel
{
    // Trạng thái ticket LÚC MỞ FORM, để phát hiện người khác vừa đổi (UC-09, 4a)
    public string? TrangThaiLucMo { get; set; }

    [Required(ErrorMessage = "Nhập kết quả giải quyết")]
    [StringLength(DanhMucTicket.KetQuaToiDa, ErrorMessage = "Kết quả giải quyết tối đa 1.000 ký tự")]
    public string? Resolution { get; set; }

    // Có thể để trống; có thì phải từ 1 đến 5
    [Range(1, 5, ErrorMessage = "Điểm hài lòng phải từ 1 đến 5")]
    public int? SatisfactionScore { get; set; }
}

// ---------- Form mở lại ticket ----------
public class TicketReopenModel
{
    public string? TrangThaiLucMo { get; set; }

    [Required(ErrorMessage = "Nhập lý do mở lại")]
    [StringLength(DanhMucTicket.LyDoMoLaiToiDa, ErrorMessage = "Lý do tối đa 500 ký tự")]
    public string? Reason { get; set; }
}

// ---------- Trang danh sách ----------
public class TicketListItem
{
    public long TicketId { get; set; }
    public string CustomerId { get; set; } = "";
    public string Category { get; set; } = "";
    public string Priority { get; set; } = "";
    public string Status { get; set; } = "";
    public DateTime CreatedAt { get; set; }
    public DateTime? ClosedAt { get; set; }
    public short? SatisfactionScore { get; set; }
    public string? AssignedName { get; set; }
    public bool IsSimulated { get; set; }
}

public class TicketListViewModel
{
    public List<TicketListItem> Items { get; set; } = new();
    public List<StaffOption> NhanVien { get; set; } = new();   // cho ô lọc theo người phụ trách

    // Giá trị bộ lọc hiện tại (để form và liên kết phân trang giữ nguyên)
    public string? CustomerId { get; set; }
    public string? Status { get; set; }
    public string? Priority { get; set; }
    public string? Staff { get; set; }   // "" = mọi người, "none" = chưa phân công, hoặc StaffID

    public int Page { get; set; } = 1;
    public int PageSize { get; set; } = 20;
    public int TongSoDong { get; set; }
    public int TongTrang => Math.Max(1, (int)Math.Ceiling(TongSoDong / (double)PageSize));
}

// ---------- Trang chi tiết (cũng dùng làm "tóm tắt" ở trang Đóng, Mở lại, Xóa) ----------
public class TicketDetailViewModel
{
    public long TicketId { get; set; }
    public string CustomerId { get; set; } = "";
    public string Category { get; set; } = "";
    public string Priority { get; set; } = "";
    public string Status { get; set; } = "";
    public DateTime CreatedAt { get; set; }
    public DateTime? ClosedAt { get; set; }
    public string? Resolution { get; set; }
    public short? SatisfactionScore { get; set; }
    public string? ReopenReason { get; set; }
    public bool IsSimulated { get; set; }
    public int? AssignedStaffId { get; set; }
    public string? AssignedName { get; set; }

    public List<StaffOption> NhanVien { get; set; } = new();   // chỉ nhân viên đang hoạt động
    public int? NguoiDangNhapId { get; set; }                  // để chọn sẵn "chính mình"
    public bool CoQuyenMoLai { get; set; }                     // Manager, Admin
    public bool CoQuyenXoa { get; set; }                       // Admin
}