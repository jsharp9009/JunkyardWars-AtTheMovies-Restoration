using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using JunkyardRestorationStudio.Models;
using JunkyardRestorationStudio.Services;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace JunkyardRestorationStudio.ViewModels;

public partial class MainViewModel : ViewModelBase
{
    [ObservableProperty]
    private RestorationProject? project;

    [ObservableProperty]
    private string status = "Loading...";

    private readonly IAudioPlayer audioPlayer =
    new AudioPlayer();
    private readonly ChoiceRepository choiceRepository = new();

    private const string ChoiceFile = "choices.json";

    public MainViewModel()
    {
        LoadProject();
    }

    [RelayCommand]
    private void Next()
    {
        if (Project == null)
            return;

        SaveChoices();

        Project.Next();
    }

    [RelayCommand]
    private void Previous()
    {
        if (Project == null)
            return;

        SaveChoices();

        Project.Previous();
    }

    [RelayCommand]
    private async Task Play20()
    {
        if (Project?.CurrentSegment == null)
            return;

        await PlayRun(Project.CurrentSegment.Audio20);
    }

    [RelayCommand]
    private async Task Play30()
    {
        if (Project?.CurrentSegment == null)
            return;

        await PlayRun(Project.CurrentSegment.Audio30);
    }

    [RelayCommand]
    private async Task Play45()
    {
        if (Project?.CurrentSegment == null)
            return;

        await PlayRun(Project.CurrentSegment.Audio45);
    }

    [RelayCommand]
    private async Task Play60()
    {
        if (Project?.CurrentSegment == null)
            return;

        await PlayRun(Project.CurrentSegment.Audio60);
    }

    [RelayCommand]
    private void Stop()
    {
        audioPlayer.Stop();
    }



    [ObservableProperty]
    private string jumpSegment = "";

    [RelayCommand]
    private void Jump()
    {
        if (Project == null)
            return;

        if (!int.TryParse(JumpSegment, out int id))
            return;

        SaveChoices();

        Project.JumpTo(id);
    }
    private void LoadProject()
    {
        try
        {
            ProjectSettings settings =
                ProjectLoader.Load("project.json");

            ReviewRepository repository =
                new();

            var segments =
                repository.Load(settings.ReviewFolder);

            Project =
                new RestorationProject(
                    settings,
                    segments);

            ChoiceRepository choiceRepository = new();

            var choices =
                choiceRepository.Load("choices.json");

            foreach (var segment in segments)
            {
                if (choices.TryGetValue(
                        segment.Id,
                        out var choice))
                {
                    segment.Choice = choice;
                }
                else
                {
                    segment.Choice = new Choice
                    {
                        SegmentId = segment.Id
                    };
                }
            }

            Status =
                $"Loaded {segments.Count} segments.";
        }
        catch (Exception ex)
        {
            Status = ex.Message;
        }
    }

    private void SaveChoices()
    {
        if (Project == null)
            return;

        choiceRepository.Save(
            ChoiceFile,
            Project.GetChoices());
    }


    public async Task HandleShortcut(
    KeyboardCommand command)
    {
        switch (command)
        {
            case KeyboardCommand.Play20:
                await Play20();
                break;

            case KeyboardCommand.Play30:
                await Play30();
                break;

            case KeyboardCommand.Play45:
                await Play45();
                break;

            case KeyboardCommand.Play60:
                await Play60();
                break;

            case KeyboardCommand.Select20:
                SelectRun("20s");
                break;

            case KeyboardCommand.Select30:
                SelectRun("30s");
                break;

            case KeyboardCommand.Select45:
                SelectRun("45s");
                break;

            case KeyboardCommand.Select60:
                SelectRun("60s");
                break;

            case KeyboardCommand.Next:
                Next();
                break;

            case KeyboardCommand.Previous:
                Previous();
                break;
        }
    }

    private void SelectRun(string run)
    {
        if (Project?.CurrentSegment == null)
            return;

        Project.CurrentSegment.Choice.SelectedRun = run;
    }

    private async Task PlayRun(string file)
    {
        await audioPlayer.PlayAsync(file);
    }
}