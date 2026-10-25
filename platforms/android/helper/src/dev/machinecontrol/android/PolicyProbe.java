package dev.machinecontrol.android;

import android.app.admin.DevicePolicyManager;
import android.content.Context;
import android.os.Looper;
import android.os.UserHandle;

/** Read-only effective wipe policy for the foreground user. Never reads stdin. */
public final class PolicyProbe {
    private PolicyProbe() {}

    public static void main(String[] arguments) {
        try {
            Looper.prepareMainLooper();
            Class<?> activityManager = Class.forName("android.app.ActivityManager");
            int user = (Integer) activityManager.getMethod("getCurrentUser").invoke(null);
            Class<?> activityThread = Class.forName("android.app.ActivityThread");
            Object thread = activityThread.getMethod("systemMain").invoke(null);
            Context system = (Context) activityThread.getMethod("getSystemContext").invoke(thread);
            UserHandle handle = (UserHandle) UserHandle.class.getMethod("of", int.class).invoke(null, user);
            Context shell = (Context) Context.class.getMethod(
                "createPackageContextAsUser", String.class, int.class, UserHandle.class
            ).invoke(system, "com.android.shell", 0, handle);
            int contextUser = (Integer) Context.class.getMethod("getUserId").invoke(shell);
            if (contextUser != user) {
                System.exit(2);
            }
            DevicePolicyManager policy = shell.getSystemService(DevicePolicyManager.class);
            int maximum = policy.getMaximumFailedPasswordsForWipe(null);
            if (maximum < 0) {
                System.exit(2);
            }
            System.out.println("userId=" + user + " maximumFailedPasswordsForWipe=" + maximum);
            System.exit(0);
        } catch (Throwable error) {
            // Unavailable/denied/unsupported policy remains unknown to the host.
            System.exit(2);
        }
    }
}
