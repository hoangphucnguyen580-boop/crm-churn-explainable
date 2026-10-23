using System;
using System.Collections.Generic;

namespace CrmChurn.Web.Models;

public partial class Staff
{
    public int StaffId { get; set; }

    public int RoleId { get; set; }

    public string FullName { get; set; } = null!;

    public string? Email { get; set; }

    public string Username { get; set; } = null!;

    public string PasswordHash { get; set; } = null!;

    public bool IsActive { get; set; }

    public virtual ICollection<AuditLog> AuditLogs { get; set; } = new List<AuditLog>();

    public virtual ICollection<CustomerContract> CustomerContracts { get; set; } = new List<CustomerContract>();

    public virtual ICollection<Interaction> Interactions { get; set; } = new List<Interaction>();

    public virtual ICollection<RiskConfig> RiskConfigs { get; set; } = new List<RiskConfig>();

    public virtual Role Role { get; set; } = null!;

    public virtual ICollection<Ticket> Tickets { get; set; } = new List<Ticket>();
}
