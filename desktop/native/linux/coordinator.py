"""Private coordinator context; AT-SPI owns the process default context."""
from gi.repository import GLib


class Coordinator:
    def __init__(self):
        self.context = GLib.MainContext.new()
        self.context.push_thread_default()
        self.loop = GLib.MainLoop.new(self.context, False)

    def attach(self, source, callback, *args):
        source.set_callback(lambda *_: callback(*args))
        return source.attach(self.context)

    def post(self, callback, *args):
        return self.attach(GLib.idle_source_new(), callback, *args)

    def timer(self, milliseconds, callback):
        return self.attach(GLib.timeout_source_new(milliseconds), callback)

    def remove(self, identifier):
        source = self.context.find_source_by_id(identifier)
        if source:
            source.destroy()

    def signal(self, signum, callback):
        return self.attach(GLib.unix_signal_source_new(signum), callback)
