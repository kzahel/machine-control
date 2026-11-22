// Covered GNOME input: request validation, exact virtual-event fencing,
// release and takeover. The real extension runs under Node with stubbed
// GNOME Shell imports; GNOME behavior itself needs the VM qualification.
//
//   node --test platforms/linux/tests/gnome_cover_input.test.mjs

import assert from 'node:assert/strict';
import {register} from 'node:module';
import {test} from 'node:test';

const EXTENSION = new URL('../guests/ubuntu/ui/gnome-cover/extension.js', import.meta.url);

// Map GNOME imports to stub modules backed by globalThis.__coverStub.
const hooks = `
export async function resolve(specifier, context, next) {
    if (specifier.startsWith('gi://') || specifier.startsWith('resource://'))
        return {url: 'stub:' + specifier, shortCircuit: true};
    return next(specifier, context);
}
export async function load(url, context, next) {
    if (!url.startsWith('stub:'))
        return next(url, context);
    const specifier = url.slice(5);
    let source;
    if (specifier.startsWith('gi://'))
        source = 'export default globalThis.__coverStub.gi[' + JSON.stringify(specifier.slice(5)) + '];';
    else if (specifier.endsWith('/extensions/extension.js'))
        source = 'export class Extension {}';
    else
        source = 'export const screenShield = globalThis.__coverStub.screenShield;' +
            'export const layoutManager = globalThis.__coverStub.layoutManager;' +
            'export let modalCount = 0;' +
            'globalThis.__coverStub.setModalCount = value => { modalCount = value; };';
    return {format: 'module', source, shortCircuit: true};
}`;
register(`data:text/javascript,${encodeURIComponent(hooks)}`);

const EventType = {
    KEY_PRESS: 'key-press', KEY_RELEASE: 'key-release', MOTION: 'motion',
    BUTTON_PRESS: 'button-press', BUTTON_RELEASE: 'button-release', SCROLL: 'scroll',
    TOUCH_BEGIN: 'touch-begin', TOUCH_UPDATE: 'touch-update',
};
const PRESSED = 1;
const RELEASED = 0;
// The X keysyms the tests name; Clutter exposes each as KEY_<name>.
const KEYS = {
    Control_L: 0xffe3, Control_R: 0xffe4, Shift_L: 0xffe1, Shift_R: 0xffe2,
    Alt_L: 0xffe9, Meta_L: 0xffe7, Super_L: 0xffeb, ISO_Level3_Shift: 0xfe03,
    Return: 0xff0d, KP_Enter: 0xff8d, Escape: 0xff1b, Tab: 0xff09, BackSpace: 0xff08,
    Delete: 0xffff, Insert: 0xff63, space: 0x20, Left: 0xff51, Right: 0xff53, Up: 0xff52,
    Down: 0xff54, Home: 0xff50, End: 0xff57, Page_Up: 0xff55, Page_Down: 0xff56,
    F1: 0xffbe, F2: 0xffbf, F3: 0xffc0, F4: 0xffc1, F5: 0xffc2, F10: 0xffc7,
    Print: 0xff61, Menu: 0xff67,
    comma: 0x2c, plus: 0x2b, slash: 0x2f, asciitilde: 0x7e,
    XF86Switch_VT_1: 0x1008fe01, XF86PowerOff: 0x1008ff2a, XF86AudioMute: 0x1008ff12,
    ...Object.fromEntries([...'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789']
        .map(character => [character, character.charCodeAt(0)])),
};

const clock = {now: 1_000_000_000};
// Child to parent. The operator (100) owns a dialog (4300); 4242 is the
// application under test.
const processes = new Map([[4242, 1], [100, 1], [4300, 100], [5151, 1], [31, 1], [32, 1], [999, 1]]);
let timers = new Map();
let nextId = 1;
const GLib = {
    PRIORITY_HIGH: -100, PRIORITY_DEFAULT: 0, SOURCE_CONTINUE: true, SOURCE_REMOVE: false,
    get_monotonic_time: () => clock.now,
    uuid_string_random: () => `lease-${nextId++}`,
    timeout_add(_priority, ms, callback) {
        const id = nextId++;
        timers.set(id, {due: clock.now + ms * 1000, interval: ms * 1000, callback});
        return id;
    },
    source_remove(id) {
        if (!timers.delete(id))
            throw new Error(`GLib source ${id} was not attached`);
    },
    // A fixture process table: /proc/PID/stat with its parent PID.
    file_get_contents(path) {
        const pid = Number(/^\/proc\/(\d+)\/stat$/.exec(path)?.[1]);
        if (!processes.has(pid))
            throw new Error('No such process');
        return [true, new TextEncoder().encode(`${pid} (odd) name) S ${processes.get(pid)} 1 1`)];
    },
    Variant: class {
        constructor(signature, value) {
            this.signature = signature;
            this.value = value;
        }
    },
};

const Clutter = {
    EventType,
    InputDeviceType: {POINTER_DEVICE: 'pointer', KEYBOARD_DEVICE: 'keyboard'},
    ButtonState: {PRESSED, RELEASED},
    KeyState: {PRESSED, RELEASED},
    ScrollDirection: {UP: 'up', DOWN: 'down', LEFT: 'left', RIGHT: 'right'},
    ScrollSource: {WHEEL: 'wheel'},
    PickMode: {REACTIVE: 'reactive'},
    EVENT_PROPAGATE: false,
    EVENT_STOP: true,
    Event: {
        add_filter(_stage, filter) {
            state.filter = filter;
            return 11;
        },
        remove_filter() {
            state.filter = null;
        },
    },
    ...Object.fromEntries(Object.entries(KEYS).map(([name, value]) => [`KEY_${name}`, value])),
};

class Widget {
    constructor(properties) {
        Object.assign(this, properties, {x: 0, y: 0, width: 0, height: 0, parent: null, destroyed: false});
    }

    set_position(x, y) {
        this.x = x;
        this.y = y;
    }

    set_size(width, height) {
        this.width = width;
        this.height = height;
    }

    is_mapped() {
        return !this.destroyed;
    }

    get_parent() {
        return this.parent;
    }

    queue_redraw() {}

    destroy() {
        this.destroyed = true;
        global.stage.children = global.stage.children.filter(child => child !== this);
    }
}

const clipboard = {
    text: null,
    set_text(_type, text) {
        this.text = text;
    },
    get_text(_type, callback) {
        const text = this.text;
        setImmediate(() => callback(this, text));
    },
};

class WindowActor {
    constructor(window) {
        this.window = window;
    }

    get_meta_window() {
        return this.window;
    }

    get_parent() {
        return null;
    }
}

const screenShield = {
    locked: true, active: true, lockRequests: 0,
    actor: {is_mapped: () => true},
    lock() {
        this.lockRequests++;
        this.locked = true;
        this.active = true;
    },
};
const layoutManager = {
    monitors: [{x: 0, y: 0, width: 1280, height: 800}],
    connect: () => 21,
    disconnect() {},
};

const state = {filter: null, devices: [], vanished: new Map(), pointer: {x: 5, y: 5}, exposed: false, lockDisabled: false};
const settingsHandlers = new Map();

function frame() {
    const pixels = new Uint8Array(1280 * 800 * 4);
    for (let offset = 0; offset < pixels.length; offset += 4)
        pixels.set([27, 33, 43, 255], offset);
    if (state.exposed)
        pixels.set([200, 200, 200, 255], 4 * (400 * 1280 + 640));
    return {width: 1280, height: 800, n_channels: 4, rowstride: 1280 * 4, get_pixels: () => pixels};
}
globalThis.__coverStub = {
    screenShield, layoutManager,
    gi: {
        Clutter, GLib, Cogl: {},
        // The physical frame CheckPixels reads: the cover colour, or not.
        GdkPixbuf: {PixbufLoader: {new_with_type: () => ({write() {}, close() {}, get_pixbuf: () => frame()})}},
        Shell: {Screenshot: class {
            screenshot(_cursor, _stream, callback) {
                setImmediate(() => callback(this, null));
            }

            screenshot_finish() {
                return [true];
            }
        }},
        GObject: {registerClass: klass => klass},
        Meta: {WindowActor},
        Mtk: {Rectangle: class {}},
        St: {Widget, Clipboard: {get_default: () => clipboard}, ClipboardType: {CLIPBOARD: 0}},
        Gio: {
            Credentials: class {
                get_unix_pid() { return 999; }
            },
            DBus: {session: {}},
            BusNameWatcherFlags: {NONE: 0},
            bus_watch_name_on_connection(_connection, owner, _flags, _appeared, vanished) {
                state.vanished.set(owner, vanished);
                return 31;
            },
            bus_unwatch_name() {},
            DBusExportedObject: {wrapJSObject: () => ({export() {}, unexport() {}})},
            MemoryOutputStream: {new_resizable: () => ({close() {}, steal_as_bytes: () => ({get_data: () => new Uint8Array(0)})})},
            SettingsSchemaSource: {get_default: () => ({lookup: () => ({has_key: () => true})})},
            Settings: class {
                get_boolean(key) {
                    assert.equal(key, 'disable-lock-screen');
                    return state.lockDisabled;
                }

                connect(_signal, handler) {
                    const id = nextId++;
                    settingsHandlers.set(id, handler);
                    return id;
                }

                disconnect(id) {
                    settingsHandlers.delete(id);
                }
            },
        },
    },
};

class VirtualDevice {
    constructor(kind) {
        this.kind = kind;
        this.calls = [];
        this.delivered = 0;
    }

    get_device_name() {
        return `Virtual ${this.kind} device for seat`;
    }

    get_device_node() {
        return null;
    }

    notify_absolute_motion(time, x, y) {
        this.calls.push(['motion', time, x, y]);
        state.pointer = {x, y};
    }

    notify_button(time, button, buttonState) {
        this.calls.push(['button', time, button, buttonState]);
    }

    notify_keyval(time, keyval, keyState) {
        this.calls.push(['key', time, keyval, keyState]);
    }

    notify_discrete_scroll(time, direction, source) {
        this.calls.push(['scroll', time, direction, source]);
    }
}

const physical = {get_device_name: () => 'Fixture Mouse', get_device_node: () => '/dev/input/event7'};
const seat = {
    create_virtual_device(type) {
        const device = new VirtualDevice(type);
        state.devices.push(device);
        return device;
    },
};

function event(type, time, device) {
    return {type: () => type, get_time_us: () => time, get_source_device: () => device};
}

function window(pid, wmClass = 'org.example.Fixture') {
    return {
        get_pid: () => pid, get_wm_class: () => wmClass, get_wm_class_instance: () => null,
        get_gtk_application_id: () => null, get_sandboxed_app_id: () => null,
    };
}

function pickWindow(target) {
    const actor = new WindowActor(target);
    global.stage.pick = () => ({get_parent: () => actor});
}

const flush = () => new Promise(resolve => setImmediate(resolve));

async function advance(ms) {
    const end = clock.now + ms * 1000;
    for (;;) {
        const [id, timer] = [...timers.entries()]
            .filter(([, entry]) => entry.due <= end)
            .sort((left, right) => left[1].due - right[1].due)[0] ?? [];
        if (!timer)
            break;
        clock.now = Math.max(clock.now, timer.due);
        const again = timer.callback();
        if (timers.get(id) === timer) {
            if (again)
                timer.due += timer.interval;
            else
                timers.delete(id);
        }
        await flush();
    }
    clock.now = end;
    await flush();
}

function devicesCalls() {
    return state.devices.flatMap(device => device.calls.map(call => [device.kind, ...call]));
}

// Turn undelivered virtual calls into compositor events, with Mutter's
// same-timestamp companions, and run them through the cover's filter.
function deliver({compress = false} = {}) {
    const verdicts = [];
    for (const device of state.devices) {
        let events = [];
        for (const [kind, time, value, phase] of device.calls.slice(device.delivered)) {
            if (kind === 'motion') {
                events.push(event(EventType.MOTION, time, device));
            } else if (kind === 'button') {
                events.push(event(phase === PRESSED ? EventType.BUTTON_PRESS : EventType.BUTTON_RELEASE, time, device));
            } else if (kind === 'scroll') {
                events.push(event(EventType.SCROLL, time, device), event(EventType.SCROLL, time, device));
            } else {
                const type = phase === PRESSED ? EventType.KEY_PRESS : EventType.KEY_RELEASE;
                const shifted = value === KEYS.A;
                if (shifted && phase === PRESSED)
                    events.push(event(type, time, device));
                events.push(event(type, time, device));
                if (shifted && phase === RELEASED)
                    events.push(event(type, time, device));
            }
        }
        device.delivered = device.calls.length;
        if (compress) {
            events = events.filter((current, index) => !(current.type() === EventType.MOTION &&
                events[index + 1]?.type() === EventType.MOTION));
        }
        for (const current of events)
            verdicts.push(state.filter(current));
    }
    return verdicts;
}

function invocation(sender) {
    const reply = {value: undefined, error: undefined};
    return Object.assign(reply, {
        get_sender: () => sender,
        return_value(value) {
            reply.value = value;
        },
        return_dbus_error(name, message) {
            reply.error = name.split('.').at(-1);
            reply.message = message;
        },
    });
}

const OWNER = ':1.42';
const {default: CoveredDesktop, parseInputRequest, resolveKey, VirtualInputQueue} = await import(EXTENSION.href);

async function coveredSession({unlock = true, within = null} = {}) {
    timers = new Map();
    clock.now += 10_000_000;
    Object.assign(state, {filter: null, devices: [], vanished: new Map(), pointer: {x: 5, y: 5}, exposed: false, lockDisabled: false});
    Object.assign(screenShield, {locked: true, active: true, lockRequests: 0});
    clipboard.text = null;
    globalThis.__coverStub.setModalCount(0);
    globalThis.get_pointer = () => [state.pointer.x, state.pointer.y, 0];
    globalThis.display = {focus: window(4242), get_focus_window() {
        return this.focus;
    }};
    globalThis.stage = {
        children: [], handlers: new Map(), keyFocus: null, grab: null, pick: () => null,
        context: {get_backend: () => ({get_default_seat: () => seat})},
        add_child(actor) {
            this.children.push(actor);
            actor.parent = this;
        },
        get_last_child() {
            return this.children.at(-1);
        },
        set_child_above_sibling(actor) {
            this.children = [...this.children.filter(child => child !== actor), actor];
        },
        connect(name, handler) {
            const id = nextId++;
            this.handlers.set(id, {name, handler});
            return id;
        },
        disconnect(id) {
            this.handlers.delete(id);
        },
        get_key_focus() {
            return this.keyFocus ?? this;
        },
        get_grab_actor() {
            return this.grab;
        },
        get_actor_at_pos(_mode, x, y) {
            return this.pick(x, y);
        },
    };
    pickWindow(window(4242));

    const extension = new CoveredDesktop();
    extension.enable();
    const begin = invocation(OWNER);
    if (within === null)
        extension.BeginAsync([], begin);
    else
        extension.BeginWithinAsync([within], begin);
    const id = begin.value.value[0];
    for (const {name, handler} of global.stage.handlers.values()) {
        if (name === 'after-paint')
            handler(global.stage, {get_layout: area => Object.assign(area, {x: 0, y: 0, width: 1280, height: 800})});
    }
    assert.equal(extension.cover.phase, 'covered');
    const call = (method, args, sender = OWNER) => {
        const reply = invocation(sender);
        extension[`${method}Async`]([id, ...args], reply);
        return reply;
    };
    const input = (request, sender = OWNER) => call('Input', [JSON.stringify(request)], sender);
    const authority = (owner = OWNER, token = id) => {
        const reply = invocation(':1.7');
        extension.CheckAuthorityAsync([owner, token], reply);
        return reply.value.value[0];
    };
    const live = (owner = OWNER, token = id) => {
        const reply = invocation(':1.7');
        extension.CheckLiveAsync([owner, token], reply);
        return reply.value.value[0];
    };
    if (unlock) {
        // The owner verified the locked frame, then native authentication
        // unlocked the same session under the cover.
        const pixels = call('CheckPixels', []);
        await flush();
        assert.equal(pixels.value.value[0], true);
        Object.assign(screenShield, {locked: false, active: false});
        await advance(50);
        assert.equal(extension.cover.unlocked, true);
    }
    return {extension, id, call, input, authority, live};
}

async function verifyPixels(call) {
    const reply = call('CheckPixels', []);
    await flush();
    return reply.value.value[0];
}

function result(reply) {
    assert.equal(reply.error, undefined, `unexpected refusal ${reply.error}`);
    return JSON.parse(reply.value.value[0]);
}

test('requests use the Linux input fields and stay bounded', () => {
    const valid = [
        [{operation: 'input.move', x: 1, y: 2}, {x: 1, y: 2}],
        [{operation: 'input.click', x: 1, y: 2}, {button: 'left', count: 1}],
        [{operation: 'input.click', x: 1, y: 2, button: 'right', count: 3}, {button: 'right', count: 3}],
        [{operation: 'input.drag', x: 1, y: 2, x2: 3, y2: 4}, {x1: 1, y1: 2, steps: 8, durationMs: 200}],
        [{operation: 'input.drag', x1: 1, y1: 2, x: 1, x2: 3, y2: 4, steps: 2, durationMs: 50}, {steps: 2}],
        [{operation: 'input.scroll', deltaY: -3}, {dy: -3, dx: 0, x: null}],
        [{operation: 'input.scroll', x: 4, y: 5, dx: 2}, {x: 4, dx: 2}],
        [{operation: 'input.key', key: 'ctrl+shift+t'}, {names: ['Control_L', 'Shift_L', 't']}],
        [{operation: 'input.text', text: 'héllo'}, {text: 'héllo', names: ['Control_L', 'v']}],
        [{operation: 'input.key', key: 'enter', guard: {targetPid: 7, protectedPids: [8]}}, {}],
    ];
    for (const [request, expected] of valid) {
        const parsed = parseInputRequest(JSON.stringify(request));
        for (const [key, value] of Object.entries(expected))
            assert.deepEqual(parsed[key], value, `${JSON.stringify(request)} ${key}`);
    }
    assert.equal(parseInputRequest(JSON.stringify(valid.at(-1)[0])).guard.protectedPids.has(8), true);

    const invalid = [
        'not json', '[]', 'null', '{}', JSON.stringify({operation: '__proto__'}),
        JSON.stringify({operation: 'input.type', text: 'x'}),
        JSON.stringify({operation: 'input.move', x: 1}),
        JSON.stringify({operation: 'input.move', x: 1.5, y: 2}),
        JSON.stringify({operation: 'input.move', x: '1', y: 2}),
        JSON.stringify({operation: 'input.move', x: 1, y: 2, requestId: 'r'}),
        JSON.stringify({operation: 'input.click', x: 1, y: 2, button: 'back'}),
        JSON.stringify({operation: 'input.click', x: 1, y: 2, button: null}),
        JSON.stringify({operation: 'input.click', x: 1, y: 2, count: 4}),
        JSON.stringify({operation: 'input.drag', x: 1, x1: 2, y: 1, x2: 3, y2: 4}),
        JSON.stringify({operation: 'input.drag', x: 1, y: 1, x2: 3, y2: 4, durationMs: 5001}),
        JSON.stringify({operation: 'input.drag', x: 1, y: 1, x2: 3, y2: 4, steps: 65}),
        JSON.stringify({operation: 'input.scroll', x: 1, dy: 1}),
        JSON.stringify({operation: 'input.scroll', dy: 1001}),
        JSON.stringify({operation: 'input.scroll', dx: 0, dy: 0}),
        JSON.stringify({operation: 'input.text', text: ''}),
        JSON.stringify({operation: 'input.text', text: 'a\u0000b'}),
        JSON.stringify({operation: 'input.text', text: 'x'.repeat(4097)}),
        JSON.stringify({operation: 'input.key', key: 'ctrl+'}),
        JSON.stringify({operation: 'input.key', key: 'NoSuchKey'}),
        JSON.stringify({operation: 'input.key', key: 'a+a'}),
        JSON.stringify({operation: 'input.key', key: 'a+b+c+d+e+f'}),
        JSON.stringify({operation: 'input.key', key: 'constructor'}),
        JSON.stringify({operation: 'input.key', key: 'tab', guard: {targetPid: 0}}),
        JSON.stringify({operation: 'input.key', key: 'tab', guard: {pid: 1}}),
        JSON.stringify({operation: 'input.key', key: 'tab', guard: {protectedPids: 'all'}}),
    ];
    for (const request of invalid)
        assert.throws(() => parseInputRequest(request), {message: 'gnome_covered_input_invalid'}, request);
    // 4096 code points are allowed even when they need surrogate pairs.
    assert.equal(parseInputRequest(JSON.stringify({operation: 'input.text', text: '😀'.repeat(4096)})).text.length, 8192);
    assert.throws(() => parseInputRequest(JSON.stringify({operation: 'input.key', key: 'tab', guard: {targetPid: 3, protectedPids: [3]}})),
        {message: 'gnome_covered_target_protected'});
});

test('keys follow the first-release allowlist', () => {
    const allowed = ['a', 'A', 'z', '7', 'comma', 'asciitilde', 'shift+a', 'ctrl+a', 'ctrl+A',
        'ctrl+shift+t', 'shift+ctrl+t', 'Control_R+Shift_R+slash', 'tab', 'shift+tab', 'ctrl+tab',
        'enter', 'KP_Enter', 'ctrl+enter', 'esc', 'Escape', 'Page_Down', 'ctrl+Home', 'shift+End',
        'backspace', 'ctrl+backspace', 'delete', 'shift+Insert', 'ctrl+Insert', 'space',
        'ctrl+space', 'ctrl+plus', 'left', 'shift+right', 'up', 'down'];
    for (const key of allowed)
        assert.doesNotThrow(() => resolveKey(key), key);
    assert.deepEqual(resolveKey('ctrl+A').keyvals, [KEYS.Control_L, KEYS.A]);

    const refused = ['alt+F4', 'alt+tab', 'alt+F2', 'super', 'super+l', 'Super_L+a', 'Meta_L+a',
        'ISO_Level3_Shift+e', 'ctrl+alt+t', 'ctrl+alt+F1', 'ctrl+alt+delete', 'F5', 'shift+F10',
        'Print', 'ctrl+Print', 'Menu', 'XF86Switch_VT_1', 'XF86PowerOff', 'XF86AudioMute',
        'ctrl', 'shift', 'ctrl+shift', 'a+ctrl', 'a+b', 'ctrl+Control_R+a', 'ctrl+esc',
        'shift+Escape', 'ctrl+F1'];
    for (const key of refused)
        assert.throws(() => resolveKey(key), {message: 'gnome_covered_key_refused'}, key);
});

test('the queue adopts only exact, pinned virtual events', () => {
    const queue = new VirtualInputQueue();
    const pointer = new VirtualDevice('pointer');
    const other = new VirtualDevice('pointer');
    const keyboard = new VirtualDevice('keyboard');
    queue.expect('pointer', EventType.MOTION, 10);
    queue.expect('pointer', EventType.MOTION, 11);
    queue.expect('pointer', EventType.BUTTON_PRESS, 12);
    assert.equal(queue.adopt(EventType.BUTTON_PRESS, 12, pointer, 0), false, 'presses cannot skip motion');
    assert.equal(queue.adopt(EventType.MOTION, 11, physical, 0), false, 'physical source');
    assert.equal(queue.adopt(EventType.MOTION, 11, keyboard, 0), false, 'wrong virtual kind');
    assert.equal(queue.adopt(EventType.MOTION, 11, pointer, 0), true, 'compressed earlier motion');
    assert.equal(queue.adopt(EventType.BUTTON_PRESS, 12, other, 0), false, 'source stays pinned');
    assert.equal(queue.adopt(EventType.BUTTON_PRESS, 12, pointer, 0), true);
    assert.equal(queue.empty, true);
    assert.equal(queue.adopt(EventType.BUTTON_PRESS, 12, pointer, 0), false, 'no replay');

    queue.expect('pointer', EventType.SCROLL, 20, true);
    assert.equal(queue.adopt(EventType.SCROLL, 20, pointer, 0), true);
    assert.equal(queue.adopt(EventType.SCROLL, 20, pointer, 1), true, 'same-timestamp companion');
    assert.equal(queue.adopt(EventType.SCROLL, 21, pointer, 1), false);
    assert.equal(queue.adopt(EventType.SCROLL, 20, pointer, 2_000_000), false, 'companions expire');
});

test('a double click is adopted and reported', async () => {
    const {extension, input} = await coveredSession();
    const reply = input({operation: 'input.click', x: 100, y: 120, count: 2, guard: {targetPid: 4242, protectedPids: [17]}});
    assert.deepEqual(deliver(), [false, false, false]);
    await advance(80);
    assert.deepEqual(deliver(), [false, false]);
    await flush();
    const value = result(reply);
    assert.deepEqual(value, {
        schema: 'machine-control-covered-input/v1', operation: 'input.click',
        delivery: 'compositor_adopted', issuedEvents: 5, targetPid: 4242,
        coordinateSpace: 'gnome_stage_logical', cursorConsequence: 'moves', clipboardTextSideEffect: false,
    });
    assert.deepEqual(devicesCalls().map(([, kind, , value, phase]) => [kind, value, phase]), [
        ['motion', 100, 120], ['button', 1, PRESSED], ['button', 1, RELEASED],
        ['button', 1, PRESSED], ['button', 1, RELEASED],
    ]);
    assert.equal(extension.cover.phase, 'covered');
    assert.equal(extension.cover.busy(), false);
});

test('local input during a drag releases the button and stops every later step', async () => {
    const {extension, input} = await coveredSession();
    const reply = input({operation: 'input.drag', x: 10, y: 10, x2: 90, y2: 10, steps: 4, durationMs: 100});
    deliver();
    await advance(25);
    deliver();
    const before = devicesCalls().length;
    assert.equal(state.filter(event(EventType.MOTION, clock.now, physical)), true, 'physical motion is swallowed');
    await flush();
    assert.equal(reply.error, 'gnome_covered_input_interrupted');
    assert.deepEqual(JSON.parse(reply.message), {
        schema: 'machine-control-covered-input/v1', reason: 'gnome_covered_input_interrupted',
        operation: 'input.drag', issuedEvents: 3, releasedButtons: [1], releasedKeys: 0,
        releasePoint: [30, 10], clipboardTextSideEffect: false, cursorConsequence: 'moves',
    });
    assert.equal(extension.cover.phase, 'relocking');
    assert.equal(extension.cover.reason, 'local_input');
    assert.equal(screenShield.lockRequests, 1);
    const after = devicesCalls().slice(before);
    assert.deepEqual(after.map(([, kind, , value, phase]) => [kind, value, phase]), [['button', 1, RELEASED]]);
    await advance(200);
    assert.equal(devicesCalls().length, before + 1, 'no step after takeover');
    // The release still reaches the application; it is not local input.
    assert.deepEqual(deliver(), [false]);
    assert.equal(extension.cover.reason, 'local_input');
});

test('owner end and lease expiry interrupt a running drag', async () => {
    for (const end of ['End', 'expiry']) {
        const {extension, call, input} = await coveredSession();
        // Steps one second apart: the two-second lease ends mid-drag.
        const reply = input({operation: 'input.drag', x: 10, y: 10, x2: 90, y2: 10, steps: 4, durationMs: 4000});
        deliver();
        if (end === 'End') {
            assert.equal(call('End', []).error, undefined);
        } else {
            await advance(2100);
        }
        await flush();
        assert.equal(reply.error, 'gnome_covered_input_interrupted', end);
        assert.equal(extension.cover.reason, end === 'End' ? 'owner_ended' : 'lease_expired');
        const buttons = devicesCalls().filter(([, kind]) => kind === 'button');
        assert.deepEqual(buttons.map(([, , , , phase]) => phase), [PRESSED, RELEASED], end);
    }
});

test('a press already queued after takeover is swallowed', async () => {
    const {extension, input} = await coveredSession();
    const reply = input({operation: 'input.click', x: 100, y: 120});
    state.filter(event(EventType.KEY_PRESS, clock.now, physical));
    await flush();
    assert.equal(reply.error, 'gnome_covered_input_interrupted');
    assert.deepEqual(deliver(), [true, true, false], 'motion and press stopped, release passes');
    assert.equal(extension.cover.reason, 'local_input');
});

test('keys and scrolls adopt Mutter companion events', async () => {
    const {extension, input} = await coveredSession();
    const key = input({operation: 'input.key', key: 'ctrl+A'});
    assert.deepEqual(deliver(), [false, false, false, false, false, false]);
    await flush();
    assert.equal(result(key).issuedEvents, 4);
    assert.equal(result(key).cursorConsequence, 'unchanged');

    const scroll = input({operation: 'input.scroll', x: 200, y: 200, dy: 2, dx: -1});
    assert.equal(deliver().every(verdict => verdict === false), true);
    await flush();
    assert.equal(result(scroll).issuedEvents, 4);
    assert.deepEqual(devicesCalls().filter(([, kind]) => kind === 'scroll').map(([, , , direction]) => direction),
        ['down', 'down', 'left']);
    assert.equal(extension.cover.phase, 'covered');

    // Clutter compresses consecutive motion from one device.
    const drag = input({operation: 'input.drag', x: 10, y: 10, x2: 50, y2: 50, steps: 2, durationMs: 2});
    await advance(1);
    await advance(1);
    assert.equal(deliver({compress: true}).every(verdict => verdict === false), true);
    await flush();
    assert.equal(result(drag).issuedEvents, 5);
    assert.equal(result(drag).dragRelease, 'destination');
});

test('text pastes the verified selection into the same focused window', async () => {
    const {input} = await coveredSession();
    const reply = input({operation: 'input.text', text: 'covered text', guard: {targetPid: 4242}});
    await flush();
    assert.equal(clipboard.text, 'covered text');
    assert.deepEqual(deliver(), [false, false, false, false]);
    await flush();
    const value = result(reply);
    assert.equal(value.clipboardTextSideEffect, true);
    assert.equal(value.textDelivery, 'clipboard_paste');
    assert.equal(value.pasteChord, 'ctrl+v');
    assert.equal(value.selectionRestored, false);
    assert.deepEqual(devicesCalls().map(([, , , keyval, phase]) => [keyval, phase]), [
        [KEYS.Control_L, PRESSED], [KEYS.v, PRESSED], [KEYS.v, RELEASED], [KEYS.Control_L, RELEASED],
    ]);

    const moved = input({operation: 'input.text', text: 'second'});
    globalThis.display.focus = window(5151);
    await flush();
    assert.equal(moved.error, 'gnome_covered_target_mismatch');
    assert.equal(devicesCalls().length, 4, 'no paste after focus moved');
});

test('unsafe targets refuse before any virtual event and keep the cover', async () => {
    const cases = [
        ['shell modal', () => globalThis.__coverStub.setModalCount(1), {operation: 'input.click', x: 5, y: 5}, 'gnome_covered_target_shell'],
        ['shell grab', () => {
            global.stage.grab = {};
        }, {operation: 'input.move', x: 5, y: 5}, 'gnome_covered_target_shell'],
        ['chrome', () => {
            global.stage.pick = () => ({get_parent: () => null});
        }, {operation: 'input.click', x: 5, y: 5}, 'gnome_covered_target_shell'],
        ['portal', () => pickWindow(window(31, 'xdg-desktop-portal-gnome')), {operation: 'input.click', x: 5, y: 5}, 'gnome_covered_target_protected'],
        ['operator', () => pickWindow(window(32, 'org.machine-control.app')), {operation: 'input.click', x: 5, y: 5}, 'gnome_covered_target_protected'],
        ['shell process', () => pickWindow(window(999)), {operation: 'input.click', x: 5, y: 5}, 'gnome_covered_target_protected'],
        ['guard', () => {}, {operation: 'input.click', x: 5, y: 5, guard: {protectedPids: [4242]}}, 'gnome_covered_target_protected'],
        ['operator dialog', () => pickWindow(window(4300, 'locked-use-dialog.py')),
            {operation: 'input.click', x: 5, y: 5, guard: {protectedPids: [100]}}, 'gnome_covered_target_protected'],
        ['vanished process', () => pickWindow(window(6000)),
            {operation: 'input.click', x: 5, y: 5, guard: {protectedPids: [100]}}, 'gnome_covered_input_unavailable'],
        ['unknown modal count', () => globalThis.__coverStub.setModalCount(undefined),
            {operation: 'input.move', x: 5, y: 5}, 'gnome_covered_target_shell'],
        ['target', () => {}, {operation: 'input.scroll', dy: 1, guard: {targetPid: 7}}, 'gnome_covered_target_mismatch'],
        ['drop', () => {
            global.stage.pick = x => ({get_parent: () => new WindowActor(window(x > 50 ? 31 : 4242, x > 50 ? 'xdg-desktop-portal-gnome' : 'app'))});
        }, {operation: 'input.drag', x: 10, y: 10, x2: 90, y2: 10}, 'gnome_covered_target_protected'],
        ['keyboard shell focus', () => {
            global.stage.keyFocus = {};
        }, {operation: 'input.key', key: 'tab'}, 'gnome_covered_target_shell'],
        ['no focus', () => {
            globalThis.display.focus = null;
        }, {operation: 'input.text', text: 'x'}, 'gnome_covered_target_shell'],
        ['off display', () => {}, {operation: 'input.move', x: 1280, y: 5}, 'gnome_covered_input_unavailable'],
        ['vt', () => {}, {operation: 'input.key', key: 'ctrl+alt+F3'}, 'gnome_covered_key_refused'],
        ['escape to a Shell modal', () => globalThis.__coverStub.setModalCount(1),
            {operation: 'input.key', key: 'esc'}, 'gnome_covered_target_shell'],
        ['locked', () => Object.assign(screenShield, {locked: true, active: true}), {operation: 'input.key', key: 'a'}, 'gnome_covered_input_unavailable'],
        ['owner', () => {}, {operation: 'input.key', key: 'a'}, 'gnome_covered_input_unavailable', ':1.99'],
    ];
    for (const [name, arrange, request, reason, sender] of cases) {
        const {extension, input} = await coveredSession();
        arrange();
        const reply = input(request, sender);
        await flush();
        assert.equal(reply.error, reason, name);
        assert.deepEqual(devicesCalls(), [], name);
        assert.equal(extension.cover.phase, 'covered', name);
        assert.equal(clipboard.text, null, name);
    }

    // The test fixture is not the operator, and a guarded process's
    // unrelated sibling remains usable.
    const fixture = await coveredSession();
    pickWindow(window(4242, 'machine-control-fixture'));
    const click = fixture.input({operation: 'input.click', x: 5, y: 6, guard: {protectedPids: [100]}});
    deliver();
    await flush();
    assert.equal(result(click).targetPid, 4242);
});

test('a Shell modal opening mid-drag ends the drag with a release', async () => {
    const {extension, input} = await coveredSession();
    const reply = input({operation: 'input.drag', x: 10, y: 10, x2: 90, y2: 10, steps: 4, durationMs: 100});
    deliver();
    globalThis.__coverStub.setModalCount(1);
    await advance(25);
    assert.equal(reply.error, 'gnome_covered_input_interrupted');
    const calls = devicesCalls().map(([, kind, , value, phase]) => [kind, value, phase]);
    assert.deepEqual(calls, [['motion', 10, 10], ['button', 1, PRESSED], ['button', 1, RELEASED]]);
    // The release follows an unconfirmed sequence; nothing else is known.
    assert.equal(extension.cover.reason, 'virtual_input_failed');
});

test('submission without a stage event reports what Mutter acknowledged', async () => {
    const {extension, input} = await coveredSession();
    const first = input({operation: 'input.click', x: 100, y: 120});
    const second = input({operation: 'input.key', key: 'a'});
    await flush();
    assert.equal(second.error, 'gnome_covered_input_unavailable');
    await advance(1000);
    assert.equal(result(first).delivery, 'submitted_to_compositor');
    assert.equal(result(first).issuedEvents, 3);
    assert.equal(extension.cover.phase, 'covered');
    assert.equal(extension.cover.busy(), false);
    // A late arrival is no longer expected: it is local input.
    assert.deepEqual(deliver(), [true, true, false]);
    assert.equal(extension.cover.reason, 'local_input');
});

test('Click keeps its reply and refuses unsafe targets without relocking', async () => {
    const {extension, call} = await coveredSession();
    const reply = call('Click', [100, 120]);
    assert.equal(reply.error, undefined);
    assert.equal(reply.value, null);
    assert.deepEqual(deliver(), [false, false, false]);
    assert.equal(extension.cover.phase, 'covered');

    const off = call('Click', [5000, 5]);
    assert.equal(off.error, 'gnome_covered_input_unavailable');
    pickWindow(window(31, 'xdg-desktop-portal-gnome'));
    const portal = call('Click', [100, 120]);
    assert.equal(portal.error, 'gnome_covered_input_unavailable');
    assert.equal(devicesCalls().length, 3);
    assert.equal(extension.cover.phase, 'covered');
});

test('the filter outlives the last virtual event before the cover is removed', async () => {
    const {extension, call, input} = await coveredSession();
    const reply = input({operation: 'input.key', key: 'a'});
    assert.equal(call('End', []).error, undefined);
    await flush();
    assert.equal(reply.error, 'gnome_covered_input_interrupted');
    await advance(500);
    assert.equal(extension.cover?.phase, 'relocking', 'kept while input may be in flight');
    assert.notEqual(state.filter, null);
    await advance(600);
    assert.equal(extension.cover, null);
    assert.equal(state.filter, null);
});

test('Version reports the installed protocol', async () => {
    const {extension} = await coveredSession();
    const reply = invocation(':1.7');
    extension.VersionAsync([], reply);
    assert.equal(reply.value.signature, '(u)');
    assert.deepEqual(reply.value.value, [1]);
});

test('CheckAuthority proves one exact, verified, locked lease and changes nothing', async () => {
    const {extension, id, call, authority} = await coveredSession({unlock: false});
    assert.equal(authority(), false, 'pixels not verified yet');
    state.exposed = true;
    assert.equal(await verifyPixels(call), false);
    assert.equal(authority(), false, 'an exposed frame verifies nothing');
    state.exposed = false;
    assert.equal(await verifyPixels(call), true);
    const lease = extension.cover.lease;
    assert.equal(authority(), true);
    assert.equal(extension.cover.lease, lease, 'read-only: no renewal');
    for (const [owner, token] of [[':1.43', id], [OWNER, `${id}x`], [id, OWNER], ['', ''], [OWNER, id.toUpperCase()]])
        assert.equal(authority(owner, token), false, `${owner} ${token}`);

    // Current health: an unrenewed lease is not current even before the tick.
    clock.now = lease;
    assert.equal(authority(), false, 'expired lease');
    clock.now = lease - 1;
    global.stage.children.push({});
    assert.equal(authority(), false, 'restacked cover');
    global.stage.children.pop();
    assert.equal(authority(), true);
    assert.equal(call('Keep', []).error, undefined);

    // One authentication per lease: after an unlock, never again.
    Object.assign(screenShield, {locked: false, active: false});
    assert.equal(authority(), false, 'unlocked');
    await advance(50);
    Object.assign(screenShield, {locked: true, active: true});
    assert.equal(extension.cover.phase, 'covered');
    assert.equal(authority(), false, 'relocked after an unlock');
    assert.equal(await verifyPixels(call), true);
    assert.equal(authority(), false, 'pixels cannot re-arm a used lease');
});

test('a cover that could have authorised keeps its conservative late-unlock hold', async () => {
    const {extension, call, authority} = await coveredSession({unlock: false});
    assert.equal(await verifyPixels(call), true);
    assert.equal(authority(), true);
    // The owner ends while the native conversation may still be running.
    assert.equal(call('End', []).error, undefined);
    assert.equal(authority(), false);
    await advance(1000);
    // A late unlock inside the hold relocks at once.
    Object.assign(screenShield, {locked: false, active: false});
    await advance(50);
    assert.equal(screenShield.locked, true);
    assert.ok(screenShield.lockRequests >= 1);
    await advance(14_000);
    assert.notEqual(extension.cover, null, 'held for the bounded conversation');
    await advance(2000);
    assert.equal(extension.cover, null);
});

test('the hard ceiling ends a kept cover and only a valid owner Renew moves it', async () => {
    const {extension, call, live} = await coveredSession({within: 3});
    const keep = async ms => {
        for (let elapsed = 0; elapsed < ms; elapsed += 500) {
            assert.equal(call('Keep', []).error, undefined);
            await advance(500);
        }
    };
    const renew = (seconds, sender = OWNER) => call('Renew', [seconds], sender);
    assert.equal(renew(5, ':1.99').error, 'locked_cover_owner_ended', 'only the owner renews');
    await keep(2500);
    assert.equal(live(), true);
    const renewed = renew(4);
    assert.deepEqual(renewed.value.value, [4]);
    assert.equal(renewed.value.signature, '(u)');
    await keep(3500);
    assert.equal(extension.cover.phase, 'covered', 'renewed past the original ceiling');
    // Keep liveness across the ceiling: it never moves the ceiling.
    for (let elapsed = 0; elapsed < 1000; elapsed += 250) {
        call('Keep', []);
        await advance(250);
    }
    assert.equal(extension.cover?.reason ?? extension.reason, 'deadline_expired');
    assert.equal(renew(4).error, 'locked_cover_owner_ended', 'no revival after the ceiling');
});

test('Renew refuses an expired ceiling and ends on an invalid extension', async () => {
    const {extension, call, live} = await coveredSession({within: 2});
    clock.now = extension.cover.deadline;
    assert.equal(live(), false, 'expired before the tick');
    assert.equal(call('Renew', [10]).error, 'locked_cover_owner_ended');
    assert.equal(extension.cover.phase, 'covered', 'refusal changes nothing');

    for (const seconds of [0, 901]) {
        const session = await coveredSession();
        assert.equal(session.call('Renew', [seconds]).error, 'locked_cover_renewal_invalid');
        assert.equal(session.extension.cover.reason, 'invalid_renewal');
        assert.equal(session.extension.cover.phase, 'relocking');
    }
    for (const within of [0, 901]) {
        timers = new Map();
        const extension = new CoveredDesktop();
        extension.enable();
        const reply = invocation(OWNER);
        extension.BeginWithinAsync([within], reply);
        assert.equal(reply.error, 'locked_cover_duration_invalid');
        assert.equal(extension.cover, null);
    }
});

test('CheckLive holds through the unlocked task and fails on any break', async () => {
    const {extension, id, call, live, authority} = await coveredSession();
    assert.equal(live(), true, 'unlocked task');
    assert.equal(authority(), false, 'authority is only before authentication');
    for (const [owner, token] of [[':1.43', id], [OWNER, `${id}x`], [id, OWNER]])
        assert.equal(live(owner, token), false);
    layoutManager.monitors = [{x: 0, y: 0, width: 1920, height: 1080}];
    assert.equal(live(), false, 'geometry changed before its signal');
    layoutManager.monitors = [{x: 0, y: 0, width: 1280, height: 800}];
    assert.equal(live(), true);
    const lease = extension.cover.lease;
    clock.now = lease;
    assert.equal(live(), false, 'Keep lease expired before the tick');
    assert.equal(extension.cover.lease, lease, 'read-only');
    clock.now = lease - 1;
    assert.equal(call('End', []).error, undefined);
    assert.equal(live(), false, 'ending');

    const fresh = await coveredSession({unlock: false});
    assert.equal(fresh.live(), false, 'pixels are verified before the live proof');
});

test('a disabled lock screen refuses Begin and ends a live cover', async () => {
    state.lockDisabled = true;
    timers = new Map();
    const extension = new CoveredDesktop();
    extension.enable();
    Object.assign(screenShield, {locked: true, active: true});
    const refused = invocation(OWNER);
    extension.BeginAsync([], refused);
    assert.equal(refused.error, 'locked_cover_lock_disabled');
    assert.equal(extension.cover, null);

    const session = await coveredSession({unlock: false});
    assert.equal(await verifyPixels(session.call), true);
    assert.equal(session.authority(), true);
    state.lockDisabled = true;
    assert.equal(session.authority(), false);
    assert.equal(session.live(), false);
    for (const handler of settingsHandlers.values())
        handler();
    assert.equal(session.extension.cover.reason, 'lock_screen_disabled');
    // GNOME will not lock, so the cover stays and keeps swallowing input.
    const lock = screenShield.lock;
    screenShield.lock = function () {
        this.lockRequests++;
    };
    Object.assign(screenShield, {locked: false, active: false});
    await advance(30_000);
    assert.equal(session.extension.cover?.phase, 'relocking');
    assert.equal(state.filter(event(EventType.KEY_PRESS, clock.now, physical)), true);
    screenShield.lock = lock;
});
