package dev.machinecontrol.android.spike;

import android.accessibilityservice.AccessibilityService;
import android.app.KeyguardManager;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Rect;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Base64;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.FutureTask;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import org.json.JSONArray;
import org.json.JSONObject;

/** Fixture-only native authority. No model-written code executes here. */
public final class ResidentService extends AccessibilityService {
    static volatile ResidentService current;
    private static final String ROUTE = "guest.user/android.accessibility.spike";
    private final Handler main = new Handler(Looper.getMainLooper());
    private final String generation = UUID.randomUUID().toString();
    private final Map<String, AccessibilityNodeInfo> references = new HashMap<>();
    private final ThreadPoolExecutor clients = new ThreadPoolExecutor(2, 2, 0,
        TimeUnit.SECONDS, new ArrayBlockingQueue<>(2));
    private ServerSocket server;
    private Socket owner;
    private String token = "";
    private long deadline;
    private int walked;
    private int observedWindow = -1;

    @Override protected void onServiceConnected() {
        current = this;
        try {
            server = new ServerSocket(0, 4, InetAddress.getByName("127.0.0.1"));
            new Thread(this::accept, "mc-android-accept").start();
        } catch (IOException error) { revoke(); }
    }

    void arm() throws Exception {
        revoke();
        if (server == null || server.isClosed()) throw new IOException("Bridge unavailable");
        byte[] secret = new byte[32];
        new SecureRandom().nextBytes(secret);
        token = Base64.encodeToString(secret, Base64.NO_WRAP | Base64.URL_SAFE);
        deadline = SystemClock.elapsedRealtime() + 900000;
        JSONObject receipt = new JSONObject().put("schema", "mc-android-spike/v1")
            .put("port", server.getLocalPort()).put("token", token).put("generation", generation);
        File file = new File(getFilesDir(), "bridge.json");
        Files.write(file.toPath(), receipt.toString().getBytes(StandardCharsets.UTF_8));
        android.system.Os.chmod(file.toString(), 0600);
        main.postDelayed(() -> { if (SystemClock.elapsedRealtime() >= deadline) revoke(); }, 900000);
    }

    void revoke() {
        token = "";
        deadline = 0;
        references.clear();
        new File(getFilesDir(), "bridge.json").delete();
        if (owner != null) { try { owner.close(); } catch (IOException ignored) { } }
        owner = null;
    }

    @Override public void onAccessibilityEvent(AccessibilityEvent event) {
        // Content events are invalidation hints for observations, not proof
        // that every native node was replaced. Revalidate membership at action
        // dispatch; unrelated events must not make ordinary model latency fail.
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null || root.getWindowId() != observedWindow ||
            !getPackageName().contentEquals(root.getPackageName())) references.clear();
    }
    @Override public void onInterrupt() { revoke(); }
    @Override public boolean onUnbind(Intent intent) { revoke(); return false; }
    @Override public void onDestroy() {
        revoke();
        current = null;
        try { if (server != null) server.close(); } catch (IOException ignored) { }
        clients.shutdownNow();
        super.onDestroy();
    }

    private void accept() {
        while (server != null && !server.isClosed()) {
            Socket socket = null;
            try {
                socket = server.accept();
                Socket accepted = socket;
                clients.execute(() -> serve(accepted));
            } catch (Exception error) {
                if (socket != null) try { socket.close(); } catch (IOException ignored) { }
            }
        }
    }

    private <T> T onMain(java.util.concurrent.Callable<T> task) throws Exception {
        FutureTask<T> pending = new FutureTask<>(task);
        main.post(pending);
        try { return pending.get(6, TimeUnit.SECONDS); }
        catch (Exception error) { pending.cancel(false); throw error; }
    }

    private static String frame(InputStream input) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        for (int n = 0; n < 65536; n++) {
            int b = input.read();
            if (b < 0) return bytes.size() == 0 ? null : failFrame();
            if (b == '\n') return bytes.toString(StandardCharsets.UTF_8.name());
            bytes.write(b);
        }
        throw new IOException("Request too large");
    }
    private static String failFrame() throws IOException { throw new IOException("Incomplete frame"); }

    private void serve(Socket socket) {
        try (Socket connection = socket) {
            connection.setSoTimeout(60000);
            String line;
            boolean admitted = false;
            while ((line = frame(connection.getInputStream())) != null) {
                JSONObject request = new JSONObject(line);
                boolean first = !admitted;
                JSONObject reply = onMain(() -> {
                    String supplied = request.optString("token");
                    if (token.isEmpty() || SystemClock.elapsedRealtime() >= deadline ||
                        !MessageDigest.isEqual(token.getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8)))
                        return refused("approval_denied", "Grant absent, revoked or expired");
                    if (first) {
                        if (!request.optString("operation").equals("open"))
                            return refused("approval_required", "Open an explicit bridge session");
                        if (owner != null && owner != connection) return refused("claim_not_held", "Fixture already controlled");
                        owner = connection;
                        return ok("open").put("data", new JSONObject().put("fixtureOnly", true)
                            .put("desktopClaimAudit", false).put("codeExecution", false));
                    }
                    if (owner != connection) return refused("control_session_closed", "Ownership ended");
                    try { return dispatch(request); }
                    catch (Refusal error) { return refused(error.code, error.getMessage()); }
                });
                if (!first && request.optString("operation").equals("capture") && reply.optBoolean("accepted"))
                    reply = capture(reply);
                byte[] response = (reply.toString() + "\n").getBytes(StandardCharsets.UTF_8);
                if (response.length > 8 * 1024 * 1024) throw new IOException("Reply too large");
                connection.getOutputStream().write(response);
                connection.getOutputStream().flush();
                if (!reply.optBoolean("accepted") && reply.optBoolean("sessionClosed")) break;
                admitted = true;
            }
        } catch (Exception ignored) {
            // No request payloads, tokens or UI contents in diagnostic logs.
        } finally {
            main.post(() -> { if (owner == socket) { owner = null; references.clear(); } });
        }
    }

    private JSONObject ok(String operation) throws Exception {
        return new JSONObject().put("accepted", true).put("operation", operation)
            .put("generation", generation).put("actualRoute", ROUTE)
            .put("coordinateSpace", "screen_physical_pixels").put("delivery", "confirmed")
            .put("effect", "unverifiable").put("uncertainty", "independent_effect_not_checked")
            .put("hostInterference", "target_foreground");
    }
    private JSONObject refused(String code, String message) throws Exception {
        boolean terminal = code.equals("approval_denied") || code.equals("approval_required") ||
            code.equals("claim_not_held") || code.equals("control_session_closed");
        return new JSONObject().put("accepted", false).put("errorCode", code).put("message", message)
            .put("sessionClosed", terminal)
            .put("generation", generation).put("actualRoute", ROUTE).put("delivery", "refused")
            .put("effect", "none").put("uncertainty", "none");
    }
    private static final class Refusal extends Exception {
        final String code;
        Refusal(String code, String message) { super(message); this.code = code; }
    }

    private AccessibilityNodeInfo fixture() throws Refusal {
        if (getSystemService(KeyguardManager.class).isDeviceLocked()) throw new Refusal("locked", "Unlock the fixture device");
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null || !getPackageName().contentEquals(root.getPackageName()))
            throw new Refusal("unsupported_scope", "Only the foreground owned fixture is authorized");
        return root;
    }

    private JSONObject dispatch(JSONObject request) throws Exception {
        String operation = request.getString("operation");
        String target = request.optString("target", getPackageName());
        if (!target.equals(getPackageName())) throw new Refusal("unsupported_scope", "Only the owned fixture is authorized");
        AccessibilityNodeInfo root = fixture();
        JSONObject reply = ok(operation);
        switch (operation) {
            case "applications":
                return reply.put("data", new JSONObject().put("applications", new JSONArray().put(
                    new JSONObject().put("applicationId", getPackageName()).put("name", "MC Android Fixture"))));
            case "windows":
                return reply.put("data", new JSONObject().put("windows", new JSONArray().put(
                    new JSONObject().put("windowId", root.getWindowId()).put("applicationId", getPackageName()))));
            case "snapshot": {
                references.clear();
                observedWindow = root.getWindowId();
                walked = 0;
                JSONArray elements = new JSONArray();
                walk(root, 0, elements, request.optString("query").toLowerCase(java.util.Locale.ROOT), UUID.randomUUID().toString());
                return reply.put("data", new JSONObject().put("elements", elements)
                    .put("truncated", walked >= 1000 || elements.length() >= 400)
                    .put("actionReferenceLifetime", "latest_snapshot_with_live_node_membership"));
            }
            case "action": {
                AccessibilityNodeInfo node = references.get(request.optString("reference"));
                if (node == null || !node.refresh() || !belongs(root, node, new int[]{0}, 0))
                    throw new Refusal("stale_reference", "Control changed; read a fresh tree");
                String view = node.getViewIdResourceName();
                if (view == null || !(view.equals(getPackageName() + ":id/fixture_input") ||
                    view.equals(getPackageName() + ":id/fixture_apply") || view.equals(getPackageName() + ":id/fixture_replace")))
                    throw new Refusal("unsupported_action", "Operator grant/settings controls are not agent actions");
                int action;
                Bundle arguments = new Bundle();
                switch (request.optString("action")) {
                    case "press": action = AccessibilityNodeInfo.ACTION_CLICK; break;
                    case "focus": action = AccessibilityNodeInfo.ACTION_FOCUS; break;
                    case "set_value":
                        action = AccessibilityNodeInfo.ACTION_SET_TEXT;
                        String text = request.getString("text");
                        if (text.length() > 4096) throw new Refusal("unsupported_text_size", "Limit text to 4096 characters");
                        arguments.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
                        break;
                    default: throw new Refusal("unsupported_action", "Only press, focus and set_value are implemented");
                }
                if (!node.getActionList().contains(new AccessibilityNodeInfo.AccessibilityAction(action, null)))
                    throw new Refusal("unsupported_action", "Control does not expose this semantic action");
                references.clear();
                boolean delivered = node.performAction(action, arguments);
                return reply.put("delivery", delivered ? "confirmed" : "unknown")
                    .put("uncertainty", delivered ? "independent_effect_not_checked" : "provider_did_not_confirm");
            }
            case "capture":
                if (Build.VERSION.SDK_INT < 34) throw new Refusal("unsupported_capture", "Window capture needs API 34");
                return reply.put("data", new JSONObject().put("windowId", root.getWindowId()).put("scope", "window"));
            default: throw new Refusal("unsupported_operation", "Operation absent from fixture spike");
        }
    }

    private boolean belongs(AccessibilityNodeInfo root, AccessibilityNodeInfo target, int[] count, int depth) {
        if (root == null || ++count[0] > 1000 || depth > 30) return false;
        if (root.equals(target)) return true;
        for (int n = 0; n < root.getChildCount(); n++) if (belongs(root.getChild(n), target, count, depth + 1)) return true;
        return false;
    }

    private void walk(AccessibilityNodeInfo node, int depth, JSONArray output, String query, String epoch) throws Exception {
        if (node == null || ++walked > 1000 || depth > 30 || output.length() >= 400) return;
        if (!node.isVisibleToUser()) return;
        String label = node.getContentDescription() != null ? node.getContentDescription().toString() :
            node.getText() != null ? node.getText().toString() : "";
        String value = node.isEditable() && node.getText() != null ? node.getText().toString() : "";
        if ((!label.isEmpty() || node.isEditable() || node.isClickable()) &&
            (query.isEmpty() || (label + " " + value).toLowerCase(java.util.Locale.ROOT).contains(query))) {
            String reference = epoch + ":" + output.length();
            references.put(reference, node);
            Rect bounds = new Rect(); node.getBoundsInScreen(bounds);
            JSONArray actions = new JSONArray();
            if (node.isClickable()) actions.put("press");
            if (node.isEditable()) actions.put("set_value");
            output.put(new JSONObject().put("reference", reference).put("depth", depth)
                .put("role", node.isEditable() ? "textfield" : node.isClickable() ? "button" : "text")
                .put("label", label).put("value", value).put("enabled", node.isEnabled())
                .put("focused", node.isFocused()).put("actions", actions)
                .put("bounds", new JSONObject().put("x", bounds.left).put("y", bounds.top)
                    .put("width", bounds.width()).put("height", bounds.height())));
        }
        for (int n = 0; n < node.getChildCount(); n++) walk(node.getChild(n), depth + 1, output, query, epoch);
    }

    private JSONObject capture(JSONObject reply) throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        JSONObject data = reply.getJSONObject("data");
        main.post(() -> {
            if (Build.VERSION.SDK_INT < 34) { done.countDown(); return; }
            takeScreenshotOfWindow(data.optInt("windowId"), getMainExecutor(), new TakeScreenshotCallback() {
                @Override public void onSuccess(ScreenshotResult result) {
                    try {
                        Bitmap hardware = Bitmap.wrapHardwareBuffer(result.getHardwareBuffer(), result.getColorSpace());
                        if (hardware == null) return;
                        Bitmap bitmap = hardware.copy(Bitmap.Config.ARGB_8888, false);
                        hardware.recycle();
                        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                        bitmap.compress(Bitmap.CompressFormat.PNG, 100, bytes);
                        bitmap.recycle();
                        data.put("png", Base64.encodeToString(bytes.toByteArray(), Base64.NO_WRAP));
                    } catch (Exception ignored) { }
                    finally { result.getHardwareBuffer().close(); done.countDown(); }
                }
                @Override public void onFailure(int code) { done.countDown(); }
            });
        });
        if (!done.await(6, TimeUnit.SECONDS) || !data.has("png"))
            return refused("unsupported_capture", "Window capture failed; protected content is not bypassed");
        // Recheck authority after the asynchronous capture before disclosing bytes.
        return onMain(() -> {
            if (token.isEmpty() || SystemClock.elapsedRealtime() >= deadline || owner == null)
                return refused("approval_denied", "Grant ended during capture");
            fixture();
            return reply;
        });
    }
}
