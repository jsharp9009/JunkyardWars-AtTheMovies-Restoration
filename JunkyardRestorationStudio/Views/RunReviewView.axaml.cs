using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Markup.Xaml;
using JunkyardRestorationStudio.Services;
using JunkyardRestorationStudio.ViewModels;

namespace JunkyardRestorationStudio.Views
{
    public partial class RunReviewView : ContentPage
    {
        public RunReviewView()
        {
            InitializeComponent();
            DataContext = new RunReviewViewModel();
        }

        private async void UserControl_KeyDown(object? sender, KeyEventArgs e)
        {

            if (DataContext is not RunReviewViewModel vm)
                return;

            var command = KeyboardMapper.Map(e);

            if (command == Models.KeyboardCommand.None)
                return;

            e.Handled = true;

            await vm.HandleShortcut(command);
        }
    }
}