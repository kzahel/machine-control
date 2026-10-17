package dev.machinecontrol.android.spike;

import android.app.Instrumentation;
import android.content.Context;
import android.os.Bundle;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.concurrent.TimeUnit;

/** Debug-only provisioning probe: execute the staged test under the host app UID. */
public final class PhonePythonProbe extends Instrumentation {
    private Bundle arguments;
    @Override public void onCreate(Bundle values) { arguments = values; start(); }
    @Override public void onStart() {
        Bundle result = new Bundle();
        Process process = null;
        try {
            Context host = getTargetContext();
            File state = new File(host.getFilesDir(), "state");
            String relative = arguments.getString("workspace", "");
            if (!relative.matches("mc-bridge-[a-f0-9]{32}")) throw new IllegalArgumentException("Explicit disposable workspace required");
            File workspace = new File(state, relative);
            File root = new File(host.getFilesDir(), "runtime");
            String lib = host.getApplicationInfo().nativeLibraryDir;
            File tmp = new File(host.getCacheDir(), relative); tmp.mkdirs();
            ArrayList<String> command = new ArrayList<>(Arrays.asList(
                lib + "/libproot.so", "--kill-on-exit", "--link2symlink", "-0", "-r", root.toString(),
                "-b", "/dev", "-b", "/proc", "-b", "/sys", "-b", state + ":/home/host",
                "-w", "/home/host/" + relative, "/usr/bin/env", "-i", "HOME=/home/host",
                "LANG=C.UTF-8", "PATH=/usr/bin:/bin", "/usr/bin/python3", "phone_probe.py"));
            ProcessBuilder builder = new ProcessBuilder(command);
            builder.environment().clear();
            builder.environment().put("PROOT_LOADER", lib + "/libproot-loader.so");
            builder.environment().put("PROOT_TMP_DIR", tmp.toString());
            builder.environment().put("LD_LIBRARY_PATH", lib);
            builder.redirectErrorStream(true);
            builder.redirectOutput(new File(workspace, "phone-probe.log"));
            process = builder.start();
            boolean ended = process.waitFor(360, TimeUnit.SECONDS);
            if (!ended) process.destroyForcibly();
            result.putString("stream", ended && process.exitValue() == 0 ? "PHONE_PYTHON_PASS\n" : "PHONE_PYTHON_FAILED; inspect private workspace\n");
            finish(ended && process.exitValue() == 0 ? -1 : 1, result);
        } catch (Exception error) {
            if (process != null) process.destroyForcibly();
            result.putString("stream", "PHONE_PYTHON_FAILED: " + error.getClass().getSimpleName() + "\n");
            finish(1, result);
        }
    }
}
