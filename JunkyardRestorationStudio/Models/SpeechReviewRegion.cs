namespace JunkyardRestorationStudio.Models;

public class SpeechReviewRegion
{
    public int Id { get; set; }
    public double Start { get; set; }
    public double End { get; set; }
    public int[] SubtitleIds { get; set; } = [];
    public string Text { get; set; } = "";
    public string BoundaryStartSource { get; set; } = "";
    public string BoundaryEndSource { get; set; } = "";
    public string Quality { get; set; } = "";
    public string Speaker { get; set; } = "";
    public string SpeakerConfidence { get; set; } = "";
    public string Notes { get; set; } = "";
}

public class SpeechReviewDecision
{
    public int Id { get; set; }
    public double OriginalStart { get; set; }
    public double OriginalEnd { get; set; }
    public double Start { get; set; }
    public double End { get; set; }
    public string Quality { get; set; } = "";
    public string Speaker { get; set; } = "";
    public string SpeakerConfidence { get; set; } = "";
    public string Notes { get; set; } = "";
}
