using Avalonia.Input;
using JunkyardRestorationStudio.Models;

namespace JunkyardRestorationStudio.Services;

public static class KeyboardMapper
{
    public static KeyboardCommand Map(KeyEventArgs e)
    {
        if (e.KeyModifiers == KeyModifiers.Control)
        {
            return e.Key switch
            {
                Key.Left => KeyboardCommand.Previous,
                Key.Right => KeyboardCommand.Next,
                _ => KeyboardCommand.None
            };
        }

        return e.Key switch
        {
            Key.D1 => KeyboardCommand.Play20,
            Key.D2 => KeyboardCommand.Play30,
            Key.D3 => KeyboardCommand.Play45,
            Key.D4 => KeyboardCommand.Play60,

            Key.Q => KeyboardCommand.Select20,
            Key.W => KeyboardCommand.Select30,
            Key.E => KeyboardCommand.Select45,
            Key.R => KeyboardCommand.Select60,

            _ => KeyboardCommand.None
        };
    }
}