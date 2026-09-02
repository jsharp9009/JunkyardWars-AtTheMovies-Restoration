using System.Collections.Generic;

namespace JunkyardRestorationStudio.Models;

public class ProjectSettings
{
    public string Name { get; set; } = "";

    public string ReviewFolder { get; set; } = "";

    public List<string> ChunkRuns { get; set; } = new();

    public int Speaker { get; set; }
}