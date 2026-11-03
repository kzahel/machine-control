namespace MachineControl.Windows;

/// Native projections and trusted operator decisions; browser authority is shared.
internal interface IBrowserPolicy
{
    bool Allows(string scope);
    void Configure(string[] scopes, int? durationSeconds, string[] profileIds);
    string? Checkpoint();
    void Restore(string checkpointId);
    void Stop();
    void Refresh() { }
    object Profiles { get; }
}
