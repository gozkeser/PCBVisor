using PCBVisorScriptHelper.Controls;
using PCBVisorScriptHelper.Models;
using PCBVisorScriptHelper.Services;

namespace PCBVisorScriptHelper.Forms;

public partial class MainForm : Form
{
    // ── Services ──────────────────────────────────────────────────────────
    private readonly ScriptRunner   _runner  = new();
    private readonly ProfileManager _profiles = new();
    private readonly SettingsManager _settings = new();
    private AppSettings _appSettings = new();

    // ── State ─────────────────────────────────────────────────────────────
    private CancellationTokenSource? _cts;
    private bool _pipelineRunning;
    private string _currentProfileName = "";

    // ── Controls (built in code, no Designer) ─────────────────────────────
    private CommonInputsPanel _commonInputs = null!;
    private Step1Panel        _step1Panel   = null!;
    private Step2Panel        _step2Panel   = null!;
    private Step3Panel        _step3Panel   = null!;
    private Step4Panel        _step4Panel   = null!;
    private TabControl        _stepTabs     = null!;
    private ImageViewerControl _viewerInput  = null!;
    private ImageViewerControl _viewerOutput = null!;
    private TabControl        _viewerTabs   = null!;
    private LogPanel          _logPanel     = null!;
    private SplitContainer    _innerSplit   = null!;

    // ── Toolbar controls ──────────────────────────────────────────────────
    private Button      _btnRunAll;
    private ComboBox    _cmbProfiles;
    private Button      _btnSaveProfile;
    private Button      _btnLoadProfile;
    private ProgressBar _progressBar;
    private Label       _lblProgress;

    // ── Menu ──────────────────────────────────────────────────────────────
    private ToolStripMenuItem _miRecentProfiles = null!;

    public MainForm()
    {
        Text            = "PCBVisor - Antigravity";
        BackColor       = Color.FromArgb(26, 34, 56); // #1A2238 Main background
        ForeColor       = Color.White;
        Font            = new Font("Segoe UI", 10f);
        MinimumSize     = new Size(1000, 600);
        KeyPreview      = true;
        
        BuildLayout();
        WireEvents();

        Load    += OnLoad;
        FormClosing += OnFormClosing;
    }

    // ── Layout ────────────────────────────────────────────────────────────

    private void BuildLayout()
    {
        // Menu bar
        var menu = BuildMenuBar();
        Controls.Add(menu);
        MainMenuStrip = menu;

        // Toolbar
        var toolbar = BuildToolbar();
        Controls.Add(toolbar);

        // Outer split: left config | right viewer
        var outerSplit = new SplitContainer
        {
            Dock             = DockStyle.Fill,
            Orientation      = Orientation.Vertical,
            SplitterWidth    = 5,
            BackColor        = Color.FromArgb(18, 18, 18),
        };
        outerSplit.Panel1.BackColor = Color.FromArgb(26, 34, 56);
        outerSplit.Panel2.BackColor = Color.FromArgb(26, 34, 56);

        // Inner split: top (common + steps) | bottom (log)
        _innerSplit = new SplitContainer
        {
            Dock          = DockStyle.Fill,
            Orientation   = Orientation.Horizontal,
            SplitterWidth = 5,
            BackColor     = Color.FromArgb(18, 18, 18),
        };

        // Common inputs
        _commonInputs = new CommonInputsPanel { Dock = DockStyle.Top };

        // Step tabs
        _stepTabs = BuildStepTabs();

        _innerSplit.Panel1.Controls.Add(_stepTabs);
        _innerSplit.Panel1.Controls.Add(_commonInputs);

        // Log
        _logPanel = new LogPanel { Dock = DockStyle.Fill };
        _innerSplit.Panel2.Controls.Add(_logPanel);

        outerSplit.Panel1.Controls.Add(_innerSplit);

        // Viewer tabs
        _viewerTabs  = new TabControl
        {
            Dock      = DockStyle.Fill,
            Appearance = TabAppearance.FlatButtons,
            BackColor = Color.FromArgb(31, 41, 66),
            Font      = new Font("Segoe UI", 10f),
        };
        _viewerInput  = new ImageViewerControl { Dock = DockStyle.Fill, BorderStyle = BorderStyle.FixedSingle };
        _viewerOutput = new ImageViewerControl { Dock = DockStyle.Fill, BorderStyle = BorderStyle.FixedSingle };
        _viewerInput.SetPlaceholder("Select a Source PNG to preview the input image.");
        _viewerOutput.SetPlaceholder("No output image yet — run the pipeline to generate results.");

        var tabIn  = new TabPage(" Input Image ")  { BackColor = Color.FromArgb(26, 34, 56) };
        var tabOut = new TabPage(" Output Image ") { BackColor = Color.FromArgb(26, 34, 56) };
        tabIn.Controls.Add(_viewerInput);
        tabOut.Controls.Add(_viewerOutput);
        _viewerTabs.TabPages.Add(tabIn);
        _viewerTabs.TabPages.Add(tabOut);

        // Viewer toolbar
        var viewerBar = BuildViewerBar();
        outerSplit.Panel2.Controls.Add(_viewerTabs);
        outerSplit.Panel2.Controls.Add(viewerBar);
        _viewerTabs.BringToFront(); // Fill control must be in front to not overlap Bottom

        Controls.Add(outerSplit);
        outerSplit.BringToFront(); // Fill control must be in front to not overlap Top


        // Fixed sizes
        _innerSplit.SplitterDistance = 480; // Changed default slightly so log is taller
        outerSplit.SplitterDistance = 460;
        _innerSplit.Panel2MinSize    = 120;
    }

    private MenuStrip BuildMenuBar()
    {
        var menu = new MenuStrip { BackColor = Color.FromArgb(45, 45, 48), ForeColor = Color.White };

        // File
        var miFile  = new ToolStripMenuItem("File");
        var miNew   = new ToolStripMenuItem("New Profile",      null, (_, _) => NewProfile())         { ShortcutKeys = Keys.Control | Keys.N };
        var miSave  = new ToolStripMenuItem("Save Profile",     null, (_, _) => SaveProfile())        { ShortcutKeys = Keys.Control | Keys.S };
        var miSaveAs= new ToolStripMenuItem("Save Profile As…", null, (_, _) => SaveProfileAs());
        var miLoad  = new ToolStripMenuItem("Load Profile…",    null, (_, _) => LoadProfileDialog())  { ShortcutKeys = Keys.Control | Keys.O };
        _miRecentProfiles = new ToolStripMenuItem("Recent Profiles");
        var miExit  = new ToolStripMenuItem("Exit",             null, (_, _) => Close());
        miFile.DropDownItems.AddRange(new ToolStripItem[] {
            miNew, miSave, miSaveAs, miLoad,
            new ToolStripSeparator(), _miRecentProfiles,
            new ToolStripSeparator(), miExit });

        // Profiles
        var miProfilesMenu = new ToolStripMenuItem("Profiles");
        var miDelete = new ToolStripMenuItem("Delete Current Profile…", null, (_, _) => DeleteProfile());
        miProfilesMenu.DropDownItems.Add(miDelete);

        // Help
        var miHelp  = new ToolStripMenuItem("Help");
        var miAbout = new ToolStripMenuItem("About", null, (_, _) => ShowAbout());
        miHelp.DropDownItems.Add(miAbout);

        menu.Items.AddRange(new ToolStripItem[] { miFile, miProfilesMenu, miHelp });
        return menu;
    }

    private Panel BuildToolbar()
    {
        var bar = new Panel
        {
            Dock      = DockStyle.Top,
            Height    = 66, // Accommodate 48px buttons + padding
            BackColor = Color.FromArgb(45, 45, 48),
            Padding   = new Padding(8, 8, 8, 8),
        };

        var table = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 1,
            ColumnCount = 7,
            BackColor = Color.Transparent,
            CellBorderStyle = TableLayoutPanelCellBorderStyle.None
        };
        table.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize)); // 0: RunAll
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 160)); // 1: ProgressBar
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); // 2: Label (stretches)
        table.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize)); // 3: Profile Label
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 190)); // 4: ComboBox
        table.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize)); // 5: Save
        table.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize)); // 6: Load

        _btnRunAll      = MakeToolBtn("▶  Run All",   Color.FromArgb(0, 122, 204), 140);
        _btnRunAll.Font = new Font("Segoe UI", 11f, FontStyle.Bold);

        _progressBar = new ProgressBar { Dock = DockStyle.Fill, Margin = new Padding(10, 4, 10, 4), Visible = false };
        
        _lblProgress = new Label
        {
            Text = "",
            BackColor = Color.Black,
            ForeColor = Color.LightGreen,
            AutoSize = false,
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleCenter,
            Font = new Font("Consolas", 10f, FontStyle.Bold),
            Margin = new Padding(0, 4, 10, 4),
            Visible = false
        };

        var lblProfile = new Label { Text = "Profile:", ForeColor = Color.FromArgb(220, 220, 220), AutoSize = true, Anchor = AnchorStyles.Left, Margin = new Padding(10, 0, 4, 0) };
        _cmbProfiles = new ComboBox
        {
            DropDownStyle = ComboBoxStyle.DropDownList,
            BackColor = Color.FromArgb(62, 62, 66),
            ForeColor = Color.White,
            Font   = new Font("Segoe UI", 10f),
            FlatStyle = FlatStyle.Flat,
            Anchor = AnchorStyles.Left | AnchorStyles.Right
        };
        _btnSaveProfile = MakeToolBtn("💾", Color.FromArgb(62, 62, 66), 48);
        _btnSaveProfile.Font = new Font("Segoe UI Emoji", 11f);
        _btnLoadProfile = MakeToolBtn("📂", Color.FromArgb(62, 62, 66), 48);
        _btnLoadProfile.Font = new Font("Segoe UI Emoji", 11f);

        table.Controls.Add(_btnRunAll, 0, 0);
        table.Controls.Add(_progressBar, 1, 0);
        table.Controls.Add(_lblProgress, 2, 0);
        table.Controls.Add(lblProfile, 3, 0);
        table.Controls.Add(_cmbProfiles, 4, 0);
        table.Controls.Add(_btnSaveProfile, 5, 0);
        table.Controls.Add(_btnLoadProfile, 6, 0);

        bar.Controls.Add(table);
        return bar;
    }

    private Panel BuildViewerBar()
    {
        var bar = new Panel { Dock = DockStyle.Bottom, Height = 34, BackColor = Color.FromArgb(45, 45, 48) };
        var flow = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.LeftToRight, Padding = new Padding(4, 4, 4, 0) };

        var btnFit    = MakeSmallBtn("Fit");
        var btnOneOne = MakeSmallBtn("1:1");
        var btnExplore= MakeSmallBtn("Open in Explorer");
        var btnSaveAs = MakeSmallBtn("Save As…");

        btnFit.Click += (_, _) => ActiveViewer?.FitToWindow();
        btnOneOne.Click += (_, _) => ActiveViewer?.ResetZoom();
        btnExplore.Click += (_, _) => OpenActiveInExplorer();
        btnSaveAs.Click  += (_, _) => SaveActiveImageAs();

        flow.Controls.AddRange(new Control[] { btnFit, btnOneOne, btnExplore, btnSaveAs });
        bar.Controls.Add(flow);
        return bar;
    }

    private TabControl BuildStepTabs()
    {
        _step1Panel = new Step1Panel { Dock = DockStyle.Fill };
        _step2Panel = new Step2Panel { Dock = DockStyle.Fill };
        _step3Panel = new Step3Panel { Dock = DockStyle.Fill };
        _step4Panel = new Step4Panel { Dock = DockStyle.Fill };

        _stepTabs = new TabControl
        {
            Dock       = DockStyle.Fill,
            Appearance = TabAppearance.FlatButtons,
            Font       = new Font("Segoe UI", 10f),
            BackColor  = Color.FromArgb(31, 41, 66),
            DrawMode   = TabDrawMode.OwnerDrawFixed
        };

        _stepTabs.DrawItem += (s, e) =>
        {
            var g = e.Graphics;
            var tab = _stepTabs.TabPages[e.Index];
            bool isRunning = tab.Text.StartsWith("⚙");
            
            using var font = isRunning ? new Font(_stepTabs.Font, FontStyle.Bold) : new Font(_stepTabs.Font, FontStyle.Regular);
            using var textBrush = new SolidBrush(Color.White);
            
            Color bgColor;
            if (isRunning) 
                bgColor = Color.FromArgb(28, 120, 50); // Dark green background
            else 
                bgColor = e.State.HasFlag(DrawItemState.Selected) ? Color.FromArgb(62, 62, 66) : Color.FromArgb(45, 45, 48);
                
            using var bgBrush = new SolidBrush(bgColor);
            
            g.FillRectangle(bgBrush, e.Bounds);
            
            var sf = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center };
            g.DrawString(tab.Text, font, textBrush, e.Bounds, sf);
        };

        AddStepTab(_stepTabs, "Step 1 — Expand",  _step1Panel);
        AddStepTab(_stepTabs, "Step 2 — Finder",  _step2Panel);
        AddStepTab(_stepTabs, "Step 3 — Origin",  _step3Panel);
        AddStepTab(_stepTabs, "Step 4 — Display", _step4Panel);

        return _stepTabs;
    }

    private static void AddStepTab(TabControl tabs, string title, Control content)
    {
        var page = new TabPage(title) { BackColor = Color.FromArgb(31, 41, 66), ForeColor = Color.White }; // #1F2942
        page.Controls.Add(content);
        tabs.TabPages.Add(page);
    }

    // ── Event wiring ──────────────────────────────────────────────────────

    private void WireEvents()
    {
        _commonInputs.SourcePngChanged   += OnSourcePngChanged;
        _commonInputs.WorkingDirChanged  += OnWorkingDirChanged;

        _step1Panel.RunRequested += async (_, _) => await RunSingleStep(0);
        _step2Panel.RunRequested += async (_, _) => await RunSingleStep(1);
        _step3Panel.RunRequested += async (_, _) => await RunSingleStep(2);
        _step4Panel.RunRequested += async (_, _) => await RunSingleStep(3);

        _btnRunAll.Click      += async (_, _) => await RunAll();
        _btnSaveProfile.Click += (_, _) => SaveProfile();
        _btnLoadProfile.Click += (_, _) => LoadProfileDialog();

        _cmbProfiles.SelectedIndexChanged += (_, _) =>
        {
            if (_cmbProfiles.SelectedItem is string name && name != _currentProfileName)
                LoadProfileByName(name);
        };

        _runner.OutputReceived += (line, type) => _logPanel.AppendLine(line, type);
    }

    // ── Load / Close ──────────────────────────────────────────────────────

    private void OnLoad(object? s, EventArgs e)
    {
        _appSettings = _settings.Load();

        // Restore window geometry
        if (_appSettings.WindowWidth > 0 && _appSettings.WindowHeight > 0)
        {
            Size = new Size(_appSettings.WindowWidth, _appSettings.WindowHeight);
            if (_appSettings.WindowX != -1 && _appSettings.WindowY != -1)
                Location = new Point(_appSettings.WindowX, _appSettings.WindowY);
            if (_appSettings.WindowMaximized)
                WindowState = FormWindowState.Maximized;
        }

        try
        {
            if (_appSettings.LogPanelHeight > 0 && _innerSplit.Height > 0)
            {
                int dist = _innerSplit.Height - _appSettings.LogPanelHeight;
                if (dist < 100) dist = 100;
                if (dist > _innerSplit.Height - _innerSplit.Panel2MinSize) dist = _innerSplit.Height - _innerSplit.Panel2MinSize;
                _innerSplit.SplitterDistance = dist;
            }
        }
        catch { }

        // Python discovery
        var python = _appSettings.PythonExePath;
        if (string.IsNullOrEmpty(python) || !File.Exists(python))
            python = PythonLocator.Locate(_appSettings.ScriptsDir);
        _commonInputs.SetPythonPath(python);
        _commonInputs.ShowPythonWarning(string.IsNullOrEmpty(python));

        // Scripts dir default to app directory
        if (string.IsNullOrEmpty(_appSettings.ScriptsDir))
            _appSettings.ScriptsDir = AppContext.BaseDirectory;
        _commonInputs.SetScriptsDir(_appSettings.ScriptsDir);

        // Populate profile dropdown
        RefreshProfileDropdown();

        // Auto-load last session
        if (!string.IsNullOrEmpty(_appSettings.LastProfile))
            LoadProfileByName(_appSettings.LastProfile);

        // Keyboard shortcuts
        KeyPreview = true;
        KeyDown += (_, ke) =>
        {
            if (ke.KeyCode == Keys.F5)               { _ = RunAll(); ke.Handled = true; }
            if (ke.Control && ke.KeyCode == Keys.W)  { _logPanel.Clear(); ke.Handled = true; }
        };
    }

    private void OnFormClosing(object? s, FormClosingEventArgs e)
    {
        // Save window state
        _appSettings.WindowMaximized = WindowState == FormWindowState.Maximized;
        if (WindowState == FormWindowState.Normal)
        {
            _appSettings.WindowX      = Location.X;
            _appSettings.WindowY      = Location.Y;
            _appSettings.WindowWidth  = Size.Width;
            _appSettings.WindowHeight = Size.Height;
        }
        _appSettings.PythonExePath = _commonInputs.PythonExe;
        _appSettings.ScriptsDir    = _commonInputs.ScriptsDir;

        try
        {
            if (_innerSplit.Height > _innerSplit.Panel2MinSize)
                _appSettings.LogPanelHeight = _innerSplit.Height - _innerSplit.SplitterDistance;
        }
        catch { }

        // Auto-save profile
        if (_appSettings.AutoSaveOnExit)
        {
            var session = BuildCurrentProfile();
            session.Name = "_last_session";
            _profiles.Save(session);
            _appSettings.LastProfile = "_last_session";
        }

        _settings.Save(_appSettings);
    }

    // ── Path propagation ──────────────────────────────────────────────────

    private void OnSourcePngChanged(object? s, EventArgs e) => PropagateAll();
    private void OnWorkingDirChanged(object? s, EventArgs e) => PropagateAll();

    private void PropagateAll()
    {
        var src = _commonInputs.SourcePng;
        var dir = _commonInputs.WorkingDir;
        if (string.IsNullOrWhiteSpace(src) || string.IsNullOrWhiteSpace(dir)) return;

        var (s1, s2j, s3j, s4) = PathPropagator.RecalculateAll(src, dir);

        _step1Panel.SetInputPng(src);
        _step1Panel.SetOutputPng(s1);
        _step2Panel.SetInputPng(s1);
        _step2Panel.SetOutputDir(dir);
        _step3Panel.SetJsonCandidates(s2j);
        _step3Panel.SetFiducialsCsv(_commonInputs.FiducialsCsv);
        _step3Panel.SetOutputJson(s3j);
        _step4Panel.SetImagePng(s1);
        _step4Panel.SetOriginJson(s3j);
        _step4Panel.SetOutputPng(s4);

        // Load input image
        if (File.Exists(src)) _viewerInput.LoadImage(src);
    }

    // ── Pipeline execution ────────────────────────────────────────────────

    private async Task RunAll()
    {
        if (_pipelineRunning) { StopPipeline(); return; }

        SetPipelineRunning(true);
        _logPanel.AppendLine("=== Run All — Pipeline started ===", Services.LogLineType.Success);

        _progressBar.Style = ProgressBarStyle.Continuous;
        _progressBar.Maximum = 4;
        _progressBar.Value = 0;
        _progressBar.Visible = true;
        _lblProgress.Visible = true;
        _progressBar.Refresh();
        _lblProgress.Refresh();
        Application.DoEvents(); // Force UI update before async work begins

        for (int i = 0; i < 4; i++)
        {
            if (_cts?.IsCancellationRequested == true) break;
            bool ok = await RunStepCore(i);
            if (ok) 
            {
                int target = i + 1;
                // Force WinForms to skip the smooth animation delay by temporarily going past the value
                if (target < _progressBar.Maximum) {
                    _progressBar.Value = target + 1;
                    _progressBar.Value = target;
                } else {
                    _progressBar.Maximum = target + 1;
                    _progressBar.Value = target + 1;
                    _progressBar.Value = target;
                    _progressBar.Maximum = target;
                }
                _progressBar.Refresh();
            }
            if (!ok) break;
        }

        if (_progressBar.Value == 4)
        {
            _lblProgress.Text = "Completed!";
            _progressBar.Refresh();
            _lblProgress.Refresh();
            await Task.Delay(2000);
        }

        SetPipelineRunning(false);
        _progressBar.Visible = false;
        _lblProgress.Visible = false;
    }

    private async Task RunSingleStep(int stepIndex)
    {
        if (_pipelineRunning) return;
        SetPipelineRunning(true);
        await RunStepCore(stepIndex);
        SetPipelineRunning(false);
    }

    private async Task<bool> RunStepCore(int stepIndex)
    {
        var panel = GetStepPanel(stepIndex);

        string err;
        bool isValid = stepIndex switch
        {
            0 => _step1Panel.Validate(out err),
            1 => _step2Panel.Validate(out err),
            2 => _step3Panel.Validate(out err),
            3 => _step4Panel.Validate(out err),
            _ => throw new ArgumentOutOfRangeException()
        };

        if (!isValid)
        {
            MessageBox.Show(err, $"Validation Error - Step {stepIndex + 1}", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return false;
        }

        panel.Status = StepStatus.Running;
        panel.SetRunEnabled(false);

        var scriptName = stepIndex switch
        {
            0 => "expand_image.py",
            1 => "fid_finder.py",
            2 => "origin_finder.py",
            3 => "fid_display.py",
            _ => "unknown.py"
        };
        _logPanel.AppendSeparator($"Step {stepIndex + 1} — {scriptName}");

        var python  = _commonInputs.PythonExe;
        var scripts = _commonInputs.ScriptsDir;
        if (string.IsNullOrWhiteSpace(python) || !File.Exists(python))
        {
            _logPanel.AppendLine("[ERROR] Python executable not configured.", Services.LogLineType.Error);
            panel.Status = StepStatus.Error;
            panel.SetRunEnabled(true);
            return false;
        }

        var scriptPath = Path.Combine(scripts, scriptName);
        var args = stepIndex switch
        {
            0 => _step1Panel.GetParams().BuildArgs(),
            1 => _step2Panel.GetParams().BuildArgs(),
            2 => _step3Panel.GetParams().BuildArgs(),
            3 => _step4Panel.GetParams().BuildArgs(),
            _ => ""
        };

        var originalText = _stepTabs.TabPages[stepIndex].Text;
        _stepTabs.TabPages[stepIndex].Text = "⚙ " + originalText;
        _stepTabs.Invalidate(); // Force redraw for bold/green tab header

        if (!_pipelineRunning)
        {
            _progressBar.Style = ProgressBarStyle.Marquee;
            _progressBar.Visible = true;
            _lblProgress.Visible = true;
            _lblProgress.Text = $"Running: {originalText.Trim()}...";
            _progressBar.Refresh();
            _lblProgress.Refresh();
            Application.DoEvents(); // Force UI update
        }
        else
        {
            _lblProgress.Text = $"Step {stepIndex + 1}/4 : {originalText.Trim()}...";
            _progressBar.Refresh();
            _lblProgress.Refresh();
            Application.DoEvents(); // Force UI update
        }

        try
        {
            _cts = new CancellationTokenSource();
            int exitCode = await _runner.RunAsync(python, scriptPath, args, _cts.Token);

            bool cancelled = _cts.IsCancellationRequested;
            panel.Status = cancelled ? StepStatus.Cancelled
                         : exitCode == 0 ? StepStatus.Success
                         : StepStatus.Error;

            if (exitCode == 0 && !cancelled)
            {
                // Post-step propagation
                PostStepPropagation(stepIndex);
            }

            panel.SetRunEnabled(true);
            return exitCode == 0 && !cancelled;
        }
        finally
        {
            _stepTabs.TabPages[stepIndex].Text = originalText;
            _stepTabs.Invalidate(); // Force redraw to remove bold/green
            
            if (!_pipelineRunning)
            {
                if (panel.Status == StepStatus.Success)
                {
                    _lblProgress.Text = "Completed!";
                    _progressBar.Refresh();
                    _lblProgress.Refresh();
                    await Task.Delay(2000);
                }
                _progressBar.Visible = false;
                _lblProgress.Visible = false;
            }
        }
    }

    private void PostStepPropagation(int stepIndex)
    {
        if (stepIndex == 3)
        {
            // Load output image
            var outPng = _step4Panel.GetOutputPng();
            if (File.Exists(outPng))
            {
                _viewerOutput.LoadImage(outPng);
                _viewerTabs.SelectedIndex = 1;
                _logPanel.AppendLine($"[+] Output image loaded: {outPng}", Services.LogLineType.Success);
            }
        }
        else if (stepIndex == 1)
        {
            // After step 2, propagate the JSON path to step 3
            var dir = _commonInputs.WorkingDir;
            var s1Out = _step1Panel.GetOutputPng();
            var s2Json = PathPropagator.Step2JsonOutput(s1Out, dir);
            _step3Panel.SetJsonCandidates(s2Json);
        }
        else if (stepIndex == 2)
        {
            // After step 3, propagate origin JSON to step 4
            var s3Json = _step3Panel.GetOutputJson();
            _step4Panel.SetOriginJson(s3Json);
        }
    }

    private void StopPipeline()
    {
        _runner.Cancel();
        _cts?.Cancel();
        _logPanel.AppendLine("[WARNING] Pipeline stopped by user.", Services.LogLineType.Warning);
    }

    private void SetPipelineRunning(bool running)
    {
        if (InvokeRequired) { BeginInvoke(() => SetPipelineRunning(running)); return; }
        _pipelineRunning   = running;
        _btnRunAll.Text    = running ? "■  Stop" : "▶  Run All";
        _btnRunAll.BackColor = running ? Color.FromArgb(218, 59, 1) : Color.FromArgb(0, 122, 204);
    }

    private StepPanelBase GetStepPanel(int index) => index switch
    {
        0 => _step1Panel, 1 => _step2Panel, 2 => _step3Panel, 3 => _step4Panel,
        _ => throw new ArgumentOutOfRangeException()
    };

    // ── Profile management ────────────────────────────────────────────────

    private void NewProfile()
    {
        _step1Panel.SetParams(new());
        _step2Panel.SetParams(new());
        _step3Panel.SetParams(new());
        _step4Panel.SetParams(new());
        _currentProfileName = "";
        Text = "PCBVisor Script Helper — [New Profile]";
    }

    private void SaveProfile()
    {
        if (string.IsNullOrEmpty(_currentProfileName))
        { SaveProfileAs(); return; }

        var p = BuildCurrentProfile();
        _profiles.Save(p);
        RefreshProfileDropdown();
        AddRecentProfile(_currentProfileName);
        _logPanel.AppendLine($"[+] Profile saved: {_currentProfileName}", Services.LogLineType.Success);
    }

    private void SaveProfileAs()
    {
        using var dlg = new InputDialog("Save Profile As", "Profile name:", _currentProfileName);
        if (dlg.ShowDialog() != DialogResult.OK || string.IsNullOrWhiteSpace(dlg.Value)) return;
        _currentProfileName = dlg.Value.Trim();
        SaveProfile();
    }

    private void LoadProfileDialog()
    {
        using var dlg = new OpenFileDialog
        {
            InitialDirectory = _profiles.ProfilesDir,
            Filter = "Profile files|*.json",
            Title  = "Load Profile",
        };
        if (dlg.ShowDialog() != DialogResult.OK) return;
        var p = _profiles.LoadFromPath(dlg.FileName);
        if (p != null) ApplyProfile(p);
    }

    private void LoadProfileByName(string name)
    {
        var p = _profiles.Load(name);
        if (p != null) ApplyProfile(p);
    }

    private void DeleteProfile()
    {
        if (string.IsNullOrEmpty(_currentProfileName)) return;
        if (MessageBox.Show($"Delete profile '{_currentProfileName}'?", "Confirm",
            MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
        {
            _profiles.Delete(_currentProfileName);
            _currentProfileName = "";
            RefreshProfileDropdown();
        }
    }

    private void ApplyProfile(PipelineProfile p)
    {
        _currentProfileName = p.Name;
        _commonInputs.SetFromProfile(p.SourcePng, p.FiducialsCsv, p.WorkingDir,
            _commonInputs.PythonExe, _commonInputs.ScriptsDir);
        _step1Panel.SetParams(p.Step1);
        _step2Panel.SetParams(p.Step2);
        _step3Panel.SetParams(p.Step3);
        _step4Panel.SetParams(p.Step4);
        Text = $"PCBVisor Script Helper — {p.Name}";
        AddRecentProfile(p.Name);
    }

    private PipelineProfile BuildCurrentProfile() => new()
    {
        Name        = string.IsNullOrEmpty(_currentProfileName) ? "Untitled" : _currentProfileName,
        SourcePng   = _commonInputs.SourcePng,
        FiducialsCsv= _commonInputs.FiducialsCsv,
        WorkingDir  = _commonInputs.WorkingDir,
        Step1       = _step1Panel.GetParams(),
        Step2       = _step2Panel.GetParams(),
        Step3       = _step3Panel.GetParams(),
        Step4       = _step4Panel.GetParams(),
    };

    private void RefreshProfileDropdown()
    {
        _cmbProfiles.Items.Clear();
        foreach (var name in _profiles.ListProfiles())
            _cmbProfiles.Items.Add(name);
        if (!string.IsNullOrEmpty(_currentProfileName))
            _cmbProfiles.SelectedItem = _currentProfileName;
    }

    private void AddRecentProfile(string name)
    {
        _appSettings.RecentProfiles.Remove(name);
        _appSettings.RecentProfiles.Insert(0, name);
        if (_appSettings.RecentProfiles.Count > 5)
            _appSettings.RecentProfiles = _appSettings.RecentProfiles.Take(5).ToList();
        RefreshRecentMenu();
    }

    private void RefreshRecentMenu()
    {
        _miRecentProfiles.DropDownItems.Clear();
        foreach (var name in _appSettings.RecentProfiles)
        {
            var n = name; // capture
            _miRecentProfiles.DropDownItems.Add(new ToolStripMenuItem(n, null,
                (_, _) => LoadProfileByName(n)));
        }
    }

    // ── Viewer helpers ────────────────────────────────────────────────────

    private ImageViewerControl? ActiveViewer =>
        _viewerTabs.SelectedIndex == 0 ? _viewerInput : _viewerOutput;

    private void OpenActiveInExplorer()
    {
        var path = ActiveViewer?.ImagePath;
        if (!string.IsNullOrEmpty(path) && File.Exists(path))
            System.Diagnostics.Process.Start("explorer.exe", $"/select,\"{path}\"");
    }

    private void SaveActiveImageAs()
    {
        var path = ActiveViewer?.ImagePath;
        if (string.IsNullOrEmpty(path) || !File.Exists(path)) return;

        using var dlg = new SaveFileDialog { Filter = "PNG files|*.png", FileName = Path.GetFileName(path) };
        if (dlg.ShowDialog() == DialogResult.OK)
            File.Copy(path, dlg.FileName, overwrite: true);
    }

    // ── UI helpers ────────────────────────────────────────────────────────

    private static Button MakeToolBtn(string text, Color backColor, int width = 100) => new()
    {
        Text      = text,
        FlatStyle = FlatStyle.Flat,
        BackColor = backColor,
        ForeColor = Color.White,
        Font      = new Font("Segoe UI", 9f),
        Width     = width,
        Height    = 48,
        Margin    = new Padding(4, 0, 4, 0),
        FlatAppearance = { BorderSize = 0 },
    };

    private static Button MakeSmallBtn(string text) => new()
    {
        Text      = text,
        FlatStyle = FlatStyle.Flat,
        BackColor = Color.FromArgb(62, 62, 66),
        ForeColor = Color.White,
        Font      = new Font("Segoe UI", 8.5f),
        Height    = 26,
        AutoSize  = true,
        Margin    = new Padding(3, 2, 3, 2),
        FlatAppearance = { BorderSize = 1, BorderColor = Color.FromArgb(85, 85, 90) },
    };

    private void ShowAbout()
    {
        MessageBox.Show(
            "PCBVisor Script Helper\nVersion 1.0\n\nAuthor: G. OZKESER\n\n" +
            "A GUI wrapper for the four-stage PCB fiducial marker detection pipeline.",
            "About", MessageBoxButtons.OK, MessageBoxIcon.Information);
    }
}
