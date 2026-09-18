using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using JunkyardRestorationStudio.Models;
using JunkyardRestorationStudio.Services;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Threading.Tasks;

namespace JunkyardRestorationStudio.ViewModels;

public partial class SpeechReviewItem : ObservableObject
{
    private readonly SpeechReviewRegion sourceRegion;

    public int Id { get; }
    public double OriginalStart { get; }
    public double OriginalEnd { get; }

    [ObservableProperty] private double start;
    [ObservableProperty] private double end;
    [ObservableProperty] private string quality = "";
    [ObservableProperty] private string speaker = "";
    [ObservableProperty] private string knownSpeakerName = "";
    [ObservableProperty] private string speakerConfidence = "";
    [ObservableProperty] private string notes = "";
    [ObservableProperty] private string finalText = "";
    [ObservableProperty] private string reviewConfidence = "";
    [ObservableProperty] private string evidenceSource = "";

    public int[] SubtitleIds { get; }
    public string Text { get; }
    public string BoundaryStartSource { get; }
    public string BoundaryEndSource { get; }

    public bool IsKnownSpeaker => Speaker == "Known";

    public string PositionDisplay => $"{Start:0.00}s – {End:0.00}s";
    public string DurationDisplay => $"{Math.Max(0, End - Start):0.00}s";
    public string BoundaryDisplay => $"Start: {BoundaryStartSource} • End: {BoundaryEndSource}";

    // Evidence-review views use SpeechReviewItem as the common compile-time type.
    // These virtual properties are overridden by SpeechEvidenceItem.
    public virtual string RussianText => "";
    public virtual string RecoveredEnglishText => "";
    public virtual string TranslatedRegionText => Text;
    public virtual string TranslationCandidatesDisplay => "";
    public virtual string EvidenceFlagsDisplay => "None";
    public virtual bool NeedsAttention => false;

    public SpeechReviewItem(SpeechReviewRegion region, SpeechReviewDecision? decision)
    {
        sourceRegion = region;

        Id = region.Id;
        OriginalStart = decision?.OriginalStart > 0 ? decision.OriginalStart : region.Start;
        OriginalEnd = decision?.OriginalEnd > 0 ? decision.OriginalEnd : region.End;

        SubtitleIds = region.SubtitleIds ?? [];
        Text = region.Text ?? "";
        BoundaryStartSource = region.BoundaryStartSource ?? "";
        BoundaryEndSource = region.BoundaryEndSource ?? "";

        Start = decision?.Start ?? region.Start;
        End = decision?.End ?? region.End;
        Quality = decision?.Quality ?? region.Quality ?? "";
        Speaker = decision?.Speaker ?? region.Speaker ?? "";
        KnownSpeakerName = decision?.KnownSpeakerName ?? "";
        SpeakerConfidence = decision?.SpeakerConfidence ?? region.SpeakerConfidence ?? "";
        Notes = decision?.Notes ?? region.Notes ?? "";
        FinalText = decision?.FinalText ?? "";
        ReviewConfidence = decision?.ReviewConfidence ?? "";
        EvidenceSource = decision?.EvidenceSource ?? "";
    }

    partial void OnSpeakerChanged(string value)
    {
        OnPropertyChanged(nameof(IsKnownSpeaker));
    }

    partial void OnStartChanged(double value)
    {
        OnPropertyChanged(nameof(PositionDisplay));
        OnPropertyChanged(nameof(DurationDisplay));
    }

    partial void OnEndChanged(double value)
    {
        OnPropertyChanged(nameof(PositionDisplay));
        OnPropertyChanged(nameof(DurationDisplay));
    }

    public void Normalize()
    {
        Start = Math.Max(0, Start);
        End = Math.Max(Start + 0.01, End);
    }

    public SpeechReviewDecision ToDecision()
    {
        Normalize();

        return new SpeechReviewDecision
        {
            Id = Id,
            OriginalStart = OriginalStart,
            OriginalEnd = OriginalEnd,
            Start = Start,
            End = End,
            Quality = Quality,
            Speaker = Speaker,
            KnownSpeakerName = KnownSpeakerName,
            SpeakerConfidence = SpeakerConfidence,
            Notes = Notes,
            FinalText = FinalText,
            ReviewConfidence = ReviewConfidence,
            EvidenceSource = EvidenceSource
        };
    }
}

public partial class SpeechReviewViewModel : ViewModelBase
{
    private readonly IAudioPlayer audioPlayer = new AudioPlayer();
    private readonly SpeechReviewRepository repository = new();

    [ObservableProperty] private ReviewProject project;
    [ObservableProperty] private string mapPath = "speech_evidence_map.json";
    [ObservableProperty] private string decisionsPath = "speech_evidence_decisions.json";
    [ObservableProperty] private string audioPath = "restored_combine_preview.wav";
    [ObservableProperty] private string status = "Not loaded.";
    [ObservableProperty] private string jumpId = "";

#pragma warning disable CS8618
    public SpeechReviewViewModel()
#pragma warning restore CS8618
    {
        Load();
    }

    public string[] QualityOptions { get; } = ["", "Good", "Muffled", "Partial", "Missing"];
    public string[] SpeakerOptions { get; } = ["", "Known", "Multiple", "Unknown"];
    public string[] SpeakerConfidenceOptions { get; } = ["", "High", "Medium", "Low"];
    public string[] ReviewConfidenceOptions { get; } = ["", "High", "Medium", "Low"];
    public string[] EvidenceSourceOptions { get; } =
        ["", "Recovered English", "Russian + translation", "Both", "Uncertain"];

    [RelayCommand]
    private void Load()
    {
        try
        {
            MapPath = ResolveExistingPath(MapPath);
            DecisionsPath = ResolveWritablePath(DecisionsPath, MapPath);
            AudioPath = ResolveExistingPath(AudioPath);

            var regions = repository.LoadEvidenceMap(MapPath);
            var decisions = repository.LoadDecisions(DecisionsPath);

            var items = new List<SpeechReviewItem>();
            foreach (var evidence in regions.OrderBy(x => x.Id))
            {
                decisions.TryGetValue(evidence.Id, out var decision);
                items.Add(new SpeechEvidenceItem(evidence, decision));
            }

            Project = new ReviewProject(items, decisions);
            Status = $"Loaded {items.Count} evidence regions.";
        }
        catch (Exception ex)
        {
            Status = ex.Message;
            Project = new ReviewProject(new List<SpeechReviewItem>(), new Dictionary<int, SpeechReviewDecision>());
        }
    }

    [RelayCommand]
    private async Task Play()
    {
        if (Project.CurrentRegion == null) return;
        var audio = ResolveExistingPath(AudioPath);
        if (!File.Exists(audio)) { Status = $"Audio file not found: {AudioPath}"; return; }
        await audioPlayer.PlaySegmentAsync(audio, Project.CurrentRegion.Start, Project.CurrentRegion.End);
    }

    [RelayCommand]
    private async Task PlayContext()
    {
        if (Project.CurrentRegion == null) return;
        var audio = ResolveExistingPath(AudioPath);
        if (!File.Exists(audio)) { Status = $"Audio file not found: {AudioPath}"; return; }
        const double context = 0.75;
        await audioPlayer.PlaySegmentAsync(audio, Math.Max(0, Project.CurrentRegion.Start - context), Project.CurrentRegion.End + context);
    }

    [RelayCommand] private void Stop() => audioPlayer.Stop();
    [RelayCommand] private void Previous() => Move(-1);
    [RelayCommand] private void Next() => Move(1);

    [RelayCommand]
    private void Jump()
    {
        if (int.TryParse(JumpId, out var id))
            Project.JumpTo(id);
    }

    [RelayCommand]
    private void NudgeStartEarlier()
    {
        if (Project.CurrentRegion == null) return;
        Project.CurrentRegion.Start = Math.Max(0, Project.CurrentRegion.Start - 0.10);
        SaveAll();
    }

    [RelayCommand]
    private void NudgeStartLater()
    {
        if (Project.CurrentRegion == null) return;
        Project.CurrentRegion.Start = Math.Min(Project.CurrentRegion.End - 0.01, Project.CurrentRegion.Start + 0.10);
        SaveAll();
    }

    [RelayCommand]
    private void NudgeEndEarlier()
    {
        if (Project.CurrentRegion == null) return;
        Project.CurrentRegion.End = Math.Max(Project.CurrentRegion.Start + 0.01, Project.CurrentRegion.End - 0.10);
        SaveAll();
    }

    [RelayCommand]
    private void NudgeEndLater()
    {
        if (Project.CurrentRegion == null) return;
        Project.CurrentRegion.End += 0.10;
        SaveAll();
    }

    [RelayCommand]
    private void Save()
    {
        SaveAll();
        Status = $"Saved {Project.Regions.Count} evidence decisions.";
    }

    public void SaveAll()
    {
        SaveCurrent();
        repository.SaveDecisions(ResolveWritablePath(DecisionsPath, MapPath), Project.Regions.Select(x => x.ToDecision()));
    }

    private void Move(int direction)
    {
        if (direction < 0) Project.Previous();
        else Project.Next();
    }

    private void SaveCurrent() => Project.CurrentRegion?.Normalize();

    public async Task HandleShortcut(string key)
    {
        switch (key)
        {
            case "1": await Play(); break;
            case "2": await PlayContext(); break;
            case "Left": Previous(); break;
            case "Right": Next(); break;
            case "Space": await Play(); break;
        }
    }

    private static string ResolveExistingPath(string path)
    {
        if (Path.IsPathRooted(path) || File.Exists(path)) return path;
        var parent = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", path));
        return File.Exists(parent) ? parent : path;
    }

    private static string ResolveWritablePath(string path, string mapPath)
    {
        if (Path.IsPathRooted(path) || File.Exists(path)) return path;
        var mapDirectory = Path.GetDirectoryName(Path.GetFullPath(mapPath));
        if (!string.IsNullOrWhiteSpace(mapDirectory)) return Path.Combine(mapDirectory, Path.GetFileName(path));
        return path;
    }
}
