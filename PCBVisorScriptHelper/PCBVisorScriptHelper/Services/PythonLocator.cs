namespace PCBVisorScriptHelper.Services;

/// <summary>
/// Locates a valid Python interpreter, first from PATH, then from
/// common virtual environment locations relative to a scripts directory.
/// </summary>
public static class PythonLocator
{
    private static readonly string[] VenvSubPaths = new[]
    {
        @".venv\Scripts\python.exe",
        @"venv\Scripts\python.exe",
        @"env\Scripts\python.exe",
        @".env\Scripts\python.exe",
    };

    /// <summary>
    /// Searches for python.exe in PATH, then in venv locations
    /// relative to <paramref name="scriptsDir"/>.
    /// Returns the first found path, or empty string if not found.
    /// </summary>
    public static string Locate(string? scriptsDir = null)
    {
        // 1. Check PATH
        var fromPath = FindInPath();
        if (!string.IsNullOrEmpty(fromPath))
            return fromPath;

        // 2. Check venv locations relative to scripts dir
        if (!string.IsNullOrWhiteSpace(scriptsDir) && Directory.Exists(scriptsDir))
        {
            foreach (var rel in VenvSubPaths)
            {
                var candidate = Path.Combine(scriptsDir, rel);
                if (File.Exists(candidate))
                    return candidate;
            }

            // Also check one level up from scripts dir (project root)
            var parent = Path.GetDirectoryName(scriptsDir);
            if (!string.IsNullOrEmpty(parent))
            {
                foreach (var rel in VenvSubPaths)
                {
                    var candidate = Path.Combine(parent, rel);
                    if (File.Exists(candidate))
                        return candidate;
                }
            }
        }

        return "";
    }

    private static string FindInPath()
    {
        var candidates = new[] { "python.exe", "python3.exe" };
        var pathVar = Environment.GetEnvironmentVariable("PATH") ?? "";
        var dirs = pathVar.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries);

        foreach (var exe in candidates)
        {
            // Try where.exe
            var result = RunWhere(exe);
            if (!string.IsNullOrEmpty(result))
                return result;

            // Manual PATH walk as fallback
            foreach (var dir in dirs)
            {
                var full = Path.Combine(dir, exe);
                if (File.Exists(full))
                    return full;
            }
        }

        return "";
    }

    private static string RunWhere(string exeName)
    {
        try
        {
            var psi = new System.Diagnostics.ProcessStartInfo("where.exe", exeName)
            {
                UseShellExecute        = false,
                RedirectStandardOutput = true,
                CreateNoWindow         = true,
            };
            using var p = System.Diagnostics.Process.Start(psi);
            if (p is null) return "";
            var output = p.StandardOutput.ReadLine()?.Trim() ?? "";
            p.WaitForExit();
            return File.Exists(output) ? output : "";
        }
        catch { return ""; }
    }
}
