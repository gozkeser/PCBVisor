using PCBVisorScriptHelper.Models.ScriptParameters;

namespace PCBVisorScriptHelper.Controls;

public sealed class Step4Panel : StepPanelBase
{
    private readonly TextBox  _txtImage;
    private readonly TextBox  _txtOriginJson;
    private readonly ComboBox _cmbLayer;
    private readonly TextBox  _txtOutputPng;

    public Step4Panel() : base("fid_display.py")
    {
        int row = 0;
        _txtImage      = AddPathRow(row++, "Image PNG",    "Original PCB image — auto-filled from Common Inputs (--image)", "PNG files|*.png");
        _txtOriginJson = AddPathRow(row++, "Origin JSON",  "Origin JSON from Step 3 — contains matrix, origin pixel, and matched fiducials (--json)", "JSON files|*.json");
        _cmbLayer      = AddComboRow(row++, "Layer",       "Layer override; auto-detected from JSON if left on Auto-detect (--layer)",
                             new[] { "Auto-detect", "BottomLayer", "TopLayer" }, "Auto-detect");
        _txtOutputPng  = AddPathRow(row++, "Output PNG",  "Leave blank to auto-derive (*_final.png) (--output)", "PNG files|*.png");
    }

    public void SetImagePng(string path)    => _txtImage.Text      = path;
    public void SetOriginJson(string path)  => _txtOriginJson.Text = path;
    public void SetOutputPng(string path)   => _txtOutputPng.Text  = path;
    public string GetOutputPng()            => _txtOutputPng.Text.Trim();

    public Step4Params GetParams() => new()
    {
        ImagePng   = _txtImage.Text.Trim(),
        OriginJson = _txtOriginJson.Text.Trim(),
        Layer      = _cmbLayer.SelectedItem?.ToString() == "Auto-detect" ? "" : (_cmbLayer.SelectedItem?.ToString() ?? ""),
        OutputPng  = _txtOutputPng.Text.Trim(),
    };

    public void SetParams(Step4Params p)
    {
        _txtImage.Text      = p.ImagePng;
        _txtOriginJson.Text = p.OriginJson;
        _cmbLayer.SelectedItem = string.IsNullOrEmpty(p.Layer) ? "Auto-detect" : p.Layer;
        _txtOutputPng.Text  = p.OutputPng;
    }

    public bool Validate(out string error)
    {
        if (!File.Exists(_txtImage.Text.Trim()))
        { error = "Step 4: Image PNG file not found."; return false; }
        if (!File.Exists(_txtOriginJson.Text.Trim()))
        { error = "Step 4: Origin JSON file not found."; return false; }
        error = ""; return true;
    }
}
