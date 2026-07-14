using PCBVisorScriptHelper.Helpers;
using PCBVisorScriptHelper.Services;

namespace PCBVisorScriptHelper.Controls;

/// <summary>
/// Log output panel: a dark RichTextBox with color-coded lines,
/// auto-scroll, line-count cap, Clear, and Copy-to-Clipboard buttons.
/// </summary>
public sealed class LogPanel : UserControl
{
    private const int MaxLines = 5000;

    private readonly RichTextBox _rtb;
    private readonly Button      _btnClear;
    private readonly Button      _btnCopy;
    private readonly Label       _lblTitle;

    public LogPanel()
    {
        // ── Title + buttons strip ─────────────────────────────────────────
        _lblTitle = new Label
        {
            Text      = "Pipeline Output",
            ForeColor = Color.FromArgb(180, 180, 180),
            Font      = new Font("Segoe UI", 9f, FontStyle.Bold),
            AutoSize  = true,
            Padding   = new Padding(4, 0, 0, 0),
        };

        _btnClear = MakeButton("🗑", Color.FromArgb(80, 80, 80));
        _btnCopy  = MakeButton("📋",  Color.FromArgb(10, 132, 255)); // Accent color
        _btnClear.Click += (_, _) => Clear();
        _btnCopy.Click  += (_, _) => CopyToClipboard();

        var strip = new Panel
        {
            Dock      = DockStyle.Top,
            Height    = 28,
            BackColor = Color.FromArgb(40, 40, 40),
            Padding   = new Padding(4, 3, 4, 0),
        };
        _btnCopy.Dock  = DockStyle.Right;
        _btnClear.Dock = DockStyle.Right;
        strip.Controls.Add(_lblTitle);
        strip.Controls.Add(_btnClear);
        strip.Controls.Add(_btnCopy);

        // ── RichTextBox ───────────────────────────────────────────────────
        _rtb = new RichTextBox
        {
            Dock        = DockStyle.Fill,
            ReadOnly    = true,
            BackColor   = Color.FromArgb(15, 21, 34), // #0F1522
            ForeColor   = Color.FromArgb(220, 220, 220),
            Font        = new Font("Consolas", 10f),
            BorderStyle = BorderStyle.None,
            WordWrap    = false,
            ScrollBars  = RichTextBoxScrollBars.Both,
        };

        Controls.Add(_rtb);
        Controls.Add(strip);
        BackColor = Color.FromArgb(15, 21, 34);
    }

    // ── Public API ────────────────────────────────────────────────────────

    public void AppendLine(string text, LogLineType type)
    {
        if (InvokeRequired)
        {
            BeginInvoke(() => AppendLine(text, type));
            return;
        }

        TrimIfNeeded();

        _rtb.SelectionStart  = _rtb.TextLength;
        _rtb.SelectionLength = 0;
        _rtb.SelectionColor  = ColorHelper.ForType(type);
        _rtb.AppendText(text + "\n");
        _rtb.SelectionColor  = _rtb.ForeColor;

        ScrollToBottom();
    }

    public void AppendSeparator(string label)
    {
        if (InvokeRequired) { BeginInvoke(() => AppendSeparator(label)); return; }

        var ts   = DateTime.Now.ToString("HH:mm:ss");
        var line = new string('─', 64);
        var msg  = $"\n{line}\n  {label}  [{ts}]\n{line}\n";

        _rtb.SelectionStart  = _rtb.TextLength;
        _rtb.SelectionLength = 0;
        _rtb.SelectionColor  = Color.FromArgb(100, 180, 255);
        _rtb.AppendText(msg);
        _rtb.SelectionColor  = _rtb.ForeColor;

        ScrollToBottom();
    }

    public void Clear()
    {
        if (InvokeRequired) { BeginInvoke(Clear); return; }
        _rtb.Clear();
    }

    public void CopyToClipboard()
    {
        if (InvokeRequired) { BeginInvoke(CopyToClipboard); return; }
        if (!string.IsNullOrEmpty(_rtb.Text))
            Clipboard.SetText(_rtb.Text);
    }

    // ── Private helpers ───────────────────────────────────────────────────

    private void ScrollToBottom()
    {
        _rtb.SelectionStart = _rtb.TextLength;
        _rtb.ScrollToCaret();
    }

    private void TrimIfNeeded()
    {
        var lines = _rtb.Lines;
        if (lines.Length < MaxLines) return;

        // Remove the first 500 lines to avoid frequent trimming
        var keep = lines.Skip(500).ToArray();
        _rtb.Lines = keep;
    }

    private static Button MakeButton(string text, Color back)
    {
        return new Button
        {
            Text      = text,
            FlatStyle = FlatStyle.Flat,
            BackColor = back,
            ForeColor = Color.White,
            Font      = new Font("Segoe UI Emoji", 10f),
            Width     = 36,
            Height    = 24,
            Margin    = new Padding(2, 0, 2, 0),
            FlatAppearance = { BorderSize = 0 },
        };
    }
}
