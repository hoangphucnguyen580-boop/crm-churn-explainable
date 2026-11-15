using CrmChurn.Web.Data;
using CrmChurn.Web.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Controllers;

// Chỉ Admin (R-11): Manager và Agent gõ URL sẽ ra trang "Không có quyền"
[Authorize(Roles = "Admin")]
public class AuditLogsController : Controller
{
    private const int KichThuocTrang = 20;

    private readonly CrmDbContext _db;
    private readonly ILogger<AuditLogsController> _logger;

    public AuditLogsController(CrmDbContext db, ILogger<AuditLogsController> logger)
    {
        _db = db;
        _logger = logger;
    }

    // ---------------------------------------------------------------
    // Danh sách: mới nhất trước, lọc theo người, bảng, khoảng ngày
    // ---------------------------------------------------------------
    [HttpGet]
    public async Task<IActionResult> Index(string? staff, string? table,
                                           DateTime? tuNgay, DateTime? denNgay, int page = 1)
    {
        if (page < 1) page = 1;

        var model = new AuditLogListViewModel
        {
            Staff = staff,
            Table = table,
            TuNgay = tuNgay?.Date,
            DenNgay = denNgay?.Date,
            Page = page,
            PageSize = KichThuocTrang
        };

        try
        {
            // Hai danh sách cho ô chọn: chỉ lấy mã và tên, KHÔNG nạp entity Staff (có PasswordHash)
            model.NhanVien = await _db.Staff.AsNoTracking()
                .OrderBy(s => s.FullName)
                .Select(s => new StaffOption { StaffId = s.StaffId, FullName = s.FullName })
                .ToListAsync();
            model.CacBang = await _db.AuditLogs.AsNoTracking()
                .Select(a => a.TableName)
                .Distinct()
                .OrderBy(t => t)
                .ToListAsync();

            // Khoảng ngày ngược: báo rõ, không hiện dòng nào (tránh hiểu nhầm là "không có dữ liệu")
            if (tuNgay.HasValue && denNgay.HasValue && tuNgay.Value.Date > denNgay.Value.Date)
            {
                model.ThongBaoLoc = "\"Từ ngày\" đang lớn hơn \"Đến ngày\". Hãy chọn lại khoảng thời gian.";
                return View(model);
            }

            IQueryable<AuditLog> query = _db.AuditLogs.AsNoTracking();

            if (int.TryParse(staff, out int maNhanVien))
            {
                query = query.Where(a => a.StaffId == maNhanVien);
            }
            if (!string.IsNullOrEmpty(table))
            {
                string tenBang = table;
                query = query.Where(a => a.TableName == tenBang);
            }
            if (tuNgay.HasValue)
            {
                DateTime tu = tuNgay.Value.Date;
                query = query.Where(a => a.OccurredAt >= tu);
            }
            if (denNgay.HasValue)
            {
                // "Đến ngày" tính hết ngày đó, nên so với đầu ngày kế tiếp
                DateTime denHet = denNgay.Value.Date.AddDays(1);
                query = query.Where(a => a.OccurredAt < denHet);
            }

            int tong = await query.CountAsync();
            int tongTrang = Math.Max(1, (int)Math.Ceiling(tong / (double)KichThuocTrang));
            if (page > tongTrang) page = tongTrang;

            // Chỉ lấy NewValues của dòng Update (để liệt kê tên cột đã đổi); dòng khác để null cho nhẹ
            var dong = await query
                .OrderByDescending(a => a.OccurredAt)
                .ThenByDescending(a => a.AuditId)
                .Skip((page - 1) * KichThuocTrang)
                .Take(KichThuocTrang)
                .Select(a => new
                {
                    a.AuditId,
                    a.OccurredAt,
                    a.Action,
                    a.TableName,
                    a.RecordKey,
                    StaffName = a.Staff.FullName,
                    Username = a.Staff.Username,
                    NewValues = a.Action == "Update" ? a.NewValues : null
                })
                .ToListAsync();

            model.Items = dong.Select(d => new AuditLogListItem
            {
                AuditId = d.AuditId,
                OccurredAt = d.OccurredAt,
                StaffName = d.StaffName,
                Username = d.Username,
                Action = d.Action,
                TableName = d.TableName,
                RecordKey = d.RecordKey,
                CotThayDoi = TomTatCotDoi(d.Action, d.NewValues)
            }).ToList();

            model.TongSoDong = tong;
            model.Page = page;
            return View(model);
        }
        catch (Exception ex)
        {
            // Không hiện danh sách rỗng giả khi mất kết nối
            _logger.LogError(ex, "Lỗi khi tải nhật ký thao tác");
            return View("LoiHeThong");
        }
    }

    // ---------------------------------------------------------------
    // Chi tiết một dòng: giá trị cũ và mới (PasswordHash luôn là ***)
    // ---------------------------------------------------------------
    [HttpGet]
    public async Task<IActionResult> Details(long id)
    {
        try
        {
            var dong = await _db.AuditLogs.AsNoTracking()
                .Where(a => a.AuditId == id)
                .Select(a => new
                {
                    a.AuditId,
                    a.OccurredAt,
                    a.Action,
                    a.TableName,
                    a.RecordKey,
                    a.OldValues,
                    a.NewValues,
                    StaffName = a.Staff.FullName,
                    Username = a.Staff.Username
                })
                .FirstOrDefaultAsync();

            if (dong == null)
            {
                TempData["ThongBao"] = "Không tìm thấy dòng nhật ký này.";
                return RedirectToAction(nameof(Index));
            }

            List<AuditValueRow>? cu = NhatKyHienThi.DocJson(dong.OldValues);
            List<AuditValueRow>? moi = NhatKyHienThi.DocJson(dong.NewValues);

            var model = new AuditLogDetailViewModel
            {
                AuditId = dong.AuditId,
                OccurredAt = dong.OccurredAt,
                StaffName = dong.StaffName,
                Username = dong.Username,
                Action = dong.Action,
                TableName = dong.TableName,
                RecordKey = dong.RecordKey,
                KhongDocDuocJson = (cu == null || moi == null),
                Rows = GhepCot(cu ?? new List<AuditValueRow>(), moi ?? new List<AuditValueRow>())
            };
            return View(model);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi tải chi tiết nhật ký {AuditId}", id);
            return View("LoiHeThong");
        }
    }

    // ---------------------------------------------------------------
    // Hàm phụ
    // ---------------------------------------------------------------

    // Dòng Update: liệt kê TÊN các cột đã đổi (không đưa giá trị ra danh sách)
    private static string? TomTatCotDoi(string action, string? newValues)
    {
        if (action != "Update") return null;

        List<AuditValueRow>? cot = NhatKyHienThi.DocJson(newValues);
        if (cot == null) return "(không đọc được)";
        return string.Join(", ", cot.Select(c => c.Cot));
    }

    // Ghép giá trị cũ và mới theo tên cột; cột chỉ có một phía thì phía kia để null
    private static List<AuditCompareRow> GhepCot(List<AuditValueRow> cu, List<AuditValueRow> moi)
    {
        var ketQua = new List<AuditCompareRow>();

        foreach (AuditValueRow cotCu in cu)
        {
            AuditValueRow? cotMoi = moi.FirstOrDefault(m => m.Cot == cotCu.Cot);
            ketQua.Add(new AuditCompareRow
            {
                Cot = cotCu.Cot,
                Cu = cotCu.GiaTri,
                Moi = cotMoi?.GiaTri
            });
        }

        foreach (AuditValueRow cotMoi in moi)
        {
            bool daCo = cu.Any(c => c.Cot == cotMoi.Cot);
            if (!daCo)
            {
                ketQua.Add(new AuditCompareRow { Cot = cotMoi.Cot, Cu = null, Moi = cotMoi.GiaTri });
            }
        }
        return ketQua;
    }
}