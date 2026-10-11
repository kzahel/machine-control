namespace MachineControl.Windows;

/// One physical provider worker, with no waiting queue. Caller completion does
/// not release capacity until native work actually ends. Stalled UIA cannot
/// accumulate threads by repeatedly timing out or disconnecting callers.
internal sealed class DesktopWork
{
    private int _active;
    internal async Task<Result> RunAsync(Request request, string generation,
        Func<CancellationToken, Task<Result>> execute, CancellationToken caller,
        TimeSpan? deadline = null)
    {
        Result Refused(string code) => new()
        {
            RequestId = request.RequestId!,
            Operation = request.Operation,
            Generation = generation,
            ActualRoute = "windows.user_session/workstation",
            ErrorCode = code,
            Delivery = "refused",
            Effect = "refused",
            RetrySafety = "safe_not_dispatched",
        };
        if (caller.IsCancellationRequested) return Refused("operation_cancelled");
        if (Interlocked.CompareExchange(ref _active, 1, 0) != 0) return Refused("native_provider_busy");
        var stop = CancellationTokenSource.CreateLinkedTokenSource(caller);
        stop.CancelAfter(deadline ?? TimeSpan.FromSeconds(30));
        var token = stop.Token;
        var work = Task.Run(async () =>
        {
            try { token.ThrowIfCancellationRequested(); return await execute(token); }
            finally { Interlocked.Exchange(ref _active, 0); }
        }, CancellationToken.None);
        // Keep cancellation alive until the physical worker has finished.
        _ = work.ContinueWith(task => { _ = task.Exception; stop.Dispose(); },
            CancellationToken.None, TaskContinuationOptions.ExecuteSynchronously, TaskScheduler.Default);
        try { return await work.WaitAsync(token); }
        catch (OperationCanceledException)
        {
            return Refused(caller.IsCancellationRequested ? "operation_cancelled" : "native_provider_timeout") with
            {
                Delivery = "unknown",
                Effect = "unknown",
                RetrySafety = "unsafe_unknown_delivery",
                Uncertainty = "Worker cancellation signalled; dispatched effects and cleanup may still be pending",
            };
        }
    }
}
