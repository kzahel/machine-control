"""One physical provider slot; timeouts never release late worker capacity."""

import threading
import queue
import time


class Cancelled(Exception):
    pass


class Ticket:
    def __init__(self, generation, expires=None, timeout=20):
        self.generation = generation
        self.expires = expires
        self.deadline = time.monotonic() + timeout
        self.cancelled = threading.Event()
        self.dispatched = False

    def check(self):
        now = time.monotonic()
        if self.cancelled.is_set() or now >= self.deadline or (
                self.expires is not None and now >= self.expires):
            raise Cancelled("Authority changed or operation deadline expired")

    def effect(self):
        self.check()
        # Once crossed, cancellation cannot prove that a native call had no effect.
        self.dispatched = True


class Work:
    def __init__(self, post, setup=lambda: None, pump=lambda: None):
        self.post = post
        self.active = None
        self.queue = queue.Queue(maxsize=1)
        self.setup = setup
        self.pump = pump
        self.thread = None

    def submit(self, ticket, run, complete):
        # Admission and completion are owned by the coordinator thread.
        if self.active is not None:
            return False
        self.active = ticket
        if self.thread is None:
            self.thread = threading.Thread(target=self.worker, daemon=True, name="mc-provider")
            self.thread.start()
        self.queue.put_nowait((ticket, run, complete))
        return True

    def worker(self):
        setup_error = None
        try:
            self.setup()
        except Exception as failure:
            setup_error = failure
        while True:
            self.pump()
            try:
                ticket, run, complete = self.queue.get(timeout=.02)
            except queue.Empty:
                continue
            try:
                if setup_error:
                    raise setup_error
                value, error = run(ticket), None
            except Exception as failure:
                value, error = None, failure

            def done(value=value, error=error, complete=complete):
                self.active = None
                complete(value, error)
                return False
            self.post(done)

    def cancel(self):
        if self.active:
            self.active.cancelled.set()
