using System.Runtime.InteropServices;

namespace MachineControl.Windows;

internal static class ApplicationActivation
{
    public static uint Activate(string applicationId, string arguments)
    {
        var type = Type.GetTypeFromCLSID(
            new Guid("45ba127d-10a8-46ea-8ab7-56ea9078943c"),
            throwOnError: true)!;
        var manager = (IApplicationActivationManager)
            Activator.CreateInstance(type)!;
        try
        {
            var result = manager.ActivateApplication(
                applicationId,
                arguments,
                ActivateOptions.None,
                out var processId);
            Marshal.ThrowExceptionForHR(result);
            return processId;
        }
        finally
        {
            Marshal.FinalReleaseComObject(manager);
        }
    }

    [Flags]
    private enum ActivateOptions
    {
        None = 0,
    }

    [ComImport]
    [Guid("2e941141-7f97-4756-ba1d-9decde894a3d")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IApplicationActivationManager
    {
        [PreserveSig]
        int ActivateApplication(
            [MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments,
            ActivateOptions options,
            out uint processId);

        [PreserveSig]
        int ActivateForFile(
            [MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            IntPtr itemArray,
            [MarshalAs(UnmanagedType.LPWStr)] string verb,
            out uint processId);

        [PreserveSig]
        int ActivateForProtocol(
            [MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            IntPtr itemArray,
            out uint processId);
    }
}
