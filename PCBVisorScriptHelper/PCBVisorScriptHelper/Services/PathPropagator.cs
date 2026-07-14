namespace PCBVisorScriptHelper.Services;

public static class PathPropagator
{
    // Step 1 output: {stem}_E.png
    public static string Step1Output(string sourcePng, string workDir) =>
        Path.Combine(workDir, Path.GetFileNameWithoutExtension(sourcePng) + "_E.png");

    // Step 2 JSON output: {stem_of_E}_fiducial_candidates.json
    public static string Step2JsonOutput(string step1Output, string workDir) =>
        Path.Combine(workDir,
            Path.GetFileNameWithoutExtension(step1Output) + "_fiducial_candidates.json");

    // Step 3 output: {stem_of_candidates_json}_origin.json
    public static string Step3JsonOutput(string step2Json, string workDir) =>
        Path.Combine(workDir,
            Path.GetFileNameWithoutExtension(step2Json) + "_origin.json");

    // Step 4 output: {stem_of_step1}_final.png
    public static string Step4Output(string step1Output, string workDir) =>
        Path.Combine(workDir,
            Path.GetFileNameWithoutExtension(step1Output) + "_final.png");

    /// <summary>
    /// Recalculates all intermediate paths from sourcePng + workDir and
    /// returns them as a tuple for the caller to distribute to step panels.
    /// </summary>
    public static (string step1Out, string step2Json, string step3Json, string step4Out)
        RecalculateAll(string sourcePng, string workDir)
    {
        var step1Out  = Step1Output(sourcePng, workDir);
        var step2Json = Step2JsonOutput(step1Out, workDir);
        var step3Json = Step3JsonOutput(step2Json, workDir);
        var step4Out  = Step4Output(step1Out, workDir);
        return (step1Out, step2Json, step3Json, step4Out);
    }
}
