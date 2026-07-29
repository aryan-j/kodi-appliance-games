using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;

namespace KodiAppliance
{
    [ComImport]
    [Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
    internal class MMDeviceEnumeratorComObject { }

    internal enum EDataFlow { Render, Capture, All }
    internal enum ERole { Console, Multimedia, Communications }

    [ComImport]
    [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IMMDeviceEnumerator
    {
        int EnumAudioEndpoints(EDataFlow dataFlow, uint stateMask, out object devices);
        int GetDefaultAudioEndpoint(EDataFlow dataFlow, ERole role, out IMMDevice device);
    }

    [ComImport]
    [Guid("D666063F-1587-4E43-81F1-B948E807363F")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IMMDevice
    {
        int Activate(ref Guid interfaceId, uint context, IntPtr activationParams,
            [MarshalAs(UnmanagedType.IUnknown)] out object instance);
    }

    [ComImport]
    [Guid("5CDF2C82-841E-4546-9722-0CF74078229A")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IAudioEndpointVolume
    {
        int RegisterControlChangeNotify(IntPtr notify);
        int UnregisterControlChangeNotify(IntPtr notify);
        int GetChannelCount(out uint count);
        int SetMasterVolumeLevel(float levelDb, Guid context);
        int SetMasterVolumeLevelScalar(float level, Guid context);
        int GetMasterVolumeLevel(out float levelDb);
        int GetMasterVolumeLevelScalar(out float level);
        int SetChannelVolumeLevel(uint channel, float levelDb, Guid context);
        int SetChannelVolumeLevelScalar(uint channel, float level, Guid context);
        int GetChannelVolumeLevel(uint channel, out float levelDb);
        int GetChannelVolumeLevelScalar(uint channel, out float level);
        int SetMute([MarshalAs(UnmanagedType.Bool)] bool mute, Guid context);
        int GetMute(out bool mute);
    }

    internal static class SystemAudio
    {
        private static IAudioEndpointVolume Endpoint()
        {
            IMMDeviceEnumerator enumerator = (IMMDeviceEnumerator)new MMDeviceEnumeratorComObject();
            IMMDevice device;
            Marshal.ThrowExceptionForHR(
                enumerator.GetDefaultAudioEndpoint(EDataFlow.Render, ERole.Multimedia, out device));
            Guid interfaceId = typeof(IAudioEndpointVolume).GUID;
            object instance;
            Marshal.ThrowExceptionForHR(device.Activate(
                ref interfaceId, 23, IntPtr.Zero, out instance));
            return (IAudioEndpointVolume)instance;
        }

        internal static int GetVolume()
        {
            try
            {
                float level;
                Marshal.ThrowExceptionForHR(Endpoint().GetMasterVolumeLevelScalar(out level));
                return Math.Max(0, Math.Min(100, (int)Math.Round(level * 100)));
            }
            catch { return 0; }
        }

        internal static int Adjust(int delta)
        {
            int value = Math.Max(0, Math.Min(100, GetVolume() + delta));
            try
            {
                Marshal.ThrowExceptionForHR(Endpoint().SetMasterVolumeLevelScalar(
                    value / 100f, Guid.Empty));
            }
            catch { }
            return GetVolume();
        }

        internal static bool ToggleMute()
        {
            try
            {
                IAudioEndpointVolume endpoint = Endpoint();
                bool muted;
                Marshal.ThrowExceptionForHR(endpoint.GetMute(out muted));
                Marshal.ThrowExceptionForHR(endpoint.SetMute(!muted, Guid.Empty));
                return !muted;
            }
            catch { return false; }
        }

        internal static bool IsMuted()
        {
            IAudioEndpointVolume endpoint = null;
            try
            {
                endpoint = Endpoint();
                bool muted;
                Marshal.ThrowExceptionForHR(endpoint.GetMute(out muted));
                return muted;
            }
            catch { return false; }
            finally
            {
                if (endpoint != null) Marshal.ReleaseComObject(endpoint);
            }
        }
    }

    internal enum RadioKind
    {
        WiFi,
        Bluetooth
    }

    internal static class SystemRadios
    {
        private static string Run(RadioKind kind, string action)
        {
            try
            {
                string script = Path.Combine(
                    AppDomain.CurrentDomain.BaseDirectory, "radio.ps1");
                if (!File.Exists(script)) return "Unavailable";
                ProcessStartInfo info = new ProcessStartInfo(
                    "powershell.exe",
                    "-NoProfile -ExecutionPolicy Bypass -File \"" + script +
                    "\" -Kind " + kind + " -Action " + action) {
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                };
                using (Process process = Process.Start(info))
                {
                    string output = process.StandardOutput.ReadToEnd().Trim();
                    process.WaitForExit(5000);
                    return output;
                }
            }
            catch { return "Unavailable"; }
        }

        internal static bool IsOn(RadioKind kind)
        {
            return Run(kind, "Status").EndsWith("On",
                StringComparison.OrdinalIgnoreCase);
        }

        internal static bool Toggle(RadioKind kind)
        {
            return Run(kind, "Toggle").EndsWith("On",
                StringComparison.OrdinalIgnoreCase);
        }
    }
}
