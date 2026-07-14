using PCBVisorScriptHelper.Models.ScriptParameters;

namespace PCBVisorScriptHelper.Controls;

public sealed class Step2Panel : StepPanelBase
{
    private readonly TextBox       _txtInput;
    private readonly TextBox       _txtOutputDir;
    private readonly NumericUpDown _numCanny;
    private readonly NumericUpDown _numCircularity;
    private readonly NumericUpDown _numMinRadius;
    private readonly NumericUpDown _numMaxRadius;
    private readonly CheckBox      _chkDebug;

    public Step2Panel() : base("fid_finder.py")
    {
        int row = 0;
        _txtInput      = AddPathRow(row++, "Input PNG",       "Expanded PNG from Step 1 — auto-filled (--input)", "PNG files|*.png");
        _txtOutputDir  = AddPathRow(row++, "Output Dir",      "Directory for annotated PNG and JSON (--output-dir)", "", isDir: true);
        _numCanny      = AddNumericRow(row++, "Canny Threshold", "Upper threshold for Canny edge detection (--canny-threshold)", 1, 1000, 100, 1, 1);
        _numCircularity = AddNumericRow(row++, "Min Circularity", "Minimum circularity 0.0–1.0 (--min-circularity)", 0, 1, (decimal)0.75, (decimal)0.01, 2);
        _numMinRadius  = AddNumericRow(row++, "Min Radius (px)", "Minimum circle radius in pixels (--min-radius)", 1, 9999, 14);
        _numMaxRadius  = AddNumericRow(row++, "Max Radius (px)", "Maximum circle radius in pixels (--max-radius)", 1, 9999, 18);
        _chkDebug      = AddCheckRow(row++,   "Debug Mode",      "Generate intermediate step-by-step images (--debug)");
    }

    public void SetInputPng(string path)  => _txtInput.Text     = path;
    public void SetOutputDir(string path) => _txtOutputDir.Text = path;
    public string GetOutputDir()          => _txtOutputDir.Text.Trim();

    public Step2Params GetParams() => new()
    {
        InputPng       = _txtInput.Text.Trim(),
        OutputDir      = _txtOutputDir.Text.Trim(),
        CannyThreshold = (double)_numCanny.Value,
        MinCircularity = (double)_numCircularity.Value,
        MinRadius      = (int)_numMinRadius.Value,
        MaxRadius      = (int)_numMaxRadius.Value,
        Debug          = _chkDebug.Checked,
    };

    public void SetParams(Step2Params p)
    {
        _txtInput.Text      = p.InputPng;
        _txtOutputDir.Text  = p.OutputDir;
        _numCanny.Value     = (decimal)Math.Clamp(p.CannyThreshold, 1, 1000);
        _numCircularity.Value = (decimal)Math.Clamp(p.MinCircularity, 0, 1);
        _numMinRadius.Value = Math.Clamp(p.MinRadius, 1, 9999);
        _numMaxRadius.Value = Math.Clamp(p.MaxRadius, 1, 9999);
        _chkDebug.Checked   = p.Debug;
    }

    public bool Validate(out string error)
    {
        if (!File.Exists(_txtInput.Text.Trim()))
        { error = "Step 2: Input PNG file not found."; return false; }
        if (_numMinRadius.Value > _numMaxRadius.Value)
        { error = "Step 2: Min Radius must be ≤ Max Radius."; return false; }
        error = ""; return true;
    }
}
