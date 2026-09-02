using CommunityToolkit.Mvvm.ComponentModel;
using System;

namespace JunkyardRestorationStudio.Models;

public partial class Choice : ObservableObject
{
    public int SegmentId { get; set; }

    [ObservableProperty]
    private string selectedRun = "";

    [ObservableProperty]
    private ReviewStatus status =
        ReviewStatus.NotReviewed;

    [ObservableProperty]
    private string notes = "";

    [ObservableProperty]
    private DateTime? reviewedOn;

    partial void OnSelectedRunChanged(string value)
    {
        ReviewedOn = DateTime.Now;

        if (Status == ReviewStatus.NotReviewed)
            Status = ReviewStatus.Reviewed;
    }

    partial void OnNotesChanged(string value)
    {
        ReviewedOn = DateTime.Now;
    }
}

public enum ReviewStatus
{
    NotReviewed,
    Reviewed,
    NeedsAttention,
    RebuildRequired
}