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
    private ProjectSettings? project;

    public MainViewModel()
    {
        project = ProjectLoader.Load("project.json");
    }

    
}