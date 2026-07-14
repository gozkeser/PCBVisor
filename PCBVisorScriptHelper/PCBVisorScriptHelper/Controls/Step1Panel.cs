using PCBVisorScriptHelper.Models.ScriptParameters;

namespace PCBVisorScriptHelper.Controls;

public sealed class Step1Panel : StepPanelBase
{
    private readonly TextBox       _txtInput;
    private readonly TextBox       _txtOutput;
    private readonly NumericUpDown _numPadding;
    private readonly NumericUpDown _numR, _numG, _numB;
    private readonly Panel         _colorPreview;

    public Step1Panel() : base("expand_image.py")
    {
        int row = 0;
        _txtInput  = AddPathRow(row++, "Input PNG",    "Source PNG — auto-filled from Common Inputs (--input)", "PNG files|*.png");
        _txtOutput = AddPathRow(row++, "Output PNG",   "Leave blank to auto-derive (*_E.png) (--output)",        "PNG files|*.png");
        _numPadding = AddNumericRow(row++, "Padding (px)", "Pixels added to all four edges (--padding)", 0, 9999, 125);

        // Color R G B row
        Table.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        var colorLabel = new Label
        {
            Text      = "Transparent RGB:",
            ForeColor = Color.FromArgb(190, 190, 190),
            Font      = new Font("Segoe UI", 8.5f),
            TextAlign = ContentAlignment.MiddleRight,
            Dock      = DockStyle.Fill,
            Padding   = new Padding(0, 0, 6, 0),
        };
        var colorRow = new FlowLayoutPanel
        {
            Dock        = DockStyle.Fill,
            FlowDirection = FlowDirection.LeftToRight,
            Margin      = new Padding(2, 4, 2, 2),
            BackColor   = Color.Transparent,
        };
        _numR = MakeColorSpinner(254); _numG = MakeColorSpinner(254); _numB = MakeColorSpinner(254);
        _colorPreview = new Panel { Width = 24, Height = 20, BackColor = Color.FromArgb(254, 254, 254), Margin = new Padding(6, 0, 0, 0) };
        _numR.ValueChanged += (_, _) => UpdatePreview(); _numG.ValueChanged += (_, _) => UpdatePreview(); _numB.ValueChanged += (_, _) => UpdatePreview();
        colorRow.Controls.AddRange(new Control[] {
            MakeMini("R"), _numR, MakeMini("G"), _numG, MakeMini("B"), _numB, _colorPreview
        });
        Table.Controls.Add(colorLabel, 0, row);
        Table.Controls.Add(colorRow,   1, row);
        Table.Controls.Add(new Label(), 2, row);
        row++;

        new ToolTip().SetToolTip(_numR, "Red channel (0-255) of the color to convert to transparent (--color)");
    }

    private void UpdatePreview() =>
        _colorPreview.BackColor = Color.FromArgb((int)_numR.Value, (int)_numG.Value, (int)_numB.Value);

    private static NumericUpDown MakeColorSpinner(int def) => new()
    {
        Minimum = 0, Maximum = 255, Value = def,
        Width = 52, BackColor = Color.FromArgb(55, 55, 60), ForeColor = Color.White,
        Font = new Font("Consolas", 8.5f), Margin = new Padding(0, 0, 2, 0),
    };
    private static Label MakeMini(string t) => new()
    {
        Text = t, ForeColor = Color.FromArgb(170, 170, 170),
        AutoSize = true, TextAlign = ContentAlignment.MiddleCenter,
        Margin = new Padding(4, 4, 2, 0),
    };

    // ── Public accessors ──────────────────────────────────────────────────

    public void SetInputPng(string path)  => _txtInput.Text  = path;
    public void SetOutputPng(string path) => _txtOutput.Text = path;
    public string GetOutputPng()          => _txtOutput.Text.Trim();

    public Step1Params GetParams() => new()
    {
        InputPng   = _txtInput.Text.Trim(),
        OutputPath = _txtOutput.Text.Trim(),
        Padding    = (int)_numPadding.Value,
        ColorR     = (int)_numR.Value,
        ColorG     = (int)_numG.Value,
        ColorB     = (int)_numB.Value,
    };

    public void SetParams(Step1Params p)
    {
        _txtInput.Text   = p.InputPng;
        _txtOutput.Text  = p.OutputPath;
        _numPadding.Value = Math.Clamp(p.Padding, 0, 9999);
        _numR.Value = Math.Clamp(p.ColorR, 0, 255);
        _numG.Value = Math.Clamp(p.ColorG, 0, 255);
        _numB.Value = Math.Clamp(p.ColorB, 0, 255);
    }

    public bool Validate(out string error)
    {
        if (!File.Exists(_txtInput.Text.Trim()))
        { error = "Step 1: Input PNG file not found."; return false; }
        error = ""; return true;
    }
}
