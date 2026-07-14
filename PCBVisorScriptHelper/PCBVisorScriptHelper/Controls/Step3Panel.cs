using PCBVisorScriptHelper.Models.ScriptParameters;

namespace PCBVisorScriptHelper.Controls;

public sealed class Step3Panel : StepPanelBase
{
    private readonly TextBox       _txtJson;
    private readonly TextBox       _txtCsv;
    private readonly ComboBox      _cmbLayer;
    private readonly TextBox       _txtOutputJson;
    private readonly NumericUpDown _numRatioTol;

    public Step3Panel() : base("origin_finder.py")
    {
        int row = 0;
        _txtJson       = AddPathRow(row++, "JSON Candidates", "Fiducial candidates JSON from Step 2 (--json)", "JSON files|*.json");
        _txtCsv        = AddPathRow(row++, "Fiducials CSV",   "Real-world fiducial coordinates — auto-filled from Common Inputs (--csv)", "CSV files|*.csv");
        _cmbLayer      = AddComboRow(row++, "Layer",          "Layer to match; auto-detected from filename if left on Auto-detect (--layer)",
                             new[] { "Auto-detect", "BottomLayer", "TopLayer" }, "Auto-detect");
        _txtOutputJson = AddPathRow(row++, "Output JSON",     "Leave blank to auto-derive (*_origin.json) (--output)", "JSON files|*.json");
        _numRatioTol   = AddNumericRow(row++, "Ratio Tolerance", "Normalized distance tolerance for candidate filtering (--ratio-tolerance)", 0, 1, (decimal)0.01, (decimal)0.001, 4);
    }

    public void SetJsonCandidates(string path) => _txtJson.Text       = path;
    public void SetFiducialsCsv(string path)   => _txtCsv.Text        = path;
    public void SetOutputJson(string path)      => _txtOutputJson.Text = path;
    public string GetOutputJson()               => _txtOutputJson.Text.Trim();

    public Step3Params GetParams() => new()
    {
        JsonCandidates = _txtJson.Text.Trim(),
        FiducialsCsv   = _txtCsv.Text.Trim(),
        Layer          = _cmbLayer.SelectedItem?.ToString() == "Auto-detect" ? "" : (_cmbLayer.SelectedItem?.ToString() ?? ""),
        OutputJson     = _txtOutputJson.Text.Trim(),
        RatioTolerance = (double)_numRatioTol.Value,
    };

    public void SetParams(Step3Params p)
    {
        _txtJson.Text       = p.JsonCandidates;
        _txtCsv.Text        = p.FiducialsCsv;
        _cmbLayer.SelectedItem = string.IsNullOrEmpty(p.Layer) ? "Auto-detect" : p.Layer;
        _txtOutputJson.Text = p.OutputJson;
        _numRatioTol.Value  = (decimal)Math.Clamp(p.RatioTolerance, 0, 1);
    }

    public bool Validate(out string error)
    {
        if (!File.Exists(_txtJson.Text.Trim()))
        { error = "Step 3: JSON candidates file not found."; return false; }
        if (!File.Exists(_txtCsv.Text.Trim()))
        { error = "Step 3: Fiducials CSV file not found."; return false; }
        error = ""; return true;
    }
}
