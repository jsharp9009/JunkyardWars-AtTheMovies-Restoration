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