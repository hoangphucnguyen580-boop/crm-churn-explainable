namespace CrmChurn.Web.Models;

// Nhóm tenure theo D-05 / FR-35: 0-6, 7-12, 13-24, 25-36, 37-48, 49-60, trên 60 tháng
public static class NhomTenure
{
    public static readonly (string Khoa, string Nhan, int Min, int Max)[] DanhSach =
    {
        ("0-6",   "0–6 tháng",     0,  6),
        ("7-12",  "7–12 tháng",    7,  12),
        ("13-24", "13–24 tháng",   13, 24),
        ("25-36", "25–36 tháng",   25, 36),
        ("37-48", "37–48 tháng",   37, 48),
        ("49-60", "49–60 tháng",   49, 60),
        ("60+",   "Trên 60 tháng", 61, int.MaxValue)
    };

    // Đổi số tháng sang nhãn nhóm để hiện trên màn hình
    public static string Nhan(int? tenure)
    {
        if (tenure == null) return "—";
        foreach (var nhom in DanhSach)
        {
            if (tenure.Value >= nhom.Min && tenure.Value <= nhom.Max) return nhom.Nhan;
        }
        return "—";
    }
}

// Hàm hiển thị dùng chung cho các View
public static class HienThi
{
    public static string Ngay(DateTime? ngay)
    {
        return ngay.HasValue ? ngay.Value.ToString("dd/MM/yyyy HH:mm") : "—";
    }

    public static string CoKhong(bool? giaTri)
    {
        if (giaTri == null) return "—";
        return giaTri.Value ? "Có" : "Không";
    }

    // Mức rủi ro lưu trong database là Low/Medium/High; trên màn hình dùng tiếng Việt
    public static string NhanRuiRo(string? mucRuiRo)
    {
        return mucRuiRo switch
        {
            "Low" => "Thấp",
            "Medium" => "Trung bình",
            "High" => "Cao",
            _ => "Chưa có dự báo"
        };
    }

    // Lớp CSS của Bootstrap cho huy hiệu mức rủi ro
    public static string LopRuiRo(string? mucRuiRo)
    {
        return mucRuiRo switch
        {
            "Low" => "bg-success",
            "Medium" => "bg-warning text-dark",
            "High" => "bg-danger",
            _ => "bg-secondary"
        };
    }
}

// ---------- Trang danh sách ----------

public class CustomerListItem
{
    public string CustomerId { get; set; } = "";
    public string CustomerStatus { get; set; } = "";
    public string? Contract { get; set; }      // hợp đồng đang hiệu lực
    public int? Tenure { get; set; }
    public string? RiskLevel { get; set; }     // mức rủi ro của dự báo gần nhất
}

public class CustomerListViewModel
{
    public List<CustomerListItem> Items { get; set; } = new();

    // Giá trị bộ lọc hiện tại (để form và các liên kết phân trang giữ nguyên)
    public string? Q { get; set; }
    public string? Contract { get; set; }
    public string? TenureGroup { get; set; }
    public string? Risk { get; set; }

    public int Page { get; set; } = 1;
    public int PageSize { get; set; } = 20;
    public int TongSoKhach { get; set; }
    public int TongTrang => Math.Max(1, (int)Math.Ceiling(TongSoKhach / (double)PageSize));

    // Danh sách giá trị hợp lệ của bộ lọc (khớp dữ liệu Telco)
    public static readonly string[] CacHopDong = { "Month-to-month", "One year", "Two year" };
    public static readonly string[] CacMucRuiRo = { "Low", "Medium", "High" };
}

// ---------- Trang chi tiết ----------

public class InteractionRow
{
    public DateTime InteractionDate { get; set; }
    public string Channel { get; set; } = "";
    public string InteractionType { get; set; } = "";
    public string? Description { get; set; }
    public string? Result { get; set; }
    public string? StaffName { get; set; }
    public bool IsSimulated { get; set; }
}

public class TicketRow
{
    public long TicketId { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? ClosedAt { get; set; }
    public string Category { get; set; } = "";
    public string Priority { get; set; } = "";
    public string Status { get; set; } = "";
    public short? SatisfactionScore { get; set; }
    public string? AssignedName { get; set; }
    public bool IsSimulated { get; set; }
}

public class PredictionRow
{
    public DateTime PredictionTime { get; set; }
    public decimal Probability { get; set; }
    public string RiskLevel { get; set; } = "";
    public string ModelName { get; set; } = "";
    public string ModelVersion { get; set; } = "";
}

public class CustomerDetailViewModel
{
    public Customer Customer { get; set; } = null!;
    public int? Tenure { get; set; }

    // BR-04: mỗi khách đúng MỘT dòng hợp đồng đang hiệu lực; khác 1 là dữ liệu lỗi
    public int SoDongHopDongHieuLuc { get; set; }
    public CustomerContract? HopDong { get; set; }

    public PredictionRow? DuBaoGanNhat { get; set; }

    public List<InteractionRow> TuongTac { get; set; } = new();
    public int TongTuongTac { get; set; }

    public List<TicketRow> Tickets { get; set; } = new();
    public int TongTicket { get; set; }
}