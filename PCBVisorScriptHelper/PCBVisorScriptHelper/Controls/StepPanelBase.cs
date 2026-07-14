using PCBVisorScriptHelper.Models.ScriptParameters;
using PCBVisorScriptHelper.Models;

namespace PCBVisorScriptHelper.Controls;

public abstract class StepPanelBase : UserControl
{
    protected readonly TableLayoutPanel Table;
    protected readonly Button           BtnRun;
    protected readonly Label            LblStatus;

    private StepStatus _status = StepStatus.Idle;

    [System.ComponentModel.DesignerSerializationVisibility(System.ComponentModel.DesignerSerializationVisibility.Hidden)]
    public StepStatus Status
    {
        get => _status;
        set { _status = value; UpdateStatusLabel(); }
    }

    public event EventHandler? RunRequested;

    protected StepPanelBase(string scriptName)
    {
        BackColor = Color.FromArgb(31, 41, 66); // Dark panel (#1F2942)
        Padding   = new Padding(15);
        Dock      = DockStyle.Fill;
        Font      = new Font("Segoe UI", 10f);

        var grp = new GroupBox
        {
            Text      = "Step Parameters",
            ForeColor = Color.FromArgb(10, 132, 255), // Accent
            Dock      = DockStyle.Fill,
            Font      = new Font("Segoe UI", 10f, FontStyle.Bold)
        };

        // Status Label
        LblStatus = new Label
        {
            Text      = "⏸ Idle",
            ForeColor = Color.FromArgb(224, 224, 224),
            Font      = new Font("Segoe UI", 10f),
            AutoSize  = true,
            Dock      = DockStyle.Left,
            Padding   = new Padding(0, 10, 0, 0)
        };

        // Run button
        BtnRun = new Button
        {
            Text      = $"▶ Run {scriptName}",
            FlatStyle = FlatStyle.Flat,
            BackColor = Color.FromArgb(255, 69, 0), // Orange accent
            ForeColor = Color.White,
            Font      = new Font("Segoe UI", 10f, FontStyle.Bold),
            Height    = 36,
            Width     = 220,
            FlatAppearance = { BorderSize = 0 },
        };
        BtnRun.Click += (_, _) => RunRequested?.Invoke(this, EventArgs.Empty);

        // Table for parameters
        Table = new TableLayoutPanel
        {
            Dock         = DockStyle.Top,
            AutoSize     = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            ColumnCount  = 3,
            BackColor    = Color.Transparent,
            CellBorderStyle = TableLayoutPanelCellBorderStyle.None,
            Padding      = new Padding(5, 10, 5, 10)
        };
        Table.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 180));
        Table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,  100));
        Table.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 45));

        // Bottom bar
        var bottom = new Panel { Dock = DockStyle.Bottom, Height = 45, BackColor = Color.Transparent };
        bottom.Controls.Add(BtnRun);
        bottom.Controls.Add(LblStatus);
        BtnRun.Dock    = DockStyle.Right;
        LblStatus.Dock = DockStyle.Left;

        grp.Controls.Add(Table);
        grp.Controls.Add(bottom);
        Controls.Add(grp);
    }

    protected TextBox AddPathRow(int row, string label, string tooltip, string filter, bool isDir = false)
    {
        Table.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));
        var lbl = MakeLabel(label);
        var txt = MakeTextBox();
        var btn = MakeBrowseButton();
        new ToolTip().SetToolTip(txt, tooltip);

        btn.Click += (_, _) => { if (isDir) BrowseDir(txt); else BrowseFile(txt, filter); };
        txt.AllowDrop = true;
        txt.DragEnter += (_, e) => { if (e.Data?.GetDataPresent(DataFormats.FileDrop) == true) e.Effect = DragDropEffects.Copy; };
        txt.DragDrop  += (_, e) => { if (e.Data?.GetData(DataFormats.FileDrop) is string[] f && f.Length > 0) txt.Text = f[0]; };

        Table.Controls.Add(lbl, 0, row);
        Table.Controls.Add(txt, 1, row);
        Table.Controls.Add(btn, 2, row);
        return txt;
    }

    protected NumericUpDown AddNumericRow(int row, string label, string tooltip, decimal min, decimal max, decimal def, decimal increment = 1, int decimals = 0)
    {
        Table.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));
        var lbl = MakeLabel(label);
        var num = new NumericUpDown
        {
            Minimum = min, Maximum = max, Value = def,
            Increment = increment, DecimalPlaces = decimals,
            BackColor = Color.FromArgb(26, 34, 56),
            ForeColor = Color.White,
            Font      = new Font("Consolas", 10f),
            Dock      = DockStyle.Fill,
            Margin    = new Padding(2, 6, 2, 2),
            BorderStyle = BorderStyle.FixedSingle
        };
        new ToolTip().SetToolTip(num, tooltip);
        Table.Controls.Add(lbl, 0, row);
        Table.Controls.Add(num, 1, row);
        Table.Controls.Add(new Label(), 2, row);
        return num;
    }

    protected CheckBox AddCheckRow(int row, string label, string tooltip, bool defaultVal = false)
    {
        Table.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));
        var lbl = MakeLabel(label);
        var chk = new CheckBox
        {
            Checked = defaultVal,
            ForeColor = Color.White,
            Font = new Font("Segoe UI", 10f),
            Dock = DockStyle.Fill,
            Margin = new Padding(4, 8, 2, 2),
        };
        new ToolTip().SetToolTip(chk, tooltip);
        Table.Controls.Add(lbl, 0, row);
        Table.Controls.Add(chk, 1, row);
        Table.Controls.Add(new Label(), 2, row);
        return chk;
    }

    protected ComboBox AddComboRow(int row, string label, string tooltip, string[] items, string defaultVal)
    {
        Table.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));
        var lbl = MakeLabel(label);
        var cmb = new ComboBox
        {
            DropDownStyle = ComboBoxStyle.DropDownList,
            BackColor = Color.FromArgb(26, 34, 56),
            ForeColor = Color.White,
            Font = new Font("Segoe UI", 10f),
            Dock = DockStyle.Fill,
            Margin = new Padding(2, 6, 2, 2),
            FlatStyle = FlatStyle.Flat
        };
        cmb.Items.AddRange(items);
        if (cmb.Items.Contains(defaultVal)) cmb.SelectedItem = defaultVal;
        else if (cmb.Items.Count > 0) cmb.SelectedIndex = 0;
        new ToolTip().SetToolTip(cmb, tooltip);
        Table.Controls.Add(lbl, 0, row);
        Table.Controls.Add(cmb, 1, row);
        Table.Controls.Add(new Label(), 2, row);
        return cmb;
    }

    private void UpdateStatusLabel()
    {
        if (InvokeRequired) { BeginInvoke(UpdateStatusLabel); return; }
        (LblStatus.Text, LblStatus.ForeColor) = _status switch
        {
            StepStatus.Idle      => ("● Idle",      Color.FromArgb(170, 170, 170)),
            StepStatus.Running   => ("● Running…",  Color.FromArgb(0, 122, 204)), // Blue
            StepStatus.Success   => ("● Success",   Color.FromArgb(28, 163, 64)),  // Corporate Green
            StepStatus.Error     => ("● Error",     Color.FromArgb(218, 59, 1)),   // Corporate Red
            StepStatus.Cancelled => ("● Cancelled", Color.FromArgb(221, 170, 0)),  // Yellow
            _                    => ("● Idle",      Color.FromArgb(170, 170, 170)),
        };
    }

    public void SetRunEnabled(bool enabled)
    {
        if (InvokeRequired) { BeginInvoke(() => SetRunEnabled(enabled)); return; }
        BtnRun.Enabled = enabled;
        BtnRun.BackColor = enabled ? Color.FromArgb(255, 69, 0) : Color.FromArgb(80, 80, 85);
    }

    private static Label MakeLabel(string text) => new()
    {
        Text      = text + ":",
        ForeColor = Color.FromArgb(224, 224, 224),
        Font      = new Font("Segoe UI", 10f),
        TextAlign = ContentAlignment.MiddleRight,
        Dock      = DockStyle.Fill,
        Padding   = new Padding(0, 0, 6, 0),
    };

    private static TextBox MakeTextBox() => new()
    {
        Dock        = DockStyle.Fill,
        BackColor   = Color.FromArgb(26, 34, 56),
        ForeColor   = Color.White,
        BorderStyle = BorderStyle.FixedSingle,
        Font        = new Font("Consolas", 10f),
        Margin      = new Padding(2, 6, 2, 2),
    };

    private static Button MakeBrowseButton() => new()
    {
        Text      = "📂",
        FlatStyle = FlatStyle.Flat,
        BackColor = Color.FromArgb(26, 34, 56),
        ForeColor = Color.White,
        Font      = new Font("Segoe UI Emoji", 11f),
        Dock      = DockStyle.Fill,
        Margin    = new Padding(4, 4, 2, 4),
        FlatAppearance = { BorderColor = Color.FromArgb(10, 132, 255), BorderSize = 1 },
    };

    private static void BrowseFile(TextBox txt, string filter)
    {
        using var dlg = new OpenFileDialog { Filter = filter, CheckFileExists = true };
        if (!string.IsNullOrEmpty(txt.Text))
            dlg.InitialDirectory = Path.GetDirectoryName(txt.Text);
        if (dlg.ShowDialog() == DialogResult.OK) txt.Text = dlg.FileName;
    }

    private static void BrowseDir(TextBox txt)
    {
        using var dlg = new FolderBrowserDialog { UseDescriptionForTitle = true };
        if (!string.IsNullOrEmpty(txt.Text) && Directory.Exists(txt.Text))
            dlg.InitialDirectory = txt.Text;
        if (dlg.ShowDialog() == DialogResult.OK) txt.Text = dlg.SelectedPath;
    }
}
