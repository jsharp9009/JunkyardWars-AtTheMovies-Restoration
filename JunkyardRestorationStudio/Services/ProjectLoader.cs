using JunkyardRestorationStudio.Models;
using System;
using System.IO;
using System.Text.Json;

namespace JunkyardRestorationStudio.Services;

public static class ProjectLoader
{
    public static ProjectSettings Load(string file)
    {
        if (!File.Exists(file))
            throw new FileNotFoundException($"Could not find '{file}'");

        string json = File.ReadAllText(file);

        Console.WriteLine("JSON:");
        Console.WriteLine(json);

        var options = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true
        };

        ProjectSettings? settings =
            JsonSerializer.Deserialize<ProjectSettings>(json, options);

        if (settings == null)
            throw new Exception("Deserialize returned null.");

        Console.WriteLine($"Name: {settings.Name}");
        Console.WriteLine($"ReviewFolder: {settings.ReviewFolder}");
        Console.WriteLine($"Speaker: {settings.Speaker}");
        Console.WriteLine($"ChunkRuns: {settings.ChunkRuns.Count}");

        return settings;
    }
}