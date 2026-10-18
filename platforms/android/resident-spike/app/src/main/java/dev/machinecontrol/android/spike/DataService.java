package dev.machinecontrol.android.spike;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.CancellationSignal;
import android.os.IBinder;
import android.os.SystemClock;
import android.util.Base64;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import org.json.JSONObject;

/** Shared read-only data plane; each authenticated connection is independent. */
public final class DataService extends Service {
    private final String generation = UUID.randomUUID().toString();
    private final Set<Socket> sockets = ConcurrentHashMap.newKeySet();
    private final ThreadPoolExecutor readers = new ThreadPoolExecutor(4, 4, 0, TimeUnit.SECONDS, new ArrayBlockingQueue<>(4));
    private final ScheduledExecutorService timers = Executors.newSingleThreadScheduledExecutor();
    private volatile String token = "";
    private long deadline;
    private ServerSocket server;
    private NativeData data;
    @Override public IBinder onBind(Intent intent) { return null; }
    @Override public int onStartCommand(Intent intent, int flags, int id) {
        if (server != null) return START_NOT_STICKY;
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("data", getString(R.string.data_channel), NotificationManager.IMPORTANCE_LOW));
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, DataActivity.class), PendingIntent.FLAG_IMMUTABLE);
        startForeground(42, new Notification.Builder(this, "data").setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle(getString(R.string.data_notification)).setContentText(getString(R.string.data_notification_detail))
            .setContentIntent(open).setOngoing(true).build());
        try {
            data = new NativeData(this);
            server = new ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"));
            byte[] secret = new byte[32]; new SecureRandom().nextBytes(secret);
            token = Base64.encodeToString(secret, Base64.NO_WRAP | Base64.URL_SAFE);
            deadline = SystemClock.elapsedRealtime() + 900000;
            JSONObject receipt = new JSONObject().put("schema", "mc-android-spike/v1").put("plane", "data")
                .put("port", server.getLocalPort()).put("token", token).put("generation", generation);
            File file = new File(getFilesDir(), "data-bridge.json");
            Files.write(file.toPath(), receipt.toString().getBytes(StandardCharsets.UTF_8));
            android.system.Os.chmod(file.toString(), 0600);
            timers.schedule(() -> { stopSelf(); }, 15, TimeUnit.MINUTES);
            new Thread(this::accept, "mc-data-accept").start();
        } catch (Exception error) { stopSelf(); }
        return START_NOT_STICKY;
    }
    private void accept() {
        while (server != null && !server.isClosed()) {
            Socket connection = null;
            try {
                connection = server.accept(); sockets.add(connection);
                Socket accepted = connection;
                readers.execute(() -> serve(accepted));
            } catch (Exception error) {
                if (connection != null) { sockets.remove(connection); try { connection.close(); } catch (Exception ignored) { } }
            }
        }
    }
    private static String frame(InputStream input) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        for (int n = 0; n < 65536; n++) {
            int b = input.read();
            if (b < 0) { if (bytes.size() == 0) return null; throw new java.io.IOException("Incomplete request"); }
            if (b == '\n') return bytes.toString(StandardCharsets.UTF_8.name());
            bytes.write(b);
        }
        throw new java.io.IOException("Request exceeds bound");
    }
    private boolean authorized(String supplied) {
        String expected = token;
        return !expected.isEmpty() && SystemClock.elapsedRealtime() < deadline &&
            MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8));
    }
    private JSONObject refusal(String code, boolean terminal) throws Exception {
        return new JSONObject().put("accepted", false).put("generation", generation).put("errorCode", code)
            .put("message", "Selected data operation unavailable: " + code).put("sessionClosed", terminal)
            .put("delivery", "refused").put("effect", "none");
    }
    private void serve(Socket socket) {
        try (Socket connection = socket) {
            connection.setSoTimeout(60000);
            boolean opened = false;
            String line;
            while ((line = frame(connection.getInputStream())) != null) {
                JSONObject request = new JSONObject(line);
                String supplied = request.optString("token");
                JSONObject reply;
                if (!authorized(supplied)) reply = refusal("approval_denied", true);
                else if (!opened && !request.optString("operation").equals("open")) reply = refusal("approval_required", true);
                else {
                    CancellationSignal cancel = new CancellationSignal();
                    ScheduledFuture<?> timeout = timers.schedule(cancel::cancel, 5, TimeUnit.SECONDS);
                    try {
                        JSONObject result = data.dispatch(request, cancel);
                        cancel.throwIfCanceled();
                        reply = authorized(supplied) ? new JSONObject().put("accepted", true).put("generation", generation)
                            .put("operation", request.optString("operation")).put("actualRoute", "guest.user/android.content-resolver.spike")
                            .put("delivery", "confirmed").put("effect", "observation").put("data", result) : refusal("approval_denied", true);
                    } catch (NativeData.Failure error) { reply = refusal(error.code, false); }
                    catch (SecurityException error) { reply = refusal("permission_revoked", false); }
                    catch (android.os.OperationCanceledException error) { reply = refusal("provider_timeout", false); }
                    catch (Exception error) { reply = refusal("provider_unavailable", false); }
                    finally { timeout.cancel(false); }
                }
                byte[] response = (reply.toString() + "\n").getBytes(StandardCharsets.UTF_8);
                if (response.length > 8 * 1024 * 1024) break;
                connection.getOutputStream().write(response); connection.getOutputStream().flush();
                if (reply.optBoolean("sessionClosed")) break;
                opened = true;
            }
        } catch (Exception ignored) { }
        finally { sockets.remove(socket); }
    }
    @Override public void onDestroy() {
        token = "";
        new File(getFilesDir(), "data-bridge.json").delete();
        try { if (server != null) server.close(); } catch (Exception ignored) { }
        for (Socket socket : sockets) try { socket.close(); } catch (Exception ignored) { }
        readers.shutdownNow(); timers.shutdownNow();
        super.onDestroy();
    }
}
