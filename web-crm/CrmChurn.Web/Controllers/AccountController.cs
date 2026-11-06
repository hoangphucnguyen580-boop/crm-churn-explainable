using System.Security.Claims;
using CrmChurn.Web.Data;
using CrmChurn.Web.Models;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Controllers;

// Cả controller cho phép chưa đăng nhập, vì đây là nơi người dùng đăng nhập
[AllowAnonymous]
public class AccountController : Controller
{
    // Lý do thất bại: PHẢI khớp danh sách trong CHECK CK_LoginAttempts_ThanhCong_LyDoThatBai
    private const string LyDoKhongCoTen = "UnknownUser";
    private const string LyDoSaiMatKhau = "WrongPassword";
    private const string LyDoBiVoHieu = "Inactive";
    private const string LyDoBiKhoa = "Locked";

    // Mọi trường hợp thất bại đều báo cùng MỘT câu, để người ngoài không dò được tên nào tồn tại
    private const string CauBaoLoiChung = "Tên đăng nhập hoặc mật khẩu không đúng.";

    private readonly CrmDbContext _db;
    private readonly IPasswordHasher<Staff> _hasher;
    private readonly IConfiguration _config;
    private readonly ILogger<AccountController> _logger;

    public AccountController(CrmDbContext db, IPasswordHasher<Staff> hasher,
                             IConfiguration config, ILogger<AccountController> logger)
    {
        _db = db;
        _hasher = hasher;
        _config = config;
        _logger = logger;
    }

    [HttpGet]
    public IActionResult Login(string? returnUrl = null)
    {
        // Đã đăng nhập rồi thì về trang chủ
        if (User.Identity?.IsAuthenticated == true)
        {
            return RedirectToAction("Index", "Home");
        }
        ViewData["ReturnUrl"] = returnUrl;
        return View(new LoginViewModel());
    }

    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Login(LoginViewModel model, string? returnUrl = null)
    {
        ViewData["ReturnUrl"] = returnUrl;

        // Trường rỗng: báo thiếu, KHÔNG ghi LoginAttempts (UC-01, ngoại lệ 2a)
        if (!ModelState.IsValid)
        {
            return View(model);
        }

        // LoginAttempts.UsernameTried là varchar(50): cắt bớt để không vỡ cột khi ai đó gõ chuỗi dài
        string tenThu = CatNgan(model.Username, 50);

        try
        {
            // Bước 1: tìm nhân viên theo tên đăng nhập (có thể null)
            var staff = await _db.Staff.FirstOrDefaultAsync(s => s.Username == model.Username);

            // Bước 2: tên này đang bị tạm khóa chưa? Kiểm TRƯỚC khi đối chiếu mật khẩu,
            // nên đang khóa thì kể cả gõ đúng mật khẩu vẫn bị từ chối (UC-01, bước 3a)
            if (await DangBiKhoaAsync(tenThu))
            {
                await GhiLanThuAsync(tenThu, false, LyDoBiKhoa, staff?.StaffId);
                return BaoLoiChung(model);
            }

            // Bước 3: xác định lý do thất bại (nếu có)
            string? lyDoThatBai = null;
            if (staff == null)
            {
                lyDoThatBai = LyDoKhongCoTen;
            }
            else if (!staff.IsActive)
            {
                lyDoThatBai = LyDoBiVoHieu;
            }
            else
            {
                var ketQua = _hasher.VerifyHashedPassword(staff, staff.PasswordHash, model.Password);
                if (ketQua == PasswordVerificationResult.Failed)
                {
                    lyDoThatBai = LyDoSaiMatKhau;
                }
            }

            if (lyDoThatBai != null)
            {
                await GhiLanThuAsync(tenThu, false, lyDoThatBai, staff?.StaffId);
                return BaoLoiChung(model);
            }

            // Bước 4: đúng hết. Lấy tên vai trò để đưa vào cookie
            string roleName = await _db.Roles
                .Where(r => r.RoleId == staff!.RoleId)
                .Select(r => r.RoleName)
                .FirstAsync();

            // Ghi nhật ký TRƯỚC khi tạo phiên: nếu ghi lỗi (mất SQL Server) thì nhảy xuống catch
            // và KHÔNG có phiên (UC-01, ngoại lệ 4b)
            await GhiLanThuAsync(tenThu, true, null, staff!.StaffId);
            await _db.WriteAuditAsync(staff.StaffId, "Login", "Staff", staff.StaffId.ToString());

            var claims = new List<Claim>
            {
                new Claim(ClaimTypes.NameIdentifier, staff.StaffId.ToString()),
                new Claim(ClaimTypes.Name, staff.Username),
                new Claim("FullName", staff.FullName),
                new Claim(ClaimTypes.Role, roleName)
            };
            var identity = new ClaimsIdentity(claims, CookieAuthenticationDefaults.AuthenticationScheme);
            await HttpContext.SignInAsync(
                CookieAuthenticationDefaults.AuthenticationScheme,
                new ClaimsPrincipal(identity));

            // Chỉ chuyển hướng tới địa chỉ nội bộ, chặn open redirect
            if (!string.IsNullOrEmpty(returnUrl) && Url.IsLocalUrl(returnUrl))
            {
                return LocalRedirect(returnUrl);
            }
            return RedirectToAction("Index", "Home");
        }
        catch (Exception ex)
        {
            // Mất SQL Server hoặc lỗi bất ngờ: ghi log kỹ thuật, báo lỗi hệ thống, KHÔNG tạo phiên
            _logger.LogError(ex, "Lỗi hệ thống khi đăng nhập");
            ModelState.AddModelError(string.Empty, "Hệ thống đang gặp sự cố tạm thời, hãy thử lại sau.");
            return View(model);
        }
    }

    // Đăng xuất bằng POST + antiforgery, không dùng GET
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Logout()
    {
        // Ghi audit TRƯỚC khi xóa cookie, vì sau đó không còn biết ai đăng xuất
        var idText = User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        if (int.TryParse(idText, out var staffId))
            await _db.WriteAuditAsync(staffId, "Logout", "Staff", staffId.ToString());

        await HttpContext.SignOutAsync(CookieAuthenticationDefaults.AuthenticationScheme);
        return RedirectToAction(nameof(Login));
    }

    // Trang hiện khi đã đăng nhập nhưng vai trò không đủ quyền
    [HttpGet]
    public IActionResult AccessDenied()
    {
        return View();
    }

    // ---------------------------------------------------------------
    // Hàm phụ
    // ---------------------------------------------------------------

    // Trả về trang Login kèm câu báo lỗi chung
    private IActionResult BaoLoiChung(LoginViewModel model)
    {
        ModelState.AddModelError(string.Empty, CauBaoLoiChung);
        return View(model);
    }

    // Ghi một dòng vào LoginAttempts. KHÔNG có tham số mật khẩu.
    private async Task GhiLanThuAsync(string tenThu, bool thanhCong, string? lyDoThatBai, int? staffId)
    {
        string? ip = HttpContext.Connection.RemoteIpAddress?.ToString();

        _db.LoginAttempts.Add(new LoginAttempt
        {
            UsernameTried = tenThu,
            AttemptedAt = DateTime.Now,   // cùng kiểu giờ với AuditLog.OccurredAt
            IsSuccess = thanhCong,
            FailReason = lyDoThatBai,     // NULL khi thành công (CHECK bắt buộc)
            StaffId = staffId,            // NULL khi tên không tồn tại
            ClientIp = ip == null ? null : CatNgan(ip, 45)
        });
        await _db.SaveChangesAsync();
    }

    // Tên này đã sai >= N lần trong M phút gần nhất chưa?
    // Chỉ đếm UnknownUser và WrongPassword; không đếm Inactive và Locked.
    // Nếu giữa chừng tên này từng đăng nhập ĐÚNG thì chỉ đếm các lần sai SAU lần đúng đó.
    private async Task<bool> DangBiKhoaAsync(string tenThu)
    {
        int soLanToiDa = _config.GetValue<int>("Login:MaxFailedAttempts", 5);
        int soPhutKhoa = _config.GetValue<int>("Login:LockoutMinutes", 15);

        DateTime moc = DateTime.Now.AddMinutes(-soPhutKhoa);

        // Lần đăng nhập đúng gần nhất của tên này (null nếu chưa có)
        DateTime? lanDungGanNhat = await _db.LoginAttempts
            .Where(a => a.UsernameTried == tenThu && a.IsSuccess)
            .MaxAsync(a => (DateTime?)a.AttemptedAt);

        if (lanDungGanNhat.HasValue && lanDungGanNhat.Value > moc)
        {
            moc = lanDungGanNhat.Value;
        }

        int soLanSai = await _db.LoginAttempts.CountAsync(a =>
            a.UsernameTried == tenThu
            && !a.IsSuccess
            && (a.FailReason == LyDoKhongCoTen || a.FailReason == LyDoSaiMatKhau)
            && a.AttemptedAt > moc);

        return soLanSai >= soLanToiDa;
    }

    private static string CatNgan(string text, int doDaiToiDa)
    {
        return text.Length <= doDaiToiDa ? text : text.Substring(0, doDaiToiDa);
    }
}