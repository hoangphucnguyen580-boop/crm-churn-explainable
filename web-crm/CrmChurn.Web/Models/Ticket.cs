using System;
using System.Collections.Generic;

namespace CrmChurn.Web.Models;

public partial class Ticket
{
    public long TicketId { get; set; }

    public int? AssignedStaffId { get; set; }

    public string CustomerId { get; set; } = null!;

    public DateTime CreatedAt { get; set; }

    public DateTime? ClosedAt { get; set; }

    public string Category { get; set; } = null!;

    public string Priority { get; set; } = null!;

    public string Status { get; set; } = null!;

    public string? Resolution { get; set; }

    public short? SatisfactionScore { get; set; }

    public bool IsSimulated { get; set; }

    public string? ReopenReason { get; set; }

    public virtual Staff? AssignedStaff { get; set; }

    public virtual Customer Customer { get; set; } = null!;
}
