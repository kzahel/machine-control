"""Run discovery under an agent-like kill-on-close Windows job.

The test child waits for assignment before launching any commands. Closing the
job after it exits kills any incorrectly retained descendants. The independent
session runner then verifies that the desktop app survived.
"""
import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys


class Limits(ctypes.Structure):
    _fields_ = [("processTime", ctypes.c_int64), ("jobTime", ctypes.c_int64),
                ("flags", wintypes.DWORD), ("minimum", ctypes.c_size_t),
                ("maximum", ctypes.c_size_t), ("active", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD)]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", Limits), ("io", ctypes.c_uint64 * 6),
                ("processMemory", ctypes.c_size_t), ("jobMemory", ctypes.c_size_t),
                ("peakProcess", ctypes.c_size_t), ("peakJob", ctypes.c_size_t)]


def main():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                               ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    child = None
    try:
        limits = ExtendedLimits()
        # KILL_ON_JOB_CLOSE | BREAKAWAY_OK: a representative agent runner that
        # permits deliberately detached applications, but reaps task children.
        limits.basic.flags = 0x2000 | 0x800
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        script = Path(__file__).with_name("discovery.py")
        gate = "import runpy,sys;sys.stdin.readline();sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')"
        child = subprocess.Popen([sys.executable, "-c", gate, str(script), *sys.argv[1:]],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, encoding="utf-8")
        process = kernel.OpenProcess(0x0100 | 0x0001, False, child.pid)
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not kernel.AssignProcessToJobObject(job, process):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(process)
        output, error = child.communicate("run\n", timeout=100)
        sys.stdout.write(output)
        sys.stderr.write(error)
        return child.returncode
    finally:
        kernel.CloseHandle(job)
        if child is not None and child.poll() is None:
            child.kill()
            child.communicate()


if __name__ == "__main__":
    raise SystemExit(main())
