using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.IO;
using System.Windows.Forms;

namespace KodiAppliance
{
    internal static class ArcticPalette
    {
        internal static readonly Color Foreground = Color.FromArgb(237, 237, 237);
        internal static readonly Color ForegroundMuted = Color.FromArgb(179, 237, 237, 237);
        internal static readonly Color Panel = Color.FromArgb(232, 18, 18, 22);
        internal static readonly Color Group = Color.FromArgb(245, 29, 29, 34);
        internal static readonly Color Control = Color.FromArgb(255, 48, 48, 54);
        internal static readonly Color ControlHover = Color.FromArgb(255, 66, 66, 73);
        internal static readonly Color Track = Color.FromArgb(255, 24, 24, 29);
        internal static readonly Color Focus = Color.FromArgb(255, 237, 237, 237);
        internal static readonly Color FocusText = Color.FromArgb(255, 18, 18, 18);
        internal static readonly Color Accent = Color.FromArgb(255, 132, 204, 225);
        internal static readonly Color Danger = Color.FromArgb(255, 214, 91, 91);
    }

    internal static class UiFonts
    {
        private static readonly PrivateFontCollection Collection = new PrivateFontCollection();
        private static FontFamily family;

        internal static void Initialize(string regular, string bold)
        {
            try
            {
                if (!String.IsNullOrEmpty(regular) && File.Exists(regular))
                    Collection.AddFontFile(regular);
                if (!String.IsNullOrEmpty(bold) && File.Exists(bold))
                    Collection.AddFontFile(bold);
                if (Collection.Families.Length > 0)
                    family = Collection.Families[0];
            }
            catch { family = null; }
        }

        internal static Font Create(float size, bool bold)
        {
            FontFamily selected = family ?? new FontFamily("Segoe UI");
            FontStyle style = bold && selected.IsStyleAvailable(FontStyle.Bold)
                ? FontStyle.Bold
                : FontStyle.Regular;
            return new Font(selected, size, style, GraphicsUnit.Point);
        }
    }

    internal static class DrawingUtil
    {
        internal static GraphicsPath RoundedRectangle(Rectangle bounds, int radius)
        {
            int diameter = Math.Max(2, radius * 2);
            GraphicsPath path = new GraphicsPath();
            path.AddArc(bounds.Left, bounds.Top, diameter, diameter, 180, 90);
            path.AddArc(bounds.Right - diameter, bounds.Top, diameter, diameter, 270, 90);
            path.AddArc(bounds.Right - diameter, bounds.Bottom - diameter, diameter, diameter, 0, 90);
            path.AddArc(bounds.Left, bounds.Bottom - diameter, diameter, diameter, 90, 90);
            path.CloseFigure();
            return path;
        }

        internal static Image LoadImage(string path)
        {
            if (String.IsNullOrEmpty(path) || !File.Exists(path)) return null;
            try
            {
                byte[] bytes = File.ReadAllBytes(path);
                using (MemoryStream stream = new MemoryStream(bytes))
                using (Image source = Image.FromStream(stream))
                    return new Bitmap(source);
            }
            catch { return null; }
        }

        internal static void DrawCover(Graphics graphics, Image image, Rectangle bounds)
        {
            if (image == null) return;
            float scale = Math.Max(
                bounds.Width / (float)image.Width,
                bounds.Height / (float)image.Height);
            int width = (int)Math.Ceiling(image.Width * scale);
            int height = (int)Math.Ceiling(image.Height * scale);
            Rectangle destination = new Rectangle(
                bounds.Left + (bounds.Width - width) / 2,
                bounds.Top + (bounds.Height - height) / 2,
                width,
                height);
            graphics.DrawImage(image, destination);
        }
    }

    internal class RoundedPanel : Panel
    {
        internal int CornerRadius { get; set; }

        internal RoundedPanel()
        {
            CornerRadius = 22;
            DoubleBuffered = true;
        }

        protected override void OnResize(EventArgs eventArgs)
        {
            base.OnResize(eventArgs);
            if (Width <= 0 || Height <= 0) return;
            using (GraphicsPath path = DrawingUtil.RoundedRectangle(
                new Rectangle(0, 0, Width, Height), CornerRadius))
                Region = new Region(path);
        }
    }

    internal class RoundedButton : Button
    {
        internal int CornerRadius { get; set; }
        internal Color NormalColor { get; set; }
        internal ButtonIcon IconKind { get; set; }

        internal RoundedButton()
        {
            CornerRadius = 18;
            NormalColor = ArcticPalette.Control;
            FlatStyle = FlatStyle.Flat;
            FlatAppearance.BorderSize = 0;
            BackColor = NormalColor;
            ForeColor = ArcticPalette.Foreground;
            TextAlign = ContentAlignment.MiddleCenter;
            TabStop = true;
            UseVisualStyleBackColor = false;
            GotFocus += delegate {
                BackColor = ArcticPalette.Focus;
                ForeColor = ArcticPalette.FocusText;
            };
            LostFocus += delegate {
                BackColor = NormalColor;
                ForeColor = ArcticPalette.Foreground;
            };
            MouseEnter += delegate { Focus(); };
        }

        protected override void OnPaint(PaintEventArgs eventArgs)
        {
            eventArgs.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            Color fill = Focused ? ArcticPalette.Focus : NormalColor;
            Color ink = Focused ? ArcticPalette.FocusText : ArcticPalette.Foreground;
            using (GraphicsPath path = DrawingUtil.RoundedRectangle(
                new Rectangle(0, 0, Width - 1, Height - 1), Math.Max(CornerRadius, Height / 2)))
            using (SolidBrush brush = new SolidBrush(fill))
                eventArgs.Graphics.FillPath(brush, path);

            int iconSpace = IconKind == ButtonIcon.None ? 0 : 42;
            if (IconKind != ButtonIcon.None)
                IconPainter.Draw(eventArgs.Graphics, IconKind,
                    new Rectangle(18, (Height - 24) / 2, 24, 24), ink);
            TextRenderer.DrawText(eventArgs.Graphics, Text, Font,
                new Rectangle(18 + iconSpace, 0, Width - 36 - iconSpace, Height),
                ink, TextFormatFlags.VerticalCenter | TextFormatFlags.Left |
                TextFormatFlags.EndEllipsis | TextFormatFlags.NoPadding);
        }

        protected override void OnResize(EventArgs eventArgs)
        {
            base.OnResize(eventArgs);
            if (Width <= 0 || Height <= 0) return;
            using (GraphicsPath path = DrawingUtil.RoundedRectangle(
                new Rectangle(0, 0, Width, Height), Math.Max(CornerRadius, Height / 2)))
                Region = new Region(path);
        }
    }

    internal sealed class RoundedPictureBox : PictureBox
    {
        internal int CornerRadius { get; set; }

        internal RoundedPictureBox()
        {
            CornerRadius = 24;
            SizeMode = PictureBoxSizeMode.Zoom;
            BackColor = ArcticPalette.Control;
        }

        protected override void OnResize(EventArgs eventArgs)
        {
            base.OnResize(eventArgs);
            if (Width <= 0 || Height <= 0) return;
            using (GraphicsPath path = DrawingUtil.RoundedRectangle(
                new Rectangle(0, 0, Width, Height), CornerRadius))
                Region = new Region(path);
        }
    }

    internal sealed class VolumeMeter : Control
    {
        private int value;
        internal int Value
        {
            get { return value; }
            set { this.value = Math.Max(0, Math.Min(100, value)); Invalidate(); }
        }

        internal VolumeMeter()
        {
            SetStyle(ControlStyles.SupportsTransparentBackColor |
                     ControlStyles.AllPaintingInWmPaint |
                     ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint, true);
            BackColor = Color.Transparent;
            Height = 54;
        }

        protected override void OnPaint(PaintEventArgs eventArgs)
        {
            base.OnPaint(eventArgs);
            Graphics graphics = eventArgs.Graphics;
            graphics.SmoothingMode = SmoothingMode.AntiAlias;
            Rectangle track = new Rectangle(0, 20, Math.Max(1, Width - 78), 12);
            using (GraphicsPath background = DrawingUtil.RoundedRectangle(track, 5))
            using (SolidBrush brush = new SolidBrush(ArcticPalette.Track))
                graphics.FillPath(brush, background);
            Rectangle fill = new Rectangle(track.X, track.Y,
                (int)(track.Width * (Value / 100f)), track.Height);
            if (fill.Width > 0)
            {
                using (GraphicsPath foreground = DrawingUtil.RoundedRectangle(fill, 5))
                using (SolidBrush brush = new SolidBrush(ArcticPalette.Accent))
                    graphics.FillPath(brush, foreground);
            }
            using (Font font = UiFonts.Create(12, true))
            using (SolidBrush brush = new SolidBrush(ArcticPalette.Foreground))
                graphics.DrawString(Value + "%", font, brush,
                    new RectangleF(Width - 78, 11, 76, 34),
                    new StringFormat { Alignment = StringAlignment.Far, LineAlignment = StringAlignment.Center });
        }
    }

    internal sealed class PromptLegend : Control
    {
        public PromptLegend()
        {
            SetStyle(ControlStyles.SupportsTransparentBackColor |
                     ControlStyles.AllPaintingInWmPaint |
                     ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint, true);
        }

        protected override void OnPaint(PaintEventArgs eventArgs)
        {
            base.OnPaint(eventArgs);
            Graphics graphics = eventArgs.Graphics;
            graphics.SmoothingMode = SmoothingMode.AntiAlias;
            int x = 0;
            x = DrawFacePrompt(graphics, x, FaceGlyph.Cross, "Select");
            x = DrawFacePrompt(graphics, x + 28, FaceGlyph.Circle, "Back");
            x = DrawTextPrompt(graphics, x + 28, "PS", "Return to game");
            x = DrawTextPrompt(graphics, x + 28, "L2", "Volume -");
            DrawTextPrompt(graphics, x + 28, "R2", "Volume +");
        }

        private int DrawFacePrompt(Graphics graphics, int x, FaceGlyph glyph, string label)
        {
            Rectangle circle = new Rectangle(x, 7, 34, 34);
            using (SolidBrush face = new SolidBrush(ArcticPalette.Foreground))
                graphics.FillEllipse(face, circle);
            using (Pen glyphPen = new Pen(ArcticPalette.FocusText, 2.4f))
            {
                if (glyph == FaceGlyph.Cross)
                {
                    graphics.DrawLine(glyphPen, x + 11, 18, x + 23, 30);
                    graphics.DrawLine(glyphPen, x + 23, 18, x + 11, 30);
                }
                else
                    graphics.DrawEllipse(glyphPen, x + 10, 17, 14, 14);
            }
            return DrawPromptLabel(graphics, x, label);
        }

        private int DrawTextPrompt(Graphics graphics, int x, string symbol, string label)
        {
            Rectangle pill = new Rectangle(x, 7, symbol == "PS" ? 38 : 40, 34);
            using (GraphicsPath path = DrawingUtil.RoundedRectangle(pill, 17))
            using (Pen pen = new Pen(ArcticPalette.Foreground, 2))
                graphics.DrawPath(pen, path);
            using (Font symbolFont = UiFonts.Create(8, true))
            using (SolidBrush brush = new SolidBrush(ArcticPalette.Foreground))
                graphics.DrawString(symbol, symbolFont, brush, pill,
                    new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center });
            return DrawPromptLabel(graphics, x + pill.Width - 34, label);
        }

        private int DrawPromptLabel(Graphics graphics, int x, string label)
        {
            using (Font labelFont = UiFonts.Create(11, false))
            using (SolidBrush brush = new SolidBrush(ArcticPalette.ForegroundMuted))
                graphics.DrawString(label, labelFont, brush, x + 44, 11);
            using (Font measureFont = UiFonts.Create(11, false))
                return x + 44 + TextRenderer.MeasureText(label, measureFont).Width;
        }
    }

    internal enum FaceGlyph { Cross, Circle, Square, Triangle }
    internal enum ButtonIcon
    {
        None, Return, Exit, VolumeDown, VolumeUp, Mute, WiFi, Bluetooth,
        Sleep, Restart, Power
    }

    internal static class IconPainter
    {
        internal static void Draw(Graphics graphics, ButtonIcon icon, Rectangle box, Color color)
        {
            using (Pen pen = new Pen(color, 2.2f))
            {
                pen.StartCap = LineCap.Round;
                pen.EndCap = LineCap.Round;
                int l = box.Left, t = box.Top, r = box.Right, b = box.Bottom;
                int cx = box.Left + box.Width / 2, cy = box.Top + box.Height / 2;
                if (icon == ButtonIcon.Return)
                {
                    graphics.DrawArc(pen, l + 4, t + 5, 16, 14, 210, 250);
                    graphics.DrawLine(pen, l + 3, cy, l + 9, cy - 6);
                    graphics.DrawLine(pen, l + 3, cy, l + 10, cy + 4);
                }
                else if (icon == ButtonIcon.Exit)
                {
                    graphics.DrawRectangle(pen, l + 3, t + 3, 13, 18);
                    graphics.DrawLine(pen, l + 10, cy, r - 1, cy);
                    graphics.DrawLine(pen, r - 6, cy - 5, r - 1, cy);
                    graphics.DrawLine(pen, r - 6, cy + 5, r - 1, cy);
                }
                else if (icon == ButtonIcon.VolumeDown || icon == ButtonIcon.VolumeUp || icon == ButtonIcon.Mute)
                {
                    graphics.DrawLine(pen, l + 2, cy - 4, l + 8, cy - 4);
                    graphics.DrawLine(pen, l + 8, cy - 4, l + 14, t + 4);
                    graphics.DrawLine(pen, l + 14, t + 4, l + 14, b - 4);
                    graphics.DrawLine(pen, l + 14, b - 4, l + 8, cy + 4);
                    graphics.DrawLine(pen, l + 8, cy + 4, l + 2, cy + 4);
                    if (icon == ButtonIcon.Mute)
                    {
                        graphics.DrawLine(pen, r - 7, cy - 5, r - 1, cy + 5);
                        graphics.DrawLine(pen, r - 1, cy - 5, r - 7, cy + 5);
                    }
                    else
                    {
                        graphics.DrawLine(pen, r - 7, cy, r - 1, cy);
                        if (icon == ButtonIcon.VolumeUp) graphics.DrawLine(pen, r - 4, cy - 3, r - 4, cy + 3);
                    }
                }
                else if (icon == ButtonIcon.WiFi)
                {
                    graphics.DrawArc(pen, l + 1, t + 3, 22, 18, 210, 120);
                    graphics.DrawArc(pen, l + 6, t + 8, 12, 10, 210, 120);
                    graphics.FillEllipse(new SolidBrush(color), cx - 2, b - 5, 4, 4);
                }
                else if (icon == ButtonIcon.Bluetooth)
                {
                    graphics.DrawLine(pen, cx, t + 1, cx, b - 1);
                    graphics.DrawLine(pen, cx, t + 1, r - 5, t + 7);
                    graphics.DrawLine(pen, r - 5, t + 7, l + 5, b - 5);
                    graphics.DrawLine(pen, l + 5, t + 5, r - 5, b - 7);
                    graphics.DrawLine(pen, r - 5, b - 7, cx, b - 1);
                }
                else if (icon == ButtonIcon.Sleep)
                {
                    graphics.DrawArc(pen, l + 3, t + 2, 18, 20, 70, 250);
                    graphics.DrawArc(pen, l + 9, t + 1, 12, 17, 105, 180);
                }
                else if (icon == ButtonIcon.Restart)
                {
                    graphics.DrawArc(pen, l + 2, t + 2, 20, 20, 35, 300);
                    graphics.DrawLine(pen, r - 1, t + 5, r - 8, t + 5);
                    graphics.DrawLine(pen, r - 1, t + 5, r - 2, t + 12);
                }
                else if (icon == ButtonIcon.Power)
                {
                    graphics.DrawArc(pen, l + 3, t + 3, 18, 18, -50, 280);
                    graphics.DrawLine(pen, cx, t + 1, cx, cy + 3);
                }
            }
        }
    }
}
