using System;
using System.Collections.Generic;

namespace CrmChurn.Web.Models;

public partial class ChurnPrediction
{
    public long PredictionId { get; set; }

    public int ModelVersionId { get; set; }

    public string? CustomerId { get; set; }

    public DateTime PredictionTime { get; set; }

    public decimal Probability { get; set; }

    public string RiskLevel { get; set; } = null!;

    public string? InputJson { get; set; }

    public string? TopFactorsJson { get; set; }

    public virtual Customer? Customer { get; set; }

    public virtual ModelVersion ModelVersion { get; set; } = null!;
}
