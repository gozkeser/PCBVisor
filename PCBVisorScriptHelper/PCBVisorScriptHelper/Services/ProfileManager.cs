using System.Text.Json;
using PCBVisorScriptHelper.Models;

namespace PCBVisorScriptHelper.Services;

/// <summary>
/// Saves and loads <see cref="PipelineProfile"/> objects as JSON files
/// in %APPDATA%\PCBVisorScriptHelper\Profiles\.
/// </summary>
public class ProfileManager
{
    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        WriteIndented = true,
    };

    public string ProfilesDir { get; }

    public ProfileManager()
    {
        ProfilesDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "PCBVisorScriptHelper", "Profiles");
        Directory.CreateDirectory(ProfilesDir);
    }

    /// <summary>Returns the file path for a given profile name.</summary>
    public string GetProfilePath(string name) =>
        Path.Combine(ProfilesDir, SanitizeFileName(name) + ".json");

    /// <summary>Lists all saved profile names (sorted alphabetically).</summary>
    public IReadOnlyList<string> ListProfiles()
    {
        return Directory.GetFiles(ProfilesDir, "*.json")
            .Select(f => Path.GetFileNameWithoutExtension(f))
            .OrderBy(n => n, StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    /// <summary>Saves the profile to disk. Uses <c>profile.Name</c> as the file name.</summary>
    public void Save(PipelineProfile profile)
    {
        var path = GetProfilePath(profile.Name);
        var json = JsonSerializer.Serialize(profile, JsonOpts);
        File.WriteAllText(path, json, System.Text.Encoding.UTF8);
    }

    /// <summary>Loads a profile by name.</summary>
    public PipelineProfile? Load(string name)
    {
        var path = GetProfilePath(name);
        if (!File.Exists(path)) return null;
        var json = File.ReadAllText(path, System.Text.Encoding.UTF8);
        return JsonSerializer.Deserialize<PipelineProfile>(json, JsonOpts);
    }

    /// <summary>Loads a profile from an arbitrary file path.</summary>
    public PipelineProfile? LoadFromPath(string filePath)
    {
        if (!File.Exists(filePath)) return null;
        var json = File.ReadAllText(filePath, System.Text.Encoding.UTF8);
        return JsonSerializer.Deserialize<PipelineProfile>(json, JsonOpts);
    }

    /// <summary>Deletes a saved profile by name.</summary>
    public bool Delete(string name)
    {
        var path = GetProfilePath(name);
        if (!File.Exists(path)) return false;
        File.Delete(path);
        return true;
    }

    private static string SanitizeFileName(string name)
    {
        var invalid = Path.GetInvalidFileNameChars();
        return string.Concat(name.Select(c => invalid.Contains(c) ? '_' : c));
    }
}
