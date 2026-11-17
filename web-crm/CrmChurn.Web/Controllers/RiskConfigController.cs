using System.Globalization;
using System.Security.Claims;
using CrmChurn.Web.Data;
using CrmChurn.Web.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Controllers;

[Authorize(Roles = "Manager,Admin")]
public class RiskConfigController : Controller
{
    private const string LoiLuu = "Không lưu được, ngưỡng cũ vẫn được giữ nguyên. Hãy thử lại sau.";

    private readonly CrmDbContext _db;
    private readonly ILogger<RiskConfigController> _logger;

    public RiskConfigController(CrmDbContext db, ILogger<RiskConfigController> logger)
    {
        _db = db;
        _logger = logger;
    }

    private int? LayStaffId()
    {
        string? chu = User.FindFirstValue(ClaimTypes.NameIdentifier);
        return int.TryParse(chu, out int id) ? id : null;
    }

    // Điền phần hiển thị (người và lúc cập nhật gần nhất, cảnh báo thiếu khóa). Không đụng MediumText/HighText.
    // Trả về chuỗi hai ngưỡng đang lưu để GET điền sẵn vào ô nhập.
    private async Task<(string? Medium, string? High)> NapThongTinAsync(RiskConfigViewModel model)
    {
        // Chỉ lấy cột cần (tên người sửa), KHÔNG nạp cả entity Staff (có PasswordHash)
        var cacDong = await _db.RiskConfigs.AsNoTracking()
            .Where(c => c.ConfigKey == NguongRuiRo.KhoaTrungBinh || c.ConfigKey == NguongRuiRo.KhoaCao)
            .Select(c => new
            {
                c.ConfigKey,
                c.ConfigValue,
                c.UpdatedAt,
                Ten = c.UpdatedByStaff != null ? c.UpdatedByStaff.FullName : null
            })
            .ToListAsync();

        var dongTb = cacDong.FirstOrDefault(c => c.ConfigKey == NguongRuiRo.KhoaTrungBinh);
        var dongCao = cacDong.FirstOrDefault(c => c.ConfigKey == NguongRuiRo.KhoaCao);

        if (dongTb == null || dongCao == null)
        {
            model.ThongBaoThieuKhoa = "Cấu hình ngưỡng bị thiếu khóa " + NguongRuiRo.KhoaTrungBinh + " hoặc "
                + NguongRuiRo.KhoaCao + ". Chạy etl\\register_model.py để tạo lại.";
            return (null, null);
        }

        // Lấy người và lúc cập nhật gần nhất trong hai dòng
        var moiNhat = dongTb.UpdatedAt >= dongCao.UpdatedAt ? dongTb : dongCao;
        model.CapNhatLuc = moiNhat.UpdatedAt;
        model.CapNhatBoi = moiNhat.Ten;   // null nếu do script ghi (UpdatedByStaffID rỗng)
        return (dongTb.ConfigValue, dongCao.ConfigValue);
    }

    // ---------------------------------------------------------------
    // Xem ngưỡng hiện tại
    // ---------------------------------------------------------------
    [HttpGet]
    public async Task<IActionResult> Index()
    {
        try
        {
            var model = new RiskConfigViewModel();
            var (tb, cao) = await NapThongTinAsync(model);
            model.MediumText = tb;
            model.HighText = cao;
            return View(model);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi tải cấu hình ngưỡng");
            return View("LoiHeThong");
        }
    }

    // ---------------------------------------------------------------
    // Sửa ngưỡng: số từ 0 đến 1, Medium < High, lưu hai khóa trong MỘT lần SaveChanges
    // ---------------------------------------------------------------
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Index(RiskConfigViewModel model)
    {
        const string LoiSo = "Nhập số từ 0 đến 1, tối đa 4 chữ số thập phân (ví dụ 0,3148).";

        bool docTb = NguongRuiRo.TryDocTuForm(model.MediumText, out decimal trungBinh);
        bool docCao = NguongRuiRo.TryDocTuForm(model.HighText, out decimal cao);
        if (!docTb) ModelState.AddModelError(nameof(model.MediumText), LoiSo);
        if (!docCao) ModelState.AddModelError(nameof(model.HighText), LoiSo);
        if (docTb && docCao && trungBinh >= cao)
        {
            ModelState.AddModelError(string.Empty, "Ngưỡng Medium phải nhỏ hơn ngưỡng High.");
        }

        try
        {
            if (!ModelState.IsValid)
            {
                await NapThongTinAsync(model);
                return View(model);
            }

            // Nạp CÓ theo dõi để EF ghi các cột đổi; audit chỉ ghi cột đổi (trước và sau)
            var cacDong = await _db.RiskConfigs
                .Where(c => c.ConfigKey == NguongRuiRo.KhoaTrungBinh || c.ConfigKey == NguongRuiRo.KhoaCao)
                .ToListAsync();
            var dongTb = cacDong.FirstOrDefault(c => c.ConfigKey == NguongRuiRo.KhoaTrungBinh);
            var dongCao = cacDong.FirstOrDefault(c => c.ConfigKey == NguongRuiRo.KhoaCao);
            if (dongTb == null || dongCao == null)
            {
                await NapThongTinAsync(model);
                return View(model);   // View sẽ hiện lời báo thiếu khóa
            }

            int? nguoiSua = LayStaffId();
            DateTime bayGio = DateTime.Now;
            bool doiTb = CapNhatNeuDoi(dongTb, trungBinh, nguoiSua, bayGio);
            bool doiCao = CapNhatNeuDoi(dongCao, cao, nguoiSua, bayGio);

            if (!doiTb && !doiCao)
            {
                TempData["ThongBao"] = "Không có thay đổi nào để lưu.";
                return RedirectToAction(nameof(Index));
            }

            await _db.SaveChangesAsync();
            TempData["ThanhCong"] = "Đã cập nhật ngưỡng rủi ro. Ngưỡng mới áp cho các dự báo thực hiện sau đó; "
                                    + "mức rủi ro đã lưu trước đây giữ nguyên.";
            return RedirectToAction(nameof(Index));
        }
        catch (Exception ex)
        {
            _db.ChangeTracker.Clear();
            _logger.LogError(ex, "Lỗi khi lưu ngưỡng rủi ro");
            ModelState.AddModelError(string.Empty, LoiLuu);
            try { await NapThongTinAsync(model); } catch { /* mất kết nối: View vẫn hiện được lời báo ở trên */ }
            return View(model);
        }
    }

    // Chỉ đổi khi giá trị mới khác giá trị đang lưu; đổi thì ghi luôn người sửa và lúc sửa
    private static bool CapNhatNeuDoi(RiskConfig dong, decimal giaTriMoi, int? nguoiSua, DateTime luc)
    {
        bool docDuoc = decimal.TryParse(dong.ConfigValue, NumberStyles.AllowDecimalPoint,
                                        CultureInfo.InvariantCulture, out decimal giaTriCu);
        if (docDuoc && giaTriCu == giaTriMoi) return false;

        dong.ConfigValue = giaTriMoi.ToString("0.0000", CultureInfo.InvariantCulture);   // khớp định dạng đã nạp: 0.3148
        dong.UpdatedByStaffId = nguoiSua;
        dong.UpdatedAt = luc;
        return true;
    }
}