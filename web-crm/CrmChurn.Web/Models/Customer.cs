using System;
using System.Collections.Generic;

namespace CrmChurn.Web.Models;

public partial class Customer
{
    public string CustomerId { get; set; } = null!;

    public string? Gender { get; set; }

    public bool SeniorCitizen { get; set; }

    public bool? Partner { get; set; }

    public bool? Dependents { get; set; }

    public DateTime? EstimatedJoinDate { get; set; }

    public string CustomerStatus { get; set; } = null!;

    public DateTime CreatedAt { get; set; }

    public virtual ICollection<ChurnPrediction> ChurnPredictions { get; set; } = new List<ChurnPrediction>();

    public virtual ICollection<CustomerContract> CustomerContracts { get; set; } = new List<CustomerContract>();

    public virtual ICollection<CustomerSnapshot> CustomerSnapshots { get; set; } = new List<CustomerSnapshot>();

    public virtual ICollection<Interaction> Interactions { get; set; } = new List<Interaction>();

    public virtual ICollection<Ticket> Tickets { get; set; } = new List<Ticket>();
}
