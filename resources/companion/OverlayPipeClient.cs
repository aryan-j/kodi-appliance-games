using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

namespace KodiAppliance
{
    /// <summary>
    /// Small newline-delimited JSON client used by non-Kodi connectors.
    /// The host connects to a connector-owned, per-session named pipe; it
    /// never opens a listening socket or accepts remote network traffic.
    /// </summary>
    internal sealed class OverlayPipeClient : IDisposable
    {
        private readonly string pipeName;
        private readonly string token;
        private readonly JavaScriptSerializer serializer = new JavaScriptSerializer();
        private readonly object sync = new object();
        private NamedPipeClientStream stream;
        private StreamWriter writer;
        private Thread readerThread;
        private bool stopping;

        internal event Action<Dictionary<string, object>> MessageReceived;
        internal event Action<Exception> Faulted;

        internal OverlayPipeClient(string name, string handshakeToken)
        {
            pipeName = name ?? "";
            token = handshakeToken ?? "";
        }

        internal bool IsConfigured
        {
            get { return !String.IsNullOrWhiteSpace(pipeName) && !String.IsNullOrWhiteSpace(token); }
        }

        internal void Start()
        {
            if (!IsConfigured || readerThread != null) return;
            readerThread = new Thread(ConnectAndRead) {
                IsBackground = true,
                Name = "Overlay pipe client"
            };
            readerThread.Start();
        }

        internal bool SendAction(string action, string ssid = null, string deviceId = null)
        {
            Dictionary<string, object> message = new Dictionary<string, object> {
                { "type", "action" },
                { "action", action ?? "" }
            };
            if (!String.IsNullOrWhiteSpace(ssid)) message["ssid"] = ssid;
            if (!String.IsNullOrWhiteSpace(deviceId)) message["deviceId"] = deviceId;
            return Send(message);
        }

        private void ConnectAndRead()
        {
            try
            {
                NamedPipeClientStream client = new NamedPipeClientStream(
                    ".", pipeName, PipeDirection.InOut, PipeOptions.None);
                client.Connect(8000);
                lock (sync)
                {
                    if (stopping)
                    {
                        client.Dispose();
                        return;
                    }
                    stream = client;
                    writer = new StreamWriter(client, new UTF8Encoding(false), 1024, true) {
                        AutoFlush = true
                    };
                }

                Send(new Dictionary<string, object> {
                    { "type", "hello" },
                    { "protocol", 1 },
                    { "token", token },
                    { "pid", ProcessId() }
                });

                using (StreamReader reader = new StreamReader(client, Encoding.UTF8, false, 1024, true))
                {
                    string line;
                    while (!stopping && (line = reader.ReadLine()) != null)
                    {
                        if (line.Length == 0 || line.Length > 256 * 1024) continue;
                        Dictionary<string, object> message =
                            serializer.DeserializeObject(line) as Dictionary<string, object>;
                        if (message != null && MessageReceived != null)
                            MessageReceived(message);
                    }
                }
            }
            catch (Exception exception)
            {
                if (!stopping && Faulted != null) Faulted(exception);
            }
            finally
            {
                lock (sync)
                {
                    if (writer != null) writer.Dispose();
                    writer = null;
                    if (stream != null) stream.Dispose();
                    stream = null;
                }
            }
        }

        private bool Send(Dictionary<string, object> message)
        {
            lock (sync)
            {
                if (stopping || writer == null) return false;
                try
                {
                    writer.WriteLine(serializer.Serialize(message));
                    writer.Flush();
                    return true;
                }
                catch
                {
                    return false;
                }
            }
        }

        private static int ProcessId()
        {
            try { return System.Diagnostics.Process.GetCurrentProcess().Id; }
            catch { return 0; }
        }

        public void Dispose()
        {
            stopping = true;
            lock (sync)
            {
                if (stream != null) stream.Dispose();
                stream = null;
                if (writer != null) writer.Dispose();
                writer = null;
            }
            if (readerThread != null && readerThread.IsAlive &&
                readerThread != Thread.CurrentThread)
            {
                readerThread.Join(500);
            }
            readerThread = null;
        }
    }
}
