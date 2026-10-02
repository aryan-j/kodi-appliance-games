using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using Playnite.SDK;
using Playnite.SDK.Events;
using Playnite.SDK.Models;
using Playnite.SDK.Plugins;

namespace GameApplianceOverlay.Playnite;

public sealed class PlayniteOverlayPlugin : GenericPlugin
{
    public static readonly Guid PluginId = new("d5f8c82c-274f-4f05-99e0-5c8ed66a3bc7");

    private readonly ILogger logger;
    private readonly IPlayniteAPI api;
    private readonly object sessionLock = new();
    private readonly PlayniteOverlaySettingsViewModel settings;
    private PlayniteOverlayPipeServer? pipe;
    private Process? overlayProcess;
    private int activeProcessId;
    private Dictionary<string, object>? activeSnapshot;

    public PlayniteOverlayPlugin(IPlayniteAPI api) : base(api)
    {
        this.api = api;
        logger = LogManager.GetLogger();
        settings = new PlayniteOverlaySettingsViewModel(this);
        Properties = new GenericPluginProperties { HasSettings = true };
        SaveDefaultsIfNeeded();
    }

    public override Guid Id => PluginId;

    public override void OnGameStarted(OnGameStartedEventArgs args)
    {
        if (!settings.Settings.Enabled || !settings.Settings.LaunchWithGame ||
            args.StartedProcessId <= 0) return;
        StartSession(args.Game, args.StartedProcessId);
    }

    public override void OnGameStopped(OnGameStoppedEventArgs args)
    {
        if (args.Game == null) return;
        lock (sessionLock)
        {
            if (activeSnapshot == null ||
                !activeSnapshot.TryGetValue("gameId", out var activeId) ||
                !String.Equals(activeId as string, args.Game.Id.ToString(), StringComparison.OrdinalIgnoreCase))
                return;
        }
        StopSession();
    }

    public override ISettings GetSettings(bool firstRunSettings) => settings;

    public override System.Windows.Controls.UserControl GetSettingsView(bool firstRunSettings)
    {
        return new PlayniteOverlaySettingsView { DataContext = settings };
    }

    internal void ApplySettings(PlayniteOverlaySettings newSettings)
    {
        if (!newSettings.Enabled) StopSession();
    }

    private void SaveDefaultsIfNeeded()
    {
        try
        {
            if (LoadPluginSettings<PlayniteOverlaySettings>() == null)
                SavePluginSettings(settings.Settings);
        }
        catch (Exception exception)
        {
            logger.Debug(exception, "Could not persist Playnite overlay defaults.");
        }
    }

    private void StartSession(Game game, int processId)
    {
        StopSession();
        var hostPath = ResolveHostPath();
        if (String.IsNullOrWhiteSpace(hostPath) || !File.Exists(hostPath))
        {
            logger.Warn($"Game Appliance Overlay host was not found: {hostPath}");
            return;
        }

        var startedAt = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var logoPath = ResolveLogoPath(game);
        var snapshot = BuildSnapshot(game, logoPath, startedAt, processId);
        var pipeName = "game-appliance-overlay-" + Process.GetCurrentProcess().Id + "-" + Guid.NewGuid().ToString("N");
        var token = Guid.NewGuid().ToString("N");

        var sessionPipe = new PlayniteOverlayPipeServer(
            pipeName,
            token,
            () => Clone(snapshot),
            message => HandleAction(message, processId),
            exception => logger.Debug(exception, "Playnite overlay pipe disconnected."));
        sessionPipe.Start();

        try
        {
            var arguments = new List<string>
            {
                "--web-ui",
                "--pid", processId.ToString(),
                "--title", game.Name ?? "Game",
                "--genres", BuildGenres(game),
                "--studio", BuildStudio(game),
                "--total-seconds", Math.Max(0, (long)game.Playtime).ToString(),
                "--session-start", startedAt.ToString(),
                "--pipe-name", pipeName,
                "--pipe-token", token
            };
            if (!String.IsNullOrWhiteSpace(logoPath))
            {
                arguments.Add("--logo");
                arguments.Add(logoPath!);
            }
            if (settings.Settings.SuspendGame) arguments.Add("--suspend-game");
            if (settings.Settings.ShowOnGameStart) arguments.Add("--preview");

            var startInfo = new ProcessStartInfo
            {
                FileName = hostPath,
                Arguments = String.Join(" ", arguments.Select(QuoteArgument)),
                WorkingDirectory = Path.GetDirectoryName(hostPath) ?? String.Empty,
                UseShellExecute = false,
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden
            };
            var process = Process.Start(startInfo);
            if (process == null) throw new InvalidOperationException("The overlay host did not start.");

            lock (sessionLock)
            {
                activeProcessId = processId;
                activeSnapshot = snapshot;
                pipe = sessionPipe;
                overlayProcess = process;
            }
            logger.Info($"Started Game Appliance Overlay for {game.Name} (PID {processId}).");
        }
        catch (Exception exception)
        {
            sessionPipe.Dispose();
            logger.Error(exception, "Failed to start Game Appliance Overlay.");
        }
    }

    private void HandleAction(Dictionary<string, object> message, int processId)
    {
        if (!message.TryGetValue("action", out var value)) return;
        var action = value as string;
        if (action == "exit") StopGame(processId);
    }

    private void StopSession()
    {
        PlayniteOverlayPipeServer? oldPipe;
        Process? oldProcess;
        lock (sessionLock)
        {
            oldPipe = pipe;
            oldProcess = overlayProcess;
            pipe = null;
            overlayProcess = null;
            activeSnapshot = null;
            activeProcessId = 0;
        }
        oldPipe?.Dispose();
        if (oldProcess != null)
        {
            try
            {
                if (!oldProcess.HasExited) oldProcess.Kill();
            }
            catch { }
            oldProcess.Dispose();
        }
    }

    private void StopGame(int processId)
    {
        try
        {
            using var process = Process.GetProcessById(processId);
            if (process.HasExited) return;
            process.CloseMainWindow();
            if (!process.WaitForExit(2500) && !process.HasExited)
                process.Kill();
        }
        catch (Exception exception)
        {
            logger.Warn(exception, $"Could not stop game process {processId}.");
        }
    }

    private string ResolveHostPath()
    {
        if (!String.IsNullOrWhiteSpace(settings.Settings.OverlayHostPath))
            return Path.GetFullPath(settings.Settings.OverlayHostPath);
        var extensionDirectory = Path.GetDirectoryName(typeof(PlayniteOverlayPlugin).Assembly.Location) ?? String.Empty;
        var packaged = Path.Combine(extensionDirectory, "companion", "KodiApplianceOverlay-0.4.6.exe");
        if (File.Exists(packaged)) return packaged;
        return Path.Combine(extensionDirectory, "KodiApplianceOverlay-0.4.6.exe");
    }

    private string? ResolveLogoPath(Game game)
    {
        var candidates = settings.Settings.PreferIcon
            ? new[] { game.Icon, game.CoverImage, game.BackgroundImage }
            : new[] { game.CoverImage, game.Icon, game.BackgroundImage };
        foreach (var candidate in candidates)
        {
            if (String.IsNullOrWhiteSpace(candidate)) continue;
            var path = api.Database.GetFullFilePath(candidate);
            if (!String.IsNullOrWhiteSpace(path) && File.Exists(path)) return path;
        }
        return null;
    }

    private static Dictionary<string, object> BuildSnapshot(Game game, string? logoPath, long startedAt, int processId)
    {
        return new Dictionary<string, object>
        {
            ["gameId"] = game.Id.ToString(),
            ["title"] = game.Name ?? "Game",
            ["genres"] = BuildGenres(game),
            ["studio"] = BuildStudio(game),
            ["logoPath"] = logoPath ?? String.Empty,
            ["totalSeconds"] = Math.Max(0, (long)game.Playtime),
            ["sessionStartEpoch"] = startedAt,
            ["processId"] = processId
        };
    }

    private static string BuildGenres(Game game)
    {
        return game.Genres == null ? String.Empty : String.Join(" / ", game.Genres.Select(item => item.Name));
    }

    private static string BuildStudio(Game game)
    {
        var developers = game.Developers?.Select(item => item.Name) ?? Enumerable.Empty<string>();
        var publishers = game.Publishers?.Select(item => item.Name) ?? Enumerable.Empty<string>();
        return String.Join(" / ", developers.Concat(publishers).Where(item => !String.IsNullOrWhiteSpace(item)).Distinct());
    }

    private static Dictionary<string, object> Clone(Dictionary<string, object> source)
    {
        return new Dictionary<string, object>(source);
    }

    private static string QuoteArgument(string value)
    {
        if (value == null) return "\"\"";
        if (value.Length > 0 && value.IndexOfAny(new[] { ' ', '\t', '\"' }) < 0) return value;
        var result = new StringBuilder("\"");
        var slashes = 0;
        foreach (var character in value)
        {
            if (character == '\\')
            {
                slashes++;
                continue;
            }
            if (character == '\"')
            {
                result.Append('\\', slashes * 2 + 1);
                result.Append('\"');
                slashes = 0;
                continue;
            }
            result.Append('\\', slashes);
            result.Append(character);
            slashes = 0;
        }
        result.Append('\\', slashes * 2);
        result.Append('\"');
        return result.ToString();
    }

    public override void Dispose()
    {
        StopSession();
        base.Dispose();
    }
}
