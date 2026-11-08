using System;
using System.Collections.Generic;

namespace CrmChurn.Web.Models;

public partial class LoginAttempt
{
    public long AttemptId { get; set; }

    public int? StaffId { get; set; }

    public string UsernameTried { get; set; } = null!;

    public DateTime AttemptedAt { get; set; }

    public bool IsSuccess { get; set; }

    public string? FailReason { get; set; }

    public string? ClientIp { get; set; }

    public virtual Staff? Staff { get; set; }
}
