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

public partial class SpeechReviewViewModel : ViewModelBase
{
    private readonly IAudioPlayer audioPlayer = new AudioPlayer();
    private readonly SpeechReviewRepository repository = new();

    [ObservableProperty]
    private ReviewProject project;

    [ObservableProperty]
    private string mapPath = "speech_review_map.json";

    [ObservableProperty]
    private string decisionsPath = "speech_review_decisions.json";

    [ObservableProperty]
    private string audioPath = "restored_combine_preview.wav";

    [ObservableProperty]
    private string status = "Not loaded.";

    [ObservableProperty]
    private string jumpId = "";


    public string[] QualityOptions { get; } = ["", "Good", "Muffled", "Partial", "Missing"];
    public string[] SpeakerOptions { get; } = ["", "Known", "Multiple", "Unknown"];
    public string[] SpeakerConfidenceOptions { get; } = ["", "High", "Medium", "Low"];

#pragma warning disable CS8618 // Non-nullable field must contain a non-null value when exiting constructor. Consider adding the 'required' modifier or declaring as nullable.
    public SpeechReviewViewModel()
#pragma warning restore CS8618 // Non-nullable field must contain a non-null value when exiting constructor. Consider adding the 'required' modifier or declaring as nullable.
    {
        Load();
    }

    [RelayCommand]
    private void Load()
    {
        try
        {
            MapPath = ResolveExistingPath(MapPath);
            DecisionsPath = ResolveWritablePath(DecisionsPath, MapPath);
            AudioPath = ResolveExistingPath(AudioPath);

            var regions = repository.LoadMap(MapPath);
            var decisions = repository.LoadDecisions(DecisionsPath);

            var Regions = new List<SpeechReviewItem>();
            foreach (var region in regions.OrderBy(x => x.Id))
            {
                decisions.TryGetValue(region.Id, out var decision);
                Regions.Add(new SpeechReviewItem(region, decision));
            }

            Project = new ReviewProject(Regions,decisions);
            Status = $"Loaded {Regions.Count} speech regions.";
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
        if (!File.Exists(audio))
        {
            Status = $"Audio file not found: {AudioPath}";
            return;
        }
        await audioPlayer.PlaySegmentAsync(audio, Project.CurrentRegion.Start, Project.CurrentRegion.End);
    }

    [RelayCommand]
    private async Task PlayContext()
    {
        if (Project.CurrentRegion == null) return;
        var audio = ResolveExistingPath(AudioPath);
        if (!File.Exists(audio))
        {
            Status = $"Audio file not found: {AudioPath}";
            return;
        }
        const double context = 0.75;
        await audioPlayer.PlaySegmentAsync(audio, Math.Max(0, Project.CurrentRegion.Start - context), Project.CurrentRegion.End + context);
    }

    [RelayCommand]
    private void Stop() => audioPlayer.Stop();

    [RelayCommand]
    private void Previous() => Move(-1);

    [RelayCommand]
    private void Next() => Move(1);

    [RelayCommand]
    private void Jump()
    {
        if (!int.TryParse(JumpId, out var id)) return;
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
        Status = $"Saved {Project.Regions.Count} speech decisions.";
    }

    public void SaveAll()
    {
        SaveCurrent();
        repository.SaveDecisions(ResolveWritablePath(DecisionsPath, MapPath), Project.Regions.Select(x => x.ToDecision()));
    }

    private void Move(int direction)
    {
        switch (direction)
        {
            case -1: Project.Previous(); break;
            case 1: Project.Next(); break;
        }
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

public partial class SpeechReviewItem : ObservableObject
{
    public int Id { get; }
    public string Text { get; }
    public int[] SubtitleIds { get; }
    public string SubtitleIdsDisplay => SubtitleIds.Length == 0 ? "None" : string.Join(", ", SubtitleIds);
    public string BoundaryStartSource { get; }
    public string BoundaryEndSource { get; }
    public double OriginalStart { get; }
    public double OriginalEnd { get; }

    [ObservableProperty] private double start;
    [ObservableProperty] private double end;
    [ObservableProperty] private string quality = "";
    [ObservableProperty] private string speaker = "";
    [ObservableProperty] private string knownSpeakerName = "";
    [ObservableProperty] private string speakerConfidence = "";
    [ObservableProperty] private string notes = "";

    public bool IsKnownSpeaker => string.Equals(Speaker, "Known", StringComparison.OrdinalIgnoreCase);
    public string PositionDisplay => $"{FormatTime(Start)} – {FormatTime(End)}";
    public string DurationDisplay => $"{Math.Max(0, End - Start):0.00}s";
    public string BoundaryDisplay => $"Start: {BoundaryStartSource}    End: {BoundaryEndSource}";

    public SpeechReviewItem(SpeechReviewRegion region, SpeechReviewDecision? decision)
    {
        Id = region.Id;
        Text = region.Text;
        SubtitleIds = region.SubtitleIds ?? [];
        BoundaryStartSource = region.BoundaryStartSource;
        BoundaryEndSource = region.BoundaryEndSource;
        OriginalStart = region.Start;
        OriginalEnd = region.End;

        Start = decision?.Start ?? region.Start;
        End = decision?.End ?? region.End;
        Quality = decision?.Quality ?? region.Quality;
        Speaker = decision?.Speaker ?? region.Speaker;
        KnownSpeakerName = decision?.KnownSpeakerName ?? "";
        SpeakerConfidence = decision?.SpeakerConfidence ?? region.SpeakerConfidence;
        Notes = decision?.Notes ?? region.Notes;
    }

    partial void OnStartChanged(double value) => OnPropertyChanged(nameof(PositionDisplay));
    partial void OnEndChanged(double value)
    {
        OnPropertyChanged(nameof(PositionDisplay));
        OnPropertyChanged(nameof(DurationDisplay));
    }

    partial void OnSpeakerChanged(string value) => OnPropertyChanged(nameof(IsKnownSpeaker));

    public void Normalize()
    {
        if (Start < 0) Start = 0;
        if (End <= Start) End = Start + 0.01;
    }

    public SpeechReviewDecision ToDecision() => new()
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
        Notes = Notes
    };

    private static string FormatTime(double seconds)
    {
        var span = TimeSpan.FromSeconds(Math.Max(0, seconds));
        return span.TotalHours >= 1 ? span.ToString(@"h\:mm\:ss\.ff") : span.ToString(@"m\:ss\.ff");
    }
}
