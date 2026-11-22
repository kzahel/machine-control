import Clutter from 'gi://Clutter';
import Cogl from 'gi://Cogl';
import GdkPixbuf from 'gi://GdkPixbuf';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Mtk from 'gi://Mtk';
import Shell from 'gi://Shell';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const PATH = '/dev/machinecontrol/CoveredDesktop';
const INTERFACE = `<node>
<interface name="dev.machinecontrol.CoveredDesktop1">
    <method name="Begin"><arg type="s" direction="out"/></method>
    <method name="Check">
        <arg type="s" direction="in"/>
        <arg type="b" direction="out"/>
    </method>
    <method name="CheckPixels">
        <arg type="s" direction="in"/>
        <arg type="b" direction="out"/>
    </method>
    <method name="Capture">
        <arg type="s" direction="in"/>
        <arg type="ay" direction="out"/>
    </method>
    <method name="Click">
        <arg type="s" direction="in"/>
        <arg type="i" direction="in"/>
        <arg type="i" direction="in"/>
    </method>
    <method name="Keep"><arg type="s" direction="in"/></method>
    <method name="End"><arg type="s" direction="in"/></method>
    <method name="Interrupt"><arg type="s" direction="in"/></method>
    <method name="Status">
        <arg type="s" direction="out"/>
        <arg type="s" direction="out"/>
    </method>
</interface>
</node>`;

const EVENT_TYPES = new Set([
    Clutter.EventType.KEY_PRESS,
    Clutter.EventType.BUTTON_PRESS,
    Clutter.EventType.MOTION,
    Clutter.EventType.SCROLL,
    Clutter.EventType.TOUCH_BEGIN,
    Clutter.EventType.TOUCH_UPDATE,
]);

const LEASE_US = 2_000_000;
const COVER_COLOR = [27, 33, 43];
// The native worker bounds its whole GDM conversation and the subsequent
// observation. A cancellation before an observed unlock keeps the cover in
// place while that conversation can still complete.
const PENDING_AUTH_US = 16_000_000;

function locked() {
    const shield = Main.screenShield;
    return shield?.locked && shield.active && shield.actor.is_mapped();
}

function areaKey({x, y, width, height}) {
    return `${x}:${y}:${width}:${height}`;
}

function boundsOf(monitors) {
    const x = Math.min(...monitors.map(monitor => monitor.x));
    const y = Math.min(...monitors.map(monitor => monitor.y));
    const right = Math.max(...monitors.map(monitor => monitor.x + monitor.width));
    const bottom = Math.max(...monitors.map(monitor => monitor.y + monitor.height));
    return {x, y, width: right - x, height: bottom - y};
}

function frameIsOpaque(bytes, bounds, monitors) {
    const loader = GdkPixbuf.PixbufLoader.new_with_type('png');
    loader.write(bytes.get_data());
    loader.close();
    const image = loader.get_pixbuf();
    if (image.width !== bounds.width || image.height !== bounds.height)
        return false;
    const pixels = image.get_pixels();
    const channels = image.n_channels;
    const stride = image.rowstride;
    for (const monitor of monitors) {
        for (let y = monitor.y - bounds.y; y < monitor.y - bounds.y + monitor.height; y++) {
            const left = y * stride + (monitor.x - bounds.x) * channels;
            const right = left + monitor.width * channels;
            for (let offset = left; offset < right; offset += channels) {
                if (pixels[offset] !== COVER_COLOR[0] || pixels[offset + 1] !== COVER_COLOR[1] ||
                    pixels[offset + 2] !== COVER_COLOR[2] || (channels === 4 && pixels[offset + 3] !== 255))
                    return false;
            }
        }
    }
    return true;
}

const CoverActor = GObject.registerClass(
class CoverActor extends St.Widget {
    vfunc_paint_node(node, context) {
        // Every normal presentation still paints the cover. Only the
        // framebuffer allocated for one authorized capture is excluded.
        if (!this.captureFramebuffer || context.get_framebuffer() !== this.captureFramebuffer)
            super.vfunc_paint_node(node, context);
    }
});

class Cover {
    constructor(owner, closed) {
        this.owner = owner;
        this.closed = closed;
        this.id = GLib.uuid_string_random();
        this.lease = GLib.get_monotonic_time() + LEASE_US;
        this.finishAfter = 0;
        this.phase = 'painting';
        this.reason = '';
        this.unlocked = false;
        this.queuedInput = [];
        this.pointer = null;
        this.pointerSource = null;
        this.painted = new Set();
        this.area = new Set(Main.layoutManager.monitors.map(areaKey));
        this.actor = new CoverActor({
            name: 'machine-control-covered-desktop',
            style: 'background-color: #1b212b;',
            reactive: false,
        });
        this.fitMonitors();
        this.input = Clutter.Event.add_filter(global.stage, event => {
            if (this.takeVirtualInput(event))
                return Clutter.EVENT_PROPAGATE;
            if (EVENT_TYPES.has(event.type())) {
                this.stop('local_input');
                return Clutter.EVENT_STOP;
            }
            return Clutter.EVENT_PROPAGATE;
        });
        global.stage.add_child(this.actor);
        this.stack = global.stage.connect('before-update', () => this.keepOnTop());
        this.paint = global.stage.connect('after-paint', (_stage, view) => {
            if (this.phase !== 'painting' || this.coverProblem())
                return;
            const layout = new Mtk.Rectangle();
            view.get_layout(layout);
            this.painted.add(areaKey(layout));
            if ([...this.area].every(key => this.painted.has(key)))
                this.phase = 'covered';
        });
        this.monitors = Main.layoutManager.connect('monitors-changed', () => {
            this.fitMonitors();
            this.stop('displays_changed');
        });
        this.watcher = Gio.bus_watch_name_on_connection(
            Gio.DBus.session, owner, Gio.BusNameWatcherFlags.NONE,
            null, () => this.stop('owner_disconnected'));
        this.timer = GLib.timeout_add(GLib.PRIORITY_HIGH, 50, () => this.tick());
        this.actor.queue_redraw();
    }

    keepOnTop() {
        if (this.actor.get_parent() === global.stage && global.stage.get_last_child() !== this.actor)
            global.stage.set_child_above_sibling(this.actor, null);
    }

    fitMonitors() {
        const monitors = Main.layoutManager.monitors;
        if (!monitors.length)
            return;
        this.bounds = boundsOf(monitors);
        this.actor.set_position(this.bounds.x, this.bounds.y);
        this.actor.set_size(this.bounds.width, this.bounds.height);
    }

    coverProblem() {
        if (!this.actor.is_mapped())
            return 'cover_unmapped';
        if (global.stage.get_last_child() !== this.actor)
            return 'cover_restacked';
        const {x, y, width, height} = this.bounds;
        if (this.actor.x !== x || this.actor.y !== y ||
            this.actor.width !== width || this.actor.height !== height)
            return 'cover_resized';
        return null;
    }

    takeVirtualInput(event) {
        const pending = this.queuedInput[0];
        if (!pending || this.phase !== 'covered' ||
            event.type() !== pending.type || event.get_time_us() !== pending.time)
            return false;
        const device = event.get_source_device();
        if (!device || device.get_device_node() ||
            device.get_device_name() !== 'Virtual pointer device for seat' ||
            (this.pointerSource && device !== this.pointerSource))
            return false;
        this.pointerSource = device;
        this.queuedInput.shift();
        return true;
    }

    click(x, y) {
        if (!Main.layoutManager.monitors.some(monitor =>
            x >= monitor.x && x < monitor.x + monitor.width &&
            y >= monitor.y && y < monitor.y + monitor.height) || this.queuedInput.length)
            throw new Error('gnome_covered_input_unavailable');
        this.pointer ??= global.stage.context.get_backend().get_default_seat()
            .create_virtual_device(Clutter.InputDeviceType.POINTER_DEVICE);
        const time = GLib.get_monotonic_time();
        const [pointerX, pointerY] = global.get_pointer();
        if (x !== pointerX || y !== pointerY)
            this.queuedInput.push({type: Clutter.EventType.MOTION, time});
        this.queuedInput.push(
            {type: Clutter.EventType.BUTTON_PRESS, time: time + 1},
            {type: Clutter.EventType.BUTTON_RELEASE, time: time + 2},
        );
        if (x !== pointerX || y !== pointerY)
            this.pointer.notify_absolute_motion(time, x, y);
        this.pointer.notify_button(time + 1, 1, Clutter.ButtonState.PRESSED);
        this.pointer.notify_button(time + 2, 1, Clutter.ButtonState.RELEASED);
    }

    async capture() {
        const {width, height} = this.bounds;
        if (width * height > 8_500_000 || this.capturing)
            throw new Error('gnome_covered_capture_unavailable');
        this.capturing = true;
        const stream = Gio.MemoryOutputStream.new_resizable();
        let step = 'setup';
        try {
            const rectangle = new Mtk.Rectangle(this.bounds);
            const context = global.stage.context.get_backend().get_cogl_context();
            step = 'allocate';
            const texture = Cogl.Texture2D.new_with_size(context, width, height);
            const framebuffer = Cogl.Offscreen.new_with_texture(texture);
            framebuffer.allocate();
            step = 'paint';
            this.actor.captureFramebuffer = framebuffer;
            try {
                global.stage.paint_to_framebuffer(
                    framebuffer, rectangle, 1, global.stage.get_color_state(),
                    Clutter.PaintFlag.CLEAR | Clutter.PaintFlag.NO_CURSORS);
            } finally {
                this.actor.captureFramebuffer = null;
            }
            step = 'encode';
            await Shell.Screenshot.composite_to_stream(
                texture, 0, 0, width, height, 1, null, 0, 0, 1, stream);
            stream.close(null);
            const bytes = stream.steal_as_bytes();
            if (bytes.get_size() > 16 * 1024 * 1024)
                throw new Error('gnome_covered_capture_unavailable');
            return bytes;
        } catch (_) {
            throw new Error('gnome_covered_capture_' + step + '_failed');
        } finally {
            this.capturing = false;
        }
    }

    keep() {
        if (this.phase === 'relocking')
            return false;
        this.lease = GLib.get_monotonic_time() + LEASE_US;
        return true;
    }

    stop(reason) {
        if (this.phase === 'relocking')
            return;
        const mayHaveAuthenticated = this.phase === 'covered' && !this.unlocked;
        this.phase = 'relocking';
        this.reason = reason;
        this.finishAfter = GLib.get_monotonic_time() +
            (mayHaveAuthenticated ? PENDING_AUTH_US : 0);
        if (!locked())
            Main.screenShield.lock(false);
    }

    tick() {
        const now = GLib.get_monotonic_time();
        const shield = Main.screenShield;
        if (!shield.locked && !shield.active)
            this.unlocked = true;
        if (this.phase !== 'relocking') {
            if (now >= this.lease)
                this.stop('lease_expired');
            else if (this.phase === 'covered') {
                this.keepOnTop();
                const problem = this.coverProblem();
                if (problem)
                    this.stop(problem);
            }
        }
        if (this.phase !== 'relocking')
            return GLib.SOURCE_CONTINUE;
        if (!locked()) {
            if (!shield.locked && !shield.active)
                shield.lock(false);
            return GLib.SOURCE_CONTINUE;
        }
        if (now < this.finishAfter)
            return GLib.SOURCE_CONTINUE;
        Clutter.Event.remove_filter(this.input);
        global.stage.disconnect(this.paint);
        global.stage.disconnect(this.stack);
        Main.layoutManager.disconnect(this.monitors);
        Gio.bus_unwatch_name(this.watcher);
        this.pointer = null;
        this.actor.destroy();
        this.closed(this.reason);
        return GLib.SOURCE_REMOVE;
    }
}

export default class CoveredDesktopExtension extends Extension {
    enable() {
        this.cover ??= null;
        this.reason ??= '';
        this.exported = Gio.DBusExportedObject.wrapJSObject(INTERFACE, this);
        this.exported.export(Gio.DBus.session, PATH);
    }

    disable() {
        this.exported?.unexport();
        this.exported = null;
        // Keep the compositor resources alive through the native relock even
        // when the extension is turned off.
        this.cover?.stop('extension_disabled');
    }

    reject(invocation, reason) {
        invocation.return_dbus_error('dev.machinecontrol.CoveredDesktop.Error.' + reason, reason);
    }

    BeginAsync(_args, invocation) {
        if (this.cover || !locked() || !Main.layoutManager.monitors.length ||
            typeof Clutter.Event.add_filter !== 'function') {
            this.reject(invocation, 'locked_cover_unavailable');
            return;
        }
        const cover = new Cover(invocation.get_sender(), reason => {
            if (this.cover === cover) {
                this.reason = reason;
                this.cover = null;
            }
        });
        this.cover = cover;
        invocation.return_value(new GLib.Variant('(s)', [cover.id]));
    }

    owns(id, invocation) {
        return this.cover?.owner === invocation.get_sender() && this.cover.id === id;
    }

    CheckAsync([id], invocation) {
        const safe = this.owns(id, invocation) &&
            this.cover.phase === 'covered' && !this.cover.coverProblem();
        invocation.return_value(new GLib.Variant('(b)', [safe]));
    }

    CheckPixelsAsync([id], invocation) {
        const allowed = () => this.owns(id, invocation) &&
            this.cover.phase === 'covered' && !this.cover.coverProblem();
        const report = value => invocation.return_value(new GLib.Variant('(b)', [value]));
        if (!allowed()) {
            report(false);
            return;
        }
        const shot = new Shell.Screenshot();
        const stream = Gio.MemoryOutputStream.new_resizable();
        shot.screenshot(false, stream, (source, result) => {
            try {
                const [captured] = source.screenshot_finish(result);
                stream.close(null);
                report(captured && allowed() &&
                    frameIsOpaque(stream.steal_as_bytes(), this.cover.bounds, Main.layoutManager.monitors));
            } catch (_) {
                report(false);
            }
        });
    }

    async CaptureAsync([id], invocation) {
        const allowed = () => this.owns(id, invocation) &&
            this.cover.phase === 'covered' && !this.cover.coverProblem() &&
            !Main.screenShield.locked && !Main.screenShield.active;
        try {
            if (allowed()) {
                const bytes = await this.cover.capture();
                if (allowed()) {
                    invocation.return_value(new GLib.Variant('(ay)', [bytes.get_data()]));
                    return;
                }
            }
        } catch (error) {
            if (/^gnome_covered_capture_(setup|allocate|paint|encode)_failed$/.test(error.message)) {
                this.reject(invocation, error.message);
                return;
            }
        }
        this.reject(invocation, 'gnome_covered_capture_unavailable');
    }

    ClickAsync([id, x, y], invocation) {
        if (this.owns(id, invocation) && this.cover.phase === 'covered' &&
            !this.cover.coverProblem() && !Main.screenShield.locked && !Main.screenShield.active) {
            try {
                this.cover.click(x, y);
                invocation.return_value(null);
                return;
            } catch (_) {
                this.cover.stop('virtual_input_failed');
            }
        }
        this.reject(invocation, 'gnome_covered_input_unavailable');
    }

    KeepAsync([id], invocation) {
        if (this.owns(id, invocation) && this.cover.keep())
            invocation.return_value(null);
        else
            this.reject(invocation, 'locked_cover_owner_ended');
    }

    EndAsync([id], invocation) {
        if (this.owns(id, invocation)) {
            this.cover.stop('owner_ended');
            invocation.return_value(null);
        } else {
            this.reject(invocation, 'locked_cover_owner_ended');
        }
    }

    InterruptAsync([id], invocation) {
        if (this.owns(id, invocation)) {
            this.cover.stop('local_input');
            invocation.return_value(null);
        } else {
            this.reject(invocation, 'locked_cover_owner_ended');
        }
    }

    Status() {
        return [this.cover?.phase ?? 'inactive', this.cover?.reason ?? this.reason];
    }
}
