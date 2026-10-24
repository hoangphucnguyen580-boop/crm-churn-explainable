using System.Text;
using CrmChurn.Web.Data;
using CrmChurn.Web.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Controllers;

// TẠM: chạy thử audit, xóa trước khi nộp. Chỉ Admin vào được.
[Authorize(Roles = "Admin")]
public class TestAuditController : Controller
{
    private readonly CrmDbContext _db;
    public TestAuditController(CrmDbContext db) => _db = db;

    public async Task<IActionResult> Chay()
    {
        var truoc = await _db.AuditLogs.CountAsync();

        // 1) RiskConfig (khóa chữ): Thêm -> Sửa -> Xóa
        var cfg = new RiskConfig { ConfigKey = "ZZ_TestAudit", ConfigValue = "1", UpdatedAt = DateTime.Now };
        _db.RiskConfigs.Add(cfg); await _db.SaveChangesAsync();
        cfg.ConfigValue = "2"; await _db.SaveChangesAsync();
        _db.RiskConfigs.Remove(cfg); await _db.SaveChangesAsync();

        // 2) Staff: kiểm che PasswordHash (Thêm -> Sửa mật khẩu -> Xóa)
        var roleId = await _db.Roles.Where(r => r.RoleName == "Agent").Select(r => r.RoleId).FirstAsync();
        var nv = new Staff
        {
            RoleId = roleId,
            FullName = "ZZ audit",
            Username = "zz_audit",
            PasswordHash = "mat_khau_gia_123",
            IsActive = true
        };
        _db.Staff.Add(nv); await _db.SaveChangesAsync();
        nv.PasswordHash = "mat_khau_gia_456"; await _db.SaveChangesAsync();
        _db.Staff.Remove(nv); await _db.SaveChangesAsync();

        // 3) Interaction (khóa identity): RecordKey của dòng Insert phải là số thật, không âm
        var customerId = await _db.Customers.Select(c => c.CustomerId).FirstAsync();
        var it = new Interaction
        {
            CustomerId = customerId,
            InteractionDate = DateTime.Now,
            Channel = "Web",
            InteractionType = "Inquiry",
            Description = "ZZ test audit",
            IsSimulated = false
        };
        _db.Interactions.Add(it); await _db.SaveChangesAsync();
        _db.Interactions.Remove(it); await _db.SaveChangesAsync();

        // 4) Không có người dùng => KHÔNG ghi audit
        var nguoiDung = _db.AuditStaffId;
        _db.AuditStaffId = null;
        var cfg2 = new RiskConfig { ConfigKey = "ZZ_KhongNguoiDung", ConfigValue = "1", UpdatedAt = DateTime.Now };
        _db.RiskConfigs.Add(cfg2); await _db.SaveChangesAsync();
        _db.RiskConfigs.Remove(cfg2); await _db.SaveChangesAsync();
        _db.AuditStaffId = nguoiDung;

        var sau = await _db.AuditLogs.CountAsync();
        var dong = (await _db.AuditLogs.OrderByDescending(a => a.AuditId).Take(sau - truoc).ToListAsync())
                   .OrderBy(a => a.AuditId).ToList();

        var sb = new StringBuilder();
        sb.AppendLine($"Số dòng audit trước {truoc}, sau {sau}, tăng {sau - truoc} (kỳ vọng 8)");
        sb.AppendLine("Lộ mật khẩu giả trong audit: " +
            (dong.Any(d => ((d.OldValues ?? "") + (d.NewValues ?? "")).Contains("mat_khau_gia")) ? "CÓ (SAI)" : "không (ĐÚNG)"));
        sb.AppendLine();
        foreach (var d in dong)
            sb.AppendLine($"{d.AuditId} | Staff {d.StaffId} | {d.Action} | {d.TableName} | khóa {d.RecordKey} | cũ {d.OldValues} | mới {d.NewValues}");
        return Content(sb.ToString(), "text/plain; charset=utf-8");
    }
}