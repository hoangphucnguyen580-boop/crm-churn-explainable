using System.Security.Claims;
using CrmChurn.Web.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Controllers;

// Cùng class với CustomersController (partial): dùng chung _db và _logger.
// [Authorize] cấp class (Agent, Manager, Admin) cộng với [Authorize] cấp action
// (Manager, Admin) nghĩa là phải thỏa CẢ HAI, tức chỉ còn Manager và Admin.
public partial class CustomersController
{
    private const string LoiLuu = "Không lưu được, chưa có dữ liệu nào bị thay đổi. Hãy thử lại sau.";

    // StaffID của người đang đăng nhập (lấy từ claim lúc đăng nhập)
    private int? LayStaffId()
    {
        string? chu = User.FindFirstValue(ClaimTypes.NameIdentifier);
        return int.TryParse(chu, out int id) ? id : null;
    }

    // ---------------------------------------------------------------
    // A. Thêm khách (FR-11)
    // ---------------------------------------------------------------
    [Authorize(Roles = "Manager,Admin")]
    [HttpGet]
    public IActionResult Create()
    {
        return View(new CustomerCreateViewModel());
    }

    [Authorize(Roles = "Manager,Admin")]
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Create(CustomerCreateViewModel model)
    {
        // Kiểm giá trị trong danh sách, mức phí, tính nhất quán (BR-15)
        // Gọi hàm kiểm trước, lưu kết quả vào biến riêng để mucPhi còn dùng được ở phía dưới
        var dsLoi = model.KiemTraNghiepVu(out decimal mucPhi);
        foreach (var (truong, noiDung) in dsLoi)
        {
            ModelState.AddModelError(truong, noiDung);
        }
        if (!ModelState.IsValid) return View(model);

        string maKhach = model.CustomerId!.Trim();
        try
        {
            if (await _db.Customers.AnyAsync(c => c.CustomerId == maKhach))
            {
                ModelState.AddModelError(nameof(model.CustomerId), "Mã khách này đã tồn tại.");
                return View(model);
            }

            // Một dòng Customers + một dòng CustomerContracts đang hiệu lực (EffectiveTo = NULL).
            // Cả hai nằm trong MỘT lần SaveChangesAsync: lỗi thì không dòng nào (kể cả audit) được lưu.
            var khach = new Customer
            {
                CustomerId = maKhach,
                Gender = model.Gender,
                SeniorCitizen = model.SeniorCitizen,
                Partner = model.Partner,
                Dependents = model.Dependents,
                CustomerStatus = DanhMucTelco.TrangThaiHoatDong
                // EstimatedJoinDate để NULL: chỉ khách IBM mới có ngày ước lượng
            };
            khach.CustomerContracts.Add(new CustomerContract
            {
                EffectiveFrom = DateTime.Now,
                UpdatedByStaffId = LayStaffId(),
                PhoneService = model.PhoneService!,
                MultipleLines = model.MultipleLines!,
                InternetService = model.InternetService!,
                OnlineSecurity = model.OnlineSecurity!,
                OnlineBackup = model.OnlineBackup!,
                DeviceProtection = model.DeviceProtection!,
                TechSupport = model.TechSupport!,
                StreamingTv = model.StreamingTv!,
                StreamingMovies = model.StreamingMovies!,
                Contract = model.Contract!,
                PaperlessBilling = model.PaperlessBilling!,
                PaymentMethod = model.PaymentMethod!,
                MonthlyCharges = mucPhi
            });
            _db.Customers.Add(khach);
            await _db.SaveChangesAsync();

            TempData["ThanhCong"] = "Đã thêm khách " + maKhach + ". Khách mới chưa có snapshot nên chưa dự báo từ CSDL được (chỉ qua nhập thủ công).";
            return RedirectToAction(nameof(Details), new { id = maKhach });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi thêm khách {CustomerId}", maKhach);
            ModelState.AddModelError(string.Empty, LoiLuu);
            return View(model);
        }
    }

    // ---------------------------------------------------------------
    // B. Sửa hồ sơ (FR-12): CustomerID không sửa được
    // ---------------------------------------------------------------
    [Authorize(Roles = "Manager,Admin")]
    [HttpGet]
    public async Task<IActionResult> Edit(string id)
    {
        try
        {
            var khach = await _db.Customers.AsNoTracking().FirstOrDefaultAsync(c => c.CustomerId == id);
            if (khach == null)
            {
                TempData["ThongBao"] = "Không tìm thấy khách hàng " + id + ".";
                return RedirectToAction(nameof(Index));
            }
            ViewData["CustomerId"] = khach.CustomerId;
            return View(new CustomerEditViewModel
            {
                Gender = khach.Gender,
                SeniorCitizen = khach.SeniorCitizen,
                Partner = khach.Partner ?? false,
                Dependents = khach.Dependents ?? false
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi mở form sửa khách {CustomerId}", id);
            return View("LoiHeThong");
        }
    }

    [Authorize(Roles = "Manager,Admin")]
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Edit(string id, CustomerEditViewModel model)
    {
        ViewData["CustomerId"] = id;
        if (model.Gender != null && !DanhMucTelco.GioiTinh.Contains(model.Gender))
        {
            ModelState.AddModelError(nameof(model.Gender), "Giá trị không hợp lệ.");
        }
        if (!ModelState.IsValid) return View(model);

        try
        {
            // Nạp có theo dõi để EF biết cột nào đổi; audit chỉ ghi các cột đổi (trước và sau)
            var khach = await _db.Customers.FirstOrDefaultAsync(c => c.CustomerId == id);
            if (khach == null)
            {
                TempData["ThongBao"] = "Không tìm thấy khách hàng " + id + ".";
                return RedirectToAction(nameof(Index));
            }

            khach.Gender = model.Gender;
            khach.SeniorCitizen = model.SeniorCitizen;
            khach.Partner = model.Partner;
            khach.Dependents = model.Dependents;

            if (!_db.ChangeTracker.HasChanges())
            {
                TempData["ThongBao"] = "Không có thay đổi nào để lưu.";
                return RedirectToAction(nameof(Details), new { id });
            }

            await _db.SaveChangesAsync();
            TempData["ThanhCong"] = "Đã cập nhật hồ sơ khách " + id + ".";
            return RedirectToAction(nameof(Details), new { id });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi sửa khách {CustomerId}", id);
            ModelState.AddModelError(string.Empty, LoiLuu);
            return View(model);
        }
    }

    // ---------------------------------------------------------------
    // C. Ngừng theo dõi (FR-13): xóa mềm, có bước xác nhận
    // ---------------------------------------------------------------
    [Authorize(Roles = "Manager,Admin")]
    [HttpGet]
    public async Task<IActionResult> Deactivate(string id)
    {
        try
        {
            var khach = await _db.Customers.AsNoTracking().FirstOrDefaultAsync(c => c.CustomerId == id);
            if (khach == null)
            {
                TempData["ThongBao"] = "Không tìm thấy khách hàng " + id + ".";
                return RedirectToAction(nameof(Index));
            }
            return View(khach);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi mở trang ngừng theo dõi {CustomerId}", id);
            return View("LoiHeThong");
        }
    }

    [Authorize(Roles = "Manager,Admin")]
    [HttpPost, ActionName("Deactivate")]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> DeactivateConfirmed(string id)
    {
        try
        {
            var khach = await _db.Customers.FirstOrDefaultAsync(c => c.CustomerId == id);
            if (khach == null)
            {
                TempData["ThongBao"] = "Không tìm thấy khách hàng " + id + ".";
                return RedirectToAction(nameof(Index));
            }
            if (khach.CustomerStatus == DanhMucTelco.TrangThaiNgung)
            {
                TempData["ThongBao"] = "Khách " + id + " đã ngừng theo dõi từ trước.";
                return RedirectToAction(nameof(Details), new { id });
            }

            // Xóa mềm: khách và toàn bộ lịch sử vẫn còn trong CSDL
            khach.CustomerStatus = DanhMucTelco.TrangThaiNgung;
            await _db.SaveChangesAsync();

            TempData["ThanhCong"] = "Đã ngừng theo dõi khách " + id + ". Hồ sơ và lịch sử vẫn được giữ.";
            return RedirectToAction(nameof(Details), new { id });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi ngừng theo dõi khách {CustomerId}", id);
            TempData["ThongBao"] = LoiLuu;
            return RedirectToAction(nameof(Details), new { id });
        }
    }
}