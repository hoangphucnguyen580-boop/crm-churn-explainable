using System;
using System.Collections.Generic;

namespace CrmChurn.Web.Models;

public partial class RiskConfig
{
    public string ConfigKey { get; set; } = null!;

    public int? UpdatedByStaffId { get; set; }

    public string ConfigValue { get; set; } = null!;

    public DateTime UpdatedAt { get; set; }

    public virtual Staff? UpdatedByStaff { get; set; }
}
