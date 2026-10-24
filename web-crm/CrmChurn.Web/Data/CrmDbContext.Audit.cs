using System.Globalization;
using System.Text.Encodings.Web;
using System.Text.Json;
using CrmChurn.Web.Models;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.ChangeTracking;

namespace CrmChurn.Web.Data;

// Phần mở rộng của CrmDbContext (file scaffold KHÔNG sửa tay).
// Tự ghi AuditLog khi Thêm/Sửa/Xóa (D-08, Y-07).
public partial class CrmDbContext
{
    // Người đang thao tác (StaffID). AuditUserFilter gán ở mỗi request.
    // null = không có người dùng (seeder, trang Login...) => KHÔNG ghi audit (AuditLog.StaffID là NOT NULL).
    public int? AuditStaffId { get; set; }

    // Chỉ audit 7 bảng theo kế hoạch Mục 6.2. KHÔNG có AuditLog (tránh lặp vô hạn).
    private static readonly HashSet<Type> AuditedTypes = new()
    {
        typeof(Customer), typeof(CustomerContract), typeof(Interaction),
        typeof(Ticket), typeof(RiskConfig), typeof(Staff), typeof(ChurnPrediction)
    };

    // Cột bị che: chỉ ghi "***", không bao giờ ghi giá trị thật (R-06)
    private static readonly HashSet<string> MaskedProperties = new() { "PasswordHash" };

    // Giữ tiếng Việt đọc được trong JSON, không đổi thành \uXXXX
    private static readonly JsonSerializerOptions AuditJson = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping
    };

    private sealed class PendingAudit
    {
        public EntityEntry Entry = null!;
        public string Action = "";
        public string TableName = "";
        public string? Key;
        public string? OldValues;
        public string? NewValues;
    }

    // ---------- Bước 1: gom thay đổi TRƯỚC khi lưu ----------
    private List<PendingAudit> CollectAudit()
    {
        var result = new List<PendingAudit>();
        ChangeTracker.DetectChanges();

        foreach (var entry in ChangeTracker.Entries().ToList())
        {
            if (!AuditedTypes.Contains(entry.Entity.GetType())) continue;
            if (entry.State is not (EntityState.Added or EntityState.Modified or EntityState.Deleted)) continue;

            var pending = new PendingAudit
            {
                Entry = entry,
                TableName = entry.Metadata.GetTableName() ?? entry.Metadata.ClrType.Name
            };

            if (entry.State == EntityState.Added)
            {
                // Insert: NewValues và khóa chỉ có giá trị thật SAU khi lưu (identity, DEFAULT) => làm ở bước 3
                pending.Action = "Insert";
            }
            else
            {
                var oldValues = new Dictionary<string, object?>();
                var newValues = new Dictionary<string, object?>();
                foreach (var prop in entry.Properties)
                {
                    var name = prop.Metadata.Name;
                    var masked = MaskedProperties.Contains(name);
                    if (entry.State == EntityState.Deleted)
                    {
                        oldValues[name] = masked ? "***" : prop.OriginalValue;
                    }
                    else if (prop.IsModified)   // Update: chỉ ghi cột có đổi (trước/sau)
                    {
                        oldValues[name] = masked ? "***" : prop.OriginalValue;
                        newValues[name] = masked ? "***" : prop.CurrentValue;
                    }
                }

                if (entry.State == EntityState.Modified && newValues.Count == 0) continue; // không cột nào đổi

                pending.Action = entry.State == EntityState.Deleted ? "Delete" : "Update";
                pending.Key = BuildKey(entry, original: true);
                pending.OldValues = oldValues.Count > 0 ? JsonSerializer.Serialize(oldValues, AuditJson) : null;
                pending.NewValues = newValues.Count > 0 ? JsonSerializer.Serialize(newValues, AuditJson) : null;
            }

            result.Add(pending);
        }
        return result;
    }

    private static string BuildKey(EntityEntry entry, bool original)
    {
        var primaryKey = entry.Metadata.FindPrimaryKey();
        if (primaryKey is null) return "";
        var parts = primaryKey.Properties.Select(p =>
        {
            var property = entry.Property(p.Name);
            return Convert.ToString(original ? property.OriginalValue : property.CurrentValue,
                                    CultureInfo.InvariantCulture);
        });
        var key = string.Join("|", parts);
        return key.Length > 50 ? key[..50] : key;   // RecordKey là varchar(50)
    }

    // ---------- Bước 3: sau lần lưu 1, thêm dòng AuditLog vào context ----------
    private void AddAuditRows(List<PendingAudit> pending)
    {
        foreach (var item in pending)
        {
            if (item.Action == "Insert")
            {
                // Lúc này ID identity và giá trị DEFAULT đã có thật
                item.Key = BuildKey(item.Entry, original: false);
                var values = new Dictionary<string, object?>();
                foreach (var prop in item.Entry.Properties)
                {
                    var name = prop.Metadata.Name;
                    values[name] = MaskedProperties.Contains(name) ? "***" : prop.CurrentValue;
                }
                item.NewValues = JsonSerializer.Serialize(values, AuditJson);
            }

            AuditLogs.Add(new AuditLog
            {
                StaffId = AuditStaffId!.Value,
                Action = item.Action,
                TableName = item.TableName,
                RecordKey = item.Key ?? "",
                OldValues = item.OldValues,
                NewValues = item.NewValues,
                OccurredAt = DateTime.Now
            });
        }
    }

    // ---------- Ghi đè SaveChanges (bản đồng bộ) ----------
    public override int SaveChanges(bool acceptAllChangesOnSuccess)
    {
        if (AuditStaffId is null) return base.SaveChanges(acceptAllChangesOnSuccess);

        var pending = CollectAudit();
        if (pending.Count == 0) return base.SaveChanges(acceptAllChangesOnSuccess);

        // Đã có giao dịch bên ngoài thì dùng luôn; chưa có thì tự mở
        var ownTransaction = Database.CurrentTransaction is null ? Database.BeginTransaction() : null;
        try
        {
            var affected = base.SaveChanges(acceptAllChangesOnSuccess);   // lần 1: dữ liệu thật
            AddAuditRows(pending);
            base.SaveChanges(acceptAllChangesOnSuccess);                  // lần 2: dòng audit
            ownTransaction?.Commit();
            return affected;
        }
        finally
        {
            ownTransaction?.Dispose();   // chưa Commit mà Dispose thì tự rollback
        }
    }

    // ---------- Ghi đè SaveChangesAsync (bản bất đồng bộ, web dùng bản này) ----------
    public override async Task<int> SaveChangesAsync(bool acceptAllChangesOnSuccess,
                                                     CancellationToken cancellationToken = default)
    {
        if (AuditStaffId is null)
            return await base.SaveChangesAsync(acceptAllChangesOnSuccess, cancellationToken);

        var pending = CollectAudit();
        if (pending.Count == 0)
            return await base.SaveChangesAsync(acceptAllChangesOnSuccess, cancellationToken);

        var ownTransaction = Database.CurrentTransaction is null
            ? await Database.BeginTransactionAsync(cancellationToken) : null;
        try
        {
            var affected = await base.SaveChangesAsync(acceptAllChangesOnSuccess, cancellationToken);
            AddAuditRows(pending);
            await base.SaveChangesAsync(acceptAllChangesOnSuccess, cancellationToken);
            if (ownTransaction is not null) await ownTransaction.CommitAsync(cancellationToken);
            return affected;
        }
        finally
        {
            if (ownTransaction is not null) await ownTransaction.DisposeAsync();
        }
    }

    // ---------- Ghi audit đăng nhập / đăng xuất (không đi qua ChangeTracker) ----------
    public async Task WriteAuditAsync(int staffId, string action, string tableName, string recordKey)
    {
        AuditLogs.Add(new AuditLog
        {
            StaffId = staffId,
            Action = action,          // 'Login' hoặc 'Logout' (cột varchar(10))
            TableName = tableName,
            RecordKey = recordKey,
            OccurredAt = DateTime.Now
        });
        await SaveChangesAsync();
    }
}