using Avalonia.Controls;
using Avalonia.Input;
using JunkyardRestorationStudio.Services;
using JunkyardRestorationStudio.ViewModels;

namespace JunkyardRestorationStudio.Views;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
    }

    private void OpenSpeechReview_Click(object? sender, Avalonia.Interactivity.RoutedEventArgs e)
    {
        var window = new SpeechReviewWindow
        {
            DataContext = new SpeechReviewViewModel()
        };

        window.Show(this);
    }

    private async void Window_KeyDown(object? sender, KeyEventArgs e)
    {
        // Ignore shortcuts while typing in a TextBox
        if (FocusManager.GetFocusedElement() is TextBox)
            return;

        if (DataContext is not MainViewModel vm)
            return;

        var command = KeyboardMapper.Map(e);

        if (command == Models.KeyboardCommand.None)
            return;

        e.Handled = true;

        await vm.HandleShortcut(command);
    }
}