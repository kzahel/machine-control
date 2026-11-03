using MachineControl.Windows;

/// A projection stub for native-only broker unit tests. No clock, routing,
/// expiry or session engine: those are tested against the shared core.
internal sealed class TestBrowserProjection : IBrowserPolicy
{
    private string[] _scopes = [];
    internal static DesktopGrants Create(TimeProvider? time = null, DesktopJournal? journal = null) =>
        new(time, journal) { BrowserPolicy = new TestBrowserProjection() };
    public bool Allows(string scope) => _scopes.Contains(scope) || scope == "browser" && _scopes.Contains("devtools");
    public void Configure(string[] scopes, int? durationSeconds, string[] profileIds) => _scopes = scopes.ToArray();
    public void Stop() => _scopes = [];
    public object Profiles => Array.Empty<object>();
}
