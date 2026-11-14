using System.Security.Claims;
using CrmChurn.Web.Data;
using CrmChurn.Web.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Controllers;

[Authorize(Roles = "Agent,Manager,Admin")]
public class TicketsController : Controller
{
    private const int KichThuocTrang = 20;
    private const string LoiLuu = "Không lưu được, chưa có dữ liệu nào bị thay đổi. Hãy thử lại sau.";
    private const string LoiDoiTrangThai = "Ticket đã đổi trạng thái, hãy tải lại trang rồi thao tác lại.";

    private readonly CrmDbContext _db;
    private readonly ILogger<TicketsController> _logger;

    public TicketsController(CrmDbContext db, ILogger<TicketsController> logger)
    {
        _db = db;
        _logger = logger;
    }

    // ---------------------------------------------------------------
    // Hàm phụ
    // ---------------------------------------------------------------

    // StaffID của người đang đăng nhập (đọc từ claim lúc đăng nhập)
    private int? LayStaffId()
    {
        string? chu = User.FindFirstValue(ClaimTypes.NameIdentifier);
        return int.TryParse(chu, out int id) ? id : null;
    }

    // Danh sách nhân viên cho ô chọn. Chỉ lấy mã và tên (không nạp PasswordHash).
    private Task<List<StaffOption>> LayNhanVienAsync(bool chiHoatDong)
    {
        IQueryable<Staff> query = _db.Staff.AsNoTracking();
        if (chiHoatDong) query = query.Where(s => s.IsActive);
        return query
            .OrderBy(s => s.FullName)
            .Select(s => new StaffOption { StaffId = s.StaffId, FullName = s.FullName })
            .ToListAsync();
    }

    // Đọc một ticket thành model hiển thị (không theo dõi). Không có thì trả null.
    private async Task<TicketDetailViewModel?> DungChiTietAsync(long id, bool kemNhanVien)
    {
        var vm = await _db.Tickets.AsNoTracking()
            .Where(t => t.TicketId == id)
            .Select(t => new TicketDetailViewModel
            {
                TicketId = t.TicketId,
                CustomerId = t.CustomerId,
                Category = t.Category,
                Priority = t.Priority,
                Status = t.Status,
                CreatedAt = t.CreatedAt,
                ClosedAt = t.ClosedAt,
                Resolution = t.Resolution,
                SatisfactionScore = t.SatisfactionScore,
                ReopenReason = t.ReopenReason,
                IsSimulated = t.IsSimulated,
                AssignedStaffId = t.AssignedStaffId,
                AssignedName = t.AssignedStaff != null ? t.AssignedStaff.FullName : null
            })
            .FirstOrDefaultAsync();
        if (vm == null) return null;

        vm.NguoiDangNhapId = LayStaffId();
        vm.CoQuyenMoLai = User.IsInRole("Manager") || User.IsInRole("Admin");
        vm.CoQuyenXoa = User.IsInRole("Admin");
        if (kemNhanVien) vm.NhanVien = await LayNhanVienAsync(true);
        return vm;
    }

    // Đọc phần tóm tắt ticket và đặt vào ViewData["Ticket"] cho các trang Đóng, Mở lại, Xóa
    private async Task<TicketDetailViewModel?> LayThongTinAsync(long id)
    {
        var vm = await DungChiTietAsync(id, false);
        ViewData["Ticket"] = vm;
        return vm;
    }

    private IActionResult KhongTimThay()
    {
        TempData["ThongBao"] = "Không tìm thấy ticket này (có thể đã bị xóa).";
        return RedirectToAction(nameof(Index));
    }

    // Quay về trang chi tiết kèm một lời báo màu vàng
    private IActionResult VeChiTiet(long id, string thongBao)
    {
        TempData["ThongBao"] = thongBao;
        return RedirectToAction(nameof(Details), new { id });
    }

    // ---------------------------------------------------------------
    // Danh sách toàn hệ thống (FR-22)
    // ---------------------------------------------------------------
    [HttpGet]
    public async Task<IActionResult> Index(string? customerId, string? status, string? priority,
                                           string? staff, int page = 1)
    {
        customerId = customerId?.Trim();
        if (page < 1) page = 1;

        var model = new TicketListViewModel
        {
            CustomerId = customerId,
            Status = status,
            Priority = priority,
            Staff = staff,
            Page = page,
            PageSize = KichThuocTrang
        };

        try
        {
            IQueryable<Ticket> query = _db.Tickets.AsNoTracking();

            // Mã khách khớp chính xác thì lọc đúng khách đó, không thì tìm gần đúng (giống trang Tương tác)
            if (!string.IsNullOrEmpty(customerId))
            {
                bool khopChinhXac = await _db.Customers.AnyAsync(c => c.CustomerId == customerId);
                if (khopChinhXac)
                    query = query.Where(t => t.CustomerId == customerId);
                else
                    query = query.Where(t => t.CustomerId.Contains(customerId));
            }

            if (status != null && DanhMucTicket.TrangThai.Contains(status))
            {
                string trangThai = status;
                query = query.Where(t => t.Status == trangThai);
            }
            if (priority != null && DanhMucTicket.UuTien.Contains(priority))
            {
                string uuTien = priority;
                query = query.Where(t => t.Priority == uuTien);
            }

            // "none" = chưa phân công (toàn bộ ticket mô phỏng nằm ở nhóm này)
            if (staff == "none")
            {
                query = query.Where(t => t.AssignedStaffId == null);
            }
            else if (int.TryParse(staff, out int maNhanVien))
            {
                query = query.Where(t => t.AssignedStaffId == maNhanVien);
            }

            int tong = await query.CountAsync();
            int tongTrang = Math.Max(1, (int)Math.Ceiling(tong / (double)KichThuocTrang));
            if (page > tongTrang) page = tongTrang;

            model.Items = await query
                .OrderByDescending(t => t.CreatedAt)
                .ThenByDescending(t => t.TicketId)
                .Skip((page - 1) * KichThuocTrang)
                .Take(KichThuocTrang)
                .Select(t => new TicketListItem
                {
                    TicketId = t.TicketId,
                    CustomerId = t.CustomerId,
                    Category = t.Category,
                    Priority = t.Priority,
                    Status = t.Status,
                    CreatedAt = t.CreatedAt,
                    ClosedAt = t.ClosedAt,
                    SatisfactionScore = t.SatisfactionScore,
                    AssignedName = t.AssignedStaff != null ? t.AssignedStaff.FullName : null,
                    IsSimulated = t.IsSimulated
                })
                .ToListAsync();

            model.TongSoDong = tong;
            model.Page = page;
            model.NhanVien = await LayNhanVienAsync(false);
            return View(model);
        }
        catch (Exception ex)
        {
            // Không hiện danh sách rỗng giả khi mất kết nối
            _logger.LogError(ex, "Lỗi khi tải danh sách ticket");
            return View("LoiHeThong");
        }
    }

    // ---------------------------------------------------------------
    // Mở ticket (FR-21): mọi vai trò
    // ---------------------------------------------------------------
    [HttpGet]
    public IActionResult Create(string? customerId)
    {
        return View(new TicketCreateModel { CustomerId = customerId?.Trim() });
    }

    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Create(TicketCreateModel model)
    {
        string maKhach = (model.CustomerId ?? "").Trim();
        model.CustomerId = maKhach;

        try
        {
            foreach (var (truong, noiDung) in model.KiemTraNghiepVu())
            {
                ModelState.AddModelError(truong, noiDung);
            }

            // Khách phải tồn tại; lấy mã đúng như trong database (SQL Server không phân biệt hoa thường)
            string? maThat = null;
            if (maKhach != "")
            {
                maThat = await _db.Customers.AsNoTracking()
                    .Where(c => c.CustomerId == maKhach)
                    .Select(c => c.CustomerId)
                    .FirstOrDefaultAsync();
                if (maThat == null)
                    ModelState.AddModelError(nameof(model.CustomerId), "Không tìm thấy khách hàng này.");
            }
            if (!ModelState.IsValid) return View(model);

            // Ticket mới: Open, chưa phân công, chưa có ClosedAt, dòng nhập tay (IsSimulated = false)
            var ticket = new Ticket
            {
                CustomerId = maThat!,
                CreatedAt = DateTime.Now,
                Category = model.Category!,
                Priority = model.Priority!,
                Status = DanhMucTicket.Open,
                IsSimulated = false
            };
            _db.Tickets.Add(ticket);
            await _db.SaveChangesAsync();

            TempData["ThanhCong"] = "Đã mở ticket " + ticket.TicketId + " cho khách " + maThat + ".";
            return RedirectToAction(nameof(Details), new { id = ticket.TicketId });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi mở ticket cho khách {CustomerId}", maKhach);
            ModelState.AddModelError(string.Empty, LoiLuu);
            return View(model);
        }
    }

    // ---------------------------------------------------------------
    // Chi tiết ticket (UC-04 bước 6): chỉ hiện thao tác hợp lệ với trạng thái và vai trò
    // ---------------------------------------------------------------
    [HttpGet]
    public async Task<IActionResult> Details(long id)
    {
        try
        {
            var vm = await DungChiTietAsync(id, true);
            if (vm == null) return KhongTimThay();
            return View(vm);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi tải chi tiết ticket {TicketId}", id);
            return View("LoiHeThong");
        }
    }

    // ---------------------------------------------------------------
    // Phân công và/hoặc đổi ưu tiên (UC-04, 7b): ticket Open hoặc InProgress, KHÔNG đổi trạng thái
    // ---------------------------------------------------------------
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Assign(long id, string? trangThaiLucMo, int? staffId, string? priority)
    {
        try
        {
            var t = await _db.Tickets.FirstOrDefaultAsync(x => x.TicketId == id);
            if (t == null) return KhongTimThay();

            if (t.Status != trangThaiLucMo) return VeChiTiet(id, LoiDoiTrangThai);
            if (t.Status == DanhMucTicket.Closed)
                return VeChiTiet(id, "Ticket đã đóng, không phân công hay đổi ưu tiên được. Hãy mở lại ticket trước.");

            if (priority == null || !DanhMucTicket.UuTien.Contains(priority))
                return VeChiTiet(id, "Mức ưu tiên không hợp lệ.");

            if (staffId.HasValue)
            {
                bool hopLe = await _db.Staff.AnyAsync(s => s.StaffId == staffId.Value && s.IsActive);
                if (!hopLe)
                    return VeChiTiet(id, "Người phụ trách không hợp lệ hoặc đã ngừng hoạt động.");
            }
            else if (t.Status == DanhMucTicket.InProgress && t.AssignedStaffId != null)
            {
                // Ticket đang xử lý phải có người phụ trách (ticket mô phỏng chưa có thì để nguyên được)
                return VeChiTiet(id, "Ticket đang xử lý phải có người phụ trách, không bỏ trống được.");
            }

            t.AssignedStaffId = staffId;
            t.Priority = priority;

            if (!_db.ChangeTracker.HasChanges())
                return VeChiTiet(id, "Không có thay đổi nào để lưu.");

            await _db.SaveChangesAsync();
            TempData["ThanhCong"] = "Đã cập nhật phân công và ưu tiên của ticket " + id + ".";
            return RedirectToAction(nameof(Details), new { id });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi phân công ticket {TicketId}", id);
            return VeChiTiet(id, LoiLuu);
        }
    }

    // ---------------------------------------------------------------
    // Bắt đầu xử lý: Open -> InProgress, bắt buộc có người phụ trách
    // ---------------------------------------------------------------
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Start(long id, string? trangThaiLucMo, int? staffId)
    {
        try
        {
            var t = await _db.Tickets.FirstOrDefaultAsync(x => x.TicketId == id);
            if (t == null) return KhongTimThay();

            if (t.Status != trangThaiLucMo) return VeChiTiet(id, LoiDoiTrangThai);
            if (t.Status != DanhMucTicket.Open)
                return VeChiTiet(id, "Chỉ ticket đang Open mới chuyển sang InProgress được.");

            if (!staffId.HasValue)
                return VeChiTiet(id, "Hãy chọn người phụ trách trước khi chuyển sang InProgress.");
            bool hopLe = await _db.Staff.AnyAsync(s => s.StaffId == staffId.Value && s.IsActive);
            if (!hopLe)
                return VeChiTiet(id, "Người phụ trách không hợp lệ hoặc đã ngừng hoạt động.");

            t.AssignedStaffId = staffId;
            t.Status = DanhMucTicket.InProgress;
            await _db.SaveChangesAsync();

            TempData["ThanhCong"] = "Ticket " + id + " đã chuyển sang InProgress.";
            return RedirectToAction(nameof(Details), new { id });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi chuyển ticket {TicketId} sang InProgress", id);
            return VeChiTiet(id, LoiLuu);
        }
    }

    // ---------------------------------------------------------------
    // Đóng ticket (FR-24): InProgress -> Closed. Trang riêng vì có ô nhập chữ.
    // ---------------------------------------------------------------
    [HttpGet]
    public async Task<IActionResult> Close(long id)
    {
        try
        {
            var tt = await LayThongTinAsync(id);
            if (tt == null) return KhongTimThay();

            if (tt.Status == DanhMucTicket.Open)
                return VeChiTiet(id, "Ticket đang Open, phải chuyển sang InProgress trước khi đóng.");
            if (tt.Status == DanhMucTicket.Closed)
                return VeChiTiet(id, "Ticket này đã đóng.");

            return View(new TicketCloseModel { TrangThaiLucMo = tt.Status });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi mở trang đóng ticket {TicketId}", id);
            return View("LoiHeThong");
        }
    }

    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Close(long id, TicketCloseModel model)
    {
        ViewData["TicketId"] = id;   // đặt trước để View vẫn có mã ticket nếu có lỗi
        try
        {
            await LayThongTinAsync(id);
            if (!ModelState.IsValid) return View(model);

            // Nạp CÓ theo dõi để EF ghi được các cột đổi (audit chỉ ghi cột đổi)
            var t = await _db.Tickets.FirstOrDefaultAsync(x => x.TicketId == id);
            if (t == null) return KhongTimThay();

            if (t.Status != model.TrangThaiLucMo) return VeChiTiet(id, LoiDoiTrangThai);
            if (t.Status == DanhMucTicket.Open)
                return VeChiTiet(id, "Ticket đang Open, phải chuyển sang InProgress trước khi đóng.");
            if (t.Status == DanhMucTicket.Closed)
                return VeChiTiet(id, "Ticket này đã đóng.");

            string ketQua = (model.Resolution ?? "").Trim();
            if (ketQua.Length == 0)
            {
                ModelState.AddModelError(nameof(model.Resolution), "Nhập kết quả giải quyết");
                return View(model);
            }

            // ClosedAt do HỆ THỐNG gán, không cho nhập tay (UC-04, 10c)
            DateTime bayGio = DateTime.Now;
            if (bayGio < t.CreatedAt)
            {
                ModelState.AddModelError(string.Empty,
                    "Giờ máy hiện tại sớm hơn giờ tạo ticket, không đóng được. Hãy kiểm tra lại giờ máy.");
                return View(model);
            }

            t.Status = DanhMucTicket.Closed;
            t.ClosedAt = bayGio;
            t.Resolution = ketQua;
            t.SatisfactionScore = model.SatisfactionScore.HasValue
                ? (short)model.SatisfactionScore.Value
                : (short?)null;
            await _db.SaveChangesAsync();

            TempData["ThanhCong"] = "Đã đóng ticket " + id + ". Thời gian xử lý: "
                                    + HienThiTicket.ThoiGianXuLy(t.CreatedAt, t.ClosedAt) + ".";
            return RedirectToAction(nameof(Details), new { id });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi đóng ticket {TicketId}", id);
            ModelState.AddModelError(string.Empty, LoiLuu);
            return View(model);
        }
    }

    // ---------------------------------------------------------------
    // Ghi điểm hài lòng SAU khi đóng (bổ sung): ticket Closed chưa có điểm, ghi một lần
    // ---------------------------------------------------------------
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Rate(long id, string? trangThaiLucMo, int? score)
    {
        try
        {
            var t = await _db.Tickets.FirstOrDefaultAsync(x => x.TicketId == id);
            if (t == null) return KhongTimThay();

            if (t.Status != trangThaiLucMo) return VeChiTiet(id, LoiDoiTrangThai);
            if (t.Status != DanhMucTicket.Closed)
                return VeChiTiet(id, "Chỉ ticket đã đóng mới ghi điểm hài lòng được.");
            if (t.SatisfactionScore != null)
                return VeChiTiet(id, "Ticket này đã có điểm hài lòng.");
            if (!score.HasValue || score.Value < 1 || score.Value > 5)
                return VeChiTiet(id, "Điểm hài lòng phải từ 1 đến 5.");

            t.SatisfactionScore = (short)score.Value;
            await _db.SaveChangesAsync();

            TempData["ThanhCong"] = "Đã ghi điểm hài lòng " + score.Value + " cho ticket " + id + ".";
            return RedirectToAction(nameof(Details), new { id });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi ghi điểm hài lòng ticket {TicketId}", id);
            return VeChiTiet(id, LoiLuu);
        }
    }

    // ---------------------------------------------------------------
    // Mở lại ticket (UC-09, FR-25): chỉ Manager, Admin; bắt buộc có lý do
    // ---------------------------------------------------------------
    [Authorize(Roles = "Manager,Admin")]
    [HttpGet]
    public async Task<IActionResult> Reopen(long id)
    {
        try
        {
            var tt = await LayThongTinAsync(id);
            if (tt == null) return KhongTimThay();
            if (tt.Status != DanhMucTicket.Closed)
                return VeChiTiet(id, "Chỉ ticket đã đóng mới mở lại được.");

            return View(new TicketReopenModel { TrangThaiLucMo = tt.Status });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi mở trang mở lại ticket {TicketId}", id);
            return View("LoiHeThong");
        }
    }

    [Authorize(Roles = "Manager,Admin")]
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Reopen(long id, TicketReopenModel model)
    {
        ViewData["TicketId"] = id;
        try
        {
            await LayThongTinAsync(id);
            if (!ModelState.IsValid) return View(model);

            var t = await _db.Tickets.FirstOrDefaultAsync(x => x.TicketId == id);
            if (t == null) return KhongTimThay();

            // UC-09, 4a: không còn Closed (người khác vừa đổi) thì không làm gì
            if (t.Status != DanhMucTicket.Closed || t.Status != model.TrangThaiLucMo)
                return VeChiTiet(id, LoiDoiTrangThai);

            string lyDo = (model.Reason ?? "").Trim();
            if (lyDo.Length == 0)
            {
                ModelState.AddModelError(nameof(model.Reason), "Nhập lý do mở lại");
                return View(model);
            }

            // Về InProgress, xóa ClosedAt và điểm hài lòng (CHECK bắt buộc), GIỮ Resolution (D-18)
            t.Status = DanhMucTicket.InProgress;
            t.ClosedAt = null;
            t.SatisfactionScore = null;
            t.ReopenReason = lyDo;
            await _db.SaveChangesAsync();

            TempData["ThanhCong"] = "Đã mở lại ticket " + id + ". Ticket đang ở trạng thái InProgress.";
            return RedirectToAction(nameof(Details), new { id });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi mở lại ticket {TicketId}", id);
            ModelState.AddModelError(string.Empty, LoiLuu);
            return View(model);
        }
    }

    // ---------------------------------------------------------------
    // Xóa (FR-26): chỉ Admin, có bước xác nhận; audit giữ giá trị cũ
    // ---------------------------------------------------------------
    [Authorize(Roles = "Admin")]
    [HttpGet]
    public async Task<IActionResult> Delete(long id)
    {
        try
        {
            var vm = await DungChiTietAsync(id, false);
            if (vm == null) return KhongTimThay();
            return View(vm);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi mở trang xóa ticket {TicketId}", id);
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
            var t = await _db.Tickets.FirstOrDefaultAsync(x => x.TicketId == id);
            if (t == null)
            {
                TempData["ThongBao"] = "Ticket này đã bị xóa từ trước.";
                return RedirectToAction(nameof(Index));
            }

            _db.Tickets.Remove(t);
            await _db.SaveChangesAsync();

            TempData["ThanhCong"] = "Đã xóa ticket " + id + ".";
            return RedirectToAction(nameof(Index));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi xóa ticket {TicketId}", id);
            TempData["ThongBao"] = LoiLuu;
            return RedirectToAction(nameof(Index));
        }
    }
}