using System.Diagnostics;
using System.Text.Json.Nodes;
using MachineControl.Windows;

/// Browser capability stub plus the real shared admission process. Native
/// tests supply time, never a second implementation of admission semantics.
internal sealed class TestBrowserProjection : IBrowserPolicy
{
    private string[] _scopes = [];
    private static readonly List<SharedBrowserHost> Hosts = [];
    static TestBrowserProjection() => AppDomain.CurrentDomain.ProcessExit += (_, _) => { foreach (var host in Hosts) host.Dispose(); };
    internal static DesktopGrants Create(TimeProvider? time = null, DesktopJournal? journal = null)
    {
        var projection = new TestBrowserProjection();
        var grants = new DesktopGrants(time, journal) { BrowserPolicy = projection };
        var start = new ProcessStartInfo(Environment.GetEnvironmentVariable("MACHINE_CONTROL_NODE") ?? "node");
        start.ArgumentList.Add(Path.GetFullPath("runtime/testing/admission-host.ts"));
        var host = new SharedBrowserHost(start, _ => { }, _ => false, () => { });
        Hosts.Add(host);
        time ??= TimeProvider.System;
        var origin = time.GetTimestamp();
        grants.Admission.Bind(frame =>
        {
            // TestTime and production TimeProvider have different frequencies.
            var milliseconds = (long)(time.GetElapsedTime(origin).TotalMilliseconds);
            host.Call(new JsonObject { ["method"] = "fixture.time", ["milliseconds"] = milliseconds });
            return host.Call(frame);
        });
        grants.Admission.Notice(0);
        return grants;
    }
    public bool Allows(string scope) => _scopes.Contains(scope) || scope == "browser" && _scopes.Contains("devtools");
    public void Configure(string[] scopes, int? durationSeconds, string[] profileIds) => _scopes = scopes.ToArray();
    public void Stop() => _scopes = [];
    public object Profiles => Array.Empty<object>();
}
