using JunkyardRestorationStudio.Models;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace JunkyardRestorationStudio.Services;

public class ReviewRepository
{
    public List<ReviewSegment> Load(string reviewFolder)
    {
        var segments = new List<ReviewSegment>();

        foreach (string folder in Directory.GetDirectories(reviewFolder))
        {
            string metadataPath =
                Path.Combine(folder, "metadata.json");

            string comparisonPath =
                Path.Combine(folder, "comparison.json");

            if (!File.Exists(metadataPath) ||
                !File.Exists(comparisonPath))
            {
                continue;
            }

            var options = new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            };

            MetadataFile metadata =
                JsonSerializer.Deserialize<MetadataFile>(
                    File.ReadAllText(metadataPath), options )!;

            ComparisonFile comparison =
                JsonSerializer.Deserialize<ComparisonFile>(
                    File.ReadAllText(comparisonPath), options )!;


            var segment = new ReviewSegment
            {
                Id = metadata.Id,
                Start = metadata.Start,
                End = metadata.End,
                Duration = metadata.Duration,

                Priority = comparison.Priority,
                Spread = comparison.Statistics.Spread,

                Folder = folder,

                MetadataFile = metadataPath,
                ComparisonFile = comparisonPath
            };

            if (comparison.PairwiseCorrelation != null)
            {
                foreach (var pair in comparison.PairwiseCorrelation)
                {
                    // key is something like "20s_30s"
                    string[] runs = pair.Key.Split('_');

                    if (runs.Length != 2)
                        continue;

                    segment.Comparisons.Add(new PairwiseComparison
                    {
                        Run1 = runs[0],
                        Run2 = runs[1],
                        Correlation = pair.Value
                    });
                }

                segment.BuildAnalysis();
            }

            segments.Add(segment);


        }


        return segments
    .OrderByDescending(s => PriorityValue(s.Priority))
    .ThenByDescending(s => s.Spread)
    .ThenBy(s => s.Start)
    .ToList();
    }

    private static int PriorityValue(string priority)
    {
        return priority switch
        {
            "High" => 3,
            "Medium" => 2,
            "Low" => 1,
            _ => 0
        };
    }
}