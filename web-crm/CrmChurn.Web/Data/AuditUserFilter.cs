using System.Security.Claims;
using Microsoft.AspNetCore.Mvc.Filters;

namespace CrmChurn.Web.Data;

// Mỗi request: lấy StaffId từ claim đăng nhập rồi gán cho DbContext (cùng một instance trong request)
public sealed class AuditUserFilter : IAsyncActionFilter
{
    private readonly CrmDbContext _db;
    public AuditUserFilter(CrmDbContext db) => _db = db;

    public Task OnActionExecutionAsync(ActionExecutingContext context, ActionExecutionDelegate next)
    {
        var idText = context.HttpContext.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        _db.AuditStaffId = int.TryParse(idText, out var id) ? id : null;   // không đăng nhập => null => không audit
        return next();
    }
}