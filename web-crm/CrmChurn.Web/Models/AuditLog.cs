using System;
using System.Collections.Generic;

namespace CrmChurn.Web.Models;

public partial class AuditLog
{
    public long AuditId { get; set; }

    public int StaffId { get; set; }

    public string Action { get; set; } = null!;

    public string TableName { get; set; } = null!;

    public string RecordKey { get; set; } = null!;

    public string? OldValues { get; set; }

    public string? NewValues { get; set; }

    public DateTime OccurredAt { get; set; }

    public virtual Staff Staff { get; set; } = null!;
}
