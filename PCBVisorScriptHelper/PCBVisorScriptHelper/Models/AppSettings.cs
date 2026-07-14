namespace PCBVisorScriptHelper.Models;

public class AppSettings
{
    public string PythonExePath   { get; set; } = "";
    public string ScriptsDir      { get; set; } = "";
    public bool   AutoSaveOnExit  { get; set; } = true;
    public int    WindowWidth      { get; set; } = 1280;
    public int    WindowHeight     { get; set; } = 800;
    public int    WindowX          { get; set; } = -1;
    public int    WindowY          { get; set; } = -1;
    public bool   WindowMaximized  { get; set; } = false;
    public List<string> RecentProfiles { get; set; } = new();
    public string LastProfile      { get; set; } = "";
    public int    LogPanelHeight   { get; set; } = 250;
}
