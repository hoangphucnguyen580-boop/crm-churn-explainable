using System;
using System.Collections.Generic;

namespace CrmChurn.Web.Models;

public partial class CustomerContract
{
    public long ContractRecordId { get; set; }

    public string CustomerId { get; set; } = null!;

    public int? UpdatedByStaffId { get; set; }

    public DateTime EffectiveFrom { get; set; }

    public DateTime? EffectiveTo { get; set; }

    public string PhoneService { get; set; } = null!;

    public string MultipleLines { get; set; } = null!;

    public string InternetService { get; set; } = null!;

    public string OnlineSecurity { get; set; } = null!;

    public string OnlineBackup { get; set; } = null!;

    public string DeviceProtection { get; set; } = null!;

    public string TechSupport { get; set; } = null!;

    public string StreamingTv { get; set; } = null!;

    public string StreamingMovies { get; set; } = null!;

    public string Contract { get; set; } = null!;

    public string PaperlessBilling { get; set; } = null!;

    public string PaymentMethod { get; set; } = null!;

    public decimal MonthlyCharges { get; set; }

    public virtual Customer Customer { get; set; } = null!;

    public virtual Staff? UpdatedByStaff { get; set; }
}
