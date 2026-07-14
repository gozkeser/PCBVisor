using PCBVisorScriptHelper.Models.ScriptParameters;

namespace PCBVisorScriptHelper.Models;

public class PipelineProfile
{
    public string Name         { get; set; } = "Untitled";
    public string SourcePng    { get; set; } = "";
    public string FiducialsCsv { get; set; } = "";
    public string WorkingDir   { get; set; } = "";
    public Step1Params Step1   { get; set; } = new();
    public Step2Params Step2   { get; set; } = new();
    public Step3Params Step3   { get; set; } = new();
    public Step4Params Step4   { get; set; } = new();
}
