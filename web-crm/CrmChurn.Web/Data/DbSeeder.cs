// ============================================================
// File: Data/DbSeeder.cs
// Mục đích: Tạo 3 vai trò và 3 tài khoản demo khi bảng Staff còn trống.
//           Mật khẩu đọc từ user-secrets (Seed:DemoPassword), được băm
//           bằng PasswordHasher của ASP.NET, KHÔNG lưu mật khẩu thuần (Y-06).
// ============================================================
using CrmChurn.Web.Models;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Data;

public static class DbSeeder
{
    // Ba vai trò theo kế hoạch Mục 7.1. KHÔNG gán cứng RoleID, để identity tự sinh.
    private static readonly string[] RoleNames = { "Admin", "Manager", "Agent" };

    // Ba tài khoản demo, mỗi vai trò một tài khoản
    private static readonly (string Username, string FullName, string RoleName)[] DemoAccounts =
    {
        ("admin",   "Quản trị viên (demo)",    "Admin"),
        ("manager", "Quản lý CSKH (demo)",     "Manager"),
        ("agent",   "Nhân viên CSKH (demo)",   "Agent"),
    };

    public static async Task SeedAsync(IServiceProvider services)
    {
        // Seeder chạy lúc khởi động, chưa có request nên tự tạo scope để lấy DbContext
        using var scope = services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<CrmDbContext>();
        var config = scope.ServiceProvider.GetRequiredService<IConfiguration>();
        var hasher = scope.ServiceProvider.GetRequiredService<IPasswordHasher<Staff>>();
        var logger = scope.ServiceProvider.GetRequiredService<ILoggerFactory>().CreateLogger("DbSeeder");

        // Bước 1: thêm vai trò còn thiếu (chạy lại nhiều lần không bị trùng)
        foreach (var roleName in RoleNames)
        {
            bool daCo = await db.Roles.AnyAsync(r => r.RoleName == roleName);
            if (!daCo)
            {
                db.Roles.Add(new Role { RoleName = roleName });
            }
        }
        await db.SaveChangesAsync();

        // Bước 2: chỉ seed tài khoản khi bảng Staff đang trống
        if (await db.Staff.AnyAsync())
        {
            return;
        }

        // Bước 3: lấy mật khẩu demo từ user-secrets; không có thì bỏ qua, KHÔNG dùng mật khẩu mặc định
        string? matKhauDemo = config["Seed:DemoPassword"];
        if (string.IsNullOrWhiteSpace(matKhauDemo))
        {
            logger.LogWarning("Chưa có Seed:DemoPassword trong user-secrets, bỏ qua seed tài khoản Staff.");
            return;
        }

        // Bước 4: tạo tài khoản, băm mật khẩu bằng PasswordHasher
        var roleIdTheoTen = await db.Roles.ToDictionaryAsync(r => r.RoleName, r => r.RoleId);
        foreach (var taiKhoan in DemoAccounts)
        {
            var staff = new Staff
            {
                RoleId = roleIdTheoTen[taiKhoan.RoleName],
                FullName = taiKhoan.FullName,
                Username = taiKhoan.Username,
                IsActive = true
            };
            staff.PasswordHash = hasher.HashPassword(staff, matKhauDemo);
            db.Staff.Add(staff);
        }
        await db.SaveChangesAsync();

        logger.LogInformation("Đã seed {Count} tài khoản Staff.", DemoAccounts.Length);
    }
}