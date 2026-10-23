using System;
using System.Collections.Generic;

namespace CrmChurn.Web.Models;

public partial class Interaction
{
    public long InteractionId { get; set; }

    public int? StaffId { get; set; }

    public string CustomerId { get; set; } = null!;

    public DateTime InteractionDate { get; set; }

    public string Channel { get; set; } = null!;

    public string InteractionType { get; set; } = null!;

    public string? Description { get; set; }

    public string? Result { get; set; }

    public bool IsSimulated { get; set; }

    public virtual Customer Customer { get; set; } = null!;

    public virtual Staff? Staff { get; set; }
}
