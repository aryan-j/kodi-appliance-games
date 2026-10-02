using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Pipes;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

namespace GameApplianceOverlay.Playnite;

internal sealed class PlayniteOverlayPipeServer : IDisposable
{
    private readonly string pipeName;
    private readonly string token;
    private readonly Func<Dictionary<string, object>> snapshotProvider;
    private readonly Action<Dictionary<string, object>> actionReceived;
    private readonly Action<Exception> errorReceived;
    private readonly JavaScriptSerializer serializer = new();
    private readonly object sync = new();
    private NamedPipeServerStream? server;
    private StreamWriter? writer;
    private Thread? worker;
    private bool stopping;

    public PlayniteOverlayPipeServer(
        string pipeName,
        string token,
        Func<Dictionary<string, object>> snapshotProvider,
        Action<Dictionary<string, object>> actionReceived,
        Action<Exception> errorReceived)
    {
        this.pipeName = pipeName;
        this.token = token;
        this.snapshotProvider = snapshotProvider;
        this.actionReceived = actionReceived;
        this.errorReceived = errorReceived;
    }

    public void Start()
    {
        worker = new Thread(Run)
        {
            IsBackground = true,
            Name = "Game Appliance Overlay pipe server"
        };
        worker.Start();
    }

    private void Run()
    {
        try
        {
            var pipe = CreatePipe();
            lock (sync)
            {
                if (stopping)
                {
                    pipe.Dispose();
                    return;
                }
                server = pipe;
            }

            pipe.WaitForConnection();
            using (var reader = new StreamReader(pipe, Encoding.UTF8, false, 1024, true))
            {
                lock (sync)
                {
                    writer = new StreamWriter(pipe, new UTF8Encoding(false), 1024, true)
                    {
                        AutoFlush = true
                    };
                }

                string? line = reader.ReadLine();
                if (!IsValidHello(line)) return;

                Send(new Dictionary<string, object>
                {
                    ["type"] = "hello",
                    ["protocol"] = 1,
                    ["ok"] = true,
                    ["snapshot"] = snapshotProvider()
                });

                while (!stopping && (line = reader.ReadLine()) != null)
                {
                    if (line.Length == 0 || line.Length > 256 * 1024) continue;
                    var message = serializer.DeserializeObject(line) as Dictionary<string, object>;
                    if (message == null) continue;
                    HandleMessage(message);
                }
            }
        }
        catch (Exception exception)
        {
            if (!stopping) errorReceived(exception);
        }
        finally
        {
            lock (sync)
            {
                writer?.Dispose();
                writer = null;
                server?.Dispose();
                server = null;
            }
        }
    }

    private void HandleMessage(Dictionary<string, object> message)
    {
        if (!message.TryGetValue("type", out var typeValue)) return;
        var type = typeValue as string;
        if (type == "ping")
        {
            Send(new Dictionary<string, object> { ["type"] = "pong" });
            return;
        }
        if (type == "action") actionReceived(message);
    }

    private bool IsValidHello(string? line)
    {
        if (String.IsNullOrWhiteSpace(line)) return false;
        var message = serializer.DeserializeObject(line) as Dictionary<string, object>;
        if (message == null || !message.TryGetValue("type", out var typeValue) ||
            !String.Equals(typeValue as string, "hello", StringComparison.Ordinal)) return false;
        return message.TryGetValue("token", out var tokenValue) &&
            String.Equals(tokenValue as string, token, StringComparison.Ordinal);
    }

    private NamedPipeServerStream CreatePipe()
    {
        var security = new PipeSecurity();
        security.SetAccessRuleProtection(true, false);
        var identity = WindowsIdentity.GetCurrent().User;
        if (identity == null) throw new InvalidOperationException("Current Windows identity is unavailable.");
        security.AddAccessRule(new PipeAccessRule(
            identity,
            PipeAccessRights.FullControl,
            AccessControlType.Allow));

        return new NamedPipeServerStream(
            pipeName,
            PipeDirection.InOut,
            1,
            PipeTransmissionMode.Byte,
            PipeOptions.None,
            0,
            0,
            security);
    }

    public bool SendSnapshot()
    {
        return Send(new Dictionary<string, object>
        {
            ["type"] = "snapshot",
            ["snapshot"] = snapshotProvider()
        });
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

    public void Dispose()
    {
        stopping = true;
        lock (sync)
        {
            server?.Dispose();
            server = null;
            writer?.Dispose();
            writer = null;
        }
        if (worker != null && worker.IsAlive && worker != Thread.CurrentThread)
            worker.Join(500);
        worker = null;
    }
}
