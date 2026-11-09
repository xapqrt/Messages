"""Monotonic clock and boot identity.

Python's time.monotonic() maps to CLOCK_UPTIME_RAW on Darwin, which pauses while
the machine sleeps. Lease expiry must not pause, so this module calls
clock_gettime(CLOCK_MONOTONIC) through libc. The boot id lets a caller refuse
timestamps from a previous boot, because the monotonic origin resets there.
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

CLOCK_MONOTONIC_LINUX = 1
CLOCK_MONOTONIC_DARWIN = 6


class ClockError(RuntimeError):
    pass


class _Timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


class _Timeval(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_int)]


def _clock_id() -> int:
    if sys.platform == "darwin":
        return CLOCK_MONOTONIC_DARWIN
    return CLOCK_MONOTONIC_LINUX


def monotonic_ns() -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    ts = _Timespec()
    rc = libc.clock_gettime(_clock_id(), ctypes.byref(ts))
    if rc != 0:
        errno = ctypes.get_errno()
        raise ClockError(f"clock_gettime failed: errno={errno}")
    return int(ts.tv_sec) * 1_000_000_000 + int(ts.tv_nsec)


def _darwin_boot_id() -> str | None:
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        tv = _Timeval()
        size = ctypes.c_size_t(ctypes.sizeof(tv))
        rc = libc.sysctlbyname(
            b"kern.boottime", ctypes.byref(tv), ctypes.byref(size), None, ctypes.c_size_t(0)
        )
        if rc == 0:
            return f"darwin-{int(tv.tv_sec)}"
    except (OSError, AttributeError):
        pass
    return None


def _linux_boot_id() -> str | None:
    try:
        value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
        return value or None
    except OSError:
        return None


def boot_id() -> str:
    value = _darwin_boot_id() if sys.platform == "darwin" else _linux_boot_id()
    if value:
        return value
    # Derived fallback: stable within a boot, changes across one, but it is not
    # a kernel identifier and callers must not treat it as one.
    return f"derived-{int(time.time() - time.monotonic())}"


@dataclass(frozen=True)
class Clock:
    boot_id: str
    now_ns: int

    @classmethod
    def read(cls) -> Clock:
        return cls(boot_id=boot_id(), now_ns=monotonic_ns())

    def elapsed_ns(self, earlier_ns: int) -> int:
        return self.now_ns - earlier_ns

    def lease_deadline_ns(self, lease_seconds: float) -> int:
        return self.now_ns + int(lease_seconds * 1_000_000_000)


def safe_env() -> dict[str, str]:
    """Environment for child processes: no credentials, stable locale."""
    keep = {"PATH", "HOME", "LANG", "LC_ALL", "TZ", "TMPDIR"}
    return {key: value for key, value in os.environ.items() if key in keep}
