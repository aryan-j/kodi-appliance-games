using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using FormsTimer = System.Windows.Forms.Timer;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace KodiAppliance
{
    internal sealed class WebOverlayForm : Form
    {
        private readonly Process game;
        private readonly string gameTitle;
        private readonly string genres;
        private readonly string studio;
        private readonly string poster;
        private readonly string fanart;
        private readonly long totalSeconds;
        private readonly long sessionStartEpoch;
        private readonly bool suspendOnOverlay;
        private readonly bool previewMode;
        private readonly Native.XInputGetStateEx getState;
        private readonly WebView2 webView;
        private readonly FormsTimer inputTimer;
        private readonly FormsTimer processTimer;
        private readonly FormsTimer metadataTimer;
        private readonly JavaScriptSerializer serializer = new JavaScriptSerializer();
        private readonly string[][] navigationRows = {
            new[] { "return", "exit" },
            new[] { "volume" },
            new[] { "outputDevice" },
            new[] { "wifi", "wifiDetails" },
            new[] { "bluetooth", "bluetoothDetails" },
            new[] { "sleep", "restart", "shutdown" }
        };
        private int focusRow;
        private int focusColumn;
        private ushort previousButtons;
        private bool overlayVisible;
        private bool gameSuspended;
        private bool webReady;
        private bool confirmationVisible;
        private bool confirmationYesFocused;
        private string pendingAction;
        private bool muted;
        private bool wifiEnabled;
        private bool bluetoothEnabled;
        private bool outputDevicePanelVisible;
        private bool connectivityPanelVisible;
        private bool connectivitySnapshotInFlight;
        private bool connectivityActionInFlight;
        private const int OverlayHotKey = 0x4B42;
        private const int HotKeyMessage = 0x0312;

        internal WebOverlayForm(
            Process gameProcess,
            string title,
            bool suspendGame,
            string posterPath,
            string fanartPath,
            string genreText,
            string studioText,
            long accumulatedSeconds,
            long startEpoch,
            bool preview)
        {
            game = gameProcess;
            gameTitle = String.IsNullOrWhiteSpace(title) ? "Game" : title;
            genres = genreText ?? "";
            studio = studioText ?? "";
            poster = posterPath ?? "";
            fanart = fanartPath ?? "";
            totalSeconds = accumulatedSeconds;
            sessionStartEpoch = NormalizeStartEpoch(startEpoch);
            suspendOnOverlay = suspendGame;
            previewMode = preview;
            getState = Native.LoadXInput();

            Text = "Kodi Appliance Overlay";
            AutoScaleMode = AutoScaleMode.None;
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.Manual;
            Bounds = Screen.PrimaryScreen.Bounds;
            TopMost = true;
            ShowInTaskbar = false;
            BackColor = Color.Magenta;
            TransparencyKey = Color.Magenta;
            KeyPreview = true;

            webView = new WebView2 {
                Dock = DockStyle.Fill,
                DefaultBackgroundColor = Color.Transparent,
                TabStop = false
            };
            Controls.Add(webView);

            inputTimer = new FormsTimer { Interval = 60 };
            inputTimer.Tick += PollController;
            processTimer = new FormsTimer { Interval = 1000 };
            processTimer.Tick += CheckGame;
            metadataTimer = new FormsTimer { Interval = 1000 };
            metadataTimer.Tick += UpdateDynamicState;

            Shown += delegate {
                InitializeWebView();
                inputTimer.Start();
                processTimer.Start();
                metadataTimer.Start();
                if (previewMode) ShowOverlay();
                else HideOverlay();
            };
            FormClosed += delegate { ResumeGame(); };
        }

        private async void InitializeWebView()
        {
            try
            {
                string baseDirectory = AppDomain.CurrentDomain.BaseDirectory;
                string uiDirectory = Path.Combine(baseDirectory, "web-ui");
                string userData = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "KodiApplianceOverlay", "WebView2");
                Directory.CreateDirectory(userData);
                CoreWebView2Environment environment =
                    await CoreWebView2Environment.CreateAsync(null, userData);
                await webView.EnsureCoreWebView2Async(environment);
                // The host process is system-DPI aware, while WebView2 applies the
                // monitor scale again to its CSS surface. Normalize to 96 DPI so
                // Claude's 16:9 layout maps to the actual fullscreen client area.
                webView.ZoomFactor = 96.0 / Math.Max(96, DeviceDpi);
                CoreWebView2 core = webView.CoreWebView2;
                core.Settings.AreDefaultContextMenusEnabled = false;
                core.Settings.AreDevToolsEnabled = false;
                core.Settings.IsStatusBarEnabled = false;
                core.Settings.IsZoomControlEnabled = false;
                core.Settings.AreBrowserAcceleratorKeysEnabled = false;
                core.SetVirtualHostNameToFolderMapping(
                    "overlay.local", uiDirectory,
                    CoreWebView2HostResourceAccessKind.DenyCors);
                MapArtwork(core, "poster.local", poster);
                MapArtwork(core, "fanart.local", fanart);
                core.WebMessageReceived += OnWebMessage;
                core.NavigationCompleted += delegate {
                    webReady = true;
                    SendInitialState();
                };
                webView.Source = new Uri("https://overlay.local/index.html");
            }
            catch (Exception exception)
            {
                LogFailure(exception);
                Application.Exit();
            }
        }

        private static void MapArtwork(CoreWebView2 core, string host, string path)
        {
            if (String.IsNullOrWhiteSpace(path) || !File.Exists(path)) return;
            string directory = Path.GetDirectoryName(path);
            if (String.IsNullOrWhiteSpace(directory)) return;
            core.SetVirtualHostNameToFolderMapping(
                host, directory, CoreWebView2HostResourceAccessKind.DenyCors);
        }

        private void OnWebMessage(object sender, CoreWebView2WebMessageReceivedEventArgs args)
        {
            try
            {
                object parsed = serializer.DeserializeObject(args.WebMessageAsJson ?? "{}");
                Dictionary<string, object> message = parsed as Dictionary<string, object>;
                if (message == null) return;
                object actionValue;
                if (!message.TryGetValue("action", out actionValue)) return;
                string action = actionValue as string;
                if (String.IsNullOrWhiteSpace(action) || action.Length > 40) return;
                string ssid = null;
                if (message.ContainsKey("ssid"))
                {
                    object ssidValue = message["ssid"];
                    ssid = ssidValue as string;
                    if (!IsSafeSsid(ssid)) return;
                    ssid = ssid.Trim();
                }
                string deviceId = null;
                if (message.ContainsKey("deviceId"))
                {
                    object deviceIdValue = message["deviceId"];
                    deviceId = deviceIdValue as string;
                    if (!IsSafeDeviceId(deviceId)) return;
                    deviceId = deviceId.Trim();
                }
                HandleAction(action, ssid, deviceId);
            }
            catch { }
        }

        private static bool IsSafeSsid(string ssid)
        {
            if (String.IsNullOrWhiteSpace(ssid) || ssid.Length > 64) return false;
            foreach (char character in ssid)
            {
                if (character < 0x20 || character == 0x7F ||
                    character == '\"' || character == '\'' ||
                    character == '\r' || character == '\n') return false;
            }
            return true;
        }

        private static bool IsSafeDeviceId(string deviceId)
        {
            if (String.IsNullOrWhiteSpace(deviceId) || deviceId.Length > 1024)
                return false;
            foreach (char character in deviceId)
            {
                if (character < 0x20 || character == 0x7F ||
                    character == '\r' || character == '\n') return false;
            }
            return true;
        }

        private void SendInitialState()
        {
            muted = SystemAudio.IsMuted();
            wifiEnabled = SystemRadios.IsOn(RadioKind.WiFi);
            bluetoothEnabled = SystemRadios.IsOn(RadioKind.Bluetooth);
            Dictionary<string, object> payload = new Dictionary<string, object> {
                { "title", gameTitle },
                { "subtitle", BuildSubtitle() },
                { "clock", DateTime.Now.ToString("h:mm tt") },
                { "sessionTime", FormatDuration(CurrentSessionSeconds()) },
                { "totalPlaytime", FormatDuration(totalSeconds) },
                { "posterUrl", ArtworkUrl("poster.local", poster) },
                { "fanartUrl", ArtworkUrl("fanart.local", fanart) },
                { "volume", SystemAudio.GetVolume() },
                { "muted", muted },
                { "outputDevices", SystemAudio.GetOutputDeviceSnapshot() },
                { "wifiEnabled", wifiEnabled },
                { "bluetoothEnabled", bluetoothEnabled },
                { "focusedAction", CurrentAction() }
            };
            Execute("window.overlayUI.initialize(" + serializer.Serialize(payload) + ");");
        }

        private string BuildSubtitle()
        {
            if (String.IsNullOrWhiteSpace(genres)) return studio;
            if (String.IsNullOrWhiteSpace(studio)) return genres;
            return genres + "  |  " + studio;
        }

        private static string ArtworkUrl(string host, string path)
        {
            if (String.IsNullOrWhiteSpace(path) || !File.Exists(path)) return "";
            return "https://" + host + "/" + Uri.EscapeDataString(Path.GetFileName(path));
        }

        private void Execute(string script)
        {
            if (!webReady || webView.CoreWebView2 == null) return;
            webView.CoreWebView2.ExecuteScriptAsync(script);
        }

        private void UpdateDynamicState(object sender, EventArgs args)
        {
            if (!webReady) return;
            Execute("window.overlayUI.setClock(" +
                serializer.Serialize(DateTime.Now.ToString("h:mm tt")) + ");");
            Execute("window.overlayUI.setSessionTime(" +
                serializer.Serialize(FormatDuration(CurrentSessionSeconds())) + ");");
            Dictionary<string, object> volume = new Dictionary<string, object> {
                { "value", SystemAudio.GetVolume() },
                { "muted", muted }
            };
            Execute("window.overlayUI.setVolume(" + serializer.Serialize(volume) + ");");
        }

        private long CurrentSessionSeconds()
        {
            long now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            return Math.Max(0, now - sessionStartEpoch);
        }

        private static long NormalizeStartEpoch(long value)
        {
            long now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            // Accept millisecond epochs defensively, but never render an
            // implausible session when a caller omits or corrupts the value.
            if (value > 100000000000L) value /= 1000;
            if (value <= 0 || value > now || now - value > 7 * 24 * 60 * 60)
                return now;
            return value;
        }

        private static string FormatDuration(long seconds)
        {
            seconds = Math.Max(0, seconds);
            return String.Format("{0:00}:{1:00}:{2:00}",
                seconds / 3600, (seconds / 60) % 60, seconds % 60);
        }

        private string CurrentAction()
        {
            return navigationRows[focusRow][focusColumn];
        }

        private void SetFocus(int row, int column)
        {
            focusRow = Math.Max(0, Math.Min(navigationRows.Length - 1, row));
            focusColumn = Math.Max(0,
                Math.Min(navigationRows[focusRow].Length - 1, column));
            Dictionary<string, object> payload = new Dictionary<string, object> {
                { "action", CurrentAction() }
            };
            Execute("window.overlayUI.setFocus(" + serializer.Serialize(payload) + ");");
        }

        private void MoveFocus(int horizontal, int vertical)
        {
            if (confirmationVisible)
            {
                confirmationYesFocused = !confirmationYesFocused;
                ShowConfirmationVisual();
                return;
            }
            if (outputDevicePanelVisible)
            {
                if (vertical < 0 || horizontal < 0)
                    Execute("window.overlayUI.moveOutputDeviceFocus('up');");
                else if (vertical > 0 || horizontal > 0)
                    Execute("window.overlayUI.moveOutputDeviceFocus('down');");
                return;
            }
            if (vertical != 0)
            {
                int row = (focusRow + vertical + navigationRows.Length)
                    % navigationRows.Length;
                SetFocus(row, Math.Min(focusColumn, navigationRows[row].Length - 1));
                return;
            }
            if (horizontal != 0)
            {
                if (CurrentAction() == "volume")
                {
                    AdjustVolume(horizontal * 5);
                    return;
                }
                int length = navigationRows[focusRow].Length;
                SetFocus(focusRow, (focusColumn + horizontal + length) % length);
            }
        }

        private void HandleAction(string action, string ssid = null, string deviceId = null)
        {
            if (outputDevicePanelVisible)
            {
                if (action == "outputDeviceClose") HideOutputDevicePanel();
                else if (action == "outputDeviceSelect" && IsSafeDeviceId(deviceId))
                    SelectOutputDevice(deviceId.Trim());
                return;
            }
            if (connectivityPanelVisible)
            {
                if (action == "connectivityClose") HideConnectivityPanel();
                else if (action == "wifiRefresh" || action == "bluetoothRefresh")
                    RequestConnectivitySnapshot(true);
                else if (action == "wifiConnect" && IsSafeSsid(ssid))
                    RequestWifiConnect(ssid.Trim());
                else if (action == "wifiSettings") OpenConnectivitySettings(RadioKind.WiFi);
                else if (action == "bluetoothSettings") OpenConnectivitySettings(RadioKind.Bluetooth);
                return;
            }
            if (confirmationVisible)
            {
                if (action == "confirmYes") ConfirmPendingAction();
                else if (action == "confirmNo") HideConfirmation();
                return;
            }
            if (action == "return") HideOverlay();
            else if (action == "exit") ShowConfirmation("Exit " + gameTitle + "?", "exit");
            else if (action == "volume") ToggleMute();
            else if (action == "outputDevice") ShowOutputDevicePanel();
            else if (action == "volumeDown") AdjustVolume(-5);
            else if (action == "volumeUp") AdjustVolume(5);
            else if (action == "mute") ToggleMute();
            else if (action == "wifi") ToggleRadio(RadioKind.WiFi);
            else if (action == "bluetooth") ToggleRadio(RadioKind.Bluetooth);
            else if (action == "wifiDetails") ShowConnectivityPanel(RadioKind.WiFi);
            else if (action == "bluetoothDetails") ShowConnectivityPanel(RadioKind.Bluetooth);
            else if (action == "sleep") ShowConfirmation("Put this PC to sleep?", "sleep");
            else if (action == "restart") ShowConfirmation("Restart this PC?", "restart");
            else if (action == "shutdown") ShowConfirmation("Shut down this PC?", "shutdown");
        }

        private void ActivateCurrent()
        {
            if (confirmationVisible)
            {
                if (confirmationYesFocused) ConfirmPendingAction();
                else HideConfirmation();
                return;
            }
            if (outputDevicePanelVisible)
            {
                Execute("window.overlayUI.activateOutputDeviceFocus();");
                return;
            }
            HandleAction(CurrentAction());
        }

        private void AdjustVolume(int delta)
        {
            int value = SystemAudio.Adjust(delta);
            Dictionary<string, object> payload = new Dictionary<string, object> {
                { "value", value }, { "muted", muted }
            };
            Execute("window.overlayUI.setVolume(" + serializer.Serialize(payload) + ");");
        }

        private void ToggleMute()
        {
            muted = SystemAudio.ToggleMute();
            AdjustVolume(0);
        }

        private void ToggleRadio(RadioKind kind)
        {
            bool enabled = SystemRadios.Toggle(kind);
            if (kind == RadioKind.WiFi) wifiEnabled = enabled;
            else bluetoothEnabled = enabled;
            Dictionary<string, object> payload = new Dictionary<string, object> {
                { "wifiEnabled", wifiEnabled },
                { "bluetoothEnabled", bluetoothEnabled }
            };
            Execute("window.overlayUI.setConnectivity(" +
                serializer.Serialize(payload) + ");");
        }

        private void ShowConnectivityPanel(RadioKind kind)
        {
            connectivityPanelVisible = true;
            Dictionary<string, object> payload = new Dictionary<string, object> {
                { "kind", kind == RadioKind.WiFi ? "wifi" : "bluetooth" },
                { "wifiEnabled", wifiEnabled },
                { "bluetoothEnabled", bluetoothEnabled },
                { "snapshot", SystemConnectivity.GetCachedSnapshot() }
            };
            Execute("window.overlayUI.showConnectivity(" +
                serializer.Serialize(payload) + ");");
            RequestConnectivitySnapshot(false);
        }

        private void RequestConnectivitySnapshot(bool forceRefresh)
        {
            if (!connectivityPanelVisible) return;
            if (connectivitySnapshotInFlight) return;
            connectivitySnapshotInFlight = true;
            ThreadPool.QueueUserWorkItem(delegate {
                object snapshot = SystemConnectivity.GetSnapshot(forceRefresh);
                try
                {
                    if (!IsDisposed && IsHandleCreated)
                    {
                        BeginInvoke((MethodInvoker)delegate {
                            connectivitySnapshotInFlight = false;
                            if (!connectivityPanelVisible) return;
                            Dictionary<string, object> payload = new Dictionary<string, object> {
                                { "snapshot", snapshot },
                                { "wifiEnabled", wifiEnabled },
                                { "bluetoothEnabled", bluetoothEnabled }
                            };
                            Execute("window.overlayUI.setConnectivityDetails(" +
                                serializer.Serialize(payload) + ");");
                        });
                    }
                    else connectivitySnapshotInFlight = false;
                }
                catch { connectivitySnapshotInFlight = false; }
            });
        }

        private void RequestWifiConnect(string ssid)
        {
            if (!connectivityPanelVisible || connectivityActionInFlight ||
                !IsSafeSsid(ssid)) return;
            connectivityActionInFlight = true;
            Execute("window.overlayUI.setConnectivityStatus(" +
                serializer.Serialize("Connecting to " + ssid.Trim() + "…") + ");");
            ThreadPool.QueueUserWorkItem(delegate {
                object result = SystemConnectivity.ConnectWifi(ssid.Trim());
                try
                {
                    if (!IsDisposed && IsHandleCreated)
                    {
                        BeginInvoke((MethodInvoker)delegate {
                            connectivityActionInFlight = false;
                            if (!connectivityPanelVisible) return;
                            Dictionary<string, object> payload = new Dictionary<string, object> {
                                { "result", result }
                            };
                            Execute("window.overlayUI.setConnectivityActionResult(" +
                                serializer.Serialize(payload) + ");");
                            RequestConnectivitySnapshot(true);
                        });
                    }
                    else connectivityActionInFlight = false;
                }
                catch { connectivityActionInFlight = false; }
            });
        }

        private void HideConnectivityPanel()
        {
            if (!connectivityPanelVisible) return;
            connectivityPanelVisible = false;
            Execute("window.overlayUI.hideConnectivity();");
            SetFocus(focusRow, focusColumn);
        }

        private void ShowOutputDevicePanel()
        {
            outputDevicePanelVisible = true;
            Execute("window.overlayUI.showOutputDevices(" +
                serializer.Serialize(SystemAudio.GetOutputDeviceSnapshot()) + ");");
        }

        private void HideOutputDevicePanel()
        {
            if (!outputDevicePanelVisible) return;
            outputDevicePanelVisible = false;
            Execute("window.overlayUI.hideOutputDevices();");
            SetFocus(focusRow, focusColumn);
        }

        private void SelectOutputDevice(string deviceId)
        {
            if (!outputDevicePanelVisible || !IsSafeDeviceId(deviceId)) return;
            bool selected = SystemAudio.SetDefaultOutputDevice(deviceId);
            Execute("window.overlayUI.setOutputDeviceStatus(" +
                serializer.Serialize(selected
                    ? "Output device updated"
                    : "Could not switch output device") + ");");
            Execute("window.overlayUI.setOutputDevices(" +
                serializer.Serialize(SystemAudio.GetOutputDeviceSnapshot()) + ");");
        }

        private void OpenConnectivitySettings(RadioKind kind)
        {
            string uri = kind == RadioKind.WiFi
                ? "ms-settings:network-wifi"
                : "ms-settings:bluetooth";
            try
            {
                Process.Start(new ProcessStartInfo(uri) { UseShellExecute = true });
            }
            catch { }
            HideConnectivityPanel();
            HideOverlay();
        }

        private void ShowConfirmation(string title, string action)
        {
            confirmationVisible = true;
            confirmationYesFocused = false;
            pendingAction = action;
            ShowConfirmationVisual(title);
        }

        private void ShowConfirmationVisual(string title = null)
        {
            Dictionary<string, object> payload = new Dictionary<string, object> {
                { "title", title ?? ConfirmationTitle() },
                { "action", pendingAction ?? "" },
                { "focusedAction", confirmationYesFocused ? "confirmYes" : "confirmNo" }
            };
            Execute("window.overlayUI." +
                (IsInlineConfirmationAction(pendingAction) ? "showPowerPrompt" : "showConfirmation") + "(" +
                serializer.Serialize(payload) + ");");
        }

        private static bool IsInlineConfirmationAction(string action)
        {
            return action == "exit" || action == "sleep" || action == "restart" || action == "shutdown";
        }

        private string ConfirmationTitle()
        {
            if (pendingAction == "exit") return "Exit " + gameTitle + "?";
            if (pendingAction == "sleep") return "Put this PC to sleep?";
            if (pendingAction == "restart") return "Restart this PC?";
            return "Shut down this PC?";
        }

        private void HideConfirmation()
        {
            confirmationVisible = false;
            pendingAction = null;
            Execute("window.overlayUI.hideConfirmation();");
            SetFocus(focusRow, focusColumn);
        }

        private void ConfirmPendingAction()
        {
            string action = pendingAction;
            HideConfirmation();
            if (action == "exit") ExitGameConfirmed();
            else if (action == "sleep")
                Application.SetSuspendState(PowerState.Suspend, true, false);
            else if (action == "restart") StartShutdown("/r /t 0");
            else if (action == "shutdown") StartShutdown("/s /t 0");
        }

        private static void StartShutdown(string arguments)
        {
            Process.Start(new ProcessStartInfo("shutdown.exe", arguments) {
                UseShellExecute = false, CreateNoWindow = true
            });
        }

        private void ExitGameConfirmed()
        {
            ResumeGame();
            try
            {
                if (!game.HasExited)
                {
                    game.CloseMainWindow();
                    if (!game.WaitForExit(3000))
                    {
                        game.Kill();
                        game.WaitForExit(3000);
                    }
                }
            }
            catch { }
            Application.Exit();
        }

        private void PollController(object sender, EventArgs args)
        {
            ushort buttons = PollControllerState();
            ushort pressed = (ushort)(buttons & ~previousButtons);
            previousButtons = buttons;
            if ((pressed & Native.Guide) != 0)
            {
                if (overlayVisible) HideOverlay(); else ShowOverlay();
                return;
            }
            if (!overlayVisible) return;
            if (outputDevicePanelVisible)
            {
                if ((pressed & Native.B) != 0)
                {
                    HideOutputDevicePanel();
                    return;
                }
                if ((pressed & Native.DPadUp) != 0) MoveFocus(0, -1);
                if ((pressed & Native.DPadDown) != 0) MoveFocus(0, 1);
                if ((pressed & Native.DPadLeft) != 0) MoveFocus(-1, 0);
                if ((pressed & Native.DPadRight) != 0) MoveFocus(1, 0);
                if ((pressed & Native.A) != 0) ActivateCurrent();
                return;
            }
            if (connectivityPanelVisible)
            {
                if ((pressed & Native.B) != 0)
                {
                    HideConnectivityPanel();
                    return;
                }
                if ((pressed & Native.DPadUp) != 0) MoveConnectivityFocus("up");
                if ((pressed & Native.DPadDown) != 0) MoveConnectivityFocus("down");
                if ((pressed & Native.DPadLeft) != 0) MoveConnectivityFocus("left");
                if ((pressed & Native.DPadRight) != 0) MoveConnectivityFocus("right");
                if ((pressed & Native.A) != 0) ActivateConnectivityFocus();
                return;
            }
            if ((pressed & Native.B) != 0)
            {
                if (confirmationVisible) HideConfirmation(); else HideOverlay();
                return;
            }
            if ((pressed & Native.DPadUp) != 0) MoveFocus(0, -1);
            if ((pressed & Native.DPadDown) != 0) MoveFocus(0, 1);
            if ((pressed & Native.DPadLeft) != 0) MoveFocus(-1, 0);
            if ((pressed & Native.DPadRight) != 0) MoveFocus(1, 0);
            if ((pressed & Native.VolumeDownCommand) != 0) AdjustVolume(-5);
            if ((pressed & Native.VolumeUpCommand) != 0) AdjustVolume(5);
            if ((pressed & Native.A) != 0) ActivateCurrent();
        }

        private ushort PollControllerState()
        {
            if (getState != null)
            {
                for (uint index = 0; index < 4; index++)
                {
                    Native.XInputState state;
                    if (getState(index, out state) != 0) continue;
                    ushort buttons = state.Gamepad.Buttons;
                    if (state.Gamepad.LeftTrigger > 100)
                        buttons |= Native.VolumeDownCommand;
                    if (state.Gamepad.RightTrigger > 100)
                        buttons |= Native.VolumeUpCommand;
                    return buttons;
                }
            }
            for (uint index = 0; index < 16; index++)
            {
                Native.JoyInfoEx state = new Native.JoyInfoEx {
                    Size = (uint)Marshal.SizeOf(typeof(Native.JoyInfoEx)),
                    Flags = Native.JoyReturnAll
                };
                if (Native.joyGetPosEx(index, ref state) != 0) continue;
                ushort mapped = 0;
                if ((state.Buttons & (1u << 1)) != 0) mapped |= Native.A;
                if ((state.Buttons & (1u << 2)) != 0) mapped |= Native.B;
                if ((state.Buttons & (1u << 12)) != 0) mapped |= Native.Guide;
                if ((state.Buttons & (1u << 6)) != 0) mapped |= Native.VolumeDownCommand;
                if ((state.Buttons & (1u << 7)) != 0) mapped |= Native.VolumeUpCommand;
                if (state.Pov != Native.JoyPovCentered)
                {
                    uint pov = state.Pov % 36000;
                    if (pov >= 31500 || pov <= 4500) mapped |= Native.DPadUp;
                    if (pov >= 13500 && pov <= 22500) mapped |= Native.DPadDown;
                    if (pov >= 22500 && pov <= 31500) mapped |= Native.DPadLeft;
                    if (pov >= 4500 && pov <= 13500) mapped |= Native.DPadRight;
                }
                return mapped;
            }
            return 0;
        }

        private void ShowOverlay()
        {
            overlayVisible = true;
            if (suspendOnOverlay && !gameSuspended)
                gameSuspended = Native.SetProcessSuspended(game.Id, true);
            Bounds = Screen.PrimaryScreen.Bounds;
            Opacity = 1;
            TopMost = true;
            Activate();
            BringToFront();
            SetFocus(0, 0);
        }

        private void HideOverlay()
        {
            if (outputDevicePanelVisible) HideOutputDevicePanel();
            if (connectivityPanelVisible) HideConnectivityPanel();
            overlayVisible = false;
            Opacity = 0;
            TopMost = false;
            Bounds = new Rectangle(-32000, -32000,
                Screen.PrimaryScreen.Bounds.Width, Screen.PrimaryScreen.Bounds.Height);
            ResumeGame();
            try
            {
                if (!game.HasExited)
                    NativeMethods.SetForegroundWindow(game.MainWindowHandle);
            }
            catch { }
        }

        private void ResumeGame()
        {
            if (!gameSuspended) return;
            Native.SetProcessSuspended(game.Id, false);
            gameSuspended = false;
        }

        private void CheckGame(object sender, EventArgs args)
        {
            try { if (game.HasExited) Application.Exit(); }
            catch { Application.Exit(); }
        }

        protected override void OnHandleCreated(EventArgs args)
        {
            base.OnHandleCreated(args);
            Native.RegisterHotKey(Handle, OverlayHotKey,
                Native.Control | Native.Shift, (uint)Keys.F12);
        }

        protected override void OnHandleDestroyed(EventArgs args)
        {
            Native.UnregisterHotKey(Handle, OverlayHotKey);
            base.OnHandleDestroyed(args);
        }

        protected override void WndProc(ref Message message)
        {
            if (message.Msg == HotKeyMessage &&
                message.WParam.ToInt32() == OverlayHotKey)
            {
                if (overlayVisible) HideOverlay(); else ShowOverlay();
                return;
            }
            base.WndProc(ref message);
        }

        protected override bool ProcessCmdKey(ref Message message, Keys keyData)
        {
            if (!overlayVisible) return base.ProcessCmdKey(ref message, keyData);
            Keys key = keyData & Keys.KeyCode;
            if (connectivityPanelVisible)
            {
                if (key == Keys.Escape || key == Keys.Back)
                {
                    HideConnectivityPanel();
                    return true;
                }
                if (key == Keys.Up || key == Keys.W) { MoveConnectivityFocus("up"); return true; }
                if (key == Keys.Down || key == Keys.S) { MoveConnectivityFocus("down"); return true; }
                if (key == Keys.Left) { MoveConnectivityFocus("left"); return true; }
                if (key == Keys.Right) { MoveConnectivityFocus("right"); return true; }
                if (key == Keys.Enter || key == Keys.Space) { ActivateConnectivityFocus(); return true; }
                return base.ProcessCmdKey(ref message, keyData);
            }
            if (key == Keys.Up || key == Keys.W) { MoveFocus(0, -1); return true; }
            if (key == Keys.Down || key == Keys.S) { MoveFocus(0, 1); return true; }
            if (key == Keys.Left) { MoveFocus(-1, 0); return true; }
            if (key == Keys.Right) { MoveFocus(1, 0); return true; }
            if (key == Keys.Enter || key == Keys.Space) { ActivateCurrent(); return true; }
            if (key == Keys.Escape || key == Keys.Back)
            {
                if (confirmationVisible) HideConfirmation(); else HideOverlay();
                return true;
            }
            return base.ProcessCmdKey(ref message, keyData);
        }

        private void MoveConnectivityFocus(string direction)
        {
            Execute("window.overlayUI.moveConnectivityFocus(" +
                serializer.Serialize(direction) + ");");
        }

        private void ActivateConnectivityFocus()
        {
            Execute("window.overlayUI.activateConnectivityFocus();");
        }

        private static void LogFailure(Exception exception)
        {
            try
            {
                string path = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "KodiApplianceOverlay", "web-overlay-error.log");
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                File.AppendAllText(path, DateTime.Now + Environment.NewLine +
                    exception + Environment.NewLine + Environment.NewLine);
            }
            catch { }
        }
    }
}
