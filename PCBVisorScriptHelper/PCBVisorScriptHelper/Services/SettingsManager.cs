using System.Text.Json;
using PCBVisorScriptHelper.Models;

namespace PCBVisorScriptHelper.Services;

/// <summary>
/// Persists <see cref="AppSettings"/> to %APPDATA%\PCBVisorScriptHelper\settings.json.
/// </summary>
public class SettingsManager
{
    private static readonly JsonSerializerOptions JsonOpts = new() { WriteIndented = true };
    private readonly string _settingsPath;

    public SettingsManager()
    {
        var dir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "PCBVisorScriptHelper");
        Directory.CreateDirectory(dir);
        _settingsPath = Path.Combine(dir, "settings.json");
    }

    public AppSettings Load()
    {
        try
        {
            if (File.Exists(_settingsPath))
            {
                var json = File.ReadAllText(_settingsPath, System.Text.Encoding.UTF8);
                return JsonSerializer.Deserialize<AppSettings>(json, JsonOpts) ?? new AppSettings();
            }
        }
        catch { /* return defaults on any error */ }
        return new AppSettings();
    }

    public void Save(AppSettings settings)
    {
        try
        {
            var json = JsonSerializer.Serialize(settings, JsonOpts);
            File.WriteAllText(_settingsPath, json, System.Text.Encoding.UTF8);
        }
        catch { /* best-effort save */ }
    }
}
