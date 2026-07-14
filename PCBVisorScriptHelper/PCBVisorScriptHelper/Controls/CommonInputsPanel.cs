namespace PCBVisorScriptHelper.Controls;

public sealed class CommonInputsPanel : UserControl
{
    private readonly TextBox _txtSource;
    private readonly TextBox _txtCsv;
    private readonly TextBox _txtWorkDir;
    private readonly TextBox _txtPython;
    private readonly TextBox _txtScripts;
    private readonly Label   _lblPythonWarning;

    public string SourcePng    => _txtSource.Text.Trim();
    public string FiducialsCsv => _txtCsv.Text.Trim();
    public string WorkingDir   => _txtWorkDir.Text.Trim();
    public string PythonExe    => _txtPython.Text.Trim();
    public string ScriptsDir   => _txtScripts.Text.Trim();

    public event EventHandler? SourcePngChanged;
    public event EventHandler? WorkingDirChanged;

    public CommonInputsPanel()
    {
        BackColor = Color.FromArgb(31, 41, 66); // Dark panel (#1F2942)
        Padding   = new Padding(15);
        Height    = 280;

        var grp = new GroupBox
        {
            Text      = "Common Inputs (Auto-populates individual steps)",
            ForeColor = Color.FromArgb(10, 132, 255), // #0A84FF Accent
            Dock      = DockStyle.Fill,
            Font      = new Font("Segoe UI", 10f, FontStyle.Bold)
        };

        var table = new TableLayoutPanel
        {
            Dock        = DockStyle.Top,
            AutoSize    = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            ColumnCount = 3,
            BackColor   = Color.Transparent,
            CellBorderStyle = TableLayoutPanelCellBorderStyle.None,
            Padding     = new Padding(5, 10, 5, 10),
        };
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 130));
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,  100));
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 45));
        for (int i = 0; i < 5; i++)
            table.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));

        _lblPythonWarning = new Label
        {
            Text = "⚠️ Python not found automatically. Please select python.exe manually.",
            ForeColor = Color.FromArgb(218, 59, 1),
            AutoSize = true, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft,
            Font = new Font("Segoe UI", 8.5f, FontStyle.Regular),
            Visible = false
        };

        _txtSource  = AddRow(table, 0, "Source PNG:",   "Original unpadded PNG image", "PNG files|*.png");
        _txtCsv     = AddRow(table, 1, "Fiducials CSV:","Real-world coordinates CSV", "CSV files|*.csv");
        _txtWorkDir = AddRow(table, 2, "Working Dir:",  "Directory where outputs will be saved", "", isDir: true);
        _txtPython  = AddRow(table, 3, "Python Exe:",   "Path to python.exe (virtual env recommended)", "Executable|*.exe");
        _txtScripts = AddRow(table, 4, "Scripts Dir:",  "Folder containing the 4 python scripts", "", isDir: true);

        table.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));
        table.Controls.Add(_lblPythonWarning, 1, 5);

        _txtSource.TextChanged  += (_, _) => SourcePngChanged?.Invoke(this, EventArgs.Empty);
        _txtWorkDir.TextChanged += (_, _) => WorkingDirChanged?.Invoke(this, EventArgs.Empty);

        grp.Controls.Add(table);
        Controls.Add(grp);
    }

    private TextBox AddRow(TableLayoutPanel table, int row, string labelText, string tooltip, string filter, bool isDir = false)
    {
        var lbl = new Label
        {
            Text = labelText, ForeColor = Color.FromArgb(224, 224, 224),
            Font = new Font("Segoe UI", 10f, FontStyle.Regular),
            TextAlign = ContentAlignment.MiddleRight, Dock = DockStyle.Fill,
            Padding = new Padding(0, 0, 6, 0)
        };
        var txt = new TextBox
        {
            Dock = DockStyle.Fill, BackColor = Color.FromArgb(26, 34, 56), // #1A2238
            ForeColor = Color.White, BorderStyle = BorderStyle.FixedSingle,
            Font = new Font("Consolas", 10f), Margin = new Padding(2, 6, 2, 2)
        };
        var btn = new Button
        {
            Text = "📂", FlatStyle = FlatStyle.Flat,
            BackColor = Color.FromArgb(26, 34, 56), ForeColor = Color.White,
            Font = new Font("Segoe UI Emoji", 11f, FontStyle.Regular),
            Dock = DockStyle.Fill, Margin = new Padding(4, 4, 2, 4),
        };
        btn.FlatAppearance.BorderColor = Color.FromArgb(10, 132, 255);
        btn.FlatAppearance.BorderSize = 1;

        new ToolTip().SetToolTip(txt, tooltip);

        btn.Click += (_, _) =>
        {
            if (isDir) {
                using var dlg = new FolderBrowserDialog { UseDescriptionForTitle = true };
                if (!string.IsNullOrEmpty(txt.Text) && Directory.Exists(txt.Text)) dlg.InitialDirectory = txt.Text;
                if (dlg.ShowDialog() == DialogResult.OK) txt.Text = dlg.SelectedPath;
            } else {
                using var dlg = new OpenFileDialog { Filter = filter, CheckFileExists = true };
                if (!string.IsNullOrEmpty(txt.Text)) dlg.InitialDirectory = Path.GetDirectoryName(txt.Text);
                if (dlg.ShowDialog() == DialogResult.OK) txt.Text = dlg.FileName;
            }
        };

        txt.AllowDrop = true;
        txt.DragEnter += (_, e) => { if (e.Data?.GetDataPresent(DataFormats.FileDrop) == true) e.Effect = DragDropEffects.Copy; };
        txt.DragDrop  += (_, e) => { if (e.Data?.GetData(DataFormats.FileDrop) is string[] f && f.Length > 0) txt.Text = f[0]; };

        table.Controls.Add(lbl, 0, row);
        table.Controls.Add(txt, 1, row);
        table.Controls.Add(btn, 2, row);
        return txt;
    }

    public void SetPythonPath(string path) => _txtPython.Text = path;
    public void SetScriptsDir(string path) => _txtScripts.Text = path;
    public void ShowPythonWarning(bool show) => _lblPythonWarning.Visible = show;

    public void SetFromProfile(string source, string csv, string dir, string python, string scriptsDir)
    {
        _txtSource.Text  = source;
        _txtCsv.Text     = csv;
        _txtWorkDir.Text = dir;
        if (!string.IsNullOrEmpty(python)) _txtPython.Text = python;
        if (!string.IsNullOrEmpty(scriptsDir)) _txtScripts.Text = scriptsDir;
    }
}
