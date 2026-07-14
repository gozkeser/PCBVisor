using System.Text.Json.Serialization;

namespace PCBVisorScriptHelper.Models.ScriptParameters;

public class Step1Params
{
    public string InputPng   { get; set; } = "";
    public string OutputPath { get; set; } = "";
    public int    Padding    { get; set; } = 125;
    public int    ColorR     { get; set; } = 254;
    public int    ColorG     { get; set; } = 254;
    public int    ColorB     { get; set; } = 254;

    public string BuildArgs() =>
        $"-i \"{InputPng}\" -p {Padding} -c {ColorR},{ColorG},{ColorB}"
        + (string.IsNullOrWhiteSpace(OutputPath) ? "" : $" -o \"{OutputPath}\"");
}
