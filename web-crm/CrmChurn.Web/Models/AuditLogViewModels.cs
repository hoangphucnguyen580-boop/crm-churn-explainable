using System.Text.Json;

namespace CrmChurn.Web.Models;

// Một cặp "tên cột - giá trị" đọc từ chuỗi JSON OldValues hoặc NewValues
public class AuditValueRow
{
    public string Cot { get; set; } = "";
    public string GiaTri { get; set; } = "";
}

// Một dòng so sánh cũ/mới ở trang chi tiết. null nghĩa là "bản ghi đó không có cột này".
public class AuditCompareRow
{
    public string Cot { get; set; } = "";
    public string? Cu { get; set; }
    public string? Moi { get; set; }
}

public static class NhatKyHienThi
{
    // Cột không bao giờ được hiện giá trị thật (R-06)
    private static readonly HashSet<string> CotBiChe =
        new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "PasswordHash" };

    public const string DauChe = "***";

    // Đọc chuỗi JSON thành danh sách (cột, giá trị).
    // - Chuỗi rỗng hoặc null: trả về danh sách rỗng (Insert không có giá trị cũ, Login/Logout không có gì)
    // - Chuỗi không phải JSON object: trả về null để nơi gọi biết là "không đọc được"
    public static List<AuditValueRow>? DocJson(string? json)
    {
        var ketQua = new List<AuditValueRow>();
        if (string.IsNullOrWhiteSpace(json))
        {
            return ketQua;
        }

        try
        {
            using JsonDocument tai = JsonDocument.Parse(json);
            if (tai.RootElement.ValueKind != JsonValueKind.Object)
            {
                return null;
            }

            foreach (JsonProperty thuocTinh in tai.RootElement.EnumerateObject())
            {
                string giaTri;
                if (CotBiChe.Contains(thuocTinh.Name))
                {
                    giaTri = DauChe;
                }
                else if (thuocTinh.Value.ValueKind == JsonValueKind.String)
                {
                    giaTri = thuocTinh.Value.GetString() ?? "";
                }
                else if (thuocTinh.Value.ValueKind == JsonValueKind.Null)
                {
                    giaTri = "NULL";
                }
                else
                {
                    giaTri = thuocTinh.Value.GetRawText();   // số, true/false
                }

                ketQua.Add(new AuditValueRow { Cot = thuocTinh.Name, GiaTri = giaTri });
            }
            return ketQua;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    // Nhãn và màu huy hiệu cho cột Hành động
    public static string NhanHanhDong(string action)
    {
        return action switch
        {
            "Insert" => "Thêm",
            "Update" => "Sửa",
            "Delete" => "Xóa",
            "Login" => "Đăng nhập",
            "Logout" => "Đăng xuất",
            _ => action
        };
    }

    public static string LopHanhDong(string action)
    {
        return action switch
        {
            "Insert" => "bg-success",
            "Update" => "bg-warning text-dark",
            "Delete" => "bg-danger",
            _ => "bg-secondary"
        };
    }

    // Nhật ký cần cả giây, nên không dùng HienThi.Ngay (chỉ đến phút)
    public static string NgayGio(DateTime ngay)
    {
        return ngay.ToString("dd/MM/yyyy HH:mm:ss");
    }
}

// ---------- Trang danh sách ----------
public class AuditLogListItem
{
    public long AuditId { get; set; }
    public DateTime OccurredAt { get; set; }
    public string StaffName { get; set; } = "";
    public string Username { get; set; } = "";
    public string Action { get; set; } = "";
    public string TableName { get; set; } = "";
    public string RecordKey { get; set; } = "";
    public string? CotThayDoi { get; set; }   // chỉ có ở dòng Update: tên các cột đã đổi
}

public class AuditLogListViewModel
{
    public List<AuditLogListItem> Items { get; set; } = new();
    public List<StaffOption> NhanVien { get; set; } = new();   // ô lọc theo người
    public List<string> CacBang { get; set; } = new();         // ô lọc theo bảng

    // Giá trị bộ lọc hiện tại (để form và liên kết phân trang giữ nguyên)
    public string? Staff { get; set; }
    public string? Table { get; set; }
    public DateTime? TuNgay { get; set; }
    public DateTime? DenNgay { get; set; }

    public int Page { get; set; } = 1;
    public int PageSize { get; set; } = 20;
    public int TongSoDong { get; set; }
    public int TongTrang => Math.Max(1, (int)Math.Ceiling(TongSoDong / (double)PageSize));

    public string? ThongBaoLoc { get; set; }
}

// ---------- Trang chi tiết ----------
public class AuditLogDetailViewModel
{
    public long AuditId { get; set; }
    public DateTime OccurredAt { get; set; }
    public string StaffName { get; set; } = "";
    public string Username { get; set; } = "";
    public string Action { get; set; } = "";
    public string TableName { get; set; } = "";
    public string RecordKey { get; set; } = "";

    public List<AuditCompareRow> Rows { get; set; } = new();
    public bool KhongDocDuocJson { get; set; }
}