using CrmChurn.Web.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Controllers;

// Cùng class với CustomersController (partial): dùng chung _db, _logger, LoiLuu, LayStaffId
public partial class CustomersController
{
    // Lỗi trùng khóa UNIQUE của SQL Server: 2627 (ràng buộc) hoặc 2601 (chỉ mục duy nhất)
    private static bool LaLoiTrungKhoa(DbUpdateException ex)
    {
        return ex.InnerException is SqlException sql && (sql.Number == 2627 || sql.Number == 2601);
    }

    // ---------------------------------------------------------------
    // GET: mở form, điền sẵn từ dòng đang hiệu lực
    // ---------------------------------------------------------------
    [Authorize(Roles = "Manager,Admin")]
    [HttpGet]
    public async Task<IActionResult> ChangeContract(string id)
    {
        try
        {
            if (!await _db.Customers.AnyAsync(c => c.CustomerId == id))
            {
                TempData["ThongBao"] = "Không tìm thấy khách hàng " + id + ".";
                return RedirectToAction(nameof(Index));
            }

            var cacHopDong = await _db.CustomerContracts.AsNoTracking()
                .Where(k => k.CustomerId == id && k.EffectiveTo == null)
                .ToListAsync();

            // UC-08, 2a: phải đúng MỘT dòng đang hiệu lực, khác 1 là dữ liệu lỗi
            if (cacHopDong.Count != 1)
            {
                TempData["ThongBao"] = "Dữ liệu lỗi: khách " + id + " có " + cacHopDong.Count
                                       + " dòng hợp đồng đang hiệu lực (phải đúng 1), không đổi được.";
                return RedirectToAction(nameof(Details), new { id });
            }

            ViewData["CustomerId"] = id;
            return View(ContractChangeViewModel.TuHopDong(cacHopDong[0]));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi mở form đổi hợp đồng của khách {CustomerId}", id);
            return View("LoiHeThong");
        }
    }

    // ---------------------------------------------------------------
    // POST: kiểm, đóng dòng cũ, thêm dòng mới
    // ---------------------------------------------------------------
    [Authorize(Roles = "Manager,Admin")]
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> ChangeContract(string id, ContractChangeViewModel model)
    {
        ViewData["CustomerId"] = id;

        // Kiểm giá trị trong danh sách, mức phí, nhất quán (BR-15).
        // Lưu kết quả vào biến riêng để mucPhi còn dùng được ở phía dưới
        var dsLoi = model.KiemTraNghiepVu(out decimal mucPhi);
        foreach (var (truong, noiDung) in dsLoi)
        {
            ModelState.AddModelError(truong, noiDung);
        }
        if (!ModelState.IsValid) return View(model);

        try
        {
            if (!await _db.Customers.AnyAsync(c => c.CustomerId == id))
            {
                TempData["ThongBao"] = "Không tìm thấy khách hàng " + id + ".";
                return RedirectToAction(nameof(Index));
            }

            // Nạp CÓ theo dõi để EF ghi được cột EffectiveTo của dòng cũ
            var cacHopDong = await _db.CustomerContracts
                .Where(k => k.CustomerId == id && k.EffectiveTo == null)
                .ToListAsync();

            if (cacHopDong.Count != 1)
            {
                TempData["ThongBao"] = "Dữ liệu lỗi: khách " + id + " có " + cacHopDong.Count
                                       + " dòng hợp đồng đang hiệu lực (phải đúng 1), không đổi được.";
                return RedirectToAction(nameof(Details), new { id });
            }
            var hopDongCu = cacHopDong[0];

            // UC-08, 5b: dòng đang hiệu lực khác dòng lúc mở form => có người vừa đổi
            if (hopDongCu.ContractRecordId != model.HopDongId)
            {
                TempData["ThongBao"] = "Dữ liệu vừa được người khác thay đổi, hãy xem lại rồi đổi lại.";
                return RedirectToAction(nameof(ChangeContract), new { id });
            }

            // UC-08, 4a: không trường nào khác thì không tạo dòng mới
            if (!model.KhacHopDong(hopDongCu, mucPhi))
            {
                ModelState.AddModelError(string.Empty, "Không có thay đổi nào so với hợp đồng hiện tại.");
                return View(model);
            }

            // UC-08, 5a: ngày hiệu lực mới phải lớn hơn ngày bắt đầu của dòng hiện tại
            DateTime ngayMoi = DateTime.Now;
            if (ngayMoi <= hopDongCu.EffectiveFrom)
            {
                ModelState.AddModelError(string.Empty,
                    "Ngày hiệu lực mới phải sau ngày bắt đầu của hợp đồng hiện tại (kiểm tra lại giờ máy).");
                return View(model);
            }

            // Một giao dịch cho cả hai bước. Có lỗi thì Dispose mà chưa Commit => tự rollback.
            // Bên trong CrmDbContext.Audit.cs thấy đã có giao dịch ngoài nên dùng chung, không tự mở thêm.
            await using var giaoDich = await _db.Database.BeginTransactionAsync();

            // Bước 1: ĐÓNG dòng cũ trước (để giải phóng chỗ "đang hiệu lực" của UNIQUE)
            hopDongCu.EffectiveTo = ngayMoi;
            await _db.SaveChangesAsync();

            // Bước 2: THÊM dòng mới đang hiệu lực
            _db.CustomerContracts.Add(new CustomerContract
            {
                CustomerId = id,
                EffectiveFrom = ngayMoi,
                EffectiveTo = null,
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
            await _db.SaveChangesAsync();

            await giaoDich.CommitAsync();

            TempData["ThanhCong"] = "Đã đổi hợp đồng và dịch vụ của khách " + id
                                    + ". Dòng cũ được đóng, dòng mới có hiệu lực từ " + HienThi.Ngay(ngayMoi) + ".";
            return RedirectToAction(nameof(Details), new { id });
        }
        catch (DbUpdateException ex) when (LaLoiTrungKhoa(ex))
        {
            // Hai người đổi cùng lúc: CSDL chặn dòng "đang hiệu lực" thứ hai (UC-08, 5b)
            _logger.LogWarning(ex, "Đổi hợp đồng bị trùng dòng đang hiệu lực của khách {CustomerId}", id);
            TempData["ThongBao"] = "Dữ liệu vừa được người khác thay đổi, không có gì bị đổi. Hãy xem lại rồi đổi lại.";
            return RedirectToAction(nameof(ChangeContract), new { id });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi đổi hợp đồng của khách {CustomerId}", id);
            ModelState.AddModelError(string.Empty, LoiLuu);
            return View(model);
        }
    }
}