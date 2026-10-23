using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Controllers;

// Trang TẠM để kiểm tra kết nối database ở T1; sẽ xóa khi làm xong trang khách hàng thật
public class DbCheckController : Controller
{
    private readonly CrmChurn.Web.Data.CrmDbContext _db;

    public DbCheckController(CrmChurn.Web.Data.CrmDbContext db)
    {
        _db = db;
    }

    public async Task<IActionResult> Index()
    {
        var lines = new List<string>();

        // Duyệt mọi bảng EF biết (lấy từ model nên không nhập tay tên bảng) và đếm số dòng
        foreach (var entityType in _db.Model.GetEntityTypes().OrderBy(e => e.GetTableName()))
        {
            var tableName = entityType.GetTableName();
            var rowCount = await _db.Database
                .SqlQueryRaw<int>("SELECT COUNT(*) AS [Value] FROM [" + tableName + "]")
                .SingleAsync();
            lines.Add(tableName + ": " + rowCount);
        }

        return Content(string.Join("\n", lines), "text/plain; charset=utf-8");
    }
}