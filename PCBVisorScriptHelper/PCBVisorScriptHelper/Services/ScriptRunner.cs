using System.Diagnostics;
using PCBVisorScriptHelper.Helpers;

namespace PCBVisorScriptHelper.Services;

public enum LogLineType { Info, Warning, Error, Success }

public class ScriptRunner
{
    public event Action<string, LogLineType>? OutputReceived;

    private Process? _process;

    /// <summary>
    /// Launches the given Python script as a child process, streams stdout/stderr
    /// back through OutputReceived in real time, and returns the exit code.
    /// </summary>
    public async Task<int> RunAsync(
        string pythonExe,
        string scriptPath,
        string arguments,
        CancellationToken token = default)
    {
        var psi = new ProcessStartInfo
        {
            FileName               = pythonExe,
            Arguments              = $"\"{scriptPath}\" {arguments}",
            UseShellExecute        = false,
            RedirectStandardOutput = true,
            RedirectStandardError  = true,
            CreateNoWindow         = true,
            StandardOutputEncoding = System.Text.Encoding.UTF8,
            StandardErrorEncoding  = System.Text.Encoding.UTF8,
        };

        _process = new Process { StartInfo = psi, EnableRaisingEvents = true };

        try
        {
            _process.Start();
        }
        catch (Exception ex)
        {
            OutputReceived?.Invoke($"[ERROR] Failed to start process: {ex.Message}", LogLineType.Error);
            return -1;
        }

        // Read stdout and stderr concurrently to avoid deadlocks
        var stdoutTask = ReadStreamAsync(_process.StandardOutput, LogLineType.Info, token);
        var stderrTask = ReadStreamAsync(_process.StandardError,  LogLineType.Error, token);

        await Task.WhenAll(stdoutTask, stderrTask);

        try
        {
            await _process.WaitForExitAsync(token);
        }
        catch (OperationCanceledException)
        {
            Cancel();
            return -2;
        }

        return _process.ExitCode;
    }

    /// <summary>Kills the running process tree.</summary>
    public void Cancel()
    {
        try
        {
            if (_process is { HasExited: false })
                _process.Kill(entireProcessTree: true);
        }
        catch { /* process may have already exited */ }
    }

    private async Task ReadStreamAsync(
        StreamReader reader, LogLineType defaultType, CancellationToken token)
    {
        try
        {
            while (!reader.EndOfStream && !token.IsCancellationRequested)
            {
                var line = await reader.ReadLineAsync(token).ConfigureAwait(false);
                if (line is null) break;
                var lineType = ColorHelper.ClassifyLine(line, defaultType);
                OutputReceived?.Invoke(line, lineType);
            }
        }
        catch (OperationCanceledException) { }
        catch (Exception ex)
        {
            OutputReceived?.Invoke($"[ERROR] Stream read error: {ex.Message}", LogLineType.Error);
        }
    }
}
