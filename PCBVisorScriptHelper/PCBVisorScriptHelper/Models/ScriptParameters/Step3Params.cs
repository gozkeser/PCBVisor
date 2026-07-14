using System.Globalization;
using System.Text.Json.Serialization;

namespace PCBVisorScriptHelper.Models.ScriptParameters;

public class Step3Params
{
    public string JsonCandidates { get; set; } = "";
    public string FiducialsCsv  { get; set; } = "";
    public string Layer          { get; set; } = ""; // "" = auto-detect
    public string OutputJson     { get; set; } = "";
    public double RatioTolerance { get; set; } = 0.01;

    public string BuildArgs() =>
        $"-j \"{JsonCandidates}\" -c \"{FiducialsCsv}\""
        + (string.IsNullOrWhiteSpace(Layer) ? "" : $" -l {Layer}")
        + (string.IsNullOrWhiteSpace(OutputJson) ? "" : $" -o \"{OutputJson}\"")
        + $" --ratio-tolerance {RatioTolerance.ToString("F4", CultureInfo.InvariantCulture)}";
}
