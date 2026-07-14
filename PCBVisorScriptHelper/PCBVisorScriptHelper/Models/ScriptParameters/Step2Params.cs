using System.Globalization;
using System.Text.Json.Serialization;

namespace PCBVisorScriptHelper.Models.ScriptParameters;

public class Step2Params
{
    public string InputPng       { get; set; } = "";
    public string OutputDir      { get; set; } = "";
    public double CannyThreshold { get; set; } = 100.0;
    public double MinCircularity { get; set; } = 0.75;
    public int    MinRadius      { get; set; } = 14;
    public int    MaxRadius      { get; set; } = 18;
    public bool   Debug          { get; set; } = false;

    public string BuildArgs() =>
        $"-i \"{InputPng}\""
        + (string.IsNullOrWhiteSpace(OutputDir) ? "" : $" -o \"{OutputDir}\"")
        + $" --canny-threshold {CannyThreshold.ToString("F1", CultureInfo.InvariantCulture)}"
        + $" --min-circularity {MinCircularity.ToString("F2", CultureInfo.InvariantCulture)}"
        + $" --min-radius {MinRadius}"
        + $" --max-radius {MaxRadius}"
        + (Debug ? " --debug" : "");
}
