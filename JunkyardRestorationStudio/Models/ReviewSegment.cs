using Avalonia.Media;
using Microsoft.VisualBasic;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace JunkyardRestorationStudio.Models;

public class ReviewSegment
{
    public int Id { get; set; }

    public double Start { get; set; }

    public double End { get; set; }

    public double Duration { get; set; }

    public string Priority { get; set; } = "";

    public double Spread { get; set; }

    public string Folder { get; set; } = "";

    public string MetadataFile { get; set; } = "";

    public string ComparisonFile { get; set; } = "";

    public Choice Choice { get; set; } = new();

    public string TimeDisplay =>
    TimeSpan.FromSeconds(Start)
        .ToString(@"hh\:mm\:ss\.fff");

    public string DurationDisplay =>
        $"{Duration:F2} sec";

    public string SpreadDisplay =>
        Spread.ToString("F3");

    public string Audio20 =>
    Path.Combine(Folder, "20s.wav");

    public string Audio30 =>
    Path.Combine(Folder, "30s.wav");

    public string Audio45 =>
        Path.Combine(Folder, "45s.wav");

    public string Audio60 =>
        Path.Combine(Folder, "60s.wav");

    public static IReadOnlyList<string> RunChoices =>
[
    "20s",
    "30s",
    "45s",
    "60s"
];

    public IBrush PriorityBrush =>
    Priority switch
    {
        "HIGH" => Brushes.Firebrick,
        "MEDIUM" => Brushes.DarkOrange,
        _ => Brushes.ForestGreen
    };

    public List<RunAnalysis> Analyses { get; } = new();

    public List<PairwiseComparison> Comparisons { get; } = new();

    public void BuildAnalysis()
    {
        Analyses.Clear();

        var totals = new Dictionary<string, double>();
        var counts = new Dictionary<string, int>();

        foreach (var comparison in Comparisons)
        {
            if (!totals.ContainsKey(comparison.Run1))
            {
                totals[comparison.Run1] = 0;
                counts[comparison.Run1] = 0;
            }

            if (!totals.ContainsKey(comparison.Run2))
            {
                totals[comparison.Run2] = 0;
                counts[comparison.Run2] = 0;
            }

            totals[comparison.Run1] += comparison.Correlation;
            totals[comparison.Run2] += comparison.Correlation;

            counts[comparison.Run1]++;
            counts[comparison.Run2]++;
        }

        foreach (var run in totals.Keys)
        {
            Analyses.Add(new RunAnalysis
            {
                RunName = run,
                Score = totals[run] / counts[run]
            });
        }

        UpdateAgreementLevels();
    }

    private void UpdateAgreementLevels()
    {
        if (Analyses.Count == 0)
            return;

        double mean = Analyses.Average(a => a.Score);

        double variance = Analyses
            .Select(a => Math.Pow(a.Score - mean, 2))
            .Average();

        double stdDev = Math.Sqrt(variance);

        foreach (var analysis in Analyses)
        {
            if (stdDev == 0)
            {
                analysis.Agreement = AgreementLevel.Good;
                continue;
            }

            double z = Math.Abs((mean - analysis.Score) / stdDev);

            analysis.Agreement =
                z >= 2
                    ? AgreementLevel.Outlier
                    : z >= 1
                        ? AgreementLevel.Warning
                        : AgreementLevel.Good;
        }

        Analyses.Sort((a, b) => Math.Abs((mean - b.Score) / stdDev).CompareTo(Math.Abs((mean - a.Score) / stdDev)));
    }
}