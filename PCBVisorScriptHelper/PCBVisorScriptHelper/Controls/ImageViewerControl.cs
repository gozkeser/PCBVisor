using PCBVisorScriptHelper.Helpers;
using PCBVisorScriptHelper.Services;

namespace PCBVisorScriptHelper.Controls;

/// <summary>
/// A Panel-derived control that displays a single PNG image with
/// mouse-wheel zoom and click-drag pan. Used for both Input and Output tabs.
/// </summary>
public sealed class ImageViewerControl : Panel
{
    private Bitmap?  _bitmap;
    private double   _zoom    = 1.0;
    private PointF   _pan     = PointF.Empty;
    private Point    _dragStart;
    private PointF   _panAtDrag;
    private bool     _dragging;
    private string   _imagePath = "";
    private string   _placeholder = "No image loaded.";

    public string? ImagePath => string.IsNullOrEmpty(_imagePath) ? null : _imagePath;

    public ImageViewerControl()
    {
        DoubleBuffered = true;
        BackColor      = Color.FromArgb(30, 30, 30);
        Cursor         = Cursors.Hand;
        ResizeRedraw   = true;
    }

    public void SetPlaceholder(string message)
    {
        _placeholder = message;
        if (_bitmap == null) Invalidate();
    }

    public void LoadImage(string path)
    {
        if (!File.Exists(path)) return;
        try
        {
            var old = _bitmap;
            using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read))
            {
                using var temp = Image.FromStream(stream);
                _bitmap = new Bitmap(temp);
            }
            old?.Dispose();
            _imagePath = path;
            FitToWindow();
            Invalidate();
        }
        catch { /* ignore bad files */ }
    }

    public void ClearImage()
    {
        _bitmap?.Dispose();
        _bitmap    = null;
        _imagePath = "";
        Invalidate();
    }

    public void FitToWindow()
    {
        if (_bitmap == null) return;
        double sx = (double)ClientSize.Width  / _bitmap.Width;
        double sy = (double)ClientSize.Height / _bitmap.Height;
        _zoom = Math.Min(sx, sy);
        _pan  = new PointF(
            (float)((ClientSize.Width  - _bitmap.Width  * _zoom) / 2),
            (float)((ClientSize.Height - _bitmap.Height * _zoom) / 2));
        Invalidate();
    }

    public void ResetZoom()
    {
        _zoom = 1.0;
        _pan  = new PointF(
            (float)((ClientSize.Width  - (_bitmap?.Width  ?? 0)) / 2),
            (float)((ClientSize.Height - (_bitmap?.Height ?? 0)) / 2));
        Invalidate();
    }

    public double ZoomPercent => _zoom * 100.0;

    public event EventHandler? ZoomChanged;

    // ── Paint ────────────────────────────────────────────────────────────────

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        var g = e.Graphics;

        if (_bitmap == null)
        {
            DrawPlaceholder(g);
            return;
        }

        g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
        g.PixelOffsetMode   = System.Drawing.Drawing2D.PixelOffsetMode.HighQuality;

        var destW = (float)(_bitmap.Width  * _zoom);
        var destH = (float)(_bitmap.Height * _zoom);
        var destRect = new RectangleF(_pan.X, _pan.Y, destW, destH);

        // Clip drawing to visible area only for performance on large images
        var clip = RectangleF.Intersect(destRect,
            new RectangleF(0, 0, ClientSize.Width, ClientSize.Height));
        if (clip.IsEmpty) return;

        // Calculate src rect corresponding to the clipped dest rect
        float srcX = (clip.X - _pan.X) / (float)_zoom;
        float srcY = (clip.Y - _pan.Y) / (float)_zoom;
        float srcW = clip.Width  / (float)_zoom;
        float srcH = clip.Height / (float)_zoom;
        var srcRect = new RectangleF(srcX, srcY, srcW, srcH);

        g.DrawImage(_bitmap, clip, srcRect, GraphicsUnit.Pixel);

        // Zoom label
        DrawZoomLabel(g);
    }

    private void DrawPlaceholder(Graphics g)
    {
        using var brush = new SolidBrush(Color.FromArgb(90, 90, 90));
        using var font  = new Font("Segoe UI", 11f);
        var size = g.MeasureString(_placeholder, font);
        g.DrawString(_placeholder, font, brush,
            (ClientSize.Width - size.Width) / 2f,
            (ClientSize.Height - size.Height) / 2f);
    }

    private void DrawZoomLabel(Graphics g)
    {
        if (_bitmap == null) return;
        var label = $"{ZoomPercent:F0}%";
        using var font  = new Font("Segoe UI", 8.5f);
        using var brush = new SolidBrush(Color.FromArgb(160, 200, 200, 200));
        var sz = g.MeasureString(label, font);
        g.DrawString(label, font, brush, ClientSize.Width - sz.Width - 6, ClientSize.Height - sz.Height - 4);
    }

    // ── Mouse ────────────────────────────────────────────────────────────────

    protected override void OnMouseWheel(MouseEventArgs e)
    {
        base.OnMouseWheel(e);
        if (_bitmap == null) return;

        double oldZoom  = _zoom;
        double factor   = e.Delta > 0 ? 1.15 : 1.0 / 1.15;
        _zoom = Math.Clamp(_zoom * factor, 0.02, 50.0);

        // Zoom toward mouse cursor
        float mx = e.X, my = e.Y;
        _pan = new PointF(
            mx - (float)(_zoom / oldZoom) * (mx - _pan.X),
            my - (float)(_zoom / oldZoom) * (my - _pan.Y));

        ZoomChanged?.Invoke(this, EventArgs.Empty);
        Invalidate();
    }

    protected override void OnMouseDown(MouseEventArgs e)
    {
        base.OnMouseDown(e);
        if (e.Button == MouseButtons.Left)
        {
            _dragging  = true;
            _dragStart = e.Location;
            _panAtDrag = _pan;
            Cursor     = Cursors.SizeAll;
        }
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);
        if (_dragging)
        {
            _pan = new PointF(
                _panAtDrag.X + e.X - _dragStart.X,
                _panAtDrag.Y + e.Y - _dragStart.Y);
            Invalidate();
        }
    }

    protected override void OnMouseUp(MouseEventArgs e)
    {
        base.OnMouseUp(e);
        _dragging = false;
        Cursor    = Cursors.Hand;
    }

    protected override void OnResize(EventArgs e)
    {
        base.OnResize(e);
        if (_bitmap != null) FitToWindow();
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing) _bitmap?.Dispose();
        base.Dispose(disposing);
    }
}
