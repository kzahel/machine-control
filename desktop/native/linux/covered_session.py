"""Own a covered GNOME console for one already-admitted Desktop task."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from gnome_cover import GnomeCover
from gnome_unlock import GnomeUnlock, UnlockRefused


@dataclass
class Renewal:
    until: float
    finished: threading.Event = field(default_factory=threading.Event)
    granted: bool = False
    sent: int = 0


class CoveredSession:
    def __init__(self, identity, owner_alive, authenticate, changed, until, *, native=GnomeUnlock, cover=GnomeCover):
        self.identity = tuple(identity[:2])
        self.owner_alive = owner_alive
        self.authenticate = authenticate
        self.changed = changed
        self.native = native
        self.cover_factory = cover
        self.cover = None
        self.active = threading.Event()
        self.cancelled = threading.Event()
        self.finished = threading.Event()
        self.deadline = 0.0
        self.until = until
        self.unlocked = False
        self.reason = None
        self.relock_verified = False
        self.local_input = False
        self.renewal = None

    def start(self):
        self.pulse()
        threading.Thread(target=self.run, daemon=True, name="mc-covered-console").start()

    def pulse(self):
        # The operator coordinator must keep proving the exact task's authority.
        # Losing that process or its ability to check policy expires the lease.
        if not self.cancelled.is_set():
            self.deadline = time.monotonic() + 2.5

    def permitted(self):
        return (not self.cancelled.is_set() and time.monotonic() < min(self.deadline, self.until)
                and self.owner_alive())

    def stop(self):
        self.active.clear()
        self.cancelled.set()

    def require_active(self):
        if not self.active.is_set() or not self.permitted() or not self.cover.covered():
            raise UnlockRefused("locked_use_guard_failed")
        return self.cover

    def request_renewal(self, until):
        if not self.active.is_set() or not self.permitted() or self.renewal is not None:
            raise UnlockRefused("control_renewal_unavailable")
        self.renewal = renewal = Renewal(until)
        return renewal

    @staticmethod
    def remaining(until):
        seconds = min(900, int(until - time.monotonic()))
        if seconds < 1:
            raise UnlockRefused("locked_guard_deadline")
        return seconds

    def maintain(self, client, provider, console):
        keep = 0.0
        activation_limit = time.monotonic() + 17
        while self.permitted():
            now = time.monotonic()
            if not self.unlocked and now >= activation_limit:
                raise UnlockRefused("gnome_authentication_timeout")
            if now >= keep:
                if not self.cover.covered():
                    raise UnlockRefused("locked_use_guard_failed")
                client.keep()
                keep = now + .3
            renewal = self.renewal
            if renewal is not None and not renewal.sent:
                renewal.sent = self.remaining(renewal.until)
                client.renew(renewal.sent)
            reply = client.next(time.monotonic() + .15)
            if reply is None:
                continue
            event = reply.get("event")
            if event in ("accepted", "submitted"):
                continue
            if event == "unlocked" and not self.unlocked:
                observed = provider.observe()
                if (observed.console != console or not observed.unlocked or not self.cover.covered()
                        or not self.cover.opaque_frame()):
                    raise UnlockRefused("gnome_cover_not_opaque")
                self.unlocked = True
                self.active.set()
                self.changed()
                continue
            if event == "renewed" and renewal is not None and reply.get("deadlineSeconds") == renewal.sent:
                self.cover.extend(self.remaining(renewal.until))
                self.until = renewal.until
                self.renewal = None
                renewal.granted = True
                renewal.finished.set()
                continue
            if event == "ended" or reply.get("accepted") is False:
                reason = reply.get("errorCode") or "locked_use_guard_failed"
                self.local_input |= reason == "locked_local_input"
                raise UnlockRefused(reason)
            raise UnlockRefused("locked_service_unavailable")

    @staticmethod
    def end_authentication(client):
        # The broker is an independent watcher of the bound native session.
        # Keep the peer open long enough for it to reap the GDM attempt.
        try:
            client.end()
            deadline = time.monotonic() + 18
            while time.monotonic() < deadline:
                reply = client.next(deadline)
                if reply is None or reply.get("event") == "ended":
                    return
        except Exception:
            # Release the socket even if the broker is gone. The compositor's
            # independent coverage and relock path still runs to completion.
            pass
        finally:
            client.close()

    def run(self):
        client = None
        try:
            provider = self.native()
            state = provider.observe()
            console = state.console
            if not state.locked or (console.session_id, console.started) != self.identity:
                raise UnlockRefused("gnome_locked_console_changed")
            self.cover = self.cover_factory(provider, console, permitted=self.permitted)
            self.cover.open(self.remaining(self.until))
            if not self.cover.opaque_frame():
                raise UnlockRefused("gnome_cover_not_opaque")
            if not self.cover.covered():
                raise UnlockRefused("locked_use_guard_failed")
            client = self.authenticate(console, self.cover, self.remaining(self.until))
            self.maintain(client, provider, console)
        except UnlockRefused as error:
            self.reason = str(error)
        except Exception:
            self.reason = "locked_use_guard_failed"
        finally:
            self.stop()
            if self.renewal is not None:
                self.renewal.finished.set()
            try:
                if self.cover is not None:
                    self.changed()
                    self.cover.close()
                if client is not None:
                    self.end_authentication(client)
                if self.cover is not None and self.cover.begin_attempted:
                    self.verify_relock(provider, console)
                self.relock_verified = True
            except Exception:
                self.reason = "gnome_relock_unverified"
            finally:
                self.finished.set()
                self.changed()

    def verify_relock(self, provider, console):
        # During interrupted GDM authentication the Shell keeps the cover
        # through a native settle window. The old LockedHint alone is insufficient.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            state = provider.observe()
            if state.console != console:
                raise UnlockRefused("gnome_locked_console_changed")
            phase, reason = self.cover.status()
            self.local_input |= reason == "local_input"
            if state.locked and phase == "inactive":
                return
            time.sleep(0.1)
        raise UnlockRefused("gnome_relock_unverified")
