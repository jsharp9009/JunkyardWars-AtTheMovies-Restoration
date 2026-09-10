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
    private Dictionary<int, SpeechReviewDecision> decisions = new();

    public ObservableCollection<SpeechReviewItem> Regions { get; } = new();

    [ObservableProperty]
    private SpeechReviewItem? currentRegion;

    [ObservableProperty]
    private string mapPath = "speech_review_map.json";

    [ObservableProperty]
    private string decisionsPath = "speech_review_decisions.json";

    [ObservableProperty]
    private string audioPath = "restored_audio.wav";

    [ObservableProperty]
    private string status = "Not loaded.";

    [ObservableProperty]
    private string jumpId = "";

    public string[] QualityOptions { get; } = ["", "Good", "Muffled", "Partial", "Missing"];
    public string[] SpeakerOptions { get; } = ["", "Known", "Multiple", "Unknown"];
    public string[] SpeakerConfidenceOptions { get; } = ["", "High", "Medium", "Low"];

    public SpeechReviewViewModel()
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

            var regions = repository.LoadMap(MapPath);
            decisions = repository.LoadDecisions(DecisionsPath);

            Regions.Clear();
            foreach (var region in regions.OrderBy(x => x.Id))
            {
                decisions.TryGetValue(region.Id, out var decision);
                Regions.Add(new SpeechReviewItem(region, decision));
            }

            CurrentRegion = Regions.FirstOrDefault();
            Status = $"Loaded {Regions.Count} speech regions.";
        }
        catch (Exception ex)
        {
            Status = ex.Message;
            Regions.Clear();
            CurrentRegion = null;
        }
    }

    [RelayCommand]
    private async Task Play()
    {
        if (CurrentRegion == null)
            return;

        var audio = ResolveExistingPath(AudioPath);
        if (!File.Exists(audio))
        {
            Status = $"Audio file not found: {AudioPath}";
            return;
        }

        await audioPlayer.PlaySegmentAsync(audio, CurrentRegion.Start, CurrentRegion.End);
    }

    [RelayCommand]
    private async Task PlayContext()
    {
        if (CurrentRegion == null)
            return;

        var audio = ResolveExistingPath(AudioPath);
        if (!File.Exists(audio))
        {
            Status = $"Audio file not found: {AudioPath}";
            return;
        }

        const double context = 0.75;
        await audioPlayer.PlaySegmentAsync(
            audio,
            Math.Max(0, CurrentRegion.Start - context),
            CurrentRegion.End + context);
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
        if (!int.TryParse(JumpId, out var id))
            return;

        var item = Regions.FirstOrDefault(x => x.Id == id);
        if (item != null)
        {
            SaveAll();
            CurrentRegion = item;
        }
    }

    [RelayCommand]
    private void NudgeStartEarlier()
    {
        if (CurrentRegion == null) return;
        CurrentRegion.Start = Math.Max(0, CurrentRegion.Start - 0.10);
    }

    [RelayCommand]
    private void NudgeStartLater()
    {
        if (CurrentRegion == null) return;
        CurrentRegion.Start = Math.Min(CurrentRegion.End - 0.01, CurrentRegion.Start + 0.10);
    }

    [RelayCommand]
    private void NudgeEndEarlier()
    {
        if (CurrentRegion == null) return;
        CurrentRegion.End = Math.Max(CurrentRegion.Start + 0.01, CurrentRegion.End - 0.10);
    }

    [RelayCommand]
    private void NudgeEndLater()
    {
        if (CurrentRegion == null) return;
        CurrentRegion.End += 0.10;
    }

    [RelayCommand]
    private void Save()
    {
        SaveAll();
        Status = $"Saved {Regions.Count} speech decisions.";
    }

    public void SaveAll()
    {
        SaveCurrent();
        repository.SaveDecisions(
            ResolveWritablePath(DecisionsPath, MapPath),
            Regions.Select(x => x.ToDecision()));
    }

    private void Move(int direction)
    {
        if (Regions.Count == 0)
            return;

        SaveAll();
        var index = CurrentRegion == null ? 0 : Regions.IndexOf(CurrentRegion);
        index = Math.Clamp(index + direction, 0, Regions.Count - 1);
        CurrentRegion = Regions[index];
    }

    private void SaveCurrent() => CurrentRegion?.Normalize();

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
        if (Path.IsPathRooted(path) || File.Exists(path))
            return path;

        var parent = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", path));
        return File.Exists(parent) ? parent : path;
    }

    private static string ResolveWritablePath(string path, string mapPath)
    {
        if (Path.IsPathRooted(path) || File.Exists(path))
            return path;

        var mapDirectory = Path.GetDirectoryName(Path.GetFullPath(mapPath));
        if (!string.IsNullOrWhiteSpace(mapDirectory))
            return Path.Combine(mapDirectory, Path.GetFileName(path));

        return path;
    }
}

public partial class SpeechReviewItem : ObservableObject
{
    public int Id { get; }
    public string Text { get; }
    public int[] SubtitleIds { get; }
    public string SubtitleIdsDisplay => string.Join(", ", SubtitleIds);
    public string BoundaryStartSource { get; }
    public string BoundaryEndSource { get; }
    public double OriginalStart { get; }
    public double OriginalEnd { get; }

    [ObservableProperty]
    private double start;

    [ObservableProperty]
    private double end;

    [ObservableProperty]
    private string quality = "";

    [ObservableProperty]
    private string speaker = "";

    [ObservableProperty]
    private string speakerConfidence = "";

    [ObservableProperty]
    private string notes = "";

    public string PositionDisplay => $"{FormatTime(Start)} – {FormatTime(End)}";
    public string DurationDisplay => $"{Math.Max(0, End - Start):0.00}s";
    public string BoundaryDisplay => $"Start: {BoundaryStartSource}    End: {BoundaryEndSource}";

    public SpeechReviewItem(SpeechReviewRegion region, SpeechReviewDecision? decision)
    {
        Id = region.Id;
        Text = region.Text;
        SubtitleIds = region.SubtitleIds;
        BoundaryStartSource = region.BoundaryStartSource;
        BoundaryEndSource = region.BoundaryEndSource;
        OriginalStart = region.Start;
        OriginalEnd = region.End;

        Start = decision?.Start ?? region.Start;
        End = decision?.End ?? region.End;
        Quality = decision?.Quality ?? region.Quality;
        Speaker = decision?.Speaker ?? region.Speaker;
        SpeakerConfidence = decision?.SpeakerConfidence ?? region.SpeakerConfidence;
        Notes = decision?.Notes ?? region.Notes;
    }

    partial void OnStartChanged(double value) => OnPropertyChanged(nameof(PositionDisplay));
    partial void OnEndChanged(double value)
    {
        OnPropertyChanged(nameof(PositionDisplay));
        OnPropertyChanged(nameof(DurationDisplay));
    }

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
        SpeakerConfidence = SpeakerConfidence,
        Notes = Notes
    };

    private static string FormatTime(double seconds)
    {
        var span = TimeSpan.FromSeconds(Math.Max(0, seconds));
        return span.TotalHours >= 1
            ? span.ToString(@"h\:mm\:ss\.ff")
            : span.ToString(@"m\:ss\.ff");
    }
}
