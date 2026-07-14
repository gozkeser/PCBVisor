using PCBVisorScriptHelper.Services;

namespace PCBVisorScriptHelper.Helpers;

/// <summary>
/// Classifies a log line by its prefix to determine display color.
/// </summary>
public static class ColorHelper
{
    public static LogLineType ClassifyLine(string line, LogLineType fallback)
    {
        if (line.StartsWith("[ERROR]",   StringComparison.OrdinalIgnoreCase)) return LogLineType.Error;
        if (line.StartsWith("Error",     StringComparison.OrdinalIgnoreCase)) return LogLineType.Error;
        if (line.StartsWith("[WARNING]", StringComparison.OrdinalIgnoreCase)) return LogLineType.Warning;
        if (line.StartsWith("[!]",       StringComparison.OrdinalIgnoreCase)) return LogLineType.Warning;
        if (line.StartsWith("[+]",       StringComparison.OrdinalIgnoreCase)) return LogLineType.Success;
        if (line.StartsWith("Done",      StringComparison.OrdinalIgnoreCase)) return LogLineType.Success;
        return fallback;
    }

    public static Color ForType(LogLineType type) => type switch
    {
        LogLineType.Warning => Color.FromArgb(255, 215, 0),   // gold
        LogLineType.Error   => Color.FromArgb(255, 80,  80),  // tomato
        LogLineType.Success => Color.FromArgb(100, 220, 100), // light green
        _                   => Color.FromArgb(220, 220, 220), // white smoke
    };
}
