"""One physical provider slot; timeouts never release late worker capacity."""

import threading
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
    def __init__(self, post):
        self.post = post
        self.active = None

    def submit(self, ticket, run, complete):
        # Admission and completion are owned by the coordinator thread.
        if self.active is not None:
            return False
        self.active = ticket

        def worker():
            try:
                value, error = run(ticket), None
            except Exception as failure:
                value, error = None, failure

            def done():
                self.active = None
                complete(value, error)
                return False
            self.post(done)
        threading.Thread(target=worker, daemon=True, name="mc-provider").start()
        return True

    def cancel(self):
        if self.active:
            self.active.cancelled.set()
