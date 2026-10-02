using System;
using System.Collections.Generic;
using System.IO;
using System.ComponentModel;
using Playnite.SDK;

namespace GameApplianceOverlay.Playnite;

public abstract class NotifyPropertyChangedObject : INotifyPropertyChanged
{
    public event PropertyChangedEventHandler? PropertyChanged;

    protected bool SetValue<T>(ref T field, T value, string propertyName)
    {
        if (EqualityComparer<T>.Default.Equals(field, value)) return false;
        field = value;
        OnPropertyChanged(propertyName);
        return true;
    }

    protected void OnPropertyChanged(string propertyName)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}

public sealed class PlayniteOverlaySettings : NotifyPropertyChangedObject
{
    private bool enabled = true;
    public bool Enabled
    {
        get => enabled;
        set => SetValue(ref enabled, value, nameof(Enabled));
    }

    private bool launchWithGame = true;
    public bool LaunchWithGame
    {
        get => launchWithGame;
        set => SetValue(ref launchWithGame, value, nameof(LaunchWithGame));
    }

    private bool showOnGameStart;
    public bool ShowOnGameStart
    {
        get => showOnGameStart;
        set => SetValue(ref showOnGameStart, value, nameof(ShowOnGameStart));
    }

    private bool suspendGame;
    public bool SuspendGame
    {
        get => suspendGame;
        set => SetValue(ref suspendGame, value, nameof(SuspendGame));
    }

    private bool preferIcon = true;
    public bool PreferIcon
    {
        get => preferIcon;
        set => SetValue(ref preferIcon, value, nameof(PreferIcon));
    }

    private string overlayHostPath = string.Empty;
    public string OverlayHostPath
    {
        get => overlayHostPath;
        set => SetValue(ref overlayHostPath, value ?? string.Empty, nameof(OverlayHostPath));
    }
}

public sealed class PlayniteOverlaySettingsViewModel : NotifyPropertyChangedObject, ISettings
{
    private readonly PlayniteOverlayPlugin plugin;

    public PlayniteOverlaySettings Settings { get; private set; }

    public PlayniteOverlaySettingsViewModel(PlayniteOverlayPlugin plugin)
    {
        this.plugin = plugin;
        Settings = plugin.LoadPluginSettings<PlayniteOverlaySettings>() ?? new PlayniteOverlaySettings();
    }

    public void BeginEdit()
    {
    }

    public void CancelEdit()
    {
        Settings = plugin.LoadPluginSettings<PlayniteOverlaySettings>() ?? new PlayniteOverlaySettings();
        OnPropertyChanged(nameof(Settings));
    }

    public void EndEdit()
    {
        plugin.SavePluginSettings(Settings);
        plugin.ApplySettings(Settings);
    }

    public bool VerifySettings(out List<string> errors)
    {
        errors = new List<string>();
        if (Settings.LaunchWithGame && !String.IsNullOrWhiteSpace(Settings.OverlayHostPath) &&
            !File.Exists(Settings.OverlayHostPath))
        {
            errors.Add("The configured overlay host executable does not exist.");
        }
        return errors.Count == 0;
    }
}
