"""Bounded exit of an already-owned fixture, with truthful recovery evidence."""
import subprocess


def finish_owned_process(process, terminate, grace_seconds=15, forced_seconds=10):
    try:
        process.wait(timeout=grace_seconds)
        requested = False
    except subprocess.TimeoutExpired:
        requested = True
        terminate(process)
        process.wait(timeout=forced_seconds)
    return {"gracefulDeadlineExceeded": requested,
            "forcedTerminationRequested": requested, "exitObserved": True}
