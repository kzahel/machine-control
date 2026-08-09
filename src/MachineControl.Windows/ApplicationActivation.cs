using System.Runtime.InteropServices;

namespace MachineControl.Windows;

internal static class ApplicationActivation
{
    private const ushort VtLpwstr = 31;
    private static readonly PropertyKey AppUserModelIdKey = new(
        new Guid("9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3"),
        5);

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
            if (manager is not null && Marshal.IsComObject(manager))
            {
                Marshal.FinalReleaseComObject(manager);
            }
        }
    }

    public static string? TryGetWindowApplicationId(long hwnd)
    {
        var interfaceId = typeof(IPropertyStore).GUID;
        var result = SHGetPropertyStoreForWindow(
            new IntPtr(hwnd),
            ref interfaceId,
            out var store);
        if (result < 0 || store is null) return null;
        var value = default(PropVariant);
        try
        {
            var key = AppUserModelIdKey;
            result = store.GetValue(ref key, out value);
            return result >= 0 && value.ValueType == VtLpwstr &&
                value.PointerValue != IntPtr.Zero
                ? Marshal.PtrToStringUni(value.PointerValue)
                : null;
        }
        finally
        {
            PropVariantClear(ref value);
            if (store is not null && Marshal.IsComObject(store))
            {
                Marshal.FinalReleaseComObject(store);
            }
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

    [ComImport]
    [Guid("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IPropertyStore
    {
        [PreserveSig]
        int GetCount(out uint propertyCount);

        [PreserveSig]
        int GetAt(uint propertyIndex, out PropertyKey key);

        [PreserveSig]
        int GetValue(ref PropertyKey key, out PropVariant value);

        [PreserveSig]
        int SetValue(ref PropertyKey key, ref PropVariant value);

        [PreserveSig]
        int Commit();
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct PropertyKey(Guid formatId, uint propertyId)
    {
        public Guid FormatId = formatId;
        public uint PropertyId = propertyId;
    }

    [StructLayout(LayoutKind.Explicit)]
    private struct PropVariant
    {
        [FieldOffset(0)] public ushort ValueType;
        [FieldOffset(8)] public IntPtr PointerValue;
    }

    [DllImport("shell32.dll", PreserveSig = true)]
    private static extern int SHGetPropertyStoreForWindow(
        IntPtr hwnd,
        ref Guid interfaceId,
        [MarshalAs(UnmanagedType.Interface)] out IPropertyStore? propertyStore);

    [DllImport("ole32.dll", PreserveSig = true)]
    private static extern int PropVariantClear(ref PropVariant value);
}
