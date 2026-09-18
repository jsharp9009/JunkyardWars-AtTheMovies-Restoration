using System.Collections.Generic;
using System.Text.Json.Serialization;
using JunkyardRestorationStudio.ViewModels;

namespace JunkyardRestorationStudio.Models;

public class SpeechEvidenceRegion
{
    public int Id { get; set; }
    public double Start { get; set; }
    public double End { get; set; }
    public double Duration { get; set; }

    [JsonPropertyName("subtitle_ids")]
    public int[] SubtitleIds { get; set; } = [];

    [JsonPropertyName("translated_region_text")]
    public string TranslatedRegionText { get; set; } = "";

    public EvidenceBoundary Boundary { get; set; } = new();
    [JsonPropertyName("review_metadata")]
    public EvidenceReviewMetadata ReviewMetadata { get; set; } = new();
    [JsonPropertyName("russian_evidence")]
    public RussianEvidence RussianEvidence { get; set; } = new();
    [JsonPropertyName("recovered_english_asr")]
    public RecoveredEnglishAsr RecoveredEnglishAsr { get; set; } = new();
    [JsonPropertyName("evidence_flags")]
    public EvidenceFlags EvidenceFlags { get; set; } = new();
}

public class EvidenceBoundary
{
    [JsonPropertyName("start_source")]
    public string StartSource { get; set; } = "";
    [JsonPropertyName("end_source")]
    public string EndSource { get; set; } = "";
}

public class EvidenceReviewMetadata
{
    public string Quality { get; set; } = "";
    public string Speaker { get; set; } = "";
    [JsonPropertyName("speaker_confidence")]
    public string SpeakerConfidence { get; set; } = "";
    [JsonPropertyName("known_speaker_name")]
    public string KnownSpeakerName { get; set; } = "";
    public string Notes { get; set; } = "";
}

public class RussianEvidence
{
    public string Text { get; set; } = "";
    public List<RussianEvidenceSegment> Segments { get; set; } = [];
}

public class RussianEvidenceSegment
{
    public int? Id { get; set; }
    public double Start { get; set; }
    public double End { get; set; }

    [JsonPropertyName("russian_text")]
    public string RussianText { get; set; } = "";

    [JsonPropertyName("translation_candidates")]
    public Dictionary<string, string> TranslationCandidates { get; set; } = [];

    [JsonPropertyName("translation")]
    public string Translation { get; set; } = "";

    [JsonPropertyName("glossary_hits")]
    public List<GlossaryHit> GlossaryHits { get; set; } = [];

    [JsonPropertyName("glossary_corrections")]
    public List<GlossaryCorrection> GlossaryCorrections { get; set; } = [];

    [JsonPropertyName("translation_review")]
    public TranslationReview TranslationReview { get; set; } = new();
}


public class GlossaryHit
{
    public string Russian { get; set; } = "";
    public string English { get; set; } = "";
}

\npublic class GlossaryCorrection\n{\n    public string Russian { get; set; } = "";\n    public string English { get; set; } = "";\n}\n\npublic class TranslationReview
{
    public string Status { get; set; } = "unreviewed";
    public string Selected { get; set; } = "";
    public string Confidence { get; set; } = "";
    public string Notes { get; set; } = "";
}

public class RecoveredEnglishAsr
{
    public string Text { get; set; } = "";
    public List<EnglishAsrSegment> Segments { get; set; } = [];

    [JsonPropertyName("average_word_confidence")]
    public double? AverageWordConfidence { get; set; }
}

public class EnglishAsrSegment
{
    public int? Id { get; set; }
    public double Start { get; set; }
    public double End { get; set; }
    public string Text { get; set; } = "";

    [JsonPropertyName("word_confidence")]
    public double? WordConfidence { get; set; }

    [JsonPropertyName("no_speech_probability")]
    public double? NoSpeechProbability { get; set; }

    [JsonPropertyName("avg_logprob")]
    public double? AvgLogprob { get; set; }
}

public class EvidenceFlags
{
    [JsonPropertyName("needs_attention")]
    public bool NeedsAttention { get; set; }

    public List<string> Flags { get; set; } = [];
}

public partial class SpeechEvidenceItem : SpeechReviewItem
{
    public SpeechEvidenceItem(SpeechEvidenceRegion evidence, SpeechReviewDecision? decision)
        : base(ToReviewRegion(evidence), decision)
    {
        RussianText = evidence.RussianEvidence?.Text ?? "";
        RecoveredEnglishText = evidence.RecoveredEnglishAsr?.Text ?? "";
        TranslationSegments = evidence.RussianEvidence?.Segments ?? [];
        EvidenceAsrSegments = evidence.RecoveredEnglishAsr?.Segments ?? [];
        EvidenceFlags = evidence.EvidenceFlags?.Flags ?? [];
        NeedsAttention = evidence.EvidenceFlags?.NeedsAttention ?? false;
        TranslatedRegionText = evidence.TranslatedRegionText ?? "";
    }

    public override string RussianText { get; }
    public override string RecoveredEnglishText { get; }
    public override string TranslatedRegionText { get; }
    public IReadOnlyList<RussianEvidenceSegment> TranslationSegments { get; }
    public IReadOnlyList<EnglishAsrSegment> EvidenceAsrSegments { get; }
    public IReadOnlyList<string> EvidenceFlags { get; }
    public override bool NeedsAttention { get; }

    public override string TranslationCandidatesDisplay
    {
        get
        {
            var lines = new List<string>();
            foreach (var segment in TranslationSegments)
            {
                foreach (var candidate in segment.TranslationCandidates)
                    lines.Add($"{candidate.Key}: {candidate.Value}");
            }

            return string.Join("\n", lines);
        }
    }

    public override string EvidenceFlagsDisplay =>
        EvidenceFlags.Count == 0 ? "None" : string.Join(" • ", EvidenceFlags);

    private static SpeechReviewRegion ToReviewRegion(SpeechEvidenceRegion evidence) => new()
    {
        Id = evidence.Id,
        Start = evidence.Start,
        End = evidence.End,
        SubtitleIds = evidence.SubtitleIds ?? [],
        Text = evidence.TranslatedRegionText ?? "",
        BoundaryStartSource = evidence.Boundary?.StartSource ?? "",
        BoundaryEndSource = evidence.Boundary?.EndSource ?? "",
        Quality = evidence.ReviewMetadata?.Quality ?? "",
        Speaker = evidence.ReviewMetadata?.Speaker ?? "",
        SpeakerConfidence = evidence.ReviewMetadata?.SpeakerConfidence ?? "",
        Notes = evidence.ReviewMetadata?.Notes ?? ""
    };
}
