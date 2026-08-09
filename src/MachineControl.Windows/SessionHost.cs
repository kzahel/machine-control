using System.IO;

namespace MachineControl.Windows;

internal sealed class SessionHost(string pipeName, string generation)
{
    public async Task RunAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            await using var server = PipeTransport.CreateSystemServer(pipeName);
            try
            {
                var (requestText, writer) = await PipeTransport.AcceptAsync(
                    server,
                    cancellationToken);
                await using (writer)
                {
                    var request = Contract.ParseRequest(requestText);
                    var currentDesktop =
                        DesktopController.GetCurrentDesktopName();
                    var inputDesktop = DesktopController.GetInputDesktopName();
                    var response = string.Equals(
                            currentDesktop,
                            inputDesktop,
                            StringComparison.OrdinalIgnoreCase)
                        ? await ProviderRouter.ExecuteAsync(
                            request,
                            generation,
                            cancellationToken)
                        : await ProtectedDesktopWorker.ExecuteAsync(
                            request,
                            generation,
                            inputDesktop,
                            cancellationToken);
                    await writer.WriteLineAsync(
                        Contract.Serialize(response).AsMemory(),
                        cancellationToken);
                }
            }
            catch (OperationCanceledException) when (
                cancellationToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception)
            {
                // A malformed or disconnected client must not kill the helper.
            }
        }
    }
}
