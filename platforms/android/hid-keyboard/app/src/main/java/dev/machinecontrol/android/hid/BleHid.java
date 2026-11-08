package dev.machinecontrol.android.hid;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattServer;
import android.bluetooth.BluetoothGattServerCallback;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.bluetooth.le.AdvertiseCallback;
import android.bluetooth.le.AdvertiseData;
import android.bluetooth.le.AdvertiseSettings;
import android.bluetooth.le.BluetoothLeAdvertiser;
import android.content.Context;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.os.ParcelUuid;
import java.util.ArrayDeque;
import java.util.Arrays;
import java.util.Deque;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

/**
 * HID over GATT (HOGP) keyboard and mouse. Hosts that hide phone-class devices
 * from their classic pairing lists, such as ChromeOS, list LE peripherals that
 * advertise the HID service, so an unrooted handheld can pair through the host's
 * own UI. Uses the same report map and report IDs as the classic transport.
 *
 * HID characteristics require an encrypted link, so a host pairs before it can
 * read the report map; Android shows its own consent or code dialog for that.
 */
@SuppressLint("MissingPermission")
final class BleHid {
    interface Events {
        void connected(BluetoothDevice device);
        void disconnected(BluetoothDevice device);
        void leds(int value);
        void protocol(boolean boot);
        void advertising(boolean on, int error);
        /** A new host paired during a pairing window; persist it as the only allowed host. */
        void pinned(String address);
    }

    static final UUID HID_SERVICE = uuid16(0x1812);
    private static final UUID HID_INFORMATION = uuid16(0x2A4A);
    private static final UUID REPORT_MAP = uuid16(0x2A4B);
    private static final UUID HID_CONTROL_POINT = uuid16(0x2A4C);
    private static final UUID REPORT = uuid16(0x2A4D);
    private static final UUID PROTOCOL_MODE = uuid16(0x2A4E);
    private static final UUID BATTERY_SERVICE = uuid16(0x180F);
    private static final UUID BATTERY_LEVEL = uuid16(0x2A19);
    private static final UUID DEVICE_INFORMATION = uuid16(0x180A);
    private static final UUID MANUFACTURER_NAME = uuid16(0x2A29);
    private static final UUID PNP_ID = uuid16(0x2A50);
    private static final UUID CCCD = uuid16(0x2902);
    private static final UUID REPORT_REFERENCE = uuid16(0x2908);
    private static final int INPUT = 1, OUTPUT = 2;
    private static final int NOTIFY_TIMEOUT_MILLIS = 1000;
    private static final int NOT_SENT = -1, LINK_LOST = -2;

    private final Context context;
    private final BluetoothManager manager;
    private final Events events;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Object sendLock = new Object();
    private final Semaphore sent = new Semaphore(0);
    private final Map<String, byte[]> subscriptions = new ConcurrentHashMap<>();
    private final Deque<BluetoothGattService> pending = new ArrayDeque<>();
    private volatile BluetoothGattServer server;
    private BluetoothLeAdvertiser advertiser;
    private volatile BluetoothGattCharacteristic keyboardInput, mouseInput, keyboardOutput, protocolMode;
    private volatile BluetoothDevice host;
    private volatile String pinned;
    private boolean lastPairing;
    private volatile String bondedInWindow;
    private volatile long bondedAt;
    private static final long BOND_GRACE_MILLIS = 30000;
    private volatile boolean lateCallback;
    private volatile boolean ready;
    private volatile boolean failed;
    private volatile boolean advertiseRequested;
    private volatile boolean advertising;
    private volatile boolean running;
    private volatile int notifyStatus = NOT_SENT;
    private volatile byte protocolValue = 1;

    BleHid(Context context, BluetoothManager manager, String pinnedHost, Events events) {
        this.context = context;
        this.manager = manager;
        this.pinned = pinnedHost;
        this.events = events;
    }

    static UUID uuid16(int value) {
        return UUID.fromString(String.format("%08x-0000-1000-8000-00805f9b34fb", value));
    }

    BluetoothDevice host() { return host; }
    boolean ready() { return ready && !failed; }
    boolean advertising() { return advertising; }
    String pinnedHost() { return pinned; }

    /**
     * The pairing window is the handheld's own discoverable period, which needs
     * consent through the system dialog: the only time a host other than the
     * pinned one may claim the handheld, and the only time it advertises
     * discoverably with its name.
     */
    boolean pairing() {
        android.bluetooth.BluetoothAdapter adapter = manager.getAdapter();
        return adapter != null && adapter.getScanMode() == android.bluetooth.BluetoothAdapter.SCAN_MODE_CONNECTABLE_DISCOVERABLE;
    }

    /**
     * A bond that completed during the pairing window: the only way a device
     * other than the pinned host may claim. Already-bonded devices that happen
     * to reconnect while the handheld is discoverable do not qualify.
     */
    synchronized void bonded(BluetoothDevice device) {
        if (!running || !pairing()) return;
        bondedInWindow = device.getAddress();
        bondedAt = SystemClock.elapsedRealtime();
        // The host usually subscribes as soon as the link is encrypted, before
        // Android announces the bond, and does not subscribe again.
        if (subscribedToInput(device)) claim(device);
    }

    private boolean subscribedToInput(BluetoothDevice device) {
        for (BluetoothGattCharacteristic input : new BluetoothGattCharacteristic[] {keyboardInput, mouseInput}) {
            if (input == null) continue;
            byte[] value = subscriptions.get(key(device, input.getDescriptor(CCCD)));
            if (value != null && (value[0] & 1) != 0) return true;
        }
        return false;
    }

    /** Forgets the pinned host; a new one must pair in a window. */
    synchronized void unpin() {
        pinned = null;
        bondedInWindow = null;
        BluetoothDevice connected = host;
        if (connected != null) {
            // The old host stops receiving input now, not at its next disconnect.
            host = null;
            BluetoothGattServer open = server;
            if (open != null) open.cancelConnection(connected);
            notifyStatus = LINK_LOST;
            sent.release();
            events.disconnected(connected);
        }
        refreshAdvertising();
    }

    /** Re-advertises when the window opens or closes; also polled, as the broadcast is not reliable. */
    synchronized void scanModeChanged() {
        boolean open = pairing();
        if (open == lastPairing) return;
        lastPairing = open;
        refreshAdvertising();
    }

    private final Runnable tick = new Runnable() {
        @Override public void run() {
            if (!running) return;
            scanModeChanged();
            main.postDelayed(this, 2000);
        }
    };

    /** Opens the GATT server; services are added one at a time, then advertising starts. */
    synchronized boolean start() {
        if (running) return true;
        BluetoothGattServer open = manager.openGattServer(context, callback);
        if (open == null) return false;
        server = open;
        running = true;
        pending.clear();
        pending.add(hidService());
        pending.add(batteryService());
        pending.add(deviceInformation());
        lastPairing = pairing();
        addNext();
        main.postDelayed(tick, 2000);
        return true;
    }

    synchronized void stop() {
        running = false;
        ready = false;
        main.removeCallbacksAndMessages(null);
        stopAdvertising();
        BluetoothGattServer open = server;
        server = null;
        BluetoothDevice connected = host;
        host = null;
        notifyStatus = LINK_LOST;
        sent.release();
        if (open != null) {
            if (connected != null) open.cancelConnection(connected);
            open.close();
        }
    }

    private synchronized void addNext() {
        if (server == null || failed) return;
        BluetoothGattService next = pending.poll();
        if (next != null) {
            if (!server.addService(next)) fail(-1);
            return;
        }
        ready = true;
        refreshAdvertising();
    }

    private void fail(int error) {
        failed = true;
        events.advertising(false, error);
    }

    /**
     * Advertises only when someone may connect: discoverably (with the name)
     * during a pairing window, otherwise connectably but not discoverably, and
     * only if a pinned host exists that could reconnect.
     */
    private synchronized void refreshAdvertising() {
        stopAdvertising();
        if (!running || !ready || failed || host != null) return;
        boolean discoverable = pairing();
        if (!discoverable && pinned == null) return;
        advertiser = manager.getAdapter().getBluetoothLeAdvertiser();
        if (advertiser == null) {
            events.advertising(false, -2);
            return;
        }
        // Fast while pairing; slow and quiet while waiting for the pinned host.
        AdvertiseSettings.Builder settings = new AdvertiseSettings.Builder()
            .setAdvertiseMode(discoverable ? AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY
                : AdvertiseSettings.ADVERTISE_MODE_LOW_POWER)
            .setTxPowerLevel(discoverable ? AdvertiseSettings.ADVERTISE_TX_POWER_HIGH
                : AdvertiseSettings.ADVERTISE_TX_POWER_MEDIUM)
            .setConnectable(true)
            .setTimeout(0);
        // Before API 34 every connectable advertisement is general discoverable.
        if (Build.VERSION.SDK_INT >= 34) settings.setDiscoverable(discoverable);
        AdvertiseData data = new AdvertiseData.Builder().addServiceUuid(new ParcelUuid(HID_SERVICE)).build();
        // The name rides in the scan response, so long names cannot overflow the
        // 31-byte advertisement, and only while pairing.
        AdvertiseData scanResponse = new AdvertiseData.Builder().setIncludeDeviceName(discoverable).build();
        advertiseRequested = true;
        advertiser.startAdvertising(settings.build(), data, scanResponse, advertiseCallback);
    }

    private synchronized void stopAdvertising() {
        if (advertiser != null && advertiseRequested) {
            try { advertiser.stopAdvertising(advertiseCallback); } catch (IllegalStateException ignored) { }
        }
        advertiseRequested = false;
        advertising = false;
    }

    private final AdvertiseCallback advertiseCallback = new AdvertiseCallback() {
        @Override public void onStartSuccess(AdvertiseSettings settings) {
            synchronized (BleHid.this) {
                // A stop or claim may have raced the start; never leave a stray advertisement.
                if (!advertiseRequested || !running || host != null) {
                    try { advertiser.stopAdvertising(this); } catch (IllegalStateException ignored) { }
                    return;
                }
                advertising = true;
            }
            events.advertising(true, 0);
        }
        @Override public void onStartFailure(int error) {
            synchronized (BleHid.this) {
                if (error != ADVERTISE_FAILED_ALREADY_STARTED) advertising = false;
            }
            events.advertising(false, error);
        }
    };

    /** Whether the host has enabled notifications for the input report with this ID. */
    boolean subscribed(int id) {
        BluetoothDevice connected = host;
        BluetoothGattCharacteristic characteristic =
            id == Reports.KEYBOARD_ID ? keyboardInput : id == Reports.MOUSE_ID ? mouseInput : null;
        if (connected == null || characteristic == null) return false;
        byte[] value = subscriptions.get(key(connected, characteristic.getDescriptor(CCCD)));
        return value != null && (value[0] & 1) != 0;
    }

    /**
     * Sends one input report as a notification and waits until the stack reports
     * it sent. A host that has not subscribed would silently drop it, so that
     * counts as a failure rather than a delivery.
     */
    boolean send(int id, byte[] report) {
        BluetoothGattCharacteristic characteristic =
            id == Reports.KEYBOARD_ID ? keyboardInput : id == Reports.MOUSE_ID ? mouseInput : null;
        if (characteristic == null || !subscribed(id)) return false;
        synchronized (sendLock) {
            BluetoothGattServer open = server;
            BluetoothDevice connected = host;
            if (open == null || connected == null) return false;
            if (lateCallback) {
                // A previous notification timed out; let its late confirmation arrive
                // so it cannot be mistaken for this one's.
                try { sent.tryAcquire(NOTIFY_TIMEOUT_MILLIS, TimeUnit.MILLISECONDS); }
                catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    return false;
                }
                lateCallback = false;
            }
            sent.drainPermits();
            notifyStatus = NOT_SENT;
            boolean queued;
            if (Build.VERSION.SDK_INT >= 33) {
                queued = open.notifyCharacteristicChanged(connected, characteristic, false, report)
                    == android.bluetooth.BluetoothStatusCodes.SUCCESS;
            } else {
                characteristic.setValue(report);
                queued = open.notifyCharacteristicChanged(connected, characteristic, false);
            }
            if (!queued) return false;
            // The stack accepts one outstanding notification; wait so reports stay in order.
            try {
                if (!sent.tryAcquire(NOTIFY_TIMEOUT_MILLIS, TimeUnit.MILLISECONDS)) {
                    lateCallback = true;
                    return false;
                }
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                return false;
            }
            return notifyStatus == BluetoothGatt.GATT_SUCCESS && connected.equals(host);
        }
    }

    private final BluetoothGattServerCallback callback = new BluetoothGattServerCallback() {
        @Override public void onServiceAdded(int status, BluetoothGattService service) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                fail(-3);
                return;
            }
            addNext();
        }

        // Android reports every LE link to this handheld here (watches, laptops using
        // other services), so a connection alone never makes a device the host; nor
        // does a link that outlived an earlier session, whose HID state may be dead.
        @Override public void onConnectionStateChange(BluetoothDevice device, int status, int state) {
            if (state != BluetoothProfile.STATE_DISCONNECTED) return;
            subscriptions.keySet().removeIf(key -> key.startsWith(device.getAddress() + "/"));
            if (device.equals(host)) {
                synchronized (BleHid.this) { host = null; }
                notifyStatus = LINK_LOST;
                sent.release();
                events.disconnected(device);
                refreshAdvertising();
            }
        }

        @Override public void onNotificationSent(BluetoothDevice device, int status) {
            notifyStatus = status;
            sent.release();
        }

        @Override public void onCharacteristicReadRequest(BluetoothDevice device, int requestId, int offset,
                BluetoothGattCharacteristic characteristic) {
            respond(device, requestId, offset, value(characteristic));
        }

        @Override public void onDescriptorReadRequest(BluetoothDevice device, int requestId, int offset,
                BluetoothGattDescriptor descriptor) {
            byte[] value;
            if (REPORT_REFERENCE.equals(descriptor.getUuid())) value = reference(descriptor.getCharacteristic());
            else if (CCCD.equals(descriptor.getUuid()))
                value = subscriptions.getOrDefault(key(device, descriptor), new byte[] {0, 0});
            else value = new byte[0];
            respond(device, requestId, offset, value);
        }

        @Override public void onCharacteristicWriteRequest(BluetoothDevice device, int requestId,
                BluetoothGattCharacteristic characteristic, boolean prepared, boolean responseNeeded,
                int offset, byte[] value) {
            boolean fromHost = device.equals(host);
            if (fromHost && characteristic == keyboardOutput && value != null && value.length > 0) {
                events.leds(value[0] & 0xff);
            } else if (fromHost && characteristic == protocolMode && value != null && value.length > 0) {
                protocolValue = value[0];
                events.protocol(value[0] == 0);
            }
            if (responseNeeded) reply(device, requestId, BluetoothGatt.GATT_SUCCESS, offset, null);
        }

        @Override public void onDescriptorWriteRequest(BluetoothDevice device, int requestId,
                BluetoothGattDescriptor descriptor, boolean prepared, boolean responseNeeded,
                int offset, byte[] value) {
            if (CCCD.equals(descriptor.getUuid()) && value != null && value.length == 2) {
                subscriptions.put(key(device, descriptor), value.clone());
                BluetoothGattCharacteristic owner = descriptor.getCharacteristic();
                if ((value[0] & 1) != 0 && (owner == keyboardInput || owner == mouseInput)) claim(device);
            }
            if (responseNeeded) reply(device, requestId, BluetoothGatt.GATT_SUCCESS, offset, value);
        }
    };

    /**
     * Subscribing to an input report is what makes a device the host: the
     * pinned host, or a device whose bond completed during a pairing window. Any other bonded LE
     * device (a laptop, a watch) can read the report map but never receives input.
     */
    private synchronized void claim(BluetoothDevice device) {
        if (host != null || !running) return;
        String address = device.getAddress();
        boolean known = address.equals(pinned);
        // A new host must claim while the window is open or shortly after its bond.
        boolean fresh = address.equals(bondedInWindow)
            && (pairing() || SystemClock.elapsedRealtime() - bondedAt < BOND_GRACE_MILLIS);
        if (!known && !fresh) return;
        bondedInWindow = null;
        host = device;
        stopAdvertising();
        if (!known) {
            pinned = address;
            events.pinned(address);
        }
        protocolValue = 1;
        events.connected(device);
    }

    private static String key(BluetoothDevice device, BluetoothGattDescriptor descriptor) {
        return device.getAddress() + "/" + System.identityHashCode(descriptor);
    }

    private void respond(BluetoothDevice device, int requestId, int offset, byte[] value) {
        if (offset > value.length) {
            reply(device, requestId, BluetoothGatt.GATT_INVALID_OFFSET, offset, null);
            return;
        }
        reply(device, requestId, BluetoothGatt.GATT_SUCCESS, offset, Arrays.copyOfRange(value, offset, value.length));
    }

    private void reply(BluetoothDevice device, int requestId, int status, int offset, byte[] value) {
        BluetoothGattServer open = server;
        if (open != null) open.sendResponse(device, requestId, status, offset, value);
    }

    private byte[] value(BluetoothGattCharacteristic characteristic) {
        UUID id = characteristic.getUuid();
        if (REPORT_MAP.equals(id)) return Reports.DESCRIPTOR;
        if (HID_INFORMATION.equals(id)) return new byte[] {0x11, 0x01, 0x00, 0x02};
        if (PROTOCOL_MODE.equals(id)) return new byte[] {protocolValue};
        if (BATTERY_LEVEL.equals(id)) return new byte[] {100};
        if (MANUFACTURER_NAME.equals(id)) return "Machine Control".getBytes(java.nio.charset.StandardCharsets.UTF_8);
        // Vendor ID source 1 (Bluetooth SIG), company 0xFFFF (reserved for testing), product 1, version 1.0.
        if (PNP_ID.equals(id)) return new byte[] {0x01, (byte) 0xff, (byte) 0xff, 0x01, 0x00, 0x00, 0x01};
        if (characteristic == keyboardInput) return new byte[Reports.KEYBOARD_SIZE];
        if (characteristic == mouseInput) return new byte[Reports.MOUSE_SIZE];
        if (characteristic == keyboardOutput) return new byte[1];
        return new byte[0];
    }

    private byte[] reference(BluetoothGattCharacteristic characteristic) {
        if (characteristic == keyboardInput) return new byte[] {Reports.KEYBOARD_ID, INPUT};
        if (characteristic == keyboardOutput) return new byte[] {Reports.KEYBOARD_ID, OUTPUT};
        if (characteristic == mouseInput) return new byte[] {Reports.MOUSE_ID, INPUT};
        return new byte[0];
    }

    private BluetoothGattService hidService() {
        BluetoothGattService service = new BluetoothGattService(HID_SERVICE, BluetoothGattService.SERVICE_TYPE_PRIMARY);
        int read = BluetoothGattCharacteristic.PERMISSION_READ_ENCRYPTED;
        int readWrite = read | BluetoothGattCharacteristic.PERMISSION_WRITE_ENCRYPTED;
        service.addCharacteristic(new BluetoothGattCharacteristic(HID_INFORMATION,
            BluetoothGattCharacteristic.PROPERTY_READ, read));
        service.addCharacteristic(new BluetoothGattCharacteristic(REPORT_MAP,
            BluetoothGattCharacteristic.PROPERTY_READ, read));
        service.addCharacteristic(new BluetoothGattCharacteristic(HID_CONTROL_POINT,
            BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE, BluetoothGattCharacteristic.PERMISSION_WRITE_ENCRYPTED));
        protocolMode = new BluetoothGattCharacteristic(PROTOCOL_MODE,
            BluetoothGattCharacteristic.PROPERTY_READ | BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE, readWrite);
        service.addCharacteristic(protocolMode);
        keyboardInput = inputReport(read);
        service.addCharacteristic(keyboardInput);
        keyboardOutput = new BluetoothGattCharacteristic(REPORT, BluetoothGattCharacteristic.PROPERTY_READ
            | BluetoothGattCharacteristic.PROPERTY_WRITE | BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE, readWrite);
        keyboardOutput.addDescriptor(new BluetoothGattDescriptor(REPORT_REFERENCE, BluetoothGattDescriptor.PERMISSION_READ_ENCRYPTED));
        service.addCharacteristic(keyboardOutput);
        mouseInput = inputReport(read);
        service.addCharacteristic(mouseInput);
        return service;
    }

    private static BluetoothGattCharacteristic inputReport(int read) {
        BluetoothGattCharacteristic report = new BluetoothGattCharacteristic(REPORT,
            BluetoothGattCharacteristic.PROPERTY_READ | BluetoothGattCharacteristic.PROPERTY_NOTIFY, read);
        report.addDescriptor(new BluetoothGattDescriptor(CCCD,
            BluetoothGattDescriptor.PERMISSION_READ | BluetoothGattDescriptor.PERMISSION_WRITE_ENCRYPTED));
        report.addDescriptor(new BluetoothGattDescriptor(REPORT_REFERENCE, BluetoothGattDescriptor.PERMISSION_READ_ENCRYPTED));
        return report;
    }

    private static BluetoothGattService batteryService() {
        BluetoothGattService service = new BluetoothGattService(BATTERY_SERVICE, BluetoothGattService.SERVICE_TYPE_PRIMARY);
        BluetoothGattCharacteristic level = new BluetoothGattCharacteristic(BATTERY_LEVEL,
            BluetoothGattCharacteristic.PROPERTY_READ | BluetoothGattCharacteristic.PROPERTY_NOTIFY,
            BluetoothGattCharacteristic.PERMISSION_READ);
        level.addDescriptor(new BluetoothGattDescriptor(CCCD,
            BluetoothGattDescriptor.PERMISSION_READ | BluetoothGattDescriptor.PERMISSION_WRITE));
        service.addCharacteristic(level);
        return service;
    }

    private static BluetoothGattService deviceInformation() {
        BluetoothGattService service = new BluetoothGattService(DEVICE_INFORMATION, BluetoothGattService.SERVICE_TYPE_PRIMARY);
        service.addCharacteristic(new BluetoothGattCharacteristic(MANUFACTURER_NAME,
            BluetoothGattCharacteristic.PROPERTY_READ, BluetoothGattCharacteristic.PERMISSION_READ));
        service.addCharacteristic(new BluetoothGattCharacteristic(PNP_ID,
            BluetoothGattCharacteristic.PROPERTY_READ, BluetoothGattCharacteristic.PERMISSION_READ));
        return service;
    }
}
