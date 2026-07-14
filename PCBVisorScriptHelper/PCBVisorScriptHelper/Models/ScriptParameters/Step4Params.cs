using System.Text.Json.Serialization;

namespace PCBVisorScriptHelper.Models.ScriptParameters;

public class Step4Params
{
    public string ImagePng   { get; set; } = "";
    public string OriginJson { get; set; } = "";
    public string Layer      { get; set; } = ""; // "" = auto-detect
    public string OutputPng  { get; set; } = "";

    public string BuildArgs() =>
        $"-i \"{ImagePng}\" -j \"{OriginJson}\""
        + (string.IsNullOrWhiteSpace(Layer) ? "" : $" -l {Layer}")
        + (string.IsNullOrWhiteSpace(OutputPng) ? "" : $" -o \"{OutputPng}\"");
}
