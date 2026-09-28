"""Bounded subprocess trees for the common scoped runner (stdlib only).

POSIX children share a new process group. Windows children enter a Job Object
before the gate opens, so the workload cannot start outside the job. This is
cleanup for cooperative tasks, not containment against a same-user shell.
"""

import ctypes
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


class WindowsJob:
    def __init__(self):
        from ctypes import wintypes as w

        class Basic(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", w.DWORD), ("min_ws", ctypes.c_size_t),
                ("max_ws", ctypes.c_size_t), ("active_limit", w.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", w.DWORD),
                ("scheduling", w.DWORD),
            ]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in (
                "read_ops", "write_ops", "other_ops", "read", "write", "other"
            )]

        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO)] + [
                (name, ctypes.c_size_t) for name in (
                    "process_memory", "job_memory", "peak_process", "peak_job"
                )
            ]

        class Accounting(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_int64) for name in
                ("user_time", "kernel_time", "period_user", "period_kernel")
            ] + [(name, w.DWORD) for name in
                 ("page_faults", "total", "active", "terminated")]

        self.accounting_type = Accounting
        self.limits_type = Extended
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            "SetInformationJobObject": (
                [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL
            ),
            "OpenProcess": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
            "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
            "QueryInformationJobObject": (
                [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD,
                 ctypes.c_void_p], w.BOOL
            ),
            "CloseHandle": ([w.HANDLE], w.BOOL),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.api, name)
            fn.argtypes, fn.restype = args, result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def assign(self, pid):
        process = self.api.OpenProcess(0x0101, False, pid)  # SET_QUOTA | TERMINATE
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.api.AssignProcessToJobObject(self.handle, process):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.api.CloseHandle(process)

    def terminate(self):
        if not self.api.TerminateJobObject(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())
        deadline = time.monotonic() + 5
        while True:
            counts = self.accounting_type()
            if not self.api.QueryInformationJobObject(
                self.handle, 1, ctypes.byref(counts), ctypes.sizeof(counts), None
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if counts.active == 0:
                return
            if time.monotonic() >= deadline:
                raise TimeoutError("Task job did not finish termination")
            time.sleep(0.02)

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None

    def detach(self):
        # Successful provider management may leave a provider-owned service.
        # Its lifecycle belongs to the adapter, not the management call.
        limits = self.limits_type()
        if not self.api.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            raise ctypes.WinError(ctypes.get_last_error())


class ProcessTree:
    def __init__(self, command, **kwargs):
        self.job = None
        self.temporary = None
        self.process = None
        try:
            if os.name == "nt":
                self.job = WindowsJob()
                self.temporary = tempfile.TemporaryDirectory(prefix="mc-gate-")
                gate = Path(self.temporary.name) / "start"
                self.process = subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve()), str(gate),
                     *command],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP, **kwargs,
                )
                self.job.assign(self.process.pid)
                gate.touch()
            else:
                self.process = subprocess.Popen(
                    command, start_new_session=True, **kwargs
                )
        except BaseException:
            if self.process is not None:
                self.process.kill()
                self.process.wait()
            self.close()
            raise

    def _signal_group(self, signum):
        deadline = time.monotonic() + 1
        while True:
            try:
                os.killpg(self.process.pid, signum)
                return
            except ProcessLookupError:
                return
            except PermissionError:
                # Darwin can return EPERM for a group containing only a
                # just-exited zombie. Reap/recheck; a persistent denial remains
                # a cleanup failure, never evidence that a process stopped.
                self.process.poll()
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)

    def stop(self, signum=signal.SIGTERM, grace=1.0):
        if self.job:
            # Console control events depend on console attachment. Job cleanup
            # gives deterministic termination for headed and headless callers.
            self.job.terminate()
        else:
            self._signal_group(signum)
            deadline = time.monotonic() + grace
            while time.monotonic() < deadline:
                self.process.poll()
                try:
                    os.killpg(self.process.pid, 0)
                except ProcessLookupError:
                    break
                except PermissionError:
                    pass  # Retry after reaping; _signal_group bounds denial.
                time.sleep(0.02)
            self._signal_group(signal.SIGKILL)
        self.process.wait(timeout=5)

    def close(self, *, detach=False):
        if self.job:
            try:
                if detach:
                    self.job.detach()
            finally:
                self.job.close()
        if self.temporary:
            self.temporary.cleanup()
        if self.process:
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                if stream:
                    stream.close()


def bounded_capture(command, *, timeout, **kwargs):
    tree = ProcessTree(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       stdin=subprocess.DEVNULL, **kwargs)
    completed = False
    try:
        stdout, stderr = tree.process.communicate(timeout=timeout)
        completed = True
        return subprocess.CompletedProcess(command, tree.process.returncode,
                                           stdout, stderr)
    finally:
        try:
            if not completed:
                tree.stop(grace=0.1)
        finally:
            tree.close(detach=completed)


if __name__ == "__main__":
    # Windows-only gate. No workload starts if assignment fails or the parent
    # disappears before opening the gate. The job kills descendants on close.
    gate = Path(sys.argv[1])
    deadline = time.monotonic() + 30
    while not gate.exists():
        if time.monotonic() >= deadline:
            raise SystemExit(1)
        time.sleep(0.01)
    child = subprocess.Popen(sys.argv[2:])
    raise SystemExit(child.wait())
