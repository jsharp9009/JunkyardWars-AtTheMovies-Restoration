using JunkyardRestorationStudio.Models;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace JunkyardRestorationStudio.Services;

public class ChoiceRepository
{
    private readonly JsonSerializerOptions options =
        new()
        {
            WriteIndented = true
        };

    public Dictionary<int, Choice> Load(string file)
    {
        if (!File.Exists(file))
            return new Dictionary<int, Choice>();

        var list =
            JsonSerializer.Deserialize<List<Choice>>(
                File.ReadAllText(file),
                options)
            ?? new List<Choice>();

        return list.ToDictionary(c => c.SegmentId);
    }

    public void Save(
    string file,
    IEnumerable<Choice> choices)
    {
        string? directory = Path.GetDirectoryName(file);

        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllText(
            file,
            JsonSerializer.Serialize(
                choices.OrderBy(c => c.SegmentId),
                options));
    }
}