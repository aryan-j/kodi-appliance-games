using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace KodiAppliance
{
    internal static class Native
    {
        [StructLayout(LayoutKind.Sequential)]
        internal struct XInputGamepad
        {
            internal ushort Buttons;
            internal byte LeftTrigger;
            internal byte RightTrigger;
            internal short ThumbLX;
            internal short ThumbLY;
            internal short ThumbRX;
            internal short ThumbRY;
        }

        [StructLayout(LayoutKind.Sequential)]
        internal struct XInputState
        {
            internal uint PacketNumber;
            internal XInputGamepad Gamepad;
        }

        [StructLayout(LayoutKind.Sequential)]
        internal struct JoyInfoEx
        {
            internal uint Size;
            internal uint Flags;
            internal uint X;
            internal uint Y;
            internal uint Z;
            internal uint R;
            internal uint U;
            internal uint V;
            internal uint Buttons;
            internal uint ButtonNumber;
            internal uint Pov;
            internal uint Reserved1;
            internal uint Reserved2;
        }

        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        internal delegate uint XInputGetStateEx(uint index, out XInputState state);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
        private static extern IntPtr LoadLibrary(string fileName);

        [DllImport("kernel32.dll")]
        private static extern IntPtr GetProcAddress(IntPtr module, IntPtr ordinal);

        [DllImport("user32.dll")]
        internal static extern void keybd_event(byte key, byte scan, uint flags, UIntPtr extraInfo);

        [DllImport("user32.dll")]
        internal static extern bool RegisterHotKey(IntPtr window, int id, uint modifiers, uint key);

        [DllImport("user32.dll")]
        internal static extern bool UnregisterHotKey(IntPtr window, int id);

        [DllImport("user32.dll")]
        internal static extern bool SetProcessDPIAware();

        [DllImport("winmm.dll")]
        internal static extern uint joyGetPosEx(uint joystickId, ref JoyInfoEx info);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenProcess(uint access, bool inheritHandle, int processId);

        [DllImport("kernel32.dll")]
        private static extern bool CloseHandle(IntPtr handle);

        [DllImport("ntdll.dll")]
        private static extern int NtSuspendProcess(IntPtr processHandle);

        [DllImport("ntdll.dll")]
        private static extern int NtResumeProcess(IntPtr processHandle);

        internal const ushort DPadUp = 0x0001;
        internal const ushort DPadDown = 0x0002;
        internal const ushort DPadLeft = 0x0004;
        internal const ushort DPadRight = 0x0008;
        internal const ushort A = 0x1000;
        internal const ushort B = 0x2000;
        internal const ushort Guide = 0x0400;
        internal const ushort VolumeDownCommand = 0x4000;
        internal const ushort VolumeUpCommand = 0x8000;

        internal const byte VolumeMute = 0xAD;
        internal const byte VolumeDown = 0xAE;
        internal const byte VolumeUp = 0xAF;
        internal const uint KeyUp = 0x0002;
        internal const uint Control = 0x0002;
        internal const uint Shift = 0x0004;
        internal const uint JoyReturnAll = 0x000000FF;
        internal const uint JoyPovCentered = 0x0000FFFF;
        private const uint ProcessSuspendResume = 0x0800;

        internal static bool SetProcessSuspended(int processId, bool suspended)
        {
            IntPtr handle = OpenProcess(ProcessSuspendResume, false, processId);
            if (handle == IntPtr.Zero) return false;
            try
            {
                return (suspended
                    ? NtSuspendProcess(handle)
                    : NtResumeProcess(handle)) == 0;
            }
            finally
            {
                CloseHandle(handle);
            }
        }

        internal static XInputGetStateEx LoadXInput()
        {
            string[] dlls = { "xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll" };
            foreach (string dll in dlls)
            {
                IntPtr module = LoadLibrary(dll);
                if (module == IntPtr.Zero) continue;
                IntPtr address = GetProcAddress(module, new IntPtr(100));
                if (address != IntPtr.Zero)
                    return (XInputGetStateEx)Marshal.GetDelegateForFunctionPointer(
                        address, typeof(XInputGetStateEx));
            }
            return null;
        }

        internal static void MediaKey(byte key)
        {
            keybd_event(key, 0, 0, UIntPtr.Zero);
            keybd_event(key, 0, KeyUp, UIntPtr.Zero);
        }
    }

    internal sealed class OverlayForm : Form
    {
        private readonly Process game;
        private readonly string gameTitle;
        private readonly Native.XInputGetStateEx getState;
        private readonly bool suspendOnOverlay;
        private readonly Timer inputTimer;
        private readonly Timer processTimer;
        private readonly Timer metadataTimer;
        private readonly List<Button[]> navigationRows = new List<Button[]>();
        private readonly RoundedPanel controlCard;
        private readonly RoundedPanel statsCard;
        private readonly RoundedPictureBox logoBox;
        private readonly VolumeMeter volumeMeter;
        private readonly Label sessionValue;
        private readonly Label totalValue;
        private readonly Label clockLabel;
        private readonly RoundedButton muteButton;
        private readonly RoundedButton wifiButton;
        private readonly RoundedButton bluetoothButton;
        private readonly Image backgroundArtwork;
        private readonly long sessionStartEpoch;
        private readonly Panel confirmationPanel;
        private readonly Label confirmationLabel;
        private readonly Button confirmationYes;
        private readonly Button confirmationNo;
        private ushort previousButtons;
        private bool overlayVisible;
        private bool gameSuspended;
        private Action confirmedAction;
        private const int OverlayHotKey = 0x4B41;
        private const int HotKeyMessage = 0x0312;

        internal OverlayForm(
            Process gameProcess,
            string title,
            bool suspendGame,
            string logo,
            string fanart,
            string genres,
            string studio,
            long totalSeconds,
            long startEpoch,
            string fontRegular,
            string fontBold,
            bool previewMode)
        {
            UiFonts.Initialize(fontRegular, fontBold);
            game = gameProcess;
            gameTitle = String.IsNullOrWhiteSpace(title) ? "Game" : title;
            suspendOnOverlay = suspendGame;
            sessionStartEpoch = startEpoch;
            getState = Native.LoadXInput();
            backgroundArtwork = DrawingUtil.LoadImage(fanart);

            Text = "Kodi Appliance Overlay";
            AutoScaleMode = AutoScaleMode.None;
            FormBorderStyle = FormBorderStyle.None;
            WindowState = FormWindowState.Maximized;
            StartPosition = FormStartPosition.Manual;
            TopMost = true;
            ShowInTaskbar = false;
            BackColor = Color.Black;
            Opacity = 1;
            KeyPreview = true;
            DoubleBuffered = true;

            Panel header = new Panel {
                Dock = DockStyle.None,
                Height = 128,
                BackColor = Color.Transparent,
                Padding = new Padding(62, 30, 62, 0)
            };
            Label titleLabel = CreateLabel(gameTitle.ToUpperInvariant(), 28, true);
            titleLabel.AutoSize = true;
            titleLabel.Location = new Point(62, 30);
            string subtitle = String.Join("  |  ", new string[] { genres, studio });
            subtitle = subtitle.Trim(' ', '|');
            Label subtitleLabel = CreateLabel(subtitle, 12, false);
            subtitleLabel.ForeColor = ArcticPalette.ForegroundMuted;
            subtitleLabel.AutoSize = true;
            subtitleLabel.Location = new Point(64, 82);
            clockLabel = CreateLabel("", 15, true);
            clockLabel.AutoSize = false;
            clockLabel.TextAlign = ContentAlignment.MiddleRight;
            clockLabel.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            clockLabel.Bounds = new Rectangle(Width - 260, 38, 190, 45);
            header.Controls.Add(titleLabel);
            header.Controls.Add(subtitleLabel);
            header.Controls.Add(clockLabel);
            Controls.Add(header);

            PromptLegend prompts = new PromptLegend {
                Dock = DockStyle.None,
                Height = 68,
                Padding = new Padding(62, 0, 0, 0),
                BackColor = ArcticPalette.Panel
            };
            Controls.Add(prompts);

            Panel content = new Panel {
                Dock = DockStyle.None,
                Padding = new Padding(62, 12, 62, 24),
                BackColor = Color.Transparent
            };
            Controls.Add(content);
            Action layoutRoot = delegate {
                header.Bounds = new Rectangle(0, 0, ClientSize.Width, 128);
                clockLabel.Bounds = new Rectangle(
                    Math.Max(0, ClientSize.Width - 260), 38, 190, 45);
                prompts.Bounds = new Rectangle(
                    62, Math.Max(0, ClientSize.Height - 68),
                    Math.Max(1, ClientSize.Width - 124), 68);
                content.Bounds = new Rectangle(
                    62, 140, Math.Max(1, ClientSize.Width - 124),
                    Math.Max(1, ClientSize.Height - 232));
            };
            Resize += delegate { layoutRoot(); };

            controlCard = new RoundedPanel {
                Dock = DockStyle.None,
                Width = 748,
                CornerRadius = 32,
                BackColor = ArcticPalette.Panel
            };
            content.Controls.Add(controlCard);

            Panel artColumn = new Panel {
                Dock = DockStyle.None,
                Width = 420,
                BackColor = Color.Transparent
            };
            content.Controls.Add(artColumn);
            logoBox = new RoundedPictureBox {
                Dock = DockStyle.Top,
                Height = 610,
                CornerRadius = 28,
                Image = DrawingUtil.LoadImage(logo)
            };
            artColumn.Controls.Add(logoBox);
            statsCard = new RoundedPanel {
                Dock = DockStyle.Bottom,
                Height = 128,
                CornerRadius = 22,
                BackColor = ArcticPalette.Panel
            };
            artColumn.Controls.Add(statsCard);
            Action layoutContent = delegate {
                controlCard.Bounds = new Rectangle(
                    0, 0, 748, Math.Max(1, content.ClientSize.Height));
                prompts.Bounds = new Rectangle(
                    24, Math.Max(710, controlCard.ClientSize.Height - 66),
                    700, 54);
            };
            content.Resize += delegate { layoutContent(); };
            Action layoutArtwork = delegate {
                int artworkX = Math.Max(820, ClientSize.Width - 482);
                logoBox.Bounds = new Rectangle(artworkX, 152, 360, 600);
                statsCard.Bounds = new Rectangle(artworkX, 774, 360, 128);
            };
            Resize += delegate { layoutArtwork(); };

            sessionValue = CreateLabel("00:00:00", 18, true);
            sessionValue.Bounds = new Rectangle(24, 20, 170, 36);
            totalValue = CreateLabel(FormatDuration(totalSeconds), 18, true);
            totalValue.Bounds = new Rectangle(218, 20, 175, 36);
            Label sessionCaption = CreateLabel("THIS SESSION", 9, false);
            sessionCaption.ForeColor = ArcticPalette.ForegroundMuted;
            sessionCaption.Bounds = new Rectangle(24, 62, 170, 28);
            Label totalCaption = CreateLabel("TOTAL PLAY TIME", 9, false);
            totalCaption.ForeColor = ArcticPalette.ForegroundMuted;
            totalCaption.Bounds = new Rectangle(218, 62, 175, 28);
            statsCard.Controls.Add(sessionValue);
            statsCard.Controls.Add(totalValue);
            statsCard.Controls.Add(sessionCaption);
            statsCard.Controls.Add(totalCaption);
            Controls.Add(logoBox);
            Controls.Add(statsCard);
            controlCard.Controls.Add(prompts);

            RoundedPanel gameGroup = MakeGroupPanel(new Rectangle(24, 24, 700, 152));
            RoundedPanel audioGroup = MakeGroupPanel(new Rectangle(24, 194, 700, 210));
            RoundedPanel connectionGroup = MakeGroupPanel(new Rectangle(24, 422, 700, 132));
            RoundedPanel powerGroup = MakeGroupPanel(new Rectangle(24, 572, 700, 132));

            Label gameSection = CreateSectionLabel("GAME", 16);
            RoundedButton returnButton = MakeButton("Return to Game", delegate { HideOverlay(); });
            RoundedButton exitButton = MakeButton("Exit Game", ExitGame);
            returnButton.IconKind = ButtonIcon.Return;
            exitButton.IconKind = ButtonIcon.Exit;
            returnButton.Bounds = new Rectangle(18, 55, 322, 72);
            exitButton.Bounds = new Rectangle(360, 55, 322, 72);

            Label audioSection = CreateSectionLabel("AUDIO", 16);
            RoundedButton volumeDown = MakeButton("", delegate { AdjustVolume(-5); });
            RoundedButton volumeUp = MakeButton("", delegate { AdjustVolume(5); });
            volumeDown.IconKind = ButtonIcon.VolumeDown;
            volumeUp.IconKind = ButtonIcon.VolumeUp;
            volumeDown.Bounds = new Rectangle(18, 52, 78, 62);
            volumeUp.Bounds = new Rectangle(604, 52, 78, 62);
            volumeMeter = new VolumeMeter {
                Bounds = new Rectangle(118, 57, 464, 52),
                Value = SystemAudio.GetVolume()
            };
            muteButton = MakeButton("Mute / Unmute", delegate { ToggleMute(); });
            muteButton.IconKind = ButtonIcon.Mute;
            muteButton.Bounds = new Rectangle(18, 132, 664, 58);

            Label connectionSection = CreateSectionLabel("CONNECTIONS", 14);
            wifiButton = MakeButton("", delegate { ToggleRadio(RadioKind.WiFi); });
            bluetoothButton = MakeButton("", delegate { ToggleRadio(RadioKind.Bluetooth); });
            wifiButton.IconKind = ButtonIcon.WiFi;
            bluetoothButton.IconKind = ButtonIcon.Bluetooth;
            wifiButton.Bounds = new Rectangle(18, 52, 322, 62);
            bluetoothButton.Bounds = new Rectangle(360, 52, 322, 62);

            Label powerSection = CreateSectionLabel("POWER", 14);
            RoundedButton sleepButton = MakeButton("Sleep", SleepComputer);
            RoundedButton restartButton = MakeButton("Restart", RestartComputer);
            RoundedButton shutdownButton = MakeButton("Shut Down", ShutdownComputer);
            sleepButton.IconKind = ButtonIcon.Sleep;
            restartButton.IconKind = ButtonIcon.Restart;
            shutdownButton.IconKind = ButtonIcon.Power;
            sleepButton.Bounds = new Rectangle(18, 52, 208, 62);
            restartButton.Bounds = new Rectangle(246, 52, 208, 62);
            shutdownButton.Bounds = new Rectangle(474, 52, 208, 62);

            AddControls(gameGroup, gameSection, returnButton, exitButton);
            AddControls(audioGroup, audioSection, volumeDown, volumeMeter, volumeUp, muteButton);
            AddControls(connectionGroup, connectionSection, wifiButton, bluetoothButton);
            AddControls(powerGroup, powerSection, sleepButton, restartButton, shutdownButton);
            AddControls(controlCard, gameGroup, audioGroup, connectionGroup, powerGroup);

            navigationRows.Add(new Button[] { returnButton, exitButton });
            navigationRows.Add(new Button[] { volumeDown, volumeUp });
            navigationRows.Add(new Button[] { muteButton });
            navigationRows.Add(new Button[] { wifiButton, bluetoothButton });
            navigationRows.Add(new Button[] { sleepButton, restartButton, shutdownButton });

            confirmationPanel = new RoundedPanel {
                BackColor = ArcticPalette.Panel,
                Size = new Size(680, 260),
                Visible = false,
                CornerRadius = 26
            };
            confirmationLabel = CreateLabel("", 20, true);
            confirmationLabel.AutoSize = false;
            confirmationLabel.TextAlign = ContentAlignment.MiddleCenter;
            confirmationLabel.Bounds = new Rectangle(35, 25, 610, 105);
            confirmationYes = MakeButton("Yes", ConfirmYes);
            confirmationNo = MakeButton("No", CancelConfirmation);
            confirmationYes.Bounds = new Rectangle(35, 155, 285, 70);
            confirmationNo.Bounds = new Rectangle(360, 155, 285, 70);
            confirmationPanel.Controls.Add(confirmationLabel);
            confirmationPanel.Controls.Add(confirmationYes);
            confirmationPanel.Controls.Add(confirmationNo);
            Controls.Add(confirmationPanel);

            inputTimer = new Timer { Interval = 60 };
            inputTimer.Tick += PollController;
            inputTimer.Start();
            processTimer = new Timer { Interval = 1000 };
            processTimer.Tick += CheckGame;
            processTimer.Start();
            metadataTimer = new Timer { Interval = 1000 };
            metadataTimer.Tick += UpdateMetadata;
            metadataTimer.Start();
            UpdateMetadata(null, EventArgs.Empty);
            UpdateRadioLabels();

            Shown += delegate {
                if (previewMode) ShowOverlay();
                else HideOverlay();
            };
            KeyDown += OnKeyDown;
            FormClosed += delegate { ResumeGame(); };
            layoutRoot();
            layoutContent();
            layoutArtwork();
            content.PerformLayout();
            logoBox.BringToFront();
            statsCard.BringToFront();
            header.BringToFront();
            prompts.BringToFront();
        }

        protected override void OnHandleCreated(EventArgs args)
        {
            base.OnHandleCreated(args);
            // Reliable fallback for controller mappers such as DS4Windows.
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
            if (message.Msg == HotKeyMessage && message.WParam.ToInt32() == OverlayHotKey)
            {
                if (overlayVisible) HideOverlay(); else ShowOverlay();
                return;
            }
            base.WndProc(ref message);
        }

        protected override void OnPaintBackground(PaintEventArgs eventArgs)
        {
            base.OnPaintBackground(eventArgs);
            if (backgroundArtwork != null)
                DrawingUtil.DrawCover(eventArgs.Graphics, backgroundArtwork, ClientRectangle);
            using (SolidBrush dim = new SolidBrush(Color.FromArgb(205, 0, 0, 8)))
                eventArgs.Graphics.FillRectangle(dim, ClientRectangle);
        }

        private Label CreateLabel(string text, float size, bool bold)
        {
            return new Label {
                Text = text,
                ForeColor = ArcticPalette.Foreground,
                BackColor = Color.Transparent,
                Font = UiFonts.Create(size, bold),
                AutoEllipsis = true
            };
        }

        private Label CreateSectionLabel(string text, int y)
        {
            Label label = CreateLabel(text, 11, true);
            label.ForeColor = ArcticPalette.ForegroundMuted;
            label.Bounds = new Rectangle(18, y, 300, 28);
            return label;
        }

        private RoundedPanel MakeGroupPanel(Rectangle bounds)
        {
            return new RoundedPanel {
                Bounds = bounds,
                CornerRadius = 24,
                BackColor = ArcticPalette.Group
            };
        }

        private static void AddControls(Control parent, params Control[] controls)
        {
            parent.Controls.AddRange(controls);
        }

        private RoundedButton MakeButton(string text, EventHandler action)
        {
            RoundedButton button = new RoundedButton {
                Text = text,
                Font = UiFonts.Create(13, true),
                CornerRadius = 18
            };
            button.FlatAppearance.BorderSize = 0;
            button.Click += action;
            return button;
        }

        private void PollController(object sender, EventArgs args)
        {
            ushort buttons = 0;
            bool found = false;
            if (getState != null)
            {
                for (uint index = 0; index < 4; index++)
                {
                    Native.XInputState state;
                    if (getState(index, out state) == 0)
                    {
                        buttons = state.Gamepad.Buttons;
                        if (state.Gamepad.LeftTrigger > 100) buttons |= Native.VolumeDownCommand;
                        if (state.Gamepad.RightTrigger > 100) buttons |= Native.VolumeUpCommand;
                        found = true;
                        break;
                    }
                }
            }
            if (!found)
                buttons = PollDirectInputStyleController();

            ushort pressed = (ushort)(buttons & ~previousButtons);
            previousButtons = buttons;

            if ((pressed & Native.Guide) != 0)
            {
                if (overlayVisible) HideOverlay(); else ShowOverlay();
                return;
            }
            if (!overlayVisible) return;
            if ((pressed & Native.B) != 0)
            {
                if (confirmationPanel.Visible) CancelConfirmation(null, EventArgs.Empty);
                else HideOverlay();
                return;
            }
            if ((pressed & Native.DPadUp) != 0) MoveFocus(0, -1);
            if ((pressed & Native.DPadDown) != 0) MoveFocus(0, 1);
            if ((pressed & Native.DPadLeft) != 0) MoveFocus(-1, 0);
            if ((pressed & Native.DPadRight) != 0) MoveFocus(1, 0);
            if ((pressed & Native.VolumeDownCommand) != 0) AdjustVolume(-5);
            if ((pressed & Native.VolumeUpCommand) != 0) AdjustVolume(5);
            if ((pressed & Native.A) != 0 && ActiveControl is Button)
                ((Button)ActiveControl).PerformClick();
        }

        private ushort PollDirectInputStyleController()
        {
            // Virtual DS4 mode is not exposed through XInput. Windows still
            // publishes it through the standard joystick API used by
            // DirectInput-style controllers, which works in the background.
            for (uint index = 0; index < 16; index++)
            {
                Native.JoyInfoEx state = new Native.JoyInfoEx {
                    Size = (uint)Marshal.SizeOf(typeof(Native.JoyInfoEx)),
                    Flags = Native.JoyReturnAll
                };
                if (Native.joyGetPosEx(index, ref state) != 0)
                    continue;

                ushort mapped = 0;
                // Standard DS4 DirectInput order: Cross 2, Circle 3, PS 13.
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

        private void MoveFocus(int horizontal, int vertical)
        {
            if (confirmationPanel.Visible)
            {
                if (ActiveControl == confirmationYes) confirmationNo.Focus();
                else confirmationYes.Focus();
                return;
            }
            int row = 0;
            int column = 0;
            for (int r = 0; r < navigationRows.Count; r++)
            {
                int found = Array.IndexOf(navigationRows[r], ActiveControl);
                if (found >= 0) { row = r; column = found; break; }
            }
            if (vertical != 0)
            {
                row = (row + vertical + navigationRows.Count) % navigationRows.Count;
                column = Math.Min(column, navigationRows[row].Length - 1);
            }
            else if (horizontal != 0)
            {
                column = (column + horizontal + navigationRows[row].Length)
                    % navigationRows[row].Length;
            }
            navigationRows[row][column].Focus();
        }

        private void ShowOverlay()
        {
            overlayVisible = true;
            if (suspendOnOverlay && !gameSuspended)
                gameSuspended = Native.SetProcessSuspended(game.Id, true);
            Opacity = 1;
            Bounds = Screen.PrimaryScreen.Bounds;
            PerformLayout();
            foreach (Control child in Controls) child.PerformLayout();
            Invalidate(true);
            TopMost = true;
            Activate();
            BringToFront();
            navigationRows[0][0].Focus();
        }

        private void HideOverlay()
        {
            overlayVisible = false;
            TopMost = false;
            Opacity = 0;
            WindowState = FormWindowState.Normal;
            Bounds = new Rectangle(-32000, -32000, 1, 1);
            ResumeGame();
            try
            {
                if (!game.HasExited)
                {
                    NativeMethods.SetForegroundWindow(game.MainWindowHandle);
                }
            }
            catch { }
        }

        private void ResumeGame()
        {
            if (!gameSuspended) return;
            Native.SetProcessSuspended(game.Id, false);
            gameSuspended = false;
        }

        private void OnKeyDown(object sender, KeyEventArgs args)
        {
            if (args.KeyCode == Keys.Escape) HideOverlay();
        }

        protected override bool ProcessCmdKey(ref Message message, Keys keyData)
        {
            // Buttons and layout panels normally consume navigation keys before
            // the form receives KeyDown. Handle them here so keyboard, remote
            // mappers and accessibility input all share the same navigation.
            Keys key = keyData & Keys.KeyCode;
            if (overlayVisible && (key == Keys.Up || key == Keys.W))
            {
                MoveFocus(0, -1);
                return true;
            }
            if (overlayVisible && (key == Keys.Down || key == Keys.S))
            {
                MoveFocus(0, 1);
                return true;
            }
            if (overlayVisible && key == Keys.Left)
            {
                MoveFocus(-1, 0);
                return true;
            }
            if (overlayVisible && key == Keys.Right)
            {
                MoveFocus(1, 0);
                return true;
            }
            if (overlayVisible && (key == Keys.Enter || key == Keys.Space))
            {
                if (ActiveControl is Button)
                    ((Button)ActiveControl).PerformClick();
                return true;
            }
            if (overlayVisible && (key == Keys.Escape || key == Keys.Back))
            {
                if (confirmationPanel.Visible) CancelConfirmation(null, EventArgs.Empty);
                else HideOverlay();
                return true;
            }
            return base.ProcessCmdKey(ref message, keyData);
        }

        private void CheckGame(object sender, EventArgs args)
        {
            try
            {
                if (game.HasExited) Application.Exit();
            }
            catch { Application.Exit(); }
        }

        private static string FormatDuration(long seconds)
        {
            seconds = Math.Max(0, seconds);
            long hours = seconds / 3600;
            if (hours >= 100) return hours + " hrs";
            return String.Format("{0:00}:{1:00}:{2:00}",
                hours, (seconds / 60) % 60, seconds % 60);
        }

        private void UpdateMetadata(object sender, EventArgs args)
        {
            long now = (long)(DateTime.UtcNow -
                new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds;
            sessionValue.Text = FormatDuration(Math.Max(0, now - sessionStartEpoch));
            clockLabel.Text = DateTime.Now.ToString("h:mm tt");
            volumeMeter.Value = SystemAudio.GetVolume();
        }

        private void AdjustVolume(int delta)
        {
            volumeMeter.Value = SystemAudio.Adjust(delta);
        }

        private void ToggleMute()
        {
            bool muted = SystemAudio.ToggleMute();
            muteButton.Text = muted ? "Unmute" : "Mute / Unmute";
        }

        private void UpdateRadioLabels()
        {
            bool wifi = SystemRadios.IsOn(RadioKind.WiFi);
            bool bluetooth = SystemRadios.IsOn(RadioKind.Bluetooth);
            wifiButton.Text = "Wi-Fi        ● " + (wifi ? "ON" : "OFF");
            bluetoothButton.Text = "Bluetooth    ● " + (bluetooth ? "ON" : "OFF");
        }

        private void ToggleRadio(RadioKind kind)
        {
            SystemRadios.Toggle(kind);
            UpdateRadioLabels();
        }

        private void ShowConfirmation(string message, Action action)
        {
            confirmedAction = action;
            confirmationLabel.Text = message;
            confirmationPanel.Location = new Point(
                Math.Max(0, (ClientSize.Width - confirmationPanel.Width) / 2),
                Math.Max(0, (ClientSize.Height - confirmationPanel.Height) / 2)
            );
            confirmationPanel.Visible = true;
            confirmationPanel.BringToFront();
            confirmationNo.Focus();
        }

        private void ExitGame(object sender, EventArgs args)
        {
            ShowConfirmation("Exit " + gameTitle + "?", ExitGameConfirmed);
        }

        private void ConfirmYes(object sender, EventArgs args)
        {
            Action action = confirmedAction;
            HideConfirmation();
            if (action != null) action();
        }

        private void CancelConfirmation(object sender, EventArgs args)
        {
            HideConfirmation();
            navigationRows[0][0].Focus();
        }

        private void HideConfirmation()
        {
            confirmationPanel.Visible = false;
            confirmedAction = null;
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

        private void SleepComputer(object sender, EventArgs args)
        {
            ShowConfirmation("Put this PC to sleep?", SleepComputerConfirmed);
        }

        private void SleepComputerConfirmed()
        {
            Application.SetSuspendState(PowerState.Suspend, true, false);
        }

        private void RestartComputer(object sender, EventArgs args)
        {
            ShowConfirmation("Restart this PC?", RestartComputerConfirmed);
        }

        private void RestartComputerConfirmed()
        {
            Process.Start(new ProcessStartInfo("shutdown.exe", "/r /t 0") {
                UseShellExecute = false,
                CreateNoWindow = true
            });
        }

        private void ShutdownComputer(object sender, EventArgs args)
        {
            ShowConfirmation("Shut down this PC?", ShutdownComputerConfirmed);
        }

        private void ShutdownComputerConfirmed()
        {
            Process.Start(new ProcessStartInfo("shutdown.exe", "/s /t 0") {
                UseShellExecute = false,
                CreateNoWindow = true
            });
        }
    }

    internal static class NativeMethods
    {
        [DllImport("user32.dll")]
        internal static extern bool SetForegroundWindow(IntPtr window);
    }

    internal static class Program
    {
        [STAThread]
        private static void Main(string[] args)
        {
            try { Native.SetProcessDPIAware(); } catch { }
            int pid = 0;
            string title = "Game";
            bool suspendGame = false;
            bool previewMode = false;
            bool webUi = false;
            string logo = "";
            string fanart = "";
            string genres = "";
            string studio = "";
            string fontRegular = "";
            string fontBold = "";
            string pipeName = "";
            string pipeToken = "";
            long totalSeconds = 0;
            long sessionStart = 0;
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--pid" && i + 1 < args.Length) Int32.TryParse(args[++i], out pid);
                else if (args[i] == "--title" && i + 1 < args.Length) title = args[++i];
                else if (args[i] == "--suspend-game") suspendGame = true;
                else if (args[i] == "--preview") previewMode = true;
                else if (args[i] == "--web-ui") webUi = true;
                else if (args[i] == "--logo" && i + 1 < args.Length) logo = args[++i];
                else if (args[i] == "--fanart" && i + 1 < args.Length) fanart = args[++i];
                else if (args[i] == "--genres" && i + 1 < args.Length) genres = args[++i];
                else if (args[i] == "--studio" && i + 1 < args.Length) studio = args[++i];
                else if (args[i] == "--total-seconds" && i + 1 < args.Length)
                    Int64.TryParse(args[++i], out totalSeconds);
                else if (args[i] == "--session-start" && i + 1 < args.Length)
                    Int64.TryParse(args[++i], out sessionStart);
                else if (args[i] == "--font-regular" && i + 1 < args.Length) fontRegular = args[++i];
                else if (args[i] == "--font-bold" && i + 1 < args.Length) fontBold = args[++i];
                else if (args[i] == "--pipe-name" && i + 1 < args.Length) pipeName = args[++i];
                else if (args[i] == "--pipe-token" && i + 1 < args.Length) pipeToken = args[++i];
            }
            if (pid <= 0) return;
            Process game;
            try { game = Process.GetProcessById(pid); }
            catch { return; }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            if (webUi)
            {
                Application.Run(new WebOverlayForm(
                    game, title, suspendGame, logo, genres, studio,
                    totalSeconds, sessionStart, previewMode, pipeName, pipeToken));
            }
            else
            {
                Application.Run(new OverlayForm(
                    game, title, suspendGame, logo, fanart, genres, studio,
                    totalSeconds, sessionStart, fontRegular, fontBold, previewMode));
            }
        }
    }
}
