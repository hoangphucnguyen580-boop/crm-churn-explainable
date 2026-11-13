using System.Globalization;
using System.Security.Claims;
using CrmChurn.Web.Data;
using CrmChurn.Web.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Controllers;

[Authorize(Roles = "Agent,Manager,Admin")]
public class InteractionsController : Controller
{
    private const int KichThuocTrang = 20;
    private const string LoiLuu = "Không lưu được, chưa có dữ liệu nào bị thay đổi. Hãy thử lại sau.";

    private readonly CrmDbContext _db;
    private readonly ILogger<InteractionsController> _logger;

    public InteractionsController(CrmDbContext db, ILogger<InteractionsController> logger)
    {
        _db = db;
        _logger = logger;
    }

    // StaffID của người đang đăng nhập (đọc từ claim lúc đăng nhập)
    private int? LayStaffId()
    {
        string? chu = User.FindFirstValue(ClaimTypes.NameIdentifier);
        return int.TryParse(chu, out int id) ? id : null;
    }

    // ---------------------------------------------------------------
    // Danh sách: lọc theo khách, loại, kênh, khoảng thời gian (FR-17)
    // ---------------------------------------------------------------
    [HttpGet]
    public async Task<IActionResult> Index(string? customerId, string? type, string? channel,
                                           DateTime? tuNgay, DateTime? denNgay, int page = 1)
    {
        customerId = customerId?.Trim();
        if (page < 1) page = 1;

        var model = new InteractionListViewModel
        {
            CustomerId = customerId,
            Type = type,
            Channel = channel,
            TuNgay = tuNgay?.Date,
            DenNgay = denNgay?.Date,
            Page = page,
            PageSize = KichThuocTrang
        };

        // Khoảng ngày ngược: báo rõ và không hiện dòng nào, tránh hiểu nhầm là "không có dữ liệu"
        if (tuNgay.HasValue && denNgay.HasValue && tuNgay.Value.Date > denNgay.Value.Date)
        {
            model.ThongBaoLoc = "\"Từ ngày\" đang lớn hơn \"Đến ngày\". Hãy chọn lại khoảng thời gian.";
            return View(model);
        }

        try
        {
            IQueryable<Interaction> query = _db.Interactions.AsNoTracking();

            // Có mã khách trùng khớp hoàn toàn thì lọc đúng khách đó (đi từ trang chi tiết),
            // không thì tìm gần đúng như ô tìm ở danh sách khách
            if (!string.IsNullOrEmpty(customerId))
            {
                bool khopChinhXac = await _db.Customers.AnyAsync(c => c.CustomerId == customerId);
                if (khopChinhXac)
                    query = query.Where(i => i.CustomerId == customerId);
                else
                    query = query.Where(i => i.CustomerId.Contains(customerId));
            }

            if (type != null && DanhMucTuongTac.Loai.Contains(type))
            {
                string loai = type;
                query = query.Where(i => i.InteractionType == loai);
            }
            if (channel != null && DanhMucTuongTac.Kenh.Contains(channel))
            {
                string kenh = channel;
                query = query.Where(i => i.Channel == kenh);
            }
            if (tuNgay.HasValue)
            {
                DateTime tu = tuNgay.Value.Date;
                query = query.Where(i => i.InteractionDate >= tu);
            }
            if (denNgay.HasValue)
            {
                // "Đến ngày" tính hết ngày đó, nên so với đầu ngày kế tiếp
                DateTime denHet = denNgay.Value.Date.AddDays(1);
                query = query.Where(i => i.InteractionDate < denHet);
            }

            int tong = await query.CountAsync();
            int tongTrang = Math.Max(1, (int)Math.Ceiling(tong / (double)KichThuocTrang));
            if (page > tongTrang) page = tongTrang;

            // Chỉ lấy cột cần hiện; KHÔNG nạp cả entity Staff (có PasswordHash)
            model.Items = await query
                .OrderByDescending(i => i.InteractionDate)
                .ThenByDescending(i => i.InteractionId)
                .Skip((page - 1) * KichThuocTrang)
                .Take(KichThuocTrang)
                .Select(i => new InteractionListItem
                {
                    InteractionId = i.InteractionId,
                    CustomerId = i.CustomerId,
                    InteractionDate = i.InteractionDate,
                    Channel = i.Channel,
                    InteractionType = i.InteractionType,
                    Description = i.Description,
                    Result = i.Result,
                    StaffName = i.Staff != null ? i.Staff.FullName : null,
                    IsSimulated = i.IsSimulated
                })
                .ToListAsync();

            model.TongSoDong = tong;
            model.Page = page;
            return View(model);
        }
        catch (Exception ex)
        {
            // Không hiện danh sách rỗng giả khi mất kết nối
            _logger.LogError(ex, "Lỗi khi tải danh sách tương tác");
            return View("LoiHeThong");
        }
    }

    // ---------------------------------------------------------------
    // Ghi nhận (FR-16): mọi vai trò
    // ---------------------------------------------------------------
    [HttpGet]
    public IActionResult Create(string? customerId)
    {
        return View(new InteractionCreateModel
        {
            CustomerId = customerId?.Trim(),
            InteractionDate = DateTime.Now   // có sẵn giờ hiện tại, người dùng sửa được
        });
    }

    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Create(InteractionCreateModel model)
    {
        string maKhach = (model.CustomerId ?? "").Trim();
        model.CustomerId = maKhach;

        try
        {
            // Khách phải tồn tại; lấy luôn ngày tham gia ước lượng để kiểm thời điểm
            DateTime? ngayThamGia = null;
            if (maKhach != "")
            {
                var khach = await _db.Customers.AsNoTracking()
                    .Where(c => c.CustomerId == maKhach)
                    .Select(c => new { c.EstimatedJoinDate })
                    .FirstOrDefaultAsync();
                if (khach == null)
                    ModelState.AddModelError(nameof(model.CustomerId), "Không tìm thấy khách hàng này.");
                else
                    ngayThamGia = khach.EstimatedJoinDate;
            }

            foreach (var (truong, noiDung) in model.KiemTraNghiepVu(ngayThamGia))
            {
                ModelState.AddModelError(truong, noiDung);
            }
            if (!ModelState.IsValid) return View(model);

            // Người phụ trách = người đang đăng nhập; IsSimulated = false (dòng nhập tay, BR-09)
            var tuongTac = new Interaction
            {
                CustomerId = maKhach,
                StaffId = LayStaffId(),
                InteractionDate = model.InteractionDate!.Value,
                Channel = model.Channel!,
                InteractionType = model.InteractionType!,
                Description = model.Description,
                Result = model.Result,
                IsSimulated = false
            };
            _db.Interactions.Add(tuongTac);
            await _db.SaveChangesAsync();

            TempData["ThanhCong"] = "Đã ghi nhận tương tác cho khách " + maKhach + ".";
            return RedirectToAction(nameof(Index), new { customerId = maKhach });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi ghi nhận tương tác của khách {CustomerId}", maKhach);
            ModelState.AddModelError(string.Empty, LoiLuu);
            return View(model);
        }
    }

    // ---------------------------------------------------------------
    // Sửa (FR-18): chỉ Manager, Admin. Không sửa khách, người phụ trách, IsSimulated.
    // ---------------------------------------------------------------
    [Authorize(Roles = "Manager,Admin")]
    [HttpGet]
    public async Task<IActionResult> Edit(long id)
    {
        try
        {
            var ban = await _db.Interactions.AsNoTracking()
                .FirstOrDefaultAsync(i => i.InteractionId == id);
            if (ban == null)
            {
                TempData["ThongBao"] = "Không tìm thấy tương tác này (có thể đã bị xóa).";
                return RedirectToAction(nameof(Index));
            }

            ViewData["InteractionId"] = id;
            ViewData["CustomerId"] = ban.CustomerId;
            ViewData["IsSimulated"] = ban.IsSimulated;
            return View(new InteractionFormModel
            {
                Channel = ban.Channel,
                InteractionType = ban.InteractionType,
                InteractionDate = ban.InteractionDate,
                Description = ban.Description,
                Result = ban.Result
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi mở form sửa tương tác {InteractionId}", id);
            return View("LoiHeThong");
        }
    }

    [Authorize(Roles = "Manager,Admin")]
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Edit(long id, InteractionFormModel model)
    {
        ViewData["InteractionId"] = id;
        try
        {
            // Nạp CÓ theo dõi để EF biết cột nào đổi (audit chỉ ghi cột đổi, trước và sau)
            var ban = await _db.Interactions.FirstOrDefaultAsync(i => i.InteractionId == id);
            if (ban == null)
            {
                TempData["ThongBao"] = "Không tìm thấy tương tác này (có thể đã bị xóa).";
                return RedirectToAction(nameof(Index));
            }
            ViewData["CustomerId"] = ban.CustomerId;
            ViewData["IsSimulated"] = ban.IsSimulated;

            DateTime? ngayThamGia = await _db.Customers.AsNoTracking()
                .Where(c => c.CustomerId == ban.CustomerId)
                .Select(c => c.EstimatedJoinDate)
                .FirstOrDefaultAsync();

            foreach (var (truong, noiDung) in model.KiemTraNghiepVu(ngayThamGia))
            {
                ModelState.AddModelError(truong, noiDung);
            }
            if (!ModelState.IsValid) return View(model);

            ban.Channel = model.Channel!;
            ban.InteractionType = model.InteractionType!;
            ban.Description = model.Description;
            ban.Result = model.Result;

            // Ô giờ trên form chỉ có đến phút, còn dữ liệu gốc có cả giây (dòng mô phỏng).
            // Chỉ ghi đè khi người dùng thật sự đổi giờ, nếu không audit sẽ ghi một thay đổi "ma".
            DateTime gioMoi = model.InteractionDate!.Value;
            const string dangPhut = "yyyy-MM-dd HH:mm";
            if (gioMoi.ToString(dangPhut, CultureInfo.InvariantCulture)
                != ban.InteractionDate.ToString(dangPhut, CultureInfo.InvariantCulture))
            {
                ban.InteractionDate = gioMoi;
            }

            if (!_db.ChangeTracker.HasChanges())
            {
                TempData["ThongBao"] = "Không có thay đổi nào để lưu.";
                return RedirectToAction(nameof(Index), new { customerId = ban.CustomerId });
            }

            await _db.SaveChangesAsync();
            TempData["ThanhCong"] = "Đã cập nhật tương tác.";
            return RedirectToAction(nameof(Index), new { customerId = ban.CustomerId });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi sửa tương tác {InteractionId}", id);
            ModelState.AddModelError(string.Empty, LoiLuu);
            return View(model);
        }
    }

    // ---------------------------------------------------------------
    // Xóa (FR-19): chỉ Admin, có bước xác nhận; audit giữ giá trị cũ
    // ---------------------------------------------------------------
    [Authorize(Roles = "Admin")]
    [HttpGet]
    public async Task<IActionResult> Delete(long id)
    {
        try
        {
            var dong = await LayDongHienThiAsync(id);
            if (dong == null)
            {
                TempData["ThongBao"] = "Không tìm thấy tương tác này (có thể đã bị xóa).";
                return RedirectToAction(nameof(Index));
            }
            return View(dong);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi mở trang xóa tương tác {InteractionId}", id);
            return View("LoiHeThong");
        }
    }

    [Authorize(Roles = "Admin")]
    [HttpPost, ActionName("Delete")]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> DeleteConfirmed(long id)
    {
        try
        {
            var ban = await _db.Interactions.FirstOrDefaultAsync(i => i.InteractionId == id);
            if (ban == null)
            {
                TempData["ThongBao"] = "Tương tác này đã bị xóa từ trước.";
                return RedirectToAction(nameof(Index));
            }

            string maKhach = ban.CustomerId;
            _db.Interactions.Remove(ban);
            await _db.SaveChangesAsync();

            TempData["ThanhCong"] = "Đã xóa tương tác của khách " + maKhach + ".";
            return RedirectToAction(nameof(Index), new { customerId = maKhach });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi xóa tương tác {InteractionId}", id);
            TempData["ThongBao"] = LoiLuu;
            return RedirectToAction(nameof(Index));
        }
    }

    // Một dòng tương tác để hiện ở trang xóa (không nạp Staff đầy đủ)
    private Task<InteractionListItem?> LayDongHienThiAsync(long id)
    {
        return _db.Interactions.AsNoTracking()
            .Where(i => i.InteractionId == id)
            .Select(i => new InteractionListItem
            {
                InteractionId = i.InteractionId,
                CustomerId = i.CustomerId,
                InteractionDate = i.InteractionDate,
                Channel = i.Channel,
                InteractionType = i.InteractionType,
                Description = i.Description,
                Result = i.Result,
                StaffName = i.Staff != null ? i.Staff.FullName : null,
                IsSimulated = i.IsSimulated
            })
            .FirstOrDefaultAsync();
    }
}