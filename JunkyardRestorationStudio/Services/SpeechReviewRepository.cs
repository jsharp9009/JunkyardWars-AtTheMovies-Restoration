using JunkyardRestorationStudio.Models;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace JunkyardRestorationStudio.Services;

public class SpeechReviewRepository
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true
    };

    public List<SpeechReviewRegion> LoadMap(string path)
    {
        if (!File.Exists(path))
            throw new FileNotFoundException("Speech review map was not found.", path);

        var json = File.ReadAllText(path);
        using var document = JsonDocument.Parse(json);

        if (document.RootElement.ValueKind == JsonValueKind.Array)
            return JsonSerializer.Deserialize<List<SpeechReviewRegion>>(json, JsonOptions) ?? [];

        if (document.RootElement.ValueKind == JsonValueKind.Object &&
            document.RootElement.TryGetProperty("regions", out var regions))
            return JsonSerializer.Deserialize<List<SpeechReviewRegion>>(regions.GetRawText(), JsonOptions) ?? [];

        throw new InvalidDataException("speech_review_map.json must contain an array of regions or an object with a 'regions' array.");
    }

    public List<SpeechEvidenceRegion> LoadEvidenceMap(string path)
    {
        if (!File.Exists(path))
            throw new FileNotFoundException("Speech evidence map was not found.", path);

        var json = File.ReadAllText(path);
        using var document = JsonDocument.Parse(json);

        if (document.RootElement.ValueKind != JsonValueKind.Object ||
            !document.RootElement.TryGetProperty("regions", out var regions))
            throw new InvalidDataException("speech_evidence_map.json must contain an object with a 'regions' array.");

        return JsonSerializer.Deserialize<List<SpeechEvidenceRegion>>(regions.GetRawText(), JsonOptions) ?? [];
    }

    public Dictionary<int, SpeechReviewDecision> LoadDecisions(string path)
    {
        if (!File.Exists(path))
            return new Dictionary<int, SpeechReviewDecision>();

        var decisions = JsonSerializer.Deserialize<List<SpeechReviewDecision>>(
            File.ReadAllText(path), JsonOptions) ?? [];

        return decisions.ToDictionary(x => x.Id);
    }

    public void SaveDecisions(string path, IEnumerable<SpeechReviewDecision> decisions)
    {
        var ordered = decisions.OrderBy(x => x.Id).ToList();
        File.WriteAllText(path, JsonSerializer.Serialize(ordered, JsonOptions));
    }
}
