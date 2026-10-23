using CrmChurn.Web.Data;
using CrmChurn.Web.Models;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc.Authorization;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

// Bộ lọc toàn cục: MỌI Action đều yêu cầu đăng nhập, trừ chỗ gắn [AllowAnonymous].
// Quên gắn [Authorize] thì mặc định vẫn bị chặn (R-11).
builder.Services.AddControllersWithViews(options =>
{
    options.Filters.Add(new AuthorizeFilter());
});

// Nối EF Core với SQL Server; chuỗi kết nối lấy từ user-secrets, không viết cứng ở đây
builder.Services.AddDbContext<CrmDbContext>(options =>
    options.UseSqlServer(builder.Configuration.GetConnectionString("Default")));

// Đăng nhập bằng cookie
builder.Services
    .AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
    .AddCookie(options =>
    {
        options.LoginPath = "/Account/Login";
        options.LogoutPath = "/Account/Logout";
        options.AccessDeniedPath = "/Account/AccessDenied";
        options.ExpireTimeSpan = TimeSpan.FromHours(8);
        options.SlidingExpiration = true;
        options.Cookie.HttpOnly = true;
        options.Cookie.SecurePolicy = CookieSecurePolicy.Always;
    });

// Băm mật khẩu bằng PasswordHasher có sẵn của ASP.NET (Y-06)
builder.Services.AddScoped<IPasswordHasher<Staff>, PasswordHasher<Staff>>();

var app = builder.Build();

// Tạo vai trò và tài khoản demo nếu chưa có
await DbSeeder.SeedAsync(app.Services);

// Configure the HTTP request pipeline.
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Home/Error");
    // The default HSTS value is 30 days. You may want to change this for production scenarios, see https://aka.ms/aspnetcore-hsts.
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseRouting();

// Thứ tự bắt buộc: xác thực (ai đó) rồi mới phân quyền (được làm gì)
app.UseAuthentication();
app.UseAuthorization();

app.MapStaticAssets();

app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Home}/{action=Index}/{id?}")
    .WithStaticAssets();

app.Run();