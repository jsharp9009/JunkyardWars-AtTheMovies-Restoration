using CommunityToolkit.Mvvm.ComponentModel;
using System.Collections.Generic;
using System.ComponentModel;
using System.Linq;

namespace JunkyardRestorationStudio.Models;

public partial class RestorationProject : ObservableObject
{
    public ProjectSettings Settings { get; }

    public IReadOnlyList<ReviewSegment> Segments { get; }

    [ObservableProperty]
    private int currentIndex;

    public string ProgressText =>
    $"{ReviewedCount} / {TotalCount} Reviewed";

    public RestorationProject(
        ProjectSettings settings,
        List<ReviewSegment> segments)
    {
        Settings = settings;
        Segments = segments;

        CurrentIndex = segments.Count > 0 ? 0 : -1;

        foreach (var segment in Segments)
        {
            segment.Choice.PropertyChanged += Choice_PropertyChanged;
        }
    }

    public ReviewSegment? CurrentSegment =>
        CurrentIndex >= 0 &&
        CurrentIndex < Segments.Count
            ? Segments[CurrentIndex]
            : null;

    public IEnumerable<Choice> GetChoices()
    {
        return Segments
            .Select(s => s.Choice);
    }

    public string CurrentPosition =>
        Segments.Count == 0
            ? "0 / 0"
            : $"{CurrentIndex + 1} / {Segments.Count}";

    public int ReviewedCount =>
    Segments.Count(s =>
        s.Choice.Status != ReviewStatus.NotReviewed);

    public int TotalCount =>
        Segments.Count;

    public double Progress =>
        TotalCount == 0
            ? 0
            : (double)ReviewedCount / TotalCount;

    public bool CanMoveNext =>
        CurrentIndex < Segments.Count - 1;

    public bool CanMovePrevious =>
        CurrentIndex > 0;

    public void Next()
    {
        if (!CanMoveNext)
            return;

        CurrentIndex++;
    }

    public void Previous()
    {
        if (!CanMovePrevious)
            return;

        CurrentIndex--;
    }

    private void Choice_PropertyChanged(
    object? sender,
    PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(Choice.Status))
        {
            OnPropertyChanged(nameof(ReviewedCount));
            OnPropertyChanged(nameof(Progress));
            OnPropertyChanged(nameof(ProgressText));
            OnPropertyChanged(nameof(ProgressPercent));
        }
    }

    partial void OnCurrentIndexChanged(int value)
    {
        OnPropertyChanged(nameof(CurrentSegment));
        OnPropertyChanged(nameof(CurrentPosition));
        OnPropertyChanged(nameof(CanMoveNext));
        OnPropertyChanged(nameof(CanMovePrevious));

        OnPropertyChanged(nameof(ReviewedCount));
        OnPropertyChanged(nameof(Progress));
        OnPropertyChanged(nameof(ProgressText));
        OnPropertyChanged(nameof(ProgressPercent));
    }

    public string ProgressPercent =>
    $"{Progress:P0}";

    public void JumpTo(int segmentId)
    {
        for (int i = 0; i < Segments.Count; i++)
        {
            if (Segments[i].Id == segmentId)
            {
                CurrentIndex = i;
                return;
            }
        }
    }
}