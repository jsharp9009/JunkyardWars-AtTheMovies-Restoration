using Avalonia.Media;

namespace JunkyardRestorationStudio.Models;

public enum AgreementLevel
{
    Good,
    Warning,
    Outlier
}

public class RunAnalysis
{
    public string RunName { get; set; } = "";

    public double Score { get; set; }

    public AgreementLevel Agreement { get; set; }

    public string ScoreDisplay =>
    $"{Score:0.000000}";

    public IBrush AgreementBrush =>
        Agreement switch
        {
            AgreementLevel.Good => Brushes.ForestGreen,
            AgreementLevel.Warning => Brushes.DarkOrange,
            AgreementLevel.Outlier => Brushes.Firebrick,
            _ => Brushes.Gray
        };

    public string AgreementText =>
        Agreement switch
        {
            AgreementLevel.Good => "Good",
            AgreementLevel.Warning => "Warning",
            AgreementLevel.Outlier => "Outlier",
            _ => ""
        };
}