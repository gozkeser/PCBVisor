namespace PCBVisorScriptHelper.Forms;

/// <summary>
/// Simple single-line text input dialog used for naming profiles.
/// </summary>
public sealed class InputDialog : Form
{
    private readonly TextBox _txt;
    public string Value => _txt.Text;

    public InputDialog(string title, string prompt, string initial = "")
    {
        Text            = title;
        Width           = 360;
        Height          = 140;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox     = false;
        MinimizeBox     = false;
        StartPosition   = FormStartPosition.CenterParent;
        BackColor       = Color.FromArgb(38, 38, 42);
        ForeColor       = Color.White;

        var lbl = new Label { Text = prompt, AutoSize = true, Location = new Point(12, 14), ForeColor = Color.FromArgb(190, 190, 190) };
        _txt = new TextBox { Text = initial, Location = new Point(12, 36), Width = 320, BackColor = Color.FromArgb(55, 55, 60), ForeColor = Color.White, BorderStyle = BorderStyle.FixedSingle };
        _txt.SelectAll();

        var btnOk     = new Button { Text = "OK",     DialogResult = DialogResult.OK,     Location = new Point(160, 70), Width = 80 };
        var btnCancel = new Button { Text = "Cancel",  DialogResult = DialogResult.Cancel,  Location = new Point(252, 70), Width = 80 };
        foreach (var b in new[] { btnOk, btnCancel })
        {
            b.FlatStyle = FlatStyle.Flat;
            b.BackColor = Color.FromArgb(60, 60, 70);
            b.ForeColor = Color.White;
            b.FlatAppearance.BorderColor = Color.FromArgb(90, 90, 100);
        }
        btnOk.BackColor = Color.FromArgb(0, 100, 70);

        AcceptButton = btnOk;
        CancelButton = btnCancel;
        Controls.AddRange(new Control[] { lbl, _txt, btnOk, btnCancel });
    }
}
