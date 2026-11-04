using System.IO;

namespace MachineControl.Windows;

internal static class RetainedPipeProxy
{
    internal static Task RunAsync(Stream input, Stream output, Stream transport) => RunAsync(
        () => { input.CopyTo(transport); transport.Flush(); },
        () => { transport.CopyTo(output); output.Flush(); });

    internal static Task RunAsync(Action send, Action receive)
    {
        var ended = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        void Start(Action direction, string name)
        {
            new Thread(() =>
            {
                try
                {
                    direction();
                    ended.TrySetResult();
                }
                catch (Exception error) { ended.TrySetException(error); }
            })
            { IsBackground = true, Name = name }.Start();
        }
        // Standard input/output use synchronous anonymous pipes on Windows.
        // A retained read must never occupy the worker needed to deliver its
        // reply. Resident EOF ends the proxy without waiting for caller input;
        // the command's process lifetime owns that background stdin reader.
        Start(send, "MachineControlChannelInput");
        Start(receive, "MachineControlChannelOutput");
        return ended.Task;
    }
}
