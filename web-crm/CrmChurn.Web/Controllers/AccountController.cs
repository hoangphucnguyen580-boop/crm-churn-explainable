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
    private readonly CrmDbContext _db;
    private readonly IPasswordHasher<Staff> _hasher;

    public AccountController(CrmDbContext db, IPasswordHasher<Staff> hasher)
    {
        _db = db;
        _hasher = hasher;
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
        if (!ModelState.IsValid)
        {
            return View(model);
        }

        // Tìm nhân viên theo tên đăng nhập
        var staff = await _db.Staff.FirstOrDefaultAsync(s => s.Username == model.Username);

        // Sai tên, sai mật khẩu hoặc tài khoản bị khóa đều báo CÙNG một câu,
        // để người ngoài không dò được tên đăng nhập nào tồn tại
        bool dangNhapDung = false;
        if (staff != null && staff.IsActive)
        {
            var ketQua = _hasher.VerifyHashedPassword(staff, staff.PasswordHash, model.Password);
            dangNhapDung = ketQua != PasswordVerificationResult.Failed;
        }
        if (!dangNhapDung)
        {
            ModelState.AddModelError(string.Empty, "Tên đăng nhập hoặc mật khẩu không đúng.");
            return View(model);
        }

        // Lấy tên vai trò để đưa vào cookie (kiểm quyền ở Action dựa vào claim này)
        string roleName = await _db.Roles
            .Where(r => r.RoleId == staff!.RoleId)
            .Select(r => r.RoleName)
            .FirstAsync();

        var claims = new List<Claim>
        {
            new Claim(ClaimTypes.NameIdentifier, staff!.StaffId.ToString()),
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

    // Đăng xuất bằng POST + antiforgery, không dùng GET
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Logout()
    {
        await HttpContext.SignOutAsync(CookieAuthenticationDefaults.AuthenticationScheme);
        return RedirectToAction(nameof(Login));
    }

    // Trang hiện khi đã đăng nhập nhưng vai trò không đủ quyền
    [HttpGet]
    public IActionResult AccessDenied()
    {
        return View();
    }
}