"""Bound GNOME/logind session observation; never unlocks or prompts."""
import os


def identity(properties, owner, uid):
    """Only the active graphical logon owned by this user is eligible."""
    user = properties.get("User", ())
    stamp = properties.get("TimestampMonotonic")
    if (properties.get("Active") is not True or properties.get("Type") != "wayland"
            or properties.get("Class") != "user" or not user or user[0] != uid
            or not isinstance(properties.get("Id"), str) or not properties["Id"]
            or not isinstance(stamp, int) or isinstance(stamp, bool) or stamp <= 0
            or not isinstance(owner, str) or not owner.startswith(":")):
        return None
    return (properties.get("Id"), stamp, owner)


def inactive_own_logon(properties, uid):
    """This user's graphical logon exists but another session holds the seat."""
    user = properties.get("User", ())
    return (properties.get("Active") is False and properties.get("Class") == "user"
            and bool(user) and user[0] == uid)


def same_logon(a, b):
    """The logind session and its start identify the console. The screensaver
    bus owner is only the lock-state source: a gnome-shell restart replaces it
    without a new login, so it never makes the same login a different one."""
    return a is not None and b is not None and tuple(a[:2]) == tuple(b[:2])


def console_elsewhere(bindings, identity):
    """A complete observation of a different login than any consent binding."""
    return identity is not None and any(
        binding is not None and not same_logon(binding, identity) for binding in bindings)


def observe(bus, completed):
    """`completed(unlocked, locked, identity, elsewhere=False)`; elsewhere is a
    positive observation that another session holds this user's seat."""
    from gi.repository import Gio, GLib
    if os.environ.get("XDG_SESSION_TYPE") != "wayland" or "GNOME" not in os.environ.get("XDG_CURRENT_DESKTOP", ""):
        completed(False, False, None)
        return
    system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def fail():
        completed(False, False, None)

    def call(connection, dest, path, interface, method, params, signature, callback):
        def reply(connection, result, _data):
            try:
                callback(connection.call_finish(result).unpack())
            except (GLib.Error, ValueError, KeyError, TypeError, IndexError):
                fail()
        connection.call(dest, path, interface, method, params, GLib.VariantType(signature),
                        Gio.DBusCallFlags.NONE, 500, None, reply, None)

    def user(value):
        def display(values):
            session_path = values[0]["Display"][1]
            def session(values):
                properties = values[0]
                if inactive_own_logon(properties, os.getuid()):
                    completed(False, False, None, True)
                    return
                def owner(values):
                    key = identity(properties, values[0], os.getuid())
                    if key is None:
                        fail()
                        return
                    def active(values):
                        locked = values[0]
                        if type(locked) is not bool:
                            fail()
                            return
                        completed(not locked, locked, key)
                    call(bus, values[0], "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver", "GetActive", None, "(b)", active)
                call(bus, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "GetNameOwner",
                     GLib.Variant("(s)", ("org.gnome.ScreenSaver",)), "(s)", owner)
            call(system, "org.freedesktop.login1", session_path, "org.freedesktop.DBus.Properties", "GetAll",
                 GLib.Variant("(s)", ("org.freedesktop.login1.Session",)), "(a{sv})", session)
        call(system, "org.freedesktop.login1", value[0], "org.freedesktop.DBus.Properties", "GetAll",
             GLib.Variant("(s)", ("org.freedesktop.login1.User",)), "(a{sv})", display)
    call(system, "org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager", "GetUser",
         GLib.Variant("(u)", (os.getuid(),)), "(o)", user)
