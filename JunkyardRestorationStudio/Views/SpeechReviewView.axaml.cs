using Avalonia.Controls;
using Avalonia.Input;
using JunkyardRestorationStudio.ViewModels;

namespace JunkyardRestorationStudio.Views;

public partial class SpeechReviewView : UserControl
{
    public SpeechReviewView()
    {
        InitializeComponent();
        DataContext = new SpeechReviewViewModel();
    }

    private async void UserControl_KeyDown(object? sender, KeyEventArgs e)
    {
        if (DataContext is not SpeechReviewViewModel viewModel)
            return;

        switch (e.Key)
        {
            case Key.Left:
                viewModel.PreviousCommand.Execute(null);
                e.Handled = true;
                break;
            case Key.Right:
                viewModel.NextCommand.Execute(null);
                e.Handled = true;
                break;
            case Key.Space:
                await viewModel.HandleShortcut("Space");
                e.Handled = true;
                break;
            case Key.D1:
                await viewModel.HandleShortcut("1");
                e.Handled = true;
                break;
            case Key.D2:
                await viewModel.HandleShortcut("2");
                e.Handled = true;
                break;
        }
    }
}
