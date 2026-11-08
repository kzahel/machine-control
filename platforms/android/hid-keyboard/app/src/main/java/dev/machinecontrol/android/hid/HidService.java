package dev.machinecontrol.android.hid;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothHidDevice;
import android.bluetooth.BluetoothHidDeviceAppSdpSettings;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Base64;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.SynchronousQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.locks.ReentrantLock;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Foreground service that registers a Bluetooth HID keyboard and mouse and
 * accepts agent commands on a token-authenticated loopback socket. ADB access
 * is the authority: the grant lives in app-private storage that only
 * {@code run-as} on this debuggable build can read, and only the ADB shell may
 * start {@link ArmActivity}. No request payloads, typed text or tokens are logged.
 *
 * Bluetooth permissions are verified before the service starts; a later
 * revocation surfaces as a SecurityException, which the control socket
 * reports as a refusal and the service treats as fatal.
 */
@SuppressLint("MissingPermission")
public final class HidService extends Service {
    static final String ACTION_START = "dev.machinecontrol.android.hid.START";
    static final String ACTION_STOP = "dev.machinecontrol.android.hid.STOP";
    static final String SCHEMA = "mc-android-hid/v1";
    static final String PREF_OPERATOR_STOPPED = "operatorStopped";
    static final long GRANT_MILLIS = 60 * 60 * 1000;
    private static final long HELD_BUTTON_MILLIS = 15000;
    private static final int NOTIFICATION = 1;
    private static final int MAX_FRAME = 64 * 1024;
    private static final int MAX_CONNECTIONS = 4;
    private static final int AUTH_TIMEOUT_MILLIS = 5000;

    interface Listener { void changed(); }

    static volatile HidService current;
    static volatile Listener listener;

    private final Handler main = new Handler(Looper.getMainLooper());
    private final String generation = UUID.randomUUID().toString();
    private final ExecutorService callbacks = Executors.newSingleThreadExecutor();
    private final ExecutorService pointer = Executors.newSingleThreadExecutor();
    private final ThreadPoolExecutor connections = new ThreadPoolExecutor(0, MAX_CONNECTIONS, 30,
        TimeUnit.SECONDS, new SynchronousQueue<>());
    private final ReentrantLock keyboardLock = new ReentrantLock();
    private final Object mouseLock = new Object();
    private final AtomicInteger cancelEpoch = new AtomicInteger();
    private BluetoothAdapter adapter;
    private volatile BluetoothHidDevice hid;
    private volatile boolean registered;
    private volatile BluetoothDevice host;
    private volatile boolean bootProtocol;
    private volatile int leds = -1;
    private int buttons;
    private int agentButtons;
    private long agentActivity;
    private ServerSocket server;
    private volatile String token = "";
    private volatile long deadline;
    private volatile boolean stopping;

    @Override public IBinder onBind(Intent intent) { return null; }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            // The operator's kill switch: agents cannot re-arm until a person relaunches the app.
            prefs().edit().putBoolean(PREF_OPERATOR_STOPPED, true).apply();
            stopSelf();
            return START_NOT_STICKY;
        }
        try {
            startForeground(NOTIFICATION, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);
        } catch (RuntimeException refused) {
            // Missing Bluetooth permission or a background-start refusal: publish no grant.
            stopSelf();
            return START_NOT_STICKY;
        }
        if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            stopSelf();
            return START_NOT_STICKY;
        }
        current = this;
        if (adapter == null) setup();
        try { arm(); } catch (Exception error) { revoke(); }
        changed();
        return START_NOT_STICKY;
    }

    private final BroadcastReceiver adapterChanges = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) { changed(); }
    };

    private void setup() {
        adapter = getSystemService(BluetoothManager.class).getAdapter();
        if (adapter == null) return;
        IntentFilter filter = new IntentFilter(BluetoothAdapter.ACTION_SCAN_MODE_CHANGED);
        filter.addAction(BluetoothAdapter.ACTION_STATE_CHANGED);
        // Protected system broadcasts only; the exported flag exists from API 33.
        if (android.os.Build.VERSION.SDK_INT >= 33) registerReceiver(adapterChanges, filter, RECEIVER_NOT_EXPORTED);
        else registerReceiver(adapterChanges, filter);
        adapter.getProfileProxy(this, new BluetoothProfile.ServiceListener() {
            @Override public void onServiceConnected(int profile, BluetoothProfile proxy) {
                hid = (BluetoothHidDevice) proxy;
                register();
            }
            @Override public void onServiceDisconnected(int profile) {
                hid = null;
                registered = false;
                host = null;
                changed();
            }
        }, BluetoothProfile.HID_DEVICE);
        try {
            server = new ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"));
            new Thread(this::accept, "mc-hid-accept").start();
        } catch (IOException error) {
            server = null;
        }
    }

    private void register() {
        BluetoothHidDevice proxy = hid;
        if (proxy == null) return;
        BluetoothHidDeviceAppSdpSettings sdp = new BluetoothHidDeviceAppSdpSettings(
            "MC HID", "Machine Control keyboard and mouse", "Machine Control",
            BluetoothHidDevice.SUBCLASS1_COMBO, Reports.DESCRIPTOR);
        proxy.registerApp(sdp, null, null, callbacks, new BluetoothHidDevice.Callback() {
            @Override public void onAppStatusChanged(BluetoothDevice plugged, boolean isRegistered) {
                registered = isRegistered;
                if (isRegistered) {
                    BluetoothDevice target = plugged != null ? plugged : savedHost();
                    if (target != null && hid != null) hid.connect(target);
                } else {
                    host = null;
                }
                changed();
            }
            @Override public void onConnectionStateChanged(BluetoothDevice device, int state) {
                if (state == BluetoothProfile.STATE_CONNECTED) {
                    host = device;
                    bootProtocol = false;
                    leds = -1; // Unknown until this host reports its LED state.
                    prefs().edit().putString("host", device.getAddress()).apply();
                } else if (state == BluetoothProfile.STATE_DISCONNECTED && device.equals(host)) {
                    host = null;
                    synchronized (mouseLock) { buttons = 0; }
                }
                changed();
            }
            @Override public void onGetReport(BluetoothDevice device, byte type, byte id, int size) {
                BluetoothHidDevice proxy = hid;
                if (proxy == null) return;
                if (id == Reports.KEYBOARD_ID && type == BluetoothHidDevice.REPORT_TYPE_INPUT)
                    proxy.replyReport(device, type, id, new byte[Reports.KEYBOARD_SIZE]);
                else if (id == Reports.KEYBOARD_ID && type == BluetoothHidDevice.REPORT_TYPE_OUTPUT)
                    proxy.replyReport(device, type, id, new byte[] {(byte) Math.max(0, leds)});
                else if (id == Reports.MOUSE_ID && type == BluetoothHidDevice.REPORT_TYPE_INPUT)
                    proxy.replyReport(device, type, id, new byte[Reports.MOUSE_SIZE]);
                else proxy.reportError(device, BluetoothHidDevice.ERROR_RSP_INVALID_RPT_ID);
            }
            @Override public void onSetReport(BluetoothDevice device, byte type, byte id, byte[] data) {
                if (id == Reports.KEYBOARD_ID && data != null && data.length > 0) leds = data[0] & 0xff;
                BluetoothHidDevice proxy = hid;
                if (proxy != null) proxy.reportError(device, BluetoothHidDevice.ERROR_RSP_SUCCESS);
            }
            @Override public void onSetProtocol(BluetoothDevice device, byte protocol) {
                bootProtocol = protocol == BluetoothHidDevice.PROTOCOL_BOOT_MODE;
            }
            @Override public void onInterruptData(BluetoothDevice device, byte id, byte[] data) {
                if (id == Reports.KEYBOARD_ID && data != null && data.length > 0) {
                    leds = data[0] & 0xff;
                    changed();
                }
            }
        });
    }

    private SharedPreferences prefs() { return getSharedPreferences("hid", MODE_PRIVATE); }

    private BluetoothDevice savedHost() {
        String address = prefs().getString("host", null);
        if (address == null || adapter == null || !BluetoothAdapter.checkBluetoothAddress(address)) return null;
        for (BluetoothDevice device : adapter.getBondedDevices())
            if (device.getAddress().equals(address)) return device;
        return null;
    }

    synchronized void arm() throws Exception {
        if (server == null) throw new IOException("Control socket unavailable");
        byte[] secret = new byte[32];
        new SecureRandom().nextBytes(secret);
        token = Base64.encodeToString(secret, Base64.NO_WRAP | Base64.URL_SAFE);
        deadline = SystemClock.elapsedRealtime() + GRANT_MILLIS;
        JSONObject grant = new JSONObject().put("schema", SCHEMA).put("port", server.getLocalPort())
            .put("token", token).put("generation", generation);
        File file = new File(getFilesDir(), "bridge.json");
        File temporary = new File(getFilesDir(), "bridge.json.tmp");
        Files.write(temporary.toPath(), grant.toString().getBytes(StandardCharsets.UTF_8));
        android.system.Os.chmod(temporary.toString(), 0600);
        if (!temporary.renameTo(file)) throw new IOException("Grant not published");
    }

    synchronized void revoke() {
        token = "";
        deadline = 0;
        new File(getFilesDir(), "bridge.json").delete();
    }

    @Override public void onDestroy() {
        stopping = true;
        revoke();
        cancelEpoch.incrementAndGet();
        if (adapter != null) unregisterReceiver(adapterChanges);
        current = null;
        try { if (server != null) server.close(); } catch (IOException ignored) { }
        BluetoothHidDevice proxy = hid;
        if (proxy != null) {
            BluetoothDevice connected = host;
            if (connected != null) {
                proxy.sendReport(connected, Reports.KEYBOARD_ID, Reports.keyboard(0, 0));
                proxy.sendReport(connected, Reports.MOUSE_ID, Reports.mouse(0, 0, 0, 0, 0));
            }
            proxy.unregisterApp();
            if (adapter != null) adapter.closeProfileProxy(BluetoothProfile.HID_DEVICE, proxy);
        }
        hid = null;
        host = null;
        registered = false;
        callbacks.shutdownNow();
        pointer.shutdownNow();
        connections.shutdownNow();
        changed();
        super.onDestroy();
    }

    // ---- State shared with the touchpad UI ----

    String summary() {
        if (adapter == null) return "Bluetooth unavailable";
        if (!adapter.isEnabled()) return "Bluetooth is off";
        if (!registered) return "Registering HID device…";
        BluetoothDevice connected = host;
        String self = "This handheld: " + adapter.getName();
        if (connected != null) return "Connected to " + connected.getName() + "\n" + self;
        String scan = adapter.getScanMode() == BluetoothAdapter.SCAN_MODE_CONNECTABLE_DISCOVERABLE
            ? "discoverable" : "not discoverable";
        return "Waiting for a host (" + scan + ")\n" + self;
    }

    private void changed() {
        main.post(() -> {
            Listener current = listener;
            if (current != null) current.changed();
            if (!stopping) getSystemService(NotificationManager.class).notify(NOTIFICATION, notification());
        });
    }

    private Notification notification() {
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("hid", getString(R.string.channel),
            NotificationManager.IMPORTANCE_LOW));
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class),
            PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop = PendingIntent.getService(this, 1,
            new Intent(this, HidService.class).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE);
        String text = host != null ? "Connected; agents can type on the host" : "Waiting for a host";
        return new Notification.Builder(this, "hid")
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .setContentTitle(getString(R.string.app_name)).setContentText(text)
            .setContentIntent(open).setOngoing(true)
            .addAction(new Notification.Action.Builder(null, getString(R.string.stop), stop).build())
            .build();
    }

    // ---- Report delivery ----

    private boolean send(int id, byte[] report) {
        BluetoothHidDevice proxy = hid;
        BluetoothDevice connected = host;
        if (proxy == null || connected == null) return false;
        return proxy.sendReport(connected, id, report);
    }

    /** Releases every key, retrying because a stuck key auto-repeats on the host. */
    private boolean releaseKeys() {
        int[] backoff = {0, 20, 50, 100};
        for (int wait : backoff) {
            if (wait > 0) SystemClock.sleep(wait);
            if (send(Reports.KEYBOARD_ID, Reports.keyboard(0, 0))) return true;
        }
        return false;
    }

    boolean move(int dx, int dy) {
        int count = Reports.stepCount(dx, dy);
        int[] xs = Reports.spread(dx, count), ys = Reports.spread(dy, count);
        for (int i = 0; i < count; i++) {
            synchronized (mouseLock) {
                if (!send(Reports.MOUSE_ID, Reports.mouse(buttons, xs[i], ys[i], 0, 0))) return false;
            }
            if (count > 1) SystemClock.sleep(4);
        }
        return true;
    }

    boolean scroll(int wheel, int pan) {
        int count = Reports.stepCount(wheel, pan);
        int[] wheels = Reports.spread(wheel, count), pans = Reports.spread(pan, count);
        for (int i = 0; i < count; i++) {
            synchronized (mouseLock) {
                if (!send(Reports.MOUSE_ID, Reports.mouse(buttons, 0, 0, wheels[i], pans[i]))) return false;
            }
            if (count > 1) SystemClock.sleep(8);
        }
        return true;
    }

    boolean button(int mask, boolean down) {
        synchronized (mouseLock) {
            buttons = down ? (buttons | mask) : (buttons & ~mask);
            return send(Reports.MOUSE_ID, Reports.mouse(buttons, 0, 0, 0, 0));
        }
    }

    /**
     * Agent-held buttons span separate CLI calls, so they are released if the
     * agent goes quiet. Moves and scrolls count as activity; only the buttons
     * the agent pressed are released, never a person's touchpad drag.
     */
    private int agentButton(int mask, boolean down) throws Refusal {
        int held;
        synchronized (mouseLock) {
            if (!button(mask, down)) throw new Refusal("send_failed", "Bluetooth stack refused the report");
            agentButtons = down ? (agentButtons | mask) : (agentButtons & ~mask);
            held = agentButtons;
        }
        touchAgentButtons();
        return held;
    }

    private void touchAgentButtons() {
        long now = SystemClock.elapsedRealtime();
        synchronized (mouseLock) {
            if (agentButtons == 0) return;
            agentActivity = now;
        }
        main.postDelayed(() -> {
            synchronized (mouseLock) { if (agentActivity != now || agentButtons == 0) return; }
            pointerAsync(this::releaseAgentButtons);
        }, HELD_BUTTON_MILLIS);
    }

    private void releaseAgentButtons() {
        synchronized (mouseLock) {
            int mask = agentButtons;
            agentButtons = 0;
            if (mask != 0) button(mask, false);
        }
    }

    private int agentButtonsHeld() {
        synchronized (mouseLock) { return agentButtons; }
    }

    private boolean releaseButtons() {
        synchronized (mouseLock) {
            buttons = 0;
            agentButtons = 0;
            for (int wait : new int[] {0, 20, 50, 100}) {
                if (wait > 0) SystemClock.sleep(wait);
                if (send(Reports.MOUSE_ID, Reports.mouse(0, 0, 0, 0, 0))) return true;
            }
            return false;
        }
    }

    boolean click(int mask, int count, int holdMillis) {
        for (int i = 0; i < count; i++) {
            if (!button(mask, true)) return false;
            SystemClock.sleep(holdMillis);
            if (!button(mask, false)) {
                releaseButtons();
                return false;
            }
            if (i + 1 < count) SystemClock.sleep(holdMillis);
        }
        return true;
    }

    /** Touchpad callbacks run off the UI thread so click holds never block drawing. */
    void pointerAsync(Runnable action) {
        if (!pointer.isShutdown()) pointer.execute(action);
    }

    /** Result of a paced keyboard delivery. */
    static final class Delivery {
        int sent;
        boolean cancelled;
        boolean released = true;
    }

    /** Sends each stroke as paced down/up reports; stops early on failure or cancel. */
    Delivery strokes(int[][] strokes, int holdMillis, int gapMillis) throws Refusal {
        // Never queue keyboard input behind another request: a caller that timed
        // out must not have its text typed minutes later.
        boolean locked;
        try { locked = keyboardLock.tryLock(500, TimeUnit.MILLISECONDS); }
        catch (InterruptedException interrupted) { locked = false; }
        if (!locked) throw new Refusal("busy", "Another keyboard request is in progress; cancel it or retry");
        try {
            Delivery result = new Delivery();
            int epoch = cancelEpoch.get();
            for (int[] stroke : strokes) {
                if (cancelEpoch.get() != epoch) { result.cancelled = true; break; }
                boolean modified = stroke[0] != 0 && stroke[1] != 0;
                if (modified) {
                    // Modifier first, so hosts that sample the modifier byte late still see it.
                    if (!send(Reports.KEYBOARD_ID, Reports.keyboard(stroke[0], 0))) break;
                    SystemClock.sleep(holdMillis);
                }
                if (!send(Reports.KEYBOARD_ID, Reports.keyboard(stroke[0], stroke[1]))) {
                    result.released = releaseKeys();
                    break;
                }
                SystemClock.sleep(holdMillis);
                if (modified) {
                    // Release the key before the modifier, as a physical keyboard does,
                    // so no host ever sees an unmodified key-up race the Shift-up.
                    if (!send(Reports.KEYBOARD_ID, Reports.keyboard(stroke[0], 0))) {
                        result.released = releaseKeys();
                        break;
                    }
                    SystemClock.sleep(holdMillis);
                }
                if (!releaseKeys()) { result.released = false; break; }
                result.sent++;
                SystemClock.sleep(gapMillis);
            }
            return result;
        } finally {
            keyboardLock.unlock();
        }
    }

    // ---- Agent control socket ----

    private void accept() {
        ServerSocket listening = server;
        while (listening != null && !listening.isClosed()) {
            Socket socket;
            try {
                socket = listening.accept();
            } catch (IOException error) {
                SystemClock.sleep(100); // Avoid spinning on persistent errors such as fd exhaustion.
                continue;
            }
            try {
                connections.execute(() -> {
                    try (Socket connection = socket) {
                        serve(connection);
                    } catch (Exception ignored) {
                        // No payloads, tokens or typed text in diagnostics.
                    }
                });
            } catch (RejectedExecutionException busy) {
                try { socket.close(); } catch (IOException ignored) { }
            }
        }
    }

    private static String frame(InputStream input) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        for (int n = 0; n <= MAX_FRAME; n++) {
            int b = input.read();
            if (b < 0) {
                if (bytes.size() == 0) return null;
                throw new IOException("Incomplete frame");
            }
            if (b == '\n') return bytes.toString(StandardCharsets.UTF_8.name());
            bytes.write(b);
        }
        throw new IOException("Request too large");
    }

    private boolean authorized(String supplied) {
        String expected = token;
        return !expected.isEmpty() && SystemClock.elapsedRealtime() < deadline &&
            MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8));
    }

    /**
     * Proves this process holds the current token without revealing it, so a
     * client never sends the token to an impostor bound to a stale port.
     */
    private String proof(String nonce) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(token.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        byte[] digest = mac.doFinal(("mc-hid-ping:" + nonce).getBytes(StandardCharsets.UTF_8));
        StringBuilder hex = new StringBuilder();
        for (byte b : digest) hex.append(String.format(Locale.ROOT, "%02x", b));
        return hex.toString();
    }

    private static void write(OutputStream output, JSONObject reply) throws IOException {
        output.write((reply.toString() + "\n").getBytes(StandardCharsets.UTF_8));
        output.flush();
    }

    private void serve(Socket socket) throws Exception {
        InputStream input = socket.getInputStream();
        OutputStream output = socket.getOutputStream();
        // Unauthenticated peers get a short deadline and one challenge, then must
        // authenticate; any pre-authentication failure closes the connection.
        long authDeadline = SystemClock.elapsedRealtime() + AUTH_TIMEOUT_MILLIS;
        boolean challenged = false;
        boolean admitted = false;
        String line;
        while (true) {
            if (!admitted) {
                // One deadline for the whole unauthenticated phase, not per read.
                long remaining = authDeadline - SystemClock.elapsedRealtime();
                if (remaining <= 0) return;
                socket.setSoTimeout((int) remaining);
            }
            line = frame(input);
            if (line == null) return;
            JSONObject request;
            try {
                request = new JSONObject(line);
            } catch (org.json.JSONException error) {
                if (!admitted) return;
                write(output, refused("bad_request", "Malformed request"));
                continue;
            }
            if (!request.has("token")) {
                String nonce = request.optString("nonce");
                if (admitted || challenged || !"ping".equals(request.optString("op")) ||
                    nonce.length() < 16 || nonce.length() > 128) return;
                challenged = true;
                if (token.isEmpty() || SystemClock.elapsedRealtime() >= deadline) {
                    write(output, new JSONObject().put("accepted", false).put("errorCode", "approval_denied"));
                    return;
                }
                write(output, new JSONObject().put("accepted", true).put("op", "ping").put("proof", proof(nonce)));
                continue;
            }
            if (!authorized(request.optString("token"))) {
                write(output, new JSONObject().put("accepted", false).put("errorCode", "approval_denied")
                    .put("message", "Grant absent, revoked or expired; arm again"));
                return;
            }
            if (!admitted) {
                admitted = true;
                socket.setSoTimeout(60000);
            }
            JSONObject reply;
            try {
                reply = dispatch(request);
            } catch (Refusal refusal) {
                reply = refused(refusal.code, refusal.getMessage());
            } catch (org.json.JSONException error) {
                reply = refused("bad_request", "Malformed request");
            } catch (SecurityException error) {
                write(output, refused("permission_denied", "Bluetooth permission was revoked"));
                main.post(this::stopSelf);
                return;
            }
            write(output, reply);
        }
    }

    private static final class Refusal extends Exception {
        final String code;
        Refusal(String code, String message) { super(message); this.code = code; }
    }

    private JSONObject ok(String op) throws Exception {
        return new JSONObject().put("accepted", true).put("op", op).put("generation", generation);
    }

    private JSONObject refused(String code, String message) {
        try {
            return new JSONObject().put("accepted", false).put("errorCode", code).put("message", message)
                .put("generation", generation);
        } catch (org.json.JSONException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    private void requireConnected() throws Refusal {
        if (hid == null || !registered) throw new Refusal("not_registered", "HID device is not registered");
        if (host == null) throw new Refusal("no_host", "No host is connected");
    }

    /** Input goes only to the connected host, and to the expected one when the caller names it. */
    private void requireHost(JSONObject request) throws Refusal {
        requireConnected();
        BluetoothDevice connected = host;
        if (connected == null) throw new Refusal("no_host", "No host is connected");
        String expected = request.optString("expectHost");
        if (!expected.isEmpty() && !expected.equalsIgnoreCase(connected.getAddress()))
            throw new Refusal("wrong_host", "The connected host is not the expected one");
        if (bootProtocol) throw new Refusal("boot_protocol", "Host selected boot protocol; unsupported");
    }

    private static int bounded(JSONObject request, String key, int fallback, int min, int max) throws Refusal {
        int value = request.optInt(key, fallback);
        if (value < min || value > max) throw new Refusal("bad_request", key + " out of range");
        return value;
    }

    private static int buttonMask(String name) throws Refusal {
        switch (name) {
            case "left": return Reports.BUTTON_LEFT;
            case "right": return Reports.BUTTON_RIGHT;
            case "middle": return Reports.BUTTON_MIDDLE;
            default: throw new Refusal("bad_request", "Unknown button");
        }
    }

    private JSONObject delivered(String op, boolean sent) throws Exception {
        if (!sent) throw new Refusal("send_failed", "Bluetooth stack refused the report");
        return ok(op).put("delivery", "sent").put("effect", "unverified");
    }

    private JSONObject keyboardReply(String op, Delivery delivery, int total) throws Exception {
        JSONObject reply;
        if (delivery.cancelled) reply = refused("cancelled", "Cancelled by a later request");
        else if (delivery.sent != total) reply = refused("send_failed", "Delivery stopped early");
        else return ok(op).put("strokesSent", delivery.sent).put("strokesTotal", total)
            .put("delivery", "sent").put("effect", "unverified");
        return reply.put("strokesSent", delivery.sent).put("strokesTotal", total).put("delivery", "partial")
            .put("released", delivery.released ? "confirmed" : "unknown");
    }

    private JSONObject dispatch(JSONObject request) throws Exception {
        String op = request.optString("op");
        switch (op) {
            case "ping": return ok(op);
            case "status": return status();
            case "connect": return connect(request);
            case "cancel": {
                cancelEpoch.incrementAndGet();
                return ok(op);
            }
            case "unplug": {
                // Android implements HID disconnect as a virtual-cable unplug, which
                // also removes the bond on the handheld. Re-pairing is then required.
                if (!request.optBoolean("confirmUnpair"))
                    throw new Refusal("confirmation_required", "Unplug removes the pairing; confirm explicitly");
                BluetoothHidDevice proxy = hid;
                BluetoothDevice connected = host;
                if (proxy == null || connected == null) throw new Refusal("no_host", "No host is connected");
                return ok(op).put("requested", proxy.disconnect(connected)).put("bondRemoved", "expected");
            }
            case "type": {
                requireHost(request);
                if (leds >= 0 && (leds & 2) != 0)
                    throw new Refusal("caps_lock_on", "Caps Lock is on at the host; letters would invert");
                String layout = request.optString("layout", "us");
                if (!Keymap.knownLayout(layout)) throw new Refusal("bad_request", "Unknown layout");
                int[][] strokes;
                try { strokes = Keymap.text(request.optString("text"), layout); }
                catch (IllegalArgumentException error) { throw new Refusal("unsupported_text", error.getMessage()); }
                int hold = bounded(request, "holdMs", 12, 2, 500);
                int gap = bounded(request, "gapMs", 12, 2, 2000);
                return keyboardReply(op, strokes(strokes, hold, gap), strokes.length);
            }
            case "key": {
                requireHost(request);
                String layout = request.optString("layout", "us");
                if (!Keymap.knownLayout(layout)) throw new Refusal("bad_request", "Unknown layout");
                JSONArray chords = request.optJSONArray("chords");
                if (chords == null || chords.length() == 0) throw new Refusal("bad_request", "chords required");
                int[][] strokes = new int[chords.length()][];
                try {
                    for (int i = 0; i < chords.length(); i++) strokes[i] = Keymap.chord(chords.getString(i), layout);
                } catch (IllegalArgumentException error) { throw new Refusal("bad_request", error.getMessage()); }
                int hold = bounded(request, "holdMs", 30, 2, 2000);
                int gap = bounded(request, "gapMs", 30, 2, 5000);
                return keyboardReply(op, strokes(strokes, hold, gap), strokes.length);
            }
            case "move": {
                requireHost(request);
                touchAgentButtons();
                return delivered(op, move(bounded(request, "dx", 0, -10000, 10000),
                    bounded(request, "dy", 0, -10000, 10000))).put("buttonsHeld", agentButtonsHeld());
            }
            case "scroll": {
                requireHost(request);
                touchAgentButtons();
                return delivered(op, scroll(bounded(request, "wheel", 0, -1000, 1000),
                    bounded(request, "pan", 0, -1000, 1000))).put("buttonsHeld", agentButtonsHeld());
            }
            case "click": {
                requireHost(request);
                return delivered(op, click(buttonMask(request.optString("button", "left")),
                    bounded(request, "count", 1, 1, 3), bounded(request, "holdMs", 40, 5, 2000)));
            }
            case "button": {
                requireHost(request);
                int held = agentButton(buttonMask(request.optString("button", "left")), request.optBoolean("down"));
                return ok(op).put("delivery", "sent").put("effect", "unverified")
                    .put("buttonsHeld", held).put("autoReleaseSeconds", HELD_BUTTON_MILLIS / 1000);
            }
            case "release": {
                // Releasing is always safe, whichever host is connected.
                requireConnected();
                cancelEpoch.incrementAndGet();
                boolean keys = releaseKeys();
                return delivered(op, releaseButtons() && keys);
            }
            case "disarm": {
                revoke();
                main.post(this::stopSelf);
                return ok(op).put("stopping", true);
            }
            default:
                throw new Refusal("bad_request", "Unknown op");
        }
    }

    private JSONObject connect(JSONObject request) throws Exception {
        BluetoothHidDevice proxy = hid;
        if (proxy == null || !registered) throw new Refusal("not_registered", "HID device is not registered");
        String address = request.optString("address").toUpperCase(Locale.ROOT);
        if (!BluetoothAdapter.checkBluetoothAddress(address)) throw new Refusal("bad_request", "Invalid address");
        BluetoothDevice device = adapter.getRemoteDevice(address);
        boolean requested = proxy.connect(device);
        long until = SystemClock.elapsedRealtime() + bounded(request, "waitMs", 10000, 0, 60000);
        while (requested && SystemClock.elapsedRealtime() < until && !device.equals(host)) SystemClock.sleep(100);
        return ok("connect").put("requested", requested).put("connected", device.equals(host));
    }

    private JSONObject status() throws Exception {
        int led = leds;
        Object capsLock = led < 0 ? "unknown" : (Object) ((led & 2) != 0);
        JSONObject result = ok("status").put("registered", registered)
            .put("bluetoothOn", adapter != null && adapter.isEnabled())
            .put("expiresInSeconds", Math.max(0, (deadline - SystemClock.elapsedRealtime()) / 1000))
            .put("protocol", bootProtocol ? "boot" : "report")
            .put("capsLock", capsLock);
        if (adapter != null && adapter.isEnabled()) {
            int mode = adapter.getScanMode();
            result.put("scanMode", mode == BluetoothAdapter.SCAN_MODE_CONNECTABLE_DISCOVERABLE ? "discoverable"
                : mode == BluetoothAdapter.SCAN_MODE_CONNECTABLE ? "connectable" : "none");
            JSONArray bonded = new JSONArray();
            for (BluetoothDevice device : adapter.getBondedDevices())
                bonded.put(new JSONObject().put("address", device.getAddress()).put("name", device.getName()));
            result.put("bonded", bonded);
        }
        BluetoothDevice connected = host;
        result.put("host", connected == null ? JSONObject.NULL
            : new JSONObject().put("address", connected.getAddress()).put("name", connected.getName()));
        return result;
    }
}
