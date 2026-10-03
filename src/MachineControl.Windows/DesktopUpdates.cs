using System.Text.Json.Nodes;

namespace MachineControl.Windows;

/// Metadata-only mailbox. The inherited operator supplies results; public
/// callers may queue discovery but cannot install, approve or set an endpoint.
internal sealed class DesktopUpdates
{
    private readonly object _gate = new();
    private JsonObject? _state;
    private bool _requested;

    internal bool Sync(JsonObject state)
    {
        lock (_gate)
        {
            _state = (JsonObject)state.DeepClone();
            var requested = _requested;
            _requested = false;
            if (requested && _state["installing"]?.GetValue<bool>() != true)
            {
                _state["checking"] = true;
                _state["phase"] = "checking";
                _state["reason"] = "manual";
            }
            return requested;
        }
    }

    internal object Request(bool check)
    {
        lock (_gate)
        {
            if (_state is null) throw new InvalidOperationException("Desktop updater is initializing");
            if (check && _state["checking"]?.GetValue<bool>() != true &&
                _state["installing"]?.GetValue<bool>() != true) _requested = true;
            return new { queued = _requested, update = _state.DeepClone() };
        }
    }
}
