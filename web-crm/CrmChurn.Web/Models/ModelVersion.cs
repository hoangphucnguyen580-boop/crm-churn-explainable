using System;
using System.Collections.Generic;

namespace CrmChurn.Web.Models;

public partial class ModelVersion
{
    public int ModelVersionId { get; set; }

    public string ModelName { get; set; } = null!;

    public string Version { get; set; } = null!;

    public DateTime TrainDate { get; set; }

    public decimal Threshold { get; set; }

    public string? MetricsJson { get; set; }

    public int? Seed { get; set; }

    public string? ConfigJson { get; set; }

    public string? DatasetHash { get; set; }

    public string? LibVersions { get; set; }

    public virtual ICollection<ChurnPrediction> ChurnPredictions { get; set; } = new List<ChurnPrediction>();
}
