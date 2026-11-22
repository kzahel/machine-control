import Clutter from 'gi://Clutter';
import Cogl from 'gi://Cogl';
import GdkPixbuf from 'gi://GdkPixbuf';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Meta from 'gi://Meta';
import Mtk from 'gi://Mtk';
import Shell from 'gi://Shell';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const PATH = '/dev/machinecontrol/CoveredDesktop';
// Installed setup preflight compares this before admitting a locked owner.
const PROTOCOL_VERSION = 1;
const INTERFACE = `<node>
<interface name="dev.machinecontrol.CoveredDesktop1">
    <method name="Begin"><arg type="s" direction="out"/></method>
    <method name="BeginWithin">
        <arg type="u" direction="in"/>
        <arg type="s" direction="out"/>
    </method>
    <method name="Renew">
        <arg type="s" direction="in"/>
        <arg type="u" direction="in"/>
        <arg type="u" direction="out"/>
    </method>
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
    <method name="Input">
        <arg type="s" direction="in"/>
        <arg type="s" direction="in"/>
        <arg type="s" direction="out"/>
    </method>
    <method name="Keep"><arg type="s" direction="in"/></method>
    <method name="End"><arg type="s" direction="in"/></method>
    <method name="Interrupt"><arg type="s" direction="in"/></method>
    <method name="Status">
        <arg type="s" direction="out"/>
        <arg type="s" direction="out"/>
    </method>
    <method name="CheckAuthority">
        <arg type="s" direction="in"/>
        <arg type="s" direction="in"/>
        <arg type="b" direction="out"/>
    </method>
    <method name="CheckLive">
        <arg type="s" direction="in"/>
        <arg type="s" direction="in"/>
        <arg type="b" direction="out"/>
    </method>
    <method name="Version"><arg type="u" direction="out"/></method>
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

// Liveness: the owner keeps the cover only while it renews this often.
const LEASE_US = 2_000_000;
// Hard ceiling: an absolute deadline that only an owner Renew moves, and
// never by more than this from the renewal.
const MAX_COVER_SECONDS = 900;
const LOCKDOWN_SCHEMA = 'org.gnome.desktop.lockdown';
const DISABLE_LOCK_KEY = 'disable-lock-screen';
const COVER_COLOR = [27, 33, 43];
// The native worker bounds its whole GDM conversation and the subsequent
// observation. A cancellation before an observed unlock keeps the cover in
// place while that conversation can still complete. The extension cannot
// observe the end of that conversation; the root broker must guard any
// unlock after this hold (see CheckAuthority).
const PENDING_AUTH_US = 16_000_000;

// Covered input. One owner-only, bounded request runs at a time. Each
// virtual event is registered before it is issued and is adopted only by
// its exact virtual source, type and timestamp. Every other press, motion,
// scroll or touch is local input and ends the cover.
const INPUT_SCHEMA = 'machine-control-covered-input/v1';
const MAX_REQUEST_CHARS = 65_536;
const MAX_TEXT_CODE_POINTS = 4096;
const MAX_SCROLL_STEPS = 1000;
const MAX_COORDINATE = 1_000_000;
const MAX_PID = 2 ** 31 - 1;
const CLICK_INTERVAL_MS = 80;
const DRAG_STEPS = 8;
const MAX_DRAG_STEPS = 64;
const DRAG_DURATION_MS = 200;
const MAX_DRAG_DURATION_MS = 5000;
// Bound for the compositor to adopt everything issued, and for the
// selection read-back before a paste.
const ADOPTION_MS = 1000;
const EVENT_DRAIN_MS = 150;
// Mutter can emit more than one event for one virtual call with the same
// timestamp: a discrete scroll step, or a key with its level modifier.
const DUPLICATE_US = 1_000_000;
// Keep the input filter after the last virtual event so a late press is
// still swallowed rather than reaching the lock screen.
const IN_FLIGHT_US = 1_000_000;
const VIRTUAL_SOURCES = {
    pointer: 'Virtual pointer device for seat',
    keyboard: 'Virtual keyboard device for seat',
};
const BUTTONS = {left: 1, middle: 2, right: 3};
// The aliases and lookup of the Linux portal input route.
const KEY_ALIASES = {
    ctrl: 'Control_L', alt: 'Alt_L', shift: 'Shift_L', super: 'Super_L',
    enter: 'Return', esc: 'Escape', tab: 'Tab', backspace: 'BackSpace',
    delete: 'Delete', space: 'space', left: 'Left', right: 'Right',
    up: 'Up', down: 'Down', home: 'Home', end: 'End',
};
// First-release key allowlist. Shell, compositor and session shortcuts use
// Super, Alt, function, media and power keys; none of those reach a covered
// session. A chord is Control and/or Shift, each at most once, then one
// base key: ASCII printable text or navigation and editing. Escape is bare.
const CHORD_MODIFIERS = [/^Control_[LR]$/, /^Shift_[LR]$/];
const EDITING_KEYS = new Set([
    'Left', 'Right', 'Up', 'Down', 'Home', 'End', 'Page_Up', 'Page_Down',
    'Tab', 'Return', 'KP_Enter', 'BackSpace', 'Delete', 'Insert', 'space',
]);
const PUNCTUATION_KEYS = new Set([
    'exclam', 'quotedbl', 'numbersign', 'dollar', 'percent', 'ampersand', 'apostrophe',
    'parenleft', 'parenright', 'asterisk', 'plus', 'comma', 'minus', 'period', 'slash',
    'colon', 'semicolon', 'less', 'equal', 'greater', 'question', 'at', 'bracketleft',
    'backslash', 'bracketright', 'asciicircum', 'underscore', 'grave', 'braceleft', 'bar',
    'braceright', 'asciitilde',
]);

function chordAllowed(names) {
    const base = names.at(-1);
    const modifiers = names.slice(0, -1);
    const kinds = modifiers.map(name => CHORD_MODIFIERS.findIndex(pattern => pattern.test(name)));
    if (kinds.some(kind => kind < 0) || new Set(kinds).size !== kinds.length)
        return false;
    if (base === 'Escape')
        return modifiers.length === 0;
    return /^[A-Za-z0-9]$/.test(base) || PUNCTUATION_KEYS.has(base) || EDITING_KEYS.has(base);
}
// Application identities that own consent or operator interfaces. Operator
// dialogs are protected by process ancestry from the owner's guard instead.
const PROTECTED_IDENTITY_PREFIXES = ['xdg-desktop-portal'];
const PROTECTED_IDENTITIES = new Set(['org.machine-control.app', 'machine-control']);
// The Linux provider's own ancestry bound.
const MAX_ANCESTRY = 32;
const INPUT_FIELDS = {
    'input.move': ['x', 'y'],
    'input.click': ['x', 'y', 'button', 'count'],
    'input.drag': ['x', 'y', 'x1', 'y1', 'x2', 'y2', 'steps', 'durationMs'],
    'input.scroll': ['x', 'y', 'dx', 'dy', 'deltaX', 'deltaY'],
    'input.key': ['key'],
    'input.text': ['text'],
};
// Refusals before any virtual event was issued. The caller may treat them
// as retry-safe. Text refusals can follow a selection change.
const PRE_EFFECT_REASONS = new Set([
    'gnome_covered_input_unavailable',
    'gnome_covered_input_invalid',
    'gnome_covered_key_refused',
    'gnome_covered_target_shell',
    'gnome_covered_target_protected',
    'gnome_covered_target_mismatch',
    'gnome_covered_text_unavailable',
]);
// Endings after possible delivery: the effect is unknown; never replay.
export const INPUT_REASONS = new Set([
    ...PRE_EFFECT_REASONS,
    'gnome_covered_input_interrupted',
    'gnome_covered_input_unconfirmed',
]);

function inputError(reason) {
    return new Error(reason);
}

function invalid() {
    return inputError('gnome_covered_input_invalid');
}

function integer(value, low, high) {
    if (!Number.isInteger(value) || value < low || value > high)
        throw invalid();
    return value;
}

function coordinate(value) {
    return integer(value, -MAX_COORDINATE, MAX_COORDINATE);
}

// The Linux provider reads `x1` before `x` and `dx` before `deltaX`.
function aliased(request, primary, secondary, fallback) {
    const hasPrimary = Object.hasOwn(request, primary);
    const hasSecondary = Object.hasOwn(request, secondary);
    if (hasPrimary && hasSecondary && request[primary] !== request[secondary])
        throw invalid();
    if (hasPrimary)
        return request[primary];
    return hasSecondary ? request[secondary] : fallback;
}

function parseGuard(value) {
    if (value === undefined)
        return {targetPid: null, protectedPids: new Set()};
    if (value === null || typeof value !== 'object' || Array.isArray(value) ||
        Object.keys(value).some(key => key !== 'targetPid' && key !== 'protectedPids'))
        throw invalid();
    const targetPid = Object.hasOwn(value, 'targetPid') ? integer(value.targetPid, 1, MAX_PID) : null;
    const listed = Object.hasOwn(value, 'protectedPids') ? value.protectedPids : [];
    if (!Array.isArray(listed) || listed.length > 64)
        throw invalid();
    const protectedPids = new Set(listed.map(pid => integer(pid, 1, MAX_PID)));
    if (targetPid !== null && protectedPids.has(targetPid))
        throw inputError('gnome_covered_target_protected');
    return {targetPid, protectedPids};
}

/** Resolve a portal-style chord such as `ctrl+shift+t` to Clutter keyvals. */
export function resolveKey(key) {
    if (typeof key !== 'string' || !key.length || key.length > 128)
        throw invalid();
    const names = key.split('+').map(name => {
        const lower = name.toLowerCase();
        return Object.hasOwn(KEY_ALIASES, lower) ? KEY_ALIASES[lower] : name;
    });
    if (names.length > 5)
        throw invalid();
    const keyvals = names.map(name => {
        if (!/^[A-Za-z0-9_]{1,40}$/.test(name))
            throw invalid();
        const keyval = Clutter[`KEY_${name}`];
        if (!Number.isInteger(keyval) || keyval <= 0 || keyval === 0xFFFFFF)
            throw invalid();
        return keyval;
    });
    if (new Set(keyvals).size !== keyvals.length)
        throw invalid();
    if (!chordAllowed(names))
        throw inputError('gnome_covered_key_refused');
    return {names, keyvals};
}

/**
 * Validate one Input request. The fields are the Linux desktop's own
 * `input.*` fields; `guard` carries the owner's protected and expected
 * application processes and can only make a request stricter.
 */
export function parseInputRequest(json) {
    if (typeof json !== 'string' || !json.length || json.length > MAX_REQUEST_CHARS)
        throw invalid();
    let request;
    try {
        request = JSON.parse(json);
    } catch (_) {
        throw invalid();
    }
    if (request === null || typeof request !== 'object' || Array.isArray(request))
        throw invalid();
    const operation = request.operation;
    if (typeof operation !== 'string' || !Object.hasOwn(INPUT_FIELDS, operation))
        throw invalid();
    const fields = INPUT_FIELDS[operation];
    for (const key of Object.keys(request)) {
        if (key !== 'operation' && key !== 'guard' && !fields.includes(key))
            throw invalid();
    }
    const guard = parseGuard(request.guard);
    const has = name => Object.hasOwn(request, name);
    switch (operation) {
    case 'input.move':
        return {operation, guard, x: coordinate(request.x), y: coordinate(request.y)};
    case 'input.click': {
        const button = has('button') ? request.button : 'left';
        if (typeof button !== 'string' || !Object.hasOwn(BUTTONS, button))
            throw invalid();
        return {
            operation, guard, button,
            x: coordinate(request.x), y: coordinate(request.y),
            count: integer(has('count') ? request.count : 1, 1, 3),
        };
    }
    case 'input.drag':
        return {
            operation, guard,
            x1: coordinate(aliased(request, 'x1', 'x')),
            y1: coordinate(aliased(request, 'y1', 'y')),
            x2: coordinate(request.x2), y2: coordinate(request.y2),
            steps: integer(has('steps') ? request.steps : DRAG_STEPS, 1, MAX_DRAG_STEPS),
            durationMs: integer(has('durationMs') ? request.durationMs : DRAG_DURATION_MS,
                1, MAX_DRAG_DURATION_MS),
        };
    case 'input.scroll': {
        if (has('x') !== has('y'))
            throw invalid();
        const dx = integer(aliased(request, 'dx', 'deltaX', 0), -MAX_SCROLL_STEPS, MAX_SCROLL_STEPS);
        const dy = integer(aliased(request, 'dy', 'deltaY', 0), -MAX_SCROLL_STEPS, MAX_SCROLL_STEPS);
        if (!dx && !dy)
            throw invalid();
        return {
            operation, guard, dx, dy,
            x: has('x') ? coordinate(request.x) : null,
            y: has('y') ? coordinate(request.y) : null,
        };
    }
    case 'input.key':
        return {operation, guard, ...resolveKey(request.key)};
    case 'input.text': {
        const text = request.text;
        if (typeof text !== 'string' || !text.length || text.includes('\0') ||
            [...text].length > MAX_TEXT_CODE_POINTS)
            throw invalid();
        // The portal route's paste chord, delivered by the cover's keyboard.
        return {operation, guard, text, ...resolveKey('ctrl+v')};
    }
    }
    throw invalid();
}

/**
 * Expected virtual events. Matching requires the exact type and timestamp
 * and the single pinned virtual device for that kind of input.
 */
export class VirtualInputQueue {
    constructor() {
        this.pending = [];
        this.duplicates = [];
        this.sources = {pointer: null, keyboard: null};
    }

    get empty() {
        return this.pending.length === 0;
    }

    expect(kind, type, time, multiple = false) {
        this.pending.push({kind, type, time, multiple});
    }

    clear() {
        this.pending = [];
    }

    sourceMatches(kind, device) {
        return !!device && !device.get_device_node() &&
            device.get_device_name() === VIRTUAL_SOURCES[kind] &&
            (this.sources[kind] === null || this.sources[kind] === device);
    }

    adopt(type, time, device, now) {
        this.duplicates = this.duplicates.filter(entry => entry.until > now);
        if (this.duplicates.some(entry => entry.type === type && entry.time === time &&
            this.sourceMatches(entry.kind, device)))
            return true;
        let index = -1;
        for (let position = 0; position < this.pending.length; position++) {
            const entry = this.pending[position];
            if (entry.type === type && entry.time === time) {
                index = position;
                break;
            }
            // Clutter compresses consecutive motion from one device. Only an
            // earlier queued motion may be passed over, by a later motion.
            if (entry.type !== Clutter.EventType.MOTION || type !== Clutter.EventType.MOTION)
                break;
        }
        if (index < 0)
            return false;
        const entry = this.pending[index];
        if (!this.sourceMatches(entry.kind, device))
            return false;
        this.sources[entry.kind] = device;
        this.pending.splice(0, index + 1);
        if (entry.multiple)
            this.duplicates.push({...entry, until: now + DUPLICATE_US});
        return true;
    }
}

function onMonitor(x, y) {
    return Main.layoutManager.monitors.some(monitor =>
        x >= monitor.x && x < monitor.x + monitor.width &&
        y >= monitor.y && y < monitor.y + monitor.height);
}

function shellModal() {
    // An unknown modal count is treated as modal.
    return !Number.isInteger(Main.modalCount) || Main.modalCount > 0;
}

function shellBusy() {
    return shellModal() || !!global.stage.get_grab_actor?.();
}

function parentPid(pid) {
    const [ok, contents] = GLib.file_get_contents(`/proc/${pid}/stat`);
    const fields = ok ? new TextDecoder().decode(contents).split(')').at(-1).trim().split(' ') : [];
    const parent = Number(fields[1]);
    if (!Number.isInteger(parent) || parent < 0)
        throw inputError('gnome_covered_input_unavailable');
    return parent;
}

/** As the Linux provider does, a guarded process protects its descendants. */
function guardedProcess(pid, protectedPids) {
    if (!protectedPids.size)
        return false;
    let ancestor = pid;
    for (let depth = 0; depth < MAX_ANCESTRY && ancestor > 1; depth++) {
        if (protectedPids.has(ancestor))
            return true;
        try {
            ancestor = parentPid(ancestor);
        } catch (_) {
            // The process changed while it was inspected.
            throw inputError('gnome_covered_input_unavailable');
        }
    }
    return false;
}

function windowIdentities(window) {
    return [
        window.get_gtk_application_id?.(), window.get_sandboxed_app_id?.(),
        window.get_wm_class?.(), window.get_wm_class_instance?.(),
    ].filter(value => typeof value === 'string').map(value => value.toLowerCase());
}

function checkWindow(window, guard) {
    const pid = window.get_pid();
    const shellPid = new Gio.Credentials().get_unix_pid();
    if (!Number.isInteger(shellPid) || shellPid <= 0 || !Number.isInteger(pid) || pid <= 0 || pid === shellPid ||
        windowIdentities(window).some(identity => PROTECTED_IDENTITIES.has(identity) ||
            PROTECTED_IDENTITY_PREFIXES.some(prefix => identity.startsWith(prefix))) ||
        guardedProcess(pid, guard.protectedPids))
        throw inputError('gnome_covered_target_protected');
    if (guard.targetPid !== null && pid !== guard.targetPid)
        throw inputError('gnome_covered_target_mismatch');
    return pid;
}

/** The application window the compositor would route a pointer event to. */
function pointerTarget(x, y, guard) {
    if (shellBusy())
        throw inputError('gnome_covered_target_shell');
    let actor = global.stage.get_actor_at_pos(Clutter.PickMode.REACTIVE, x, y);
    while (actor && !(actor instanceof Meta.WindowActor))
        actor = actor.get_parent();
    const window = actor?.get_meta_window();
    if (!window)
        throw inputError('gnome_covered_target_shell');
    return checkWindow(window, guard);
}

/** The application window that would receive keyboard input. */
function keyboardTarget(guard) {
    // No key reaches Shell chrome, a Shell modal or a compositor grab.
    if (shellBusy())
        throw inputError('gnome_covered_target_shell');
    const focus = global.stage.get_key_focus();
    if (focus && focus !== global.stage)
        throw inputError('gnome_covered_target_shell');
    const window = global.display.get_focus_window();
    if (!window)
        throw inputError('gnome_covered_target_shell');
    return checkWindow(window, guard);
}

function knownReason(error, fallback) {
    return INPUT_REASONS.has(error?.message) ? error.message : fallback;
}

let lockdownSettings;

/**
 * GNOME Shell refuses to lock while this lockdown key is set, so the cover
 * could never be removed safely. A missing schema counts as disabled.
 */
function lockScreenDisabled() {
    try {
        if (lockdownSettings === undefined) {
            const schema = Gio.SettingsSchemaSource.get_default()?.lookup(LOCKDOWN_SCHEMA, true);
            lockdownSettings = schema?.has_key(DISABLE_LOCK_KEY)
                ? new Gio.Settings({settings_schema: schema}) : null;
        }
        return !lockdownSettings || lockdownSettings.get_boolean(DISABLE_LOCK_KEY);
    } catch (_) {
        return true;
    }
}

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
    constructor(owner, closed, seconds) {
        this.owner = owner;
        this.closed = closed;
        this.id = GLib.uuid_string_random();
        const now = GLib.get_monotonic_time();
        this.lease = now + LEASE_US;
        this.deadline = now + seconds * 1_000_000;
        this.finishAfter = 0;
        this.phase = 'painting';
        this.reason = '';
        this.unlocked = false;
        this.queue = new VirtualInputQueue();
        this.devices = {pointer: null, keyboard: null};
        this.pressedButtons = new Set();
        this.pressedKeys = [];
        this.sequence = null;
        this.lastTime = 0;
        this.lastIssued = 0;
        this.lastMotion = null;
        // Set once the owner's CheckPixels saw only the cover while locked.
        this.pixelsVerified = false;
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
        this.lockdown = lockdownSettings?.connect(`changed::${DISABLE_LOCK_KEY}`, () => {
            if (lockScreenDisabled())
                this.stop('lock_screen_disabled');
        }) ?? 0;
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
        if (this.phase !== 'covered' || !this.queue.adopt(event.type(), event.get_time_us(),
            event.get_source_device(), GLib.get_monotonic_time()))
            return false;
        this.sequence?.progress?.();
        return true;
    }

    inputReady() {
        return this.liveReady() && !Main.screenShield.locked && !Main.screenShield.active;
    }

    renewable() {
        return this.phase !== 'relocking' && GLib.get_monotonic_time() < this.deadline;
    }

    layoutCurrent() {
        const current = Main.layoutManager.monitors.map(areaKey);
        return current.length > 0 && current.length === this.area.size &&
            current.every(key => this.area.has(key) && this.painted.has(key));
    }

    /**
     * Read-only: the verified cover is still whole and both leases are
     * current. The pixels were verified while locked, before any unlock;
     * locked or unlocked does not matter now.
     */
    liveReady() {
        const now = GLib.get_monotonic_time();
        return this.phase === 'covered' && this.pixelsVerified && !this.coverProblem() &&
            this.layoutCurrent() && now < this.lease && now < this.deadline &&
            !lockScreenDisabled();
    }

    /**
     * Read-only: ready for the one native authentication of this lease.
     * Live, the original session is still locked and no unlock has been
     * observed under this lease.
     */
    authenticationReady() {
        return this.liveReady() && !this.unlocked && !this.busy() &&
            locked() && Main.screenShield.locked && Main.screenShield.active;
    }

    busy() {
        return this.sequence !== null || !this.queue.empty;
    }

    nextTime() {
        this.lastTime = Math.max(GLib.get_monotonic_time(), this.lastTime + 1);
        return this.lastTime;
    }

    device(kind) {
        this.devices[kind] ??= global.stage.context.get_backend().get_default_seat()
            .create_virtual_device(kind === 'pointer'
                ? Clutter.InputDeviceType.POINTER_DEVICE : Clutter.InputDeviceType.KEYBOARD_DEVICE);
        return this.devices[kind];
    }

    issue(kind, type, multiple, notify) {
        const device = this.device(kind);
        const time = this.nextTime();
        // Mutter can consume cleanup releases without routing them through
        // the stage filter. Require independent adoption of each disruptive
        // event. A release still has to be issued successfully.
        if (EVENT_TYPES.has(type))
            this.queue.expect(kind, type, time, multiple);
        this.lastIssued = time;
        if (this.sequence)
            this.sequence.issued++;
        notify(device, time);
    }

    motion(x, y) {
        this.issue('pointer', Clutter.EventType.MOTION, false,
            (device, time) => device.notify_absolute_motion(time, x, y));
        this.lastMotion = [x, y];
        if (this.sequence)
            this.sequence.moved = true;
    }

    moveTo(x, y) {
        const [pointerX, pointerY] = global.get_pointer();
        if (x !== pointerX || y !== pointerY)
            this.motion(x, y);
    }

    button(code, pressed) {
        if (pressed)
            this.pressedButtons.add(code);
        this.issue('pointer', pressed ? Clutter.EventType.BUTTON_PRESS : Clutter.EventType.BUTTON_RELEASE,
            false, (device, time) => device.notify_button(time, code,
                pressed ? Clutter.ButtonState.PRESSED : Clutter.ButtonState.RELEASED));
        if (!pressed)
            this.pressedButtons.delete(code);
    }

    keyval(keyval, pressed) {
        if (pressed)
            this.pressedKeys.push(keyval);
        this.issue('keyboard', pressed ? Clutter.EventType.KEY_PRESS : Clutter.EventType.KEY_RELEASE,
            true, (device, time) => device.notify_keyval(time, keyval,
                pressed ? Clutter.KeyState.PRESSED : Clutter.KeyState.RELEASED));
        const held = this.pressedKeys.lastIndexOf(keyval);
        if (!pressed && held >= 0)
            this.pressedKeys.splice(held, 1);
    }

    chord(keyvals) {
        const pressed = [];
        try {
            for (const keyval of keyvals) {
                this.keyval(keyval, true);
                pressed.push(keyval);
            }
        } finally {
            for (const keyval of pressed.reverse())
                this.keyval(keyval, false);
        }
    }

    scrollStep(direction) {
        this.issue('pointer', Clutter.EventType.SCROLL, true,
            (device, time) => device.notify_discrete_scroll(time, direction, Clutter.ScrollSource.WHEEL));
    }

    /**
     * Release whatever the cover's virtual devices still hold. This is
     * cleanup, never a new action: no motion precedes it, and a release is
     * not local input to the filter.
     */
    releaseAll() {
        const released = this.sequence?.released;
        for (const keyval of this.pressedKeys.splice(0).reverse()) {
            try {
                this.devices.keyboard?.notify_keyval(this.nextTime(), keyval, Clutter.KeyState.RELEASED);
            } catch (_) {
                // Mutter also releases held keys when the device is disposed.
            }
            this.lastIssued = this.lastTime;
            if (released)
                released.keys++;
        }
        for (const code of [...this.pressedButtons]) {
            this.pressedButtons.delete(code);
            if (released) {
                released.buttons.push(code);
                // The last position issued to the compositor, where the
                // button comes up; a drop can happen there.
                released.point = this.lastMotion ?? global.get_pointer().slice(0, 2);
            }
            try {
                this.devices.pointer?.notify_button(this.nextTime(), code, Clutter.ButtonState.RELEASED);
            } catch (_) {
                // As above, for held buttons.
            }
            this.lastIssued = this.lastTime;
        }
    }

    /** Stop a running request where it is, release held input and wake it. */
    abortInput() {
        this.releaseAll();
        const sequence = this.sequence;
        if (!sequence || sequence.aborted)
            return;
        sequence.aborted = true;
        sequence.interrupt?.();
    }

    /**
     * Resolve after `ms`, or when `arm` reports a value. Rejects with
     * `timeoutReason` (when given) or when the request is interrupted.
     */
    waitFor(sequence, ms, timeoutReason = null, arm = null) {
        return new Promise((resolve, reject) => {
            if (sequence.aborted) {
                reject(inputError('gnome_covered_input_interrupted'));
                return;
            }
            let done = false;
            let timer = 0;
            const finish = (remove, reason, value) => {
                if (done)
                    return;
                done = true;
                sequence.timers.delete(timer);
                if (remove)
                    GLib.source_remove(timer);
                sequence.progress = sequence.interrupt = null;
                if (reason)
                    reject(inputError(reason));
                else
                    resolve(value);
            };
            timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
                finish(false, timeoutReason);
                return GLib.SOURCE_REMOVE;
            });
            sequence.timers.add(timer);
            sequence.interrupt = () => finish(true, 'gnome_covered_input_interrupted');
            arm?.(value => finish(true, null, value));
        });
    }

    requireCovered(sequence) {
        if (sequence.aborted || !this.inputReady())
            throw inputError('gnome_covered_input_interrupted');
    }

    /** All target checks happen here, before any virtual event. */
    planInput(request) {
        const {guard} = request;
        switch (request.operation) {
        case 'input.move':
        case 'input.click':
            if (!onMonitor(request.x, request.y))
                throw inputError('gnome_covered_input_unavailable');
            return pointerTarget(request.x, request.y, guard);
        case 'input.drag': {
            for (let step = 0; step <= request.steps; step++) {
                const [x, y] = this.dragPoint(request, step);
                if (!onMonitor(x, y))
                    throw inputError('gnome_covered_input_unavailable');
            }
            // A drop may land in another application, never on protected
            // or Shell surfaces.
            pointerTarget(request.x2, request.y2, {targetPid: null, protectedPids: guard.protectedPids});
            return pointerTarget(request.x1, request.y1, guard);
        }
        case 'input.scroll': {
            const [x, y] = request.x === null ? global.get_pointer() : [request.x, request.y];
            if (!onMonitor(x, y))
                throw inputError('gnome_covered_input_unavailable');
            return pointerTarget(x, y, guard);
        }
        case 'input.key':
        case 'input.text':
            return keyboardTarget(guard);
        }
        throw invalid();
    }

    dragPoint(request, step) {
        return [
            Math.round(request.x1 + (request.x2 - request.x1) * step / request.steps),
            Math.round(request.y1 + (request.y2 - request.y1) * step / request.steps),
        ];
    }

    async perform(request, sequence) {
        switch (request.operation) {
        case 'input.move':
            this.moveTo(request.x, request.y);
            return;
        case 'input.click': {
            const code = BUTTONS[request.button];
            this.moveTo(request.x, request.y);
            for (let index = 0; index < request.count; index++) {
                if (index) {
                    await this.waitFor(sequence, CLICK_INTERVAL_MS);
                    this.requireCovered(sequence);
                }
                this.button(code, true);
                this.button(code, false);
            }
            return;
        }
        case 'input.drag': {
            const interval = Math.max(1, Math.round(request.durationMs / request.steps));
            this.moveTo(request.x1, request.y1);
            this.button(BUTTONS.left, true);
            for (let step = 1; step <= request.steps; step++) {
                await this.waitFor(sequence, interval);
                this.requireCovered(sequence);
                // A window move holds a compositor grab, but a Shell modal
                // such as the overview must not receive the rest of a drag.
                if (shellModal())
                    throw inputError('gnome_covered_input_interrupted');
                const [x, y] = this.dragPoint(request, step);
                this.motion(x, y);
            }
            this.button(BUTTONS.left, false);
            return;
        }
        case 'input.scroll': {
            if (request.x !== null)
                this.moveTo(request.x, request.y);
            // Vertical first, as the portal route does; positive is down/right.
            const axes = [
                [request.dy, Clutter.ScrollDirection.DOWN, Clutter.ScrollDirection.UP],
                [request.dx, Clutter.ScrollDirection.RIGHT, Clutter.ScrollDirection.LEFT],
            ];
            for (const [steps, positive, negative] of axes) {
                for (let step = 0; step < Math.abs(steps); step++)
                    this.scrollStep(steps > 0 ? positive : negative);
            }
            return;
        }
        case 'input.key':
            this.chord(request.keyvals);
            return;
        case 'input.text': {
            const clipboard = St.Clipboard.get_default();
            sequence.clipboard = true;
            clipboard.set_text(St.ClipboardType.CLIPBOARD, request.text);
            const observed = await this.waitFor(sequence, ADOPTION_MS, 'gnome_covered_text_unavailable',
                done => clipboard.get_text(St.ClipboardType.CLIPBOARD, (_clipboard, text) => done(text)));
            if (observed !== request.text)
                throw inputError('gnome_covered_text_unavailable');
            this.requireCovered(sequence);
            // Focus can move while the selection is read back.
            if (keyboardTarget(request.guard) !== sequence.targetPid)
                throw inputError('gnome_covered_target_mismatch');
            this.chord(request.keyvals);
            return;
        }
        }
        throw invalid();
    }

    async runInput(request) {
        if (!this.inputReady() || this.busy())
            throw inputError('gnome_covered_input_unavailable');
        let targetPid;
        try {
            targetPid = this.planInput(request);
        } catch (error) {
            throw inputError(knownReason(error, 'gnome_covered_input_unavailable'));
        }
        const sequence = {
            aborted: false, issued: 0, moved: false, clipboard: false, targetPid,
            released: {buttons: [], keys: 0, point: null},
            timers: new Set(), progress: null, interrupt: null,
        };
        // What the caller can rely on when a request ends after it started.
        const failure = reason => Object.assign(inputError(reason), {
            facts: {
                schema: INPUT_SCHEMA, reason, operation: request.operation,
                issuedEvents: sequence.issued,
                releasedButtons: [...sequence.released.buttons],
                releasedKeys: sequence.released.keys,
                releasePoint: sequence.released.point,
                clipboardTextSideEffect: sequence.clipboard,
                cursorConsequence: sequence.moved ? 'moves' : 'unchanged',
            },
        });
        this.sequence = sequence;
        try {
            await this.perform(request, sequence);
            if (!this.queue.empty) {
                await this.waitFor(sequence, EVENT_DRAIN_MS, null, done => {
                    sequence.progress = () => this.queue.empty && done();
                });
            }
            this.requireCovered(sequence);
            // Mutter's native virtual-device API can deliver input to
            // Wayland even when Clutter never reports the event to this
            // stage filter. Report the actual acknowledgement in each case.
            const adopted = this.queue.empty;
            this.queue.clear();
            const result = {
                schema: INPUT_SCHEMA,
                operation: request.operation,
                delivery: adopted ? 'compositor_adopted' : 'submitted_to_compositor',
                issuedEvents: sequence.issued,
                targetPid,
                coordinateSpace: 'gnome_stage_logical',
                cursorConsequence: sequence.moved ? 'moves' : 'unchanged',
                clipboardTextSideEffect: sequence.clipboard,
            };
            if (request.operation === 'input.text')
                Object.assign(result, {textDelivery: 'clipboard_paste', pasteChord: 'ctrl+v', selectionRestored: false});
            if (request.operation === 'input.drag')
                result.dragRelease = 'destination';
            return result;
        } catch (error) {
            this.releaseAll();
            if (sequence.aborted)
                throw failure('gnome_covered_input_interrupted');
            const reason = knownReason(error, null);
            if (reason === 'gnome_covered_input_unconfirmed')
                throw failure(reason);
            if (!sequence.issued) {
                throw failure(reason && PRE_EFFECT_REASONS.has(reason)
                    ? reason : 'gnome_covered_input_unavailable');
            }
            // Any other failure after a virtual event is not a known state.
            this.stop('virtual_input_failed');
            throw failure('gnome_covered_input_interrupted');
        } finally {
            for (const timer of sequence.timers)
                GLib.source_remove(timer);
            if (this.sequence === sequence)
                this.sequence = null;
        }
    }

    click(x, y) {
        if (!onMonitor(x, y) || this.busy())
            throw inputError('gnome_covered_input_unavailable');
        try {
            pointerTarget(x, y, {targetPid: null, protectedPids: new Set()});
        } catch (error) {
            throw inputError(knownReason(error, 'gnome_covered_input_unavailable'));
        }
        this.moveTo(x, y);
        this.button(BUTTONS.left, true);
        this.button(BUTTONS.left, false);
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
        // No further step runs. Presses already queued in the compositor
        // are no longer adopted and the filter swallows them.
        this.abortInput();
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
            if (now >= this.deadline)
                this.stop('deadline_expired');
            else if (now >= this.lease)
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
        if (now < this.finishAfter || this.sequence || now < this.lastIssued + IN_FLIGHT_US)
            return GLib.SOURCE_CONTINUE;
        Clutter.Event.remove_filter(this.input);
        global.stage.disconnect(this.paint);
        global.stage.disconnect(this.stack);
        Main.layoutManager.disconnect(this.monitors);
        Gio.bus_unwatch_name(this.watcher);
        if (this.lockdown)
            lockdownSettings?.disconnect(this.lockdown);
        this.devices = {pointer: null, keyboard: null};
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

    reject(invocation, reason, message = reason) {
        invocation.return_dbus_error('dev.machinecontrol.CoveredDesktop.Error.' + reason, message);
    }

    BeginAsync(_args, invocation) {
        this.begin(invocation, MAX_COVER_SECONDS);
    }

    BeginWithinAsync([seconds], invocation) {
        if (!Number.isInteger(seconds) || seconds < 1 || seconds > MAX_COVER_SECONDS) {
            this.reject(invocation, 'locked_cover_duration_invalid');
            return;
        }
        this.begin(invocation, seconds);
    }

    begin(invocation, seconds) {
        if (lockScreenDisabled()) {
            this.reject(invocation, 'locked_cover_lock_disabled');
            return;
        }
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
        }, seconds);
        this.cover = cover;
        invocation.return_value(new GLib.Variant('(s)', [cover.id]));
    }

    /**
     * Move the hard ceiling to now + seconds. Never revives an ending or
     * expired cover; an out-of-range request from the owner ends it.
     */
    RenewAsync([id, seconds], invocation) {
        if (!this.owns(id, invocation) || !this.cover.renewable()) {
            this.reject(invocation, 'locked_cover_owner_ended');
            return;
        }
        if (!Number.isInteger(seconds) || seconds < 1 || seconds > MAX_COVER_SECONDS) {
            this.cover.stop('invalid_renewal');
            this.reject(invocation, 'locked_cover_renewal_invalid');
            return;
        }
        this.cover.deadline = GLib.get_monotonic_time() + seconds * 1_000_000;
        invocation.return_value(new GLib.Variant('(u)', [seconds]));
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
        const cover = this.cover;
        // Only a frame taken entirely while locked can verify the cover for
        // authentication.
        const lockedThroughout = () => locked() && !cover.unlocked;
        const lockedAtStart = lockedThroughout();
        const shot = new Shell.Screenshot();
        const stream = Gio.MemoryOutputStream.new_resizable();
        shot.screenshot(false, stream, (source, result) => {
            try {
                const [captured] = source.screenshot_finish(result);
                stream.close(null);
                const opaque = captured && allowed() && this.cover === cover &&
                    frameIsOpaque(stream.steal_as_bytes(), cover.bounds, Main.layoutManager.monitors);
                if (opaque && lockedAtStart && lockedThroughout())
                    cover.pixelsVerified = true;
                report(opaque);
            } catch (_) {
                report(false);
            }
        });
    }

    /**
     * Read-only proof for the credential broker immediately before it
     * dispatches a password: the exact live owner connection and lease
     * token, a verified and healthy cover, and the session still locked
     * with no unlock observed under this lease. Any caller may ask; the
     * answer reveals only whether that exact pair is current.
     */
    CheckAuthorityAsync([owner, token], invocation) {
        const cover = this.exactCover(owner, token);
        invocation.return_value(new GLib.Variant('(b)', [!!cover?.authenticationReady()]));
    }

    /**
     * Read-only proof the broker can hold for the whole task: the exact
     * live owner and token, the verified cover still whole on the same
     * geometry, and both leases current. Locked or unlocked.
     */
    CheckLiveAsync([owner, token], invocation) {
        const cover = this.exactCover(owner, token);
        invocation.return_value(new GLib.Variant('(b)', [!!cover?.liveReady()]));
    }

    exactCover(owner, token) {
        const cover = this.cover;
        return cover && typeof owner === 'string' && typeof token === 'string' &&
            owner.length > 0 && token.length > 0 &&
            cover.owner === owner && cover.id === token ? cover : null;
    }

    VersionAsync(_parameters, invocation) {
        invocation.return_value(new GLib.Variant('(u)', [PROTOCOL_VERSION]));
    }

    async CaptureAsync([id], invocation) {
        const allowed = () => this.owns(id, invocation) && this.cover.inputReady();
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
        if (this.owns(id, invocation) && this.cover.inputReady()) {
            try {
                this.cover.click(x, y);
                invocation.return_value(null);
                return;
            } catch (error) {
                // A refusal before any virtual event keeps the cover. Any
                // other failure may have pressed the button.
                if (!PRE_EFFECT_REASONS.has(error?.message))
                    this.cover.stop('virtual_input_failed');
            }
        }
        this.reject(invocation, 'gnome_covered_input_unavailable');
    }

    InputAsync([id, requestJson], invocation) {
        if (!this.owns(id, invocation) || !this.cover.inputReady()) {
            this.reject(invocation, 'gnome_covered_input_unavailable');
            return;
        }
        let request;
        try {
            request = parseInputRequest(requestJson);
        } catch (error) {
            this.reject(invocation, knownReason(error, 'gnome_covered_input_invalid'));
            return;
        }
        this.cover.runInput(request).then(
            result => invocation.return_value(new GLib.Variant('(s)', [JSON.stringify(result)])),
            error => {
                const reason = knownReason(error, 'gnome_covered_input_interrupted');
                // A request that started reports its facts as JSON; the
                // D-Bus error name stays the reason.
                const facts = error?.facts?.reason === reason ? JSON.stringify(error.facts) : reason;
                this.reject(invocation, reason, facts);
            });
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
