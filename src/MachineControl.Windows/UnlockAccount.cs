using System.IO;
using System.Runtime.InteropServices;
using System.Security.Principal;

namespace MachineControl.Windows;

internal static class UnlockAccount
{
    // Display names are not authority. Accept only a unique local SAM mapping;
    // domain, cloud and ambiguous names need separate provider evidence.
    public static string UniqueDisplayName(string sid)
    {
        var accounts = new List<(string Sid, string Display)>();
        var resume = 0;
        var error = NetUserEnum(null, 0, 0, out var users, -1, out var count, out _, ref resume);
        try
        {
            if (error != 0 || count > 1000) throw new InvalidDataException("local_account_discovery_uncertain");
            for (var i = 0; i < count; i++)
            {
                var name = Marshal.PtrToStringUni(Marshal.ReadIntPtr(users, i * IntPtr.Size))!;
                if (NetUserGetInfo(null, name, 10, out var info) != 0)
                    throw new InvalidDataException("local_account_discovery_uncertain");
                try
                {
                    var fullName = Marshal.PtrToStringUni(Marshal.ReadIntPtr(info, 3 * IntPtr.Size));
                    var accountSid = (SecurityIdentifier)new NTAccount(Environment.MachineName, name)
                        .Translate(typeof(SecurityIdentifier));
                    accounts.Add((accountSid.Value, string.IsNullOrEmpty(fullName) ? name : fullName));
                }
                finally { NetApiBufferFree(info); }
            }
        }
        finally { if (users != IntPtr.Zero) NetApiBufferFree(users); }
        var target = accounts.SingleOrDefault(account => account.Sid == sid);
        if (target.Display is null || accounts.Count(account =>
            string.Equals(account.Display, target.Display, StringComparison.OrdinalIgnoreCase)) != 1)
            throw new InvalidDataException("local_account_display_ambiguous");
        return target.Display;
    }

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)]
    private static extern int NetUserEnum(string? server, int level, int filter, out IntPtr buffer,
        int maximum, out int count, out int total, ref int resume);
    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)]
    private static extern int NetUserGetInfo(string? server, string user, int level, out IntPtr buffer);
    [DllImport("netapi32.dll")]
    private static extern int NetApiBufferFree(IntPtr buffer);
}
