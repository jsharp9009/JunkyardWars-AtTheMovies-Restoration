using CommunityToolkit.Mvvm.ComponentModel;
using JunkyardRestorationStudio.ViewModels;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Linq;
using System.Text;

namespace JunkyardRestorationStudio.Models 
{
    public  partial class ReviewProject : ObservableObject
    {

        public IList<SpeechReviewItem> Regions { get; }

        public IDictionary<int, SpeechReviewDecision> Decisions { get; }

        [ObservableProperty]
        private int currentIndex;

        public string ProgressText =>
        $"{ReviewedCount} / {TotalCount} Reviewed";

        public ReviewProject(
            IList<SpeechReviewItem> regions,
            IDictionary<int, SpeechReviewDecision> decisions)
        {
            Regions = regions;
            Decisions = decisions;

            CurrentIndex = regions.Count > 0 ? 0 : -1;

            //foreach (var region in Regions)
            //{
            //    region.Choice.PropertyChanged += Choice_PropertyChanged;
            //}
        }

        public SpeechReviewItem? CurrentRegion =>
            CurrentIndex >= 0 &&
            CurrentIndex < Regions.Count
                ? Regions[CurrentIndex]
                : null;

        public string CurrentPosition =>
            Regions.Count == 0
                ? "0 / 0"
                : $"{CurrentIndex + 1} / {Regions.Count}";

        public int ReviewedCount =>
        Decisions.Count(r => r.Value.Quality != "");

        public int TotalCount =>
            Regions.Count;

        public double Progress =>
            TotalCount == 0
                ? 0
                : (double)ReviewedCount / TotalCount;

        public bool CanMoveNext =>
            CurrentIndex < Regions.Count - 1;

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
            OnPropertyChanged(nameof(CurrentRegion));
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

        public void JumpTo(int regionId)
        {
            for (int i = 0; i < Regions.Count; i++)
            {
                if (Regions[i].Id == regionId)
                {
                    CurrentIndex = i;
                    return;
                }
            }
        }
    }
}
