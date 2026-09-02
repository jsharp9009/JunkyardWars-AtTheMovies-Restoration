using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace JunkyardRestorationStudio.Models;

public class ComparisonFile
{
    public string Priority { get; set; } = "";

    public Statistics Statistics { get; set; } = new();

    [JsonPropertyName("pairwise_correlation")]
    public Dictionary<string, double> PairwiseCorrelation { get; set; } = new();
}

public class Statistics
{
    public double Min { get; set; }

    public double Max { get; set; }

    public double Average { get; set; }

    public double Spread { get; set; }
}