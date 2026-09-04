using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Web.Script.Serialization;

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
        int EnumAudioEndpoints(EDataFlow dataFlow, uint stateMask,
            out IMMDeviceCollection devices);
        int GetDefaultAudioEndpoint(EDataFlow dataFlow, ERole role, out IMMDevice device);
    }

    [ComImport]
    [Guid("0BD7A1BE-7A1A-44DB-8397-CC5392387B5E")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IMMDeviceCollection
    {
        int GetCount(out uint count);
        int Item(uint index, out IMMDevice device);
    }

    [ComImport]
    [Guid("D666063F-1587-4E43-81F1-B948E807363F")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IMMDevice
    {
        int Activate(ref Guid interfaceId, uint context, IntPtr activationParams,
            [MarshalAs(UnmanagedType.IUnknown)] out object instance);
        int OpenPropertyStore(uint access, out IPropertyStore properties);
        int GetId([MarshalAs(UnmanagedType.LPWStr)] out string id);
        int GetState(out uint state);
    }

    [ComImport]
    [Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IPropertyStore
    {
        int GetCount(out uint count);
        int GetAt(uint index, out PROPERTYKEY key);
        int GetValue(ref PROPERTYKEY key, out PROPVARIANT value);
        int SetValue(ref PROPERTYKEY key, ref PROPVARIANT value);
        int Commit();
    }

    [ComImport]
    [Guid("870AF99C-171D-4F9E-AF0D-E63DF40C2BC9")]
    internal class PolicyConfigClientComObject { }

    [ComImport]
    [Guid("F8679F50-850A-41CF-9C72-430F290290C8")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IPolicyConfig
    {
        int GetMixFormat([MarshalAs(UnmanagedType.LPWStr)] string deviceId,
            IntPtr format);
        int GetDeviceFormat([MarshalAs(UnmanagedType.LPWStr)] string deviceId,
            [MarshalAs(UnmanagedType.Bool)] bool defaultFormat, IntPtr format);
        int ResetDeviceFormat([MarshalAs(UnmanagedType.LPWStr)] string deviceId);
        int SetDeviceFormat([MarshalAs(UnmanagedType.LPWStr)] string deviceId,
            IntPtr endpointFormat, IntPtr mixFormat);
        int GetProcessingPeriod([MarshalAs(UnmanagedType.LPWStr)] string deviceId,
            [MarshalAs(UnmanagedType.Bool)] bool defaultFormat,
            IntPtr defaultPeriod, IntPtr minimumPeriod);
        int SetProcessingPeriod([MarshalAs(UnmanagedType.LPWStr)] string deviceId,
            IntPtr period);
        int GetShareMode([MarshalAs(UnmanagedType.LPWStr)] string deviceId,
            IntPtr mode);
        int SetShareMode([MarshalAs(UnmanagedType.LPWStr)] string deviceId,
            IntPtr mode);
        int GetPropertyValue([MarshalAs(UnmanagedType.LPWStr)] string deviceId,
            [MarshalAs(UnmanagedType.Bool)] bool isFxStore, IntPtr key, IntPtr value);
        int SetPropertyValue([MarshalAs(UnmanagedType.LPWStr)] string deviceId,
            [MarshalAs(UnmanagedType.Bool)] bool isFxStore, IntPtr key, IntPtr value);
        int SetDefaultEndpoint([MarshalAs(UnmanagedType.LPWStr)] string deviceId,
            ERole role);
        int SetEndpointVisibility([MarshalAs(UnmanagedType.LPWStr)] string deviceId,
            [MarshalAs(UnmanagedType.Bool)] bool visible);
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct PROPERTYKEY
    {
        internal Guid fmtid;
        internal uint pid;

        internal PROPERTYKEY(string formatId, uint propertyId)
        {
            fmtid = Guid.Parse(formatId);
            pid = propertyId;
        }
    }

    [StructLayout(LayoutKind.Explicit, Pack = 1)]
    internal struct PROPVARIANT
    {
        [FieldOffset(0)] internal ushort variantType;
        [FieldOffset(2)] internal ushort reserved1;
        [FieldOffset(4)] internal ushort reserved2;
        [FieldOffset(6)] internal ushort reserved3;
        [FieldOffset(8)] internal IntPtr pointerValue;
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
        private const uint DeviceStateActive = 0x1;
        private const uint StgmRead = 0;
        private static readonly PROPERTYKEY FriendlyNameKey = new PROPERTYKEY(
            "A45C254E-DF1C-4EFD-8020-67D146A850E0", 14);

        [DllImport("ole32.dll")]
        private static extern int PropVariantClear(ref PROPVARIANT value);

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

        internal static object GetOutputDeviceSnapshot()
        {
            List<object> devices = new List<object>();
            string defaultId = null;
            IMMDeviceEnumerator enumerator = null;
            IMMDeviceCollection collection = null;
            IMMDevice defaultDevice = null;
            try
            {
                enumerator = (IMMDeviceEnumerator)new MMDeviceEnumeratorComObject();
                try
                {
                    Marshal.ThrowExceptionForHR(enumerator.GetDefaultAudioEndpoint(
                        EDataFlow.Render, ERole.Multimedia, out defaultDevice));
                    defaultDevice.GetId(out defaultId);
                }
                catch { defaultId = null; }

                Marshal.ThrowExceptionForHR(enumerator.EnumAudioEndpoints(
                    EDataFlow.Render, DeviceStateActive, out collection));
                uint count;
                Marshal.ThrowExceptionForHR(collection.GetCount(out count));
                for (uint index = 0; index < count; index++)
                {
                    IMMDevice device = null;
                    try
                    {
                        Marshal.ThrowExceptionForHR(collection.Item(index, out device));
                        string id;
                        device.GetId(out id);
                        if (String.IsNullOrWhiteSpace(id)) continue;
                        string name = ReadFriendlyName(device);
                        devices.Add(new Dictionary<string, object> {
                            { "id", id },
                            { "name", String.IsNullOrWhiteSpace(name) ? "Unnamed output" : name },
                            { "isDefault", String.Equals(id, defaultId, StringComparison.OrdinalIgnoreCase) }
                        });
                    }
                    catch { }
                    finally { ReleaseComObject(device); }
                }
            }
            catch { }
            finally
            {
                ReleaseComObject(defaultDevice);
                ReleaseComObject(collection);
                ReleaseComObject(enumerator);
            }

            return new Dictionary<string, object> {
                { "defaultId", defaultId ?? "" },
                { "devices", devices }
            };
        }

        internal static bool SetDefaultOutputDevice(string deviceId)
        {
            if (String.IsNullOrWhiteSpace(deviceId) || deviceId.Length > 1024)
                return false;
            foreach (char character in deviceId)
            {
                if (character < 0x20 || character == 0x7F ||
                    character == '\r' || character == '\n') return false;
            }

            IPolicyConfig policy = null;
            bool selected = false;
            try
            {
                policy = (IPolicyConfig)new PolicyConfigClientComObject();
                ERole[] roles = { ERole.Console, ERole.Multimedia, ERole.Communications };
                foreach (ERole role in roles)
                {
                    if (policy.SetDefaultEndpoint(deviceId, role) >= 0)
                        selected = true;
                }
            }
            catch { return false; }
            finally { ReleaseComObject(policy); }
            return selected;
        }

        private static string ReadFriendlyName(IMMDevice device)
        {
            IPropertyStore properties = null;
            PROPVARIANT value = new PROPVARIANT();
            try
            {
                Marshal.ThrowExceptionForHR(device.OpenPropertyStore(StgmRead, out properties));
                PROPERTYKEY key = FriendlyNameKey;
                Marshal.ThrowExceptionForHR(properties.GetValue(ref key, out value));
                if (value.variantType == 31 && value.pointerValue != IntPtr.Zero)
                    return Marshal.PtrToStringUni(value.pointerValue);
                if (value.variantType == 8 && value.pointerValue != IntPtr.Zero)
                    return Marshal.PtrToStringBSTR(value.pointerValue);
                if (value.variantType == 30 && value.pointerValue != IntPtr.Zero)
                    return Marshal.PtrToStringAnsi(value.pointerValue);
                return null;
            }
            catch { return null; }
            finally
            {
                try { PropVariantClear(ref value); } catch { }
                ReleaseComObject(properties);
            }
        }

        private static void ReleaseComObject(object value)
        {
            try
            {
                if (value != null && Marshal.IsComObject(value))
                    Marshal.ReleaseComObject(value);
            }
            catch { }
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

    // Connectivity details are intentionally read-only and separate from the
    // existing radio toggle path.  A short process-local cache keeps opening
    // the panel from repeatedly starting PowerShell while still allowing an
    // explicit Refresh action to request fresh data.
    internal static class SystemConnectivity
    {
        private static readonly object CacheLock = new object();
        private static readonly TimeSpan CacheLifetime = TimeSpan.FromSeconds(3);
        private static string cachedJson;
        private static DateTime cachedAtUtc;

        // Returns immediately and never starts a process.  The overlay uses
        // this for the first paint, then refreshes on a worker thread.
        internal static object GetCachedSnapshot()
        {
            lock (CacheLock)
            {
                return Deserialize(String.IsNullOrWhiteSpace(cachedJson)
                    ? "{}" : cachedJson);
            }
        }

        internal static object GetSnapshot(bool forceRefresh)
        {
            lock (CacheLock)
            {
                if (!forceRefresh && !String.IsNullOrWhiteSpace(cachedJson) &&
                    DateTime.UtcNow - cachedAtUtc < CacheLifetime)
                    return Deserialize(cachedJson);

                string json = RunSnapshot();
                cachedJson = String.IsNullOrWhiteSpace(json) ? "{}" : json;
                cachedAtUtc = DateTime.UtcNow;
                return Deserialize(cachedJson);
            }
        }

        internal static object ConnectWifi(string ssid)
        {
            if (!IsSafeSsid(ssid))
            {
                return new Dictionary<string, object> {
                    { "result", "Invalid" },
                    { "message", "Invalid network name" }
                };
            }
            object result = Deserialize(RunScript("Connect", ssid.Trim()));
            Invalidate();
            return result;
        }

        internal static void Invalidate()
        {
            lock (CacheLock)
            {
                cachedJson = null;
                cachedAtUtc = DateTime.MinValue;
            }
        }

        private static object Deserialize(string json)
        {
            try
            {
                return new JavaScriptSerializer().DeserializeObject(json);
            }
            catch
            {
                return new Dictionary<string, object>();
            }
        }

        private static string RunSnapshot()
        {
            return RunScript("Snapshot", null);
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

        private static string QuoteArgument(string value)
        {
            StringBuilder result = new StringBuilder();
            result.Append('\"');
            int backslashes = 0;
            foreach (char character in value ?? "")
            {
                if (character == '\\')
                {
                    backslashes++;
                    continue;
                }
                if (character == '\"')
                {
                    result.Append(new string('\\', backslashes * 2 + 1));
                    result.Append('\"');
                }
                else
                {
                    result.Append(new string('\\', backslashes));
                    result.Append(character);
                }
                backslashes = 0;
            }
            result.Append(new string('\\', backslashes * 2));
            result.Append('\"');
            return result.ToString();
        }

        private static string RunScript(string action, string ssid)
        {
            try
            {
                string script = Path.Combine(
                    AppDomain.CurrentDomain.BaseDirectory, "connectivity.ps1");
                if (!File.Exists(script)) return "{}";
                ProcessStartInfo info = new ProcessStartInfo(
                    "powershell.exe",
                    "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File " +
                    QuoteArgument(script) + " -Action " + action +
                    (String.IsNullOrWhiteSpace(ssid) ? "" :
                        " -Ssid " + QuoteArgument(ssid))) {
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                };
                using (Process process = Process.Start(info))
                {
                    if (process == null) return "{}";
                    // This work runs off the UI thread.  Keep a hard bound for
                    // a slow Windows PnP provider while allowing normal helper
                    // startup/queries to finish without returning false data.
                    if (!process.WaitForExit(6000))
                    {
                        try { process.Kill(); } catch { }
                        return "{}";
                    }
                    string output = process.StandardOutput.ReadToEnd().Trim();
                    return String.IsNullOrWhiteSpace(output) ? "{}" : output;
                }
            }
            catch { return "{}"; }
        }
    }
}
