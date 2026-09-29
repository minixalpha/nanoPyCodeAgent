"""Interrupt synchronous work at a wall-clock deadline on POSIX CLI runs."""

from contextlib import contextmanager
import signal
import threading


class DeadlineExceeded(BaseException):
    """A local deadline, which transport and best-effort handlers must not retry."""


def check_deadline_support() -> None:
    if not hasattr(signal, "setitimer") or threading.current_thread() is not threading.main_thread():
        raise ValueError("wall-clock budgets require a POSIX main thread")
    if signal.getitimer(signal.ITIMER_REAL)[0]:
        raise ValueError("wall-clock budgets cannot share an active SIGALRM timer")


@contextmanager
def wall_clock_limit(seconds: float | None):
    """Bound a blocking operation, restoring the caller's signal handler."""
    if seconds is None:
        yield
        return
    if seconds <= 0:
        raise DeadlineExceeded("wall-clock budget exhausted")
    check_deadline_support()
    previous = signal.getsignal(signal.SIGALRM)

    def expire(signum, frame):
        raise DeadlineExceeded("wall-clock budget exhausted")

    signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
