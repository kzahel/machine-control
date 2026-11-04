#!/usr/bin/python3
"""Bind the private policy child to its actual native parent's lifetime."""
import ctypes
import os
import signal
import sys


def main():
    if len(sys.argv)<3:raise SystemExit('policy_parent_required')
    parent=int(sys.argv[1])
    if parent<=1:raise SystemExit('policy_parent_required')
    # Run after exec in a single-threaded launcher, never in preexec_fn in
    # the resident's threaded process. SIGKILL cannot be deferred by a stuck
    # runtime or its signal handlers. Normal exec preserves this kernel bond.
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(1,signal.SIGKILL,0,0,0)!=0 or os.getppid()!=parent:
        raise SystemExit('policy_parent_unavailable')
    os.execve(sys.argv[2],sys.argv[2:],dict(os.environ))


if __name__=='__main__':main()
